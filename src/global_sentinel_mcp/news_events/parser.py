"""GDELT 2.0 export file parser with authoritative 61-column schema."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

# Authoritative GDELT 2.0 Events column list — 61 columns, indexes 0–60.
# Source: linwoodc3/gdelt2HeaderRows
GDELT_COLUMNS: list[str] = [
    "GLOBALEVENTID",       # 0
    "SQLDATE",             # 1
    "MonthYear",           # 2
    "Year",                # 3
    "FractionDate",        # 4
    "Actor1Code",          # 5
    "Actor1Name",          # 6
    "Actor1CountryCode",   # 7
    "Actor1KnownGroupCode",  # 8
    "Actor1EthnicCode",    # 9
    "Actor1Religion1Code", # 10
    "Actor1Religion2Code", # 11
    "Actor1Type1Code",     # 12
    "Actor1Type2Code",     # 13
    "Actor1Type3Code",     # 14
    "Actor2Code",          # 15
    "Actor2Name",          # 16
    "Actor2CountryCode",   # 17
    "Actor2KnownGroupCode",  # 18
    "Actor2EthnicCode",    # 19
    "Actor2Religion1Code", # 20
    "Actor2Religion2Code", # 21
    "Actor2Type1Code",     # 22
    "Actor2Type2Code",     # 23
    "Actor2Type3Code",     # 24
    "IsRootEvent",         # 25
    "EventCode",           # 26
    "EventBaseCode",       # 27
    "EventRootCode",       # 28
    "QuadClass",           # 29
    "GoldsteinScale",      # 30
    "NumMentions",         # 31
    "NumSources",          # 32
    "NumArticles",         # 33
    "AvgTone",             # 34
    "Actor1Geo_Type",      # 35
    "Actor1Geo_FullName",  # 36
    "Actor1Geo_CountryCode",  # 37
    "Actor1Geo_ADM1Code",    # 38
    "Actor1Geo_ADM2Code",    # 39
    "Actor1Geo_Lat",       # 40
    "Actor1Geo_Long",      # 41
    "Actor1Geo_FeatureID", # 42
    "Actor2Geo_Type",      # 43
    "Actor2Geo_FullName",  # 44
    "Actor2Geo_CountryCode",  # 45
    "Actor2Geo_ADM1Code",    # 46
    "Actor2Geo_ADM2Code",    # 47
    "Actor2Geo_Lat",       # 48
    "Actor2Geo_Long",      # 49
    "Actor2Geo_FeatureID", # 50
    "ActionGeo_Type",      # 51
    "ActionGeo_FullName",  # 52
    "ActionGeo_CountryCode",  # 53
    "ActionGeo_ADM1Code",    # 54
    "ActionGeo_ADM2Code",    # 55
    "ActionGeo_Lat",       # 56
    "ActionGeo_Long",      # 57
    "ActionGeo_FeatureID", # 58
    "DATEADDED",           # 59
    "SOURCEURL",           # 60
]

assert len(GDELT_COLUMNS) == 61, f"Expected 61 columns, got {len(GDELT_COLUMNS)}"


def parse_export_zip(content: bytes) -> pd.DataFrame:
    """Unzip an in-memory GDELT export CSV.zip and return a DataFrame."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".CSV")]
        if not csv_names:
            return pd.DataFrame(columns=GDELT_COLUMNS)
        with zf.open(csv_names[0]) as f:
            df = pd.read_csv(
                f,
                sep="\t",
                names=GDELT_COLUMNS,
                header=None,
                dtype=str,
                on_bad_lines="skip",
            )

    # Coerce numeric columns
    df["GoldsteinScale"] = pd.to_numeric(df["GoldsteinScale"], errors="coerce")
    df["NumArticles"] = pd.to_numeric(df["NumArticles"], errors="coerce").fillna(0).astype(int)

    return df
