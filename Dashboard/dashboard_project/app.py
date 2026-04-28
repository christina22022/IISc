import dash
from dash import html, dcc, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
from datetime import datetime

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
    """
    Parse gram staining metrics from gram_staining_total (wide format)
    OR by counting rows in gram_staining_data.
    Returns dict with keys:
      total_isolates, gram_neg_pct, gram_neg_count,
      bacillus_pct, cocci_pct, mucoid_pct
    All values reflect the ACTUAL data in the sheets.
    """
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

    # ── Try wide-format gram_staining_total first ─────────────────────────
    # Expected columns: total_isolates, gram_negative_percent,
    #                   bacillus_percent, cocci_percent, mucoid_layer_percent
    if not gt.empty:
        print(f"[DEBUG] gram_staining_total columns: {list(gt.columns)}")
        print(f"[DEBUG] gram_staining_total head:\n{gt.head(2)}")

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

        # If wide format columns were found, compute gram_neg_count and return
        if ti_col and gnp_col:
            result["gram_neg_count"] = int(round(result["total_isolates"] * result["gram_neg_pct"] / 100))
            print(f"[DEBUG] gram_staining parsed result (wide): {result}")
            return result

        # ── Positional fallback if named columns not found ────────────────
        # But only if the DataFrame clearly has the right columns by position
        if len(gt.columns) >= 2:
            print(f"[WARN] gram_staining_total: could not find metric/value columns by name, trying positional read")
            # Try reading first row values positionally
            # Columns order: total_isolates, gram_negative_percent, bacillus_percent, cocci_percent, mucoid_layer_percent
            cols = list(gt.columns)
            row0 = gt.iloc[0]
            # Check if any column name contains "total" or "isolate"
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
                print(f"[DEBUG] gram_staining parsed result (positional): {result}")
                return result

    # ── Fallback: count directly from gram_staining_data rows ────────────
    if not gsd.empty:
        print(f"[DEBUG] gram_staining_data columns: {list(gsd.columns)}")
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

        # morphology from gram_staining_data
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

        print(f"[DEBUG] gram_staining parsed result (from gsd rows): {result}")

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

            # ── For gram_staining_total: do NOT pivot — it's already wide ──
            if t == "gram_staining_total":
                # Just clean values, skip the 2-column pivot logic
                def clean_val(x):
                    if isinstance(x, str):
                        x = x.strip().replace("%", "")
                    return x
                for col in df.columns:
                    df[col] = df[col].apply(clean_val)
                d[t] = df
                continue

            # ── Convert vertical → horizontal for other 2-column sheets ──
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


def _extract_header_values(data):
    aqi_str = "—"
    aq = data.get("air_quality", pd.DataFrame())
    aq_param_col = find_col(aq, ["parameter", "param", "metric"])
    aq_value_col = find_col(aq, ["value", "reading", "measurement"])
    if aq_param_col and aq_value_col and not aq.empty:
        aqi_rows = aq[aq[aq_param_col].astype(str).str.strip().str.upper() == "AQI"]
        if not aqi_rows.empty:
            vals = pd.to_numeric(aqi_rows[aq_value_col], errors="coerce").dropna()
            if not vals.empty:
                aqi_str = str(int(round(vals.mean())))

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

    aq = d.get("air_quality", pd.DataFrame())
    aq_param_col = find_col(aq, ["parameter", "param", "metric", "field"])
    aq_value_col = find_col(aq, ["value", "reading", "measurement"])
    kpis["aqi"] = "—"
    if aq_param_col and aq_value_col and not aq.empty:
        aqi_rows = aq[aq[aq_param_col].astype(str).str.strip().str.upper() == "AQI"]
        if not aqi_rows.empty:
            vals = pd.to_numeric(aqi_rows[aq_value_col], errors="coerce").dropna()
            if not vals.empty:
                kpis["aqi"] = fmt_num(round(vals.mean()))

    kpis["humidity"] = "—"
    if aq_param_col and aq_value_col and not aq.empty:
        hum_rows = aq[aq[aq_param_col].astype(str).str.strip().str.upper().isin(
            ["HUMIDITY", "RH", "RELATIVE HUMIDITY", "AMBIENT HUMIDITY"]
        )]
        if not hum_rows.empty:
            vals = pd.to_numeric(hum_rows[aq_value_col], errors="coerce").dropna()
            if not vals.empty:
                kpis["humidity"] = fmt_num(round(vals.mean(), 1))

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
            kpi_card("AQI",               kpis["aqi"],           "",          "Avg — air quality index",    "amber"),
            kpi_card("Humidity",          kpis["humidity"],      "%",         "Ambient avg reading",        "blue"),
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


def page_human(d):
    md  = d.get("majorDiseases",        pd.DataFrame())
    vt  = d.get("vectorDiseaseTrend",   pd.DataFrame())
    db  = d.get("diseaseBurden",        pd.DataFrame())
    sc  = d.get("phcScreeningPrograms", pd.DataFrame())
    vi  = d.get("vectorInsights",       pd.DataFrame())
    kpi = d.get("kpi_data",             pd.DataFrame())
    di  = d.get("disease_insights",     pd.DataFrame())

    h_population   = kpi_val_from_wide(kpi, ["totalPopulation", "total_population", "Total Population", "Population"], "3,573")
    h_phc_services = kpi_val_from_wide(kpi, ["phcServices", "PHC Services", "phcservices"], "8+")
    h_hypertension = kpi_val_from_wide(kpi, ["hypertension", "Hypertension", "hypertensionCases", "bpCases"], "—")
    h_dengue_peak  = kpi_val_from_wide(kpi, ["denguePeak", "dengue", "dengueCases", "Dengue"], "—")
    h_malaria_range= kpi_val_from_wide(kpi, ["malariaRange", "malaria", "malariaCases", "Malaria"], "—")

    if h_population == "3,573":
        h_population = kpi_val(kpi, ["Total Population", "Population", "Village Population"], "3,573")
    if h_phc_services == "8+":
        h_phc_services = kpi_val(kpi, ["PHC Services", "PHC Programs", "Services"], "8+")
    if h_hypertension == "—":
        h_hypertension = kpi_val(kpi, ["Hypertension", "Hypertension Cases", "BP Cases"], "—")
    if h_dengue_peak == "—":
        h_dengue_peak = kpi_val(kpi, ["Dengue Peak", "Dengue", "Dengue Cases"], "—")
    if h_malaria_range == "—":
        h_malaria_range = kpi_val(kpi, ["Malaria Range", "Malaria Cases", "Malaria"], "—")

    vi_disease_col = find_col(vi, ["disease"])
    vi_cases_col   = find_col(vi, ["casesRange", "cases_range", "cases", "caseRange"])
    vi_insight_col = find_col(vi, ["insight", "description", "note"])

    def get_vi_value(disease_name, col, default):
        if vi_disease_col and col and not vi.empty:
            row = vi[vi[vi_disease_col].astype(str).str.strip().str.lower() == disease_name.lower()]
            if not row.empty:
                val = str(row[col].iloc[0]).strip()
                return val if val and val.lower() != "nan" else default
        return default

    malaria_cases   = get_vi_value("malaria",     vi_cases_col,   "30–50/yr")
    malaria_insight = get_vi_value("malaria",     vi_insight_col, "Peak during monsoon. RDT used at PHC.")
    dengue_cases    = get_vi_value("dengue",      vi_cases_col,   "—")
    dengue_insight  = get_vi_value("dengue",      vi_insight_col, "Spike linked to high rainfall and standing water.")
    chikungunya_cases   = get_vi_value("chikungunya",   vi_cases_col,   "—")
    chikungunya_insight = get_vi_value("chikungunya",   vi_insight_col, "Sporadic post-monsoon. Nets distributed.")
    rainfall_insight    = get_vi_value("rainfall",      vi_insight_col,
                                       "↑ Rainfall → ↑ Vector breeding → ↑ Disease burden (2022 confirmed)")

    db_cat_col = find_col(db, ["diseaseCategory", "disease_category", "disease", "category"])
    db_val_col = find_col(db, ["value", "score", "severity"])
    db_sub_col = find_col(db, ["sublabel", "sub_label", "description", "note"])

    def get_db(cat_name, default_pct, default_sub):
        if db_cat_col and db_val_col and not db.empty:
            row = db[db[db_cat_col].astype(str).str.strip().str.lower().str.contains(cat_name.lower())]
            if not row.empty:
                pct = pd.to_numeric(row[db_val_col].iloc[0], errors="coerce")
                sub = str(row[db_sub_col].iloc[0]).strip() if db_sub_col else default_sub
                sub = sub if sub and sub.lower() != "nan" else default_sub
                return (float(pct) if pd.notna(pct) else default_pct), sub
        return default_pct, default_sub

    db_hyp_pct,  db_hyp_sub  = get_db("hypertension",  72, "Rising (age 40+)")
    db_diab_pct, db_diab_sub = get_db("diabetes",       65, "Growing — lifestyle factors")
    db_tb_pct,   db_tb_sub   = get_db("tuberculosis",   45, "Endemic — lower SES groups")
    db_anm_pct,  db_anm_sub  = get_db("anemia",         55, "Nutritional deficiency")
    db_mal_pct,  db_mal_sub  = get_db("malaria",         35, "30–50 cases/yr")
    db_den_pct,  db_den_sub  = get_db("dengue",          48, "Cases — peak season")
    db_lep_pct,  db_lep_sub  = get_db("leptospirosis",   18, "Monsoon linked")

    di_text_col  = find_col(di, ["insight_text", "insight", "finding", "text"])
    di_color_col = find_col(di, ["color_key", "color", "pillar"])
    color_lk     = {"blue": C_BLUE, "red": C_RED, "amber": C_AMBER, "green": C_GREEN}
    disease_insight_rows = []
    if di_text_col and not di.empty:
        for _, row in di.iterrows():
            txt = str(row.get(di_text_col, "")).strip()
            if not txt or txt.lower() == "nan":
                continue
            c_key = str(row.get(di_color_col, "blue")).strip().lower() if di_color_col else "blue"
            disease_insight_rows.append(insight_row(txt, color_lk.get(c_key, C_BLUE)))

    dis_col  = find_col(md, ["disease"])
    case_col = find_col(md, ["cases", "value"])
    fig_dis  = empty_fig("No disease case-load data available")
    if dis_col and case_col:
        md_s = coerce_numeric(md, [case_col]).dropna(subset=[dis_col, case_col]).sort_values(case_col, ascending=True)
        n = len(md_s)
        if n:
            clrs = [C_RED if i >= 2*n//3 else (C_AMBER if i >= n//3 else C_GREEN) for i in range(n)]
            fig_dis = go.Figure()
            fig_dis.add_trace(go.Bar(
                x=md_s[case_col], y=md_s[dis_col], orientation="h",
                marker_color=clrs, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Cases: %{x}<extra></extra>",
            ))
    fig_dis.update_layout(**PL("Major Diseases at PHC (2020–2024)", xaxis_title="Cases Reported"))

    year_col = find_col(vt, ["year"])
    fig_vec  = empty_fig("No vector disease trend data available")
    if year_col:
        vt_plot = coerce_numeric(vt, [year_col])
        fig_vec = go.Figure()
        for col, dash, color, name in [
            (find_col(vt, ["malaria"]),       "solid", C_BLUE,   "Malaria"),
            (find_col(vt, ["dengue"]),        "solid", C_RED,    "Dengue"),
            (find_col(vt, ["chikungunya"]),   "dash",  C_PURPLE, "Chikungunya"),
            (find_col(vt, ["leptospirosis"]), "dot",   C_GREEN,  "Leptospirosis"),
        ]:
            if col:
                vt_plot = coerce_numeric(vt_plot, [col])
                valid = vt_plot[[year_col, col]].dropna()
                if valid.empty:
                    continue
                fig_vec.add_trace(go.Scatter(
                    x=valid[year_col], y=valid[col], name=name, mode="lines+markers",
                    line=dict(color=color, width=2.2, dash=dash),
                    marker=dict(size=7, color=color),
                ))
        if not fig_vec.data:
            fig_vec = empty_fig("No vector disease trend data available")
    fig_vec.update_layout(**PL("Vector-Borne Disease Trend 2020–2024", yaxis_title="Cases", xaxis_title="Year"))

    badge_map_bg   = {"Active": "good", "Seasonal": "warn", "Periodic": "info"}
    screening_rows = []
    if not sc.empty:
        for _, row in sc.iterrows():
            screening_rows.append([
                (row.get("screeningType", ""), 2),
                (row.get("frequency", ""),     1),
                (badge(row.get("status", ""), badge_map_bg.get(row.get("status", ""), "info")), 1),
            ])

    return html.Div([
        section_banner("Human Pillar", "PRIMARY HEALTH CENTRE · BETTAHALASURU"),

        html.Div([
            kpi_card("Total Population",  h_population,    "",          "Bettahalasuru",              "blue"),
            kpi_card("PHC Services",      h_phc_services,  "programs",  "Screening programs active",  "green"),
            kpi_card("Hypertension Cases", h_hypertension,  "cases",    "Highest single disease",     "red"),
            kpi_card("Dengue Peak",       h_dengue_peak,   "cases",     "Spike — stagnant water",     "amber"),
            kpi_card("Malaria Range",     h_malaria_range, "cases/yr",  "Monsoon driven",             "purple"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        html.Div([
            html.Div([
                html.Div(style={"height": "3px", "background": C_BLUE, "borderRadius": "0 0 0 0", "margin": "-14px -16px 12px"}),
                html.P("🦟 MALARIA", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P(malaria_cases, style={"fontSize": "20px", "fontWeight": "700", "color": C_BLUE, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P(malaria_insight, style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_BLUE}"}),
            html.Div([
                html.Div(style={"height": "3px", "background": C_RED, "borderRadius": "0", "margin": "-14px -16px 12px"}),
                html.P("🦟 DENGUE", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P(dengue_cases, style={"fontSize": "20px", "fontWeight": "700", "color": C_RED, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P(dengue_insight, style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_RED}"}),
            html.Div([
                html.Div(style={"height": "3px", "background": C_PURPLE, "borderRadius": "0", "margin": "-14px -16px 12px"}),
                html.P("🦟 CHIKUNGUNYA", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P(chikungunya_cases, style={"fontSize": "20px", "fontWeight": "700", "color": C_PURPLE, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P(chikungunya_insight, style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_PURPLE}"}),
            html.Div([
                html.Div(style={"height": "3px", "background": C_AMBER, "borderRadius": "0", "margin": "-14px -16px 12px"}),
                html.P("🌧 RAINFALL LINK", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P("High corr.", style={"fontSize": "18px", "fontWeight": "700", "color": C_AMBER, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P(rainfall_insight, style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_AMBER}"}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(4,1fr)", "gap": "12px", "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_dis, config={"displayModeBar": False}), "blue"),
            chart_card(dcc.Graph(figure=fig_vec, config={"displayModeBar": False}), "green"),
        ]),

        grid2([
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                card_title("Disease Burden by Category"),
                progress_bar("Hypertension & CVD",      db_hyp_sub,  db_hyp_pct,  "red"),
                progress_bar("Diabetes (Type 2)",        db_diab_sub, db_diab_pct, "amber"),
                progress_bar("Tuberculosis",             db_tb_sub,   db_tb_pct,   "red"),
                progress_bar("Anemia (women & children)", db_anm_sub, db_anm_pct,  "purple"),
                progress_bar("Malaria (seasonal)",       db_mal_sub,  db_mal_pct,  "blue"),
                progress_bar("Dengue",                   db_den_sub,  db_den_pct,  "red"),
                progress_bar("Leptospirosis",            db_lep_sub,  db_lep_pct,  "green"),
            ], style=CARD_STYLE),

            html.Div([
                card_top_bar(C_PURPLE),
                html.Div(style={"height": "6px"}),
                card_title("PHC Screening Programs"),
                data_table_wrap(
                    [("Screening Type", 2), ("Frequency", 1), ("Status", 1)],
                    screening_rows if screening_rows else [
                        [("Blood Pressure Monitoring", 2), ("Weekly", 1),       (badge("Active",   "good"), 1)],
                        [("Blood Sugar Testing",        2), ("Weekly", 1),       (badge("Active",   "good"), 1)],
                        [("Antenatal Care",             2), ("Weekly", 1),       (badge("Active",   "good"), 1)],
                        [("TB Sputum / Chest X-Ray",   2), ("Symptomatic", 1),  (badge("Active",   "good"), 1)],
                        [("Malaria & Dengue RDT",       2), ("Peak seasons", 1), (badge("Seasonal", "warn"), 1)],
                        [("HIV Testing",                2), ("On request", 1),   (badge("Active",   "good"), 1)],
                        [("Eye & Vision Screening",     2), ("Health camps", 1), (badge("Periodic", "info"), 1)],
                        [("Anemia (Hemoglobin)",        2), ("Weekly", 1),       (badge("Active",   "good"), 1)],
                    ]
                ),
            ], style=CARD_STYLE),
        ]),

        html.Div(disease_insight_rows) if disease_insight_rows else html.Div([
            insight_row(
                f"{r.get('disease','')}: {r.get('casesRange','')} cases — {r.get('insight','')}",
                [C_BLUE, C_RED, C_AMBER][i % 3]
            )
            for i, (_, r) in enumerate(vi.iterrows())
        ] if not vi.empty else []),
    ])


def page_animal(d):
    rp   = d.get("rabiesProjection", pd.DataFrame())
    abc  = d.get("abcProgram",       pd.DataFrame())
    amr  = d.get("amrFindings",      pd.DataFrame())
    ai   = d.get("animalInsights",   pd.DataFrame())
    akpi = d.get("animal_kpi_data",  pd.DataFrame())
    abl  = d.get("antibioticLevels", pd.DataFrame())

    a_stray_dogs  = kpi_val_from_wide(akpi, ["strayDogs", "stray_dogs", "stray dogs"], "—")
    a_abc_count   = kpi_val_from_wide(akpi, ["abcProgramCount", "abc_program_count", "abcProgram", "abc", "abcCount"], "—")
    a_rabies_rate = kpi_val_from_wide(akpi, ["rabiesInfectionRate", "rabiesRate", "rabies_rate", "rabiesInfRate", "rabiesInf"], "—")
    a_livestock   = kpi_val_from_wide(akpi, ["livestockMonitored", "livestock_monitored", "livestock"], "—")
    a_amr_status  = kpi_val_from_wide(akpi, ["amrStatus", "AMR Status", "amrOverall", "antibioticStatus"], "Safe")

    if a_stray_dogs == "—":
        a_stray_dogs = kpi_val(akpi, ["Stray Dogs", "Stray Dog Population", "Dogs"], "—")
    if a_abc_count == "—":
        a_abc_count = kpi_val(akpi, ["ABC Count", "ABC Program", "ABC", "Neutered"], "—")
    if a_rabies_rate == "—":
        a_rabies_rate = kpi_val(akpi, ["Rabies Rate", "Rabies Reduction", "Rabies Infection Rate"], "—")
    if a_livestock == "—":
        a_livestock = kpi_val(akpi, ["Livestock", "Livestock Monitored", "Animals Monitored"], "—")

    gauge_val = 550
    gauge_raw = kpi_val_from_wide(akpi, ["strayDogs", "stray_dogs"], None)
    if gauge_raw is None:
        gauge_raw = kpi_val(akpi, ["Stray Dogs", "Stray Dog Population", "Dogs", "ABC Gauge"], None)
    if gauge_raw is not None:
        try:
            gauge_val = float(str(gauge_raw).replace(",", "").replace("+", ""))
        except ValueError:
            gauge_val = 550

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
            cnt_badge = badge(cnt_val, "good") if cnt_val and cnt_val.lower() != "nan" else badge("—", "info")
            abc_table_rows_dynamic.append([
                (str(row.get(abc_date_col, "")).strip(),     1.5),
                (str(row.get(abc_activity_col, "")).strip(), 3),
                (cnt_badge,                                  1),
            ])

    abc_table_rows = abc_table_rows_dynamic if abc_table_rows_dynamic else [
        [("05-Mar-2024", 1.5), ("Dogs picked up from Bettahalasuru village",             3), (badge("17", "info"), 1)],
        [("06-Mar-2024", 1.5), ("Neutering completed + anti-rabies vaccination",         3), (badge("17", "good"), 1)],
        [("07–10-Mar-2024", 1.5), ("Post-operative care + antibiotic shots (4 days)",   3), (badge("All 17", "good"), 1)],
        [("11-Mar-2024", 1.5), ("Released at original pickup location",                  3), (badge("17", "good"), 1)],
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
            bkind    = "good" if stat_txt.lower() in ("safe", "clear", "ok") else "warn"
            perm_val = str(row.get(amr_perm_col, "—")).strip() if amr_perm_col else "—"
            amr_table_rows_dynamic.append([
                (str(row.get(amr_ant_col,    "")).strip(), 1.2),
                (str(row.get(amr_sample_col, "")).strip(), 1.5),
                (str(row.get(amr_level_col,  "")).strip(), 1.5),
                (perm_val,                                 1.2),
                (badge(stat_txt, bkind),                   1),
            ])

    amr_table_rows = amr_table_rows_dynamic if amr_table_rows_dynamic else [
        [("Doxycycline", 1.2), ("Pig Excreta",   1.5), ("0.000002 mg/g",  1.5), ("0.02 mg/g", 1.2), (badge("Safe",  "good"), 1)],
        [("Doxycycline", 1.2), ("Hen Excreta",   1.5), ("0.00348 mg/g",   1.5), ("0.02 mg/g", 1.2), (badge("Safe",  "good"), 1)],
        [("Amoxicillin", 1.2), ("Feed",          1.5), ("None detected",  1.5), ("—",         1.2), (badge("Clear", "good"), 1)],
        [("Amoxicillin", 1.2), ("Excreta",       1.5), ("None detected",  1.5), ("—",         1.2), (badge("Clear", "good"), 1)],
        [("Amoxicillin", 1.2), ("Water",         1.5), ("None detected",  1.5), ("—",         1.2), (badge("Clear", "good"), 1)],
    ]

    rp_year_col = find_col(rp, ["year"])
    fig_rab = empty_fig("No rabies projection data available")
    if rp_year_col:
        rp_plot = coerce_numeric(rp, [rp_year_col])
        fig_rab = go.Figure()
        for col, color, dash, name in [
            (find_col(rp, ["noAbc"]),              C_RED,   "dot",   "No ABC"),
            (find_col(rp, ["withAbc"]),            C_AMBER, "dash",  "ABC Only"),
            (find_col(rp, ["withAbcVaccination"]), C_GREEN, "solid", "ABC + Vaccination"),
        ]:
            if col:
                rp_plot = coerce_numeric(rp_plot, [col])
                valid = rp_plot[[rp_year_col, col]].dropna()
                if valid.empty:
                    continue
                fig_rab.add_trace(go.Scatter(
                    x=valid[rp_year_col], y=valid[col], name=name, mode="lines+markers",
                    line=dict(color=color, width=2.5, dash=dash),
                    marker=dict(size=7, color=color),
                    fill="tozeroy" if name == "No ABC" else "none",
                    fillcolor=rgba(C_RED, 0.05),
                ))
        if not fig_rab.data:
            fig_rab = empty_fig("No rabies projection data available")
    fig_rab.update_layout(**PL("Rabies Projection — 5-Year Model",
                                yaxis_title="Infected Animals", xaxis_title="Year"))

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
    abc_pl = {k: v for k, v in PL("ABC Programme — Bettahalasuru").items() if k != "xaxis"}
    fig_abc.update_layout(**abc_pl)
    fig_abc.update_xaxes(
        gridcolor="rgba(0,0,0,0.08)", linecolor=BORDER,
        tickfont_color=MUTED, title_text="Animals",
    )

    amr_antibiotic_col_c = find_col(amr, ["antibiotic"])
    amr_sample_col_c     = find_col(amr, ["sampleType", "sample_type", "sample"])
    amr_level_col_c      = find_col(amr, ["levelFound", "level_found", "level"])
    amr_limit_col_c      = find_col(amr, ["permissible", "limit"])
    fig_amr = empty_fig("No AMR findings data available")
    if amr_antibiotic_col_c and amr_sample_col_c and amr_level_col_c and amr_limit_col_c:
        amr_v = coerce_numeric(amr, [amr_level_col_c, amr_limit_col_c])
        amr_v = amr_v.dropna(subset=[amr_antibiotic_col_c, amr_sample_col_c, amr_level_col_c, amr_limit_col_c]).copy()
        if not amr_v.empty:
            fig_amr = go.Figure()
            fig_amr.add_trace(go.Bar(
                x=amr_v[amr_antibiotic_col_c].astype(str) + " / " + amr_v[amr_sample_col_c].astype(str),
                y=amr_v[amr_level_col_c], name="Level Found", marker_color=C_BLUE,
                marker_line_width=0,
            ))
            fig_amr.add_trace(go.Scatter(
                x=amr_v[amr_antibiotic_col_c].astype(str) + " / " + amr_v[amr_sample_col_c].astype(str),
                y=amr_v[amr_limit_col_c], name="Permissible Limit", mode="markers",
                marker=dict(color=C_RED, size=14, symbol="line-ew",
                            line=dict(width=3, color=C_RED)),
            ))
    fig_amr.update_layout(**PL("AMR Residue vs Permissible Limits", yaxis_title="Concentration (mg/L)"))

    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=gauge_val,
        title={"text": "Stray Dogs in Programme", "font": {"color": C_AMBER, "size": 13}},
        number={"font": {"color": C_AMBER, "size": 42}},
        gauge=dict(
            axis=dict(range=[0, 800], tickcolor=MUTED, tickfont_color=MUTED),
            bar=dict(color=C_AMBER, thickness=0.28),
            bgcolor="#ffffff", bordercolor=BORDER,
            steps=[
                dict(range=[0,   200], color="#f0fdf4"),
                dict(range=[200, 400], color="#fef3c7"),
                dict(range=[400, 600], color="#fff7ed"),
                dict(range=[600, 800], color="#fee2e2"),
            ],
            threshold=dict(line=dict(color=C_RED, width=2.5), value=700),
        ),
    ))
    fig_g.update_layout(**PLgauge(), height=250, margin=dict(l=24, r=24, t=44, b=16))

    animal_insight_rows = []
    if ai_insight_col and not ai.empty:
        for i, (_, row) in enumerate(ai.iterrows()):
            txt = str(row.get(ai_insight_col, "")).strip()
            if txt and txt.lower() != "nan":
                animal_insight_rows.append(insight_row(txt, [C_RED, C_AMBER, C_GREEN][i % 3]))

    return html.Div([
        section_banner("Animal Pillar", "STRAY DOG MANAGEMENT · LIVESTOCK AMR · POULTRY & PIGGERY · BETTAHALASURU"),

        html.Div([
            kpi_card("Stray Dogs",         a_stray_dogs,  "",          "Village population",          "blue"),
            kpi_card("ABC Programme",      a_abc_count,   "animals",   "Neutered + anti-rabies shots","green"),
            kpi_card("Rabies Rate",        a_rabies_rate, "%",         "Post-ABC cohort",             "red"),
            kpi_card("Livestock",          a_livestock,   "animals",   "Via Vet Department",          "amber"),
            kpi_card("AMR Status",         a_amr_status,  "",          "Within permissible limits",   "green"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_rab, config={"displayModeBar": False}), "red"),
            chart_card(dcc.Graph(figure=fig_abc, config={"displayModeBar": False}), "amber"),
        ]),

        grid2([
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                card_title("Stray Dog ABC — Bettahalasuru"),
                data_table_wrap(
                    [("Date", 1.5), ("Activity", 3), ("Count", 1)],
                    abc_table_rows,
                ),
                html.Div([
                    html.P("ABC Program Key Insight", style={
                        "fontFamily": "'DM Mono',monospace", "fontSize": "10px", "fontWeight": "700",
                        "color": MUTED, "letterSpacing": "1px", "textTransform": "uppercase", "margin": "0 0 6px",
                    }),
                    html.P([
                        "Neutralization significantly reduces population growth, but rabies vaccination must accompany ABC programs. "
                        "Neutered populations show a ",
                        html.Strong(neutered_infection_rate, style={"color": C_RED}),
                        " infection rate vs ",
                        html.Strong(non_neutered_infection_rate, style={"color": C_GREEN}),
                        " in non-neutered — requiring a combined population control + vaccination strategy.",
                    ], style={"fontSize": "12px", "color": MUTED, "lineHeight": "1.7"}),
                ], style={"padding": "12px", "background": rgba(C_BLUE, 0.04), "borderRadius": "8px",
                          "borderLeft": f"3px solid {C_BLUE}"}),
            ], style=CARD_STYLE),

            chart_card(
                html.Div([
                    card_title("Livestock AMR Findings vs Permissible Limits"),
                    dcc.Graph(figure=fig_amr, config={"displayModeBar": False}),
                ]), "green"
            ),
        ]),

        grid2([
            chart_card(dcc.Graph(figure=fig_g, config={"displayModeBar": False}), "amber"),
            html.Div([
                card_top_bar(C_RED),
                html.Div(style={"height": "6px"}),
                card_title("Livestock AMR — Detailed Findings"),
                data_table_wrap(
                    [("Antibiotic", 1.2), ("Sample Type", 1.5), ("Level Found", 1.5), ("Permissible", 1.2), ("Status", 1)],
                    amr_table_rows,
                ),
                html.Div(
                    "Detection method: HPLC analysis. Current antibiotic levels pose no immediate AMR risk, but ongoing monitoring is essential.",
                    style={"fontSize": "11px", "color": MUTED, "padding": "10px", "lineHeight": "1.6",
                           "background": rgba(C_GREEN, 0.05), "borderRadius": "6px", "borderLeft": f"3px solid {C_GREEN}"}
                ),
            ], style=CARD_STYLE),
        ]),

        html.Div(animal_insight_rows) if animal_insight_rows else html.Div(),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1: Environment page — unique insights per chart, no duplication
# FIX 2/3: Gram staining uses parse_gram_staining() for all values
# FIX 4: Effluent TDS KPI label includes "(Sample 1)"
# ══════════════════════════════════════════════════════════════════════════════

def page_environment(d):
    wq  = d.get("water_quality",       pd.DataFrame())
    vc  = d.get("villagewatercfu",     pd.DataFrame())
    lc  = d.get("lake_water_cfu",      pd.DataFrame())
    gsd = d.get("gram_staining_data",  pd.DataFrame())
    mc  = d.get("microbial_analysis",  pd.DataFrame())
    aq  = d.get("air_quality",         pd.DataFrame())
    sc  = d.get("soil_cfu",            pd.DataFrame())
    pv  = d.get("physiochem_village_waterquality", pd.DataFrame())

    # ── FIX 2 & 3: Parse gram staining from actual data ───────────────────
    gs = parse_gram_staining(d)
    total_isolates = gs["total_isolates"]
    gram_neg_pct   = gs["gram_neg_pct"]
    gram_neg_count = gs["gram_neg_count"]
    bacillus_pct   = gs["bacillus_pct"]
    cocci_pct      = gs["cocci_pct"]
    mucoid_pct     = gs["mucoid_pct"]

    # ── AQI from air_quality sheet ────────────────────────────────────────
    aqi_val      = 135
    humidity_val = "—"
    aq_param_col = find_col(aq, ["parameter", "param", "metric"])
    aq_value_col = find_col(aq, ["value", "reading", "measurement"])
    if aq_param_col and aq_value_col and not aq.empty:
        for _, aq_row in aq.iterrows():
            p = str(aq_row[aq_param_col]).strip().upper()
            v = aq_row[aq_value_col]
            if p == "AQI":
                parsed = pd.to_numeric(v, errors="coerce")
                if pd.notna(parsed):
                    aqi_val = parsed
            elif p in ("HUMIDITY", "RH", "RELATIVE HUMIDITY"):
                parsed = pd.to_numeric(v, errors="coerce")
                if pd.notna(parsed):
                    humidity_val = fmt_num(parsed)

    # ── FIX 4: Effluent TDS from Sample 1 specifically ───────────────────
    effluent_tds = "—"
    wq_source_col_e = find_col(wq, ["source_name", "sourceName", "source", "location", "label"])
    wq_tds_col_e    = find_col(wq, ["TDS_ppm", "TDS", "tds"])
    wq_id_col_kpi   = find_col(wq, ["sampleId", "sample_id", "id", "sample_no", "Sample no.", "Sample no"])

    if not wq.empty and wq_tds_col_e:
        # Try to get Sample 1 by ID first
        if wq_id_col_kpi:
            s1_mask = wq[wq_id_col_kpi].astype(str).str.strip().str.lower().isin(["s1", "1", "sample 1", "sample1"])
            if s1_mask.any():
                tds_raw = pd.to_numeric(wq.loc[s1_mask, wq_tds_col_e].iloc[0], errors="coerce")
                if pd.notna(tds_raw):
                    effluent_tds = f"{int(tds_raw):,}"
        # Fallback: first row matching "effluent" in source name
        if effluent_tds == "—" and wq_source_col_e:
            mask = wq[wq_source_col_e].astype(str).str.lower().str.contains("effluent|household", na=False)
            if mask.any():
                tds_raw = pd.to_numeric(wq.loc[mask, wq_tds_col_e].iloc[0], errors="coerce")
                if pd.notna(tds_raw):
                    effluent_tds = f"{int(tds_raw):,}"
        # Fallback: very first row
        if effluent_tds == "—":
            tds_raw = pd.to_numeric(wq[wq_tds_col_e].iloc[0], errors="coerce")
            if pd.notna(tds_raw):
                effluent_tds = f"{int(tds_raw):,}"

    # ── FIX 1a: Water Quality scatter — TDS vs DO with status coloring ────
    # Shows: which sources are fit/unfit for drinking based on TDS & DO thresholds
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

    # ── FIX 1b: Physiochemical radar — pH, EC, turbidity profile per source ──
    # Shows: multi-parameter physicochemical fingerprint — DIFFERENT from TDS/DO scatter
    wq_ph_col_r  = find_col(wq, ["pH", "ph"])
    wq_ec_col_r  = find_col(wq, ["EC_mS", "EC_uS", "EC", "ec"])
    wq_ntu_col_r = find_col(wq, ["turbidity_NTU", "turbidity", "NTU"])
    fig_physchem = empty_fig("No physicochemical data available")

    if wq_source_col and wq_ph_col_r and wq_ec_col_r and wq_ntu_col_r and not wq.empty:
        pc_plot = coerce_numeric(wq, [wq_ph_col_r, wq_ec_col_r, wq_ntu_col_r])
        pc_plot = pc_plot.dropna(subset=[wq_source_col, wq_ph_col_r, wq_ec_col_r]).copy()

        if not pc_plot.empty:
            # Normalise each parameter to 0–100 for radar display
            def norm_col(col):
                mn, mx = pc_plot[col].min(), pc_plot[col].max()
                if mx == mn:
                    return pd.Series([50.0] * len(pc_plot), index=pc_plot.index)
                return ((pc_plot[col] - mn) / (mx - mn) * 100).round(1)

            pc_plot["pH_norm"]  = norm_col(wq_ph_col_r)
            pc_plot["EC_norm"]  = norm_col(wq_ec_col_r)
            pc_plot["NTU_norm"] = norm_col(wq_ntu_col_r) if wq_ntu_col_r else 0

            # Build a grouped bar chart: each source = group, parameters = bars
            # Shows how each source compares across pH / EC / Turbidity
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

            # Add safe-zone reference line at 50 (midpoint)
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

    # ── Village water CFU ─────────────────────────────────────────────────
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

    # ── Lake water CFU ────────────────────────────────────────────────────
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

    # ── Soil CFU ──────────────────────────────────────────────────────────
    sc_sample_col = find_col(sc, ["sample", "Sample", "site_name", "location"])
    sc_mean_col   = find_col(sc, ["mean_cfu", "CFU avg", "CFU_avg"])
    fig_soil = empty_fig("No soil CFU data available")
    if sc_sample_col and sc_mean_col:
        sc_plot = coerce_numeric(sc, [sc_mean_col]).dropna(subset=[sc_sample_col, sc_mean_col]).copy()
        if not sc_plot.empty:
            colors = [C_RED, C_BLUE, C_GREEN] * ((len(sc_plot) // 3) + 1)
            fig_soil = go.Figure()
            fig_soil.add_trace(go.Bar(
                x=sc_plot[sc_sample_col], y=sc_plot[sc_mean_col],
                marker_color=colors[:len(sc_plot)], marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>%{y:.4f} CFU/mL<extra></extra>",
            ))
    fig_soil.update_layout(**PL("Soil Microbial Load by Site (CFU/mL)", yaxis_title="CFU/mL"))

    # ── FIX 2 & 3: Gram staining pie from parsed data ────────────────────
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

    # ── AQI gauge ─────────────────────────────────────────────────────────
    fig_aqi = go.Figure(go.Indicator(
        mode="gauge+number", value=float(aqi_val),
        title={"text": "Air Quality Index (AQI)", "font": {"color": C_AMBER, "size": 13}},
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

    # ── Water quality table ───────────────────────────────────────────────
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
            for attr in ["ph_v", "ec_v", "tds_v", "do_v", "ntu_v"]:
                if locals()[attr] == "nan":
                    locals()[attr]  # just reference; fix below
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

    # ── Microbial table ───────────────────────────────────────────────────
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

    # ── FIX 3: Gram staining morphology breakdown chart from gsd rows ────
    fig_gram_morph = empty_fig("No gram staining morphology data available")
    if not gsd.empty:
        stain_col = find_col(gsd, ["gram_stain", "gramStain", "stain", "result", "gram stain", "gram", "type"])
        morph_col = find_col(gsd, ["morphology", "shape", "colony_morphology", "colony morphology"])

        if stain_col and not gsd.empty:
            stain_vals = gsd[stain_col].astype(str).str.strip()
            counts = stain_vals.value_counts()
            if not counts.empty:
                bar_colors = []
                for label in counts.index:
                    ll = label.lower()
                    if "neg" in ll:
                        bar_colors.append(C_RED)
                    elif "pos" in ll:
                        bar_colors.append(C_GREEN)
                    else:
                        bar_colors.append(C_BLUE)
                fig_gram_morph = go.Figure()
                fig_gram_morph.add_trace(go.Bar(
                    x=counts.index.tolist(),
                    y=counts.values.tolist(),
                    marker_color=bar_colors,
                    marker_line_width=0,
                    hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>",
                ))
                fig_gram_morph.update_layout(**PL(
                    f"Gram Staining Distribution — {total_isolates} Isolates",
                    yaxis_title="Isolate Count",
                    xaxis_title="Stain Result",
                ))

    return html.Div([
        section_banner("Environment Pillar", "WATER · MICROBIOLOGY · GRAM STAINING · SOIL · AIR QUALITY"),

        # ── FIX 4: KPI card label includes "(Sample 1)" ───────────────────
        grid4([
            kpi_card("AQI Level",              fmt_num(aqi_val), "",    "Unhealthy for sensitive groups",     "amber"),
            kpi_card("Humidity",               humidity_val,     "%",   "Respiratory risk assessment",        "blue"),
            kpi_card("Effluent TDS (Sample 1)", effluent_tds,    "ppm", "S1 Effluent Household — WHO lim 500","red"),
            kpi_card("Gram –ve Isolates",      f"{gram_neg_count}/{total_isolates}", "",
                     f"{gram_neg_pct:.1f}% Gram-negative of {total_isolates} isolates", "purple"),
        ]),

        # ── FIX 1: Two distinct water charts ─────────────────────────────
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

        # ── FIX 2 & 3: Gram staining — pie (Neg/Pos split) + morphology bar ──
        grid2([
            chart_card(dcc.Graph(figure=fig_gr,         config={"displayModeBar": False}), "red"),
            chart_card(dcc.Graph(figure=fig_gram_morph, config={"displayModeBar": False}), "purple"),
        ]),

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

            # ── FIX 2 & 3: Gram staining summary uses parsed data ─────────
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
    zoo  = d.get("zoonoticTransmission", pd.DataFrame())
    rd   = d.get("rainfallDisease",      pd.DataFrame())
    ints = d.get("interactionStrength",  pd.DataFrame())
    rm   = d.get("riskMatrix",           pd.DataFrame())
    cp   = d.get("crossPillarIndex",     pd.DataFrame())
    aq   = d.get("air_quality",          pd.DataFrame())
    wq   = d.get("water_quality",        pd.DataFrame())

    aqi_val = "—"
    humidity_val = "—"
    effluent_tds = "—"

    aq_param_col = find_col(aq, ["parameter", "param", "metric"])
    aq_value_col = find_col(aq, ["value", "reading", "measurement"])
    if aq_param_col and aq_value_col and not aq.empty:
        for _, aq_row in aq.iterrows():
            p = str(aq_row[aq_param_col]).strip().upper()
            v = pd.to_numeric(aq_row[aq_value_col], errors="coerce")
            if pd.isna(v):
                continue
            if p == "AQI":
                aqi_val = v
            elif p in ("HUMIDITY", "RH", "RELATIVE HUMIDITY"):
                humidity_val = fmt_num(v)

    wq_source_col = find_col(wq, ["source_name", "sourceName", "source", "location", "label"])
    wq_tds_col = find_col(wq, ["TDS_ppm", "TDS", "tds"])
    if wq_source_col and wq_tds_col and not wq.empty:
        mask = wq[wq_source_col].astype(str).str.lower().str.contains("effluent|household", na=False)
        if mask.any():
            tds_raw = pd.to_numeric(wq.loc[mask, wq_tds_col].iloc[0], errors="coerce")
            if pd.notna(tds_raw):
                effluent_tds = f"{int(tds_raw):,}"

    top_risk_urgency  = "—"
    rm_factor_col_k   = find_col(rm, ["factor"])
    rm_urgency_col_k  = find_col(rm, ["urgency"])
    if rm_factor_col_k and rm_urgency_col_k and not rm.empty:
        rm_u = coerce_numeric(rm, [rm_urgency_col_k]).dropna(subset=[rm_urgency_col_k])
        if not rm_u.empty:
            top_risk_urgency = fmt_num(rm_u[rm_urgency_col_k].max())

    rainfall_corr = "—"
    rd_rain_col_k = find_col(rd, ["rainfallIndex", "rainfall_index", "rainfall"])
    rd_dengue_col = find_col(rd, ["dengueCases", "dengue"])
    if rd_rain_col_k and rd_dengue_col and not rd.empty:
        rd_c = coerce_numeric(rd, [rd_rain_col_k, rd_dengue_col]).dropna(subset=[rd_rain_col_k, rd_dengue_col])
        if len(rd_c) >= 2:
            corr = rd_c[rd_rain_col_k].corr(rd_c[rd_dengue_col])
            if pd.notna(corr):
                rainfall_corr = f"{corr:.2f}"

    lepto_env_pct = "—"
    zoo_path_col  = find_col(zoo, ["pathway"])
    zoo_env_col   = find_col(zoo, ["environmental"])
    if zoo_path_col and zoo_env_col and not zoo.empty:
        lepto_row = zoo[zoo[zoo_path_col].astype(str).str.lower().str.contains("lepto")]
        if not lepto_row.empty:
            val = pd.to_numeric(lepto_row[zoo_env_col].iloc[0], errors="coerce")
            if pd.notna(val):
                lepto_env_pct = fmt_num(val)

    abc_vacc_eff = "—"
    rp2 = d.get("rabiesProjection", pd.DataFrame())
    rp_year_col2  = find_col(rp2, ["year"])
    rp_noabc_col  = find_col(rp2, ["noAbc"])
    rp_vacc_col   = find_col(rp2, ["withAbcVaccination"])
    if rp_year_col2 and rp_noabc_col and rp_vacc_col and not rp2.empty:
        rp2_n = coerce_numeric(rp2, [rp_noabc_col, rp_vacc_col]).dropna(subset=[rp_noabc_col, rp_vacc_col])
        if not rp2_n.empty:
            last = rp2_n.iloc[-1]
            no_abc = last[rp_noabc_col]
            with_vacc = last[rp_vacc_col]
            if no_abc > 0:
                abc_vacc_eff = fmt_num(round((1 - with_vacc / no_abc) * 100))

    oh_reduction = "—"
    proj3 = d.get("projectedOutcome", pd.DataFrame())
    proj_year3 = find_col(proj3, ["year"])
    proj_no3   = find_col(proj3, ["noIntervention", "baseline"])
    proj_full3 = find_col(proj3, ["fullOneHealth", "full"])
    if proj_year3 and proj_no3 and proj_full3 and not proj3.empty:
        p3 = coerce_numeric(proj3, [proj_no3, proj_full3]).dropna(subset=[proj_no3, proj_full3])
        if not p3.empty:
            last3 = p3.iloc[-1]
            if last3[proj_no3] > 0:
                oh_reduction = f"−{fmt_num(round((1 - last3[proj_full3] / last3[proj_no3]) * 100))}"

    zoo_pathway_col = find_col(zoo, ["pathway"])
    fig_zoo = empty_fig("No zoonotic transmission data available")
    if zoo_pathway_col:
        zoo_plot = coerce_numeric(zoo, [
            find_col(zoo, ["directContact"]),
            find_col(zoo, ["environmental"]),
            find_col(zoo, ["foodWater"]),
            find_col(zoo, ["vectorMediated"]),
        ])
        fig_zoo = go.Figure()
        for col, c, name in [
            (find_col(zoo, ["directContact"]), C_RED,   "Direct Contact"),
            (find_col(zoo, ["environmental"]), C_GREEN, "Environmental"),
            (find_col(zoo, ["foodWater"]),     C_AMBER, "Food / Water"),
            (find_col(zoo, ["vectorMediated"]),C_BLUE,  "Vector Mediated"),
        ]:
            if col:
                valid = zoo_plot[[zoo_pathway_col, col]].dropna()
                if valid.empty:
                    continue
                fig_zoo.add_trace(go.Bar(x=valid[zoo_pathway_col], y=valid[col], name=name, marker_color=c))
        if not fig_zoo.data:
            fig_zoo = empty_fig("No zoonotic transmission data available")
    fig_zoo.update_layout(**PL("Zoonotic Transmission Pathways", barmode="stack", yaxis_title="Transmission %"))
    fig_zoo.update_xaxes(tickangle=-15)

    rd_rain_col = find_col(rd, ["rainfallIndex"])
    rd_year_col = find_col(rd, ["year"])
    fig_rain = empty_fig("No rainfall-disease data available")
    if rd_rain_col:
        rd_plot = coerce_numeric(rd, [rd_rain_col, rd_year_col] if rd_year_col else [rd_rain_col])
        fig_rain = go.Figure()
        for col, c, name in [
            (find_col(rd, ["dengueCases"]),   C_RED,    "Dengue"),
            (find_col(rd, ["malariaCases"]),  C_PURPLE, "Malaria"),
            (find_col(rd, ["leptospirosis"]), C_GREEN,  "Leptospirosis"),
        ]:
            if col:
                rd_plot = coerce_numeric(rd_plot, [col])
                valid = rd_plot[[rd_rain_col, col] + ([rd_year_col] if rd_year_col else [])].dropna(subset=[rd_rain_col, col])
                if valid.empty:
                    continue
                fig_rain.add_trace(go.Scatter(
                    x=valid[rd_rain_col], y=valid[col], name=name,
                    mode="markers+lines", marker=dict(size=10, color=c),
                    line=dict(color=c, width=1.8),
                    text=valid[rd_year_col] if rd_year_col else None,
                    hovertemplate=f"<b>{name}</b><br>Rainfall: %{{x}}<br>Cases: %{{y}}<extra></extra>",
                ))
        if not fig_rain.data:
            fig_rain = empty_fig("No rainfall-disease data available")
    fig_rain.update_layout(**PL("Rainfall Index vs Vector Disease Cases",
                                 xaxis_title="Rainfall Index", yaxis_title="Cases"))

    ints_label_col   = find_col(ints, ["interaction"])
    ints_current_col = find_col(ints, ["current"])
    ints_after_col   = find_col(ints, ["afterIntervention", "after_intervention"])
    fig_int = empty_fig("No interaction strength data available")
    if ints_label_col and ints_current_col and ints_after_col:
        ints_plot = coerce_numeric(ints, [ints_current_col, ints_after_col]).dropna(subset=[ints_label_col, ints_current_col, ints_after_col])
        if not ints_plot.empty:
            fig_int = go.Figure()
            fig_int.add_trace(go.Bar(x=ints_plot[ints_label_col], y=ints_plot[ints_current_col],
                                      name="Current", marker_color=C_RED, marker_line_width=0))
            fig_int.add_trace(go.Bar(x=ints_plot[ints_label_col], y=ints_plot[ints_after_col],
                                      name="After Intervention", marker_color=rgba(C_GREEN, 0.6),
                                      marker_line_color=C_GREEN, marker_line_width=1.5))
    fig_int.update_layout(**PL("Cross-Pillar Interaction — Before vs After",
                                barmode="group", yaxis_title="Interaction Score"))

    rm_likelihood_col = find_col(rm, ["likelihood"])
    rm_impact_col     = find_col(rm, ["impact"])
    rm_urgency_col    = find_col(rm, ["urgency"])
    rm_factor_col     = find_col(rm, ["factor"])
    fig_bub = empty_fig("No risk matrix data available")
    if rm_likelihood_col and rm_impact_col and rm_urgency_col and rm_factor_col:
        rm_plot = coerce_numeric(rm, [rm_likelihood_col, rm_impact_col, rm_urgency_col])
        rm_plot = rm_plot.dropna(subset=[rm_likelihood_col, rm_impact_col, rm_urgency_col, rm_factor_col]).copy()
        if not rm_plot.empty:
            fig_bub = px.scatter(
                rm_plot, x=rm_likelihood_col, y=rm_impact_col, size=rm_urgency_col,
                hover_name=rm_factor_col, text=rm_factor_col, size_max=55,
                color=rm_urgency_col,
                color_continuous_scale=[[0, C_GREEN], [0.4, C_AMBER], [0.7, C_RED], [1, "#7f1d1d"]],
                title="Risk Matrix — Likelihood vs Impact (size = Urgency)",
                labels={rm_likelihood_col: "Likelihood (%)", rm_impact_col: "Impact Score"},
            )
            fig_bub.update_traces(textposition="top center", textfont=dict(size=9, color=MUTED))
            fig_bub.update_layout(**PL())
            fig_bub.update_coloraxes(colorbar_tickfont_color=MUTED, colorbar_title_font_color=MUTED)

    return html.Div([
        section_banner("Interconnectedness", "HOW HUMAN · ANIMAL · ENVIRONMENT HEALTH ARE LINKED IN BETTAHALASURU"),

        html.Div([
            kpi_card("Top Risk — Urgency", top_risk_urgency, "score", "Highest urgency factor",       "red"),
            kpi_card("Rainfall Corr.",     rainfall_corr,    "",      "Dengue correlation index",     "amber"),
            kpi_card("Lepto Env Route",    lepto_env_pct,    "%",     "Environmental/soil dominant",  "green"),
            kpi_card("Rabies ABC+Vacc",    abc_vacc_eff,     "%",     "Reduction vs no intervention", "blue"),
            kpi_card("Full OH 2030",       oh_reduction,     "%",     "Burden vs doing nothing",      "green"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        html.Div([
            html.P([
                html.Strong("One Health Nexus: "),
                "Household effluent flows into the lake (Human→Environment), livestock excreta contaminates "
                "soil and water (Animal→Environment), contaminated water drives disease burden (Environment→Human). "
                "Full One Health intervention reduces all pillar-to-pillar interaction scores by 40–65%. "
                "Monsoon seasons are the highest-risk windows for dengue, malaria, and leptospirosis simultaneously.",
            ], style={"fontSize": "13px", "color": MUTED, "lineHeight": "1.7", "margin": "0"}),
        ], style={
            "background": rgba(C_BLUE, 0.04), "border": f"1px solid {rgba(C_BLUE, 0.2)}",
            "borderLeft": f"4px solid {C_BLUE}", "borderRadius": "10px",
            "padding": "14px 18px", "marginBottom": "20px",
        }),

        html.Div([
            html.Div([
                html.Div([
                    html.Span("👤→🌿", style={"fontSize": "14px"}),
                    html.Span("Human → Environment", style={"fontSize": "11px", "fontWeight": "600", "color": C_BLUE, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P(f"Effluent TDS {effluent_tds} ppm | TNTC at lake entries | Open borewell breeding",
                       style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_BLUE}"}),
            html.Div([
                html.Div([
                    html.Span("🐾→🌿", style={"fontSize": "14px"}),
                    html.Span("Animal → Environment", style={"fontSize": "11px", "fontWeight": "600", "color": C_GREEN, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P("Horse stable TNTC | Doxy residues in soil-water | E. coli from manure",
                       style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_GREEN}"}),
            html.Div([
                html.Div([
                    html.Span("🌿→👤", style={"fontSize": "14px"}),
                    html.Span("Environment → Human", style={"fontSize": "11px", "fontWeight": "600", "color": C_RED, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P(f"AQI {fmt_num(aqi_val)} + {humidity_val}% humidity | Contaminated lake water consumed | Monsoon vectors",
                       style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_RED}"}),
            html.Div([
                html.Div([
                    html.Span("🐾→👤", style={"fontSize": "14px"}),
                    html.Span("Animal → Human", style={"fontSize": "11px", "fontWeight": "600", "color": C_PURPLE, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P("Rabies post-ABC | Leptospirosis risk | AMR food-chain risk",
                       style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_PURPLE}"}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(4,1fr)", "gap": "12px", "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_zoo,  config={"displayModeBar": False}), "red"),
            chart_card(dcc.Graph(figure=fig_rain, config={"displayModeBar": False}), "green"),
        ]),
        grid2([
            chart_card(dcc.Graph(figure=fig_int,  config={"displayModeBar": False}), "amber"),
            chart_card(dcc.Graph(figure=fig_bub,  config={"displayModeBar": False}), "blue"),
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


if __name__ == "__main__":
    app.run(debug=True)