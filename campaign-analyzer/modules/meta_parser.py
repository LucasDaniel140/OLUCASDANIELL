"""
Meta Ads CSV parser.

Normalizes exported Meta Ads reports to the standard campaign schema.
Handles both PT-BR and EN column names from Meta Business Manager exports.
"""

import pandas as pd
from modules.utils import safe_float, safe_int

# Maps Meta Ads column names (PT-BR and EN) to the standard schema fields.
# If multiple source columns map to the same target, the first one found wins.
META_COLUMN_MAP = {
    # Campaign / ad set / ad names
    "Nome da campanha": "campaign_name",
    "Campaign name": "campaign_name",
    "Nome do conjunto de anúncios": "adset_name",
    "Ad Set Name": "adset_name",
    "Nome do anúncio": "ad_name",
    "Ad name": "ad_name",
    # Impressions
    "Impressões": "impressions",
    "Impressions": "impressions",
    # Clicks
    "Cliques no link": "clicks",
    "Link clicks": "clicks",
    "Cliques (todos)": "clicks",
    "Clicks (all)": "clicks",
    # Spend
    "Valor usado (BRL)": "spend",
    "Amount spent (BRL)": "spend",
    "Valor gasto": "spend",
    # Conversions
    "Resultados": "conversions",
    "Results": "conversions",
    "Conversões": "conversions",
    "Conversions": "conversions",
    # Revenue
    "Receita de conversão": "revenue",
    "Conversion value": "revenue",
    "Valor de conversão": "revenue",
    # Calculated metrics (may already be present in the export)
    "CTR (taxa de cliques no link)": "ctr",
    "CTR (todos)": "ctr",
    "CTR (link click-through rate)": "ctr",
    "CPC (custo por clique no link)": "cpc",
    "CPC (cost per link click)": "cpc",
    "CPM (custo por 1.000 impressões)": "cpm",
    "CPM (cost per 1,000 impressions reached)": "cpm",
    "Custo por resultado": "cpa",
    "Cost per result": "cpa",
    # Date
    "Dia": "date",
    "Day": "date",
    "Data de início dos relatórios": "date",
    "Reporting starts": "date",
}

# Canonical schema with default values
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


class MetaParser:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse(self) -> pd.DataFrame:
        df = pd.read_csv(
            self.filepath,
            encoding="utf-8-sig",
            sep=None,
            engine="python",
            thousands=".",
            decimal=",",
        )
        df.columns = df.columns.str.strip()
        df = self._rename_columns(df)
        df = self._ensure_schema(df)
        df = self._calculate_metrics(df)
        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename_map = {}
        already_mapped = set()
        for col in df.columns:
            target = META_COLUMN_MAP.get(col)
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
        df["conversions"] = df["conversions"].apply(safe_int)
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

        # CTR (%) — only when impressions exist and CTR wasn't exported
        df.loc[imp & (df["ctr"] == 0), "ctr"] = (
            df.loc[imp & (df["ctr"] == 0), "clicks"]
            / df.loc[imp & (df["ctr"] == 0), "impressions"]
            * 100
        ).round(4)

        # CPC — cost per click
        df.loc[clk & (df["cpc"] == 0), "cpc"] = (
            df.loc[clk & (df["cpc"] == 0), "spend"]
            / df.loc[clk & (df["cpc"] == 0), "clicks"]
        ).round(4)

        # CPM — cost per 1 000 impressions
        df.loc[imp & (df["cpm"] == 0), "cpm"] = (
            df.loc[imp & (df["cpm"] == 0), "spend"]
            / df.loc[imp & (df["cpm"] == 0), "impressions"]
            * 1000
        ).round(4)

        # CPA — cost per conversion
        df.loc[cnv & (df["cpa"] == 0), "cpa"] = (
            df.loc[cnv & (df["cpa"] == 0), "spend"]
            / df.loc[cnv & (df["cpa"] == 0), "conversions"]
        ).round(4)

        # ROAS — return on ad spend
        df.loc[spd & rev & (df["roas"] == 0), "roas"] = (
            df.loc[spd & rev & (df["roas"] == 0), "revenue"]
            / df.loc[spd & rev & (df["roas"] == 0), "spend"]
        ).round(4)

        return df
