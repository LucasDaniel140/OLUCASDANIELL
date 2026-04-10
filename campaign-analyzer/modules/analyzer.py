"""
Campaign analyzer.

Computes aggregated KPIs and basic performance diagnostics from a
normalized DataFrame produced by MetaParser or GoogleParser.
"""

import pandas as pd


def summarize(df: pd.DataFrame) -> dict:
    """Return a dict with totals and averages for the main KPIs."""
    total_impressions = int(df["impressions"].sum())
    total_clicks = int(df["clicks"].sum())
    total_spend = round(float(df["spend"].sum()), 2)
    total_conversions = int(df["conversions"].sum())
    total_revenue = round(float(df["revenue"].sum()), 2)

    avg_ctr = round(total_clicks / total_impressions * 100, 4) if total_impressions else 0.0
    avg_cpc = round(total_spend / total_clicks, 4) if total_clicks else 0.0
    avg_cpm = round(total_spend / total_impressions * 1000, 4) if total_impressions else 0.0
    avg_cpa = round(total_spend / total_conversions, 4) if total_conversions else 0.0
    roas = round(total_revenue / total_spend, 4) if total_spend else 0.0

    return {
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_spend": total_spend,
        "total_conversions": total_conversions,
        "total_revenue": total_revenue,
        "avg_ctr": avg_ctr,
        "avg_cpc": avg_cpc,
        "avg_cpm": avg_cpm,
        "avg_cpa": avg_cpa,
        "roas": roas,
    }


def top_campaigns(df: pd.DataFrame, metric: str = "spend", n: int = 5) -> pd.DataFrame:
    """Return the top N campaigns ranked by a given metric."""
    if "campaign_name" not in df.columns or metric not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby("campaign_name")[metric]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )
