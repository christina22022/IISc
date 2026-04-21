import dash
from dash import html, dcc, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "One Health Dashboard — Bettahalasuru"

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

def xl(file, sheet):
    return pd.read_excel(os.path.join(DATA, file), sheet_name=sheet)

# ── Data ───────────────────────────────────────────────────────────────────────
phc_summary      = xl("human.xlsx",             "phcSummary")
major_diseases   = xl("human.xlsx",             "majorDiseases")
disease_burden   = xl("human.xlsx",             "diseaseBurden")
vector_trend     = xl("human.xlsx",             "vectorDiseaseTrend")
phc_screening    = xl("human.xlsx",             "phcScreeningPrograms")
vector_insights  = xl("human.xlsx",             "vectorInsights")

abc_program      = xl("animal.xlsx",            "abcProgram")
rabies_proj      = xl("animal.xlsx",            "rabiesProjection")
amr_findings     = xl("animal.xlsx",            "amrFindings")
animal_insights  = xl("animal.xlsx",            "animalInsights")

water_quality    = xl("Environment.xlsx",       "water_quality")
village_cfu      = xl("Environment.xlsx",       "villagewatercfu")
lake_cfu         = xl("Environment.xlsx",       "lake_water_cfu")
gram_total       = xl("Environment.xlsx",       "gram_staining_total")
microbial        = xl("Environment.xlsx",       "microbial_analysis")
air_quality      = xl("Environment.xlsx",       "air_quality")
soil_cfu         = xl("Environment.xlsx",       "soil_cfu")
physiochem_vill  = xl("Environment.xlsx",       "physiochem_village_waterquality")

risk_matrix      = xl("interconnectedness.xlsx","riskMatrix")
zoonotic         = xl("interconnectedness.xlsx","zoonoticTransmission")
rainfall_disease = xl("interconnectedness.xlsx","rainfallDisease")
cross_pillar     = xl("interconnectedness.xlsx","crossPillarIndex")
interaction_str  = xl("interconnectedness.xlsx","interactionStrength")
projected        = xl("interconnectedness.xlsx","projectedOutcome")

village_cfu.columns  = ["source","rep1","rep2","rep3"]
village_cfu["mean_cfu"] = village_cfu[["rep1","rep2","rep3"]].mean(axis=1).round(3)
lake_cfu.columns     = ["sample","rep1","rep2","rep3"]
lake_cfu["mean_cfu"] = lake_cfu[["rep1","rep2","rep3"]].mean(axis=1).round(3)
soil_cfu.columns     = ["sample","rep1","rep2","rep3"]
soil_cfu["mean_cfu"] = soil_cfu[["rep1","rep2","rep3"]].mean(axis=1).round(3)

# ══════════════════════════════════════════════════════════════════════════════
# LIGHT THEME  (fixed)
# ══════════════════════════════════════════════════════════════════════════════
T = {
    "bg":       "#f0f4f8",
    "surface":  "#ffffff",
    "card":     "#ffffff",
    "border":   "#e2e8f0",
    "border2":  "#cbd5e1",
    "text":     "#1e293b",
    "muted":    "#64748b",
    "subtle":   "#f8fafc",
    "grid":     "#f1f5f9",
    "shadow":   "0 1px 4px rgba(0,0,0,0.07)",
}

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN COLOUR SYSTEMS  — multiple colours per domain
# ══════════════════════════════════════════════════════════════════════════════

# OVERVIEW / INTERCONNECTIONS — slate-blue multi
OV = {
    "c1": "#3b82f6",   # blue       — primary
    "c2": "#8b5cf6",   # violet
    "c3": "#06b6d4",   # cyan
    "c4": "#10b981",   # emerald
    "c5": "#f59e0b",   # amber
    "danger": "#ef4444",
    "scale": [[0,"#dbeafe"],[0.33,"#93c5fd"],[0.66,"#3b82f6"],[1,"#1d4ed8"]],
    "header_bg": "#eff6ff",
    "header_border": "#bfdbfe",
    "desc_bg": "#f0f9ff",
    "desc_border": "#bae6fd",
    "desc_left": "#3b82f6",
}

# HUMAN — purple multi
HU = {
    "c1": "#7c3aed",   # deep violet — primary
    "c2": "#db2777",   # pink
    "c3": "#0891b2",   # cyan-blue
    "c4": "#059669",   # green
    "c5": "#d97706",   # amber
    "danger": "#ef4444",
    "scale": [[0,"#ede9fe"],[0.33,"#c4b5fd"],[0.66,"#8b5cf6"],[1,"#5b21b6"]],
    "header_bg": "#faf5ff",
    "header_border": "#e9d5ff",
    "desc_bg": "#fdf4ff",
    "desc_border": "#e9d5ff",
    "desc_left": "#7c3aed",
}

# ANIMAL — warm earth multi
AN = {
    "c1": "#b45309",   # amber-brown — primary
    "c2": "#dc2626",   # red
    "c3": "#16a34a",   # green
    "c4": "#0369a1",   # blue
    "c5": "#7c3aed",   # violet
    "danger": "#ef4444",
    "scale": [[0,"#fef3c7"],[0.33,"#fcd34d"],[0.66,"#d97706"],[1,"#92400e"]],
    "header_bg": "#fffbeb",
    "header_border": "#fde68a",
    "desc_bg": "#fefce8",
    "desc_border": "#fde68a",
    "desc_left": "#b45309",
}

# ENVIRONMENT — nature multi
EN = {
    "c1": "#059669",   # emerald — primary
    "c2": "#0891b2",   # cyan
    "c3": "#65a30d",   # lime
    "c4": "#7c3aed",   # violet
    "c5": "#f59e0b",   # amber
    "danger": "#ef4444",
    "scale": [[0,"#d1fae5"],[0.33,"#6ee7b7"],[0.66,"#10b981"],[1,"#065f46"]],
    "header_bg": "#f0fdf4",
    "header_border": "#bbf7d0",
    "desc_bg": "#f0fdfa",
    "desc_border": "#99f6e4",
    "desc_left": "#059669",
}

PALETTES = {
    "overview": OV, "human": HU, "animal": AN,
    "environment": EN, "interconnections": OV,
}

# ══════════════════════════════════════════════════════════════════════════════
# PLOT HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def PL(pal, title="", **kw):
    """Base plotly layout — light mode."""
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
        hoverlabel=dict(bgcolor="#f8fafc", bordercolor=T["border2"],
                        font=dict(color=T["text"], size=12)),
    )
    base.update(kw)
    return base

def PL_noax(pal, title="", **kw):
    return {k: v for k, v in PL(pal, title, **kw).items() if "axis" not in k}

def PL_nogauge(pal, title=""):
    return {k: v for k, v in PL_noax(pal, title).items() if k != "margin"}

# ══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════
def page_header(title, subtitle, pal):
    return html.Div([
        html.Div(style={
            "width":"5px","height":"54px","borderRadius":"4px",
            "background":f"linear-gradient(to bottom,{pal['c1']},{pal['c2']})",
            "marginRight":"18px","flexShrink":"0",
        }),
        html.Div([
            html.H2(title, style={
                "margin":"0","fontSize":"22px","fontWeight":"700",
                "color":pal["c1"],"fontFamily":"'Inter',sans-serif","letterSpacing":"-0.3px",
            }),
            html.P(subtitle, style={"margin":"4px 0 0","fontSize":"13px",
                                     "color":T["muted"],"lineHeight":"1.5"}),
        ])
    ], style={
        "display":"flex","alignItems":"center","marginBottom":"22px",
        "background":pal["header_bg"],"border":f"1px solid {pal['header_border']}",
        "borderRadius":"12px","padding":"16px 20px",
    })

def section_head(text, color):
    return html.P(text, style={
        "color":color,"fontSize":"10px","fontWeight":"700","letterSpacing":"2.5px",
        "textTransform":"uppercase","margin":"0 0 12px",
        "borderBottom":f"2px solid {color}20","paddingBottom":"8px",
    })

def description_box(text, pal):
    return html.Div(text, style={
        "background":pal["desc_bg"],"border":f"1px solid {pal['desc_border']}",
        "borderLeft":f"4px solid {pal['desc_left']}","borderRadius":"8px",
        "padding":"14px 18px","fontSize":"13px","color":T["muted"],
        "lineHeight":"1.8","marginBottom":"22px",
    })

def kpi_card(label, value, unit, color, sub):
    return html.Div([
        html.Div(style={"height":"3px","background":color,
                        "borderRadius":"10px 10px 0 0","margin":"-16px -18px 14px"}),
        html.P(label, style={"margin":"0 0 6px","fontSize":"10px","fontWeight":"700",
                              "letterSpacing":"2px","textTransform":"uppercase",
                              "color":T["muted"]}),
        html.Div([
            html.Span(str(value), style={"fontSize":"26px","fontWeight":"700",
                                          "color":color,"lineHeight":"1"}),
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

def insight_card(text, color):
    return html.Div([
        html.Div(style={"width":"3px","background":color,"borderRadius":"2px",
                        "marginRight":"12px","flexShrink":"0","minHeight":"100%"}),
        html.P(text, style={"margin":"0","fontSize":"12px","color":T["text"],"lineHeight":"1.65"}),
    ], style={
        "display":"flex","alignItems":"flex-start",
        "background":T["card"],"border":f"1px solid {T['border']}",
        "borderLeft":f"3px solid {color}","borderRadius":"8px",
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

def table_header(cols):
    return html.Div([
        html.Div(c, style={"flex":str(f),"fontSize":"10px","fontWeight":"700",
                            "color":T["muted"],"letterSpacing":"1.5px",
                            "textTransform":"uppercase","padding":"0 8px"})
        for c, f in cols
    ], style={"display":"flex","padding":"10px 14px",
               "background":T["subtle"],"borderBottom":f"1px solid {T['border']}"})

def table_row_div(cells):
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

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
def page_overview():
    pal = OV
    rm  = risk_matrix.copy()

    # Risk radar — each metric a different domain colour
    fig_risk = go.Figure()
    for col, color, name in [
        ("likelihood", HU["c1"], "Likelihood"),
        ("impact",     AN["c1"], "Impact"),
        ("urgency",    EN["c1"], "Urgency"),
    ]:
        vals = rm[col].tolist() + [rm[col].iloc[0]]
        cats = rm["factor"].tolist() + [rm["factor"].iloc[0]]
        fig_risk.add_trace(go.Scatterpolar(
            r=vals, theta=cats, name=name, fill="toself",
            line=dict(color=color, width=2), opacity=0.75,
            fillcolor="rgba(0,0,0,0)",
        ))
    fig_risk.update_layout(
        **PL_noax(pal, "Multi-Factor Risk Radar"),
        polar=dict(
            bgcolor="#ffffff",
            radialaxis=dict(range=[0,100], gridcolor=T["grid"],
                            tickfont_color=T["muted"], tickfont_size=9,
                            linecolor=T["border2"]),
            angularaxis=dict(gridcolor=T["grid"], tickfont_color=T["text"],
                             linecolor=T["border2"]),
        ),
    )

    # Projected outcomes
    fig_proj = go.Figure()
    for col, color, name, dash in [
        ("noIntervention", "#ef4444",  "No Intervention",  "solid"),
        ("partial",        AN["c1"],   "Partial One Health","dash"),
        ("fullOneHealth",  EN["c1"],   "Full One Health",   "solid"),
    ]:
        fig_proj.add_trace(go.Scatter(
            x=projected["year"], y=projected[col], name=name,
            mode="lines+markers", line=dict(color=color, width=2.5, dash=dash),
            marker=dict(size=7, color=color),
            fill="tozeroy" if col=="fullOneHealth" else "none",
            fillcolor="rgba(5,150,105,0.06)",
        ))
    fig_proj.update_layout(**PL(pal, "Projected Disease Burden 2025–2030",
                                  yaxis_title="Burden Index", xaxis_title="Year"))

    # Cross-pillar risk — coloured by value
    cp = cross_pillar.sort_values("value", ascending=True).copy()
    cp_colors = [pal["c4"] if v<50 else (pal["c5"] if v<70 else pal["c1"]) for v in cp["value"]]
    fig_cross = go.Figure(go.Bar(
        x=cp["value"], y=cp["factor"], orientation="h",
        marker_color=cp_colors, marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Risk Score: %{x}<extra></extra>",
    ))
    fig_cross.update_layout(**PL(pal, "Cross-Pillar Risk Index",
                                   xaxis_title="Risk Score"))
    fig_cross.add_vline(x=70, line_dash="dot", line_color="#ef4444", line_width=1,
                        annotation_text="High risk", annotation_font_color="#ef4444",
                        annotation_font_size=10)

    return html.Div([
        page_header("One Health Overview — Bettahalasuru Village",
                    "Integrated study of Human, Animal & Environmental health — rural Karnataka (Population 5,500)", pal),
        description_box(
            "This dashboard presents a comprehensive One Health assessment of Bettahalasuru village. "
            "Navigate through the five tabs to explore each pillar. Water contamination scores highest on urgency (95/100). "
            "A full One Health intervention could reduce the disease burden by 80% by 2030 compared to inaction.", pal),

        section_head("Study Summary", pal["c1"]),
        kpi_row([
            kpi_card("Village Population",   "5,500", "residents",      pal["c1"], "Bettahalasuru, Karnataka"),
            kpi_card("PHC Services",         "8",     "active programs", HU["c1"], "Screening + treatment"),
            kpi_card("Stray Dogs in ABC",    "550",   "animals",         AN["c1"], "Mar 2024 programme"),
            kpi_card("Water Sources Tested", "10",    "locations",       EN["c1"], "Village + lake combined"),
            kpi_card("Top Risk Score",       "95",    "urgency",         "#ef4444","Water contamination"),
        ]),

        grid2([
            chart_box(dcc.Graph(figure=fig_risk,  config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_proj,  config={"displayModeBar":False})),
        ]),

        grid3([
            chart_box(dcc.Graph(figure=fig_cross, config={"displayModeBar":False}), span=2),
            html.Div([
                section_head("Key Findings", pal["c1"]),
                insight_card("Water contamination is the top urgency risk (95/100). Household effluent TDS at 1,420 ppm — nearly 3× the safe limit of 500 ppm.", pal["c1"]),
                insight_card("Dengue spiked to 60 cases in 2022 following high rainfall (index 95). Rainfall is a strong predictor of vector disease burden.", pal["c2"]),
                insight_card("ABC + Vaccination is the only rabies scenario that prevents exponential spread. ABC alone slows growth but does not stop it.", pal["c3"]),
                insight_card("Full One Health intervention could reduce disease burden 80% by 2030 vs doing nothing.", pal["c4"]),
            ], style={"background":T["card"],"border":f"1px solid {T['border']}",
                      "borderRadius":"10px","padding":"18px","boxShadow":T["shadow"]}),
        ]),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: HUMAN HEALTH
# ══════════════════════════════════════════════════════════════════════════════
def page_human():
    pal = HU

    # Disease bar — gradient from light to dark purple by case count
    fig_dis = px.bar(
        major_diseases.sort_values("cases", ascending=True),
        x="cases", y="disease", orientation="h",
        color="cases",
        color_continuous_scale=[[0,"#ede9fe"],[0.4,"#a78bfa"],[0.7,"#7c3aed"],[1,"#4c1d95"]],
        title="Disease Case Load",
        labels={"cases":"Cases Reported","disease":""},
    )
    fig_dis.update_layout(**PL(pal))
    fig_dis.update_coloraxes(showscale=False)

    # Vector trend — each disease a distinct colour
    fig_vec = go.Figure()
    vcfg = [
        ("malaria",       pal["c1"], "solid"),
        ("dengue",        pal["c2"], "solid"),
        ("chikungunya",   pal["c3"], "dash"),
        ("leptospirosis", pal["c4"], "dot"),
    ]
    for col, color, dash in vcfg:
        fig_vec.add_trace(go.Scatter(
            x=vector_trend["year"], y=vector_trend[col],
            name=col.capitalize(), mode="lines+markers",
            line=dict(color=color, width=2.2, dash=dash),
            marker=dict(size=7, color=color),
        ))
    fig_vec.update_layout(**PL(pal, "Vector-Borne Disease Trend 2020–2024",
                                 yaxis_title="Cases", xaxis_title="Year"))

    # Disease burden — severity colours (green→amber→red)
    db = disease_burden.copy()
    db_colors = [
        EN["c1"] if v < 45 else (AN["c5"] if v < 65 else pal["c2"])
        for v in db["value"]
    ]
    fig_bur = go.Figure(go.Bar(
        x=db["value"], y=db["diseaseCategory"], orientation="h",
        marker_color=db_colors, marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Severity: %{x}<extra></extra>",
    ))
    fig_bur.update_layout(**PL(pal, "Disease Burden Severity Index",
                                 xaxis_title="Severity Score"))

    # Screening status pie — multiple purples
    sc = phc_screening["status"].value_counts().reset_index()
    sc.columns = ["status","count"]
    fig_sc = px.pie(
        sc, names="status", values="count", hole=0.55,
        color_discrete_sequence=[pal["c1"], pal["c2"], pal["c3"]],
        title="PHC Programs by Status",
    )
    fig_sc.update_layout(**PL_noax(pal))
    fig_sc.update_traces(textfont_color=T["text"])

    return html.Div([
        page_header("Human Health Pillar",
                    "Primary Health Centre data — Bettahalasuru village, Population 5,500", pal),
        description_box(
            "The PHC serves 5,500 residents with 8 active programs. Hypertension (75) and Diabetes (65) are the "
            "dominant conditions, both rising due to lifestyle and dietary changes. Vector-borne diseases are "
            "strongly seasonal — dengue peaked at 60 cases in 2022 due to above-average rainfall and "
            "stagnant water near the lake. Malaria is endemic at 30–50 cases per monsoon season.", pal),

        section_head("PHC Key Indicators", pal["c1"]),
        kpi_row([
            kpi_card("Total Population",    "5,500",  "",          pal["c1"], "Bettahalasuru"),
            kpi_card("Hypertension Cases",  "75",     "cases",     pal["c2"], "Highest single disease"),
            kpi_card("Dengue Peak (2022)",  "60",     "cases",     "#ef4444", "Spike — stagnant water"),
            kpi_card("Malaria Range",       "30–50",  "cases/yr",  pal["c3"], "Monsoon driven"),
            kpi_card("Active Programs",     "8",      "services",  pal["c4"], "Weekly + seasonal"),
        ]),

        grid2([
            chart_box(dcc.Graph(figure=fig_dis, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_vec, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_bur, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_sc,  config={"displayModeBar":False})),
        ]),

        section_head("Vector Disease Insights", pal["c2"]),
        html.Div([
            insight_card(f"{r['disease']}: {r['casesRange']} cases — {r['insight']}",
                         [pal["c1"],pal["c2"],pal["c3"]][i % 3])
            for i, (_, r) in enumerate(vector_insights.iterrows())
        ]),

        section_head("PHC Screening Programs", pal["c3"]),
        table_wrap([
            table_header([("Screening Type",2),("Frequency",1),("Status",1)]),
            *[table_row_div([
                (row["screeningType"], 2),
                (row["frequency"],     1),
                (status_pill(row["status"],
                             {"Active":"#ede9fe","Seasonal":"#fef3c7","Periodic":"#d1fae5"}.get(row["status"],"#f1f5f9"),
                             {"Active":pal["c1"],"Seasonal":AN["c1"],"Periodic":EN["c1"]}.get(row["status"],T["muted"])),
                 1),
            ]) for _, row in phc_screening.iterrows()]
        ]),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ANIMAL HEALTH
# ══════════════════════════════════════════════════════════════════════════════
def page_animal():
    pal = AN

    # Rabies projection — 3 distinct colours
    fig_rab = go.Figure()
    rab_cfg = [
        ("noAbc",             "#ef4444", "solid", "No ABC"),
        ("withAbc",           pal["c1"], "dash",  "ABC Only"),
        ("withAbcVaccination",pal["c3"], "solid", "ABC + Vaccination"),
    ]
    for col, color, dash, name in rab_cfg:
        fig_rab.add_trace(go.Scatter(
            x=rabies_proj["year"], y=rabies_proj[col], name=name,
            mode="lines+markers", line=dict(color=color, width=2.5, dash=dash),
            marker=dict(size=7, color=color),
            fill="tozeroy" if col=="noAbc" else "none",
            fillcolor="rgba(239,68,68,0.05)",
        ))
    fig_rab.update_layout(**PL(pal, "Rabies Projection — 5-Year Model",
                                 yaxis_title="Infected Animals", xaxis_title="Year"))

    # ABC steps — alternating warm tones
    abc_colors = [pal["c1"],pal["c5"],pal["c1"],pal["c5"],pal["c5"],pal["c5"],pal["c3"]]
    fig_abc = go.Figure()
    for i, row in abc_program.iterrows():
        fig_abc.add_trace(go.Bar(
            x=[row["count"]], y=[row["activity"]], orientation="h",
            marker_color=abc_colors[i], showlegend=False,
            hovertemplate=f"<b>{row['activity']}</b><br>Animals: {row['count']}<extra></extra>",
        ))
    abc_pl = {k:v for k,v in PL(pal,"ABC Programme — March 2024 (17 Dogs)").items() if k!="xaxis"}
    fig_abc.update_layout(**abc_pl, xaxis=dict(
        range=[0,20], gridcolor=T["grid"], linecolor=T["border2"],
        tickfont_color=T["muted"], title_font_color=T["muted"],
        title_text="Animals",
    ))

    # AMR — grouped bars
    amr_v = amr_findings[amr_findings["permissible"].notna()].copy()
    fig_amr = go.Figure()
    fig_amr.add_trace(go.Bar(
        x=amr_v["antibiotic"] + " / " + amr_v["sampleType"],
        y=amr_v["levelFound"], name="Level Found",
        marker_color=pal["c1"],
    ))
    fig_amr.add_trace(go.Scatter(
        x=amr_v["antibiotic"] + " / " + amr_v["sampleType"],
        y=amr_v["permissible"], name="Permissible Limit",
        mode="markers", marker=dict(color="#ef4444", size=14,
            symbol="line-ew", line=dict(width=3, color="#ef4444")),
    ))
    fig_amr.update_layout(**PL(pal, "AMR Residue vs Permissible Limits",
                                 yaxis_title="Concentration (mg/L)"))

    # Dogs gauge
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=550,
        title={"text":"Stray Dogs in Programme","font":{"color":pal["c1"],"size":13}},
        number={"font":{"color":pal["c1"],"size":42}},
        gauge=dict(
            axis=dict(range=[0,800], tickcolor=T["muted"], tickfont_color=T["muted"]),
            bar=dict(color=pal["c1"], thickness=0.28),
            bgcolor="#ffffff", bordercolor=T["border2"],
            steps=[
                dict(range=[0,200],  color="#fef3c7"),
                dict(range=[200,500],color="#fde68a"),
                dict(range=[500,700],color="#fcd34d"),
                dict(range=[700,800],color="#fca5a5"),
            ],
            threshold=dict(line=dict(color="#ef4444",width=2.5), value=700),
        ),
    ))
    fig_g.update_layout(**PL_nogauge(pal), height=250,
                         margin=dict(l=24,r=24,t=44,b=16))

    return html.Div([
        page_header("Animal Health Pillar",
                    "Stray dog management (ABC), rabies surveillance, livestock & antimicrobial resistance", pal),
        description_box(
            "The Animal Birth Control (ABC) programme managed 550 stray dogs and cats in Bettahalasuru. "
            "In March 2024, 17 dogs were neutered and vaccinated over 7 days. The rabies model shows that "
            "only ABC + Vaccination prevents exponential spread — ABC alone reduces growth but cannot halt it. "
            "AMR screening found doxycycline levels well within permissible limits — no immediate AMR risk.", pal),

        section_head("Animal Health Key Indicators", pal["c1"]),
        kpi_row([
            kpi_card("Dogs in Programme",  "550",    "animals",  pal["c1"], "Dogs & cats managed"),
            kpi_card("ABC Batch Mar 2024", "17",     "animals",  pal["c5"], "Neutered + vaccinated"),
            kpi_card("Rabies Rate",        "13",     "%",        "#ef4444", "Post-ABC cohort"),
            kpi_card("Livestock Monitored","700–1k", "animals",  pal["c4"], "Via Vet Department"),
            kpi_card("AMR Status",         "Safe",   "",         EN["c1"],  "Within permissible limits"),
        ]),

        grid2([
            chart_box(dcc.Graph(figure=fig_rab, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_abc, config={"displayModeBar":False})),
        ]),
        grid2([
            chart_box(dcc.Graph(figure=fig_amr, config={"displayModeBar":False})),
            chart_box(dcc.Graph(figure=fig_g,   config={"displayModeBar":False})),
        ]),

        section_head("Key Animal Health Insights", pal["c2"]),
        html.Div([
            insight_card(row["insight"], [pal["c1"],pal["c2"],pal["c3"]][i % 3])
            for i, (_, row) in enumerate(animal_insights.iterrows())
        ]),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════
def page_environment():
    pal = EN
    wq  = water_quality.copy()

    # Water quality scatter — coloured by status
    st_col = {
        "Unfit":       "#ef4444",
        "Treat First": "#f59e0b",
        "Borderline":  HU["c1"],
        "Agriculture": pal["c1"],
    }
    fig_wq = px.scatter(
        wq, x="TDS_ppm", y="DO_mg_L", color="drinking_status",
        color_discrete_map=st_col, size="turbidity_NTU", size_max=35,
        hover_name="source_name",
        title="Water Quality — TDS vs Dissolved Oxygen",
        labels={"TDS_ppm":"TDS (ppm)","DO_mg_L":"DO (mg/L)",
                "drinking_status":"Status"},
        hover_data=["pH","EC_mS","turbidity_NTU"],
    )
    fig_wq.add_vline(x=500, line_dash="dot", line_color=pal["c1"], line_width=1.5,
                     annotation_text="TDS safe ≤500",
                     annotation_font=dict(color=pal["c1"], size=10))
    fig_wq.add_hline(y=6, line_dash="dot", line_color=pal["c2"], line_width=1.5,
                     annotation_text="DO safe ≥6",
                     annotation_font=dict(color=pal["c2"], size=10))
    fig_wq.update_layout(**PL(pal))

    # Village CFU — gradient green
    fig_vc = px.bar(
        village_cfu.sort_values("mean_cfu"), x="mean_cfu", y="source", orientation="h",
        color="mean_cfu",
        color_continuous_scale=[[0,"#d1fae5"],[0.5,"#34d399"],[1,"#065f46"]],
        title="Village Water — Mean CFU/mL",
        labels={"mean_cfu":"CFU/mL","source":""},
    )
    fig_vc.update_layout(**PL(pal))
    fig_vc.update_coloraxes(showscale=False)

    # Lake CFU — gradient cyan
    fig_lc = px.bar(
        lake_cfu.sort_values("mean_cfu", ascending=False),
        x="sample", y="mean_cfu", color="mean_cfu",
        color_continuous_scale=[[0,"#cffafe"],[0.5,"#22d3ee"],[1,"#0e7490"]],
        title="Lake Entry Points — Mean CFU/mL",
        labels={"mean_cfu":"CFU/mL","sample":""},
    )
    fig_lc.update_layout(**PL(pal))
    fig_lc.update_coloraxes(showscale=False)
    fig_lc.update_xaxes(tickangle=-25)

    # Soil CFU — gradient lime
    fig_sc = px.bar(
        soil_cfu, x="sample", y="mean_cfu", color="mean_cfu",
        color_continuous_scale=[[0,"#ecfccb"],[0.5,"#a3e635"],[1,"#3f6212"]],
        title="Soil CFU by Site",
        labels={"mean_cfu":"CFU/mL","sample":""},
    )
    fig_sc.update_layout(**PL(pal))
    fig_sc.update_coloraxes(showscale=False)
    fig_sc.update_xaxes(tickangle=-10)

    # Gram staining donut — green vs grey
    gt = gram_total.iloc[0]
    fig_gr = go.Figure(go.Pie(
        labels=["Gram Negative","Gram Positive"],
        values=[gt["gram_negative_percent"], 100 - gt["gram_negative_percent"]],
        hole=0.58,
        marker_colors=[pal["c1"], T["border2"]],
        textfont_color=T["text"],
    ))
    fig_gr.update_layout(**PL_noax(pal, "Gram Staining — 26 Isolates"))
    fig_gr.update_traces(textfont_color=T["text"])

    # AQI gauge
    aqi_val = int(air_quality[air_quality["parameter"]=="AQI"]["value"].iloc[0])
    fig_aqi = go.Figure(go.Indicator(
        mode="gauge+number", value=aqi_val,
        title={"text":"Air Quality Index (AQI)","font":{"color":pal["c1"],"size":13}},
        number={"font":{"color":"#d97706","size":40}},
        gauge=dict(
            axis=dict(range=[0,200], tickcolor=T["muted"], tickfont_color=T["muted"]),
            bar=dict(color="#d97706", thickness=0.25),
            bgcolor="#ffffff", bordercolor=T["border2"],
            steps=[
                dict(range=[0,50],   color="#d1fae5"),
                dict(range=[50,100], color="#d1fae5"),
                dict(range=[100,150],color="#fef3c7"),
                dict(range=[150,200],color="#fee2e2"),
            ],
            threshold=dict(line=dict(color="#ef4444",width=2.5), value=150),
        ),
    ))
    fig_aqi.update_layout(**PL_nogauge(pal), height=250,
                           margin=dict(l=24,r=24,t=44,b=16))

    return html.Div([
        page_header("Environment Pillar",
                    "Water physico-chemistry, microbial load, gram staining, soil & air quality — Bettahalasuru", pal),
        description_box(
            "Samples were collected from 10 water sources, 3 soil sites, and ambient air. "
            "Household effluent had TDS of 1,420 ppm (safe limit: 500 ppm) and dissolved oxygen of just 0.08 mg/L — near anoxic. "
            "TNTC (Too Numerous To Count) bacterial colonies were found at multiple lake entry points. "
            "All 26 gram-stained isolates were Gram-negative, confirming faecal contamination. "
            "E. coli was present in all 3 soil sites.", pal),

        section_head("Environment Key Indicators", pal["c1"]),
        kpi_row([
            kpi_card("Household Effluent TDS","1,420","ppm",     "#ef4444", "Safe limit: 500 ppm"),
            kpi_card("Effluent DO",            "0.08","mg/L",    "#ef4444", "Near anoxic (safe: ≥6)"),
            kpi_card("Gram Negative",          "100", "%",       pal["c1"], "All 26 isolates"),
            kpi_card("Air Quality Index",      "135", "",        "#d97706", "Unhealthy for sensitive groups"),
            kpi_card("E. coli in Soil",        "3/3", "sites",   "#d97706", "All sites positive"),
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

        section_head("Microbial Status — Lake Entry Points", pal["c2"]),
        table_wrap([
            table_header([("Location",2),("NA Plate Count",1),("EMB Indicator",1),("Status",1)]),
            *[table_row_div([
                (row["location"], 2),
                (str(row["na_plate_count"]), 1),
                (str(row["emb_indicator"]), 1),
                (status_pill(row["microbial_status"],
                             {"High":"#fee2e2","Moderate":"#fef3c7"}.get(row["microbial_status"],"#d1fae5"),
                             {"High":"#dc2626","Moderate":"#d97706"}.get(row["microbial_status"],EN["c1"])), 1),
            ]) for _, row in microbial.iterrows()]
        ]),

        section_head("Water Sample Field Notes", pal["c3"]),
        table_wrap([
            table_header([("ID",0.5),("Sample Label",2),("Field Observation",4)]),
            *[table_row_div([
                (f"S{int(row['Sample no.'])}", 0.5),
                (str(row["Label"]).strip(), 2),
                (str(row["Label Description"])[:120]+("…" if len(str(row["Label Description"]))>120 else ""), 4),
            ]) for _, row in physiochem_vill.iterrows() if pd.notna(row["Label Description"])]
        ]),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INTERCONNECTIONS
# ══════════════════════════════════════════════════════════════════════════════
def page_interconnections():
    pal = OV

    # Zoonotic — each transmission type a different domain colour
    zoo = zoonotic.copy()
    fig_zoo = go.Figure()
    for col, color, name in [
        ("directContact",  HU["c1"], "Direct Contact"),
        ("environmental",  EN["c1"], "Environmental"),
        ("foodWater",      AN["c1"], "Food / Water"),
        ("vectorMediated", OV["c3"], "Vector Mediated"),
    ]:
        fig_zoo.add_trace(go.Bar(x=zoo["pathway"], y=zoo[col],
                                  name=name, marker_color=color))
    fig_zoo.update_layout(**PL(pal, "Zoonotic Transmission Pathways",
                                 barmode="stack", yaxis_title="Transmission %"))
    fig_zoo.update_xaxes(tickangle=-15)

    # Rainfall vs disease
    fig_rain = go.Figure()
    for col, color, name in [
        ("dengueCases",   HU["c2"], "Dengue"),
        ("malariaCases",  HU["c1"], "Malaria"),
        ("leptospirosis", AN["c1"], "Leptospirosis"),
    ]:
        fig_rain.add_trace(go.Scatter(
            x=rainfall_disease["rainfallIndex"], y=rainfall_disease[col],
            name=name, mode="markers+lines",
            marker=dict(size=10, color=color),
            line=dict(color=color, width=1.8),
            text=rainfall_disease["year"],
            hovertemplate=f"<b>{name}</b><br>Rainfall: %{{x}}<br>Cases: %{{y}}<br>Year: %{{text}}<extra></extra>",
        ))
    fig_rain.update_layout(**PL(pal, "Rainfall Index vs Vector Disease Cases",
                                  xaxis_title="Rainfall Index", yaxis_title="Cases"))

    # Interaction strength — before/after
    ints = interaction_str.copy()
    fig_int = go.Figure()
    fig_int.add_trace(go.Bar(x=ints["interaction"], y=ints["current"],
                              name="Current Strength", marker_color="#ef4444"))
    fig_int.add_trace(go.Bar(x=ints["interaction"], y=ints["afterIntervention"],
                              name="After Intervention", marker_color=EN["c1"]))
    fig_int.update_layout(**PL(pal, "Cross-Pillar Interaction — Before vs After",
                                 barmode="group", yaxis_title="Interaction Score"))

    # Risk bubble
    rm = risk_matrix.copy()
    def urgency_color(u):
        if u >= 85: return "#ef4444"
        if u >= 70: return AN["c1"]
        return EN["c1"]
    fig_bub = px.scatter(
        rm, x="likelihood", y="impact", size="urgency",
        hover_name="factor", text="factor", size_max=55,
        color="urgency",
        color_continuous_scale=[[0,"#d1fae5"],[0.4,"#fbbf24"],[1,"#ef4444"]],
        title="Risk Matrix — Likelihood vs Impact (size = Urgency)",
        labels={"likelihood":"Likelihood (%)","impact":"Impact Score","urgency":"Urgency"},
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
            "One Health recognises that human, animal, and environmental health cannot be separated. "
            "Household effluent enters the lake (Human→Environment), livestock excreta contaminates soil and water "
            "(Animal→Environment), and contaminated water drives disease burden (Environment→Human). "
            "The interaction strength chart shows that full One Health intervention can reduce every "
            "pillar-to-pillar score by 40–65%. The rainfall data confirms that monsoon seasons are the "
            "highest-risk windows for dengue, malaria, and leptospirosis simultaneously.", pal),

        section_head("Interconnection Key Indicators", pal["c1"]),
        kpi_row([
            kpi_card("Top Risk — Urgency",  "95",   "score",        "#ef4444", "Water contamination"),
            kpi_card("Rainfall Correlation","High", "",             pal["c2"], "Dengue spike 2022"),
            kpi_card("Lepto — Env route",  "60%",  "environmental",EN["c1"],  "Soil/water dominant"),
            kpi_card("Rabies — ABC+Vacc",  "86%",  "reduction",    AN["c3"],  "vs no intervention yr 5"),
            kpi_card("Full OH by 2030",    "−80%", "burden",       EN["c1"],  "vs doing nothing"),
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
# NAV + ROUTING
# ══════════════════════════════════════════════════════════════════════════════
TAB_CFG = [
    ("overview",         "Overview",          OV["c1"]),
    ("human",            "Human Health",      HU["c1"]),
    ("animal",           "Animal Health",     AN["c1"]),
    ("environment",      "Environment",       EN["c1"]),
    ("interconnections", "Interconnections",  OV["c2"]),
]

def nav_header_comp():
    return html.Div([
        html.Div([
            html.Span("●", style={"color":EN["c1"],"marginRight":"6px","fontSize":"11px"}),
            html.Span("●", style={"color":HU["c1"],"marginRight":"6px","fontSize":"11px"}),
            html.Span("●", style={"color":AN["c1"],"marginRight":"14px","fontSize":"11px"}),
            html.Span("ONE HEALTH DASHBOARD", style={
                "fontFamily":"'Inter',sans-serif","fontSize":"14px",
                "fontWeight":"700","color":T["text"],"letterSpacing":"2px",
            }),
            html.Span("  Bettahalasuru Village Study", style={
                "fontSize":"12px","color":T["muted"],"marginLeft":"10px",
            }),
        ], style={"display":"flex","alignItems":"center"}),
        html.Div("● LIVE", style={"fontSize":"10px","color":EN["c1"],
                                    "fontWeight":"700","letterSpacing":"2px"}),
    ], style={
        "display":"flex","justifyContent":"space-between","alignItems":"center",
        "padding":"13px 28px","borderBottom":f"1px solid {T['border']}",
        "background":T["surface"],"position":"sticky","top":"0","zIndex":"300",
        "boxShadow":"0 1px 6px rgba(0,0,0,0.07)",
    })

app.layout = html.Div([
    html.Link(rel="stylesheet",
              href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"),
    dcc.Store(id="tab-store", data="overview"),
    nav_header_comp(),
    # Tab bar
    dcc.Tabs(
        id="main-tabs", value="overview",
        children=[
            dcc.Tab(
                label=label, value=val,
                style={
                    "padding":"10px 20px","fontSize":"12px","fontWeight":"600",
                    "letterSpacing":"0.3px","fontFamily":"'Inter',sans-serif",
                    "color":T["muted"],"background":"transparent",
                    "borderBottom":"3px solid transparent","border":"none",
                    "borderRadius":"0",
                },
                selected_style={
                    "padding":"10px 20px","fontSize":"12px","fontWeight":"700",
                    "letterSpacing":"0.3px","fontFamily":"'Inter',sans-serif",
                    "color":color,"background":T["subtle"],
                    "borderBottom":f"3px solid {color}","border":"none",
                    "borderRadius":"0",
                },
            )
            for val, label, color in TAB_CFG
        ],
        style={"background":T["surface"],"borderBottom":f"1px solid {T['border']}",
               "padding":"0 24px","boxShadow":"0 1px 3px rgba(0,0,0,0.04)"},
    ),
    html.Div(id="page-content", style={
        "padding":"28px 32px","maxWidth":"1440px","margin":"0 auto",
    }),
], style={"background":T["bg"],"minHeight":"100vh",
           "fontFamily":"'Inter',sans-serif","color":T["text"]})


@app.callback(Output("page-content","children"), Input("main-tabs","value"))
def render_page(tab):
    pages = {
        "overview":         page_overview,
        "human":            page_human,
        "animal":           page_animal,
        "environment":      page_environment,
        "interconnections": page_interconnections,
    }
    return pages.get(tab, page_overview)()


if __name__ == "__main__":
    app.run(debug=True)
    #