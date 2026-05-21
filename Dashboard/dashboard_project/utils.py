import os

BASE_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={tab}"

VILLAGE_CONFIG = {
    "village1": {
        "name": "BETTAHALASURU",
        "overview_sheet": "19gLj_SxcjJCwppnn1Y7q_2MmXzdG_-ik",
        "human_sheet": "1kMzWtBm-cKM8kQLgGRnfCQS8_cxizlTm",
        "animal_sheet": "1hmixQht8zdETU0vA3w1-bduZeRqdp-2m",
        "environment_sheet": "1AGIFjGQy4Y2hpMjF-ZwfW5OVAOVMU04y",
        "interconnectedness_sheet": "1uYM6V-usylcrgVyD57J7stv-NGUKchBK",
    },
    "village2": {
        "name": "Village 2",
        "overview_sheet": "1rirF-jWznc0r6_7GKoRKKPk5gKFaS9XvefnVOoXxrzY",
        "human_sheet": "18hsiTzjLEpyzBgQffjiwSYGtRJ9z5CErXPa7jL1YwAs",
        "animal_sheet": "18hsiTzjLEpyzBgQffjiwSYGtRJ9z5CErXPa7jL1YwAs",
        "environment_sheet": "19fLxsu8N1oJbZYy6PeN6-OrvOVqdl4BzqyyJk5Nx7MQ",
        "interconnectedness_sheet": "1X1sO3dDjkve83bDCdl-6JR0Q-gp1wBYlyM_n0GC7muM",
    },
    "village3": {
        "name": "Village 3",
        "overview_sheet": "16qOZaoSGC4qJojdyREPT-5KBe7oiUlHBgymnsweAyV8",
        "human_sheet": "15zx59Ur6jJ2Jm4gp810TvQO9C0nPzEi_9aopd3AbLVo",
        "animal_sheet": "1pupQs4Meh8B9e_7rsCAVcZkcePksiVSZiBjnYhFsbaI",
        "environment_sheet": "1iKzI2I0EE1evn31DZrJyPE_FqQ5Zn03JX_9m5ELx1PA",
        "interconnectedness_sheet": "1RfTZ779n7s2ijZar4FqXRe-7Haec4reGVrDEaJP_VVg",
    },
    "village4": {
        "name": "Village 4",
        "overview_sheet": "1hm-t_N2ztGZUEFsQwtR872FvvPFirvUccOYbVWgFxYg",
        "human_sheet": "1yh8K61b-fEWWZ50QtHNTQ42mDLxHtxZWrqHpxv-fJ6o",
        "animal_sheet": "1TRT5UkZxRsiQJFGKZ8E_RX2whZHzOiVmmgi39IKATMc",
        "environment_sheet": "1J5GXl8OgreBu0eUUui3eryY2ZVEjwbXNscajCDP9SVU",
        "interconnectedness_sheet": "1mdQ7_ABCdtTtQa8YWG-ZOQLE7U4Tfpynw_aX8QJzzTE",
    },
}

C_BLUE = "#0284c7"
C_GREEN = "#16a34a"
C_RED = "#dc2626"
C_PURPLE = "#7e22ce"
C_AMBER = "#b45309"


def find_col(df, candidates):
    if df is None or getattr(df, "empty", True):
        return None
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for candidate in candidates:
        key = str(candidate).strip().lower()
        if key in lookup:
            return lookup[key]
    for col in df.columns:
        col_norm = str(col).strip().lower()
        if any(str(candidate).strip().lower() in col_norm for candidate in candidates):
            return col
    return None


def kpi_val(df, labels, default="-"):
    metric_col = find_col(df, ["metric", "name", "label", "indicator"])
    value_col = find_col(df, ["value", "data_value", "count", "number"])
    if metric_col and value_col:
        for label in labels:
            rows = df[df[metric_col].astype(str).str.lower().str.contains(str(label).lower(), na=False)]
            if not rows.empty:
                val = rows[value_col].iloc[0]
                return default if str(val).lower() == "nan" else val
    return default


def village_config(village_key):
    return VILLAGE_CONFIG.get(village_key, VILLAGE_CONFIG["village1"])

