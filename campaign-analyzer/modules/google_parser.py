"""
Google Ads CSV parser.

Normalizes exported Google Ads reports to the standard campaign schema.
Handles the default EN column names from Google Ads Manager exports.
"""

import pandas as pd
from modules.utils import safe_float, safe_int

# Maps Google Ads column names to standard schema fields.
GOOGLE_COLUMN_MAP = {
    # Campaign / ad group / ad names
    "Campaign": "campaign_name",
    "Campaign name": "campaign_name",
    "Ad group": "adset_name",
    "Ad group name": "adset_name",
    "Ad": "ad_name",
    "Ad name": "ad_name",
    "Description": "ad_name",
    # Impressions
    "Impr.": "impressions",
    "Impressions": "impressions",
    # Clicks
    "Clicks": "clicks",
    # Spend / cost
    "Cost": "spend",
    "Cost (BRL)": "spend",
    "Custo": "spend",
    "Cost / conv.": "cpa",
    "Cost / conversion": "cpa",
    # Conversions
    "Conversions": "conversions",
    "Conv.": "conversions",
    "Conversões": "conversions",
    # Revenue / conversion value
    "Conv. value": "revenue",
    "Conversion value": "revenue",
    "Valor de conv.": "revenue",
    # Calculated metrics
    "CTR": "ctr",
    "Avg. CPC": "cpc",
    "Avg. CPM": "cpm",
    "ROAS": "roas",
    "Conv. value / cost": "roas",
    # Date
    "Day": "date",
    "Date": "date",
    "Week": "date",
    "Month": "date",
}

_SCHEMA_DEFAULTS = {
    "campaign_name": "",
    "adset_name": "",
    "ad_name": "",
    "impressions": 0,
    "clicks": 0,
    "spend": 0.0,
    "conversions": 0,
    "revenue": 0.0,
    "ctr": 0.0,
    "cpc": 0.0,
    "cpm": 0.0,
    "cpa": 0.0,
    "roas": 0.0,
    "date": None,
}


class GoogleParser:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse(self) -> pd.DataFrame:
        df = pd.read_csv(
            self.filepath,
            encoding="utf-8-sig",
            sep=None,
            engine="python",
            thousands=",",
            decimal=".",
            skiprows=self._detect_header_row(),
        )
        df.columns = df.columns.str.strip()
        df = self._drop_totals_row(df)
        df = self._rename_columns(df)
        df = self._ensure_schema(df)
        df = self._calculate_metrics(df)
        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_header_row(self) -> int:
        """Google Ads exports sometimes prepend metadata rows before the header."""
        with open(self.filepath, encoding="utf-8-sig") as f:
            for i, line in enumerate(f):
                # The header row typically starts with 'Campaign' or 'Day'
                if line.startswith(("Campaign", "Day", "Date", "Ad group", "Ad ")):
                    return i
        return 0

    def _drop_totals_row(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove the 'Total' summary row Google Ads appends at the bottom."""
        if df.empty:
            return df
        first_col = df.columns[0]
        return df[~df[first_col].astype(str).str.lower().str.startswith("total")]

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename_map = {}
        already_mapped = set()
        for col in df.columns:
            target = GOOGLE_COLUMN_MAP.get(col)
            if target and target not in already_mapped:
                rename_map[col] = target
                already_mapped.add(target)
        return df.rename(columns=rename_map)

    def _ensure_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, default in _SCHEMA_DEFAULTS.items():
            if col not in df.columns:
                df[col] = default

        df["impressions"] = df["impressions"].apply(safe_int)
        df["clicks"] = df["clicks"].apply(safe_int)
        df["conversions"] = df["conversions"].apply(safe_float)  # Google allows fractional
        df["conversions"] = df["conversions"].apply(lambda x: safe_int(x))
        df["spend"] = df["spend"].apply(safe_float)
        df["revenue"] = df["revenue"].apply(safe_float)
        df["ctr"] = df["ctr"].apply(safe_float)
        df["cpc"] = df["cpc"].apply(safe_float)
        df["cpm"] = df["cpm"].apply(safe_float)
        df["cpa"] = df["cpa"].apply(safe_float)
        df["roas"] = df["roas"].apply(safe_float)

        return df[list(_SCHEMA_DEFAULTS.keys())]

    def _calculate_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        imp = df["impressions"] > 0
        clk = df["clicks"] > 0
        spd = df["spend"] > 0
        cnv = df["conversions"] > 0
        rev = df["revenue"] > 0

        df.loc[imp & (df["ctr"] == 0), "ctr"] = (
            df.loc[imp & (df["ctr"] == 0), "clicks"]
            / df.loc[imp & (df["ctr"] == 0), "impressions"]
            * 100
        ).round(4)

        df.loc[clk & (df["cpc"] == 0), "cpc"] = (
            df.loc[clk & (df["cpc"] == 0), "spend"]
            / df.loc[clk & (df["cpc"] == 0), "clicks"]
        ).round(4)

        df.loc[imp & (df["cpm"] == 0), "cpm"] = (
            df.loc[imp & (df["cpm"] == 0), "spend"]
            / df.loc[imp & (df["cpm"] == 0), "impressions"]
            * 1000
        ).round(4)

        df.loc[cnv & (df["cpa"] == 0), "cpa"] = (
            df.loc[cnv & (df["cpa"] == 0), "spend"]
            / df.loc[cnv & (df["cpa"] == 0), "conversions"]
        ).round(4)

        df.loc[spd & rev & (df["roas"] == 0), "roas"] = (
            df.loc[spd & rev & (df["roas"] == 0), "revenue"]
            / df.loc[spd & rev & (df["roas"] == 0), "spend"]
        ).round(4)

        return df
