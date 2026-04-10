"""
Goals persistence module.

Stores and retrieves per-client campaign goals in:
  campaign-analyzer/data/client_goals.json

Each entry is keyed by the client's normalized slug and contains:
  client_name, slug, target_cpa, min_roas, min_ctr, max_cpc, monthly_budget
  (any field can be absent if not defined)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_IS_VERCEL = bool(os.environ.get("VERCEL"))
_DATA_DIR = (
    Path("/tmp/campaign-analyzer/data")
    if _IS_VERCEL
    else Path(__file__).parent.parent / "data"
)
_GOALS_FILE = _DATA_DIR / "client_goals.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load() -> dict:
    if not _GOALS_FILE.exists():
        return {}
    try:
        with open(_GOALS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _persist(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_GOALS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_goals(client_slug: str) -> dict | None:
    """Return the goals dict for a client slug, or None if not defined."""
    return _load().get(client_slug)


def save_goals(client_slug: str, client_name: str, goals: dict) -> None:
    """Persist goals for a client slug (merges with existing entry)."""
    data = _load()
    data[client_slug] = {
        "client_name": client_name,
        "slug": client_slug,
        **{k: v for k, v in goals.items() if v is not None},
    }
    _persist(data)


def list_all_goals() -> list[dict]:
    """Return a list of all saved goal entries."""
    return list(_load().values())
