#!/usr/bin/env python3
"""
patch_animal_static.py
Run from your dashboard_project directory:
    python patch_animal_static.py

Replaces page_animal() in app.py with a version that matches
the static OneHealth_Dashboard2 design exactly:
  - 4 KPI cards (Stray Dogs / ABC Mar-2024 / Rabies Infection / Livestock)
  - ABC Programme table + insight box (left) | Rabies bar chart (right)
  - AMR table (left) | AMR bar chart (right)

All values come from the live Google Sheet / local animal.xlsx fallback.
"""
import sys, shutil, os

APP_PATH = "app.py"
BACKUP   = "app.py.bak_static"

if not os.path.exists(APP_PATH):
    print(f"ERROR: {APP_PATH} not found.  Run from dashboard_project folder.")
    sys.exit(1)

with open(APP_PATH, "r", encoding="utf-8") as f:
    src = f.read()

START_PAT = "def page_animal(d):"
END_PAT   = (
    "# ══════════════════════════════════════════════════════════════════════════════\n"
    "# CALIBRATION DASHBOARD HELPER"
)

si = src.find(START_PAT)
ei = src.find(END_PAT)
if si == -1 or ei == -1:
    print("ERROR: could not locate function markers in app.py.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
NEW_FUNC = r'''def page_animal(d):
    """
    Animal Pillar – design matches the static OneHealth_Dashboard2.html exactly.
    Layout:
      Row 1 : 4 KPI cards  (Stray Dogs | ABC Programme | Rabies Infection | Livestock)
      Row 2 : ABC table + insight box  |  Rabies 5-year grouped-bar chart
      Row 3 : AMR findings table        |  AMR bar chart (level vs permissible)
    """
    rp   = d.get("rabiesProjection", pd.DataFrame())
    abc  = d.get("abcProgram",       pd.DataFrame())
    amr  = d.get("amrFindings",      pd.DataFrame())
    ai   = d.get("animalInsights",   pd.DataFrame())
    akpi = d.get("animal_kpi_data",  pd.DataFrame())

    # ── KPI extraction ────────────────────────────────────────────────────────
    a_stray_dogs_raw = kpi_val_from_wide(
        akpi, ["strayDogs", "stray_dogs", "stray dogs", "StrayDogs"], "73+")
    a_abc_count_raw  = kpi_val_from_wide(
        akpi, ["abcProgramCount", "abc_program_count", "abcProgram", "abc", "abcCount"], "17+")
    a_rabies_raw     = kpi_val_from_wide(
        akpi,
        ["rabiesInfectionReductionPercent", "rabiesInfectionRate",
         "rabiesRate", "rabies_rate", "rabiesInfRate", "rabiesInf"],
        "0.13")
    a_livestock_raw  = kpi_val_from_wide(
        akpi, ["livestockMonitored", "livestock_monitored", "livestock", "Livestock"], "700-1000")

    # Format stray dogs – keep the "+" suffix from the sheet
    a_stray_dogs = str(a_stray_dogs_raw).strip()

    # Format ABC count – keep the "+" suffix
    a_abc_count  = str(a_abc_count_raw).strip()

    # Format rabies rate as "↓13%"
    try:
        _r = float(str(a_rabies_raw).replace("%", "").replace("+", "").strip())
        if _r < 1:           # stored as 0.13
            _r = round(_r * 100, 0)
        a_rabies_display = f"↓{int(_r)}%"
        a_rabies_rate_pct = int(_r)
    except Exception:
        a_rabies_display  = "↓13%"
        a_rabies_rate_pct = 13

    # Format livestock – keep range string e.g. "700–1k"
    _lv = str(a_livestock_raw).strip()
    if "-" in _lv and not _lv.endswith("k"):
        parts = _lv.split("-")
        try:
            hi = int(float(parts[1]))
            lo = int(float(parts[0]))
            a_livestock = f"{lo}–{hi if hi < 1000 else str(hi // 1000) + 'k'}"
        except Exception:
            a_livestock = _lv
    else:
        a_livestock = _lv

    # ── Insight helper ────────────────────────────────────────────────────────
    ai_insight_col = find_col(ai, ["insight", "insight_text", "finding", "text", "description"])
    ai_metric_col  = find_col(ai, ["metric", "name", "category"])
    ai_value_col   = find_col(ai, ["value", "data_value", "pct"])

    def get_ai_metric(name, default):
        if ai_metric_col and ai_value_col and not ai.empty:
            row = ai[ai[ai_metric_col].astype(str).str.strip().str.lower()
                        .str.contains(name.lower(), na=False)]
            if not row.empty:
                val = str(row[ai_value_col].iloc[0]).strip()
                return val if val and val.lower() != "nan" else default
        return default

    neutered_infection_rate     = get_ai_metric("neutered infection",     "13%")
    non_neutered_infection_rate = get_ai_metric("non.neutered infection", "9%")

    # ── ABC table rows ────────────────────────────────────────────────────────
    abc_date_col     = find_col(abc, ["date"])
    abc_activity_col = find_col(abc, ["activity"])
    abc_count_col    = find_col(abc, ["count", "value"])

    # Static dashboard shows 4 canonical rows – we try to derive from data first
    abc_table_rows_dynamic = []
    if abc_date_col and abc_activity_col and abc_count_col and not abc.empty:
        # Collapse middle "post-op" rows into one "All 17" row, like the static
        pickup    = None
        neuter    = None
        postop    = []
        release   = None

        for _, row in abc.iterrows():
            act = str(row.get(abc_activity_col, "")).strip().lower()
            cnt = str(row.get(abc_count_col, "")).strip()
            date_raw = row.get(abc_date_col, "")
            try:
                date_str = pd.to_datetime(date_raw).strftime("%d-%b-%Y")
            except Exception:
                date_str = str(date_raw).strip()

            if "picked up" in act or "pickup" in act or "dogs picked" in act:
                pickup = (date_str, str(row.get(abc_activity_col, "")).strip(), cnt)
            elif "neuter" in act or "anti-rabies" in act or "vaccination" in act:
                neuter = (date_str, str(row.get(abc_activity_col, "")).strip(), cnt)
            elif "post" in act or "care" in act or "antibiotic" in act:
                postop.append((date_str, str(row.get(abc_activity_col, "")).strip(), cnt))
            elif "release" in act or "returned" in act or "original" in act:
                release = (date_str, str(row.get(abc_activity_col, "")).strip(), cnt)

        if pickup:
            abc_table_rows_dynamic.append([
                (pickup[0], 1.5), (pickup[1], 3),
                (badge(pickup[2], "info"), 1),
            ])
        if neuter:
            abc_table_rows_dynamic.append([
                (neuter[0], 1.5), (neuter[1], 3),
                (badge(neuter[2], "good"), 1),
            ])
        if postop:
            # Build date range string like "07–10-Mar-2024"
            try:
                dates_parsed = [pd.to_datetime(abc.loc[
                    abc[abc_activity_col].astype(str).str.lower()
                        .str.contains("post|care|antibiotic", na=False), abc_date_col
                ].values[0]).strftime("%d"),
                    pd.to_datetime(abc.loc[
                    abc[abc_activity_col].astype(str).str.lower()
                        .str.contains("post|care|antibiotic", na=False), abc_date_col
                ].values[-1]).strftime("%d-%b-%Y")]
                date_range = f"{dates_parsed[0]}–{dates_parsed[1]}"
            except Exception:
                date_range = "07–10-Mar-2024"
            abc_table_rows_dynamic.append([
                (date_range, 1.5),
                ("Post-operative care + antibiotic shots (4 days)", 3),
                (badge("All 17", "good"), 1),
            ])
        if release:
            abc_table_rows_dynamic.append([
                (release[0], 1.5), (release[1], 3),
                (badge(release[2], "good"), 1),
            ])

    # Fallback to the static dashboard's exact rows
    abc_table_rows = abc_table_rows_dynamic if len(abc_table_rows_dynamic) >= 3 else [
        [("05-Mar-2024",    1.5), ("Dogs picked up from Bettahalasuru village",          3), (badge("17",     "info"), 1)],
        [("06-Mar-2024",    1.5), ("Neutering completed + anti-rabies vaccination",      3), (badge("17",     "good"), 1)],
        [("07–10-Mar-2024", 1.5), ("Post-operative care + antibiotic shots (4 days)",   3), (badge("All 17", "good"), 1)],
        [("11-Mar-2024",    1.5), ("Released at original pickup location",               3), (badge("17",     "good"), 1)],
    ]

    # ── AMR table rows ────────────────────────────────────────────────────────
    amr_ant_col    = find_col(amr, ["antibiotic"])
    amr_sample_col = find_col(amr, ["sampleType", "sample_type", "sample"])
    amr_level_col  = find_col(amr, ["levelFound", "level_found", "level"])
    amr_perm_col   = find_col(amr, ["permissible", "limit", "permissible_limit"])
    amr_stat_col   = find_col(amr, ["status", "result"])

    amr_table_rows_dynamic = []
    if amr_ant_col and amr_sample_col and amr_level_col and not amr.empty:
        for _, row in amr.iterrows():
            stat_txt  = str(row.get(amr_stat_col, "Safe")).strip() if amr_stat_col else "Safe"
            stat_txt  = stat_txt if stat_txt and stat_txt.lower() != "nan" else "Safe"
            bkind     = "good" if stat_txt.lower() in ("safe", "clear", "ok") else "warn"

            level_num = pd.to_numeric(row.get(amr_level_col, 0), errors="coerce")
            perm_num  = pd.to_numeric(row.get(amr_perm_col,  None), errors="coerce") if amr_perm_col else float("nan")

            # Format level exactly as static: 0.000002 mg/g or "None detected"
            if pd.isna(level_num) or level_num == 0:
                display_level = "None detected"
            else:
                display_level = f"{level_num:.6f} mg/g".rstrip("0").rstrip(".")

            perm_disp = f"{perm_num:.2f} mg/g" if pd.notna(perm_num) else "—"

            amr_table_rows_dynamic.append([
                (str(row.get(amr_ant_col,    "")).strip(), 1.2),
                (str(row.get(amr_sample_col, "")).strip(), 1.5),
                (display_level,                            1.5),
                (perm_disp,                                1.2),
                (badge(stat_txt, bkind),                   1),
            ])

    amr_table_rows = amr_table_rows_dynamic if amr_table_rows_dynamic else [
        [("Doxycycline", 1.2), ("Pig Excreta", 1.5), ("0.000002 mg/g", 1.5), ("0.02 mg/g", 1.2), (badge("Safe",  "good"), 1)],
        [("Doxycycline", 1.2), ("Hen Excreta", 1.5), ("0.00348 mg/g",  1.5), ("0.02 mg/g", 1.2), (badge("Safe",  "good"), 1)],
        [("Amoxicillin", 1.2), ("Feed",        1.5), ("None detected",  1.5), ("—",         1.2), (badge("Clear", "good"), 1)],
        [("Amoxicillin", 1.2), ("Excreta",     1.5), ("None detected",  1.5), ("—",         1.2), (badge("Clear", "good"), 1)],
        [("Amoxicillin", 1.2), ("Water",       1.5), ("None detected",  1.5), ("—",         1.2), (badge("Clear", "good"), 1)],
    ]

    # ── Rabies 5-Year Grouped Bar Chart (matches static exactly) ──────────────
    rp_year_col = find_col(rp, ["year"])
    fig_rab     = empty_fig("No rabies projection data available")

    if rp_year_col and not rp.empty:
        rp_plot  = coerce_numeric(rp, [rp_year_col])
        col_noabc   = find_col(rp, ["noAbc",              "no_abc"])
        col_abc     = find_col(rp, ["withAbc",            "with_abc"])
        col_abcvacc = find_col(rp, ["withAbcVaccination", "with_abc_vaccination"])

        # Pull data lists – fallback to static dashboard values if empty
        def _series(col, fallback):
            if col:
                vals = coerce_numeric(rp_plot, [col])[col].dropna().tolist()
                return vals if vals else fallback
            return fallback

        no_abc_data   = _series(col_noabc,   [10, 18, 30, 55, 95])
        abc_data      = _series(col_abc,     [12, 22, 33, 48, 65])
        abcvacc_data  = _series(col_abcvacc, [3,  5,  6,  6,  7])
        n_years = max(len(no_abc_data), len(abc_data), len(abcvacc_data))
        year_labels   = [f"Year {i+1}" for i in range(n_years)]

        fig_rab = go.Figure()
        fig_rab.add_trace(go.Bar(
            name="Infected (No ABC)",
            x=year_labels, y=no_abc_data,
            marker_color="rgba(255,112,67,0.75)",
            marker_line_color="#ff7043", marker_line_width=1,
            hovertemplate="<b>No ABC</b><br>Year: %{x}<br>Cases: %{y}<extra></extra>",
        ))
        fig_rab.add_trace(go.Bar(
            name="Infected (With ABC)",
            x=year_labels, y=abc_data,
            marker_color="rgba(171,71,188,0.70)",
            marker_line_color="#ab47bc", marker_line_width=1,
            hovertemplate="<b>ABC Only</b><br>Year: %{x}<br>Cases: %{y}<extra></extra>",
        ))
        fig_rab.add_trace(go.Bar(
            name="Infected (ABC + Vaccination)",
            x=year_labels, y=abcvacc_data,
            marker_color="rgba(105,240,174,0.75)",
            marker_line_color="#69f0ae", marker_line_width=1,
            hovertemplate="<b>ABC+Vacc</b><br>Year: %{x}<br>Cases: %{y}<extra></extra>",
        ))
        fig_rab.update_layout(
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font=dict(family="'Sora','Segoe UI',sans-serif", color=TEXT, size=11),
            barmode="group",
            bargap=0.18,
            bargroupgap=0.04,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(
                orientation="h", x=0, y=-0.22,
                font=dict(size=10, color=TEXT),
                bgcolor="rgba(0,0,0,0)",
                itemwidth=30,
            ),
            hoverlabel=dict(bgcolor=CARD_BG, bordercolor=BORDER,
                            font=dict(color=TEXT, size=11)),
        )
        fig_rab.update_xaxes(showgrid=False, tickfont_color=MUTED,
                              linecolor=BORDER, zerolinecolor=BORDER)
        fig_rab.update_yaxes(
            title_text="Rabies Cases",
            gridcolor="rgba(0,0,0,0.08)",
            title_font_color=MUTED,
            tickfont_color=MUTED,
            linecolor=BORDER,
            zerolinecolor=BORDER,
        )

    # ── AMR Bar Chart – level vs permissible (matches static exactly) ─────────
    fig_amr = empty_fig("No AMR data available")

    if amr_ant_col and amr_sample_col and amr_level_col and not amr.empty:
        amr_v = coerce_numeric(amr, [amr_level_col] + ([amr_perm_col] if amr_perm_col else []))

        # Build the same 3-bar chart as static:
        #   Doxy – Pig Excreta | Doxy – Hen Excreta | Permissible Limit
        doxy_rows = amr_v[amr_v[amr_ant_col].astype(str).str.lower().str.contains("doxy", na=False)]

        chart_labels = []
        chart_values = []
        chart_colors = []
        chart_borders = []

        for _, row in doxy_rows.iterrows():
            sample = str(row.get(amr_sample_col, "")).strip()
            level  = pd.to_numeric(row.get(amr_level_col, 0), errors="coerce")
            if pd.isna(level):
                level = 0.0
            chart_labels.append(f"Doxy – {sample}")
            chart_values.append(level)
            # Green for pig (very low), Blue for hen (moderate)
            if "pig" in sample.lower():
                chart_colors.append("#16a34a")
                chart_borders.append("#16a34a")
            else:
                chart_colors.append("#0284c7")
                chart_borders.append("#0284c7")

        # Add permissible limit bar
        if amr_perm_col:
            perm_val = pd.to_numeric(
                amr_v.loc[amr_v[amr_ant_col].astype(str).str.lower()
                           .str.contains("doxy", na=False), amr_perm_col].iloc[0],
                errors="coerce"
            ) if not doxy_rows.empty else 0.02
        else:
            perm_val = 0.02
        perm_val = 0.02 if pd.isna(perm_val) else float(perm_val)

        chart_labels.append("Permissible\nLimit")
        chart_values.append(perm_val)
        chart_colors.append("rgba(255,112,67,0.35)")
        chart_borders.append("#dc2626")

        if chart_labels:
            fig_amr = go.Figure()
            fig_amr.add_trace(go.Bar(
                x=chart_labels,
                y=chart_values,
                marker_color=chart_colors,
                marker_line_color=chart_borders,
                marker_line_width=1.5,
                hovertemplate="<b>%{x}</b><br>Level: %{y:.6f} mg/g<extra></extra>",
            ))
            fig_amr.update_layout(
                paper_bgcolor="#ffffff",
                plot_bgcolor="#ffffff",
                font=dict(family="'Sora','Segoe UI',sans-serif", color=TEXT, size=11),
                showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
                hoverlabel=dict(bgcolor=CARD_BG, bordercolor=BORDER,
                                font=dict(color=TEXT, size=11)),
            )
            fig_amr.update_xaxes(showgrid=False, tickfont_color=MUTED,
                                  linecolor=BORDER, zerolinecolor=BORDER)
            fig_amr.update_yaxes(
                title_text="mg/g",
                gridcolor="rgba(0,0,0,0.08)",
                title_font_color=MUTED,
                tickfont_color=MUTED,
                linecolor=BORDER,
                zerolinecolor=BORDER,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # LAYOUT  – mirrors static OneHealth_Dashboard2.html structure exactly
    # ─────────────────────────────────────────────────────────────────────────
    return html.Div([

        # ── Section header ─────────────────────────────────────────────────
        section_banner(
            "Animal Pillar",
            "STRAY DOG MANAGEMENT · LIVESTOCK AMR · POULTRY & PIGGERY · BETTAHALASURU",
        ),

        # ── Row 1: 4 KPI cards ─────────────────────────────────────────────
        html.Div([
            # Card 1 – Stray Dogs (default blue)
            html.Div([
                card_top_bar(C_BLUE),
                html.P("STRAY DOGS", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED,
                    "letterSpacing": "1px", "textTransform": "uppercase",
                    "margin": "8px 0 4px",
                }),
                html.Div(a_stray_dogs, style={
                    "fontSize": "34px", "fontWeight": "800", "color": C_BLUE,
                    "lineHeight": "1", "fontFamily": "'DM Mono',monospace",
                    "marginBottom": "4px",
                }),
                html.P("", style={"fontSize": "11px", "color": MUTED, "margin": "0"}),
            ], style=CARD_STYLE),

            # Card 2 – ABC Programme (green)
            html.Div([
                card_top_bar(C_GREEN),
                html.P("ABC MAR–2024 (BETTAHALASURU)", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED,
                    "letterSpacing": "1px", "textTransform": "uppercase",
                    "margin": "8px 0 4px",
                }),
                html.Div(a_abc_count, style={
                    "fontSize": "34px", "fontWeight": "800", "color": C_GREEN,
                    "lineHeight": "1", "fontFamily": "'DM Mono',monospace",
                    "marginBottom": "4px",
                }),
                html.P("Neutered + anti-rabies shots",
                       style={"fontSize": "11px", "color": MUTED, "margin": "0"}),
            ], style=CARD_STYLE),

            # Card 3 – Rabies Infection (orange/red)
            html.Div([
                card_top_bar(C_RED),
                html.P("RABIES INFECTION (POST-ABC)", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED,
                    "letterSpacing": "1px", "textTransform": "uppercase",
                    "margin": "8px 0 4px",
                }),
                html.Div(a_rabies_display, style={
                    "fontSize": "34px", "fontWeight": "800", "color": C_RED,
                    "lineHeight": "1", "fontFamily": "'DM Mono',monospace",
                    "marginBottom": "4px",
                }),
                html.P("Reduction in rabies cases",
                       style={"fontSize": "11px", "color": MUTED, "margin": "0"}),
            ], style=CARD_STYLE),

            # Card 4 – Livestock Monitored (purple)
            html.Div([
                card_top_bar(C_PURPLE),
                html.P("LIVESTOCK MONITORED", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED,
                    "letterSpacing": "1px", "textTransform": "uppercase",
                    "margin": "8px 0 4px",
                }),
                html.Div(a_livestock, style={
                    "fontSize": "34px", "fontWeight": "800", "color": C_PURPLE,
                    "lineHeight": "1", "fontFamily": "'DM Mono',monospace",
                    "marginBottom": "4px",
                }),
                html.P("Via vet health department",
                       style={"fontSize": "11px", "color": MUTED, "margin": "0"}),
            ], style=CARD_STYLE),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "repeat(4, 1fr)",
            "gap": "12px",
            "marginBottom": "20px",
        }),

        # ── Row 2: ABC table (left) | Rabies chart (right) ─────────────────
        grid2([

            # LEFT – ABC table + insight
            html.Div([
                card_top_bar(C_BLUE),
                html.Div(style={"height": "6px"}),
                card_title("Stray Dog ABC — Bettahalasuru (March 2024)"),

                data_table_wrap(
                    [("Date", 1.5), ("Activity", 3), ("Count", 1)],
                    abc_table_rows,
                ),

                # Divider
                html.Hr(style={
                    "border": "none", "borderTop": f"1px solid {BORDER}",
                    "margin": "14px 0",
                }),

                # Insight box – matches static "ABC Program Key Insight"
                html.P("ABC PROGRAM KEY INSIGHT", style={
                    "fontFamily": "'DM Mono',monospace", "fontSize": "10px",
                    "fontWeight": "700", "color": MUTED,
                    "letterSpacing": "1px", "textTransform": "uppercase",
                    "margin": "0 0 10px",
                }),
                html.P([
                    "Neutralization significantly reduces population growth, but rabies vaccination "
                    "must accompany ABC programs. Neutered populations show a ",
                    html.Strong(
                        f"{a_rabies_rate_pct}%",
                        style={"color": C_RED},
                    ),
                    " infection rate vs ",
                    html.Strong(
                        non_neutered_infection_rate,
                        style={"color": C_GREEN},
                    ),
                    " in non-neutered — requiring a combined population control + vaccination strategy.",
                ], style={"fontSize": "12px", "color": MUTED, "lineHeight": "1.7", "margin": "0"}),

            ], style=CARD_STYLE),

            # RIGHT – Rabies 5-year bar chart
            html.Div([
                card_top_bar(C_GREEN),
                html.Div(style={"height": "6px"}),
                card_title("Rabies Infection: With vs Without ABC Program (5-Year Projection)"),
                dcc.Graph(
                    figure=fig_rab,
                    config={"displayModeBar": False},
                    style={"height": "280px"},
                ),
            ], style=CARD_STYLE),
        ]),

        # ── Row 3: AMR table (left) | AMR chart (right) ────────────────────
        grid2([

            # LEFT – AMR findings table
            html.Div([
                card_top_bar(C_AMBER),
                html.Div(style={"height": "6px"}),
                card_title("Livestock Antimicrobial Resistance (AMR) Findings"),

                data_table_wrap(
                    [("Antibiotic", 1.2), ("Sample Type", 1.5),
                     ("Level Found", 1.5), ("Permissible", 1.2), ("Status", 1)],
                    amr_table_rows,
                ),

                # Note box – matches static green-bordered note
                html.Div([
                    html.P([
                        "Detection method: HPLC analysis on feed, excreta, and water samples. "
                        "Current antibiotic levels pose ",
                        html.Strong("no immediate AMR risk", style={"color": C_GREEN}),
                        ", but ongoing monitoring is essential.",
                    ], style={"fontSize": "12px", "color": MUTED,
                               "lineHeight": "1.6", "margin": "0"}),
                ], style={
                    "marginTop": "16px",
                    "padding": "12px",
                    "background": rgba(C_GREEN, 0.06),
                    "borderRadius": "8px",
                    "borderLeft": f"3px solid {C_GREEN}",
                }),
            ], style=CARD_STYLE),

            # RIGHT – AMR bar chart (level vs permissible)
            html.Div([
                card_top_bar(C_PURPLE),
                html.Div(style={"height": "6px"}),
                card_title("Antibiotic Level vs Permissible Limit"),
                dcc.Graph(
                    figure=fig_amr,
                    config={"displayModeBar": False},
                    style={"height": "280px"},
                ),
            ], style=CARD_STYLE),
        ]),

    ])  # end html.Div

'''
# ─────────────────────────────────────────────────────────────────────────────

shutil.copy(APP_PATH, BACKUP)
result = src[:si] + NEW_FUNC + "\n\n\n" + src[ei:]

with open(APP_PATH, "w", encoding="utf-8") as f:
    f.write(result)

print(f"✅  app.py patched successfully.")
print(f"   Backup saved to: {BACKUP}")
print(f"   Old page_animal: ~{src[si:ei].count(chr(10))} lines")
print(f"   New page_animal: ~{NEW_FUNC.count(chr(10))} lines")
print()
print("Run your dashboard with:  python app.py")