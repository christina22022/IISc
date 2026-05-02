import dash
from dash import html, dcc, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import os
import re
import threading
import time
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# LIVE AQI / HUMIDITY SCRAPER  (aqi.in — Bangalore)
# ══════════════════════════════════════════════════════════════════════════════

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPER_AVAILABLE = True
except ImportError:
    _SCRAPER_AVAILABLE = False
    print("[WARN] requests / beautifulsoup4 not installed. "
          "Install with: pip install requests beautifulsoup4\n"
          "Falling back to Google Sheet air_quality data.")

_LIVE_AQI_CACHE = {"aqi": None, "humidity": None, "fetched_at": None}
_LIVE_AQI_LOCK  = threading.Lock()

_AQI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_first_number(text):
    """Return first integer found in text, or None."""
    m = re.search(r"\d+", str(text))
    return int(m.group()) if m else None


def _scrape_aqi_in():
    """
    Scrape live AQI and humidity for Bangalore from aqi.in.
    Returns (aqi_int_or_None, humidity_int_or_None).
    """
    aqi_val = None
    hum_val = None

    if not _SCRAPER_AVAILABLE:
        return aqi_val, hum_val

    # ── 1. AQI page ──────────────────────────────────────────────────────────
    try:
        resp = requests.get(
            "https://www.aqi.in/in/dashboard/india/karnataka/bangalore",
            headers=_AQI_HEADERS,
            timeout=12,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # Strategy A: look for the large AQI number in a known class pattern
            # aqi.in renders a big number with class containing "aqi-value", "liveAqi", etc.
            for selector in [
                "[class*='liveAqi']",
                "[class*='aqi-value']",
                "[class*='AqiValue']",
                "[class*='aqiValue']",
                "[class*='live-aqi']",
            ]:
                el = soup.select_one(selector)
                if el:
                    val = _parse_first_number(el.get_text())
                    if val and 1 <= val <= 500:
                        aqi_val = val
                        break

            # Strategy B: scan <script> tags for JSON-like AQI field
            if aqi_val is None:
                for script in soup.find_all("script"):
                    txt = script.string or ""
                    # e.g. "aqi":122 or "aqiValue":135
                    m = re.search(r'"aqi(?:Value)?"\s*:\s*(\d+)', txt, re.I)
                    if m:
                        val = int(m.group(1))
                        if 1 <= val <= 500:
                            aqi_val = val
                            break

            # Strategy C: find the first standalone large number near "AQI" text
            if aqi_val is None:
                page_text = soup.get_text(separator=" ")
                # Look for pattern: "Live AQI  122" or "AQI 135"
                m = re.search(
                    r"(?:Live\s+AQI|AQI\s*\(US\)|AQI)\s*[:\-]?\s*(\d{1,3})\b",
                    page_text, re.I
                )
                if m:
                    val = int(m.group(1))
                    if 1 <= val <= 500:
                        aqi_val = val

            # Strategy D: look for humidity on the AQI dashboard page too
            if hum_val is None:
                page_text = soup.get_text(separator=" ")
                m = re.search(
                    r"[Hh]umidity\s*[:\-]?\s*(\d{1,3})\s*%",
                    page_text
                )
                if m:
                    val = int(m.group(1))
                    if 0 <= val <= 100:
                        hum_val = val

    except Exception as e:
        print(f"[WARN] AQI page scrape failed: {e}")

    # ── 2. Weather page (for humidity if not yet found) ───────────────────────
    if hum_val is None:
        try:
            resp2 = requests.get(
                "https://www.aqi.in/weather/in/india/karnataka/bangalore",
                headers=_AQI_HEADERS,
                timeout=12,
            )
            if resp2.status_code == 200:
                soup2 = BeautifulSoup(resp2.text, "html.parser")

                # Strategy A: class-based selector
                for selector in [
                    "[class*='humidity']",
                    "[class*='Humidity']",
                ]:
                    el = soup2.select_one(selector)
                    if el:
                        val = _parse_first_number(el.get_text())
                        if val and 0 <= val <= 100:
                            hum_val = val
                            break

                # Strategy B: scan scripts
                if hum_val is None:
                    for script in soup2.find_all("script"):
                        txt = script.string or ""
                        m = re.search(r'"humidity"\s*:\s*(\d+)', txt, re.I)
                        if m:
                            val = int(m.group(1))
                            if 0 <= val <= 100:
                                hum_val = val
                                break

                # Strategy C: text pattern
                if hum_val is None:
                    page_text2 = soup2.get_text(separator=" ")
                    m = re.search(
                        r"[Hh]umidity\s*[:\-]?\s*(\d{1,3})\s*%",
                        page_text2
                    )
                    if m:
                        val = int(m.group(1))
                        if 0 <= val <= 100:
                            hum_val = val

                # Strategy D: also grab AQI from weather page if still missing
                if aqi_val is None:
                    page_text2 = soup2.get_text(separator=" ")
                    m = re.search(r"\bAQI\b\s*[:\-]?\s*(\d{1,3})\b", page_text2)
                    if m:
                        val = int(m.group(1))
                        if 1 <= val <= 500:
                            aqi_val = val

        except Exception as e:
            print(f"[WARN] Weather page scrape failed: {e}")

    return aqi_val, hum_val


def fetch_live_aqi_humidity(force=False):
    """
    Return (aqi_str, humidity_str) from live scrape.
    Results are cached for 10 minutes unless force=True.
    Returns (None, None) on failure so callers can fall back to sheet data.
    """
    global _LIVE_AQI_CACHE

    with _LIVE_AQI_LOCK:
        now = time.time()
        cache_age = now - (_LIVE_AQI_CACHE["fetched_at"] or 0)
        if not force and _LIVE_AQI_CACHE["fetched_at"] and cache_age < 600:
            return _LIVE_AQI_CACHE["aqi"], _LIVE_AQI_CACHE["humidity"]

       # print("[INFO] Fetching live AQI/humidity from aqi.in …")
        aqi_val, hum_val = _scrape_aqi_in()

        _LIVE_AQI_CACHE["aqi"]        = str(aqi_val)  if aqi_val  is not None else None
        _LIVE_AQI_CACHE["humidity"]   = str(hum_val)  if hum_val  is not None else None
        _LIVE_AQI_CACHE["fetched_at"] = now

       # if aqi_val is None:
     #     print(f"[INFO] Live AQI={aqi_val}  Humidity={hum_val}")
     #   else:
      #      print("[WARN] Live AQI scrape returned no value — will use sheet data.")

       # return _LIVE_AQI_CACHE["aqi"], _LIVE_AQI_CACHE["humidity"]


# Pre-warm the cache at startup (non-blocking)
def _warm_cache():
    try:
        fetch_live_aqi_humidity(force=True)
    except Exception:
        pass

threading.Thread(target=_warm_cache, daemon=True).start()


app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "One Health Dashboard — Bettahalasuru"

# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS CONFIG
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={tab}"

SHEETS = {
    "human_id":   "1kMzWtBm-cKM8kQLgGRnfCQS8_cxizlTm",
    "animal_id":  "1hmixQht8zdETU0vA3w1-bduZeRqdp-2m",
    "env_id":     "1AGIFjGQy4Y2hpMjF-ZwfW5OVAOVMU04y",
    "inter_id":   "1uYM6V-usylcrgVyD57J7stv-NGUKchBK",
    "overview_id":"19gLj_SxcjJCwppnn1Y7q_2MmXzdG_-ik",
}

TABS = {
    # ───────── HUMAN ─────────
    "kpi_data":                ("human_id", "kpi_data"),
    "disease_insights":        ("human_id", "disease_insights"),
    "majorDiseases":           ("human_id", "majorDiseases"),
    "diseaseBurden":           ("human_id", "diseaseBurden"),
    "vectorInsights":          ("human_id", "vectorInsights"),
    "vectorDiseaseTrend":      ("human_id", "vectorDiseaseTrend"),
    "phcScreeningPrograms":    ("human_id", "phcScreeningPrograms"),
    "humanHealthMaster":       ("human_id", "humanHealthMaster"),

    # ───────── ANIMAL ─────────
    "animal_kpi_data":         ("animal_id", "animal_kpi_data"),
    "abcProgram":              ("animal_id", "abcProgram"),
    "rabiesProjection":        ("animal_id", "rabiesProjection"),
    "amrFindings":             ("animal_id", "amrFindings"),
    "antibioticLevels":        ("animal_id", "antibioticLevels"),
    "animalInsights":          ("animal_id", "animalInsights"),

    # ───────── ENVIRONMENT ─────────
    "final_waterQuality_complete": ("env_id", "final_waterQuality_complete"),
    "lake_full_integration":       ("env_id", "lake_full_integration"),
    "gram_staining_data":          ("env_id", "gram_staining_data"),
    "gram_staining_total":         ("env_id", "gram_staining_total"),
    "Doxy_Calibration":            ("env_id", "Doxy_Calibration"),
    "Amox_Calibration":            ("env_id", "Amox_Calibration"),
    "Amox_Samples":                ("env_id", "Amox_Samples"),
    "Doxy_Samples":                ("env_id", "Doxy_Samples"),
    "AMR_Summary_Dashboard":       ("env_id", "AMR_Summary_Dashboard"),
    "air_quality":                 ("env_id", "air_quality"),
    "soil_data":                   ("env_id", "soil_data"),
    "soil_cfu":                    ("env_id", "soil_cfu"),

    # ───────── INTERCONNECTED ─────────
    "riskMatrix":            ("inter_id", "riskMatrix"),
    "zoonoticTransmission":  ("inter_id", "zoonoticTransmission"),
    "rainfallDisease":       ("inter_id", "rainfallDisease"),
    "crossPillarIndex":      ("inter_id", "crossPillarIndex"),
    "interactionStrength":   ("inter_id", "interactionStrength"),
    "projectedOutcome":      ("inter_id", "projectedOutcome"),

    # ───────── OVERVIEW ─────────
    "onehealth_summary":     ("overview_id", "onehealth_summary"),
    "onehealth_risk":        ("overview_id", "onehealth_risk"),
}

BASE = os.path.dirname(os.path.abspath(__file__))
DDIR = os.path.join(BASE, "data")
LOCAL = {
    "human_id":    os.path.join(DDIR, "human.xlsx"),
    "animal_id":   os.path.join(DDIR, "animal.xlsx"),
    "env_id":      os.path.join(DDIR, "Environment.xlsx"),
    "inter_id":    os.path.join(DDIR, "interconnectedness.xlsx"),
    "overview_id": os.path.join(DDIR, "overview.xlsx"),
}


def fetch(tab_name):
    sid_key, tab = TABS[tab_name]
    sheet_id = SHEETS[sid_key]
    if sheet_id and not sheet_id.startswith("YOUR_"):
        try:
            url = BASE_URL.format(sheet_id=sheet_id, tab=tab)
            df = pd.read_csv(url)
            return df
        except Exception as e:
            print(f"[WARN] Google Sheets fetch failed for {tab_name}: {e}. Falling back to local.")
    local_path = LOCAL.get(sid_key)
    if not local_path:
        raise FileNotFoundError(f"No local fallback configured for key: {sid_key}")
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local fallback file not found: {local_path}")
    return pd.read_excel(local_path, sheet_name=tab)
#────────────────────────────────────────────────────────────────────────────
#-----------CHAT BOT----------------------------------------------------------------------------------------------------------------------------------------------------
#────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are ONE Health Bot, a friendly and helpful assistant for the One Health Dashboard of Bettahalasuru village, Karnataka.\n"
    "You were built to help users understand health data about this village in a warm, conversational and informative way.\n"
    "STRICT RULES - follow these always:\n"
    "1. NEVER share, mention, or hint at any Google Sheets links, spreadsheet URLs, or data source links.\n"
    "2. NEVER mention words like Google Sheets, spreadsheet, Excel, dataset, database, data source, sheet, csv, or any technical storage terms.\n"
    "3. If anyone asks for data sources, links, or where data comes from, respond with exactly: I am not able to provide that.\n"
    "4. NEVER use ** for bold or any markdown formatting like *, #, __, etc.\n"
    "5. When listing items always put each item on its own line starting with a number or dash. Never write a list as a single paragraph.\n"
    "6. Focus only on One Health topics: human health, animal health, environment, and their connections in Bettahalasuru.\n"
    "7. When user says hi, hello, hey or any greeting — respond in a friendly warm way and invite them to ask about the dashboard.\n"
      " - NEVER start your reply with Hello or Hi if the conversation has already started.\n"
    "8. NEVER add a second paragraph asking follow-up questions like 'Would you like to know more?' or 'I am here to help'. Give the answer and stop. One paragraph only.\n"
    "9. NEVER say things like 'I am so glad you are here' or 'lovely village' or any overly enthusiastic phrases. Be calm, helpful and direct.\n"
    "10. When user sends short positive words like ok, done, good, great, thanks, thank you, nice, cool, perfect — reply with a short warm acknowledgement like Sure, Glad to help, Anytime, Let me know. Nothing more.\n"
    "11. When user sends short negative words like no, nope, not really — reply briefly and politely like Alright, let me know if you need anything.\n"
    "12. NEVER say No answer available or I do not know. If you are unsure, say I do not have enough data on that right now, please check with the health team.\n"    
    "13. Always be warm, polite and conversational like a helpful village health assistant.\n"
    "14. ALWAYS answer exactly what the user asked. If they ask for one specific number, give that exact number first. Never replace it with a different but related number.\n"
    "15. First sentence must directly answer only what was asked. Match the question to the exact data field. Never use a related or similar number as a substitute.\n"
)


def build_prompt(user_question, history=None):
    try:
        # ── HUMAN DATA ──────────────────────────────────────────────────
        # kpi_data columns: location, totalPopulation, malePopulation,
        #   femalePopulation, phcServices, household
        kpi_df = DATA.get("kpi_data", pd.DataFrame())
        population   = kpi_val_from_wide(kpi_df, ["totalPopulation"], "N/A")
        male_pop     = kpi_val_from_wide(kpi_df, ["malePopulation"], "N/A")
        female_pop   = kpi_val_from_wide(kpi_df, ["femalePopulation"], "N/A")
        phc_services = kpi_val_from_wide(kpi_df, ["phcServices"], "N/A")
        households   = kpi_val_from_wide(kpi_df, ["household"], "N/A")

        # majorDiseases columns: disease, cases
        md_df = DATA.get("majorDiseases", pd.DataFrame())
        major_diseases = "N/A"
        if not md_df.empty and "disease" in md_df.columns and "cases" in md_df.columns:
            major_diseases = "\n".join(
                f"  {row['disease']}: {row['cases']} cases"
                for _, row in md_df.iterrows()
                if pd.notna(row["disease"])
            )

        # diseaseBurden columns: diseaseCategory, value, note
        db_df = DATA.get("diseaseBurden", pd.DataFrame())
        disease_burden = "N/A"
        if not db_df.empty:
            disease_burden = "\n".join(
                f"  {row['diseaseCategory']}: score {row['value']} — {row['note']}"
                for _, row in db_df.iterrows()
                if pd.notna(row.get("diseaseCategory"))
            )

        # vectorInsights columns: disease, casesRange, insight
        vi_df = DATA.get("vectorInsights", pd.DataFrame())
        vector_insights = "N/A"
        if not vi_df.empty:
            vector_insights = "\n".join(
                f"  {row['disease']}: {row['casesRange']} cases — {row['insight']}"
                for _, row in vi_df.iterrows()
                if pd.notna(row.get("disease"))
            )

        # vectorDiseaseTrend columns: year, malaria, dengue, chikungunya, leptospirosis
        vt_df = DATA.get("vectorDiseaseTrend", pd.DataFrame())
        vector_trend = "N/A"
        if not vt_df.empty:
            vector_trend = vt_df.to_string(index=False)

        # phcScreeningPrograms columns: screeningType, frequency, status
        sc_df = DATA.get("phcScreeningPrograms", pd.DataFrame())
        screening = "N/A"
        if not sc_df.empty:
            screening = "\n".join(
                f"  {row['screeningType']}: {row['frequency']} — {row['status']}"
                for _, row in sc_df.iterrows()
                if pd.notna(row.get("screeningType"))
            )

        # ── ANIMAL DATA ─────────────────────────────────────────────────
        # animal_kpi_data columns: location, strayDogs, abcProgramCount,
        #   rabiesInfectionReductionPercent, livestockMonitored, avianSpecies
        akpi_df = DATA.get("animal_kpi_data", pd.DataFrame())
        stray_dogs   = kpi_val_from_wide(akpi_df, ["strayDogs"], "N/A")
        abc_count    = kpi_val_from_wide(akpi_df, ["abcProgramCount"], "N/A")
        rabies_rate  = kpi_val_from_wide(akpi_df, ["rabiesInfectionReductionPercent"], "N/A")
        livestock    = kpi_val_from_wide(akpi_df, ["livestockMonitored"], "N/A")
        avian        = kpi_val_from_wide(akpi_df, ["avianSpecies"], "N/A")

        # abcProgram columns: date, activity, count
        abc_df = DATA.get("abcProgram", pd.DataFrame())
        abc_program = "N/A"
        if not abc_df.empty:
            abc_program = "\n".join(
                f"  {row['date']}: {row['activity']} — {row['count']}"
                for _, row in abc_df.iterrows()
                if pd.notna(row.get("activity"))
            )

        # rabiesProjection columns: year, noAbc, withAbc, withAbcVaccination
        rp_df = DATA.get("rabiesProjection", pd.DataFrame())
        rabies_proj = "N/A"
        if not rp_df.empty:
            rabies_proj = rp_df.to_string(index=False)

        # amrFindings columns: antibiotic, sampleType, levelFound, permissible, status
        amr_df = DATA.get("amrFindings", pd.DataFrame())
        amr_findings = "N/A"
        if not amr_df.empty:
            amr_findings = "\n".join(
                f"  {row['antibiotic']} in {row['sampleType']}: {row['levelFound']} (limit {row['permissible']}) — {row['status']}"
                for _, row in amr_df.iterrows()
                if pd.notna(row.get("antibiotic"))
            )

        # animalInsights columns: insight
        ai_df = DATA.get("animalInsights", pd.DataFrame())
        animal_insights = "N/A"
        if not ai_df.empty and "insight" in ai_df.columns:
            animal_insights = "\n".join(
                f"  - {row['insight']}"
                for _, row in ai_df.iterrows()
                if pd.notna(row.get("insight"))
            )

        # ── ENVIRONMENT DATA ─────────────────────────────────────────────
        # air_quality columns: parameter, value, unit, interpretation
        aq_df = DATA.get("air_quality", pd.DataFrame())
        aqi = humidity = "N/A"
        if not aq_df.empty and "parameter" in aq_df.columns and "value" in aq_df.columns:
            for _, row in aq_df.iterrows():
                p = str(row["parameter"]).strip().upper()
                v = str(row["value"]).strip()
                interp = str(row.get("interpretation", "")).strip()
                if p == "AQI":
                    aqi = f"{v} ({interp})"
                elif p == "HUMIDITY":
                    humidity = f"{v}% ({interp})"

        # final_waterQuality_complete columns: sampleId, sourceName, pH,
        #   EC_uS, TDS_ppm, DO_mg_L, turbidity_NTU, drinkingStatus
        wq_df = DATA.get("water_quality", pd.DataFrame())
        water_quality = "N/A"
        if not wq_df.empty:
            water_quality = "\n".join(
                f"  {row.get('sampleId','')}: {row.get('sourceName','')} | "
                f"pH {row.get('pH','')} | TDS {row.get('TDS_ppm','')} ppm | "
                f"DO {row.get('DO_mg_L','')} mg/L | Status: {row.get('drinkingStatus','')}"
                for _, row in wq_df.iterrows()
                if pd.notna(row.get("sourceName"))
            )

        # gram_staining_total columns: total_isolates, gram_negative_percent,
        #   bacillus_percent, cocci_percent, mucoid_layer_percent
        gram_df = DATA.get("gram_staining_total", pd.DataFrame())
        gram_data = "N/A"
        if not gram_df.empty:
            row = gram_df.iloc[0]
            gram_data = (
                f"  Total isolates: {row.get('total_isolates','N/A')}\n"
                f"  Gram negative: {row.get('gram_negative_percent','N/A')}%\n"
                f"  Bacillus: {row.get('bacillus_percent','N/A')}%\n"
                f"  Cocci: {row.get('cocci_percent','N/A')}%\n"
                f"  Mucoid layer: {row.get('mucoid_layer_percent','N/A')}%"
            )

        # soil_data columns: site_id, site_name, na_growth_10_2,
        #   colony_count_10_6, e_coli_present
        raw_soil = DATA.get("soil_data", pd.DataFrame())
        soil_data = "N/A"
        if not raw_soil.empty and "site_name" in raw_soil.columns:
            soil_data = "\n".join(
                f"  {row['site_name']}: colony count {row.get('colony_count_10_6','N/A')} | E.coli: {row.get('e_coli_present','N/A')}"
                for _, row in raw_soil.iterrows()
                if pd.notna(row.get("site_name"))
            )

        # soil_cfu columns: Sample, CFU(Replicate1), CFU( Replicate 2),
        #   CFU(replicate3), CFU avg
        sc_cfu_df = DATA.get("soil_cfu", pd.DataFrame())
        soil_cfu = "N/A"
        if not sc_cfu_df.empty:
            s_col   = find_col(sc_cfu_df, ["sample", "Sample"])
            avg_col = find_col(sc_cfu_df, ["CFU avg", "mean_cfu"])
            if s_col and avg_col:
                soil_cfu = "\n".join(
                    f"  {row[s_col]}: {row[avg_col]} CFU/mL"
                    for _, row in sc_cfu_df.iterrows()
                    if pd.notna(row.get(s_col))
                )

        # ── INTERCONNECTIONS DATA ────────────────────────────────────────
        # riskMatrix columns: factor, likelihood, impact, urgency
        rm_df = DATA.get("riskMatrix", pd.DataFrame())
        risk_matrix = "N/A"
        if not rm_df.empty:
            risk_matrix = "\n".join(
                f"  {row['factor']}: likelihood {row['likelihood']}% | impact {row['impact']} | urgency {row['urgency']}"
                for _, row in rm_df.iterrows()
                if pd.notna(row.get("factor"))
            )

        # zoonoticTransmission columns: pathway, directContact, environmental,
        #   foodWater, vectorMediated
        zoo_df = DATA.get("zoonoticTransmission", pd.DataFrame())
        zoonotic = "N/A"
        if not zoo_df.empty:
            zoonotic = "\n".join(
                f"  {row['pathway']}: direct {row.get('directContact',0)}% | env {row.get('environmental',0)}% | food/water {row.get('foodWater',0)}% | vector {row.get('vectorMediated',0)}%"
                for _, row in zoo_df.iterrows()
                if pd.notna(row.get("pathway"))
            )

        # rainfallDisease columns: year, rainfallIndex, dengueCases,
        #   malariaCases, leptospirosis
        rd_df = DATA.get("rainfallDisease", pd.DataFrame())
        rainfall_disease = "N/A"
        if not rd_df.empty:
            rainfall_disease = rd_df.to_string(index=False)

        # interactionStrength columns: interaction, current, afterIntervention
        ints_df = DATA.get("interactionStrength", pd.DataFrame())
        interaction = "N/A"
        if not ints_df.empty:
            interaction = "\n".join(
                f"  {row['interaction']}: current {row['current']} → after intervention {row['afterIntervention']}"
                for _, row in ints_df.iterrows()
                if pd.notna(row.get("interaction"))
            )

        # projectedOutcome columns: year, noIntervention, partial, fullOneHealth
        proj_df = DATA.get("projectedOutcome", pd.DataFrame())
        projected = "N/A"
        if not proj_df.empty:
            projected = proj_df.to_string(index=False)

        # onehealth_summary columns: category, score
        oh_sum_df = DATA.get("onehealth_summary", pd.DataFrame())
        oh_summary = "N/A"
        if not oh_sum_df.empty:
            oh_summary = oh_sum_df.to_string(index=False)

        # onehealth_risk columns: indicator, level, description
        oh_risk_df = DATA.get("onehealth_risk", pd.DataFrame())
        oh_risk = "N/A"
        if not oh_risk_df.empty:
            oh_risk = oh_risk_df.to_string(index=False)

    except Exception as e:
        print(f"[build_prompt error] {e}")

    # ── CONVERSATION HISTORY ─────────────────────────────────────────────
    history_text = ""
    if history:
        for msg in history[-6:]:
            role = "User" if msg.get("role") == "user" else "Bot"
            history_text += f"{role}: {msg.get('text', '')}\n"

    context = f"""
{SYSTEM_PROMPT}

RESPONSE FORMAT REMINDER - STRICTLY FOLLOW:
- Write the direct fact or number in the first sentence.
- Write one sentence of context below it separated by a blank line.
- Use ONLY the exact numbers from the data below. Never guess or calculate.
- Never write the words line or part in your response.
- Stop after 2 sentences total.

━━━ LIVE DATA FROM BETTAHALASURU DASHBOARD ━━━

── HUMAN HEALTH ──
Total Population    : {population}
Male Population     : {male_pop}
Female Population   : {female_pop}
Households          : {households}
PHC Services        : {phc_services}

Major Diseases (PHC cases):
{major_diseases}

Disease Burden Scores:
{disease_burden}

Vector Disease Insights:
{vector_insights}

Vector Disease Trend by Year:
{vector_trend}

PHC Screening Programs:
{screening}

── ANIMAL HEALTH ──
Stray Dogs          : {stray_dogs}
ABC Programme Count : {abc_count}
Rabies Reduction    : {rabies_rate}
Livestock Monitored : {livestock}
Avian Species       : {avian}

ABC Programme Activity:
{abc_program}

Rabies 5-Year Projection:
{rabies_proj}

AMR Antibiotic Findings:
{amr_findings}

Animal Health Insights:
{animal_insights}

── ENVIRONMENT ──
Air Quality Index   : {aqi}
Humidity            : {humidity}

Village Water Quality:
{water_quality}

Gram Staining Summary:
{gram_data}

Soil Site Data:
{soil_data}

Soil CFU Data:
{soil_cfu}

── INTERCONNECTIONS ──
Risk Matrix:
{risk_matrix}

Zoonotic Transmission Pathways:
{zoonotic}

Rainfall vs Disease (by year):
{rainfall_disease}

Cross-Pillar Interaction Strength:
{interaction}

Projected Health Outcomes:
{projected}

── ONE HEALTH OVERVIEW ──
Surveillance Scores:
{oh_summary}

Risk Indicators:
{oh_risk}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── CONVERSATION SO FAR ──
{history_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

User: {user_question}
Bot:"""
    return context
def ask_ollama(user_question):
    prompt = build_prompt(user_question)
    try:
        response = requests.post(
            "http://172.25.32.117:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 200,
                    "temperature": 0.6,
                    "top_p": 0.9,
                }
            },
            timeout=120
        )
        return response.json().get("response", "Sorry, I could not get a response.")
    except requests.exceptions.Timeout:
        return "⏱️ The model took too long to respond. Please try again with a shorter question."
    except requests.exceptions.ConnectionError:
        return "❌ Could not connect to Ollama. Please make sure Ollama is running."
    except Exception as e:
        return f"⚠️ Something went wrong: {str(e)}"
    

#___________________________________________________________________________________________________________________________________________________________________________
#---------------------------------------------------------------------------------------------------------------------------------------------------------------
def safe_mean_cfu(df, name_col):
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    label_col = find_col(out, [name_col, "source", "source_name", "sourceName", "sample", "Sample", "location", "site_name"])
    mean_col = find_col(out, ["mean_cfu", "CFU_avg", "CFU avg", "cfu_avg", "cfuavg", "colony_count_10_6", "na_plate_count"])
    if label_col and mean_col:
        result = out[[label_col, mean_col]].copy()
        result.columns = [name_col, "mean_cfu"]
        result["mean_cfu"] = pd.to_numeric(result["mean_cfu"], errors="coerce")
        return result.dropna(subset=[name_col, "mean_cfu"])

    rep_cols = [
        find_col(out, ["rep1", "CFU(Replicate1)", "CFU Replicate1"]),
        find_col(out, ["rep2", "CFU( Replicate 2)", "CFU(Replicate2)", "CFU Replicate2"]),
        find_col(out, ["rep3", "CFU(replicate3)", "CFU Replicate3"]),
    ]
    if label_col and all(rep_cols):
        result = out[[label_col] + rep_cols].copy()
        result.columns = [name_col, "rep1", "rep2", "rep3"]
        for col in ["rep1", "rep2", "rep3"]:
            result[col] = pd.to_numeric(result[col], errors="coerce")
        result["mean_cfu"] = result[["rep1", "rep2", "rep3"]].mean(axis=1).round(3)
        return result.dropna(subset=[name_col, "mean_cfu"])

    expected = [name_col, "rep1", "rep2", "rep3"]
    if len(out.columns) >= 4:
        result = out.iloc[:, :4].copy()
        result.columns = expected
        for col in ["rep1", "rep2", "rep3"]:
            result[col] = pd.to_numeric(result[col], errors="coerce")
        result["mean_cfu"] = result[["rep1", "rep2", "rep3"]].mean(axis=1).round(3)
        return result.dropna(subset=[name_col, "mean_cfu"])

    return pd.DataFrame(columns=[name_col, "mean_cfu"])


def normalize_key(value):
    return "".join(ch.lower() for ch in str(value).strip() if ch.isalnum())


def find_col(df, candidates):
    if df is None or df.empty:
        return None
    col_map = {normalize_key(col): col for col in df.columns}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in col_map:
            return col_map[key]
    return None


def coerce_numeric(df, columns):
    out = df.copy()
    for col in columns:
        if col and col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def lookup_kpi_value(df, labels, default):
    name_col = find_col(df, ["metric", "name", "kpi", "field"])
    value_col = find_col(df, ["value", "score"])
    if not name_col or not value_col:
        return default

    label_keys = {normalize_key(label) for label in labels}
    temp = df[[name_col, value_col]].copy()
    temp["_metric_key"] = temp[name_col].map(normalize_key)
    match = temp[temp["_metric_key"].isin(label_keys)]
    if match.empty:
        return default
    value = match[value_col].iloc[0]
    return default if pd.isna(value) else str(value)


def kpi_val_from_wide(df, field_names, default="—"):
    """
    Look up a value from a WIDE (transposed) single-row KPI DataFrame.
    Returns the RAW string value without averaging ranges or stripping suffixes.
    """
    if df is None or df.empty:
        return default
    col_map = {normalize_key(col): col for col in df.columns}
    for fname in field_names:
        key = normalize_key(fname)
        if key in col_map:
            actual_col = col_map[key]
            val = df[actual_col].iloc[0]
            if pd.notna(val) and str(val).strip() not in ("", "nan"):
                return str(val).strip()
    return default


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2 & 3: Gram staining parser — reads wide-format gram_staining_total
# and also counts from gram_staining_data if total sheet is unavailable
# ══════════════════════════════════════════════════════════════════════════════

def parse_gram_staining(d):
    gt = d.get("gram_staining_total", pd.DataFrame())
    gsd = d.get("gram_staining_data", pd.DataFrame())

    result = {
        "total_isolates": 0,
        "gram_neg_pct": 0.0,
        "gram_neg_count": 0,
        "bacillus_pct": 0.0,
        "cocci_pct": 0.0,
        "mucoid_pct": 0.0,
    }

    if not gt.empty:

        ti_col   = find_col(gt, ["total_isolates", "totalIsolates", "total isolates", "isolates"])
        gnp_col  = find_col(gt, ["gram_negative_percent", "gramNegativePercent", "gram negative percent",
                                  "gram_neg_pct", "gramNegPct"])
        bac_col  = find_col(gt, ["bacillus_percent", "bacillusPercent", "bacillus percent", "bacillus"])
        coc_col  = find_col(gt, ["cocci_percent", "cocciPercent", "cocci percent", "cocci"])
        muc_col  = find_col(gt, ["mucoid_layer_percent", "mucoidLayerPercent", "mucoid layer percent",
                                  "mucoid percent", "mucoid"])

        if ti_col:
            val = pd.to_numeric(gt[ti_col].iloc[0], errors="coerce")
            if pd.notna(val):
                result["total_isolates"] = int(val)

        if gnp_col:
            val = pd.to_numeric(gt[gnp_col].iloc[0], errors="coerce")
            if pd.notna(val):
                result["gram_neg_pct"] = float(val)

        if bac_col:
            val = pd.to_numeric(gt[bac_col].iloc[0], errors="coerce")
            if pd.notna(val):
                result["bacillus_pct"] = float(val)

        if coc_col:
            val = pd.to_numeric(gt[coc_col].iloc[0], errors="coerce")
            if pd.notna(val):
                result["cocci_pct"] = float(val)

        if muc_col:
            val = pd.to_numeric(gt[muc_col].iloc[0], errors="coerce")
            if pd.notna(val):
                result["mucoid_pct"] = float(val)

        if ti_col and gnp_col:
            result["gram_neg_count"] = int(round(result["total_isolates"] * result["gram_neg_pct"] / 100))
            return result

        if len(gt.columns) >= 2:
            print(f"[WARN] gram_staining_total: could not find metric/value columns by name, trying positional read")
            cols = list(gt.columns)
            row0 = gt.iloc[0]
            for i, c in enumerate(cols):
                ck = normalize_key(c)
                if "total" in ck or "isolate" in ck:
                    val = pd.to_numeric(row0.iloc[i], errors="coerce")
                    if pd.notna(val):
                        result["total_isolates"] = int(val)
                elif "gramneg" in ck or "gramnega" in ck or "negative" in ck:
                    val = pd.to_numeric(row0.iloc[i], errors="coerce")
                    if pd.notna(val):
                        result["gram_neg_pct"] = float(val)
                elif "bacill" in ck:
                    val = pd.to_numeric(row0.iloc[i], errors="coerce")
                    if pd.notna(val):
                        result["bacillus_pct"] = float(val)
                elif "cocci" in ck:
                    val = pd.to_numeric(row0.iloc[i], errors="coerce")
                    if pd.notna(val):
                        result["cocci_pct"] = float(val)
                elif "mucoid" in ck:
                    val = pd.to_numeric(row0.iloc[i], errors="coerce")
                    if pd.notna(val):
                        result["mucoid_pct"] = float(val)

            if result["total_isolates"] > 0:
                result["gram_neg_count"] = int(round(result["total_isolates"] * result["gram_neg_pct"] / 100))
                return result

    if not gsd.empty:
        stain_col = find_col(gsd, ["gram_stain", "gramStain", "stain", "result", "gram stain", "type"])
        total_rows = len(gsd.dropna(how="all"))
        result["total_isolates"] = total_rows

        if stain_col:
            stain_vals = gsd[stain_col].astype(str).str.strip().str.lower()
            neg_count = stain_vals.str.contains("negative|gram.neg|gram neg", na=False).sum()
            pos_count = stain_vals.str.contains("positive|gram.pos|gram pos", na=False).sum()
            if neg_count + pos_count > 0:
                result["gram_neg_count"] = int(neg_count)
                result["gram_neg_pct"] = round(neg_count / (neg_count + pos_count) * 100, 2)
            else:
                result["gram_neg_count"] = total_rows
                result["gram_neg_pct"] = 100.0

        morph_col = find_col(gsd, ["morphology", "shape", "colony_morphology", "colony morphology"])
        if morph_col:
            morph_vals = gsd[morph_col].astype(str).str.strip().str.lower()
            bac_count = morph_vals.str.contains("bacill|rod", na=False).sum()
            coc_count = morph_vals.str.contains("cocc|sphere|spherical", na=False).sum()
            if total_rows > 0:
                result["bacillus_pct"] = round(bac_count / total_rows * 100, 2)
                result["cocci_pct"] = round(coc_count / total_rows * 100, 2)

        mucoid_col = find_col(gsd, ["mucoid", "capsule", "mucoid_layer"])
        if mucoid_col:
            muc_vals = gsd[mucoid_col].astype(str).str.strip().str.lower()
            muc_count = muc_vals.str.contains("yes|present|true|mucoid", na=False).sum()
            if total_rows > 0:
                result["mucoid_pct"] = round(muc_count / total_rows * 100, 2)


    return result


def load_all():
    d = {}

    for t in TABS.keys():
        try:
            df = fetch(t)

            if not isinstance(df, pd.DataFrame):
                try:
                    df = pd.DataFrame(df)
                except Exception:
                    df = pd.DataFrame()

            if t == "gram_staining_total":
                def clean_val(x):
                    if isinstance(x, str):
                        x = x.strip().replace("%", "")
                    return x
                for col in df.columns:
                    df[col] = df[col].apply(clean_val)
                d[t] = df
                continue

            # ── For majorDiseases: do NOT transpose — it is already a tall table
            #    with columns: disease, cases
            if t == "majorDiseases":
                def clean_val_md(x):
                    if isinstance(x, str):
                        x = x.strip().replace("%", "")
                    return x
                for col in df.columns:
                    df[col] = df[col].apply(clean_val_md)
                d[t] = df
                continue

            # ── For disease_insights: do NOT transpose — tall table
            #    with columns: disease, metric, value, notes
            if t == "disease_insights":
                def clean_val_di(x):
                    if isinstance(x, str):
                        x = x.strip().replace("%", "")
                    return x
                for col in df.columns:
                    df[col] = df[col].apply(clean_val_di)
                d[t] = df
                
                continue

            if df.shape[1] == 2:
                try:
                    df = df.set_index(df.columns[0]).T.reset_index(drop=True)
                except Exception:
                    pass

            def clean_val(x):
                if isinstance(x, str):
                    x = x.strip()
                    x = x.replace("%", "")
                return x

            for col in df.columns:
                df[col] = df[col].apply(clean_val)

            d[t] = df

        except Exception as e:
            print(f"[ERROR] Could not load {t}: {e}")
            d[t] = pd.DataFrame()

    if "final_waterQuality_complete" in d:
        d["water_quality"] = d["final_waterQuality_complete"].copy()
        if not d["water_quality"].empty:
            d["villagewatercfu"] = d["water_quality"].copy()

    if "lake_full_integration" in d:
        d["lake_water_cfu"] = d["lake_full_integration"].copy()

    if "villagewatercfu" not in d or d.get("villagewatercfu", pd.DataFrame()).empty:
        if "soil_data" in d and not d["soil_data"].empty:
            d["villagewatercfu"] = d["soil_data"].copy()
        else:
            d["villagewatercfu"] = pd.DataFrame()

    d.setdefault("microbial_analysis", pd.DataFrame())
    d.setdefault("physiochem_village_waterquality", pd.DataFrame())

    d["villagewatercfu"] = safe_mean_cfu(d.get("villagewatercfu", pd.DataFrame()), "source")
    d["lake_water_cfu"]  = safe_mean_cfu(d.get("lake_water_cfu",  pd.DataFrame()), "sample")
    d["soil_cfu"]        = safe_mean_cfu(d.get("soil_cfu",        pd.DataFrame()), "sample")

    return d

DATA = load_all()

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

C_BLUE   = "#0284c7"
C_GREEN  = "#16a34a"
C_RED    = "#dc2626"
C_PURPLE = "#7e22ce"
C_AMBER  = "#b45309"

DEEP     = "#ffffff"
PANEL    = "#f8fafc"
CARD_BG  = "#f1f5f9"
BORDER   = "rgba(0,0,0,0.1)"
TEXT     = "#0f172a"
MUTED    = "#1e293b"


def PL(title="", **kw):
    base = dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="'Sora','Segoe UI',sans-serif", color=TEXT, size=11),
        margin=dict(l=20, r=20, t=44, b=20),
        title=dict(text=title, font=dict(size=13, color=TEXT, family="'Sora',sans-serif")),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, borderwidth=1, font_size=10),
        xaxis=dict(gridcolor="rgba(0,0,0,0.08)", linecolor=BORDER, tickfont_color=MUTED,
                   title_font_color=MUTED, zerolinecolor=BORDER),
        yaxis=dict(gridcolor="rgba(0,0,0,0.08)", linecolor=BORDER, tickfont_color=MUTED,
                   title_font_color=MUTED, zerolinecolor=BORDER),
        hoverlabel=dict(bgcolor=CARD_BG, bordercolor=BORDER, font=dict(color=TEXT, size=11)),
    )
    base.update(kw)
    return base


def PLna(title="", **kw):
    return {k: v for k, v in PL(title, **kw).items() if "axis" not in k}


def PLgauge():
    return {k: v for k, v in PLna().items() if k != "margin"}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgba(hex_color, alpha):
    r, g, b = hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


# ── Design primitives ──────────────────────────────────────────────────────

CARD_STYLE = {
    "background": CARD_BG,
    "border": f"1px solid {BORDER}",
    "borderRadius": "12px",
    "padding": "14px 16px",
    "position": "relative",
    "overflow": "hidden",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
    "transition": "transform 0.2s, box-shadow 0.2s",
}


def card_top_bar(color):
    return html.Div(style={
        "position": "absolute", "top": "0", "left": "0", "right": "0",
        "height": "3px", "background": color, "opacity": "0.7",
    })


def section_banner(title, subtitle):
    return html.Div([
        html.H2(title, style={
            "fontFamily": "'Playfair Display',serif",
            "fontSize": "32px", "fontWeight": "700",
            "margin": "0 0 4px", "color": TEXT,
        }),
        html.P(subtitle, style={
            "fontFamily": "'DM Mono',monospace",
            "fontSize": "11px", "color": MUTED,
            "letterSpacing": "0.5px", "fontWeight": "600", "margin": "0 0 28px",
        }),
    ])


def hero_box(title, body):
    return html.Div([
        html.H2(title, style={
            "fontFamily": "'Playfair Display',serif",
            "fontSize": "24px", "margin": "0 0 8px", "color": TEXT,
        }),
        html.P(body, style={"fontSize": "13px", "color": MUTED, "lineHeight": "1.7", "textAlign": "justify"}),
    ], style={
        "background": "linear-gradient(135deg,#f1f5f9 0%,#ffffff 100%)",
        "border": f"1px solid {BORDER}", "borderRadius": "20px",
        "padding": "32px 36px", "marginBottom": "24px", "position": "relative", "overflow": "hidden",
    })


def pillar_chip(label, color):
    return html.Div(label, style={
        "padding": "8px 16px", "borderRadius": "10px", "fontSize": "12px", "fontWeight": "600",
        "background": rgba(color, 0.1), "border": f"1px solid {rgba(color, 0.3)}",
        "color": color, "display": "flex", "alignItems": "center", "gap": "6px",
    })


def kpi_card(label, value, unit, sub, accent_color="blue"):
    accent_map = {
        "blue": C_BLUE, "green": C_GREEN, "red": C_RED, "purple": C_PURPLE, "amber": C_AMBER,
    }
    color = accent_map.get(accent_color, C_BLUE)
    return html.Div([
        card_top_bar(color),
        html.P(label, style={
            "fontFamily": "'DM Mono',monospace", "fontSize": "10px", "fontWeight": "700",
            "color": MUTED, "letterSpacing": "1px", "textTransform": "uppercase", "margin": "6px 0 4px",
        }),
        html.Div([
            html.Span(str(value), style={
                "fontSize": "30px", "fontWeight": "800",
                "color": color, "lineHeight": "1",
                "fontFamily": "'DM Mono',monospace",
            }),
            html.Span(f" {unit}", style={"fontSize": "13px", "color": MUTED, "marginLeft": "4px"}),
        ]),
        html.P(sub, style={"fontSize": "11px", "color": MUTED, "margin": "4px 0 0"}),
    ], style={**CARD_STYLE})


def kpi_row(children):
    return html.Div(children, style={
        "display": "grid",
        "gridTemplateColumns": f"repeat({len(children)}, 1fr)",
        "gap": "12px", "marginBottom": "20px",
    })


def chart_card(child, accent="blue", span=1):
    accent_map = {"blue": C_BLUE, "green": C_GREEN, "red": C_RED, "purple": C_PURPLE, "amber": C_AMBER}
    color = accent_map.get(accent, C_BLUE)
    return html.Div([
        card_top_bar(color),
        child,
    ], style={
        **CARD_STYLE,
        "gridColumn": f"span {span}",
        "paddingTop": "18px",
    })


def grid2(children):
    return html.Div(children, style={
        "display": "grid", "gridTemplateColumns": "1fr 1fr",
        "gap": "20px", "marginBottom": "24px",
    })


def grid3(children):
    return html.Div(children, style={
        "display": "grid", "gridTemplateColumns": "repeat(3,1fr)",
        "gap": "16px", "marginBottom": "24px",
    })


def grid4(children):
    return html.Div(children, style={
        "display": "grid", "gridTemplateColumns": "repeat(4,1fr)",
        "gap": "16px", "marginBottom": "20px",
    })


def section_label(text):
    return html.P(text, style={
        "fontFamily": "'DM Mono',monospace", "fontSize": "10px", "fontWeight": "700",
        "color": MUTED, "letterSpacing": "2px", "textTransform": "uppercase",
        "margin": "0 0 4px",
    })


def card_title(text):
    return html.P(text, style={"fontSize": "13px", "fontWeight": "700", "margin": "0 0 10px", "color": TEXT})


def badge(text, kind="info"):
    styles = {
        "good":   {"background": "rgba(22,163,74,0.15)",  "color": "#15803d", "border": "1px solid rgba(22,163,74,0.3)"},
        "warn":   {"background": "rgba(180,83,9,0.12)",   "color": "#92400e", "border": "1px solid rgba(180,83,9,0.3)"},
        "bad":    {"background": "rgba(220,38,38,0.12)",  "color": "#b91c1c", "border": "1px solid rgba(220,38,38,0.3)"},
        "info":   {"background": "rgba(2,132,199,0.12)",  "color": "#0369a1", "border": "1px solid rgba(2,132,199,0.3)"},
        "purple": {"background": "rgba(107,33,168,0.12)", "color": "#6b21a8", "border": "1px solid rgba(107,33,168,0.3)"},
    }
    s = styles.get(kind, styles["info"])
    return html.Span(text, style={
        "display": "inline-block", "padding": "2px 8px", "borderRadius": "4px",
        "fontSize": "10px", "fontFamily": "'DM Mono',monospace", "fontWeight": "500",
        **s,
    })


def progress_bar(label, sub_label, pct, color="blue"):
    color_map = {
        "blue":   "linear-gradient(90deg,#0284c7,#0369a1)",
        "green":  "linear-gradient(90deg,#16a34a,#15803d)",
        "red":    "linear-gradient(90deg,#dc2626,#b91c1c)",
        "purple": "linear-gradient(90deg,#7e22ce,#6b21a8)",
        "amber":  "linear-gradient(90deg,#b45309,#92400e)",
    }
    pct_clamped = max(0, min(100, float(pct) if pct is not None else 0))
    return html.Div([
        html.Div([
            html.Span(label, style={"color": TEXT, "fontWeight": "600", "fontSize": "12px"}),
            html.Span(sub_label, style={"color": MUTED, "fontFamily": "'DM Mono',monospace", "fontSize": "11px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "5px"}),
        html.Div(
            html.Div(style={"width": f"{pct_clamped}%", "height": "100%", "borderRadius": "4px",
                            "background": color_map.get(color, color_map["blue"]), "transition": "width 1s ease"}),
            style={"height": "6px", "background": "rgba(0,0,0,0.08)", "borderRadius": "4px", "overflow": "hidden"}
        ),
    ], style={"marginBottom": "14px"})


def data_table_wrap(header_cols, rows):
    header = html.Div([
        html.Div(c, style={
            "flex": str(f), "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
            "fontWeight": "700", "color": TEXT, "letterSpacing": "0.8px",
            "textTransform": "uppercase", "padding": "0 8px",
        }) for c, f in header_cols
    ], style={
        "display": "flex", "padding": "8px 12px",
        "borderBottom": f"1px solid {BORDER}", "background": PANEL,
    })

    body_rows = []
    for row in rows:
        body_rows.append(html.Div([
            html.Div(cell, style={
                "flex": str(f), "fontSize": "12px", "color": MUTED,
                "padding": "0 8px", "display": "flex", "alignItems": "center",
            }) for cell, f in row
        ], style={
            "display": "flex", "alignItems": "center", "padding": "9px 12px",
            "borderBottom": f"1px solid rgba(0,0,0,0.06)",
        }))

    return html.Div([header] + body_rows, style={
        "background": DEEP, "border": f"1px solid {BORDER}",
        "borderRadius": "10px", "overflow": "hidden", "marginBottom": "20px",
    })


def insight_row(text, color):
    return html.Div([
        html.Div(style={"width": "3px", "background": color, "borderRadius": "2px",
                        "marginRight": "10px", "flexShrink": "0", "alignSelf": "stretch"}),
        html.P(f"→  {text}", style={"margin": "0", "fontSize": "12px", "color": MUTED, "lineHeight": "1.65"}),
    ], style={
        "display": "flex", "alignItems": "flex-start",
        "background": CARD_BG, "border": f"1px solid {BORDER}",
        "borderRadius": "8px", "padding": "10px 12px", "marginBottom": "7px",
    })


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: extract a named metric from kpi-style sheets
# ══════════════════════════════════════════════════════════════════════════════

def kpi_val(df, labels, default="—"):
    return lookup_kpi_value(df, labels, default)


def fmt_num(val, default="—"):
    try:
        v = float(val)
        if v == int(v):
            return str(int(v))
        return f"{v:,.2f}"
    except (TypeError, ValueError):
        return default


# ══════════════════════════════════════════════════════════════════════════════
# LIVE AQI HELPER — used by all page renderers and the header
# ══════════════════════════════════════════════════════════════════════════════

def get_live_aqi_humidity(d):
    """
    Returns (aqi_str, humidity_str).
    Tries live scrape first; falls back to Google Sheet air_quality tab data.
    """
    live_aqi, live_hum = fetch_live_aqi_humidity()

    # ── Sheet fallback values ────────────────────────────────────────────────
    sheet_aqi = "—"
    sheet_hum = "—"
    aq = d.get("air_quality", pd.DataFrame())
    aq_param_col = find_col(aq, ["parameter", "param", "metric"])
    aq_value_col = find_col(aq, ["value", "reading", "measurement"])
    if aq_param_col and aq_value_col and not aq.empty:
        for _, aq_row in aq.iterrows():
            p = str(aq_row[aq_param_col]).strip().upper()
            v = aq_row[aq_value_col]
            parsed = pd.to_numeric(v, errors="coerce")
            if p == "AQI" and pd.notna(parsed):
                sheet_aqi = str(int(round(float(parsed))))
            elif p in ("HUMIDITY", "RH", "RELATIVE HUMIDITY", "AMBIENT HUMIDITY") and pd.notna(parsed):
                sheet_hum = fmt_num(round(float(parsed), 1))

    aqi_str = live_aqi  if live_aqi  is not None else sheet_aqi
    hum_str = live_hum  if live_hum  is not None else sheet_hum

    return aqi_str, hum_str


def _extract_header_values(data):
    """Used to initialise the header bar with AQI + population."""
    aqi_str, _ = get_live_aqi_humidity(data)

    pop_str = "—"
    kpi_df = data.get("kpi_data", pd.DataFrame())
    pop_wide = kpi_val_from_wide(
        kpi_df,
        ["totalPopulation", "total_population", "Total Population", "Population"],
        default=None
    )
    if pop_wide is not None:
        pop_str = pop_wide
    else:
        kpi_field_col = find_col(kpi_df, ["field", "metric", "name", "kpi", "location"])
        kpi_value_col = find_col(kpi_df, ["value", "score"])
        if kpi_field_col and kpi_value_col and not kpi_df.empty:
            for _, row in kpi_df.iterrows():
                nk = normalize_key(str(row[kpi_field_col]))
                if nk in ("totalpopulation", "population"):
                    v = row[kpi_value_col]
                    if pd.notna(v):
                        pop_str = str(v)
                    break

    return aqi_str, pop_str


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW PAGE HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _get_overview_kpis(d):
    kpis = {}

    kpi_df = d.get("kpi_data", pd.DataFrame())

    kpis["households"] = kpi_val_from_wide(
        kpi_df,
        ["household", "households", "Household", "Households"],
        default="—"
    )

    kpis["total_population"] = kpi_val_from_wide(
        kpi_df,
        ["totalPopulation", "total_population", "Total Population", "Population"],
        default="—"
    )

    akpi = d.get("animal_kpi_data", pd.DataFrame())

    kpis["livestock"] = kpi_val_from_wide(
        akpi,
        ["livestockMonitored", "livestock_monitored", "livestock", "Livestock"],
        default="—"
    )

    kpis["stray_dogs"] = kpi_val_from_wide(
        akpi,
        ["strayDogs", "stray_dogs", "stray dogs", "StrayDogs"],
        default="—"
    )

    kpis["abc_count"] = kpi_val_from_wide(
        akpi,
        ["abcProgramCount", "abc_program_count", "abcProgram", "abc", "ABC", "abcCount"],
        default="—"
    )

    kpis["avian"] = kpi_val_from_wide(
        akpi,
        ["avianSpecies", "avain_species", "avianspecies", "avainSpecies", "avian species",
         "avain species", "avain", "avian"],
        default="—"
    )

    # ── AQI and humidity from LIVE scrape (with sheet fallback) ─────────────
    live_aqi, live_hum = get_live_aqi_humidity(d)
    kpis["aqi"]      = live_aqi if live_aqi  not in (None, "—") else "—"
    kpis["humidity"] = live_hum if live_hum  not in (None, "—") else "—"

    wq = d.get("final_waterQuality_complete", pd.DataFrame())
    kpis["water_sources"] = "—"
    if not wq.empty:
        sid_col = find_col(wq, ["sampleId", "sample_id", "id", "sample_no", "Sample no.", "Sample no"])
        if sid_col:
            count = wq[sid_col].dropna().shape[0]
            kpis["water_sources"] = str(count) if count > 0 else "—"
        else:
            kpis["water_sources"] = str(len(wq))

    return kpis


def _build_surveillance_radar(d):
    oh_sum = d.get("onehealth_summary", pd.DataFrame())

    EXPECTED_CATEGORIES = [
        "Water Quality", "Air Quality", "Soil Health",
        "Animal Health", "Human NCD", "Vector Disease", "AMR Risk",
    ]

    cat_col   = find_col(oh_sum, ["category"])
    score_col = find_col(oh_sum, ["score"])

    current_scores = {}
    if cat_col and score_col and not oh_sum.empty:
        oh_num = coerce_numeric(oh_sum, [score_col])
        for _, row in oh_num.iterrows():
            cat = str(row[cat_col]).strip()
            val = row[score_col]
            if pd.notna(val):
                current_scores[cat] = float(val)

    categories = EXPECTED_CATEGORIES
    current_vals = [current_scores.get(c, 0) for c in categories]
    target_val   = 80

    cats_closed    = categories + [categories[0]]
    current_closed = current_vals + [current_vals[0]]
    target_closed  = [target_val] * (len(categories) + 1)

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=current_closed,
        theta=cats_closed,
        name="Current Status",
        fill="toself",
        line=dict(color="#1d4ed8", width=2.5, dash="solid"),
        fillcolor="rgba(59,130,246,0.18)",
        marker=dict(size=7, color="#1d4ed8", symbol="circle"),
        hovertemplate="<b>%{theta}</b><br>Score: %{r}<extra></extra>",
    ))

    fig.add_trace(go.Scatterpolar(
        r=target_closed,
        theta=cats_closed,
        name="Target (80)",
        fill="none",
        line=dict(color="#16a34a", width=2, dash="dash"),
        marker=dict(size=6, color="#16a34a", symbol="circle-open"),
        hovertemplate="<b>Target</b>: %{r}<extra></extra>",
    ))

    critical = [c for c, v in zip(categories, current_vals) if v < 40]
    critical_msg = ""

    fig.update_layout(
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#f8fafc",
        font=dict(family="'Sora','Segoe UI',sans-serif", color=TEXT, size=11),
        margin=dict(l=40, r=40, t=70, b=40),
        title=dict(
            text="One Health Surveillance Summary",
            font=dict(size=14, color=TEXT, family="'Sora',sans-serif"),
            x=0.02, xanchor="left",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=BORDER,
            borderwidth=0,
            font_size=11,
            orientation="h",
            x=0.02,
            y=-0.08,
        ),
        polar=dict(
            bgcolor="#ffffff",
            radialaxis=dict(
                range=[0, 100],
                gridcolor="rgba(0,0,0,0.10)",
                tickfont=dict(color=MUTED, size=9),
                linecolor="rgba(0,0,0,0.15)",
                tickvals=[20, 40, 60, 80, 100],
                showticklabels=True,
            ),
            angularaxis=dict(
                gridcolor="rgba(0,0,0,0.10)",
                tickfont=dict(color=TEXT, size=11),
                linecolor="rgba(0,0,0,0.15)",
            ),
        ),
        annotations=[
            dict(
                text="── Current Status  ╌╌ Target (80)",
                xref="paper", yref="paper",
                x=0.02, y=1.06,
                xanchor="left",
                showarrow=False,
                font=dict(size=10, color=MUTED, family="'DM Mono',monospace"),
            )
        ],
    )

    if critical:
        fig.add_annotation(
            text=f"⚠ Critical categories below 40-point target detected",
            xref="paper", yref="paper",
            x=0.02, y=1.13,
            xanchor="left",
            showarrow=False,
            font=dict(size=10, color=C_RED, family="'Sora',sans-serif"),
            bgcolor="rgba(254,226,226,0.8)",
            bordercolor=C_RED,
            borderwidth=1,
            borderpad=4,
        )

    return fig, critical_msg


RISK_LEVEL_MAP = {
    "low":       30,
    "moderate":  60,
    "high":      85,
    "very high": 95,
    "detected":  90,
}


def _build_risk_indicators(d):
    oh_risk = d.get("onehealth_risk", pd.DataFrame())

    ind_col  = find_col(oh_risk, ["indicator"])
    lvl_col  = find_col(oh_risk, ["level"])
    desc_col = find_col(oh_risk, ["description"])

    default_risks = [
        {"indicator": "Water Contamination Risk",    "level": "High",      "score": 85, "desc": "High — 8/10 samples exceed WHO TDS limits",     "color": C_RED},
        {"indicator": "Vector-borne Disease Pressure","level": "Moderate",  "score": 60, "desc": "Moderate — seasonal spikes",                    "color": C_AMBER},
        {"indicator": "AMR Antibiotic Residue Risk",  "level": "Low",       "score": 30, "desc": "Low — within safe limits",                      "color": C_GREEN},
        {"indicator": "Stray Dog Rabies Risk",        "level": "Moderate",  "score": 60, "desc": "Moderate — 13% infected in neutered pop.",       "color": C_AMBER},
        {"indicator": "Air Quality Index",            "level": "Moderate",  "score": 65, "desc": "135 AQI — Unhealthy for sensitive groups",       "color": C_AMBER},
        {"indicator": "Soil Microbial Load",          "level": "Very High", "score": 95, "desc": "Very High — horse stable soil TNTC",             "color": C_RED},
        {"indicator": "E.coli/Enterobacter Presence", "level": "Detected",  "score": 90, "desc": "Detected in lake & soil samples",                "color": C_RED},
    ]

    risks = []
    if ind_col and lvl_col and not oh_risk.empty:
        rows = oh_risk[[ind_col, lvl_col] + ([desc_col] if desc_col else [])].copy()
        rows = rows.dropna(subset=[ind_col, lvl_col])
        for _, row in rows.iterrows():
            lvl_str = str(row[lvl_col]).strip()
            score = RISK_LEVEL_MAP.get(lvl_str.lower(), None)
            if score is None:
                score = pd.to_numeric(lvl_str, errors="coerce")
                if pd.isna(score):
                    score = 50
            desc = str(row.get(desc_col, "")).strip() if desc_col else ""
            if not desc or desc.lower() == "nan":
                desc = f"{lvl_str}"
            lv = lvl_str.lower()
            color = C_GREEN if lv == "low" else (C_AMBER if lv == "moderate" else C_RED)
            risks.append({
                "indicator": str(row[ind_col]).strip(),
                "level": lvl_str,
                "score": float(score),
                "desc": desc,
                "color": color,
            })

    if not risks:
        risks = default_risks

    risks = sorted(risks, key=lambda x: x["score"], reverse=True)

    risk_items = []
    for r in risks:
        pct = min(100, max(0, r["score"]))
        bar_color = r["color"]
        risk_items.append(
            html.Div([
                html.Div([
                    html.Span(r["indicator"], style={
                        "fontSize": "12px", "fontWeight": "600", "color": TEXT,
                        "fontFamily": "'Sora',sans-serif",
                    }),
                    html.Span(r["desc"], style={
                        "fontSize": "11px", "color": MUTED,
                        "fontFamily": "'Sora',sans-serif",
                        "textAlign": "right",
                    }),
                ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "5px"}),
                html.Div(
                    html.Div(style={
                        "width": f"{pct}%", "height": "100%", "borderRadius": "4px",
                        "background": bar_color, "transition": "width 1s ease",
                    }),
                    style={
                        "height": "8px", "background": "rgba(0,0,0,0.08)",
                        "borderRadius": "4px", "overflow": "hidden",
                    }
                ),
            ], style={"marginBottom": "16px"})
        )

    return html.Div([
        html.P("Key Risk Indicators at a Glance", style={
            "fontSize": "14px", "fontWeight": "700", "color": TEXT,
            "fontFamily": "'Sora',sans-serif", "margin": "0 0 16px",
        }),
        *risk_items,
    ], style={
        "background": "#ffffff",
        "borderRadius": "12px",
        "padding": "20px 24px",
        "height": "100%",
    })


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RENDERERS
# ══════════════════════════════════════════════════════════════════════════════

def empty_fig(msg="No data available"):
    fig = go.Figure()
    fig.add_annotation(
        text=msg,
        x=0.5, y=0.5,
        xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=14),
    )
    fig.update_layout(template="plotly_white")
    return fig


def page_overview(d):
    kpis = _get_overview_kpis(d)

    def ensure_plus(val):
        s = str(val).strip()
        if s == "—":
            return s
        if not s.endswith("+"):
            return s + "+"
        return s

    kpis["stray_dogs"] = ensure_plus(kpis["stray_dogs"])
    kpis["abc_count"]  = ensure_plus(kpis["abc_count"])
    kpis["avian"]      = ensure_plus(kpis["avian"])

    fig_risk, critical_msg = _build_surveillance_radar(d)
    risk_indicators_html = _build_risk_indicators(d)

    return html.Div([
        hero_box(
            "One Health Dashboard",
            "A science-driven, integrated data platform assessing the health of humans, animals, and the "
            "environment at the village interface — built on the One Health framework by Planetary Health "
            "Foundation, an initiative of Equine Biotech, IISc.",
        ),

        html.Div([
            kpi_card("Households",        kpis["households"],    "",          "Bettahalasuru, Karnataka",   "blue"),
            kpi_card("Livestock",         kpis["livestock"],     "animals",   "Via Vet Department",         "green"),
            kpi_card("Stray Dogs",        kpis["stray_dogs"],    "",          "Village population",         "amber"),
            kpi_card("ABC Programme",     kpis["abc_count"],     "animals",   "Neutered + anti-rabies",     "red"),
            kpi_card("Avian Species",     kpis["avian"],         "species",   "Observed in area",           "purple"),
            kpi_card("AQI",               kpis["aqi"],           "",          "Live — Bangalore air quality","amber"),
            kpi_card("Humidity",          kpis["humidity"],      "%",         "Live — Bangalore weather",   "blue"),
            kpi_card("Water Sources",     kpis["water_sources"], "tested",    "Village + lake combined",    "red"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(8,1fr)", "gap": "12px", "marginBottom": "20px"}),

        html.Div([
            html.Div([
                dcc.Graph(
                    figure=fig_risk,
                    config={"displayModeBar": False},
                    style={"height": "420px"},
                ),
            ], style={
                "background": "#f8fafc",
                "border": f"1px solid {BORDER}",
                "borderRadius": "12px",
                "overflow": "hidden",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
            }),

            html.Div([
                risk_indicators_html,
            ], style={
                "background": "#fffbeb",
                "border": f"1px solid {BORDER}",
                "borderRadius": "12px",
                "padding": "20px 24px",
                "overflow": "hidden",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
            }),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "1fr 1fr",
            "gap": "20px",
            "marginBottom": "24px",
        }),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: read disease_insights tab (tall format: disease, metric, value, notes)
# Returns a dict keyed by disease name (lowercase) with sub-keys: value, notes
# ══════════════════════════════════════════════════════════════════════════════

def _parse_disease_insights(di_df):
    result = {}
    if di_df is None or di_df.empty:
        return result

    disease_col = find_col(di_df, ["disease", "Disease", "diseaseName", "disease_name"])
    value_col   = find_col(di_df, ["value", "Value", "cases", "casesRange"])
    notes_col   = find_col(di_df, ["notes", "Notes", "insight", "note", "description", "finding"])

    if not disease_col:
        return result

    for _, row in di_df.iterrows():
        disease_name = str(row.get(disease_col, "")).strip().lower()
        if not disease_name or disease_name == "nan":
            continue

        val = ""
        if value_col:
            raw = str(row.get(value_col, "")).strip()
            val = raw if raw and raw.lower() != "nan" else ""

        note = ""
        if notes_col:
            raw_note = str(row.get(notes_col, "")).strip()
            note = raw_note if raw_note and raw_note.lower() != "nan" else ""

        result[disease_name] = {"value": val, "notes": note}

    return result


# ══════════════════════════════════════════════════════════════════════════════
# HUMAN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def page_human(d):
    md  = d.get("majorDiseases",        pd.DataFrame())
    vt  = d.get("vectorDiseaseTrend",   pd.DataFrame())
    db  = d.get("diseaseBurden",        pd.DataFrame())
    sc  = d.get("phcScreeningPrograms", pd.DataFrame())
    vi  = d.get("vectorInsights",       pd.DataFrame())
    kpi = d.get("kpi_data",             pd.DataFrame())
    di  = d.get("disease_insights",     pd.DataFrame())

    h_population = kpi_val_from_wide(
        kpi,
        ["totalPopulation", "total_population", "Total Population", "Population"],
        default=None,
    )
    if h_population is None:
        h_population = kpi_val(kpi, ["Total Population", "Population", "Village Population"], "—")

    h_male = kpi_val_from_wide(
        kpi,
        ["male", "Male", "malePop", "malePopulation", "male_population",
         "Male Population", "Males"],
        default=None,
    )
    if h_male is None:
        h_male = kpi_val(kpi, ["Male", "Male Population", "Males"], "—")

    h_female = kpi_val_from_wide(
        kpi,
        ["female", "Female", "femalePop", "femalePopulation", "female_population",
         "Female Population", "Females"],
        default=None,
    )
    if h_female is None:
        h_female = kpi_val(kpi, ["Female", "Female Population", "Females"], "—")

    h_phc_services = kpi_val_from_wide(
        kpi,
        ["phcServices", "phc_services", "PHC Services", "screeningPrograms",
         "screening_programs", "Screening Programs", "phcService"],
        default=None,
    )
    if h_phc_services is None:
        h_phc_services = kpi_val(kpi, ["PHC Services", "Screening Programs", "Services"], "8+")

    di_parsed = _parse_disease_insights(di)

    malaria_data        = di_parsed.get("malaria", {})
    malaria_cases       = malaria_data.get("value",  "30–50/yr")
    malaria_insight     = malaria_data.get("notes",  "Peak during monsoon. RDT used at PHC.")

    dengue_data         = di_parsed.get("dengue", {})
    dengue_cases        = dengue_data.get("value",   "60 cases")
    dengue_insight      = dengue_data.get("notes",   "2022 spike — high rainfall, standing water.")

    chikungunya_data    = di_parsed.get("chikungunya", {})
    chikungunya_cases   = chikungunya_data.get("value",  "10–25/yr")
    chikungunya_insight = chikungunya_data.get("notes",  "Sporadic post-monsoon. Nets distributed.")

    rainfall_data       = di_parsed.get("rainfall", {})
    rainfall_val        = rainfall_data.get("value",   "High correlation")
    rainfall_insight    = rainfall_data.get("notes",   "↑ Rainfall → ↑ Vector breeding → ↑ Disease burden (2022 confirmed)")

    vi_disease_col = find_col(vi, ["disease", "Disease", "diseaseName", "disease_name"])
    vi_cases_col   = find_col(vi, ["casesRange", "cases_range", "cases", "caseRange",
                                   "Cases", "range", "value"])
    vi_insight_col = find_col(vi, ["insight", "description", "note", "Insight",
                                   "Description", "finding"])

    def get_vi_fallback(disease_name, col, default):
        if not col or vi.empty or vi_disease_col is None:
            return default
        try:
            mask = (
                vi[vi_disease_col]
                .astype(str).str.strip().str.lower()
                == disease_name.lower()
            )
            row = vi[mask]
            if not row.empty:
                val = str(row[col].iloc[0]).strip()
                return val if val and val.lower() not in ("nan", "", "none") else default
        except Exception:
            pass
        return default

    if not malaria_cases or malaria_cases == "—":
        malaria_cases   = get_vi_fallback("malaria",     vi_cases_col,   "30–50/yr")
    if not malaria_insight or malaria_insight == "—":
        malaria_insight = get_vi_fallback("malaria",     vi_insight_col, "Peak during monsoon. RDT used at PHC.")

    if not dengue_cases or dengue_cases == "—":
        dengue_cases    = get_vi_fallback("dengue",      vi_cases_col,   "60 cases")
    if not dengue_insight or dengue_insight == "—":
        dengue_insight  = get_vi_fallback("dengue",      vi_insight_col, "2022 spike — high rainfall, standing water.")

    if not chikungunya_cases or chikungunya_cases == "—":
        chikungunya_cases   = get_vi_fallback("chikungunya", vi_cases_col,   "10–25/yr")
    if not chikungunya_insight or chikungunya_insight == "—":
        chikungunya_insight = get_vi_fallback("chikungunya", vi_insight_col, "Sporadic post-monsoon. Nets distributed.")

    if not rainfall_val or rainfall_val == "—":
        rainfall_val    = get_vi_fallback("rainfall",    vi_cases_col,   "High correlation")
    if not rainfall_insight or rainfall_insight == "—":
        rainfall_insight = get_vi_fallback(
            "rainfall", vi_insight_col,
            "↑ Rainfall → ↑ Vector breeding → ↑ Disease burden (2022 confirmed)"
        )

    db_cat_col = find_col(db, ["diseaseCategory", "disease_category", "disease", "category"])
    db_val_col = find_col(db, ["value", "score", "severity"])
    db_sub_col = find_col(db, ["sublabel", "sub_label", "description", "note"])

    def get_db(cat_name, default_pct, default_sub):
        if db_cat_col and db_val_col and not db.empty:
            mask = db[db_cat_col].astype(str).str.strip().str.lower().str.contains(
                cat_name.lower(), na=False
            )
            row = db[mask]
            if not row.empty:
                pct = pd.to_numeric(row[db_val_col].iloc[0], errors="coerce")
                sub = (
                    str(row[db_sub_col].iloc[0]).strip()
                    if db_sub_col else default_sub
                )
                sub = sub if sub and sub.lower() not in ("nan", "") else default_sub
                return (float(pct) if pd.notna(pct) else default_pct), sub
        return default_pct, default_sub

    db_hyp_pct,  db_hyp_sub  = get_db("hypertension",  72, "Rising (age 40+)")
    db_diab_pct, db_diab_sub = get_db("diabetes",       65, "Growing — lifestyle factors")
    db_tb_pct,   db_tb_sub   = get_db("tuberculosis",   45, "Endemic — lower SES groups")
    db_anm_pct,  db_anm_sub  = get_db("anemia",         55, "Nutritional deficiency")
    db_mal_pct,  db_mal_sub  = get_db("malaria",         35, "30–50 cases/yr")
    db_den_pct,  db_den_sub  = get_db("dengue",          48, "Cases — peak season")
    db_lep_pct,  db_lep_sub  = get_db("leptospirosis",   18, "Monsoon linked")

    badge_map_bg   = {"Active": "good", "Seasonal": "warn", "Periodic": "info"}
    screening_rows = []
    if not sc.empty:
        for _, row in sc.iterrows():
            screening_rows.append([
                (row.get("screeningType", ""), 2),
                (row.get("frequency",      ""), 1),
                (badge(row.get("status", ""),
                       badge_map_bg.get(row.get("status", ""), "info")), 1),
            ])

    di_text_col  = find_col(di, ["insight_text", "insight", "finding", "text"])
    di_color_col = find_col(di, ["color_key", "color", "pillar"])
    color_lk     = {"blue": C_BLUE, "red": C_RED, "amber": C_AMBER, "green": C_GREEN}
    disease_insight_rows = []
    if di_text_col and not di.empty:
        for _, row in di.iterrows():
            txt = str(row.get(di_text_col, "")).strip()
            if not txt or txt.lower() == "nan":
                continue
            c_key = (
                str(row.get(di_color_col, "blue")).strip().lower()
                if di_color_col else "blue"
            )
            disease_insight_rows.append(insight_row(txt, color_lk.get(c_key, C_BLUE)))

    print(f"[DEBUG] majorDiseases shape: {md.shape}, columns: {list(md.columns)}")
    if not md.empty:
        print(md.head())

    dis_col  = find_col(md, [
        "disease", "Disease", "diseaseName", "disease_name",
        "name", "Name", "category", "Category", "label", "Label"
    ])
    case_col = find_col(md, [
        "cases", "Cases", "case", "Case",
        "value", "Value", "score", "Score",
        "prevalenceScore", "prevalence_score", "prevalence", "Prevalence",
        "count", "Count", "burden", "Burden"
    ])

    fig_dis  = empty_fig("No disease case-load data available")

    if dis_col and case_col:
        md_work = md.copy()
        md_work[case_col] = pd.to_numeric(md_work[case_col], errors="coerce")
        md_s = (
            md_work
            .dropna(subset=[dis_col, case_col])
            .sort_values(case_col, ascending=True)
        )
        n = len(md_s)
        print(f"[DEBUG] majorDiseases after dropna: {n} rows")
        if n:
            palette = []
            for i in range(n):
                frac = i / max(n - 1, 1)
                if frac < 0.35:
                    palette.append("#22c55e")
                elif frac < 0.65:
                    palette.append("#f59e0b")
                elif frac < 0.85:
                    palette.append("#f97316")
                else:
                    palette.append("#ef4444")

            fig_dis = go.Figure()
            fig_dis.add_trace(go.Bar(
                x=md_s[case_col],
                y=md_s[dis_col],
                orientation="h",
                marker=dict(
                    color=palette,
                    line_width=0,
                    cornerradius=8,
                    opacity=0.88,
                ),
                hovertemplate="<b>%{y}</b><br>Score: %{x}<extra></extra>",
            ))
            fig_dis.add_vline(
                x=60,
                line_dash="dot",
                line_color=rgba(C_RED, 0.45),
                line_width=1.5,
                annotation_text="High burden (>60)",
                annotation_font=dict(color=C_RED, size=9),
                annotation_position="top right",
            )
            fig_dis.add_vline(
                x=40,
                line_dash="dot",
                line_color=rgba(C_AMBER, 0.45),
                line_width=1.5,
                annotation_text="Moderate (40)",
                annotation_font=dict(color=C_AMBER, size=9),
                annotation_position="bottom right",
            )
            fig_dis.update_layout(**PL(
                "Major Diseases at PHC (2020–2024)",
                xaxis_title="Prevalence Score (0 = absent, 100 = very high)",
                xaxis=dict(
                    range=[0, 110],
                    gridcolor="rgba(0,0,0,0.04)",
                    showgrid=True,
                    zeroline=False,
                    tickfont_color=MUTED,
                    title_font_color=MUTED,
                ),
                yaxis=dict(
                    gridcolor="rgba(0,0,0,0)",
                    linecolor=BORDER,
                    tickfont=dict(color=TEXT, size=11),
                    title_font_color=MUTED,
                ),
                margin=dict(l=10, r=24, t=56, b=44),
                bargap=0.32,
            ))
            fig_dis.add_annotation(
                text=(
                    "<span style='color:#ef4444'>● High burden (>60)</span>  "
                    "<span style='color:#f59e0b'>● Moderate (40–60)</span>  "
                    "<span style='color:#22c55e'>● Low (<40)</span>"
                ),
                xref="paper", yref="paper",
                x=0.0, y=-0.10,
                xanchor="left",
                showarrow=False,
                font=dict(size=9, family="'DM Mono',monospace", color=MUTED),
            )
    else:
        print(f"[WARN] majorDiseases: could not find disease or cases columns. Available: {list(md.columns)}")

    year_col = find_col(vt, ["year", "Year"])
    fig_vec  = empty_fig("No vector disease trend data available")

    if year_col:
        vt_plot = coerce_numeric(vt, [year_col])
        fig_vec  = go.Figure()

        SERIES = [
            (find_col(vt, ["malaria",       "Malaria"]),       "#3b82f6", "Malaria",       True),
            (find_col(vt, ["dengue",        "Dengue"]),        "#ef4444", "Dengue",        True),
            (find_col(vt, ["chikungunya",   "Chikungunya"]),   "#a855f7", "Chikungunya",   False),
            (find_col(vt, ["leptospirosis", "Leptospirosis"]), "#22c55e", "Leptospirosis", False),
        ]

        for col, color, name, do_fill in SERIES:
            if not col:
                continue
            vt_plot = coerce_numeric(vt_plot, [col])
            valid   = vt_plot[[year_col, col]].dropna()
            if valid.empty:
                continue
            fig_vec.add_trace(go.Scatter(
                x=valid[year_col],
                y=valid[col],
                name=name,
                mode="lines+markers",
                line=dict(color=color, width=2.5, shape="spline", smoothing=1.3),
                marker=dict(size=8, color=color,
                            line=dict(width=2, color="#ffffff"), symbol="circle"),
                fill="tozeroy" if do_fill else "none",
                fillcolor=rgba(color, 0.06) if do_fill else "rgba(0,0,0,0)",
                hovertemplate=f"<b>{name}</b><br>Year: %{{x}}<br>Cases: %{{y}}<extra></extra>",
            ))

        if not fig_vec.data:
            fig_vec = empty_fig("No vector disease trend data available")
        else:
            fig_vec.update_layout(**PL(
                "Vector-Borne Disease Trend (Annual Cases)",
                yaxis_title="Cases",
                xaxis_title="Year",
                hovermode="x unified",
                legend=dict(
                    orientation="h", x=0, y=1.10,
                    bgcolor="rgba(0,0,0,0)", font_size=10,
                    itemsizing="constant",
                ),
                margin=dict(l=20, r=20, t=64, b=20),
            ))

    header = section_banner("Human Pillar", "PRIMARY HEALTH CENTRE · BETTAHALASURU")

    population_card = html.Div([
        card_top_bar(C_BLUE),
        html.P("TOTAL POPULATION", style={
            "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
            "fontWeight": "700", "color": MUTED, "letterSpacing": "1.2px",
            "textTransform": "uppercase", "margin": "10px 0 6px",
        }),
        html.Div(str(h_population), style={
            "fontSize": "48px", "fontWeight": "800", "color": C_BLUE,
            "lineHeight": "1", "fontFamily": "'DM Mono',monospace",
            "letterSpacing": "-2px", "marginBottom": "14px",
        }),
        html.Div([
            html.Div([
                html.Span("♂ MALE", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "9px",
                    "fontWeight": "700", "color": C_BLUE,
                    "letterSpacing": "0.8px", "display": "block", "marginBottom": "2px",
                }),
                html.Span(str(h_male), style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "20px",
                    "fontWeight": "700", "color": C_BLUE,
                }),
            ], style={
                "background": rgba(C_BLUE, 0.08),
                "border": f"1px solid {rgba(C_BLUE, 0.25)}",
                "borderRadius": "10px", "padding": "8px 18px",
                "flex": "1", "textAlign": "center",
            }),
            html.Div([
                html.Span("♀ FEMALE", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "9px",
                    "fontWeight": "700", "color": C_PURPLE,
                    "letterSpacing": "0.8px", "display": "block", "marginBottom": "2px",
                }),
                html.Span(str(h_female), style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "20px",
                    "fontWeight": "700", "color": C_PURPLE,
                }),
            ], style={
                "background": rgba(C_PURPLE, 0.08),
                "border": f"1px solid {rgba(C_PURPLE, 0.25)}",
                "borderRadius": "10px", "padding": "8px 18px",
                "flex": "1", "textAlign": "center",
            }),
        ], style={"display": "flex", "gap": "10px"}),
        html.P("Bettahalasuru Village, Karnataka", style={
            "fontSize": "11px", "color": MUTED, "margin": "8px 0 0",
        }),
    ], style={
        **CARD_STYLE,
        "padding": "18px 22px 22px",
        "boxShadow": f"0 4px 24px {rgba(C_BLUE, 0.10)}",
        "flex": "1",
    })

    phc_services_card = html.Div([
        card_top_bar(C_GREEN),
        html.P("PHC SERVICES", style={
            "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
            "fontWeight": "700", "color": MUTED, "letterSpacing": "1.2px",
            "textTransform": "uppercase", "margin": "10px 0 6px",
        }),
        html.Div(str(h_phc_services), style={
            "fontSize": "56px", "fontWeight": "800", "color": C_GREEN,
            "lineHeight": "1", "fontFamily": "'DM Mono',monospace",
            "letterSpacing": "-2px", "marginBottom": "12px",
        }),
        html.P("Screening programs active", style={
            "fontSize": "12px", "color": MUTED, "margin": "0 0 16px",
        }),
        html.Div([
            html.Span("Blood Pressure", style={
                "fontSize": "10px", "padding": "3px 9px", "borderRadius": "20px",
                "background": rgba(C_GREEN, 0.10),
                "border": f"1px solid {rgba(C_GREEN, 0.25)}",
                "color": "#166534", "marginRight": "5px",
                "fontFamily": "'DM Mono',monospace",
            }),
            html.Span("Malaria RDT", style={
                "fontSize": "10px", "padding": "3px 9px", "borderRadius": "20px",
                "background": rgba(C_GREEN, 0.10),
                "border": f"1px solid {rgba(C_GREEN, 0.25)}",
                "color": "#166534", "marginRight": "5px",
                "fontFamily": "'DM Mono',monospace",
            }),
            html.Span("+ more", style={
                "fontSize": "10px", "padding": "3px 9px", "borderRadius": "20px",
                "background": "rgba(0,0,0,0.05)",
                "border": f"1px solid {BORDER}",
                "color": MUTED, "fontFamily": "'DM Mono',monospace",
            }),
        ], style={"display": "flex", "flexWrap": "wrap", "gap": "5px"}),
    ], style={
        **CARD_STYLE,
        "padding": "18px 22px 22px",
        "boxShadow": f"0 4px 24px {rgba(C_GREEN, 0.08)}",
        "flex": "1",
    })

    top_kpi_row = html.Div(
        [population_card, phc_services_card],
        style={"display": "flex", "gap": "20px", "marginBottom": "28px"},
    )

    VECTOR_DEFS = [
        ("🦟", "MALARIA",       C_BLUE,   malaria_cases,     malaria_insight),
        ("🦟", "DENGUE",        C_RED,    dengue_cases,      dengue_insight),
        ("🦟", "CHIKUNGUNYA",   C_PURPLE, chikungunya_cases, chikungunya_insight),
        ("🌧",  "RAINFALL LINK", C_AMBER,  rainfall_val,      rainfall_insight),
    ]

    def vector_mini(icon, title, color_hex, value_str, insight_str, is_last=False):
        return html.Div([
            html.Div(style={
                "height": "2px", "background": color_hex,
                "borderRadius": "1px", "marginBottom": "10px", "opacity": "0.7",
            }),
            html.Div([
                html.Span(icon,  style={"fontSize": "15px"}),
                html.Span(title, style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "9px",
                    "fontWeight": "700", "color": color_hex,
                    "letterSpacing": "0.8px", "textTransform": "uppercase",
                }),
            ], style={"display": "flex", "alignItems": "center",
                      "gap": "5px", "marginBottom": "6px"}),
            html.P(str(value_str), style={
                "fontFamily": "'DM Mono',monospace", "fontSize": "20px",
                "fontWeight": "700", "color": color_hex,
                "margin": "0 0 5px", "lineHeight": "1",
            }),
            html.P(str(insight_str), style={
                "fontSize": "10px", "color": MUTED,
                "margin": "0", "lineHeight": "1.55",
            }),
        ], style={
            "flex": "1",
            "minWidth": "0",
            "padding": "0 20px 0 0" if not is_last else "0",
            "borderRight": f"1px solid {BORDER}" if not is_last else "none",
        })

    vector_mini_cards = [
        vector_mini(
            icon=icon,
            title=title,
            color_hex=color,
            value_str=value,
            insight_str=insight,
            is_last=(i == len(VECTOR_DEFS) - 1),
        )
        for i, (icon, title, color, value, insight) in enumerate(VECTOR_DEFS)
    ]

    vector_cluster = html.Div([
        html.Div([
            html.Div(style={
                "width": "3px", "height": "18px", "background": C_BLUE,
                "borderRadius": "2px", "marginRight": "10px",
            }),
            html.P(
                "Vector-Borne Disease — Rainfall Correlation & Key Findings",
                style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED,
                    "letterSpacing": "1.2px", "textTransform": "uppercase", "margin": "0",
                }
            ),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "18px"}),
        html.Div(
            vector_mini_cards,
            style={"display": "flex", "gap": "20px", "alignItems": "flex-start"},
        ),
    ], style={
        **CARD_STYLE,
        "padding": "20px 24px 22px",
        "marginBottom": "28px",
        "boxShadow": "0 2px 16px rgba(0,0,0,0.05)",
    })

    charts_row = grid2([
        chart_card(
            html.Div([
                dcc.Graph(
                    figure=fig_dis,
                    config={"displayModeBar": False},
                    style={"height": "360px"},
                ),
            ]),
            "blue",
        ),
        chart_card(
            html.Div([
                dcc.Graph(
                    figure=fig_vec,
                    config={"displayModeBar": False},
                    style={"height": "360px"},
                ),
            ]),
            "green",
        ),
    ])

    burden_screening = grid2([
        html.Div([
            card_top_bar(C_BLUE),
            html.Div(style={"height": "6px"}),
            card_title("Disease Burden by Category"),
            progress_bar("Hypertension & CVD",       db_hyp_sub,  db_hyp_pct,  "red"),
            progress_bar("Diabetes (Type 2)",         db_diab_sub, db_diab_pct, "amber"),
            progress_bar("Tuberculosis",              db_tb_sub,   db_tb_pct,   "red"),
            progress_bar("Anemia (women & children)", db_anm_sub,  db_anm_pct,  "purple"),
            progress_bar("Malaria (seasonal)",        db_mal_sub,  db_mal_pct,  "blue"),
            progress_bar("Dengue",                    db_den_sub,  db_den_pct,  "red"),
            progress_bar("Leptospirosis",             db_lep_sub,  db_lep_pct,  "green"),
        ], style=CARD_STYLE),

        html.Div([
            card_top_bar(C_PURPLE),
            html.Div(style={"height": "6px"}),
            card_title("PHC Screening Programs"),
            data_table_wrap(
                [("Screening Type", 2), ("Frequency", 1), ("Status", 1)],
                screening_rows if screening_rows else [
                    [("Blood Pressure Monitoring", 2), ("Weekly",       1), (badge("Active",   "good"), 1)],
                    [("Blood Sugar Testing",        2), ("Weekly",       1), (badge("Active",   "good"), 1)],
                    [("Antenatal Care",             2), ("Weekly",       1), (badge("Active",   "good"), 1)],
                    [("TB Sputum / Chest X-Ray",   2), ("Symptomatic",  1), (badge("Active",   "good"), 1)],
                    [("Malaria & Dengue RDT",       2), ("Peak seasons", 1), (badge("Seasonal", "warn"), 1)],
                    [("HIV Testing",                2), ("On request",   1), (badge("Active",   "good"), 1)],
                    [("Eye & Vision Screening",     2), ("Health camps", 1), (badge("Periodic", "info"), 1)],
                    [("Anemia (Hemoglobin)",        2), ("Weekly",       1), (badge("Active",   "good"), 1)],
                ],
            ),
        ], style=CARD_STYLE),
    ])

    insights = html.Div(disease_insight_rows) if disease_insight_rows else html.Div([
        insight_row(
            f"{r.get('disease','')}: {r.get('casesRange','')} cases — {r.get('insight','')}",
            [C_BLUE, C_RED, C_AMBER][i % 3],
        )
        for i, (_, r) in enumerate(vi.iterrows())
    ] if not vi.empty else [])

    return html.Div([
        header,
        top_kpi_row,
        vector_cluster,
        charts_row,
        burden_screening,
        insights,
    ])


def page_animal(d):
    rp   = d.get("rabiesProjection", pd.DataFrame())
    abc  = d.get("abcProgram",       pd.DataFrame())
    amr  = d.get("amrFindings",      pd.DataFrame())
    ai   = d.get("animalInsights",   pd.DataFrame())
    akpi = d.get("animal_kpi_data",  pd.DataFrame())
    abl  = d.get("antibioticLevels", pd.DataFrame())

    # ── Exact KPI values (strip ranges and "+" suffix) ────────────────────────
    a_stray_dogs_raw = kpi_val_from_wide(akpi, ["strayDogs", "stray_dogs", "stray dogs"], "73")
    _stray_num = 73
    try:
        _stray_num = int(str(a_stray_dogs_raw).replace("+", "").replace(",", "").strip())
    except Exception:
        _stray_num = 73
    a_stray_dogs = str(_stray_num)

    a_abc_count_raw = kpi_val_from_wide(akpi, ["abcProgramCount", "abc_program_count", "abcProgram", "abc", "abcCount"], "17")
    _abc_num = 17
    try:
        _abc_num = int(str(a_abc_count_raw).replace("+", "").replace(",", "").strip())
    except Exception:
        _abc_num = 17
    a_abc_count = str(_abc_num)

    _abc_coverage_pct = round((_abc_num / max(_stray_num, 1)) * 100, 1)
    a_abc_coverage = f"{_abc_coverage_pct}%"

    _livestock_raw = kpi_val_from_wide(akpi, ["livestockMonitored", "livestock_monitored", "livestock"], "850")
    _livestock_num = 850
    try:
        clean = str(_livestock_raw).replace(",", "").strip()
        if "-" in clean:
            parts = [float(x.strip()) for x in clean.split("-")]
            _livestock_num = int(sum(parts) / len(parts))
        else:
            _livestock_num = int(float(clean.replace("+", "")))
    except Exception:
        _livestock_num = 850
    a_livestock = f"{_livestock_num:,}"

    a_rabies_rate_raw = kpi_val_from_wide(akpi,
        ["rabiesInfectionRate", "rabiesInfectionReductionPercent", "rabiesRate",
         "rabies_rate", "rabiesInfRate", "rabiesInf"], "13")
    try:
        _rabies_pct = float(str(a_rabies_rate_raw).replace("%", "").strip())
        if _rabies_pct < 1:
            _rabies_pct = round(_rabies_pct * 100, 1)
        a_rabies_rate = f"{_rabies_pct:.0f}"
    except Exception:
        a_rabies_rate = "13"

    a_amr_status = kpi_val_from_wide(akpi, ["amrStatus", "AMR Status", "amrOverall", "antibioticStatus"], "Safe")

    gauge_val = float(_stray_num)

    ai_insight_col = find_col(ai, ["insight", "insight_text", "finding", "text", "description"])
    ai_metric_col  = find_col(ai, ["metric", "name", "category"])
    ai_value_col   = find_col(ai, ["value", "data_value", "pct"])

    def get_ai_metric(name, default):
        if ai_metric_col and ai_value_col and not ai.empty:
            row = ai[ai[ai_metric_col].astype(str).str.strip().str.lower().str.contains(name.lower())]
            if not row.empty:
                val = str(row[ai_value_col].iloc[0]).strip()
                return val if val and val.lower() != "nan" else default
        return default

    neutered_infection_rate     = get_ai_metric("neutered infection",    "13%")
    non_neutered_infection_rate = get_ai_metric("non.neutered infection", "9%")

    abc_date_col     = find_col(abc, ["date"])
    abc_activity_col = find_col(abc, ["activity"])
    abc_count_col    = find_col(abc, ["count", "value"])

    abc_table_rows_dynamic = []
    if abc_date_col and abc_activity_col and abc_count_col and not abc.empty:
        for _, row in abc.iterrows():
            cnt_val = str(row.get(abc_count_col, "")).strip()
            cnt_badge = badge(cnt_val, "good") if cnt_val and cnt_val.lower() != "nan" else badge("\u2014", "info")
            date_raw = row.get(abc_date_col, "")
            try:
                date_str = pd.to_datetime(date_raw).strftime("%d-%b-%Y")
            except Exception:
                date_str = str(date_raw).strip()
            abc_table_rows_dynamic.append([
                (date_str,                                        1.5),
                (str(row.get(abc_activity_col, "")).strip(),      3),
                (cnt_badge,                                       1),
            ])

    abc_table_rows = abc_table_rows_dynamic if abc_table_rows_dynamic else [
        [("05-Mar-2024", 1.5), ("Dogs picked up from Bettahalasuru village",     3), (badge("17", "info"),  1)],
        [("06-Mar-2024", 1.5), ("Neutering completed + anti-rabies vaccination", 3), (badge("17", "good"),  1)],
        [("07-Mar-2024", 1.5), ("Post-operative care + antibiotic shots (Day 1)",3), (badge("17", "good"),  1)],
        [("11-Mar-2024", 1.5), ("Released at original pickup location",          3), (badge("17", "good"),  1)],
    ]

    amr_ant_col    = find_col(amr, ["antibiotic"])
    amr_sample_col = find_col(amr, ["sampleType", "sample_type", "sample"])
    amr_level_col  = find_col(amr, ["levelFound", "level_found", "level"])
    amr_perm_col   = find_col(amr, ["permissible", "limit", "permissible_limit"])
    amr_stat_col   = find_col(amr, ["status", "result"])

    amr_table_rows_dynamic = []
    if amr_ant_col and amr_sample_col and amr_level_col and not amr.empty:
        for _, row in amr.iterrows():
            stat_txt = str(row.get(amr_stat_col, "Safe")).strip() if amr_stat_col else "Safe"
            stat_txt = stat_txt if stat_txt and stat_txt.lower() != "nan" else "Safe"
            bkind = "good" if stat_txt.lower() in ("safe", "clear", "ok") else "warn"
            perm_val_raw = row.get(amr_perm_col, None) if amr_perm_col else None
            level_raw = row.get(amr_level_col, 0)
            perm_num  = pd.to_numeric(perm_val_raw, errors="coerce")
            level_num = pd.to_numeric(level_raw, errors="coerce")
            if pd.isna(level_num) or level_num <= 0:
                display_level = "< LOD (HPLC)"
                risk_badge    = badge("< LOD", "good")
            else:
                display_level = f"{level_num:.6f} mg/g"
                if pd.notna(perm_num) and perm_num > 0:
                    risk_pct  = round((level_num / perm_num) * 100, 2)
                    risk_badge = badge(f"{risk_pct:.2f}%",
                                       "good" if risk_pct < 50 else ("warn" if risk_pct < 80 else "bad"))
                else:
                    risk_badge = badge("N/A", "info")
            perm_disp = f"{perm_num:.4f} mg/g" if pd.notna(perm_num) else "\u2014"
            amr_table_rows_dynamic.append([
                (str(row.get(amr_ant_col,    "")).strip(), 1.2),
                (str(row.get(amr_sample_col, "")).strip(), 1.4),
                (display_level,                            1.4),
                (perm_disp,                                1.2),
                (risk_badge,                               1),
                (badge(stat_txt, bkind),                   0.8),
            ])

    amr_table_rows = amr_table_rows_dynamic if amr_table_rows_dynamic else [
        [("Doxycycline", 1.2), ("Pig Excreta", 1.4), ("0.000002 mg/g", 1.4), ("0.0200 mg/g", 1.2), (badge("0.01%",  "good"), 1), (badge("Safe",  "good"), 0.8)],
        [("Doxycycline", 1.2), ("Hen Excreta", 1.4), ("0.003480 mg/g", 1.4), ("0.0200 mg/g", 1.2), (badge("17.40%", "good"), 1), (badge("Safe",  "good"), 0.8)],
        [("Amoxicillin", 1.2), ("Feed",        1.4), ("< LOD (HPLC)", 1.4),  ("\u2014",      1.2), (badge("< LOD",  "good"), 1), (badge("Clear", "good"), 0.8)],
        [("Amoxicillin", 1.2), ("Excreta",     1.4), ("< LOD (HPLC)", 1.4),  ("\u2014",      1.2), (badge("< LOD",  "good"), 1), (badge("Clear", "good"), 0.8)],
        [("Amoxicillin", 1.2), ("Water",       1.4), ("< LOD (HPLC)", 1.4),  ("\u2014",      1.2), (badge("< LOD",  "good"), 1), (badge("Clear", "good"), 0.8)],
    ]

    rp_year_col = find_col(rp, ["year"])
    fig_rab = empty_fig("No rabies projection data available")
    if rp_year_col:
        rp_plot = coerce_numeric(rp, [rp_year_col])
        import numpy as np
        base_case   = 10.0
        growth_rate = 0.57
        vacc_effect = 0.52
        t_arr = np.arange(1, 6)
        model_no_abc   = [round(base_case * ((1 + growth_rate) ** t), 1)               for t in t_arr]
        model_abc_vacc = [round(base_case * ((1 + growth_rate - vacc_effect) ** t), 1) for t in t_arr]
        fig_rab = go.Figure()
        for col, color, dash, name in [
            (find_col(rp, ["noAbc"]),              C_RED,   "dot",   "No Intervention (Data)"),
            (find_col(rp, ["withAbc"]),            C_AMBER, "dash",  "ABC Only (Data)"),
            (find_col(rp, ["withAbcVaccination"]), C_GREEN, "solid", "ABC + Vaccination (Data)"),
        ]:
            if col:
                rp_plot2 = coerce_numeric(rp_plot, [col])
                valid = rp_plot2[[rp_year_col, col]].dropna()
                if valid.empty:
                    continue
                fig_rab.add_trace(go.Scatter(
                    x=valid[rp_year_col], y=valid[col], name=name, mode="lines+markers",
                    line=dict(color=color, width=2.5, dash=dash),
                    marker=dict(size=7, color=color),
                    fill="tozeroy" if "No Intervention" in name else "none",
                    fillcolor=rgba(C_RED, 0.05),
                    hovertemplate=f"<b>{name}</b><br>Year: %{{x}}<br>Infected: %{{y}}<extra></extra>",
                ))
        fig_rab.add_trace(go.Scatter(
            x=list(t_arr), y=model_no_abc, name="Model: No Intervention",
            mode="lines", line=dict(color=rgba(C_RED, 0.4), width=1.5, dash="dot"),
            hovertemplate="<b>Model (no ABC)</b><br>Year: %{x}<br>Projected: %{y}<br><i>10\xd7(1+0.57)^t</i><extra></extra>",
        ))
        fig_rab.add_trace(go.Scatter(
            x=list(t_arr), y=model_abc_vacc, name="Model: ABC+Vaccination",
            mode="lines", line=dict(color=rgba(C_GREEN, 0.4), width=1.5, dash="dot"),
            hovertemplate="<b>Model (ABC+Vacc)</b><br>Year: %{x}<br>Projected: %{y}<br><i>10\xd7(1+0.57\u22120.52)^t</i><extra></extra>",
        ))
    fig_rab.update_layout(**PL("Rabies Projection \u2014 5-Year (Actual vs Dynamic Model)",
                                yaxis_title="Infected Animals", xaxis_title="Year",
                                legend=dict(orientation="h", x=0, y=1.14, font_size=9),
                                margin=dict(l=20, r=20, t=80, b=20)))

    fig_abc = empty_fig("No ABC programme data available")
    if abc_activity_col and abc_count_col and not abc.empty:
        abc_plot = coerce_numeric(abc, [abc_count_col]).dropna(subset=[abc_activity_col, abc_count_col])
        step_cols = [C_RED, C_AMBER, C_AMBER, C_AMBER, C_AMBER, C_AMBER, C_GREEN]
        fig_abc = go.Figure()
        for i, (_, row) in enumerate(abc_plot.iterrows()):
            fig_abc.add_trace(go.Bar(
                x=[row[abc_count_col]], y=[row[abc_activity_col]], orientation="h",
                marker_color=step_cols[min(i, len(step_cols) - 1)],
                showlegend=False,
                hovertemplate=f"<b>{row[abc_activity_col]}</b><br>Animals: {row[abc_count_col]}<extra></extra>",
            ))
        if not fig_abc.data:
            fig_abc = empty_fig("No ABC programme data available")
    abc_pl = {k: v for k, v in PL("ABC Programme \u2014 Bettahalasuru (Mar 2024)").items() if k != "xaxis"}
    fig_abc.update_layout(**abc_pl)
    fig_abc.update_xaxes(gridcolor="rgba(0,0,0,0.08)", linecolor=BORDER,
                          tickfont_color=MUTED, title_text="Animals")

    amr_antibiotic_col_c = find_col(amr, ["antibiotic"])
    amr_sample_col_c     = find_col(amr, ["sampleType", "sample_type", "sample"])
    amr_level_col_c      = find_col(amr, ["levelFound", "level_found", "level"])
    amr_limit_col_c      = find_col(amr, ["permissible", "limit"])
    fig_amr = empty_fig("No AMR findings data available")
    if amr_antibiotic_col_c and amr_sample_col_c and amr_level_col_c and amr_limit_col_c:
        amr_v = coerce_numeric(amr, [amr_level_col_c, amr_limit_col_c])
        amr_v = amr_v.dropna(subset=[amr_antibiotic_col_c, amr_sample_col_c,
                                      amr_level_col_c, amr_limit_col_c]).copy()
        if not amr_v.empty:
            amr_v["_risk_pct"] = (amr_v[amr_level_col_c] / amr_v[amr_limit_col_c] * 100).round(2)
            xlabels = amr_v[amr_antibiotic_col_c].astype(str) + " / " + amr_v[amr_sample_col_c].astype(str)
            fig_amr = go.Figure()
            fig_amr.add_trace(go.Bar(
                x=xlabels, y=amr_v["_risk_pct"],
                name="AMR Risk Index (%)",
                marker_color=[C_GREEN if v < 50 else (C_AMBER if v < 80 else C_RED)
                              for v in amr_v["_risk_pct"]],
                marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>Risk Index: %{y:.2f}%<br>(Detected \xf7 Limit \xd7 100)<extra></extra>",
            ))
            fig_amr.add_hline(y=50, line_dash="dot", line_color=C_AMBER, line_width=1.5,
                              annotation_text="Moderate risk (50%)",
                              annotation_font=dict(color=C_AMBER, size=9))
            fig_amr.add_hline(y=80, line_dash="dot", line_color=C_RED, line_width=1.5,
                              annotation_text="High risk (80%)",
                              annotation_font=dict(color=C_RED, size=9))
    fig_amr.update_layout(**PL("AMR Risk Index (%) \u2014 Detected \xf7 Permissible Limit \xd7 100",
                                yaxis_title="AMR Risk Index (%)"))

    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=gauge_val,
        title={"text": f"Stray Dogs \u2014 ABC Coverage {a_abc_coverage}", "font": {"color": C_AMBER, "size": 12}},
        number={"font": {"color": C_AMBER, "size": 42}},
        gauge=dict(
            axis=dict(range=[0, 120], tickcolor=MUTED, tickfont_color=MUTED),
            bar=dict(color=C_AMBER, thickness=0.28),
            bgcolor="#ffffff", bordercolor=BORDER,
            steps=[
                dict(range=[0,   30], color="#f0fdf4"),
                dict(range=[30,  60], color="#fef3c7"),
                dict(range=[60,  90], color="#fff7ed"),
                dict(range=[90, 120], color="#fee2e2"),
            ],
            threshold=dict(line=dict(color=C_GREEN, width=2.5), value=_abc_num),
        ),
    ))
    fig_g.update_layout(**PLgauge(), height=250, margin=dict(l=24, r=24, t=44, b=16))

    _sheet_insights = []
    if ai_insight_col and not ai.empty:
        for _, row in ai.iterrows():
            txt = str(row.get(ai_insight_col, "")).strip()
            if txt and txt.lower() != "nan":
                _sheet_insights.append(txt)

    _computed_5 = [
        f"ABC Coverage: {_abc_num}/{_stray_num} stray dogs ({a_abc_coverage}) neutered + vaccinated in the March 2024 programme",
        f"AMR Risk Index (HPLC): Doxycycline in Hen Excreta at 17.4% of permissible limit \u2014 within safe range (<50%)",
        "Amoxicillin in feed, excreta, and water all below Limit of Detection \u2014 no detectable residue via HPLC analysis",
        "Dynamic model: ABC + Vaccination projects ~93% reduction in 5-year rabies caseload vs no-intervention baseline",
        f"Livestock ~{_livestock_num:,} animals via Vet Department \u2014 annual HPLC-based AMR surveillance recommended",
    ]

    _all_ins = _sheet_insights + [x for x in _computed_5 if x not in _sheet_insights]
    _ins_colors = [C_RED, C_AMBER, C_GREEN, C_BLUE, C_PURPLE]
    final_insight_rows = [insight_row(t, _ins_colors[i % 5]) for i, t in enumerate(_all_ins[:5])]

    from datetime import datetime as _dt
    _ts = _dt.now().strftime("%d %b %Y %H:%M")
    timestamp_badge = html.Div([
        html.Span("\u23f1 Data refreshed: ", style={"color": MUTED, "fontSize": "11px"}),
        html.Span(_ts, style={"fontFamily": "'DM Mono',monospace", "fontSize": "11px",
                              "color": C_GREEN, "fontWeight": "600"}),
        html.Span("  \xb7  Detection: HPLC (High Performance Liquid Chromatography)",
                  style={"color": MUTED, "fontSize": "10px", "marginLeft": "6px"}),
    ], style={
        "padding": "6px 14px", "borderRadius": "8px",
        "background": rgba(C_GREEN, 0.05), "border": f"1px solid {rgba(C_GREEN, 0.2)}",
        "marginBottom": "20px", "display": "inline-flex", "alignItems": "center",
    })

    return html.Div([
        section_banner("Animal Pillar",
                        "STRAY DOG MANAGEMENT \xb7 LIVESTOCK AMR \xb7 POULTRY & PIGGERY \xb7 BETTAHALASURU"),
        timestamp_badge,
        html.Div([
            kpi_card("Stray Dogs",       a_stray_dogs,     "",         "Village census (Mar 2024)",        "blue"),
            kpi_card("ABC Programme",    a_abc_count,      "animals",  "Neutered + anti-rabies shots",     "green"),
            kpi_card("ABC Coverage",     a_abc_coverage,   "",         f"{_abc_num}/{_stray_num} dogs",    "purple"),
            kpi_card("Rabies Rate",      a_rabies_rate,    "% (ABC)",  "Post-ABC cohort infection rate",   "red"),
            kpi_card("Livestock",        a_livestock,      "animals",  "Via Vet Dept (midpoint est.)",     "amber"),
            kpi_card("AMR Status",       a_amr_status,     "",         "HPLC \u2014 Within permissible limits", "green"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(6,1fr)",
                  "gap": "12px", "marginBottom": "20px"}),
        grid2([
            chart_card(dcc.Graph(figure=fig_rab, config={"displayModeBar": False}), "red"),
            chart_card(dcc.Graph(figure=fig_abc, config={"displayModeBar": False}), "amber"),
        ]),
        grid2([
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                card_title("Stray Dog ABC Programme \u2014 Bettahalasuru (Mar 2024)"),
                data_table_wrap(
                    [("Date", 1.5), ("Activity", 3), ("Count", 1)],
                    abc_table_rows,
                ),
                html.Div([
                    html.P("ABC Programme \u2014 Key Insight", style={
                        "fontFamily": "'DM Mono',monospace", "fontSize": "10px", "fontWeight": "700",
                        "color": MUTED, "letterSpacing": "1px", "textTransform": "uppercase",
                        "margin": "0 0 6px",
                    }),
                    html.P([
                        "Neutering alone reduces population growth but rabies vaccination is essential. "
                        "Post-ABC cohort shows a ",
                        html.Strong(f"{a_rabies_rate}% infection rate", style={"color": C_RED}),
                        " \u2014 a combined population control + vaccination strategy is required for sustained control.",
                    ], style={"fontSize": "12px", "color": MUTED, "lineHeight": "1.7"}),
                ], style={"padding": "12px", "background": rgba(C_BLUE, 0.04), "borderRadius": "8px",
                          "borderLeft": f"3px solid {C_BLUE}"}),
            ], style=CARD_STYLE),
            chart_card(html.Div([
                card_title("AMR Risk Index \u2014 Detected Level \xf7 Permissible Limit \xd7 100"),
                dcc.Graph(figure=fig_amr, config={"displayModeBar": False}),
            ]), "green"),
        ]),
        grid2([
            chart_card(dcc.Graph(figure=fig_g, config={"displayModeBar": False}), "amber"),
            html.Div([
                card_top_bar(C_RED),
                html.Div(style={"height": "6px"}),
                card_title("Livestock AMR \u2014 HPLC Residue Analysis with Risk Index"),
                data_table_wrap(
                    [("Antibiotic", 1.2), ("Sample", 1.4), ("Detected (mg/g)", 1.4),
                     ("Permissible", 1.2), ("Risk Index", 1), ("Status", 0.8)],
                    amr_table_rows,
                ),
                html.Div(
                    "Detection via HPLC. Values at or below the instrument detection limit reported as "
                    "< LOD. AMR Risk Index = (Detected \xf7 Permissible Limit) \xd7 100. "
                    "All current levels pose no immediate AMR risk.",
                    style={"fontSize": "11px", "color": MUTED, "padding": "10px", "lineHeight": "1.6",
                           "background": rgba(C_GREEN, 0.05), "borderRadius": "6px",
                           "borderLeft": f"3px solid {C_GREEN}"}
                ),
            ], style=CARD_STYLE),
        ]),
        html.Div([
            html.Div([
                html.Div(style={"width": "3px", "height": "18px", "background": C_BLUE,
                                "borderRadius": "2px", "marginRight": "10px"}),
                html.P("Key Findings & Computed Metrics", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED, "letterSpacing": "1.2px",
                    "textTransform": "uppercase", "margin": "0",
                }),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "14px"}),
            *final_insight_rows,
        ], style={**CARD_STYLE, "padding": "20px 24px", "marginTop": "8px"}),
    ])




# ══════════════════════════════════════════════════════════════════════════════
# CALIBRATION DASHBOARD HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _build_calib_content(drug_filter):
    doxy_raw = DATA.get("Doxy_Calibration", pd.DataFrame())
    amox_raw = DATA.get("Amox_Calibration", pd.DataFrame())

    def prep(df, drug_name):
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        expected_col = find_col(df, ["Expected Conc (ng/mL)", "Expected Conc", "expected_conc", "ExpectedConc"])
        final_col    = find_col(df, ["Final Conc (ng/mL)",   "Final Conc",    "final_conc",    "FinalConc"])
        accuracy_col = find_col(df, ["Accuracy (%)", "Accuracy", "accuracy"])
        peak_col     = find_col(df, ["Peak Area", "peak_area", "PeakArea"])
        sample_col   = find_col(df, ["Sample File", "sample_file", "SampleFile", "sample"])
        if not all([expected_col, final_col, accuracy_col, peak_col]):
            return pd.DataFrame()
        df = coerce_numeric(df, [expected_col, final_col, accuracy_col, peak_col])
        df = df.dropna(subset=[expected_col, accuracy_col, peak_col])
        df["_drug"]     = drug_name
        df["_expected"] = df[expected_col]
        df["_final"]    = df[final_col]
        df["_accuracy"] = df[accuracy_col]
        df["_peak"]     = df[peak_col]
        df["_sample"]   = df[sample_col].astype(str) if sample_col else "—"
        df["_qc_pass"]  = (df["_accuracy"] >= 80) & (df["_accuracy"] <= 120)
        return df

    doxy = prep(doxy_raw, "Doxycycline")
    amox = prep(amox_raw, "Amoxicillin")

    if drug_filter == "doxy":
        frames = [doxy] if not doxy.empty else []
    elif drug_filter == "amox":
        frames = [amox] if not amox.empty else []
    else:
        frames = [df for df in [doxy, amox] if not df.empty]

    if not frames:
        empty = go.Figure()
        empty.add_annotation(text="No calibration data available", x=0.5, y=0.5,
                             xref="paper", yref="paper", showarrow=False, font=dict(size=14))
        empty.update_layout(**PL("Calibration"))
        empty_card = chart_card(dcc.Graph(figure=empty, config={"displayModeBar": False}), "blue", span=2)
        return html.Div([empty_card]), html.Div()

    combined = pd.concat(frames, ignore_index=True)

    DRUG_COLORS = {"Doxycycline": C_BLUE, "Amoxicillin": C_GREEN}
    fig_curve    = go.Figure()
    fig_accuracy = go.Figure()
    metric_list  = []

    for drug, grp in combined.groupby("_drug"):
        color    = DRUG_COLORS.get(drug, C_BLUE)
        pass_df  = grp[grp["_qc_pass"]].copy()
        fail_df  = grp[~grp["_qc_pass"]].copy()

        if not pass_df.empty:
            fig_curve.add_trace(go.Scatter(
                x=pass_df["_expected"], y=pass_df["_peak"],
                mode="markers", name=f"{drug} (pass)",
                marker=dict(color=color, size=9, line=dict(width=1, color="white")),
                customdata=pass_df[["_sample", "_expected", "_final", "_accuracy"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Expected: %{customdata[1]:.2f} ng/mL<br>"
                    "Final: %{customdata[2]:.2f} ng/mL<br>"
                    "Accuracy: %{customdata[3]:.1f}%<extra></extra>"
                ),
            ))

        if not fail_df.empty:
            fig_curve.add_trace(go.Scatter(
                x=fail_df["_expected"], y=fail_df["_peak"],
                mode="markers", name=f"{drug} (fail)",
                marker=dict(color=C_RED, size=9, symbol="x",
                            line=dict(width=2, color=C_RED)),
                customdata=fail_df[["_sample", "_expected", "_final", "_accuracy"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Expected: %{customdata[1]:.2f} ng/mL<br>"
                    "Final: %{customdata[2]:.2f} ng/mL<br>"
                    "Accuracy: %{customdata[3]:.1f}%<extra></extra>"
                ),
            ))

        r2_val = None
        if len(pass_df) >= 2:
            x_p = pass_df["_expected"].values.astype(float)
            y_p = pass_df["_peak"].values.astype(float)
            try:
                coeffs  = np.polyfit(x_p, y_p, 1)
                x_line  = np.linspace(x_p.min(), x_p.max(), 300)
                y_line  = np.polyval(coeffs, x_line)
                y_pred  = np.polyval(coeffs, x_p)
                ss_res  = np.sum((y_p - y_pred) ** 2)
                ss_tot  = np.sum((y_p - y_p.mean()) ** 2)
                r2_val  = float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0
                fig_curve.add_trace(go.Scatter(
                    x=x_line, y=y_line, mode="lines",
                    name=f"{drug} fit (R²={r2_val:.4f})",
                    line=dict(color=color, width=2, dash="dash"),
                    hoverinfo="skip",
                ))
            except Exception:
                pass

        ref_df = grp.dropna(subset=["_expected", "_final"]).sort_values("_expected")
        if not ref_df.empty:
            fig_curve.add_trace(go.Scatter(
                x=ref_df["_expected"].values,
                y=ref_df["_final"].values,
                mode="lines", name=f"{drug} ideal (y=x)",
                line=dict(color=rgba(color, 0.35), width=1.5, dash="dot"),
                hoverinfo="skip",
            ))

        acc_df = grp.dropna(subset=["_expected", "_accuracy"]).sort_values("_expected")
        if not acc_df.empty:
            bar_colors = [color if p else C_RED for p in acc_df["_qc_pass"]]
            fig_accuracy.add_trace(go.Bar(
                x=[f"{v:.2f}" for v in acc_df["_expected"]],
                y=acc_df["_accuracy"],
                name=drug,
                marker_color=bar_colors,
                marker_line_width=0,
                hovertemplate="Expected: %{x} ng/mL<br>Accuracy: %{y:.1f}%<extra></extra>",
            ))

        metric_list.append({
            "drug":  drug,
            "r2":    r2_val,
            "excl":  len(fail_df),
            "pass":  len(pass_df),
        })

    fig_accuracy.add_hrect(
        y0=80, y1=120,
        fillcolor=rgba(C_GREEN, 0.08), line_width=0,
        annotation_text="QC Pass (80–120%)",
        annotation_font=dict(color=C_GREEN, size=9),
    )
    fig_accuracy.add_hline(y=80,  line_dash="dot", line_color=C_GREEN, line_width=1.2)
    fig_accuracy.add_hline(y=120, line_dash="dot", line_color=C_GREEN, line_width=1.2)

    fig_curve.update_layout(**PL(
        "Calibration Curve — Peak Area vs Expected Conc",
        xaxis_title="Expected Conc (ng/mL)",
        yaxis_title="Peak Area",
    ))
    fig_curve.update_xaxes(zeroline=False)

    fig_accuracy.update_layout(**PL(
        "Accuracy Plot — QC Band 80–120%",
        barmode="group",
        xaxis_title="Expected Conc (ng/mL)",
        yaxis_title="Accuracy (%)",
    ))
    fig_accuracy.update_xaxes(tickangle=-30)

    charts_div = grid2([
        chart_card(dcc.Graph(figure=fig_curve,    config={"displayModeBar": False}), "blue"),
        chart_card(dcc.Graph(figure=fig_accuracy, config={"displayModeBar": False}), "green"),
    ])

    mc = []
    for m in metric_list:
        r2_str = f"{m['r2']:.4f}" if m["r2"] is not None else "N/A"
        mc += [
            kpi_card(f"{m['drug']} R²",    r2_str,       "",    "QC-pass regression",        "blue"),
            kpi_card(f"{m['drug']} Curve", str(m["pass"]), "pts", "QC-pass data points",      "green"),
            kpi_card(f"{m['drug']} Excl.", str(m["excl"]), "pts", "QC-fail (excluded)",        "red"),
            kpi_card("QC Range",           "80–120",      "%",   "Fixed acceptance window",   "amber"),
        ]

    n_cols   = min(len(mc), 8)
    n_cols   = max(n_cols, 1)
    metrics_div = html.Div(mc, style={
        "display": "grid",
        "gridTemplateColumns": f"repeat({n_cols}, 1fr)",
        "gap": "12px", "marginBottom": "20px",
    })

    return charts_div, metrics_div


def page_environment(d):
    wq  = d.get("water_quality",       pd.DataFrame())
    vc  = d.get("villagewatercfu",     pd.DataFrame())
    lc  = d.get("lake_water_cfu",      pd.DataFrame())
    gsd = d.get("gram_staining_data",  pd.DataFrame())
    mc  = d.get("microbial_analysis",  pd.DataFrame())
    sc  = d.get("soil_cfu",            pd.DataFrame())
    pv  = d.get("physiochem_village_waterquality", pd.DataFrame())

    gs = parse_gram_staining(d)
    total_isolates = gs["total_isolates"]
    gram_neg_pct   = gs["gram_neg_pct"]
    gram_neg_count = gs["gram_neg_count"]
    bacillus_pct   = gs["bacillus_pct"]
    cocci_pct      = gs["cocci_pct"]
    mucoid_pct     = gs["mucoid_pct"]

    # ── AQI and humidity from LIVE scrape (with sheet fallback) ──────────────
    live_aqi_str, live_hum_str = get_live_aqi_humidity(d)

    try:
        aqi_val = float(live_aqi_str) if live_aqi_str not in (None, "—") else 135
    except (TypeError, ValueError):
        aqi_val = 135

    humidity_val = live_hum_str if live_hum_str not in (None, "—") else "—"

    effluent_tds = "—"
    wq_source_col_e = find_col(wq, ["source_name", "sourceName", "source", "location", "label"])
    wq_tds_col_e    = find_col(wq, ["TDS_ppm", "TDS", "tds"])
    wq_id_col_kpi   = find_col(wq, ["sampleId", "sample_id", "id", "sample_no", "Sample no.", "Sample no"])

    if not wq.empty and wq_tds_col_e:
        if wq_id_col_kpi:
            s1_mask = wq[wq_id_col_kpi].astype(str).str.strip().str.lower().isin(["s1", "1", "sample 1", "sample1"])
            if s1_mask.any():
                tds_raw = pd.to_numeric(wq.loc[s1_mask, wq_tds_col_e].iloc[0], errors="coerce")
                if pd.notna(tds_raw):
                    effluent_tds = f"{int(tds_raw):,}"
        if effluent_tds == "—" and wq_source_col_e:
            mask = wq[wq_source_col_e].astype(str).str.lower().str.contains("effluent|household", na=False)
            if mask.any():
                tds_raw = pd.to_numeric(wq.loc[mask, wq_tds_col_e].iloc[0], errors="coerce")
                if pd.notna(tds_raw):
                    effluent_tds = f"{int(tds_raw):,}"
        if effluent_tds == "—":
            tds_raw = pd.to_numeric(wq[wq_tds_col_e].iloc[0], errors="coerce")
            if pd.notna(tds_raw):
                effluent_tds = f"{int(tds_raw):,}"

    wq_tds_col       = find_col(wq, ["TDS_ppm", "TDS"])
    wq_do_col        = find_col(wq, ["DO_mg_L", "DO"])
    wq_status_col    = find_col(wq, ["drinking_status", "drinkingStatus"])
    wq_turbidity_col = find_col(wq, ["turbidity_NTU", "turbidity"])
    wq_source_col    = find_col(wq, ["source_name", "sourceName", "source", "location"])
    fig_wq = empty_fig("No water quality data available")
    if all([wq_tds_col, wq_do_col, wq_status_col, wq_turbidity_col, wq_source_col]):
        wq_plot = coerce_numeric(wq, [wq_tds_col, wq_do_col, wq_turbidity_col])
        wq_plot = wq_plot.dropna(subset=[wq_tds_col, wq_do_col, wq_turbidity_col, wq_status_col, wq_source_col]).copy()
        color_map = {"Unfit": C_RED, "Treat First": C_AMBER, "Borderline": C_PURPLE, "Agriculture": C_GREEN}
        if not wq_plot.empty:
            fig_wq = px.scatter(
                wq_plot, x=wq_tds_col, y=wq_do_col, color=wq_status_col,
                color_discrete_map=color_map, size=wq_turbidity_col, size_max=35,
                hover_name=wq_source_col,
                title="Water Potability — TDS vs Dissolved Oxygen",
                labels={wq_tds_col: "TDS (ppm)", wq_do_col: "DO (mg/L)", wq_status_col: "Drinking Status"},
                hover_data=[c for c in [find_col(wq_plot, ["pH"]), find_col(wq_plot, ["EC_mS", "EC_uS"]), wq_turbidity_col] if c],
            )
            fig_wq.add_vline(x=500, line_dash="dot", line_color=C_BLUE, line_width=1.5,
                             annotation_text="TDS safe ≤500 ppm", annotation_font=dict(color=C_BLUE, size=10))
            fig_wq.add_hline(y=6, line_dash="dot", line_color=C_GREEN, line_width=1.5,
                             annotation_text="DO safe ≥6 mg/L", annotation_font=dict(color=C_GREEN, size=10))
    fig_wq.update_layout(**PL("Water Potability — TDS vs Dissolved Oxygen (bubble size = turbidity)"))

    wq_ph_col_r  = find_col(wq, ["pH", "ph"])
    wq_ec_col_r  = find_col(wq, ["EC_mS", "EC_uS", "EC", "ec"])
    wq_ntu_col_r = find_col(wq, ["turbidity_NTU", "turbidity", "NTU"])
    fig_physchem = empty_fig("No physicochemical data available")

    if wq_source_col and wq_ph_col_r and wq_ec_col_r and wq_ntu_col_r and not wq.empty:
        pc_plot = coerce_numeric(wq, [wq_ph_col_r, wq_ec_col_r, wq_ntu_col_r])
        pc_plot = pc_plot.dropna(subset=[wq_source_col, wq_ph_col_r, wq_ec_col_r]).copy()

        if not pc_plot.empty:
            def norm_col(col):
                mn, mx = pc_plot[col].min(), pc_plot[col].max()
                if mx == mn:
                    return pd.Series([50.0] * len(pc_plot), index=pc_plot.index)
                return ((pc_plot[col] - mn) / (mx - mn) * 100).round(1)

            pc_plot["pH_norm"]  = norm_col(wq_ph_col_r)
            pc_plot["EC_norm"]  = norm_col(wq_ec_col_r)
            pc_plot["NTU_norm"] = norm_col(wq_ntu_col_r) if wq_ntu_col_r else 0

            params = ["pH (normalised)", "EC (normalised)", "Turbidity (normalised)"]
            norm_cols = ["pH_norm", "EC_norm", "NTU_norm"]
            colors_p = [C_BLUE, C_PURPLE, C_AMBER]

            fig_physchem = go.Figure()
            for norm_c, param, col_c in zip(norm_cols, params, colors_p):
                if norm_c in pc_plot.columns:
                    fig_physchem.add_trace(go.Bar(
                        name=param,
                        x=pc_plot[wq_source_col].astype(str),
                        y=pc_plot[norm_c],
                        marker_color=col_c,
                        marker_line_width=0,
                        hovertemplate=f"<b>%{{x}}</b><br>{param}: %{{y:.1f}}<extra></extra>",
                    ))

            fig_physchem.add_hline(
                y=50,
                line_dash="dot", line_color=C_GREEN, line_width=1.5,
                annotation_text="Mid-range reference",
                annotation_font=dict(color=C_GREEN, size=9),
            )

    fig_physchem.update_layout(**PL(
        "Physicochemical Profile — pH, EC & Turbidity by Source (normalised 0–100)",
        barmode="group",
        yaxis_title="Normalised Score (0–100)",
        xaxis_title="Water Source",
    ))
    fig_physchem.update_xaxes(tickangle=-20)

    vc_source_col = find_col(vc, ["source", "source_name", "sourceName", "sample", "location"])
    vc_mean_col   = find_col(vc, ["mean_cfu", "CFU_avg", "CFU avg"])
    fig_vc = empty_fig("No village water CFU data available")
    if vc_source_col and vc_mean_col:
        vc_s = coerce_numeric(vc, [vc_mean_col]).dropna(subset=[vc_source_col, vc_mean_col]).sort_values(vc_mean_col)
        n = len(vc_s)
        if n:
            bclr = [C_GREEN if i < max(1, n // 2) else C_BLUE for i in range(n)]
            fig_vc = go.Figure()
            fig_vc.add_trace(go.Bar(
                x=vc_s[vc_mean_col], y=vc_s[vc_source_col], orientation="h",
                marker_color=bclr, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>%{x:.3f} CFU/mL<extra></extra>",
            ))
    fig_vc.update_layout(**PL("Village Water Sources — Mean Bacterial CFU/mL", xaxis_title="CFU/mL"))

    lc_sample_col = find_col(lc, ["sample", "location", "source"])
    lc_mean_col   = find_col(lc, ["mean_cfu", "CFU_avg", "CFU avg"])
    fig_lc = empty_fig("No lake water CFU data available")
    if lc_sample_col and lc_mean_col:
        lc_s = coerce_numeric(lc, [lc_mean_col]).dropna(subset=[lc_sample_col, lc_mean_col]).sort_values(lc_mean_col, ascending=False)
        n = len(lc_s)
        if n:
            bclr = [C_RED if i < max(1, n // 3) else (C_AMBER if i < max(2, 2 * n // 3) else C_BLUE) for i in range(n)]
            fig_lc = go.Figure()
            fig_lc.add_trace(go.Bar(
                x=lc_s[lc_sample_col], y=lc_s[lc_mean_col],
                marker_color=bclr, marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>%{y:.3f} CFU/mL<extra></extra>",
            ))
    fig_lc.update_layout(**PL("Lake Entry Points — Mean Bacterial CFU/mL", yaxis_title="CFU/mL"))
    fig_lc.update_xaxes(tickangle=-25)

    soil_data_df = d.get("soil_data", pd.DataFrame())
    fig_soil = empty_fig("No soil data available")

    if not soil_data_df.empty:
        site_col   = find_col(soil_data_df, ["site", "name", "location", "site_name"])
        na2_col    = find_col(soil_data_df, ["na_growth_10_2"])
        na6_col    = find_col(soil_data_df, ["colony_count_10_6"])
        emb_col    = find_col(soil_data_df, ["e_coli_present"])

        if site_col and any([na2_col, na6_col, emb_col]):
            soil_plot = coerce_numeric(
                soil_data_df,
                [c for c in [na2_col, na6_col, emb_col] if c]
            ).copy()
            soil_plot = soil_plot.dropna(subset=[site_col])

            sites = soil_plot[site_col].astype(str).tolist()
            n = min(len(soil_plot), 3)
            x_labels = sites[:n]

            na2_vals = pd.to_numeric(soil_plot[na2_col], errors="coerce").fillna(0).values[:n]
            na6_vals = pd.to_numeric(soil_plot[na6_col], errors="coerce").fillna(0).values[:n]
            emb_vals = pd.to_numeric(soil_plot[emb_col], errors="coerce").fillna(0).values[:n]

            fig_soil = go.Figure()
            fig_soil.add_trace(go.Bar(
                x=x_labels, y=na2_vals,
                name="NA (10⁻²) — Growth",
                marker_color="#D85A30", marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>NA (10⁻²): %{y:.1f} (×3000)<extra></extra>",
            ))
            fig_soil.add_trace(go.Bar(
                x=x_labels, y=na6_vals,
                name="NA (10⁻⁶) — Colony Count",
                marker_color="#7BB3D4", marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>NA (10⁻⁶): %{y:.1f} (×300)<extra></extra>",
            ))
            fig_soil.add_trace(go.Bar(
                x=x_labels, y=emb_vals,
                name="EMB — E. coli Indicator",
                marker_color="#A8D5B5", marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>EMB: %{y:.1f} (×30)<extra></extra>",
            ))

            fig_soil.update_layout(**PL(
                "Soil Microbial Load by Site",
                barmode="group",
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
            ))
            fig_soil.update_yaxes(
                range=[0, 120],
                tickvals=[0, 20, 40, 60, 80, 100, 120],
                title_text="Scaled Count (arbitrary units)",
                showgrid=True,
                gridcolor="rgba(0,0,0,0.08)",
            )
            fig_soil.update_xaxes(title_text="Sampling Site")
            fig_soil.update_layout(
                legend=dict(
                    orientation="h", yanchor="top", y=-0.18,
                    xanchor="center", x=0.5,
                    font=dict(size=10),
                    bgcolor="rgba(0,0,0,0)",
                )
            )

    fig_gr = go.Figure()
    gram_pos_pct = max(0.0, 100.0 - gram_neg_pct)
    fig_gr.add_trace(go.Pie(
        labels=["Gram Negative", "Gram Positive"],
        values=[gram_neg_pct, gram_pos_pct],
        hole=0.58,
        marker_colors=[C_RED, BORDER],
        textfont_color=TEXT,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{percent}<br>Count: %{value:.1f}%<extra></extra>",
    ))
    fig_gr.update_layout(**PLna(f"Gram Staining — {total_isolates} Isolates ({gram_neg_count} Gram–ve)"))

    fig_aqi = go.Figure(go.Indicator(
        mode="gauge+number", value=float(aqi_val),
        title={"text": "Air Quality Index (AQI) — Live Bangalore", "font": {"color": C_AMBER, "size": 13}},
        number={"font": {"color": C_AMBER, "size": 40}},
        gauge=dict(
            axis=dict(range=[0, 200], tickcolor=MUTED, tickfont_color=MUTED),
            bar=dict(color=C_AMBER, thickness=0.25),
            bgcolor="#ffffff", bordercolor=BORDER,
            steps=[
                dict(range=[0,   50],  color="#d1fae5"),
                dict(range=[50, 100],  color="#ecfccb"),
                dict(range=[100, 150], color="#fef3c7"),
                dict(range=[150, 200], color="#fee2e2"),
            ],
            threshold=dict(line=dict(color=C_RED, width=2.5), value=150),
        ),
    ))
    fig_aqi.update_layout(**PLgauge(), height=250, margin=dict(l=24, r=24, t=44, b=16))

    wq_id_col     = find_col(wq, ["sample_id", "sampleId", "id", "sample_no", "Sample no.", "Sample no"])
    wq_label_col  = find_col(wq, ["source_name", "sourceName", "source", "location", "label", "Label"])
    wq_ph_col     = find_col(wq, ["pH", "ph"])
    wq_ec_col     = find_col(wq, ["EC_mS", "EC_uS", "EC", "ec"])
    wq_tds_col2   = find_col(wq, ["TDS_ppm", "TDS", "tds"])
    wq_do_col2    = find_col(wq, ["DO_mg_L", "DO", "do"])
    wq_ntu_col    = find_col(wq, ["turbidity_NTU", "turbidity", "NTU", "ntu"])
    wq_drink_col  = find_col(wq, ["drinking_status", "drinkingStatus", "status", "Status"])

    status_badge_map = {
        "unfit":       "bad",
        "treat first": "warn",
        "borderline":  "warn",
        "agriculture": "info",
        "safe":        "good",
        "potable":     "good",
    }

    wq_table_rows_dynamic = []
    if wq_label_col and not wq.empty:
        for i, (_, row) in enumerate(wq.iterrows()):
            s_id    = str(row.get(wq_id_col,    f"S{i+1}")).strip() if wq_id_col else f"S{i+1}"
            label   = str(row.get(wq_label_col, "")).strip()
            ph_v    = str(round(pd.to_numeric(row.get(wq_ph_col,   "—"), errors="coerce"), 2)) if wq_ph_col else "—"
            ec_v    = str(round(pd.to_numeric(row.get(wq_ec_col,   "—"), errors="coerce"))) if wq_ec_col else "—"
            tds_v   = str(round(pd.to_numeric(row.get(wq_tds_col2, "—"), errors="coerce"))) if wq_tds_col2 else "—"
            do_v    = str(round(pd.to_numeric(row.get(wq_do_col2,  "—"), errors="coerce"), 2)) if wq_do_col2 else "—"
            ntu_v   = str(round(pd.to_numeric(row.get(wq_ntu_col,  "—"), errors="coerce"), 2)) if wq_ntu_col else "—"
            status  = str(row.get(wq_drink_col, "—")).strip() if wq_drink_col else "—"
            bkind   = status_badge_map.get(status.lower(), "info")
            ph_v  = ph_v  if ph_v  != "nan" else "—"
            ec_v  = ec_v  if ec_v  != "nan" else "—"
            tds_v = tds_v if tds_v != "nan" else "—"
            do_v  = do_v  if do_v  != "nan" else "—"
            ntu_v = ntu_v if ntu_v != "nan" else "—"
            wq_table_rows_dynamic.append([
                (s_id,  0.5),
                (label, 2),
                (ph_v,  0.6),
                (ec_v,  0.8),
                (tds_v, 0.8),
                (do_v,  0.6),
                (ntu_v, 0.8),
                (badge(status, bkind), 1),
            ])

    wq_table_rows_fallback = [
        [("S1",  0.5), ("Effluent Household",    2), ("7.52", 0.6), ("1990", 0.8), ("1420", 0.8), ("1.8",  0.6), ("10.46", 0.8), (badge("Unfit",       "bad"),  1)],
        [("S2",  0.5), ("Borewell (Closed Tank)",2), ("7.42", 0.6), ("1549", 0.8), ("1120", 0.8), ("6.55", 0.6), ("7.12",  0.8), (badge("Treat First",  "warn"), 1)],
        [("S3",  0.5), ("Borewell (Open Tank)",  2), ("7.33", 0.6), ("1619", 0.8), ("1150", 0.8), ("6.17", 0.6), ("0.43",  0.8), (badge("Treat First",  "warn"), 1)],
        [("S4",  0.5), ("Effluent (Common Drain)",2),("7.35", 0.6), ("1193", 0.8), ("912",  0.8), ("7.89", 0.6), ("3.56",  0.8), (badge("Unfit",        "bad"),  1)],
        [("S5",  0.5), ("Right Lake",             2), ("7.73", 0.6), ("443",  0.8), ("312",  0.8), ("9.48", 0.6), ("2.99",  0.8), (badge("Borderline",   "warn"), 1)],
        [("S6",  0.5), ("Bund Water",             2), ("7.55", 0.6), ("624",  0.8), ("305",  0.8), ("8.62", 0.6), ("0.30",  0.8), (badge("Agriculture",  "info"), 1)],
        [("S7",  0.5), ("Left Lake",              2), ("8.41", 0.6), ("720",  0.8), ("288",  0.8), ("9.26", 0.6), ("2.08",  0.8), (badge("Borderline",   "warn"), 1)],
        [("S8",  0.5), ("Central Lake",           2), ("7.72", 0.6), ("846",  0.8), ("297",  0.8), ("9.13", 0.6), ("1.42",  0.8), (badge("Borderline",   "warn"), 1)],
        [("S9",  0.5), ("Poultry Farm BW",        2), ("6.61", 0.6), ("538",  0.8), ("378",  0.8), ("7.03", 0.6), ("0.32",  0.8), (badge("Treat First",  "warn"), 1)],
        [("S10", 0.5), ("Piggery Water",          2), ("6.25", 0.6), ("112",  0.8), ("204",  0.8), ("8.91", 0.6), ("BDL",   0.8), (badge("Agriculture",  "info"), 1)],
    ]
    wq_table_rows = wq_table_rows_dynamic if wq_table_rows_dynamic else wq_table_rows_fallback

    mc_table_rows = []
    if not mc.empty:
        for _, row in mc.iterrows():
            status = row.get("microbial_status", "")
            mc_table_rows.append([
                (str(row.get("location", "")),        2),
                (str(row.get("na_plate_count", "")),  1),
                (str(row.get("emb_indicator", "")),   1.5),
                (badge(status, "bad" if status == "High" else "warn"), 1),
            ])

    _calib_charts_init, _calib_metrics_init = _build_calib_content("overlay")

    return html.Div([
        section_banner("Environment Pillar", "WATER · MICROBIOLOGY · GRAM STAINING · SOIL · AIR QUALITY · CALIBRATION"),

        grid4([
            kpi_card("AQI Level",              fmt_num(aqi_val), "",    "Live — Bangalore air quality",       "amber"),
            kpi_card("Humidity",               humidity_val,     "%",   "Live — Bangalore weather",           "blue"),
            kpi_card("Effluent TDS (Sample 1)", effluent_tds,    "ppm", "S1 Effluent Household — WHO lim 500","red"),
            kpi_card("Gram –ve Isolates",      f"{gram_neg_count}/{total_isolates}", "",
                     f"{gram_neg_pct:.1f}% Gram-negative of {total_isolates} isolates", "purple"),
        ]),

        grid2([
            chart_card(dcc.Graph(figure=fig_wq,       config={"displayModeBar": False}), "blue"),
            chart_card(dcc.Graph(figure=fig_physchem, config={"displayModeBar": False}), "purple"),
        ]),

        html.Div([
            card_top_bar(C_BLUE),
            html.Div(style={"height": "6px"}),
            card_title("Water Quality Summary Table — Full Panel"),
            data_table_wrap(
                [("Sample", 0.5), ("Source", 2), ("pH", 0.6), ("EC µS", 0.8), ("TDS ppm", 0.8), ("DO mg/L", 0.6), ("NTU", 0.8), ("Drinking?", 1)],
                wq_table_rows,
            ),
            html.P("WHO drinking water TDS limit: 500 ppm | Turbidity limit: <1 NTU | DO >6 mg/L recommended",
                   style={"fontSize": "11px", "color": MUTED, "marginTop": "6px"}),
        ], style={**CARD_STYLE, "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_vc,   config={"displayModeBar": False}), "blue"),
            chart_card(dcc.Graph(figure=fig_lc,   config={"displayModeBar": False}), "red"),
        ]),

        grid2([
            chart_card(dcc.Graph(figure=fig_soil, config={"displayModeBar": False}), "amber"),
            chart_card(dcc.Graph(figure=fig_aqi,  config={"displayModeBar": False}), "amber"),
        ]),

        html.Div([
            chart_card(dcc.Graph(figure=fig_gr, config={"displayModeBar": False}), "red", span=1),
        ], style={"marginBottom": "24px"}),

        html.Div([
            card_top_bar(C_BLUE),
            html.Div(style={"height": "6px"}),
            card_title("Antibiotic Calibration Dashboard — Doxycycline & Amoxicillin"),
            dcc.RadioItems(
                id="calib-toggle",
                options=[
                    {"label": "  Overlay (both drugs)",  "value": "overlay"},
                    {"label": "  Doxycycline only",      "value": "doxy"},
                    {"label": "  Amoxicillin only",      "value": "amox"},
                ],
                value="overlay",
                inline=True,
                inputStyle={"marginRight": "5px"},
                labelStyle={
                    "marginRight": "24px", "cursor": "pointer",
                    "fontSize": "12px", "fontFamily": "'DM Mono',monospace",
                    "color": MUTED,
                },
                style={"marginBottom": "14px"},
            ),
            html.Div(id="calib-metrics", children=_calib_metrics_init),
            html.Div(id="calib-charts",  children=_calib_charts_init),
        ], style={**CARD_STYLE, "marginBottom": "20px"}),

        grid2([
            html.Div([
                card_top_bar(C_RED),
                html.Div(style={"height": "6px"}),
                card_title("Microbial Analysis — Water Samples (Lake Entries)"),
                data_table_wrap(
                    [("Location", 2), ("NA Plate", 1), ("EMB Indicator", 1.5), ("Status", 1)],
                    mc_table_rows if mc_table_rows else [
                        [("Lake BH Entry 1", 2), ("Moderate (257 col)", 1), ("Enterobacter aerogenes", 1.5), (badge("Moderate", "warn"), 1)],
                        [("Lake BH Entry 2", 2), ("TNTC",              1), ("Enterobacter aerogenes", 1.5), (badge("High",     "bad"),  1)],
                        [("Lake BH Entry 3", 2), ("TNTC",              1), ("Enterobacter aerogenes", 1.5), (badge("High",     "bad"),  1)],
                        [("Lake BH 2",       2), ("High (380 col)",    1), ("Enterobacter aerogenes", 1.5), (badge("Moderate", "warn"), 1)],
                        [("Lake EF 1",       2), ("TNTC",              1), ("High coliform load",     1.5), (badge("High",     "bad"),  1)],
                        [("Lake BH 3",       2), ("TNTC / 200",        1), ("Mixed enteric flora",    1.5), (badge("High",     "bad"),  1)],
                    ]
                ),
                html.P("Media: NA, EMB, XLD | Incubation: 37°C, 24 hrs | Date: 22/01/2026",
                       style={"fontSize": "11px", "color": MUTED}),
            ], style=CARD_STYLE),

            html.Div([
                card_top_bar(C_GREEN),
                html.Div(style={"height": "6px"}),
                card_title(f"Gram Staining Summary — {total_isolates} Isolates"),
                progress_bar(
                    "Gram Negative (all isolates)",
                    f"{gram_neg_count}/{total_isolates} = {gram_neg_pct:.1f}%",
                    gram_neg_pct, "red"
                ),
                progress_bar(
                    "Bacillus morphology",
                    f"~{bacillus_pct:.1f}% of isolates",
                    bacillus_pct, "blue"
                ),
                progress_bar(
                    "Cocci morphology",
                    f"~{cocci_pct:.1f}% of isolates",
                    cocci_pct, "green"
                ),
                progress_bar(
                    "Mucoid layer presence",
                    f"~{mucoid_pct:.1f}% of isolates",
                    mucoid_pct, "purple"
                ),
                html.Div([
                    html.P([
                        f"{gram_neg_count} of {total_isolates} tested isolates were ",
                        html.Strong("Gram-negative", style={"color": C_RED}),
                        f" ({gram_neg_pct:.1f}%). Dominant types: rod-shaped (Bacillus ~{bacillus_pct:.0f}%) and "
                        f"spherical (Cocci ~{cocci_pct:.0f}%). "
                        f"Mucoid layers in ~{mucoid_pct:.0f}% suggest capsule-forming, potentially pathogenic organisms.",
                    ], style={"fontSize": "12px", "color": MUTED, "lineHeight": "1.6", "margin": "0"}),
                ], style={"padding": "12px", "background": rgba(C_RED, 0.05), "borderRadius": "8px",
                          "borderLeft": f"3px solid {C_RED}"}),
            ], style=CARD_STYLE),
        ]),

        html.Div([
            card_top_bar(C_BLUE),
            html.Div(style={"height": "6px"}),
            card_title("Water Sample Field Notes"),
            data_table_wrap(
                [("ID", 0.5), ("Sample Label", 2), ("Field Observation", 4)],
                [
                    [(f"S{int(row['Sample no.'])}" if pd.notna(row.get("Sample no.")) else "", 0.5),
                     (str(row.get("Label", "")).strip(), 2),
                     (str(row.get("Label Description", ""))[:120] + ("…" if len(str(row.get("Label Description", ""))) > 120 else ""), 4)]
                    for _, row in pv.iterrows() if pd.notna(row.get("Label Description", ""))
                ]
            ),
        ], style={**CARD_STYLE, "marginBottom": "20px"}) if not pv.empty else html.Div(),
    ])


def page_interconnections(d):
    try:
        zoo  = d.get("zoonoticTransmission", pd.DataFrame())
        rd   = d.get("rainfallDisease",      pd.DataFrame())
        ints = d.get("interactionStrength",  pd.DataFrame())
        rm   = d.get("riskMatrix",           pd.DataFrame())
        cp   = d.get("crossPillarIndex",     pd.DataFrame())
        proj = d.get("projectedOutcome",     pd.DataFrame())
    except Exception:
        zoo = rd = ints = rm = cp = proj = pd.DataFrame()

    # ── CHART 1: Risk Matrix — Bubble chart ──────────────────────────────────
    fig_bub = empty_fig("No risk matrix data available")
    try:
        rm_factor_col     = find_col(rm, ["factor"])
        rm_likelihood_col = find_col(rm, ["likelihood"])
        rm_impact_col     = find_col(rm, ["impact"])
        rm_urgency_col    = find_col(rm, ["urgency"])

        if rm_factor_col and rm_likelihood_col and rm_impact_col and rm_urgency_col and not rm.empty:
            rm_plot = coerce_numeric(rm, [rm_likelihood_col, rm_impact_col, rm_urgency_col]).copy()
            rm_plot = rm_plot.dropna(subset=[rm_factor_col, rm_likelihood_col, rm_impact_col, rm_urgency_col])

            if not rm_plot.empty:
                u_min = rm_plot[rm_urgency_col].min()
                u_max = rm_plot[rm_urgency_col].max()
                COLOR_MAP = {
                    "water contamination":   "rgba(255,112,67,0.65)",
                    "e.coli in lakes":       "rgba(255,112,67,0.50)",
                    "ecoli in lakes":        "rgba(255,112,67,0.50)",
                    "vector-borne diseases": "rgba(79,195,247,0.55)",
                    "vectorborne diseases":  "rgba(79,195,247,0.55)",
                    "rabies":                "rgba(255,202,40,0.60)",
                    "rabies/stray dogs":     "rgba(255,202,40,0.60)",
                    "soil microbial load":   "rgba(171,71,188,0.50)",
                    "air quality (aqi 135)": "rgba(255,202,40,0.45)",
                    "air quality":           "rgba(255,202,40,0.45)",
                    "amr from livestock":    "rgba(105,240,174,0.55)",
                    "ncd burden":            "rgba(79,195,247,0.40)",
                }
                BORDER_MAP = {
                    "water contamination":   C_RED,
                    "e.coli in lakes":       C_RED,
                    "ecoli in lakes":        C_RED,
                    "vector-borne diseases": C_BLUE,
                    "vectorborne diseases":  C_BLUE,
                    "rabies":                C_AMBER,
                    "rabies/stray dogs":     C_AMBER,
                    "soil microbial load":   C_PURPLE,
                    "air quality (aqi 135)": C_AMBER,
                    "air quality":           C_AMBER,
                    "amr from livestock":    C_GREEN,
                    "ncd burden":            C_BLUE,
                }
                fig_bub = go.Figure()
                for _, row in rm_plot.iterrows():
                    fname     = str(row[rm_factor_col]).strip()
                    fkey      = fname.lower()
                    lval      = float(row[rm_likelihood_col])
                    ival      = float(row[rm_impact_col])
                    uval      = float(row[rm_urgency_col])
                    r         = 11 + (uval - u_min) / (u_max - u_min) * 11 if u_max > u_min else 16
                    bg_color  = COLOR_MAP.get(fkey, "rgba(79,195,247,0.45)")
                    brd_color = BORDER_MAP.get(fkey, C_BLUE)
                    fig_bub.add_trace(go.Scatter(
                        x=[lval], y=[ival],
                        mode="markers",
                        name=fname,
                        marker=dict(
                            size=r * 2,
                            color=bg_color,
                            line=dict(color=brd_color, width=1.5),
                            sizemode="diameter",
                        ),
                        hovertemplate=f"<b>{fname}</b><br>Likelihood: {lval}<br>Impact: {ival}<br>Urgency: {uval}<extra></extra>",
                    ))
                fig_bub.update_layout(**PL(
                    "Risk Matrix — Likelihood vs Impact",
                    xaxis=dict(title="Likelihood →", range=[0, 110],
                               gridcolor="rgba(0,0,0,0.07)", tickfont_color=MUTED,
                               showticklabels=False, title_font_color=MUTED,
                               zerolinecolor=BORDER, linecolor=BORDER),
                    yaxis=dict(title="Impact →", range=[0, 110],
                               gridcolor="rgba(0,0,0,0.07)", tickfont_color=MUTED,
                               showticklabels=False, title_font_color=MUTED,
                               zerolinecolor=BORDER, linecolor=BORDER),
                    showlegend=True,
                    legend=dict(bgcolor="rgba(0,0,0,0)", font_size=9,
                                orientation="h", x=0, y=-0.18),
                    margin=dict(l=20, r=20, t=44, b=60),
                ))
    except Exception as e:
        print(f"[interconnect] risk matrix error: {e}")

    # ── CHART 2: Rainfall vs Vector Disease ──────────────────────────────────
    fig_rain = empty_fig("No rainfall-disease data available")
    try:
        rd_year_col    = find_col(rd, ["year"])
        rd_rain_col    = find_col(rd, ["rainfallIndex", "rainfall_index", "rainfall"])
        rd_dengue_col  = find_col(rd, ["dengueCases",   "dengue"])
        rd_malaria_col = find_col(rd, ["malariaCases",  "malaria"])
        rd_lepto_col   = find_col(rd, ["leptospirosis", "lepto"])

        if rd_year_col and rd_rain_col and not rd.empty:
            rd_plot = coerce_numeric(rd, [c for c in [rd_year_col, rd_rain_col, rd_dengue_col, rd_malaria_col, rd_lepto_col] if c]).copy()
            rd_plot = rd_plot.dropna(subset=[rd_year_col, rd_rain_col])
            if not rd_plot.empty:
                fig_rain = go.Figure()
                fig_rain.add_trace(go.Scatter(
                    x=rd_plot[rd_year_col].astype(str),
                    y=rd_plot[rd_rain_col],
                    name="Rainfall Index",
                    mode="lines+markers",
                    line=dict(color="rgba(79,195,247,0.9)", width=2.5, shape="spline"),
                    marker=dict(size=5, color=C_BLUE),
                    fill="tozeroy", fillcolor="rgba(79,195,247,0.08)",
                    yaxis="y",
                    hovertemplate="<b>Rainfall</b><br>Year: %{x}<br>Index: %{y}<extra></extra>",
                ))
                disease_series = []
                if rd_dengue_col:
                    disease_series.append((rd_dengue_col, C_RED,    "Dengue Cases",  False))
                if rd_malaria_col:
                    disease_series.append((rd_malaria_col, C_PURPLE, "Malaria Cases", True))
                if rd_lepto_col:
                    disease_series.append((rd_lepto_col,  C_GREEN,  "Leptospirosis", True))
                for col, color, name, use_dash in disease_series:
                    valid = rd_plot[[rd_year_col, col]].dropna()
                    if valid.empty:
                        continue
                    line_cfg = dict(color=color, width=2, shape="spline")
                    if use_dash:
                        line_cfg["dash"] = "dash"
                    fig_rain.add_trace(go.Scatter(
                        x=valid[rd_year_col].astype(str),
                        y=valid[col],
                        name=name,
                        mode="lines+markers",
                        line=line_cfg,
                        marker=dict(size=5, color=color),
                        fill="tozeroy" if name == "Dengue Cases" else "none",
                        fillcolor="rgba(255,112,67,0.07)" if name == "Dengue Cases" else "rgba(0,0,0,0)",
                        yaxis="y2",
                        hovertemplate=f"<b>{name}</b><br>Year: %{{x}}<br>Cases: %{{y}}<extra></extra>",
                    ))
                fig_rain.update_layout(
                    title=dict(text="Rainfall vs Vector-Borne Disease Burden",
                               font=dict(size=13, color=TEXT)),
                    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                    font=dict(family="'Sora','Segoe UI',sans-serif", color=TEXT, size=11),
                    margin=dict(l=20, r=50, t=44, b=20),
                    hovermode="x unified",
                    legend=dict(bgcolor="rgba(0,0,0,0)", font_size=9,
                                orientation="h", x=0, y=-0.18),
                    xaxis=dict(gridcolor="rgba(0,0,0,0.07)", linecolor=BORDER,
                               tickfont_color=MUTED, title_font_color=MUTED),
                    yaxis=dict(title="Rainfall Index",
                               title_font=dict(color=C_BLUE),
                               tickfont=dict(color=C_BLUE),
                               gridcolor="rgba(0,0,0,0.07)", linecolor=BORDER),
                    yaxis2=dict(title="Disease Cases",
                                title_font=dict(color=C_RED),
                                tickfont=dict(color=C_RED),
                                overlaying="y", side="right",
                                gridcolor="rgba(0,0,0,0)", showgrid=False,
                                linecolor=BORDER),
                )
    except Exception as e:
        print(f"[interconnect] rainfall chart error: {e}")

    # ── CHART 3: Zoonotic Transmission — stacked horizontal bar ──────────────
    fig_zoo = empty_fig("No zoonotic transmission data available")
    try:
        zoo_path_col = find_col(zoo, ["pathway"])
        zoo_dc_col   = find_col(zoo, ["directContact",  "direct_contact",  "direct"])
        zoo_env_col  = find_col(zoo, ["environmental",  "environment"])
        zoo_fw_col   = find_col(zoo, ["foodWater",      "food_water",      "food"])
        zoo_vec_col  = find_col(zoo, ["vectorMediated", "vector_mediated", "vector"])

        if zoo_path_col and not zoo.empty:
            zoo_plot = coerce_numeric(zoo, [c for c in [zoo_dc_col, zoo_env_col, zoo_fw_col, zoo_vec_col] if c]).copy()
            zoo_plot = zoo_plot.dropna(subset=[zoo_path_col])
            if not zoo_plot.empty:
                fig_zoo = go.Figure()
                series = [
                    (zoo_dc_col,  "rgba(255,112,67,0.70)",  "Direct Contact"),
                    (zoo_env_col, "rgba(255,202,40,0.65)",  "Environmental Route"),
                    (zoo_fw_col,  "rgba(171,71,188,0.55)",  "Food / Water Chain"),
                    (zoo_vec_col, "rgba(79,195,247,0.55)",  "Vector Mediated"),
                ]
                for col, color, name in series:
                    if not col:
                        continue
                    valid = zoo_plot[[zoo_path_col, col]].dropna()
                    if valid.empty:
                        continue
                    fig_zoo.add_trace(go.Bar(
                        y=valid[zoo_path_col].astype(str),
                        x=valid[col],
                        name=name,
                        orientation="h",
                        marker_color=color,
                        marker_line_width=0,
                        hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x}}%<extra></extra>",
                    ))
                fig_zoo.update_layout(**PL(
                    "Zoonotic & AMR Transmission Pressure (Animal \u2192 Human)",
                    barmode="stack",
                    xaxis=dict(title="Transmission Pressure (relative %)",
                               range=[0, 100], gridcolor="rgba(0,0,0,0.07)",
                               tickfont_color=MUTED, title_font_color=MUTED,
                               linecolor=BORDER, zerolinecolor=BORDER),
                    yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont_color=MUTED,
                               title_font_color=MUTED, linecolor=BORDER, zerolinecolor=BORDER),
                    legend=dict(bgcolor="rgba(0,0,0,0)", font_size=9,
                                orientation="h", x=0, y=-0.18),
                    margin=dict(l=20, r=20, t=44, b=80),
                ))
    except Exception as e:
        print(f"[interconnect] zoonotic chart error: {e}")

    # ── CHART 4: Cross-Pillar Contamination — Polar Area ─────────────────────
    # FIX: The sheet loads in WIDE format — factor names become column headers,
    # values sit in row 0.  find_col() correctly returns None because no column
    # is literally called "factor" or "value".  We detect this and melt.
    fig_polar = empty_fig("No cross-pillar contamination data available")
    try:
        if not cp.empty:
            cp_factor_col = find_col(cp, ["factor", "Factor", "name", "label", "pathway", "Pathway"])
            cp_value_col  = find_col(cp, ["value",  "Value",  "score", "Score", "index",   "Index", "risk", "Risk"])

            print(f"[DEBUG crossPillar] columns={list(cp.columns)}  factor={cp_factor_col}  value={cp_value_col}")
            print(cp.head())

            # ── WIDE-FORMAT DETECTION & MELT ─────────────────────────────────
            # When pandas reads the sheet it turns  factor | value  header into
            # column names, so every factor label (Water TDS, Soil E.coli …)
            # becomes a column header and row 0 contains the numeric values.
            # find_col returns None because none of those column names contain
            # the word "factor" or "value".  We detect this situation and melt.
            if (cp_factor_col is None or cp_value_col is None) and not cp.empty:
                print("[DEBUG crossPillar] wide-format detected — melting to long format")
                try:
                    row0 = cp.iloc[0]
                    numeric_cols = [
                        c for c in cp.columns
                        if pd.to_numeric(row0[c], errors="coerce") is not None
                        and str(row0[c]).strip() not in ("", "nan")
                        and pd.notna(pd.to_numeric(row0[c], errors="coerce"))
                    ]
                    if numeric_cols:
                        cp_melted = pd.DataFrame({
                            "factor": numeric_cols,
                            "value":  [pd.to_numeric(row0[c], errors="coerce") for c in numeric_cols],
                        })
                        cp_melted = cp_melted.dropna(subset=["value"])
                        if not cp_melted.empty:
                            cp            = cp_melted
                            cp_factor_col = "factor"
                            cp_value_col  = "value"
                            print(f"[DEBUG crossPillar] melted OK — {len(cp_melted)} rows")
                            print(cp_melted)
                except Exception as melt_err:
                    print(f"[DEBUG crossPillar] melt failed: {melt_err}")

            # ── BUILD POLAR CHART ─────────────────────────────────────────────
            if cp_factor_col and cp_value_col and not cp.empty:
                cp_plot = cp[[cp_factor_col, cp_value_col]].copy()
                cp_plot[cp_value_col] = pd.to_numeric(cp_plot[cp_value_col], errors="coerce")
                cp_plot = cp_plot.dropna(subset=[cp_factor_col, cp_value_col])
                cp_plot = cp_plot[cp_plot[cp_factor_col].astype(str).str.strip() != ""]

                if not cp_plot.empty:
                    labels = cp_plot[cp_factor_col].astype(str).tolist()
                    values = cp_plot[cp_value_col].tolist()

                    bg_colors, brd_colors = [], []
                    for v in values:
                        if v >= 70:
                            bg_colors.append("rgba(255,112,67,0.55)")
                            brd_colors.append(C_RED)
                        elif v >= 50:
                            bg_colors.append("rgba(255,202,40,0.55)")
                            brd_colors.append(C_AMBER)
                        elif v >= 30:
                            bg_colors.append("rgba(105,240,174,0.55)")
                            brd_colors.append(C_GREEN)
                        else:
                            bg_colors.append("rgba(79,195,247,0.45)")
                            brd_colors.append(C_BLUE)

                    fig_polar = go.Figure()
                    fig_polar.add_trace(go.Barpolar(
                        r=values,
                        theta=labels,
                        marker_color=bg_colors,
                        marker_line_color=brd_colors,
                        marker_line_width=1.5,
                        hovertemplate="<b>%{theta}</b><br>Risk Index: %{r}/100<extra></extra>",
                    ))
                    fig_polar.update_layout(
                        paper_bgcolor="#ffffff",
                        font=dict(family="'Sora','Segoe UI',sans-serif", color=TEXT, size=9),
                        margin=dict(l=10, r=10, t=10, b=10),
                        polar=dict(
                            bgcolor="#ffffff",
                            radialaxis=dict(
                                range=[0, 100],
                                tickfont=dict(size=8, color=MUTED),
                                gridcolor="rgba(0,0,0,0.08)",
                                showticklabels=False,
                            ),
                            angularaxis=dict(
                                tickfont=dict(size=8, color=TEXT),
                                gridcolor="rgba(0,0,0,0.08)",
                            ),
                        ),
                        showlegend=False,
                    )
                else:
                    print("[DEBUG crossPillar] cp_plot empty after dropna")
            else:
                print("[DEBUG crossPillar] could not resolve factor/value columns after melt attempt")
    except Exception as e:
        print(f"[interconnect] polar chart error: {e}")
        import traceback; traceback.print_exc()

    # ── CHART 5: Pillar Interaction Strength ─────────────────────────────────
    fig_int = empty_fig("No interaction strength data available")
    try:
        ints_label_col   = find_col(ints, ["interaction"])
        ints_current_col = find_col(ints, ["current"])
        ints_after_col   = find_col(ints, ["afterIntervention", "after_intervention", "after"])

        if ints_label_col and ints_current_col and ints_after_col and not ints.empty:
            ints_plot = coerce_numeric(ints, [ints_current_col, ints_after_col]).copy()
            ints_plot = ints_plot.dropna(subset=[ints_label_col, ints_current_col, ints_after_col])
            if not ints_plot.empty:
                labels  = ints_plot[ints_label_col].astype(str).tolist()
                current = ints_plot[ints_current_col].tolist()
                after   = ints_plot[ints_after_col].tolist()
                CURRENT_COLORS = [
                    "rgba(79,195,247,0.65)",
                    "rgba(105,240,174,0.65)",
                    "rgba(255,112,67,0.65)",
                    "rgba(255,202,40,0.60)",
                    "rgba(171,71,188,0.65)",
                    "rgba(255,202,40,0.50)",
                ]
                fig_int = go.Figure()
                fig_int.add_trace(go.Bar(
                    x=labels, y=current,
                    name="Current Pressure",
                    marker_color=[CURRENT_COLORS[i % len(CURRENT_COLORS)] for i in range(len(labels))],
                    marker_line_width=0,
                    hovertemplate="<b>%{x}</b><br>Current: %{y}<extra></extra>",
                ))
                fig_int.add_trace(go.Bar(
                    x=labels, y=after,
                    name="After Intervention",
                    marker_color="rgba(105,240,174,0.25)",
                    marker_line_color=C_GREEN, marker_line_width=1.5,
                    hovertemplate="<b>%{x}</b><br>After Intervention: %{y}<extra></extra>",
                ))
                fig_int.update_layout(**PL(
                    "One Health Pillar Interaction Strength",
                    barmode="group",
                    yaxis=dict(title="Interaction Strength (0\u2013100)", range=[0, 100],
                               gridcolor="rgba(0,0,0,0.07)", tickfont_color=MUTED,
                               title_font_color=MUTED, linecolor=BORDER, zerolinecolor=BORDER),
                    xaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=9, color=TEXT),
                               tickangle=-10, title_font_color=MUTED,
                               linecolor=BORDER, zerolinecolor=BORDER),
                    legend=dict(bgcolor="rgba(0,0,0,0)", font_size=9,
                                orientation="h", x=0, y=-0.18),
                    margin=dict(l=20, r=20, t=44, b=60),
                ))
    except Exception as e:
        print(f"[interconnect] interaction chart error: {e}")

    # ── CHART 6: Projected Outcome ────────────────────────────────────────────
    fig_proj = empty_fig("No projected outcome data available")
    try:
        proj_year_col = find_col(proj, ["year"])
        proj_no_col   = find_col(proj, ["noIntervention", "no_intervention", "baseline"])
        proj_part_col = find_col(proj, ["partial"])
        proj_full_col = find_col(proj, ["fullOneHealth", "full_one_health", "full"])

        if proj_year_col and proj_no_col and not proj.empty:
            proj_plot = coerce_numeric(proj, [c for c in [proj_year_col, proj_no_col, proj_part_col, proj_full_col] if c]).copy()
            proj_plot = proj_plot.dropna(subset=[proj_year_col, proj_no_col])
            if not proj_plot.empty:
                fig_proj = go.Figure()
                series_cfg = []
                if proj_no_col:
                    series_cfg.append((proj_no_col,   "rgba(255,112,67,0.9)",  "rgba(255,112,67,0.08)",
                                       2.5, False, 4, C_RED,   "No Intervention (Composite Risk)"))
                if proj_part_col:
                    series_cfg.append((proj_part_col, "rgba(255,202,40,0.9)",  "rgba(255,202,40,0.06)",
                                       2.0, True,  4, C_AMBER, "Partial Intervention"))
                if proj_full_col:
                    series_cfg.append((proj_full_col, "rgba(105,240,174,0.9)", "rgba(105,240,174,0.08)",
                                       2.5, False, 5, C_GREEN, "Full One Health Protocol"))
                for col, border_c, fill_c, width, use_dash, pt_size, pt_color, name in series_cfg:
                    valid = proj_plot[[proj_year_col, col]].dropna()
                    if valid.empty:
                        continue
                    line_cfg = dict(color=border_c, width=width, shape="spline", smoothing=0.8)
                    if use_dash:
                        line_cfg["dash"] = "dash"
                    fig_proj.add_trace(go.Scatter(
                        x=valid[proj_year_col].astype(str),
                        y=valid[col],
                        name=name,
                        mode="lines+markers",
                        line=line_cfg,
                        marker=dict(size=pt_size, color=pt_color),
                        fill="tozeroy", fillcolor=fill_c,
                        hovertemplate=f"<b>{name}</b><br>Year: %{{x}}<br>Risk Score: %{{y}}<extra></extra>",
                    ))
                fig_proj.update_layout(**PL(
                    "Projected Health Outcome \u2014 With vs Without Intervention",
                    hovermode="x unified",
                    yaxis=dict(title="Composite Risk Score", range=[0, 110],
                               gridcolor="rgba(0,0,0,0.07)", tickfont_color=MUTED,
                               title_font_color=MUTED, linecolor=BORDER, zerolinecolor=BORDER),
                    xaxis=dict(gridcolor="rgba(0,0,0,0.07)", tickfont_color=MUTED,
                               title_font_color=MUTED, linecolor=BORDER, zerolinecolor=BORDER),
                    legend=dict(bgcolor="rgba(0,0,0,0)", font_size=9,
                                orientation="h", x=0, y=-0.18),
                    margin=dict(l=20, r=20, t=44, b=60),
                ))
    except Exception as e:
        print(f"[interconnect] projection chart error: {e}")

    # ── FORCE-DIRECTED GRAPH ──────────────────────────────────────────────────
    # FIX: html.Script() is silently stripped by Dash/React and never executes.
    # Solution: render the entire interactive graph inside a self-contained
    # srcdoc iframe.  The iframe runs its own JS completely independently of
    # Dash's renderer, so the SVG force simulation works every time.
    _graph_iframe_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#f1f5f9; font-family:'DM Mono',monospace; overflow:hidden; }
  #ic-wrapper { position:relative; width:100%; height:100vh; }
  svg { width:100%; height:100%; }
  #ic-tooltip {
    position:absolute; background:rgba(15,23,42,0.95); color:#e2e8f0;
    border-radius:12px; padding:13px 17px; font-size:12px;
    font-family:'DM Mono',monospace; pointer-events:none; opacity:0;
    max-width:270px; line-height:1.65; z-index:100;
    border:1px solid rgba(79,195,247,0.25);
    box-shadow:0 8px 32px rgba(0,0,0,0.22);
    transition:opacity 0.15s; display:none;
  }
  #legend-row {
    position:absolute; top:10px; left:12px; right:12px;
    display:flex; flex-wrap:wrap; gap:6px; z-index:50;
  }
  .chip {
    padding:4px 10px; border-radius:20px; font-size:10px; font-weight:600;
    cursor:pointer; transition:all 0.18s;
    background:rgba(0,0,0,0.06); display:flex; align-items:center; gap:5px;
  }
</style>
</head>
<body>
<div id="ic-wrapper">
  <div id="legend-row"></div>
  <svg id="ic-svg"></svg>
  <div id="ic-tooltip"></div>
</div>
<script>
(function() {
  var PATHWAYS = [
    { id:'h2e', label:'Human \u2192 Environment', emoji:'\ud83d\udc64\u2192\ud83c\udf3f', color:'#4fc3f7' },
    { id:'a2e', label:'Animal \u2192 Environment', emoji:'\ud83d\udc3e\u2192\ud83c\udf3f', color:'#69f0ae' },
    { id:'e2h', label:'Environment \u2192 Human',  emoji:'\ud83c\udf3f\u2192\ud83d\udc64', color:'#ff7043' },
    { id:'a2h', label:'Animal \u2192 Human',       emoji:'\ud83d\udc3e\u2192\ud83d\udc64', color:'#ab47bc' },
    { id:'h2a', label:'Human \u2192 Animal',       emoji:'\ud83d\udc64\u2192\ud83d\udc3e', color:'#ffca28' },
    { id:'priority', label:'Priority Interventions', emoji:'\ud83c\udfaf', color:'#ef5350' },
  ];
  var NODES = [
    { id:'human',   emoji:'\ud83d\udc64', sub:'HUMAN',       color:'#4fc3f7', r:52,
      info:'<b style="color:#0284c7">Human Pillar</b><br>3,573 residents \u00b7 PHC monitored<br>NCD burden, vector-borne & zoonotic disease risk' },
    { id:'animal',  emoji:'\ud83d\udc3e', sub:'ANIMAL',      color:'#69f0ae', r:52,
      info:'<b style="color:#15803d">Animal Pillar</b><br>73+ strays \u00b7 700\u20131k livestock<br>Rabies 13% post-ABC \u00b7 AMR monitored' },
    { id:'environ', emoji:'\ud83c\udf3f', sub:'ENVIRONMENT', color:'#ff7043', r:52,
      info:'<b style="color:#b91c1c">Environment Pillar</b><br>AQI 135 \u00b7 Humidity 37%<br>8/10 water samples exceed WHO TDS \u00b7 TNTC soil load' },
    { id:'water',  emoji:'\ud83d\udca7', sub:'Water',    color:'#29b6f6', r:26,
      info:'<b style="color:#29b6f6">Water Contamination</b><br>TDS 1420 ppm (household effluent)<br>Enterobacter in all lake entries' },
    { id:'air',    emoji:'\ud83d\udca8', sub:'Air/AQI', color:'#ffca28', r:24,
      info:'<b style="color:#92400e">Air Quality</b><br>AQI 135 \u2014 unhealthy for sensitive groups<br>Humidity 37% amplifies respiratory risk' },
    { id:'vector', emoji:'\ud83e\udda0', sub:'Vectors', color:'#4fc3f7', r:26,
      info:'<b style="color:#0284c7">Vector-Borne Disease</b><br>Malaria 30\u201350/yr \u00b7 Dengue 60 (2022)<br>Chikungunya 10\u201325/yr' },
    { id:'rabies', emoji:'\ud83d\udc15', sub:'Rabies',  color:'#ffca28', r:24,
      info:'<b style="color:#92400e">Rabies / Zoonosis</b><br>13% post-ABC infection rate<br>Leptospirosis 15 cases (2021)' },
    { id:'amr',    emoji:'\ud83d\udc8a', sub:'AMR',     color:'#ab47bc', r:22,
      info:'<b style="color:#6b21a8">AMR Residues</b><br>Doxycycline in pig/hen excreta<br>Below threshold \u00b7 Ongoing monitoring needed' },
    { id:'soil',   emoji:'\ud83c\udf31', sub:'Soil',    color:'#69f0ae', r:22,
      info:'<b style="color:#15803d">Soil Microbes</b><br>Horse stable: TNTC + E. coli indicator<br>Manure applied to agricultural fields' },
    { id:'waste',  emoji:'\ud83d\udeb0', sub:'Effluent',color:'#ff7043', r:22,
      info:'<b style="color:#b91c1c">Effluent & Waste</b><br>TDS 1420, DO 1.8 mg/L in drains<br>Open dumps sustain stray populations' },
  ];
  var EDGES = [
    { s:'human',   t:'waste',   p:'h2e', label:'Sewage discharge',             info:'Household waste (TDS 1420 ppm) enters drains \u2192 lake entries show TNTC counts' },
    { s:'waste',   t:'environ', p:'h2e', label:'Drain \u2192 lake & soil',     info:'Effluent (DO 1.8 mg/L) flows to lakes & groundwater, raising pathogen burden' },
    { s:'human',   t:'vector',  p:'h2e', label:'Borewell tanks \u2192 breeding',info:'Open tanks and poor drainage create Anopheles/Aedes breeding habitats' },
    { s:'animal',  t:'soil',    p:'a2e', label:'Manure \u2192 soil',           info:'Horse stable TNTC, pig/poultry excreta with doxycycline residues in fields' },
    { s:'soil',    t:'water',   p:'a2e', label:'Runoff \u2192 waterbodies',    info:'Microbial-laden stable soil runoff reaches lake entries \u2014 E. coli on EMB confirmed' },
    { s:'animal',  t:'amr',     p:'a2e', label:'Antibiotic residues',          info:'Doxycycline: pig 0.000002 mg/g, hen 0.00348 mg/g \u2014 both below 0.02 mg/g limit' },
    { s:'water',   t:'human',   p:'e2h', label:'Contaminated drinking water',  info:'Villagers use lake water \u2192 E. coli & Enterobacter \u2192 GI illness risk' },
    { s:'air',     t:'human',   p:'e2h', label:'Poor AQI \u2192 respiratory',  info:'AQI 135 + low humidity \u2192 TB, COPD, respiratory infections in children & elderly' },
    { s:'vector',  t:'human',   p:'e2h', label:'Mosquito transmission',        info:'Dengue 60 (2022), malaria 30\u201350/yr, chikungunya 10\u201325/yr from stagnant water zones' },
    { s:'environ', t:'air',     p:'e2h', label:'Quarrying & emissions',        info:'Quarrying depletes groundwater & raises dust \u2014 forcing reliance on surface sources' },
    { s:'rabies',  t:'human',   p:'a2h', label:'Rabies bite risk',             info:'13% rabies infection in neutered-only pop. 73+ strays. Dog bites reported.' },
    { s:'animal',  t:'rabies',  p:'a2h', label:'Stray dog reservoir',          info:'ABC program (17 dogs, Mar 2024) neutered \u2014 vaccination gaps leave 13% infected' },
    { s:'amr',     t:'human',   p:'a2h', label:'AMR food-chain risk',          info:'Sub-threshold residues risk transferring resistance to human gut flora via food chain' },
    { s:'human',   t:'rabies',  p:'h2a', label:'ABC intervention',             info:'ABC program: 17 dogs neutered + anti-rabies shot (Mar 2024).' },
    { s:'human',   t:'amr',     p:'h2a', label:'Antibiotic use patterns',      info:'Farming economics shape doxycycline use in livestock.' },
    { s:'waste',   t:'animal',  p:'h2a', label:'Dumps \u2192 stray feeding',   info:'Open food waste dumps sustain stray dog/cat populations, perpetuating rabies cycle' },
    { s:'human',   t:'environ', p:'priority', label:'Water treatment needed',   info:'Borewell TDS/EC exceed WHO in 8/10 samples \u2192 install treatment systems urgently' },
    { s:'animal',  t:'environ', p:'priority', label:'AMR & soil surveillance',  info:'Continuous HPLC monitoring of excreta & runoff to detect AMR threshold crossing' },
    { s:'environ', t:'human',   p:'priority', label:'AQI & lake monitoring',    info:'Emission controls + regular lake Enterobacter testing' },
  ];

  function init() {
    var wrapper   = document.getElementById('ic-wrapper');
    var svg       = document.getElementById('ic-svg');
    var tooltip   = document.getElementById('ic-tooltip');
    var legendRow = document.getElementById('legend-row');
    var W = wrapper.clientWidth  || 900;
    var H = wrapper.clientHeight || 520;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    var NS = 'http://www.w3.org/2000/svg';

    /* arrowhead defs */
    var defs = document.createElementNS(NS, 'defs');
    PATHWAYS.forEach(function(pw) {
      var m = document.createElementNS(NS, 'marker');
      m.setAttribute('id', 'arr-' + pw.id);
      m.setAttribute('markerWidth', '7'); m.setAttribute('markerHeight', '7');
      m.setAttribute('refX', '6');       m.setAttribute('refY', '3.5');
      m.setAttribute('orient', 'auto');
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d', 'M0,0 L0,7 L7,3.5 Z');
      p.setAttribute('fill', pw.color);
      m.appendChild(p); defs.appendChild(m);
    });
    svg.appendChild(defs);

    /* node map + initial positions */
    var nodeMap = {};
    NODES.forEach(function(n){ nodeMap[n.id] = n; n.vx = 0; n.vy = 0; });
    nodeMap['human'].x   = W*0.50; nodeMap['human'].y   = H*0.15;
    nodeMap['animal'].x  = W*0.13; nodeMap['animal'].y  = H*0.75;
    nodeMap['environ'].x = W*0.87; nodeMap['environ'].y = H*0.75;
    nodeMap['water'].x   = W*0.78; nodeMap['water'].y   = H*0.38;
    nodeMap['air'].x     = W*0.88; nodeMap['air'].y     = H*0.52;
    nodeMap['vector'].x  = W*0.50; nodeMap['vector'].y  = H*0.38;
    nodeMap['rabies'].x  = W*0.28; nodeMap['rabies'].y  = H*0.45;
    nodeMap['amr'].x     = W*0.38; nodeMap['amr'].y     = H*0.62;
    nodeMap['soil'].x    = W*0.22; nodeMap['soil'].y    = H*0.60;
    nodeMap['waste'].x   = W*0.62; nodeMap['waste'].y   = H*0.55;

    /* edges */
    var edgeGroup = document.createElementNS(NS, 'g');
    svg.appendChild(edgeGroup);
    var linkEls = EDGES.map(function(edge) {
      var pw    = PATHWAYS.find(function(p){ return p.id === edge.p; });
      var color = pw ? pw.color : '#888';
      var sN = nodeMap[edge.s], tN = nodeMap[edge.t];
      var sw = edge.p === 'priority' ? 2.5 : (sN&&sN.r>30||tN&&tN.r>30) ? 2 : 1.5;
      var line = document.createElementNS(NS, 'line');
      line.setAttribute('stroke', color);
      line.setAttribute('stroke-width', sw);
      line.setAttribute('stroke-opacity', '0.7');
      line.setAttribute('marker-end', 'url(#arr-' + edge.p + ')');
      line.style.cursor = 'pointer';
      line.style.transition = 'opacity 0.2s';
      line.addEventListener('mouseenter', function(e) {
        tooltip.innerHTML =
          '<div style="font-weight:700;color:' + color + ';margin-bottom:5px;">' +
          (pw ? pw.emoji + ' ' + pw.label : '') + '</div>' +
          '<div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">\u2197 ' + edge.label + '</div>' +
          edge.info;
        showTip(e);
      });
      line.addEventListener('mouseleave', hideTip);
      edgeGroup.appendChild(line);
      return { el:line, p:edge.p, s:edge.s, t:edge.t };
    });

    /* nodes */
    var nodeGroup = document.createElementNS(NS, 'g');
    svg.appendChild(nodeGroup);
    var nodeEls = NODES.map(function(nd) {
      var g = document.createElementNS(NS, 'g');
      g.style.cursor = 'grab';
      var glow = document.createElementNS(NS, 'circle');
      glow.setAttribute('r', nd.r+12);
      glow.setAttribute('fill', nd.color);
      glow.setAttribute('opacity', nd.r>40?'0.07':'0.05');
      g.appendChild(glow);
      var c = document.createElementNS(NS, 'circle');
      c.setAttribute('r', nd.r);
      c.setAttribute('fill', nd.r>40 ? nd.color : '#f8fafc');
      c.setAttribute('fill-opacity', nd.r>40 ? '0.15' : '0.97');
      c.setAttribute('stroke', nd.color);
      c.setAttribute('stroke-width', nd.r>40 ? '2.5' : '2');
      g.appendChild(c);
      var em = document.createElementNS(NS, 'text');
      em.setAttribute('text-anchor','middle');
      em.setAttribute('dominant-baseline','middle');
      em.setAttribute('font-size', nd.r>40?'26':'16');
      em.setAttribute('y', nd.r>40?'-8':'-5');
      em.textContent = nd.emoji;
      g.appendChild(em);
      var sub = document.createElementNS(NS, 'text');
      sub.setAttribute('text-anchor','middle');
      sub.setAttribute('dominant-baseline','middle');
      sub.setAttribute('font-size', nd.r>40?'11':'9');
      sub.setAttribute('font-weight','700');
      sub.setAttribute('font-family',"'DM Mono',monospace");
      sub.setAttribute('fill', nd.r>40?nd.color:'#334155');
      sub.setAttribute('y', nd.r>40?'14':'11');
      sub.textContent = nd.sub;
      g.appendChild(sub);
      /* drag */
      var dragging=false, ox,oy,sx,sy;
      g.addEventListener('mousedown', function(e) {
        dragging=false; ox=e.clientX; oy=e.clientY; sx=nd.x; sy=nd.y;
        e.preventDefault();
        var mm = function(e2) {
          if(Math.abs(e2.clientX-ox)>3||Math.abs(e2.clientY-oy)>3) dragging=true;
          nd.x=Math.max(nd.r+4,Math.min(W-nd.r-4,sx+e2.clientX-ox));
          nd.y=Math.max(nd.r+4,Math.min(H-nd.r-4,sy+e2.clientY-oy));
          tick=Math.min(tick,40); updatePos();
        };
        var mu = function() {
          window.removeEventListener('mousemove',mm);
          window.removeEventListener('mouseup',mu);
          if(!dragging){ tooltip.innerHTML=nd.info; tooltip.style.display='block'; tooltip.style.opacity='1'; }
        };
        window.addEventListener('mousemove',mm);
        window.addEventListener('mouseup',mu);
      });
      g.addEventListener('mouseleave', hideTip);
      nodeGroup.appendChild(g);
      return { el:g };
    });

    /* legend chips */
    var activePathway = null;
    PATHWAYS.forEach(function(pw) {
      var chip = document.createElement('div');
      chip.className = 'chip';
      chip.id = 'chip-' + pw.id;
      chip.style.border = '1px solid ' + pw.color + '55';
      chip.style.color  = pw.color;
      chip.innerHTML = '<span>' + pw.emoji + '</span><span>' + pw.label + '</span>';
      chip.addEventListener('click', function() {
        activePathway = (activePathway === pw.id) ? null : pw.id;
        PATHWAYS.forEach(function(p2) {
          var ch = document.getElementById('chip-'+p2.id);
          if(!ch) return;
          var active = !activePathway || activePathway===p2.id;
          ch.style.opacity   = active ? '1' : '0.35';
          ch.style.background = (activePathway===p2.id) ? p2.color+'22' : 'rgba(0,0,0,0.06)';
        });
        linkEls.forEach(function(le) {
          le.el.style.opacity = (!activePathway || le.p===activePathway) ? '1' : '0.08';
        });
      });
      legendRow.appendChild(chip);
    });

    /* force simulation */
    var tick = 0;
    function applyForces() {
      var REP=4000, DAMP=0.78;
      var fx=new Float32Array(NODES.length), fy=new Float32Array(NODES.length);
      for(var i=0;i<NODES.length;i++) for(var j=i+1;j<NODES.length;j++) {
        var dx=NODES[j].x-NODES[i].x, dy=NODES[j].y-NODES[i].y;
        var dist=Math.sqrt(dx*dx+dy*dy)||0.1;
        var minD=NODES[i].r+NODES[j].r+20;
        var f=dist<minD?REP/(dist*dist):REP*0.3/(dist*dist);
        fx[i]-=f*dx/dist; fy[i]-=f*dy/dist; fx[j]+=f*dx/dist; fy[j]+=f*dy/dist;
      }
      EDGES.forEach(function(e){
        var si=NODES.findIndex(function(n){return n.id===e.s;});
        var ti=NODES.findIndex(function(n){return n.id===e.t;});
        if(si<0||ti<0) return;
        var dx=NODES[ti].x-NODES[si].x, dy=NODES[ti].y-NODES[si].y;
        var dist=Math.sqrt(dx*dx+dy*dy)||1;
        var ideal=(NODES[si].r+NODES[ti].r)*3.0;
        var f=0.008*(dist-ideal);
        fx[si]+=f*dx/dist; fy[si]+=f*dy/dist; fx[ti]-=f*dx/dist; fy[ti]-=f*dy/dist;
      });
      NODES.forEach(function(n,i){
        fx[i]+=(W/2-n.x)*0.004; fy[i]+=(H/2-n.y)*0.004;
      });
      NODES.forEach(function(n,i){
        n.vx=((n.vx||0)+fx[i])*DAMP; n.vy=((n.vy||0)+fy[i])*DAMP;
        n.x=Math.max(n.r+4,Math.min(W-n.r-4,n.x+n.vx));
        n.y=Math.max(n.r+4,Math.min(H-n.r-4,n.y+n.vy));
      });
    }
    function updatePos() {
      linkEls.forEach(function(le){
        var s=nodeMap[le.s], t=nodeMap[le.t]; if(!s||!t) return;
        var dx=t.x-s.x, dy=t.y-s.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
        le.el.setAttribute('x1',s.x+dx/dist*(s.r+2));  le.el.setAttribute('y1',s.y+dy/dist*(s.r+2));
        le.el.setAttribute('x2',t.x-dx/dist*(t.r+10)); le.el.setAttribute('y2',t.y-dy/dist*(t.r+10));
      });
      nodeEls.forEach(function(ne,i){
        ne.el.setAttribute('transform','translate('+NODES[i].x+','+NODES[i].y+')');
      });
    }
    function loop(){ if(tick<220){applyForces();tick++;} updatePos(); requestAnimationFrame(loop); }
    loop();

    /* tooltip helpers */
    function showTip(e){ tooltip.style.display='block'; tooltip.style.opacity='1'; moveTip(e); document.addEventListener('mousemove',moveTip); }
    function hideTip(){ tooltip.style.display='none'; tooltip.style.opacity='0'; document.removeEventListener('mousemove',moveTip); }
    function moveTip(e){
      var rect=wrapper.getBoundingClientRect();
      var x=e.clientX-rect.left+16, y=e.clientY-rect.top+16;
      if(x+290>W) x=e.clientX-rect.left-294;
      if(y+140>H) y=e.clientY-rect.top-144;
      tooltip.style.left=x+'px'; tooltip.style.top=y+'px';
    }
  }

  window.addEventListener('load', function(){ setTimeout(init, 100); });
})();
</script>
</body>
</html>"""

    # Graph card uses iframe (srcdoc) — the only reliable way to run custom JS
    # inside a Dash app.  html.Script() is stripped by React and never executes.
    graph_card = html.Div([
        html.Div([
            html.Span(
                "Click pathway to highlight \u00b7 Hover nodes & edges \u00b7 Drag to reposition",
                style={"fontSize": "11px", "color": MUTED,
                       "fontFamily": "'DM Mono',monospace", "letterSpacing": "0.4px"},
            ),
        ], style={
            "padding": "20px 24px 12px",
            "display": "flex", "alignItems": "center",
            "justifyContent": "space-between", "flexWrap": "wrap", "gap": "12px",
        }),
        html.Iframe(
            srcDoc=_graph_iframe_html,
            style={
                "width": "100%",
                "height": "580px",
                "border": "none",
                "display": "block",
            },
        ),
    ], style={
        **CARD_STYLE,
        "padding": "0", "overflow": "hidden", "borderRadius": "20px",
        "marginBottom": "24px",
    })

    # ── BUILD PAGE ────────────────────────────────────────────────────────────
    return html.Div([
        section_banner(
            "Interconnectedness",
            "HOW HUMAN \u00b7 ANIMAL \u00b7 ENVIRONMENT HEALTH ARE LINKED IN BETTAHALASURU"
        ),

        graph_card,

        # ROW 1: Risk Matrix + Rainfall vs Disease
        grid2([
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                html.P("Bubble size = urgency score \u00b7 Hover for details", style={
                    "fontSize": "10px", "color": MUTED,
                    "fontFamily": "'DM Mono',monospace", "margin": "0 0 8px",
                }),
                dcc.Graph(figure=fig_bub, config={"displayModeBar": False},
                          style={"height": "300px"}),
            ], style=CARD_STYLE),

            html.Div([
                card_top_bar(C_GREEN),
                html.Div(style={"height": "6px"}),
                html.P("Environment \u2192 Human pathway \u00b7 2020\u20132024", style={
                    "fontSize": "10px", "color": MUTED,
                    "fontFamily": "'DM Mono',monospace", "margin": "0 0 8px",
                }),
                dcc.Graph(figure=fig_rain, config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], style=CARD_STYLE),
        ]),

        # ROW 2: Zoonotic + Cross-Pillar Polar
        grid2([
            html.Div([
                card_top_bar(C_RED),
                html.Div(style={"height": "6px"}),
                html.P("Stacked pathways by route and severity", style={
                    "fontSize": "10px", "color": MUTED,
                    "fontFamily": "'DM Mono',monospace", "margin": "0 0 8px",
                }),
                dcc.Graph(figure=fig_zoo, config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], style=CARD_STYLE),

            html.Div([
                card_top_bar(C_PURPLE),
                html.Div(style={"height": "6px"}),
                card_title("Cross-Pillar Contamination Index"),
                html.P(
                    "Each segment = a contamination pathway between pillars. "
                    "Larger area = higher risk (0\u2013100 scale).",
                    style={"fontSize": "10px", "color": MUTED,
                           "fontFamily": "'DM Mono',monospace", "margin": "0 0 4px"}
                ),
                html.Div([
                    html.Span("\ud83d\udd34 High Risk (>70)",       style={"fontSize":"9px","padding":"2px 7px","borderRadius":"4px","background":"rgba(255,112,67,0.15)","color":"#b91c1c","fontFamily":"'DM Mono',monospace","marginRight":"4px"}),
                    html.Span("\ud83d\udfe1 Medium Risk (50\u201370)",style={"fontSize":"9px","padding":"2px 7px","borderRadius":"4px","background":"rgba(255,202,40,0.15)","color":"#92400e","fontFamily":"'DM Mono',monospace","marginRight":"4px"}),
                    html.Span("\ud83d\udfe2 Lower Risk (<50)",       style={"fontSize":"9px","padding":"2px 7px","borderRadius":"4px","background":"rgba(105,240,174,0.15)","color":"#15803d","fontFamily":"'DM Mono',monospace","marginRight":"4px"}),
                    html.Span("\ud83d\udd35 Managed",                style={"fontSize":"9px","padding":"2px 7px","borderRadius":"4px","background":"rgba(79,195,247,0.15)","color":"#0284c7","fontFamily":"'DM Mono',monospace"}),
                ], style={"display":"flex","flexWrap":"wrap","gap":"4px","marginBottom":"8px"}),
                dcc.Graph(figure=fig_polar, config={"displayModeBar": False},
                          style={"height": "260px"}),
                html.Div(
                    "\u26a0 Critical: Water TDS (Human\u2192Env), Soil E. coli (Animal\u2192Env), "
                    "Lake contamination (Env\u2192Human) and Effluent discharge (Human\u2192Env) "
                    "all score above 70 \u2014 indicating urgent intervention needed.",
                    style={
                        "marginTop": "8px", "fontSize": "10px", "color": MUTED,
                        "lineHeight": "1.6", "padding": "8px",
                        "background": "rgba(255,112,67,0.05)", "borderRadius": "6px",
                        "borderLeft": f"3px solid {C_RED}",
                    }
                ),
            ], style=CARD_STYLE),
        ]),

        # ROW 3: Interaction Strength + Projected Outcome
        grid2([
            html.Div([
                card_top_bar(C_AMBER),
                html.Div(style={"height": "6px"}),
                html.P("Bidirectional flow scores between pillars", style={
                    "fontSize": "10px", "color": MUTED,
                    "fontFamily": "'DM Mono',monospace", "margin": "0 0 8px",
                }),
                dcc.Graph(figure=fig_int, config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], style=CARD_STYLE),

            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                html.P("Composite risk score over 5 years", style={
                    "fontSize": "10px", "color": MUTED,
                    "fontFamily": "'DM Mono',monospace", "margin": "0 0 8px",
                }),
                dcc.Graph(figure=fig_proj, config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], style=CARD_STYLE),
        ]),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# APP LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

def page_guard(page_fn):
    def wrapped(d):
        try:
            return page_fn(d)
        except Exception as e:
            print(f"[ERROR] Page failed: {e}")
            import traceback
            traceback.print_exc()
            return html.Div("Error loading page")
    return wrapped


page_overview        = page_guard(page_overview)
page_human           = page_guard(page_human)
page_animal          = page_guard(page_animal)
page_environment     = page_guard(page_environment)
page_interconnections = page_guard(page_interconnections)


app.index_string = """<!DOCTYPE html>
<html>
<head>
{%metas%}
<title>{%title%}</title>
{%favicon%}
{%css%}
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700;800&family=DM+Mono:wght@300;400;500&family=Playfair+Display:ital,wght@0,700;1,400&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #ffffff; font-family: 'Sora', sans-serif; }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #f1f5f9; }
  ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.2); border-radius: 4px; }
</style>
</head>
<body>
{%app_entry%}
<footer>
{%config%}
{%scripts%}
{%renderer%}
</footer>
</body>
</html>"""

TAB_CFG = [
    ("overview",         "⬡  Overview"),
    ("human",            "👤  Human Pillar"),
    ("animal",           "🐾  Animal Pillar"),
    ("environment",      "🌿  Environment Pillar"),
    ("interconnections", "⟳  Interconnectedness"),
]

_INIT_AQI, _INIT_POP = _extract_header_values(DATA)


app.layout = html.Div([
    dcc.Interval(id="refresh-interval", interval=60 * 1000, n_intervals=0),
    dcc.Store(id="data-timestamp", data=""),
    dcc.Store(id="chat-store", data=[]), #CHAT_BOT

    html.Header([
        html.Div([
            html.Div("🌍", style={
                "width": "48px", "height": "48px", "borderRadius": "12px",
                "background": "linear-gradient(135deg,#4fc3f7 0%,#69f0ae 100%)",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontSize": "22px", "boxShadow": "0 0 24px rgba(79,195,247,0.4)",
                "flexShrink": "0",
            }),
            html.Div([
                html.H1("One Health Village", style={
                    "fontFamily": "'Sora',sans-serif",
                    "fontSize": "22px", "fontWeight": "700",
                    "margin": "0", "color": TEXT,
                    "letterSpacing": "-0.3px",
                }),
                html.P("BETTAHALASURU · KARNATAKA · PLANETARY HEALTH FOUNDATION", style={
                    "fontFamily": "'DM Mono',monospace",
                    "fontSize": "10px", "color": MUTED,
                    "letterSpacing": "0.5px", "fontWeight": "600",
                    "margin": "2px 0 0",
                }),
            ]),
        ], style={"display": "flex", "alignItems": "center", "gap": "14px"}),

        html.Div([
            html.Div([html.Span("📍 "), "Bangalore Rural, KA"], style={
                "padding": "5px 12px", "borderRadius": "20px",
                "background": "rgba(0,0,0,0.06)", "border": f"1px solid {BORDER}",
                "fontSize": "11px", "fontFamily": "'DM Mono',monospace", "color": MUTED,
                "display": "flex", "alignItems": "center", "gap": "4px",
            }),
            html.Div(id="header-population", children=[
                "Population ", html.Span(_INIT_POP, style={"color": C_BLUE, "fontWeight": "600"}),
            ], style={
                "padding": "5px 12px", "borderRadius": "20px",
                "background": "rgba(0,0,0,0.06)", "border": f"1px solid {BORDER}",
                "fontSize": "11px", "fontFamily": "'DM Mono',monospace", "color": MUTED,
                "display": "flex", "alignItems": "center", "gap": "4px",
            }),
            html.Div(id="header-aqi", children=[
                "AQI ", html.Span(_INIT_AQI, style={"color": C_AMBER, "fontWeight": "600"}),
            ], style={
                "padding": "5px 12px", "borderRadius": "20px",
                "background": "rgba(0,0,0,0.06)", "border": f"1px solid {BORDER}",
                "fontSize": "11px", "fontFamily": "'DM Mono',monospace", "color": MUTED,
                "display": "flex", "alignItems": "center", "gap": "4px",
            }),
            html.Div([
                html.Div(id="last-update-display", style={"fontSize": "11px", "color": MUTED}),
                html.Button("↻ Refresh", id="manual-refresh-btn", n_clicks=0, style={
                    "background": "rgba(0,0,0,0.06)", "border": f"1px solid {C_GREEN}",
                    "color": C_GREEN, "borderRadius": "20px", "padding": "5px 14px",
                    "fontSize": "11px", "cursor": "pointer", "fontFamily": "'DM Mono',monospace",
                    "fontWeight": "600", "marginLeft": "8px",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),

    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "padding": "16px 40px",
        "borderBottom": f"1px solid {BORDER}",
        "background": "rgba(255,255,255,0.97)",
        "backdropFilter": "blur(12px)",
        "position": "sticky", "top": "0", "zIndex": "300",
        "boxShadow": "0 1px 8px rgba(0,0,0,0.06)",
        "fontFamily": "'Sora',sans-serif",
    }),

    dcc.Tabs(
        id="main-tabs", value="overview",
        children=[
            dcc.Tab(
                label=label, value=val,
                style={
                    "padding": "12px 20px", "fontSize": "11px", "fontWeight": "600",
                    "letterSpacing": "0.5px", "textTransform": "uppercase",
                    "fontFamily": "'DM Mono',monospace",
                    "color": "#334155", "background": "transparent",
                    "borderBottom": "2px solid transparent", "border": "none", "borderRadius": "0",
                },
                selected_style={
                    "padding": "12px 20px", "fontSize": "11px", "fontWeight": "600",
                    "letterSpacing": "0.5px", "textTransform": "uppercase",
                    "fontFamily": "'DM Mono',monospace",
                    "color": C_BLUE, "background": "transparent",
                    "borderBottom": f"2px solid {C_BLUE}", "border": "none", "borderRadius": "0",
                },
            )
            for val, label in TAB_CFG
        ],
        style={
            "background": "rgba(255,255,255,0.97)",
            "backdropFilter": "blur(16px)",
            "borderBottom": f"1px solid {BORDER}",
            "padding": "0 40px",
            "position": "sticky", "top": "73px", "zIndex": "200",
            "boxShadow": "0 1px 4px rgba(0,0,0,0.04)",
        },
    ),

    html.Div(id="page-content", style={
        "padding": "36px 40px 60px",
        "maxWidth": "1440px", "margin": "0 auto",
        "fontFamily": "'Sora',sans-serif",
        "background": "#ffffff",
    }),

    # ── AI Chatbot Bot ──────────────────────────────────────────────────────
    html.Div(id="chatbot-container", children=[

        # Floating toggle button
        html.Button("💬", id="chat-toggle-btn", n_clicks=0, style={
            "position": "fixed", "bottom": "30px", "right": "30px",
            "width": "60px", "height": "60px", "borderRadius": "50%",
            "background": "linear-gradient(135deg, #0284c7, #0ea5e9)",
            "color": "white", "border": "none",
            "fontSize": "26px", "cursor": "pointer", "zIndex": "1000",
            "boxShadow": "0 4px 20px rgba(2,132,199,0.5)",
            "transition": "transform 0.2s",
        }),

        # Chat panel
        html.Div(id="chat-panel", children=[

            # Header
            html.Div([
                html.Div([
                 html.Img(src="/assets/bot.png", style={
                    "width": "38px", "height": "38px", "borderRadius": "50%",
                    "objectFit": "cover", "flexShrink": "0",
                }),
                    html.Div([
                        html.Div("ONE Health Bot", style={
                            "color": "white", "fontWeight": "700",
                            "fontSize": "14px", "fontFamily": "'Sora',sans-serif",
                        }),
                        html.Div([
                            html.Span("●", style={"color": "#4ade80", "fontSize": "10px", "marginRight": "4px"}),
                            html.Span("DASHBOARD ASSISTANT", style={
                                "color": "rgba(255,255,255,0.7)", "fontSize": "10px",
                                "fontFamily": "'Space Mono', monospace", "letterSpacing": "0.5px",
                            }),
                        ], style={"display": "flex", "alignItems": "center"}),
                    ]),
                ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
                html.Div([
                    html.Button("⤢", id="chat-expand-btn", n_clicks=0, style={
                        "background": "transparent", "border": "none", "color": "rgba(255,255,255,0.7)",
                        "fontSize": "16px", "cursor": "pointer", "padding": "4px 8px",
                    }),
                    html.Button("✕", id="chat-close-btn", n_clicks=0, style={
                        "background": "transparent", "border": "none", "color": "rgba(255,255,255,0.7)",
                        "fontSize": "16px", "cursor": "pointer", "padding": "4px 8px",
                    }),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={
                "background": "linear-gradient(135deg, #1e3a5f, #0284c7)",
                "padding": "14px 16px", "borderRadius": "16px 16px 0 0",
                "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            }),

            # Chat history
            html.Div(id="chat-history", children=[
                html.Div([
                    html.Div("👋 Hello! I'm your ONE Health Assistant for Bettahalasuru village. Ask me anything about human health, animal health, environment, or interconnections data!", style={
                        "background": "white", "padding": "10px 14px",
                        "borderRadius": "4px 16px 16px 16px",
                        "fontSize": "13px", "color": "#1e293b", "lineHeight": "1.6",
                        "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
                        "maxWidth": "85%",
                    }),
                    html.Div("Just now", style={"fontSize": "10px", "color": "#94a3b8", "marginTop": "4px", "marginLeft": "4px"}),
                ], style={"display": "flex", "flexDirection": "column", "alignItems": "flex-start", "marginBottom": "12px"}),
            ], style={
                "height": "420px",
                "overflowY": "scroll",
                "overflowX": "hidden",
                "padding": "16px",
                "background": "#f1f5f9",
                "display": "flex",
                "flexDirection": "column",
                "scrollBehavior": "smooth",
            }),

            # Typing indicator (hidden by default)
            html.Div(id="typing-indicator", children=[
                html.Div([
                    html.Span(style={
                        "width": "7px", "height": "7px", "borderRadius": "50%",
                        "background": "#94a3b8", "display": "inline-block",
                        "animation": "bounce 1s infinite", "margin": "0 2px",
                    }),
                    html.Span(style={
                        "width": "7px", "height": "7px", "borderRadius": "50%",
                        "background": "#94a3b8", "display": "inline-block",
                        "animation": "bounce 1s infinite 0.2s", "margin": "0 2px",
                    }),
                    html.Span(style={
                        "width": "7px", "height": "7px", "borderRadius": "50%",
                        "background": "#94a3b8", "display": "inline-block",
                        "animation": "bounce 1s infinite 0.4s", "margin": "0 2px",
                    }),
                ], style={
                    "background": "white", "padding": "10px 16px",
                    "borderRadius": "4px 16px 16px 16px",
                    "display": "inline-flex", "alignItems": "center",
                    "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
                }),
            ], style={"padding": "0 16px 8px", "background": "#f1f5f9", "display": "none"}),

            # Input area
            html.Div([
                dcc.Textarea(
                    id="chat-input",
                    placeholder="Ask ONE Health Bot...",
                    value="",
                    style={
                        "flex": "1",
                        "borderRadius": "24px", "border": "1px solid #e2e8f0",
                        "fontSize": "13px", "fontFamily": "'Sora',sans-serif",
                        "resize": "none", "outline": "none",
                        "background": "#f8fafc", "color": "#1e293b",
                        "lineHeight": "1.5", "maxHeight": "60px", "height": "38px", "padding": "8px 14px",
                        "overflowY": "auto",
                        "boxShadow": "inset 0 1px 3px rgba(0,0,0,0.05)",
                    }
                ),
                html.Button("➤", id="chat-send-btn", n_clicks=0, style={
                    "width": "40px", "height": "40px", "borderRadius": "50%",
                    "background": "linear-gradient(135deg, #0284c7, #0ea5e9)",
                    "color": "white", "border": "none", "fontSize": "16px",
                    "cursor": "pointer", "flexShrink": "0",
                    "boxShadow": "0 2px 8px rgba(2,132,199,0.4)",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                }),
            ], style={
                "display": "flex", "alignItems": "center", "gap": "10px",
                "padding": "12px 16px", "background": "white",
                "borderTop": "1px solid #e2e8f0", "borderRadius": "0 0 16px 16px",
            }),

            # Footer
            html.Div("PROTECTED BY ◎ IISc Bangalore", style={
                "textAlign": "center", "fontSize": "9px", "color": "#94a3b8",
                "padding": "6px", "background": "white",
                "borderRadius": "0 0 16px 16px",
                "fontFamily": "'Space Mono', monospace", "letterSpacing": "0.5px",
            }),

        ], style={
            "display": "none",
            "position": "fixed", "bottom": "100px", "right": "30px",
            "width": "360px", "borderRadius": "16px",
            "boxShadow": "0 12px 40px rgba(0,0,0,0.18)",
            "zIndex": "999", "border": "1px solid #e2e8f0",
            "fontFamily": "'Sora',sans-serif",
            "overflow": "hidden",
        }),
    ]),

], style={
    "background": "#ffffff",
    "minHeight": "100vh",
    "fontFamily": "'Sora',sans-serif",
    "color": TEXT,
})

# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════


@app.callback(
    Output("data-timestamp",     "data"),
    Output("last-update-display","children"),
    Output("header-aqi",         "children"),
    Output("header-population",  "children"),
    Input("refresh-interval",    "n_intervals"),
    Input("manual-refresh-btn",  "n_clicks"),
)
def refresh_data(n_intervals, n_clicks):
    global DATA
    DATA = load_all()

    # Force-refresh the live AQI cache when the user clicks Refresh
    from dash import ctx as dash_ctx
    triggered = dash_ctx.triggered_id if dash_ctx.triggered_id else ""
    force = (triggered == "manual-refresh-btn")
    fetch_live_aqi_humidity(force=force)

    ts = datetime.now().strftime("%d %b %Y %H:%M:%S")
    aqi_str, pop_str = _extract_header_values(DATA)
    aqi_content = ["AQI ", html.Span(aqi_str, style={"color": C_AMBER, "fontWeight": "600"})]
    pop_content  = ["Population ", html.Span(pop_str, style={"color": C_BLUE, "fontWeight": "600"})]
    return ts, f"Updated: {ts}", aqi_content, pop_content


@app.callback(
    Output("page-content", "children"),
    Input("main-tabs",      "value"),
    Input("data-timestamp", "data"),
)
def render_page(tab, _ts):
    d = DATA
    pages = {
        "overview":         page_overview,
        "human":            page_human,
        "animal":           page_animal,
        "environment":      page_environment,
        "interconnections": page_interconnections,
    }
    return pages.get(tab, page_overview)(d)

# ══════════════════════════════════════════════════════════════════════════════
# CHATBOT CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

app.clientside_callback(
    """
    function(id) {
        setTimeout(function() {
            var input = document.getElementById('chat-input');
            if (!input) return;

            if (window._chatKeyHandler) {
                input.removeEventListener('keydown', window._chatKeyHandler);
            }

            window._chatKeyHandler = function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    e.stopPropagation();
                    var btn = document.getElementById('chat-send-btn');
                    if (btn) btn.click();
                }
            };

            input.addEventListener('keydown', window._chatKeyHandler);

            // Auto scroll to bottom whenever new content added
            var chatBox = document.getElementById('chat-history');
            if (chatBox) {
                if (window._chatScrollObserver) {
                    window._chatScrollObserver.disconnect();
                }
                window._chatScrollObserver = new MutationObserver(function() {
                    chatBox.scrollTop = chatBox.scrollHeight;
                });
                window._chatScrollObserver.observe(chatBox, {
                    childList: true,
                    subtree: true
                });
            }

        }, 500);
        return id;
    }
    """,
    Output("chat-input", "id"),
    Input("chat-input", "id"),
)

@app.callback(
    Output("chat-panel", "style"),
    Input("chat-toggle-btn", "n_clicks"),
    Input("chat-close-btn",  "n_clicks"),
    Input("chat-expand-btn", "n_clicks"),
    State("chat-panel", "style"),
    prevent_initial_call=True,
)
def toggle_chat(open_clicks, close_clicks, expand_clicks, current_style):
    from dash import ctx
    triggered = ctx.triggered_id

    normal_style = {
        "display": "block",
        "position": "fixed",
        "bottom": "100px",
        "right": "30px",
        "width": "380px",
        "height": "560px",
        "borderRadius": "16px",
        "boxShadow": "0 12px 40px rgba(0,0,0,0.18)",
        "zIndex": "999",
        "border": "1px solid #e2e8f0",
        "fontFamily": "'Sora',sans-serif",
        "overflow": "hidden",
    }

    fullscreen_style = {
        "display": "block",
        "position": "fixed",
        "top": "0",
        "left": "0",
        "right": "0",
        "bottom": "0",
        "width": "100vw",
        "height": "100vh",
        "borderRadius": "0",
        "boxShadow": "none",
        "zIndex": "9999",
        "border": "none",
        "fontFamily": "'Sora',sans-serif",
        "overflow": "hidden",
    }

    hidden_style = {
        "display": "none",
        "position": "fixed",
        "bottom": "100px",
        "right": "30px",
        "width": "380px",
        "height": "560px",
        "borderRadius": "16px",
        "zIndex": "999",
        "fontFamily": "'Sora',sans-serif",
        "overflow": "hidden",
    }

    if triggered == "chat-close-btn":
        return hidden_style

    if triggered == "chat-expand-btn":
        is_fullscreen = (
            current_style is not None and
            current_style.get("width") == "100vw"
        )
        return normal_style if is_fullscreen else fullscreen_style

    # chat-toggle-btn
    open_clicks = open_clicks or 0
    if open_clicks % 2 == 1:
        return normal_style
    return hidden_style

@app.callback(
    Output("chat-store", "data"),
    Output("chat-input", "value"),
    Input("chat-send-btn", "n_clicks"),
    State("chat-input",    "value"),
    State("chat-store",    "data"),
    prevent_initial_call=True,
)
def store_chat(n_clicks, user_input, stored):
    if not user_input or not user_input.strip():
        return stored or [], ""

    from datetime import datetime
    now = datetime.now().strftime("%I:%M %p")

    messages = list(stored or [])
    messages.append({"role": "user", "text": user_input.strip(), "time": now})
    bot_reply = ask_ollama(user_input.strip())
    messages.append({"role": "bot", "text": bot_reply, "time": now})

    return messages, ""


@app.callback(
    Output("chat-history", "children"),
    Input("chat-store", "data"),
)
def render_chat(messages):
    welcome = html.Div([
        html.Div(
            "👋 Hello! I am your ONE Health Assistant for Bettahalasuru village. "
            "Ask me anything about human health, animal health, environment, or interconnections data!",
            style={
                "background": "#e8f0fe", "padding": "10px 14px",
                "borderRadius": "4px 16px 16px 16px",
                "fontSize": "13px", "color": "#0d1b2a", "lineHeight": "1.6",
                "boxShadow": "0 1px 4px rgba(0,0,0,0.08)", "maxWidth": "85%",
            }
        ),
        html.Div("Just now", style={
            "fontSize": "10px", "color": "#94a3b8",
            "marginTop": "4px", "marginLeft": "4px",
        }),
    ], style={"display": "flex", "flexDirection": "column", "alignItems": "flex-start", "marginBottom": "12px"})

    if not messages:
        return [welcome]

    def clean_text(text):
        import re
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'#+\s?', '', text)
        return text.strip()

    def format_message(text):
        text = clean_text(text)
        lines = text.split('\n')
        elements = []
        for line in lines:
            line = line.strip()
            if not line:
                elements.append(html.Br())
            else:
                elements.append(html.Div(line, style={
                    "marginBottom": "4px",
                    "lineHeight": "1.6",
                }))
        return elements

    bubbles = [welcome]
    for msg in messages:
        role = msg.get("role")
        text = msg.get("text", "")
        time = msg.get("time", "")

        if role == "user":
            bubbles.append(html.Div([
                html.Div(text, style={
                    "background": "linear-gradient(135deg, #01579b, #0277bd)",
                    "color": "white", "padding": "10px 14px",
                    "borderRadius": "16px 4px 16px 16px",
                    "fontSize": "13px", "lineHeight": "1.6",
                    "maxWidth": "85%", "boxShadow": "0 2px 8px rgba(1,87,155,0.35)",
                }),
                html.Div(time, style={
                    "fontSize": "10px", "color": "#94a3b8",
                    "marginTop": "4px", "marginRight": "4px",
                }),
            ], style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end", "marginBottom": "12px"}))

        elif role == "bot":
            bubbles.append(html.Div([
                html.Div(format_message(text), style={
                    "background": "#e8f0fe", "color": "#0d1b2a",
                    "padding": "10px 14px",
                    "borderRadius": "4px 16px 16px 16px",
                    "fontSize": "13px",
                    "maxWidth": "85%", "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
                }),
                html.Div(time, style={
                    "fontSize": "10px", "color": "#94a3b8",
                    "marginTop": "4px", "marginLeft": "4px",
                }),
            ], style={"display": "flex", "flexDirection": "column", "alignItems": "flex-start", "marginBottom": "12px"}))

    return bubbles
#════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("calib-charts",  "children"),
    Output("calib-metrics", "children"),
    Input("calib-toggle",   "value"),
)
def update_calibration(drug_filter):
    if not drug_filter:
        drug_filter = "overlay"
    charts_div, metrics_div = _build_calib_content(drug_filter)
    return charts_div, metrics_div


if __name__ == "__main__":
    app.run(debug=True)