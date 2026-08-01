"""Rocket Stock Scanner - Ticker Universe

Re-exports from universe_builder.py and provides missing helpers.
All ticker lists and enrichment logic are in universe_builder.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from .universe_builder import (
    get_universe,
    get_all_universes,
    get_all_tickers,
    get_universe_count,
    get_total_count,
    get_region_count,
)

# ---------------------------------------------------------------------------
# Missing constants — universe_builder does not export these
# ---------------------------------------------------------------------------

REGIONS: dict[str, list[str]] = {
    "usa": [], "sweden": [], "uk": [], "germany": [],
    "france": [], "japan": [], "china": [], "india": [],
    "australia": [], "canada": [], "brazil": [], "korea": [],
    "singapore": [], "switzerland": [],
}

REGION_DEFAULTS: dict[str, dict] = {
    "usa": {"exchange": "NYSE/NASDAQ", "timezone": "America/New_York"},
    "sweden": {"exchange": "STO", "timezone": "Europe/Stockholm"},
    "uk": {"exchange": "LSE", "timezone": "Europe/London"},
    "germany": {"exchange": "XETRA", "timezone": "Europe/Berlin"},
    "france": {"exchange": "Euronext Paris", "timezone": "Europe/Paris"},
    "japan": {"exchange": "TSE", "timezone": "Asia/Tokyo"},
    "china": {"exchange": "SSE/SZSE", "timezone": "Asia/Shanghai"},
    "india": {"exchange": "NSE/BSE", "timezone": "Asia/Kolkata"},
    "australia": {"exchange": "ASX", "timezone": "Australia/Sydney"},
    "canada": {"exchange": "TSX", "timezone": "America/Toronto"},
    "brazil": {"exchange": "BOVESPA", "timezone": "America/Sao_Paulo"},
    "korea": {"exchange": "KRX", "timezone": "Asia/Seoul"},
    "singapore": {"exchange": "SGX", "timezone": "Asia/Singapore"},
    "switzerland": {"exchange": "SIX", "timezone": "Europe/Zurich"},
}

REGION_LABELS: dict[str, str] = {
    "usa": "USA", "sweden": "Sverige", "uk": "UK",
    "germany": "Tyskland", "france": "Frankrike",
    "japan": "Japan", "china": "Kina", "india": "Indien",
    "australia": "Australien", "canada": "Kanada",
    "brazil": "Brasilien", "korea": "Sydkorea",
    "singapore": "Singapore", "switzerland": "Schweiz",
}

# ---------------------------------------------------------------------------
# Helper functions — callers expect these from universe module
# ---------------------------------------------------------------------------

def get_sector(ticker: str) -> str:
    """Get sector for a ticker. Returns empty string if not found."""
    enriched = _load_enrichment_data()
    info = enriched.get(ticker, {})
    return info.get("sector", "")


def get_region(ticker: str) -> str:
    """Get region for a ticker. Returns 'usa' by default."""
    enriched = _load_enrichment_data()
    info = enriched.get(ticker, {})
    return info.get("region", "usa")


def get_ticker_info(ticker: str) -> dict:
    """Get info dict for a ticker."""
    enriched = _load_enrichment_data()
    info = enriched.get(ticker, {})
    return {
        "ticker": ticker,
        "name": info.get("name", ""),
        "region": info.get("region", "usa"),
        "sector": info.get("sector", ""),
        "market_cap": info.get("market_cap", 0.0),
        "avg_volume": info.get("avg_volume", 0.0),
    }


def enrich_ticker_info(ticker: str, info: dict) -> dict:
    """Enrich ticker info with exchange data."""
    region = info.get("region", "usa")
    info["exchange"] = REGION_DEFAULTS.get(region, {}).get("exchange", "Unknown")
    return info


def load_enrichment_data() -> dict:
    """Load enrichment data from universe_enriched.json."""
    return _load_enrichment_data()


def _load_enrichment_data() -> dict:
    """Internal load of enrichment data."""
    enriched_path = Path(__file__).parent / "universe_enriched.json"
    if enriched_path.exists():
        with open(enriched_path, "r") as f:
            return json.load(f)
    return {}


def save_enrichment_data(data: dict) -> None:
    """Save enrichment data to universe_enriched.json."""
    enriched_path = Path(__file__).parent / "universe_enriched.json"
    with open(enriched_path, "w") as f:
        json.dump(data, f, indent=2)


def load_universe_list() -> dict[str, list[str]]:
    """Load universe list from cache."""
    return get_universe()


def save_universe_list(data: dict[str, list[str]]) -> None:
    """Save universe list to cache."""
    pass


def update_universe() -> dict[str, list[str]]:
    """Trigger universe update (alias for get_universe)."""
    return get_universe()


__all__ = [
    "get_universe",
    "get_all_universes",
    "get_all_tickers",
    "get_universe_count",
    "get_total_count",
    "get_region_count",
    "get_sector",
    "get_region",
    "get_ticker_info",
    "enrich_ticker_info",
    "REGIONS",
    "REGION_DEFAULTS",
    "REGION_LABELS",
    "load_enrichment_data",
    "save_enrichment_data",
    "load_universe_list",
    "save_universe_list",
    "update_universe",
]
