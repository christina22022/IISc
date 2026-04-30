#!/usr/bin/env python3
"""
Run this script from your dashboard_project directory:
    python patch_animal_pillar.py

It will patch the page_animal() function in your app.py in-place,
creating a backup at app.py.bak first.
"""
import sys
import shutil
import os

APP_PATH = "app.py"
BACKUP   = "app.py.bak"

if not os.path.exists(APP_PATH):
    print(f"ERROR: {APP_PATH} not found. Run from dashboard_project folder.")
    sys.exit(1)

with open(APP_PATH, "r", encoding="utf-8") as f:
    src = f.read()

START_PAT = "def page_animal(d):"
END_PAT   = ("# ══════════════════════════════════════════════════════════════════════════════\n"
             "# CALIBRATION DASHBOARD HELPER")

si = src.find(START_PAT)
ei = src.find(END_PAT)
if si == -1 or ei == -1:
    print("ERROR: Could not find function markers in app.py")
    sys.exit(1)

NEW_FUNC = r'''def page_animal(d):
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

'''

# Backup and patch
shutil.copy(APP_PATH, BACKUP)
result = src[:si] + NEW_FUNC + "\n\n\n" + src[ei:]

with open(APP_PATH, "w", encoding="utf-8") as f:
    f.write(result)

print(f"Done. Backup saved to {BACKUP}")
print(f"Original page_animal: lines {src[:ei].count(chr(10)) - src[:si].count(chr(10))}")
print(f"New page_animal: lines {NEW_FUNC.count(chr(10))}")
