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
    "onehealth_kpi":         ("overview_id", "onehealth_kpi"),
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
    name_col = find_col(df, ["metric", "name", "kpi"])
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


def load_all():
    d = {}
    for t in TABS.keys():
        try:
            d[t] = fetch(t)
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
# NEW DESIGN SYSTEM — from OneHealth_Dashboard2.html
# ══════════════════════════════════════════════════════════════════════════════

# Core palette (light, clean, professional)
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

# Plotly theme helper — crisp light background
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


def hero_box(title, body, chips=None):
    return html.Div([
        html.H2(title, style={
            "fontFamily": "'Playfair Display',serif",
            "fontSize": "24px", "margin": "0 0 8px", "color": TEXT,
        }),
        html.P(body, style={"fontSize": "13px", "color": MUTED, "lineHeight": "1.7", "textAlign": "justify"}),
        html.Div(chips or [], style={"display": "flex", "gap": "12px", "marginTop": "20px", "flexWrap": "wrap"}),
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
    return html.Div([
        html.Div([
            html.Span(label, style={"color": TEXT, "fontWeight": "600", "fontSize": "12px"}),
            html.Span(sub_label, style={"color": MUTED, "fontFamily": "'DM Mono',monospace", "fontSize": "11px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "5px"}),
        html.Div(
            html.Div(style={"width": f"{pct}%", "height": "100%", "borderRadius": "4px",
                            "background": color_map.get(color, color_map["blue"]), "transition": "width 1s ease"}),
            style={"height": "6px", "background": "rgba(0,0,0,0.08)", "borderRadius": "4px", "overflow": "hidden"}
        ),
    ], style={"marginBottom": "14px"})


def data_table_wrap(header_cols, rows):
    """header_cols: list of (label, flex), rows: list of list of (content, flex)"""
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
    rm = d.get("riskMatrix", pd.DataFrame())
    proj = d.get("projectedOutcome", pd.DataFrame())
    cp = d.get("crossPillarIndex", pd.DataFrame())
    oh_kpi = d.get("onehealth_kpi", pd.DataFrame())

    overview_kpis = {
        "Village Population": lookup_kpi_value(oh_kpi, ["Village Population", "Population"], "5,500"),
        "PHC Services": lookup_kpi_value(oh_kpi, ["PHC Services", "PHC Service"], "8"),
        "Stray Dogs in ABC": lookup_kpi_value(oh_kpi, ["Stray Dogs in ABC", "ABC Program", "ABC"], "550"),
        "Water Sources Tested": lookup_kpi_value(oh_kpi, ["Water Sources Tested"], "10"),
        "Top Risk Score": lookup_kpi_value(oh_kpi, ["Top Risk Score", "Top Risk"], "95"),
    }

    # Radar — multi-factor risk
    factor_col = find_col(rm, ["factor"])
    radar_cols = [
        (find_col(rm, ["likelihood"]), C_BLUE, "Likelihood"),
        (find_col(rm, ["impact"]), C_RED, "Impact"),
        (find_col(rm, ["urgency"]), C_AMBER, "Urgency"),
    ]
    fig_risk = empty_fig("No risk matrix data available")
    if factor_col and any(col for col, _, _ in radar_cols):
        rm_plot = coerce_numeric(rm, [col for col, _, _ in radar_cols if col])
        rm_plot = rm_plot[rm_plot[factor_col].notna()].copy()
        fig_risk = go.Figure()
        for col, color, name in radar_cols:
            if not col:
                continue
            valid = rm_plot[[factor_col, col]].dropna()
            if valid.empty:
                continue
            vals = valid[col].tolist() + [valid[col].iloc[0]]
            cats = valid[factor_col].astype(str).tolist() + [str(valid[factor_col].iloc[0])]
            fig_risk.add_trace(go.Scatterpolar(
                r=vals, theta=cats, name=name, fill="toself",
                line=dict(color=color, width=2), fillcolor=rgba(color, 0.08),
            ))
        if not fig_risk.data:
            fig_risk = empty_fig("No risk matrix data available")
    fig_risk.update_layout(
        **PLna("Multi-Factor Risk Radar"),
        polar=dict(
            bgcolor="#ffffff",
            radialaxis=dict(range=[0, 100], gridcolor="rgba(0,0,0,0.08)",
                            tickfont_color=MUTED, tickfont_size=9, linecolor=BORDER),
            angularaxis=dict(gridcolor="rgba(0,0,0,0.08)", tickfont_color=TEXT, linecolor=BORDER),
        ),
    )

    # Projected outcome
    year_col = find_col(proj, ["year"])
    proj_cols = [
        (find_col(proj, ["noIntervention", "baseline"]), C_RED, "dot", "No Intervention"),
        (find_col(proj, ["partial", "partialOneHealth"]), C_AMBER, "dash", "Partial One Health"),
        (find_col(proj, ["fullOneHealth", "full"]), C_GREEN, "solid", "Full One Health"),
    ]
    fig_proj = empty_fig("No projected outcome data available")
    if year_col and any(col for col, _, _, _ in proj_cols):
        proj_plot = coerce_numeric(proj, [year_col] + [col for col, _, _, _ in proj_cols if col])
        fig_proj = go.Figure()
        for col, color, dash, name in proj_cols:
            if not col:
                continue
            valid = proj_plot[[year_col, col]].dropna()
            if valid.empty:
                continue
            fig_proj.add_trace(go.Scatter(
                x=valid[year_col], y=valid[col], name=name, mode="lines+markers",
                line=dict(color=color, width=2.5, dash=dash),
                marker=dict(size=7, color=color),
                fill="tozeroy" if name == "Full One Health" else "none",
                fillcolor=rgba(C_GREEN, 0.06),
            ))
        if not fig_proj.data:
            fig_proj = empty_fig("No projected outcome data available")
    fig_proj.update_layout(**PL("Projected Disease Burden 2025–2030",
                                 yaxis_title="Burden Index", xaxis_title="Year"))

    # Cross-pillar risk
    cp_factor_col = find_col(cp, ["factor", "category"])
    cp_value_col = find_col(cp, ["value", "score"])
    fig_cross = empty_fig("No cross-pillar risk data available")
    if cp_factor_col and cp_value_col:
        cp_plot = coerce_numeric(cp, [cp_value_col]).dropna(subset=[cp_factor_col, cp_value_col]).copy()
        if not cp_plot.empty:
            cp_s = cp_plot.sort_values(cp_value_col, ascending=True)
            bar_colors = [C_GREEN if v < 50 else (C_AMBER if v < 70 else C_RED) for v in cp_s[cp_value_col]]
            fig_cross = go.Figure()
            fig_cross.add_trace(go.Bar(
                x=cp_s[cp_value_col], y=cp_s[cp_factor_col], orientation="h",
                marker_color=bar_colors, marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Risk Score: %{x}<extra></extra>",
            ))
            fig_cross.add_vline(x=70, line_dash="dot", line_color=C_RED,
                                line_width=1.5, annotation_text="High risk",
                                annotation_font=dict(color=C_RED, size=10))
    fig_cross.update_layout(**PL("Cross-Pillar Risk Index", xaxis_title="Risk Score"))

    return html.Div([
        hero_box(
            "One Health Dashboard",
            "A science-driven, integrated data platform assessing the health of humans, animals, and the "
            "environment at the village interface — built on the One Health framework by Planetary Health "
            "Foundation, an initiative of Equine Biotech, IISc.",
            chips=[
                pillar_chip("👤 Human Health",   C_BLUE),
                pillar_chip("🐾 Animal Health",  C_GREEN),
                pillar_chip("🌿 Environment",    C_RED),
            ]
        ),
        # 5 KPI cards
        html.Div([
            kpi_card("Village Population",   overview_kpis["Village Population"],   "",          "Bettahalasuru, Karnataka",    "blue"),
            kpi_card("PHC Services",         overview_kpis["PHC Services"],         "programs",  "Screening + treatment",       "green"),
            kpi_card("Stray Dogs in ABC",    overview_kpis["Stray Dogs in ABC"],    "animals",   "Mar 2024 programme",          "amber"),
            kpi_card("Water Sources Tested", overview_kpis["Water Sources Tested"], "locations", "Village + lake combined",     "red"),
            kpi_card("Top Risk Score",       overview_kpis["Top Risk Score"],       "urgency",   "Water contamination",         "red"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_risk, config={"displayModeBar": False}), "blue"),
            chart_card(dcc.Graph(figure=fig_proj, config={"displayModeBar": False}), "green"),
        ]),

        html.Div([
            chart_card(dcc.Graph(figure=fig_cross, config={"displayModeBar": False}), "amber", span=2),
            html.Div([
                html.P("Key Findings", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px", "fontWeight": "700",
                    "color": MUTED, "letterSpacing": "2px", "textTransform": "uppercase", "margin": "0 0 12px",
                }),
                insight_row("Water contamination is the top urgency risk (95/100). Household effluent TDS at 1,420 ppm — 3× the safe limit.", C_BLUE),
                insight_row("Dengue spiked to 60 cases in 2022 following high rainfall (index 95). Rainfall strongly predicts vector disease burden.", C_RED),
                insight_row("ABC + Vaccination is the only scenario that prevents exponential rabies spread. ABC alone slows but cannot stop it.", C_AMBER),
                insight_row("Full One Health intervention could reduce disease burden 80% by 2030 vs doing nothing.", C_GREEN),
            ], style={**CARD_STYLE, "paddingTop": "16px"}),
        ], style={
            "display": "grid", "gridTemplateColumns": "2fr 1fr",
            "gap": "20px", "marginBottom": "24px",
        }),
    ])


def page_human(d):
    md = d.get("majorDiseases",        pd.DataFrame())
    vt = d.get("vectorDiseaseTrend",   pd.DataFrame())
    db = d.get("diseaseBurden",        pd.DataFrame())
    sc = d.get("phcScreeningPrograms", pd.DataFrame())
    vi = d.get("vectorInsights",       pd.DataFrame())

    # Disease case-load bar
    dis_col = find_col(md, ["disease"])
    case_col = find_col(md, ["cases", "value"])
    fig_dis = empty_fig("No disease case-load data available")
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

    # Vector disease trend
    year_col = find_col(vt, ["year"])
    fig_vec = empty_fig("No vector disease trend data available")
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

    # Disease burden severity
    fig_bur = go.Figure()
    if not db.empty and all(col in db.columns for col in ["value", "diseaseCategory"]):
        db_s = db.sort_values("value")
        bclrs = [C_GREEN if v < 45 else (C_AMBER if v < 65 else C_RED) for v in db_s["value"]]
        fig_bur.add_trace(go.Bar(
            x=db_s["value"], y=db_s["diseaseCategory"], orientation="h",
            marker_color=bclrs, marker_line_width=0,
        ))
    fig_bur.update_layout(**PL("Disease Burden Severity Index", xaxis_title="Severity Score"))

    # Screening program pie
    fig_sc = go.Figure()
    if not sc.empty and "status" in sc.columns:
        sc_c = sc["status"].value_counts().reset_index()
        sc_c.columns = ["status", "count"]
        fig_sc = px.pie(sc_c, names="status", values="count", hole=0.55,
                        color_discrete_sequence=[C_BLUE, C_AMBER, C_GREEN],
                        title="PHC Programs by Status")
        fig_sc.update_layout(**PLna())
        fig_sc.update_traces(textfont_color=TEXT)

    # Screening table rows
    badge_map_bg    = {"Active": "good", "Seasonal": "warn", "Periodic": "info"}
    screening_rows  = []
    if not sc.empty:
        for _, row in sc.iterrows():
            screening_rows.append([
                (row.get("screeningType", ""), 2),
                (row.get("frequency", ""),     1),
                (badge(row.get("status", ""), badge_map_bg.get(row.get("status", ""), "info")), 1),
            ])

    return html.Div([
        section_banner("Human Pillar", "PRIMARY HEALTH CENTRE · BETTAHALASURU"),

        # Vector disease highlight row
        html.Div([
            kpi_card("Total Population",  "3,573",  "",          "Bettahalasuru",            "blue"),
            kpi_card("PHC Services",      "8+",     "programs",  "Screening programs active","green"),
            kpi_card("Hypertension Cases","75",      "cases",    "Highest single disease",   "red"),
            kpi_card("Dengue Peak 2022",  "60",      "cases",    "Spike — stagnant water",   "amber"),
            kpi_card("Malaria Range",     "30–50",   "cases/yr", "Monsoon driven",           "purple"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        # Vector disease highlight cards
        html.Div([
            html.Div([
                html.Div(style={"height": "3px", "background": C_BLUE, "borderRadius": "0 0 0 0", "margin": "-14px -16px 12px"}),
                html.P("🦟 MALARIA", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P("30–50/yr", style={"fontSize": "20px", "fontWeight": "700", "color": C_BLUE, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P("Peak during monsoon. RDT used at PHC.", style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_BLUE}"}),
            html.Div([
                html.Div(style={"height": "3px", "background": C_RED, "borderRadius": "0", "margin": "-14px -16px 12px"}),
                html.P("🦟 DENGUE", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P("60 cases", style={"fontSize": "20px", "fontWeight": "700", "color": C_RED, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P("2022 spike — high rainfall, standing water.", style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_RED}"}),
            html.Div([
                html.Div(style={"height": "3px", "background": C_PURPLE, "borderRadius": "0", "margin": "-14px -16px 12px"}),
                html.P("🦟 CHIKUNGUNYA", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P("10–25/yr", style={"fontSize": "20px", "fontWeight": "700", "color": C_PURPLE, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P("Sporadic post-monsoon. Nets distributed.", style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_PURPLE}"}),
            html.Div([
                html.Div(style={"height": "3px", "background": C_AMBER, "borderRadius": "0", "margin": "-14px -16px 12px"}),
                html.P("🌧 RAINFALL LINK", style={"fontFamily": "'DM Mono',monospace", "fontSize": "10px", "color": MUTED, "fontWeight": "700", "margin": "0 0 2px"}),
                html.P("High corr.", style={"fontSize": "18px", "fontWeight": "700", "color": C_AMBER, "fontFamily": "'DM Mono',monospace", "margin": "0"}),
                html.P("↑ Rainfall → ↑ Vector breeding → ↑ Disease burden (2022 confirmed)", style={"fontSize": "10px", "color": MUTED, "margin": "2px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_AMBER}"}),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(4,1fr)", "gap": "12px", "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_dis, config={"displayModeBar": False}), "blue"),
            chart_card(dcc.Graph(figure=fig_vec, config={"displayModeBar": False}), "green"),
        ]),

        grid2([
            # Disease burden as progress bars
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                card_title("Disease Burden by Category"),
                progress_bar("Hypertension & CVD",     "Rising (age 40+)",             72, "red"),
                progress_bar("Diabetes (Type 2)",      "Growing — lifestyle factors",  65, "amber"),
                progress_bar("Tuberculosis",            "Endemic — lower SES groups",   45, "red"),
                progress_bar("Anemia (women & children)","Nutritional deficiency",      55, "purple"),
                progress_bar("Malaria (seasonal)",     "30–50 cases/yr",               35, "blue"),
                progress_bar("Dengue",                 "60 cases (2022 spike)",         48, "red"),
                progress_bar("Leptospirosis",          "15 cases (2021)",               18, "green"),
            ], style=CARD_STYLE),

            # Screening programs table
            html.Div([
                card_top_bar(C_PURPLE),
                html.Div(style={"height": "6px"}),
                card_title("PHC Screening Programs"),
                data_table_wrap(
                    [("Screening Type", 2), ("Frequency", 1), ("Status", 1)],
                    screening_rows if screening_rows else [
                        (("Blood Pressure Monitoring", 2), ("Weekly", 1), (badge("Active", "good"), 1)),
                        (("Blood Sugar Testing", 2),       ("Weekly", 1), (badge("Active", "good"), 1)),
                        (("Antenatal Care", 2),            ("Weekly", 1), (badge("Active", "good"), 1)),
                        (("TB Sputum / Chest X-Ray", 2),   ("Symptomatic", 1), (badge("Active", "good"), 1)),
                        (("Malaria & Dengue RDT", 2),      ("Peak seasons", 1), (badge("Seasonal", "warn"), 1)),
                        (("HIV Testing", 2),               ("On request", 1), (badge("Active", "good"), 1)),
                        (("Eye & Vision Screening", 2),    ("Health camps", 1), (badge("Periodic", "info"), 1)),
                        (("Anemia (Hemoglobin)", 2),       ("Weekly", 1), (badge("Active", "good"), 1)),
                    ]
                ),
            ], style=CARD_STYLE),
        ]),

        # Vector insights
        html.Div([
            insight_card_row
            for insight_card_row in [
                insight_row(f"{r.get('disease','')}: {r.get('casesRange','')} cases — {r.get('insight','')}", [C_BLUE, C_RED, C_AMBER][i % 3])
                for i, (_, r) in enumerate(vi.iterrows())
            ]
        ]) if not vi.empty else html.Div(),
    ])


def page_animal(d):
    rp  = d.get("rabiesProjection", pd.DataFrame())
    abc = d.get("abcProgram",       pd.DataFrame())
    amr = d.get("amrFindings",      pd.DataFrame())
    ai  = d.get("animalInsights",   pd.DataFrame())

    # Rabies projection
    rp_year_col = find_col(rp, ["year"])
    fig_rab = empty_fig("No rabies projection data available")
    if rp_year_col:
        rp_plot = coerce_numeric(rp, [rp_year_col])
        fig_rab = go.Figure()
        for col, color, dash, name in [
            (find_col(rp, ["noAbc"]), C_RED, "dot", "No ABC"),
            (find_col(rp, ["withAbc"]), C_AMBER, "dash", "ABC Only"),
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

    # ABC programme bar
    abc_activity_col = find_col(abc, ["activity"])
    abc_count_col = find_col(abc, ["count", "value"])
    fig_abc = empty_fig("No ABC programme data available")
    if abc_activity_col and abc_count_col:
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
    abc_pl = {k: v for k, v in PL("ABC Programme — March 2024 (17 Dogs)").items() if k != "xaxis"}
    fig_abc.update_layout(**abc_pl, xaxis=dict(
        range=[0, 20], gridcolor="rgba(0,0,0,0.08)", linecolor=BORDER,
        tickfont_color=MUTED, title_text="Animals",
    ))

    # AMR residue chart
    amr_antibiotic_col = find_col(amr, ["antibiotic"])
    amr_sample_col = find_col(amr, ["sampleType", "sample_type"])
    amr_level_col = find_col(amr, ["levelFound", "level_found"])
    amr_limit_col = find_col(amr, ["permissible", "limit"])
    fig_amr = empty_fig("No AMR findings data available")
    if amr_antibiotic_col and amr_sample_col and amr_level_col and amr_limit_col:
        amr_v = coerce_numeric(amr, [amr_level_col, amr_limit_col])
        amr_v = amr_v.dropna(subset=[amr_antibiotic_col, amr_sample_col, amr_level_col, amr_limit_col]).copy()
        if not amr_v.empty:
            fig_amr = go.Figure()
            fig_amr.add_trace(go.Bar(
                x=amr_v[amr_antibiotic_col].astype(str) + " / " + amr_v[amr_sample_col].astype(str),
                y=amr_v[amr_level_col], name="Level Found", marker_color=C_BLUE,
                marker_line_width=0,
            ))
            fig_amr.add_trace(go.Scatter(
                x=amr_v[amr_antibiotic_col].astype(str) + " / " + amr_v[amr_sample_col].astype(str),
                y=amr_v[amr_limit_col], name="Permissible Limit", mode="markers",
                marker=dict(color=C_RED, size=14, symbol="line-ew",
                            line=dict(width=3, color=C_RED)),
            ))
    fig_amr.update_layout(**PL("AMR Residue vs Permissible Limits", yaxis_title="Concentration (mg/L)"))

    # Gauge — stray dogs
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=550,
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

    # ABC program static table
    abc_table_rows = [
        [("05-Mar-2024", 1.5), ("Dogs picked up from Bettahalasuru village", 3), (badge("17", "info"), 1)],
        [("06-Mar-2024", 1.5), ("Neutering completed + anti-rabies vaccination", 3), (badge("17", "good"), 1)],
        [("07–10-Mar-2024", 1.5), ("Post-operative care + antibiotic shots (4 days)", 3), (badge("All 17", "good"), 1)],
        [("11-Mar-2024", 1.5), ("Released at original pickup location", 3), (badge("17", "good"), 1)],
    ]

    return html.Div([
        section_banner("Animal Pillar", "STRAY DOG MANAGEMENT · LIVESTOCK AMR · POULTRY & PIGGERY · BETTAHALASURU"),

        html.Div([
            kpi_card("Stray Dogs",          "73+",    "",           "Village population",          "blue"),
            kpi_card("ABC Mar-2024",         "17+",    "animals",    "Neutered + anti-rabies shots","green"),
            kpi_card("Rabies Rate",          "↓13",   "%",          "Post-ABC cohort",             "red"),
            kpi_card("Livestock Monitored",  "700–1k", "animals",    "Via Vet Department",          "amber"),
            kpi_card("AMR Status",           "Safe",   "",           "Within permissible limits",   "green"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        grid2([
            chart_card(dcc.Graph(figure=fig_rab, config={"displayModeBar": False}), "red"),
            chart_card(dcc.Graph(figure=fig_abc, config={"displayModeBar": False}), "amber"),
        ]),

        grid2([
            # ABC detail table
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                card_title("Stray Dog ABC — Bettahalasuru (March 2024)"),
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
                        html.Strong("13%", style={"color": C_RED}),
                        " infection rate vs ",
                        html.Strong("9%", style={"color": C_GREEN}),
                        " in non-neutered — requiring a combined population control + vaccination strategy.",
                    ], style={"fontSize": "12px", "color": MUTED, "lineHeight": "1.7"}),
                ], style={"padding": "12px", "background": rgba(C_BLUE, 0.04), "borderRadius": "8px",
                          "borderLeft": f"3px solid {C_BLUE}"}),
            ], style=CARD_STYLE),

            # AMR chart
            chart_card(
                html.Div([
                    card_title("Livestock AMR Findings vs Permissible Limits"),
                    dcc.Graph(figure=fig_amr, config={"displayModeBar": False}),
                ]), "green"
            ),
        ]),

        grid2([
            chart_card(dcc.Graph(figure=fig_g, config={"displayModeBar": False}), "amber"),
            # AMR static table
            html.Div([
                card_top_bar(C_RED),
                html.Div(style={"height": "6px"}),
                card_title("Livestock AMR — Detailed Findings"),
                data_table_wrap(
                    [("Antibiotic", 1.2), ("Sample Type", 1.5), ("Level Found", 1.5), ("Permissible", 1.2), ("Status", 1)],
                    [
                        [("Doxycycline", 1.2), ("Pig Excreta", 1.5), ("0.000002 mg/g", 1.5), ("0.02 mg/g", 1.2), (badge("Safe", "good"), 1)],
                        [("Doxycycline", 1.2), ("Hen Excreta", 1.5), ("0.00348 mg/g", 1.5), ("0.02 mg/g", 1.2), (badge("Safe", "good"), 1)],
                        [("Amoxicillin", 1.2), ("Feed", 1.5),        ("None detected", 1.5), ("—", 1.2),         (badge("Clear", "good"), 1)],
                        [("Amoxicillin", 1.2), ("Excreta", 1.5),     ("None detected", 1.5), ("—", 1.2),         (badge("Clear", "good"), 1)],
                        [("Amoxicillin", 1.2), ("Water", 1.5),       ("None detected", 1.5), ("—", 1.2),         (badge("Clear", "good"), 1)],
                    ]
                ),
                html.Div(
                    "Detection method: HPLC analysis. Current antibiotic levels pose no immediate AMR risk, but ongoing monitoring is essential.",
                    style={"fontSize": "11px", "color": MUTED, "padding": "10px", "lineHeight": "1.6",
                           "background": rgba(C_GREEN, 0.05), "borderRadius": "6px", "borderLeft": f"3px solid {C_GREEN}"}
                ),
            ], style=CARD_STYLE),
        ]),

        html.Div([
            insight_row(row.get("insight", ""), [C_RED, C_AMBER, C_GREEN][i % 3])
            for i, (_, row) in enumerate(ai.iterrows())
        ]) if not ai.empty else html.Div(),
    ])


def page_environment(d):
    wq  = d.get("water_quality",    pd.DataFrame())
    vc  = d.get("villagewatercfu",  pd.DataFrame())
    lc  = d.get("lake_water_cfu",   pd.DataFrame())
    gt  = d.get("gram_staining_total", pd.DataFrame())
    mc  = d.get("microbial_analysis", pd.DataFrame())
    aq  = d.get("air_quality",      pd.DataFrame())
    sc  = d.get("soil_cfu",         pd.DataFrame())
    pv  = d.get("physiochem_village_waterquality", pd.DataFrame())

    # Water quality scatter
    wq_tds_col = find_col(wq, ["TDS_ppm", "TDS"])
    wq_do_col = find_col(wq, ["DO_mg_L", "DO"])
    wq_status_col = find_col(wq, ["drinking_status", "drinkingStatus"])
    wq_turbidity_col = find_col(wq, ["turbidity_NTU", "turbidity"])
    wq_source_col = find_col(wq, ["source_name", "sourceName", "source", "location"])
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
                title="Water Quality — TDS vs Dissolved Oxygen",
                labels={wq_tds_col: "TDS (ppm)", wq_do_col: "DO (mg/L)", wq_status_col: "Status"},
                hover_data=[c for c in [find_col(wq_plot, ["pH"]), find_col(wq_plot, ["EC_mS", "EC_uS"]), wq_turbidity_col] if c],
            )
            fig_wq.add_vline(x=500, line_dash="dot", line_color=C_BLUE, line_width=1.5,
                             annotation_text="TDS safe ≤500", annotation_font=dict(color=C_BLUE, size=10))
            fig_wq.add_hline(y=6, line_dash="dot", line_color=C_GREEN, line_width=1.5,
                             annotation_text="DO safe ≥6", annotation_font=dict(color=C_GREEN, size=10))
            fig_wq.update_layout(**PL())
    fig_wq.update_layout(**PL("Water Quality — TDS vs Dissolved Oxygen"))

    # Village water CFU
    vc_source_col = find_col(vc, ["source", "source_name", "sourceName", "sample", "location"])
    vc_mean_col = find_col(vc, ["mean_cfu", "CFU_avg", "CFU avg"])
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
    fig_vc.update_layout(**PL("Village Water — Mean CFU/mL", xaxis_title="CFU/mL"))

    # Lake water CFU
    lc_sample_col = find_col(lc, ["sample", "location", "source"])
    lc_mean_col = find_col(lc, ["mean_cfu", "CFU_avg", "CFU avg"])
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
    fig_lc.update_layout(**PL("Lake Entry Points — Mean CFU/mL", yaxis_title="CFU/mL"))
    fig_lc.update_xaxes(tickangle=-25)

    # Soil CFU
    sc_sample_col = find_col(sc, ["sample", "Sample", "site_name", "location"])
    sc_mean_col = find_col(sc, ["mean_cfu", "CFU avg", "CFU_avg"])
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
    fig_soil.update_layout(**PL("Soil CFU by Site", yaxis_title="CFU/mL"))

    # Gram staining pie
    gt_neg_col = find_col(gt, ["gram_negative_percent"])
    fig_gr = empty_fig("No gram staining data available")
    if gt_neg_col:
        g = gt.iloc[0]
        val = pd.to_numeric(g[gt_neg_col], errors="coerce")
        if pd.notna(val):
            fig_gr = go.Figure()
            fig_gr.add_trace(go.Pie(
                labels=["Gram Negative", "Gram Positive"],
                values=[val, 100 - val],
                hole=0.58,
                marker_colors=[C_RED, BORDER],
                textfont_color=TEXT,
            ))
    fig_gr.update_layout(**PLna("Gram Staining — 26 Isolates"))

    # AQI gauge
    aqi_val = 135
    aq_param_col = find_col(aq, ["parameter"])
    aq_value_col = find_col(aq, ["value"])
    if aq_param_col and aq_value_col:
        row = aq[aq[aq_param_col].astype(str).str.strip().str.upper() == "AQI"]
        if not row.empty:
            v = pd.to_numeric(row[aq_value_col].iloc[0], errors="coerce")
            if pd.notna(v):
                aqi_val = v

    fig_aqi = go.Figure(go.Indicator(
        mode="gauge+number", value=aqi_val,
        title={"text": "Air Quality Index (AQI)", "font": {"color": C_AMBER, "size": 13}},
        number={"font": {"color": C_AMBER, "size": 40}},
        gauge=dict(
            axis=dict(range=[0, 200], tickcolor=MUTED, tickfont_color=MUTED),
            bar=dict(color=C_AMBER, thickness=0.25),
            bgcolor="#ffffff", bordercolor=BORDER,
            steps=[
                dict(range=[0,   50], color="#d1fae5"),
                dict(range=[50, 100], color="#ecfccb"),
                dict(range=[100,150], color="#fef3c7"),
                dict(range=[150,200], color="#fee2e2"),
            ],
            threshold=dict(line=dict(color=C_RED, width=2.5), value=150),
        ),
    ))
    fig_aqi.update_layout(**PLgauge(), height=250, margin=dict(l=24, r=24, t=44, b=16))

    # Water quality summary table
    wq_table_rows = [
        [("S1", 0.5), ("Effluent Household", 2), ("7.52", 0.6), ("1990", 0.8), ("1420", 0.8), ("1.8", 0.6), ("10.46", 0.8), (badge("Unfit", "bad"), 1)],
        [("S2", 0.5), ("Borewell (Closed Tank)", 2), ("7.42", 0.6), ("1549", 0.8), ("1120", 0.8), ("6.55", 0.6), ("7.12", 0.8), (badge("Treat First", "warn"), 1)],
        [("S3", 0.5), ("Borewell (Open Tank)", 2), ("7.33", 0.6), ("1619", 0.8), ("1150", 0.8), ("6.17", 0.6), ("0.43", 0.8), (badge("Treat First", "warn"), 1)],
        [("S4", 0.5), ("Effluent (Common Drain)", 2), ("7.35", 0.6), ("1193", 0.8), ("912", 0.8), ("7.89", 0.6), ("3.56", 0.8), (badge("Unfit", "bad"), 1)],
        [("S5", 0.5), ("Right Lake", 2), ("7.73", 0.6), ("443", 0.8), ("312", 0.8), ("9.48", 0.6), ("2.99", 0.8), (badge("Borderline", "warn"), 1)],
        [("S6", 0.5), ("Bund Water", 2), ("7.55", 0.6), ("624", 0.8), ("305", 0.8), ("8.62", 0.6), ("1.30", 0.8), (badge("Agriculture", "info"), 1)],
        [("S7", 0.5), ("Left Lake", 2), ("8.41", 0.6), ("720", 0.8), ("288", 0.8), ("9.26", 0.6), ("2.08", 0.8), (badge("Borderline", "warn"), 1)],
        [("S8", 0.5), ("Central Lake", 2), ("7.72", 0.6), ("846", 0.8), ("297", 0.8), ("9.13", 0.6), ("1.42", 0.8), (badge("Borderline", "warn"), 1)],
        [("S9", 0.5), ("Poultry Farm BW", 2), ("6.61", 0.6), ("538", 0.8), ("378", 0.8), ("7.03", 0.6), ("0.32", 0.8), (badge("Treat First", "warn"), 1)],
        [("S10", 0.5), ("Piggery Water", 2), ("6.25", 0.6), ("112", 0.8), ("204", 0.8), ("8.91", 0.6), ("BDL", 0.8), (badge("Agriculture", "info"), 1)],
    ]

    # Microbial table
    mc_table_rows = []
    if not mc.empty:
        for _, row in mc.iterrows():
            status = row.get("microbial_status", "")
            mc_table_rows.append([
                (str(row.get("location", "")), 2),
                (str(row.get("na_plate_count", "")), 1),
                (str(row.get("emb_indicator", "")), 1.5),
                (badge(status, "bad" if status == "High" else "warn"), 1),
            ])

    return html.Div([
        section_banner("Environment Pillar", "WATER · MICROBIOLOGY · GRAM STAINING · SOIL · AIR QUALITY"),

        grid4([
            kpi_card("AQI Level",          "135",     "",      "Unhealthy for sensitive groups", "amber"),
            kpi_card("Humidity",           "37",      "%",     "Low — respiratory risk elevated","blue"),
            kpi_card("Effluent TDS",       "1,420",   "ppm",   "WHO limit: 500 ppm",             "red"),
            kpi_card("Gram –ve Isolates",  "100",     "%",     "All 26 isolates — water & soil", "purple"),
        ]),

        grid2([
            chart_card(dcc.Graph(figure=fig_wq,  config={"displayModeBar": False}), "blue"),
            chart_card(dcc.Graph(figure=fig_gr,  config={"displayModeBar": False}), "red"),
        ]),

        # Full water quality table
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

        grid2([
            # Microbial lake entry table
            html.Div([
                card_top_bar(C_RED),
                html.Div(style={"height": "6px"}),
                card_title("Microbial Analysis — Water Samples (Lake Entries)"),
                data_table_wrap(
                    [("Location", 2), ("NA Plate", 1), ("EMB Indicator", 1.5), ("Status", 1)],
                    mc_table_rows if mc_table_rows else [
                        [("Lake BH Entry 1", 2), ("Moderate (257 col)", 1), ("Enterobacter aerogenes", 1.5), (badge("Moderate", "warn"), 1)],
                        [("Lake BH Entry 2", 2), ("TNTC", 1),              ("Enterobacter aerogenes", 1.5), (badge("High", "bad"), 1)],
                        [("Lake BH Entry 3", 2), ("TNTC", 1),              ("Enterobacter aerogenes", 1.5), (badge("High", "bad"), 1)],
                        [("Lake BH 2", 2),        ("High (380 col)", 1),    ("Enterobacter aerogenes", 1.5), (badge("Moderate", "warn"), 1)],
                        [("Lake EF 1", 2),        ("TNTC", 1),              ("High coliform load", 1.5),     (badge("High", "bad"), 1)],
                        [("Lake BH 3", 2),        ("TNTC / 200", 1),        ("Mixed enteric flora", 1.5),    (badge("High", "bad"), 1)],
                    ]
                ),
                html.P("Media: NA, EMB, XLD | Incubation: 37°C, 24 hrs | Date: 22/01/2026",
                       style={"fontSize": "11px", "color": MUTED}),
            ], style=CARD_STYLE),

            # Gram staining summary
            html.Div([
                card_top_bar(C_GREEN),
                html.Div(style={"height": "6px"}),
                card_title("Gram Staining Summary — 26 Isolates"),
                progress_bar("Gram Negative (all isolates)", "26/26 = 100%", 100, "red"),
                progress_bar("Bacillus morphology",           "~65% of isolates", 65, "blue"),
                progress_bar("Cocci morphology",              "~35% of isolates", 35, "green"),
                progress_bar("Mucoid layer presence",         "~30% of isolates", 30, "purple"),
                html.Div([
                    html.P([
                        "All 26 tested isolates were ",
                        html.Strong("Gram-negative", style={"color": C_RED}),
                        ". Dominant types: rod-shaped (Bacillus) and spherical (Cocci). Mucoid layers in ~30% suggest capsule-forming, potentially pathogenic organisms.",
                    ], style={"fontSize": "12px", "color": MUTED, "lineHeight": "1.6", "margin": "0"}),
                ], style={"padding": "12px", "background": rgba(C_RED, 0.05), "borderRadius": "8px",
                          "borderLeft": f"3px solid {C_RED}"}),
            ], style=CARD_STYLE),
        ]),

        # Water sample field notes
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

    # Zoonotic transmission stacked
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
            (find_col(zoo, ["directContact"]), C_RED, "Direct Contact"),
            (find_col(zoo, ["environmental"]), C_GREEN, "Environmental"),
            (find_col(zoo, ["foodWater"]), C_AMBER, "Food / Water"),
            (find_col(zoo, ["vectorMediated"]), C_BLUE, "Vector Mediated"),
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

    # Rainfall vs disease
    rd_rain_col = find_col(rd, ["rainfallIndex"])
    rd_year_col = find_col(rd, ["year"])
    fig_rain = empty_fig("No rainfall-disease data available")
    if rd_rain_col:
        rd_plot = coerce_numeric(rd, [rd_rain_col, rd_year_col] if rd_year_col else [rd_rain_col])
        fig_rain = go.Figure()
        for col, c, name in [
            (find_col(rd, ["dengueCases"]), C_RED, "Dengue"),
            (find_col(rd, ["malariaCases"]), C_PURPLE, "Malaria"),
            (find_col(rd, ["leptospirosis"]), C_GREEN, "Leptospirosis"),
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

    # Interaction strength before/after
    ints_label_col = find_col(ints, ["interaction"])
    ints_current_col = find_col(ints, ["current"])
    ints_after_col = find_col(ints, ["afterIntervention", "after_intervention"])
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

    # Risk bubble chart
    rm_likelihood_col = find_col(rm, ["likelihood"])
    rm_impact_col = find_col(rm, ["impact"])
    rm_urgency_col = find_col(rm, ["urgency"])
    rm_factor_col = find_col(rm, ["factor"])
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
            kpi_card("Top Risk — Urgency",   "95",    "score", "Water contamination",          "red"),
            kpi_card("Rainfall Corr.",        "High",  "",      "Dengue spike 2022",            "amber"),
            kpi_card("Lepto Env Route",       "60",    "%",     "Environmental/soil dominant",  "green"),
            kpi_card("Rabies ABC+Vacc",       "86",    "%",     "Reduction vs no intervention", "blue"),
            kpi_card("Full OH 2030",          "−80",   "%",     "Burden vs doing nothing",      "green"),
        ], style={"display": "grid", "gridTemplateColumns": "repeat(5,1fr)", "gap": "12px", "marginBottom": "20px"}),

        # Context box
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

        # Pathway indicators
        html.Div([
            html.Div([
                html.Div([
                    html.Span("👤→🌿", style={"fontSize": "14px"}),
                    html.Span("Human → Environment", style={"fontSize": "11px", "fontWeight": "600", "color": C_BLUE, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P("Effluent TDS 1,420 ppm | TNTC at lake entries | Open borewell breeding", style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_BLUE}"}),
            html.Div([
                html.Div([
                    html.Span("🐾→🌿", style={"fontSize": "14px"}),
                    html.Span("Animal → Environment", style={"fontSize": "11px", "fontWeight": "600", "color": C_GREEN, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P("Horse stable TNTC | Doxy residues in soil-water | E. coli from manure", style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_GREEN}"}),
            html.Div([
                html.Div([
                    html.Span("🌿→👤", style={"fontSize": "14px"}),
                    html.Span("Environment → Human", style={"fontSize": "11px", "fontWeight": "600", "color": C_RED, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P("AQI 135 + 37% humidity | Contaminated lake water consumed | Monsoon vectors", style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
            ], style={**CARD_STYLE, "borderLeft": f"3px solid {C_RED}"}),
            html.Div([
                html.Div([
                    html.Span("🐾→👤", style={"fontSize": "14px"}),
                    html.Span("Animal → Human", style={"fontSize": "11px", "fontWeight": "600", "color": C_PURPLE, "marginLeft": "6px"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.P("Rabies 13% post-ABC | Leptospirosis 15 cases | AMR food-chain risk", style={"fontSize": "10px", "color": MUTED, "margin": "4px 0 0"}),
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
            return html.Div("Error loading page")
    return wrapped


page_overview = page_guard(page_overview)
page_human = page_guard(page_human)
page_animal = page_guard(page_animal)
page_environment = page_guard(page_environment)
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

app.layout = html.Div([
    dcc.Interval(id="refresh-interval", interval=60 * 1000, n_intervals=0),
    dcc.Store(id="data-timestamp", data=""),

    # ── Header ──────────────────────────────────────────────────────────────
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
            html.Div(["Population ", html.Span("~3,573", style={"color": C_BLUE, "fontWeight": "600"})], style={
                "padding": "5px 12px", "borderRadius": "20px",
                "background": "rgba(0,0,0,0.06)", "border": f"1px solid {BORDER}",
                "fontSize": "11px", "fontFamily": "'DM Mono',monospace", "color": MUTED,
                "display": "flex", "alignItems": "center", "gap": "4px",
            }),
            html.Div(["AQI ", html.Span("135", style={"color": C_AMBER, "fontWeight": "600"})], style={
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

    # ── Navigation tabs ───────────────────────────────────────────────────
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

    # ── Page content ─────────────────────────────────────────────────────
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
    Output("data-timestamp", "data"),
    Output("last-update-display", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("manual-refresh-btn", "n_clicks"),
)
def refresh_data(n_intervals, n_clicks):
    global DATA
    DATA = load_all()
    ts = datetime.now().strftime("%d %b %Y %H:%M:%S")
    return ts, f"Updated: {ts}"


@app.callback(
    Output("page-content", "children"),
    Input("main-tabs", "value"),
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
