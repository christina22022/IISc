import dash
from dash import html, dcc, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
from datetime import datetime

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "One Health Dashboard — Bettahalasuru"

# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS CONFIG
# Replace each URL below with your own published CSV link from Google Sheets:
#   File → Share → Publish to web → choose sheet → CSV → Copy link
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={tab}"

SHEETS = {
    # ── PASTE YOUR SHEET IDs BELOW ──────────────────────────────────────────
    # Format: "sheet_id": "YOUR_GOOGLE_SHEET_ID_HERE"
    # To get: open Google Sheet → copy the long ID from the URL
    #   https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit
    "human_id":   "YOUR_HUMAN_SHEET_ID",
    "animal_id":  "YOUR_ANIMAL_SHEET_ID",
    "env_id":     "YOUR_ENV_SHEET_ID",
    "inter_id":   "YOUR_INTERCONNECT_SHEET_ID",
}

# Tab names must match exactly what you named the sheets in Google Sheets
TABS = {
    "phcSummary":                    ("human_id",  "phcSummary"),
    "majorDiseases":                 ("human_id",  "majorDiseases"),
    "diseaseBurden":                 ("human_id",  "diseaseBurden"),
    "vectorDiseaseTrend":            ("human_id",  "vectorDiseaseTrend"),
    "phcScreeningPrograms":          ("human_id",  "phcScreeningPrograms"),
    "vectorInsights":                ("human_id",  "vectorInsights"),
    "abcProgram":                    ("animal_id", "abcProgram"),
    "rabiesProjection":              ("animal_id", "rabiesProjection"),
    "amrFindings":                   ("animal_id", "amrFindings"),
    "animalInsights":                ("animal_id", "animalInsights"),
    "water_quality":                 ("env_id",    "water_quality"),
    "villagewatercfu":               ("env_id",    "villagewatercfu"),
    "lake_water_cfu":                ("env_id",    "lake_water_cfu"),
    "gram_staining_total":           ("env_id",    "gram_staining_total"),
    "microbial_analysis":            ("env_id",    "microbial_analysis"),
    "air_quality":                   ("env_id",    "air_quality"),
    "soil_cfu":                      ("env_id",    "soil_cfu"),
    "physiochem_village_waterquality":("env_id",   "physiochem_village_waterquality"),
    "riskMatrix":                    ("inter_id",  "riskMatrix"),
    "zoonoticTransmission":          ("inter_id",  "zoonoticTransmission"),
    "rainfallDisease":               ("inter_id",  "rainfallDisease"),
    "crossPillarIndex":              ("inter_id",  "crossPillarIndex"),
    "interactionStrength":           ("inter_id",  "interactionStrength"),
    "projectedOutcome":              ("inter_id",  "projectedOutcome"),
}

# ── Fallback: local Excel (used when Google Sheets IDs not yet configured) ─────
BASE  = os.path.dirname(os.path.abspath(__file__))
DDIR  = os.path.join(BASE, "data")
LOCAL = {
    "human_id":  os.path.join(DDIR, "human.xlsx"),
    "animal_id": os.path.join(DDIR, "animal.xlsx"),
    "env_id":    os.path.join(DDIR, "Environment.xlsx"),
    "inter_id":  os.path.join(DDIR, "interconnectedness.xlsx"),
}

def fetch(tab_name):
    """Fetch a sheet — tries Google Sheets first, falls back to local Excel."""
    sid_key, tab = TABS[tab_name]
    sheet_id = SHEETS[sid_key]

    # If user has configured Google Sheets ID, try it
    if not sheet_id.startswith("YOUR_"):
        try:
            url = BASE_URL.format(sheet_id=sheet_id, tab=tab)
            df  = pd.read_csv(url)
            return df
        except Exception as e:
            print(f"[WARN] Google Sheets fetch failed for {tab_name}: {e}. Falling back to local.")

    # Fallback to local Excel
    local_path = LOCAL[sid_key]
    return pd.read_excel(local_path, sheet_name=tab)

def load_all():
    """Load and preprocess all sheets. Returns a dict of DataFrames."""
    d = {}
    tabs = list(TABS.keys())
    for t in tabs:
        try:
            d[t] = fetch(t)
        except Exception as e:
            print(f"[ERROR] Could not load {t}: {e}")
            d[t] = pd.DataFrame()

    # Preprocess CFU columns
    for key, cols in [
        ("villagewatercfu",  ["source","rep1","rep2","rep3"]),
        ("lake_water_cfu",   ["sample","rep1","rep2","rep3"]),
        ("soil_cfu",         ["sample","rep1","rep2","rep3"]),
    ]:
        if not d[key].empty:
            d[key].columns = cols
            d[key]["mean_cfu"] = d[key][["rep1","rep2","rep3"]].mean(axis=1).round(3)

    return d

# Initial load at startup
DATA = load_all()

# ══════════════════════════════════════════════════════════════════════════════
# COLOUR SYSTEM
# Inspired by: Turmeric & Indigo, Plum/Deep Wine, Sage & Pearl,
#              Terracotta & Warm White, Glacier Teal, Copper & Gold
# Each domain picks 2–3 of these palettes and mixes them as a gradient set
# ══════════════════════════════════════════════════════════════════════════════

# Base palettes
TURMERIC  = "#e8a020"   # warm golden yellow
INDIGO    = "#3730a3"   # deep stable blue
PLUM      = "#7e1f5a"   # deep wine / moody purple
DEEP_WINE = "#9b1c3e"
SAGE      = "#6b8f71"   # soft natural green
PEARL     = "#f5f0eb"   # off-white warm
TERRACOTTA= "#c0622a"   # earthy burnt orange
WARM_WHITE= "#fdf6f0"
GLACIER   = "#0891b2"   # fresh modern teal
COPPER    = "#b5651d"   # rich copper
GOLD      = "#c9920c"   # deep gold

# Light theme base
T = {
    "bg":      "#fafaf8",          # warm off-white — Pearl inspired
    "surface": "#ffffff",
    "card":    "#ffffff",
    "border":  "#e8e4dc",
    "border2": "#d4cfc4",
    "text":    "#1c1917",
    "muted":   "#78716c",
    "subtle":  "#f5f0eb",          # Pearl
    "grid":    "#f0ede8",
    "shadow":  "0 1px 4px rgba(0,0,0,0.08)",
}

# ── Per-domain colour sets (mismatch gradient — different palette families) ─────

# OVERVIEW — Turmeric + Indigo (warm meets cool)
OV = {
    "c1": INDIGO,       "c2": TURMERIC,     "c3": GLACIER,
    "c4": SAGE,         "c5": COPPER,       "danger": "#dc2626",
    "grad": [[0,"#e0e7ff"],[0.4,"#818cf8"],[0.7,INDIGO],[1,"#1e1b4b"]],
    "hbg": "#eef2ff",   "hborder": "#c7d2fe",
    "dbg": "#f0f5ff",   "dborder": "#c7d2fe",  "dleft": INDIGO,
    # mismatch gradient bar — indigo to turmeric
    "mg_start": "#c7d2fe", "mg_mid": INDIGO, "mg_end": TURMERIC,
}

# HUMAN — Plum/Deep Wine + Turmeric (moody depth + warm highlight)
HU = {
    "c1": PLUM,         "c2": DEEP_WINE,    "c3": TURMERIC,
    "c4": COPPER,       "c5": INDIGO,       "danger": "#dc2626",
    "grad": [[0,"#fce7f3"],[0.35,"#c084fc"],[0.65,PLUM],[1,"#4a0e35"]],
    "hbg": "#fdf2f8",   "hborder": "#f0abdc",
    "dbg": "#fef9fd",   "dborder": "#f0abdc",  "dleft": PLUM,
    # mismatch: plum → turmeric → deep wine
    "mg_start": "#fce7f3", "mg_mid": PLUM, "mg_end": TURMERIC,
}

# ANIMAL — Terracotta + Copper + Gold (earthy artisan)
AN = {
    "c1": TERRACOTTA,   "c2": COPPER,       "c3": GOLD,
    "c4": PLUM,         "c5": SAGE,         "danger": "#dc2626",
    "grad": [[0,"#fef3c7"],[0.35,GOLD],[0.65,COPPER],[1,TERRACOTTA]],
    "hbg": "#fff7ed",   "hborder": "#fed7aa",
    "dbg": "#fffbeb",   "dborder": "#fed7aa",  "dleft": TERRACOTTA,
    # mismatch: gold → copper → terracotta
    "mg_start": "#fde68a", "mg_mid": COPPER, "mg_end": TERRACOTTA,
}

# ENVIRONMENT — Sage + Glacier Teal + Pearl (nature + tech refresh)
EN = {
    "c1": SAGE,         "c2": GLACIER,      "c3": "#2dd4bf",
    "c4": GOLD,         "c5": PLUM,         "danger": "#dc2626",
    "grad": [[0,"#d1fae5"],[0.35,"#34d399"],[0.65,SAGE],[1,"#1a3a1f"]],
    "hbg": "#f0fdf4",   "hborder": "#bbf7d0",
    "dbg": "#f0fdfa",   "dborder": "#99f6e4",  "dleft": GLACIER,
    # mismatch: sage → glacier teal → gold
    "mg_start": "#d1fae5", "mg_mid": GLACIER, "mg_end": GOLD,
}

PALETTES = {
    "overview": OV, "human": HU, "animal": AN,
    "environment": EN, "interconnections": OV,
}

# ══════════════════════════════════════════════════════════════════════════════
# GRADIENT HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgba(hex_color, alpha):
    r, g, b = hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"

def gradient_css(c1, c2, c3=None):
    """CSS linear gradient string — used for header accent bars."""
    if c3:
        return f"linear-gradient(135deg,{c1},{c2},{c3})"
    return f"linear-gradient(135deg,{c1},{c2})"

def mismatch_scale(pal):
    """Plotly color_continuous_scale using a domain's mismatch gradient."""
    return [[0, pal["mg_start"]], [0.5, pal["mg_mid"]], [1, pal["mg_end"]]]

# ══════════════════════════════════════════════════════════════════════════════
# PLOT LAYOUT FACTORY
# ══════════════════════════════════════════════════════════════════════════════
def PL(pal, title="", **kw):
    base = dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="'Inter','Segoe UI',sans-serif", color=T["text"], size=12),
        margin=dict(l=16, r=16, t=48, b=16),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=T["border2"],
                    borderwidth=1, font_size=11),
        xaxis=dict(gridcolor=T["grid"], linecolor=T["border2"],
                   tickfont_color=T["muted"], title_font_color=T["muted"],
                   zerolinecolor=T["border2"]),
        yaxis=dict(gridcolor=T["grid"], linecolor=T["border2"],
                   tickfont_color=T["muted"], title_font_color=T["muted"],
                   zerolinecolor=T["border2"]),
        title=dict(text=title, font=dict(size=13, color=pal["c1"],
                   family="'Inter',sans-serif")),
        hoverlabel=dict(bgcolor=T["subtle"], bordercolor=T["border2"],
                        font=dict(color=T["text"], size=12)),
    )
    base.update(kw)
    return base

def PLna(pal, title="", **kw):
    return {k: v for k, v in PL(pal, title, **kw).items() if "axis" not in k}

def PLgauge(pal):
    return {k: v for k, v in PLna(pal).items() if k != "margin"}

# ══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════
def page_header(title, subtitle, pal):
    grad = gradient_css(pal["c1"], pal["c2"], pal.get("c3"))
    return html.Div([
        html.Div(style={
            "width":"6px","height":"58px","borderRadius":"4px",
            "background":grad,"marginRight":"18px","flexShrink":"0",
        }),
        html.Div([
            html.H2(title, style={
                "margin":"0","fontSize":"22px","fontWeight":"700",
                "background":grad,
                "WebkitBackgroundClip":"text",
                "WebkitTextFillColor":"transparent",
                "fontFamily":"'Inter',sans-serif","letterSpacing":"-0.3px",
            }),
            html.P(subtitle, style={"margin":"4px 0 0","fontSize":"13px",
                                     "color":T["muted"],"lineHeight":"1.5"}),
        ])
    ], style={
        "display":"flex","alignItems":"center","marginBottom":"22px",
        "background":pal["hbg"],"border":f"1px solid {pal['hborder']}",
        "borderRadius":"12px","padding":"16px 20px",
        "boxShadow":T["shadow"],
    })

def section_head(text, pal):
    grad = gradient_css(pal["c1"], pal["c2"])
    return html.Div([
        html.Div(style={
            "width":"100%","height":"2px","borderRadius":"2px",
            "background":grad,"marginBottom":"10px",
        }),
        html.P(text, style={
            "color":pal["c1"],"fontSize":"10px","fontWeight":"700",
            "letterSpacing":"2.5px","textTransform":"uppercase","margin":"0 0 12px",
        }),
    ])

def description_box(text, pal):
    return html.Div(text, style={
        "background":pal["dbg"],"border":f"1px solid {pal['dborder']}",
        "borderLeft":f"4px solid {pal['dleft']}","borderRadius":"8px",
        "padding":"14px 18px","fontSize":"13px","color":T["muted"],
        "lineHeight":"1.8","marginBottom":"22px",
    })

def kpi_card(label, value, unit, color1, color2, sub):
    grad = gradient_css(color1, color2)
    return html.Div([
        html.Div(style={"height":"4px","background":grad,
                        "borderRadius":"10px 10px 0 0","margin":"-16px -18px 14px"}),
        html.P(label, style={"margin":"0 0 6px","fontSize":"10px","fontWeight":"700",
                              "letterSpacing":"2px","textTransform":"uppercase",
                              "color":T["muted"]}),
        html.Div([
            html.Span(str(value), style={"fontSize":"26px","fontWeight":"700",
                                          "color":color1,"lineHeight":"1",
                                          "background":grad,
                                          "WebkitBackgroundClip":"text",
                                          "WebkitTextFillColor":"transparent"}),
            html.Span(f" {unit}", style={"fontSize":"12px","color":T["muted"],"marginLeft":"4px"}),
        ]),
        html.P(sub, style={"margin":"6px 0 0","fontSize":"11px","color":T["muted"]}),
    ], style={
        "background":T["card"],"border":f"1px solid {T['border']}",
        "borderRadius":"10px","padding":"16px 18px","flex":"1","minWidth":"150px",
        "boxShadow":T["shadow"],
    })

def kpi_row(children):
    return html.Div(children, style={"display":"flex","gap":"14px",
                                      "flexWrap":"wrap","marginBottom":"22px"})

def insight_card(text, c1, c2):
    return html.Div([
        html.Div(style={"width":"3px","background":gradient_css(c1,c2),
                        "borderRadius":"2px","marginRight":"12px",
                        "flexShrink":"0","alignSelf":"stretch"}),
        html.P(text, style={"margin":"0","fontSize":"12px",
                             "color":T["text"],"lineHeight":"1.65"}),
    ], style={
        "display":"flex","alignItems":"flex-start",
        "background":T["card"],"border":f"1px solid {T['border']}",
        "borderLeft":f"3px solid {c1}","borderRadius":"8px",
        "padding":"12px 14px","marginBottom":"8px","boxShadow":T["shadow"],
    })

def chart_box(child, span=1):
    return html.Div(child, style={
        "background":T["card"],"border":f"1px solid {T['border']}",
        "borderRadius":"10px","padding":"10px","gridColumn":f"span {span}",
        "boxShadow":T["shadow"],
    })

def grid2(children):
    return html.Div(children, style={
        "display":"grid","gridTemplateColumns":"repeat(2,minmax(0,1fr))",
        "gap":"16px","marginBottom":"20px",
    })

def grid3(children):
    return html.Div(children, style={
        "display":"grid","gridTemplateColumns":"repeat(3,minmax(0,1fr))",
        "gap":"16px","marginBottom":"20px",
    })

def status_pill(text, bg, color):
    return html.Span(text, style={
        "background":bg,"color":color,"fontSize":"10px","fontWeight":"700",
        "padding":"2px 10px","borderRadius":"20px",
    })

def table_head(cols):
    return html.Div([
        html.Div(c, style={"flex":str(f),"fontSize":"10px","fontWeight":"700",
                            "color":T["muted"],"letterSpacing":"1.5px",
                            "textTransform":"uppercase","padding":"0 8px"})
        for c, f in cols
    ], style={"display":"flex","padding":"10px 14px",
               "background":T["subtle"],"borderBottom":f"1px solid {T['border']}"})

def table_row(cells):
    return html.Div([
        html.Div(c, style={"flex":str(f),"fontSize":"12px","color":T["text"],"padding":"0 8px"})
        for c, f in cells
    ], style={"display":"flex","alignItems":"center","padding":"10px 14px",
               "borderBottom":f"1px solid {T['border']}"})

def table_wrap(children):
    return html.Div(children, style={
        "background":T["card"],"border":f"1px solid {T['border']}",
        "borderRadius":"10px","overflow":"hidden","marginBottom":"20px",
        "boxShadow":T["shadow"],
    })

def last_updated_badge(ts):
    return html.Div([
        html.Span("Last updated: ", style={"color":T["muted"],"fontSize":"11px"}),
        html.Span(ts, style={"color":SAGE,"fontSize":"11px","fontWeight":"600"}),
    ], style={"textAlign":"right","marginBottom":"16px"})

# ══════════════════════════════════════════════════════════════════════════════
# PAGE BUILDERS  (all receive live DATA dict)
# ══════════════════════════════════════════════════════════════════════════════
def page_overview(d):
    pal = OV
    rm  = d.get("riskMatrix", pd.DataFrame())
    proj = d.get("projectedOutcome", pd.DataFrame())
    cp   = d.get("crossPillarIndex", pd.DataFrame())

    # Risk radar — each pillar colour
    fig_risk = go.Figure()
    if not rm.empty:
        for col, c1, c2, name in [
            ("likelihood", HU["c1"], HU["c2"], "Likelihood"),
            ("impact",     AN["c1"], AN["c2"], "Impact"),
            ("urgency",    EN["c1"], EN["c2"], "Urgency"),
        ]:
            vals = rm[col].tolist() + [rm[col].iloc[0]]
            cats = rm["factor"].tolist() + [rm["factor"].iloc[0]]
            fig_risk.add_trace(go.Scatterpolar(
                r=vals, theta=cats, name=name, fill="toself",
                line=dict(color=c1, width=2.2),
                fillcolor=rgba(c1, 0.08),
            ))
    fig_risk.update_layout(
        **PLna(pal, "Multi-Factor Risk Radar"),
        polar=dict(
            bgcolor="#ffffff",
            radialaxis=dict(range=[0,100], gridcolor=T["grid"],
                            tickfont_color=T["muted"], tickfont_size=9,
                            linecolor=T["border2"]),
            angularaxis=dict(gridcolor=T["grid"], tickfont_color=T["text"],
                             linecolor=T["border2"]),
        ),
    )

    # Projected outcomes — mismatch colours
    fig_proj = go.Figure()
    if not proj.empty:
        pcfg = [
            ("noIntervention", "#dc2626", "dot",   "No Intervention"),
            ("partial",         TURMERIC,  "dash",  "Partial One Health"),
            ("fullOneHealth",   SAGE,      "solid", "Full One Health"),
        ]
        for col, color, dash, name in pcfg:
            if col in proj.columns:
                fig_proj.add_trace(go.Scatter(
                    x=proj["year"], y=proj[col], name=name,
                    mode="lines+markers",
                    line=dict(color=color, width=2.5, dash=dash),
                    marker=dict(size=7, color=color),
                    fill="tozeroy" if col=="fullOneHealth" else "none",
                    fillcolor=rgba(SAGE, 0.06),
                ))
    fig_proj.update_layout(**PL(pal, "Projected Disease Burden 2025–2030",
                                  yaxis_title="Burden Index", xaxis_title="Year"))

    # Cross pillar — colour by risk level using mismatch
    fig_cross = go.Figure()
    if not cp.empty:
        cp_s = cp.sort_values("value", ascending=True).copy()
        bar_colors = [
            SAGE if v < 50 else (TURMERIC if v < 70 else TERRACOTTA)
            for v in cp_s["value"]
        ]
        fig_cross.add_trace(go.Bar(
            x=cp_s["value"], y=cp_s["factor"], orientation="h",
            marker_color=bar_colors, marker_line_width=0,
            hovertemplate="<b>%{y}</b><br>Risk Score: %{x}<extra></extra>",
        ))
        fig_cross.add_vline(x=70, line_dash="dot", line_color=DEEP_WINE,
                            line_width=1.5, annotation_text="High risk",
                            annotation_font=dict(color=DEEP_WINE, size=10))
    fig_cross.update_layout(**PL(pal, "Cross-Pillar Risk Index",
                                   xaxis_title="Risk Score"))

    return html.Div([
        page_header("One Health Overview — Bettahalasuru Village",
                    "Integrated study of Human, Animal & Environmental health — rural Karnataka (Population 5,500)", pal),
        description_box(
            "This dashboard presents a comprehensive One Health assessment of Bettahalasuru village. "
            "Navigate through the five tabs to explore each pillar in depth. "
            "Water contamination scores highest on urgency (95/100). "
            "A full One Health intervention could reduce the disease burden 80% by 2030 compared to inaction.", pal),

        section_head("Study Summary", pal),
        kpi_row([
            kpi_card("Village Population",   "5,500", "residents",      INDIGO,     TURMERIC,    "Bettahalasuru, Karnataka"),
            kpi_card("PHC Services",         "8",     "active programs", HU["c1"],  HU["c3"],    "Screening + treatment"),
            kpi_card("Stray Dogs in ABC",    "550",   "animals",         AN["c1"],  AN["c2"],    "Mar 2024 programme"),
            kpi_card("Water Sources Tested", "10",    "locations",       EN["c1"],  EN["c2"],    "Village + lake combined"),
            kpi_card("Top Risk Score",       "95",    "urgency",         DEEP_WINE, TERRACOTTA,  "Water contamination"),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_risk,  config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_proj,  config={"displayModeBar":False})),
        ]),
        grid3([
            chart_box(dcc.Graph(figure=fig_cross, config={"displayModeBar":False}), span=2),
            html.Div([
                section_head("Key Findings", pal),
                insight_card("Water contamination is the top urgency risk (95/100). Household effluent TDS at 1,420 ppm — 3× the safe limit.", INDIGO, TURMERIC),
                insight_card("Dengue spiked to 60 cases in 2022 following high rainfall (index 95). Rainfall strongly predicts vector disease burden.", PLUM, DEEP_WINE),
                insight_card("ABC + Vaccination is the only scenario that prevents exponential rabies spread. ABC alone slows but cannot stop it.", TERRACOTTA, COPPER),
                insight_card("Full One Health intervention could reduce disease burden 80% by 2030 vs doing nothing.", SAGE, GLACIER),
            ], style={"background":T["card"],"border":f"1px solid {T['border']}",
                      "borderRadius":"10px","padding":"18px","boxShadow":T["shadow"]}),
        ]),
    ])


def page_human(d):
    pal = HU
    md  = d.get("majorDiseases",    pd.DataFrame())
    vt  = d.get("vectorDiseaseTrend", pd.DataFrame())
    db  = d.get("diseaseBurden",    pd.DataFrame())
    sc  = d.get("phcScreeningPrograms", pd.DataFrame())
    vi  = d.get("vectorInsights",   pd.DataFrame())

    # Disease bar — plum → turmeric gradient
    fig_dis = go.Figure()
    if not md.empty:
        md_s = md.sort_values("cases", ascending=True)
        n    = len(md_s)
        colors = [gradient_css(PLUM, TURMERIC)] * n  # individual bars coloured by intensity
        bar_clr = [PLUM if i < n//3 else (DEEP_WINE if i < 2*n//3 else TURMERIC) for i in range(n)]
        fig_dis = go.Figure(go.Bar(
            x=md_s["cases"], y=md_s["disease"], orientation="h",
            marker_color=bar_clr, marker_line_width=0,
            hovertemplate="<b>%{y}</b><br>Cases: %{x}<extra></extra>",
        ))
    fig_dis.update_layout(**PL(pal, "Disease Case Load — PHC Bettahalasuru",
                                 xaxis_title="Cases Reported"))

    # Vector trend — plum, deep wine, copper, turmeric
    fig_vec = go.Figure()
    if not vt.empty:
        vcfg = [("malaria","solid",PLUM), ("dengue","solid",DEEP_WINE),
                ("chikungunya","dash",TURMERIC), ("leptospirosis","dot",COPPER)]
        for col, dash, color in vcfg:
            if col in vt.columns:
                fig_vec.add_trace(go.Scatter(
                    x=vt["year"], y=vt[col], name=col.capitalize(),
                    mode="lines+markers",
                    line=dict(color=color, width=2.2, dash=dash),
                    marker=dict(size=7, color=color),
                ))
    fig_vec.update_layout(**PL(pal, "Vector-Borne Disease Trend 2020–2024",
                                 yaxis_title="Cases", xaxis_title="Year"))

    # Burden — sage to plum (low→high)
    fig_bur = go.Figure()
    if not db.empty:
        db_s = db.sort_values("value")
        bclr = [SAGE if v<45 else (TURMERIC if v<65 else PLUM) for v in db_s["value"]]
        fig_bur.add_trace(go.Bar(
            x=db_s["value"], y=db_s["diseaseCategory"], orientation="h",
            marker_color=bclr, marker_line_width=0,
            hovertemplate="<b>%{y}</b><br>Severity: %{x}<extra></extra>",
        ))
    fig_bur.update_layout(**PL(pal, "Disease Burden Severity Index",
                                 xaxis_title="Severity Score"))

    # Screening status donut — plum, turmeric, copper
    fig_sc = go.Figure()
    if not sc.empty:
        sc_c = sc["status"].value_counts().reset_index()
        sc_c.columns = ["status","count"]
        fig_sc = px.pie(sc_c, names="status", values="count", hole=0.55,
                        color_discrete_sequence=[PLUM, TURMERIC, COPPER],
                        title="PHC Programs by Status")
        fig_sc.update_layout(**PLna(pal))
        fig_sc.update_traces(textfont_color=T["text"])

    return html.Div([
        page_header("Human Health Pillar",
                    "Primary Health Centre data — Bettahalasuru village, Population 5,500", pal),
        description_box(
            "The PHC serves 5,500 residents with 8 active health programs. Hypertension (75 cases) and "
            "Diabetes (65 cases) are rising due to lifestyle changes. Vector-borne diseases peak in monsoon — "
            "dengue spiked to 60 cases in 2022 due to above-average rainfall and stagnant water near the lake. "
            "Malaria remains endemic at 30–50 cases per season.", pal),
        section_head("PHC Key Indicators", pal),
        kpi_row([
            kpi_card("Total Population",    "5,500",  "",          PLUM,      INDIGO,     "Bettahalasuru"),
            kpi_card("Hypertension Cases",  "75",     "cases",     DEEP_WINE, PLUM,       "Highest single disease"),
            kpi_card("Dengue Peak 2022",    "60",     "cases",     TURMERIC,  DEEP_WINE,  "Spike — stagnant water"),
            kpi_card("Malaria Range",       "30–50",  "cases/yr",  COPPER,    TURMERIC,   "Monsoon driven"),
            kpi_card("Active Programs",     "8",      "services",  INDIGO,    PLUM,       "Weekly + seasonal"),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_dis, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_vec, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_bur, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_sc,  config={"displayModeBar":False})),
        ]),
        section_head("Vector Disease Insights", pal),
        html.Div([
            insight_card(f"{r['disease']}: {r['casesRange']} cases — {r['insight']}",
                         [PLUM, DEEP_WINE, TURMERIC][i % 3],
                         [TURMERIC, COPPER, PLUM][i % 3])
            for i, (_, r) in enumerate(vi.iterrows())
        ]) if not vi.empty else html.Div(),
        section_head("PHC Screening Programs", pal),
        table_wrap([
            table_head([("Screening Type",2),("Frequency",1),("Status",1)]),
            *[table_row([
                (row["screeningType"],2),(row["frequency"],1),
                (status_pill(row["status"],
                    {"Active":"#f5f0ff","Seasonal":"#fef3c7","Periodic":"#e6f7ee"}.get(row["status"],"#f5f5f5"),
                    {"Active":PLUM,"Seasonal":TURMERIC,"Periodic":SAGE}.get(row["status"],T["muted"])), 1),
            ]) for _, row in sc.iterrows()]
        ]) if not sc.empty else html.Div(),
    ])


def page_animal(d):
    pal = AN
    rp  = d.get("rabiesProjection", pd.DataFrame())
    abc = d.get("abcProgram",       pd.DataFrame())
    amr = d.get("amrFindings",      pd.DataFrame())
    ai  = d.get("animalInsights",   pd.DataFrame())

    # Rabies projection — red, terracotta, sage
    fig_rab = go.Figure()
    if not rp.empty:
        rcfg = [
            ("noAbc",             "#dc2626", "dot",   "No ABC"),
            ("withAbc",           TERRACOTTA,"dash",  "ABC Only"),
            ("withAbcVaccination",SAGE,      "solid", "ABC + Vaccination"),
        ]
        for col, color, dash, name in rcfg:
            if col in rp.columns:
                fig_rab.add_trace(go.Scatter(
                    x=rp["year"], y=rp[col], name=name, mode="lines+markers",
                    line=dict(color=color, width=2.5, dash=dash),
                    marker=dict(size=7, color=color),
                    fill="tozeroy" if col=="noAbc" else "none",
                    fillcolor=rgba("#dc2626", 0.05),
                ))
    fig_rab.update_layout(**PL(pal, "Rabies Projection — 5-Year Model",
                                 yaxis_title="Infected Animals", xaxis_title="Year"))

    # ABC steps — terracotta to gold gradient per step
    fig_abc = go.Figure()
    if not abc.empty:
        step_cols = [TERRACOTTA, COPPER, GOLD, COPPER, COPPER, COPPER, SAGE]
        for i, (_, row) in enumerate(abc.iterrows()):
            fig_abc.add_trace(go.Bar(
                x=[row["count"]], y=[row["activity"]], orientation="h",
                marker_color=step_cols[min(i, len(step_cols)-1)],
                showlegend=False,
                hovertemplate=f"<b>{row['activity']}</b><br>Animals: {row['count']}<extra></extra>",
            ))
    abc_pl = {k:v for k,v in PL(pal,"ABC Programme — March 2024 (17 Dogs)").items() if k!="xaxis"}
    fig_abc.update_layout(**abc_pl, xaxis=dict(
        range=[0,20], gridcolor=T["grid"], linecolor=T["border2"],
        tickfont_color=T["muted"], title_text="Animals",
    ))

    # AMR — copper bars, red danger line
    fig_amr = go.Figure()
    if not amr.empty:
        amr_v = amr[amr["permissible"].notna()].copy()
        if not amr_v.empty:
            fig_amr.add_trace(go.Bar(
                x=amr_v["antibiotic"] + " / " + amr_v["sampleType"],
                y=amr_v["levelFound"], name="Level Found",
                marker_color=COPPER,
            ))
            fig_amr.add_trace(go.Scatter(
                x=amr_v["antibiotic"] + " / " + amr_v["sampleType"],
                y=amr_v["permissible"], name="Permissible Limit",
                mode="markers", marker=dict(
                    color="#dc2626", size=14, symbol="line-ew",
                    line=dict(width=3, color="#dc2626")),
            ))
    fig_amr.update_layout(**PL(pal, "AMR Residue vs Permissible Limits",
                                 yaxis_title="Concentration (mg/L)"))

    # Gauge — terracotta→copper→gold steps
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=550,
        title={"text":"Stray Dogs in Programme","font":{"color":TERRACOTTA,"size":13}},
        number={"font":{"color":TERRACOTTA,"size":42}},
        gauge=dict(
            axis=dict(range=[0,800], tickcolor=T["muted"], tickfont_color=T["muted"]),
            bar=dict(color=TERRACOTTA, thickness=0.28),
            bgcolor="#ffffff", bordercolor=T["border2"],
            steps=[
                dict(range=[0,200],  color="#fff7ed"),
                dict(range=[200,400],color="#fed7aa"),
                dict(range=[400,600],color="#fbbf24"),
                dict(range=[600,800],color="#fca5a5"),
            ],
            threshold=dict(line=dict(color="#dc2626",width=2.5), value=700),
        ),
    ))
    fig_g.update_layout(**PLgauge(pal), height=250, margin=dict(l=24,r=24,t=44,b=16))

    return html.Div([
        page_header("Animal Health Pillar",
                    "Stray dog management (ABC), rabies surveillance, livestock & antimicrobial resistance", pal),
        description_box(
            "The ABC programme managed 550 stray dogs and cats in Bettahalasuru. In March 2024, 17 dogs "
            "were neutered and vaccinated over 7 days. The rabies model shows that only ABC + Vaccination "
            "prevents exponential spread — ABC alone reduces growth but cannot halt it. "
            "AMR screening found doxycycline levels well within permissible limits — no immediate AMR risk detected.", pal),
        section_head("Animal Health Key Indicators", pal),
        kpi_row([
            kpi_card("Dogs in Programme",  "550",    "animals",  TERRACOTTA, COPPER,    "Dogs & cats managed"),
            kpi_card("ABC Batch Mar 2024", "17",     "animals",  GOLD,       TURMERIC,  "Neutered + vaccinated"),
            kpi_card("Rabies Rate",        "13",     "%",        DEEP_WINE,  PLUM,      "Post-ABC cohort"),
            kpi_card("Livestock Monitored","700–1k", "animals",  COPPER,     GOLD,      "Via Vet Department"),
            kpi_card("AMR Status",         "Safe",   "",         SAGE,       GLACIER,   "Within permissible limits"),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_rab, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_abc, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_amr, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_g,   config={"displayModeBar":False})),
        ]),
        section_head("Key Insights", pal),
        html.Div([
            insight_card(row["insight"], [TERRACOTTA,COPPER,GOLD][i%3],
                         [GOLD,TURMERIC,SAGE][i%3])
            for i, (_, row) in enumerate(ai.iterrows())
        ]) if not ai.empty else html.Div(),
    ])


def page_environment(d):
    pal = EN
    wq  = d.get("water_quality",              pd.DataFrame())
    vc  = d.get("villagewatercfu",             pd.DataFrame())
    lc  = d.get("lake_water_cfu",              pd.DataFrame())
    gt  = d.get("gram_staining_total",         pd.DataFrame())
    mc  = d.get("microbial_analysis",          pd.DataFrame())
    aq  = d.get("air_quality",                 pd.DataFrame())
    sc  = d.get("soil_cfu",                    pd.DataFrame())
    pv  = d.get("physiochem_village_waterquality", pd.DataFrame())

    # Water scatter — status colours from palette
    fig_wq = go.Figure()
    if not wq.empty:
        st_col = {"Unfit":"#dc2626","Treat First":TURMERIC,
                  "Borderline":PLUM,"Agriculture":SAGE}
        fig_wq = px.scatter(
            wq, x="TDS_ppm", y="DO_mg_L", color="drinking_status",
            color_discrete_map=st_col, size="turbidity_NTU", size_max=35,
            hover_name="source_name",
            title="Water Quality — TDS vs Dissolved Oxygen",
            labels={"TDS_ppm":"TDS (ppm)","DO_mg_L":"DO (mg/L)","drinking_status":"Status"},
            hover_data=["pH","EC_mS","turbidity_NTU"],
        )
        fig_wq.add_vline(x=500, line_dash="dot", line_color=GLACIER, line_width=1.5,
                         annotation_text="TDS safe ≤500",
                         annotation_font=dict(color=GLACIER, size=10))
        fig_wq.add_hline(y=6, line_dash="dot", line_color=SAGE, line_width=1.5,
                         annotation_text="DO safe ≥6",
                         annotation_font=dict(color=SAGE, size=10))
        fig_wq.update_layout(**PL(pal))

    # Village CFU — sage to glacier mismatch
    fig_vc = go.Figure()
    if not vc.empty:
        vc_s = vc.sort_values("mean_cfu")
        n    = len(vc_s)
        bar_clr = [SAGE if i < n//2 else GLACIER for i in range(n)]
        fig_vc.add_trace(go.Bar(
            x=vc_s["mean_cfu"], y=vc_s["source"], orientation="h",
            marker_color=bar_clr, marker_line_width=0,
            hovertemplate="<b>%{y}</b><br>%{x:.3f} CFU/mL<extra></extra>",
        ))
    fig_vc.update_layout(**PL(pal, "Village Water — Mean CFU/mL",
                               xaxis_title="CFU/mL"))

    # Lake CFU — glacier to plum (intensity)
    fig_lc = go.Figure()
    if not lc.empty:
        lc_s = lc.sort_values("mean_cfu", ascending=False)
        n    = len(lc_s)
        bar_clr = [PLUM if i < n//3 else (DEEP_WINE if i < 2*n//3 else GLACIER) for i in range(n)]
        fig_lc.add_trace(go.Bar(
            x=lc_s["sample"], y=lc_s["mean_cfu"],
            marker_color=bar_clr, marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>%{y:.3f} CFU/mL<extra></extra>",
        ))
    fig_lc.update_layout(**PL(pal, "Lake Entry Points — Mean CFU/mL",
                               yaxis_title="CFU/mL"))
    fig_lc.update_xaxes(tickangle=-25)

    # Soil — terracotta to gold (earthy)
    fig_sc = go.Figure()
    if not sc.empty:
        fig_sc.add_trace(go.Bar(
            x=sc["sample"], y=sc["mean_cfu"],
            marker_color=[TERRACOTTA, COPPER, GOLD],
            marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>%{y:.4f} CFU/mL<extra></extra>",
        ))
    fig_sc.update_layout(**PL(pal, "Soil CFU by Site", yaxis_title="CFU/mL"))
    fig_sc.update_xaxes(tickangle=-10)

    # Gram staining donut
    fig_gr = go.Figure()
    if not gt.empty:
        g = gt.iloc[0]
        fig_gr.add_trace(go.Pie(
            labels=["Gram Negative","Gram Positive"],
            values=[g["gram_negative_percent"], 100-g["gram_negative_percent"]],
            hole=0.58,
            marker_colors=[GLACIER, T["border2"]],
            textfont_color=T["text"],
        ))
    fig_gr.update_layout(**PLna(pal, "Gram Staining — 26 Isolates"))

    # AQI gauge
    aqi_val = 135
    if not aq.empty:
        aq_row = aq[aq["parameter"]=="AQI"]
        if not aq_row.empty:
            aqi_val = int(aq_row["value"].iloc[0])
    fig_aqi = go.Figure(go.Indicator(
        mode="gauge+number", value=aqi_val,
        title={"text":"Air Quality Index (AQI)","font":{"color":GLACIER,"size":13}},
        number={"font":{"color":TURMERIC,"size":40}},
        gauge=dict(
            axis=dict(range=[0,200], tickcolor=T["muted"], tickfont_color=T["muted"]),
            bar=dict(color=TURMERIC, thickness=0.25),
            bgcolor="#ffffff", bordercolor=T["border2"],
            steps=[
                dict(range=[0,50],   color="#d1fae5"),
                dict(range=[50,100], color="#ecfccb"),
                dict(range=[100,150],color="#fef3c7"),
                dict(range=[150,200],color="#fee2e2"),
            ],
            threshold=dict(line=dict(color="#dc2626",width=2.5), value=150),
        ),
    ))
    fig_aqi.update_layout(**PLgauge(pal), height=250, margin=dict(l=24,r=24,t=44,b=16))

    return html.Div([
        page_header("Environment Pillar",
                    "Water physico-chemistry, microbial load, gram staining, soil & air quality", pal),
        description_box(
            "Samples collected from 10 water sources, 3 soil sites, and ambient air. "
            "Household effluent TDS was 1,420 ppm (safe limit 500 ppm) and dissolved oxygen was 0.08 mg/L — near anoxic. "
            "TNTC (Too Numerous To Count) bacterial colonies were found at multiple lake entry points. "
            "All 26 gram-stained isolates were Gram-negative, confirming faecal contamination. "
            "E. coli was present in all 3 soil sites tested.", pal),
        section_head("Environment Key Indicators", pal),
        kpi_row([
            kpi_card("Effluent TDS",    "1,420","ppm",     DEEP_WINE,  PLUM,      "Safe limit: 500 ppm"),
            kpi_card("Effluent DO",     "0.08", "mg/L",    PLUM,       TERRACOTTA,"Near anoxic (safe: ≥6)"),
            kpi_card("Gram Negative",   "100",  "%",       GLACIER,    SAGE,      "All 26 isolates"),
            kpi_card("AQI",             "135",  "",        TURMERIC,   COPPER,    "Unhealthy for sensitive groups"),
            kpi_card("E. coli Soil",    "3/3",  "sites",   COPPER,     TURMERIC,  "All sites positive"),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_wq, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_gr, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_vc, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_lc, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_sc,  config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_aqi, config={"displayModeBar":False})),
        ]),
        section_head("Microbial Status — Lake Entry Points", pal),
        table_wrap([
            table_head([("Location",2),("NA Plate Count",1),("EMB Indicator",1),("Status",1)]),
            *[table_row([
                (row["location"],2),(str(row["na_plate_count"]),1),(str(row["emb_indicator"]),1),
                (status_pill(row["microbial_status"],
                    {"High":"#fee2e2","Moderate":"#fef3c7"}.get(row["microbial_status"],"#d1fae5"),
                    {"High":"#dc2626","Moderate":TURMERIC}.get(row["microbial_status"],SAGE)), 1),
            ]) for _, row in mc.iterrows()]
        ]) if not mc.empty else html.Div(),
        section_head("Water Sample Field Notes", pal),
        table_wrap([
            table_head([("ID",0.5),("Sample Label",2),("Field Observation",4)]),
            *[table_row([
                (f"S{int(row['Sample no.'])}", 0.5),
                (str(row["Label"]).strip(), 2),
                (str(row["Label Description"])[:120]+("…" if len(str(row["Label Description"]))>120 else ""), 4),
            ]) for _, row in pv.iterrows() if pd.notna(row.get("Label Description",""))]
        ]) if not pv.empty else html.Div(),
    ])


def page_interconnections(d):
    pal = OV
    zoo = d.get("zoonoticTransmission", pd.DataFrame())
    rd  = d.get("rainfallDisease",      pd.DataFrame())
    ints= d.get("interactionStrength",  pd.DataFrame())
    rm  = d.get("riskMatrix",           pd.DataFrame())

    # Zoonotic — each pathway gets its domain colour
    fig_zoo = go.Figure()
    if not zoo.empty:
        for col, c, name in [
            ("directContact",  PLUM,       "Direct Contact"),
            ("environmental",  SAGE,       "Environmental"),
            ("foodWater",      TURMERIC,   "Food / Water"),
            ("vectorMediated", GLACIER,    "Vector Mediated"),
        ]:
            if col in zoo.columns:
                fig_zoo.add_trace(go.Bar(
                    x=zoo["pathway"], y=zoo[col], name=name, marker_color=c,
                ))
    fig_zoo.update_layout(**PL(pal, "Zoonotic Transmission Pathways",
                                 barmode="stack", yaxis_title="Transmission %"))
    fig_zoo.update_xaxes(tickangle=-15)

    # Rainfall vs disease
    fig_rain = go.Figure()
    if not rd.empty:
        for col, c, name in [("dengueCases",DEEP_WINE,"Dengue"),
                               ("malariaCases",PLUM,"Malaria"),
                               ("leptospirosis",COPPER,"Leptospirosis")]:
            if col in rd.columns:
                fig_rain.add_trace(go.Scatter(
                    x=rd["rainfallIndex"], y=rd[col],
                    name=name, mode="markers+lines",
                    marker=dict(size=10, color=c),
                    line=dict(color=c, width=1.8),
                    text=rd["year"],
                    hovertemplate=f"<b>{name}</b><br>Rainfall: %{{x}}<br>Cases: %{{y}}<br>Year: %{{text}}<extra></extra>",
                ))
    fig_rain.update_layout(**PL(pal, "Rainfall Index vs Vector Disease Cases",
                                  xaxis_title="Rainfall Index", yaxis_title="Cases"))

    # Interaction strength — red→green transformation
    fig_int = go.Figure()
    if not ints.empty:
        fig_int.add_trace(go.Bar(x=ints["interaction"], y=ints["current"],
                                  name="Current", marker_color=DEEP_WINE))
        fig_int.add_trace(go.Bar(x=ints["interaction"], y=ints["afterIntervention"],
                                  name="After Intervention", marker_color=SAGE))
    fig_int.update_layout(**PL(pal, "Cross-Pillar Interaction — Before vs After",
                                 barmode="group", yaxis_title="Interaction Score"))

    # Risk bubble — mismatch sage→turmeric→wine gradient
    fig_bub = go.Figure()
    if not rm.empty:
        fig_bub = px.scatter(
            rm, x="likelihood", y="impact", size="urgency",
            hover_name="factor", text="factor", size_max=55,
            color="urgency",
            color_continuous_scale=[[0,SAGE],[0.4,TURMERIC],[0.7,COPPER],[1,DEEP_WINE]],
            title="Risk Matrix — Likelihood vs Impact (size = Urgency)",
            labels={"likelihood":"Likelihood (%)","impact":"Impact Score"},
        )
        fig_bub.update_traces(textposition="top center",
                              textfont=dict(size=9, color=T["muted"]))
        fig_bub.update_layout(**PL(pal))
        fig_bub.update_coloraxes(colorbar_tickfont_color=T["muted"],
                                  colorbar_title_font_color=T["muted"])

    return html.Div([
        page_header("Interconnections — One Health Web",
                    "How human, animal & environmental health interact, amplify risk, and respond to joint intervention", pal),
        description_box(
            "One Health recognises that human, animal, and environmental health are inseparable. "
            "Household effluent flows into the lake (Human→Environment), livestock excreta contaminates soil and water "
            "(Animal→Environment), contaminated water drives disease burden (Environment→Human). "
            "The interaction chart shows full One Health intervention reduces all pillar-to-pillar scores by 40–65%. "
            "The rainfall data confirms monsoon seasons are the highest-risk windows for dengue, malaria, and leptospirosis simultaneously.", pal),
        section_head("Interconnection Key Indicators", pal),
        kpi_row([
            kpi_card("Top Risk — Urgency", "95",   "score",        DEEP_WINE,  PLUM,       "Water contamination"),
            kpi_card("Rainfall Corr.",     "High", "",             TURMERIC,   COPPER,     "Dengue spike 2022"),
            kpi_card("Lepto Env Route",    "60%",  "environmental",SAGE,       GLACIER,    "Soil/water dominant"),
            kpi_card("Rabies ABC+Vacc",    "86%",  "reduction",    TERRACOTTA, GOLD,       "vs no intervention yr 5"),
            kpi_card("Full OH 2030",       "−80%", "burden",       SAGE,       INDIGO,     "vs doing nothing"),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_zoo,  config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_rain, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_int,  config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_bub,  config={"displayModeBar":False})),
        ]),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# TAB CONFIG
# ══════════════════════════════════════════════════════════════════════════════
TAB_CFG = [
    ("overview",         "Overview",          gradient_css(INDIGO, TURMERIC)),
    ("human",            "Human Health",      gradient_css(PLUM, DEEP_WINE)),
    ("animal",           "Animal Health",     gradient_css(TERRACOTTA, COPPER)),
    ("environment",      "Environment",       gradient_css(SAGE, GLACIER)),
    ("interconnections", "Interconnections",  gradient_css(INDIGO, TURMERIC, SAGE)),
]

# ══════════════════════════════════════════════════════════════════════════════
# APP LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
app.layout = html.Div([
    html.Link(rel="stylesheet",
              href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"),

    # Auto-refresh interval — every 60 seconds
    dcc.Interval(id="refresh-interval", interval=60*1000, n_intervals=0),

    # Store for data timestamp
    dcc.Store(id="data-timestamp", data=""),

    # ── Header ──────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            # Three dots — one per domain — with mismatch gradient colours
            html.Div(style={
                "width":"10px","height":"10px","borderRadius":"50%",
                "background":gradient_css(PLUM, DEEP_WINE),
                "marginRight":"6px","flexShrink":"0",
            }),
            html.Div(style={
                "width":"10px","height":"10px","borderRadius":"50%",
                "background":gradient_css(TERRACOTTA, COPPER),
                "marginRight":"6px","flexShrink":"0",
            }),
            html.Div(style={
                "width":"10px","height":"10px","borderRadius":"50%",
                "background":gradient_css(SAGE, GLACIER),
                "marginRight":"16px","flexShrink":"0",
            }),
            html.Span("ONE HEALTH DASHBOARD", style={
                "fontFamily":"'Inter',sans-serif","fontSize":"14px",
                "fontWeight":"700","color":T["text"],"letterSpacing":"2px",
            }),
            html.Span("  Bettahalasuru Village", style={
                "fontSize":"12px","color":T["muted"],"marginLeft":"10px",
            }),
        ], style={"display":"flex","alignItems":"center"}),

        # Right side — live indicator + manual refresh + timestamp
        html.Div([
            html.Div(id="last-update-display", style={
                "fontSize":"11px","color":T["muted"],"marginRight":"16px",
            }),
            html.Button("↻ Refresh Now", id="manual-refresh-btn", n_clicks=0, style={
                "background":T["subtle"],"border":f"1px solid {T['border2']}",
                "color":SAGE,"borderRadius":"20px","padding":"5px 14px",
                "fontSize":"11px","cursor":"pointer","fontFamily":"'Inter',sans-serif",
                "fontWeight":"600","marginRight":"12px",
            }),
            html.Span("● LIVE", style={
                "fontSize":"10px","color":SAGE,"fontWeight":"700","letterSpacing":"2px"
            }),
        ], style={"display":"flex","alignItems":"center"}),

    ], style={
        "display":"flex","justifyContent":"space-between","alignItems":"center",
        "padding":"13px 28px","borderBottom":f"1px solid {T['border']}",
        "background":T["surface"],"position":"sticky","top":"0","zIndex":"300",
        "boxShadow":"0 1px 6px rgba(0,0,0,0.07)",
    }),

    # ── Tab bar ─────────────────────────────────────────────────────────────
    dcc.Tabs(
        id="main-tabs", value="overview",
        children=[
            dcc.Tab(
                label=label, value=val,
                style={
                    "padding":"10px 20px","fontSize":"12px","fontWeight":"600",
                    "letterSpacing":"0.3px","fontFamily":"'Inter',sans-serif",
                    "color":T["muted"],"background":"transparent",
                    "borderBottom":"3px solid transparent","border":"none","borderRadius":"0",
                },
                selected_style={
                    "padding":"10px 20px","fontSize":"12px","fontWeight":"700",
                    "letterSpacing":"0.3px","fontFamily":"'Inter',sans-serif",
                    "color":T["text"],"background":T["subtle"],
                    "borderBottom":f"3px solid transparent",
                    "border":"none","borderRadius":"0",
                    "borderImage":f"{grad} 1",
                },
            )
            for val, label, grad in TAB_CFG
        ],
        style={
            "background":T["surface"],"borderBottom":f"1px solid {T['border']}",
            "padding":"0 24px","boxShadow":"0 1px 3px rgba(0,0,0,0.04)",
        },
    ),

    # ── Page content ─────────────────────────────────────────────────────────
    html.Div(id="page-content", style={
        "padding":"28px 32px","maxWidth":"1440px","margin":"0 auto",
    }),

], style={"background":T["bg"],"minHeight":"100vh",
           "fontFamily":"'Inter',sans-serif","color":T["text"]})

# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

# Auto/manual data refresh
@app.callback(
    Output("data-timestamp","data"),
    Output("last-update-display","children"),
    Input("refresh-interval","n_intervals"),
    Input("manual-refresh-btn","n_clicks"),
)
def refresh_data(n_intervals, n_clicks):
    global DATA
    DATA = load_all()
    ts   = datetime.now().strftime("%d %b %Y %H:%M:%S")
    return ts, f"Updated: {ts}"


# Render page content
@app.callback(
    Output("page-content","children"),
    Input("main-tabs","value"),
    Input("data-timestamp","data"),
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