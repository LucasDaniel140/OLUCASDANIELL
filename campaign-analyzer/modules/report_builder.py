"""
Report builder.

Assembles the analysis results into a structured dict ready for rendering,
and (optionally) persists a JSON report to the reports/ folder.
"""

import json
import os
from datetime import datetime

import pandas as pd

from modules.analyzer import summarize, top_campaigns


def build_report(
    df: pd.DataFrame,
    client_name: str,
    platform: str,
    date_start: str,
    date_end: str,
    report_folder: str,
) -> dict:
    """Build and persist the report, returning it as a dict."""
    summary = summarize(df)
    top_by_spend = top_campaigns(df, metric="spend").to_dict("records")
    top_by_conversions = top_campaigns(df, metric="conversions").to_dict("records")

    report = {
        "meta": {
            "client_name": client_name,
            "platform": platform,
            "date_start": date_start,
            "date_end": date_end,
            "generated_at": datetime.now().isoformat(),
            "total_rows": len(df),
        },
        "summary": summary,
        "top_campaigns_by_spend": top_by_spend,
        "top_campaigns_by_conversions": top_by_conversions,
    }

    _persist(report, client_name, report_folder)
    return report


def _persist(report: dict, client_name: str, report_folder: str) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_client = client_name.lower().replace(" ", "_")
    filename = f"{timestamp}_{safe_client}_report.json"
    filepath = os.path.join(report_folder, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
