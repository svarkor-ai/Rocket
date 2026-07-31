"""FINVIZ short interest data scraper for Rocket Scanner.

Fetches short interest data from FINVIZ's screener page.
Data is updated ~twice per month (1st and 15th), cached for 24h.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

# FINVIZ short interest screener page
_URL = "https://finviz.com/screener.ashx?v=152"

# Cache location within the project
_CACHE_DIR = Path("data") / "cache"
_CACHE_FILE = _CACHE_DIR / "finviz_short_interest.json"

# Cache TTL: 24 hours (data changes bi-weekly)
_CACHE_TTL_SECONDS = 24 * 60 * 60

# HTTP timeout
_TIMEOUT = 15


@dataclass
class ShortInterestData:
    """Short interest metrics for a single ticker."""
    ticker: str
    short_percent_of_float: float  # Short float %
    short_volume_ratio: float      # Short volume / total volume
    last_updated: Optional[str] = None


def _load_cache() -> dict[str, dict]:
    """Load short interest data from cache file.

    Returns:
        Dict of ticker -> short interest data, or empty dict on failure.
    """
    try:
        if not _CACHE_FILE.exists():
            return {}
        if time.time() - _CACHE_FILE.stat().st_mtime > _CACHE_TTL_SECONDS:
            return {}
        with open(_CACHE_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        logger.debug("Short interest operation failed")
    return {}


def _save_cache(data: dict[str, dict]) -> None:
    """Save short interest data to cache file.

    Args:
        data: Dict of ticker -> short interest data dict.
    """
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        logger.debug("Short interest operation failed")


def scrape_short_interest() -> dict[str, dict]:
    """Scrape short interest data from FINVIZ.

    Fetches the FINVIZ short interest screener page and parses the HTML
    table to extract ticker -> short interest metrics.

    Results are cached for 24 hours. On scrape failure, returns empty dict
    (graceful degradation).

    Returns:
        Dictionary mapping ticker symbols to their short interest data:
        {
            "AAPL": {
                "short_percent_of_float": 3.15,
                "short_volume_ratio": 2.89,
            },
            ...
        }
    """
    # Check cache first
    cache = _load_cache()
    if cache:
        return cache

    # Fetch page with timeout
    try:
        response = httpx.get(_URL, timeout=_TIMEOUT)
        if response.status_code != 200:
            return {}
        html = response.text
    except Exception:
        return {}

    # Parse HTML table
    try:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            return {}

        results = {}
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            # First cell: ticker symbol inside <a> tag
            link = cells[0].find("a")
            if link is None:
                continue
            ticker = link.get_text(strip=True).upper()
            if not ticker or len(ticker) < 2:
                continue

            # Second cell: short % of float (e.g., "3.15%")
            short_float_text = cells[1].get_text(strip=True)
            short_float = _parse_percent(short_float_text)

            # Third cell: short volume ratio (e.g., "2.89%")
            short_vol_text = cells[2].get_text(strip=True)
            short_vol = _parse_percent(short_vol_text)

            if short_float is not None or short_vol is not None:
                results[ticker] = {
                    "short_percent_of_float": short_float if short_float is not None else 0.0,
                    "short_volume_ratio": short_vol if short_vol is not None else 0.0,
                }

        # Save to cache
        if results:
            _save_cache(results)

        return results

    except Exception:
        return {}


def _parse_percent(text: str) -> Optional[float]:
    """Parse a percentage string like '3.15%' to a float.

    Args:
        text: String containing a percentage value.

    Returns:
        Float value of the percentage, or None if parsing fails.
    """
    if not text:
        return None
    try:
        text = text.replace("%", "").strip()
        return float(text)
    except (ValueError, TypeError):
        return None


def get_short_interest(tickers: list[str]) -> dict[str, ShortInterestData]:
    """Get short interest data for specific tickers.

    Args:
        tickers: List of ticker symbols to look up.

    Returns:
        Dictionary mapping tickers to ShortInterestData objects.
        Tickers not found in the data get a default neutral entry.
    """
    all_data = scrape_short_interest()
    result = {}
    for ticker in tickers:
        ticker_upper = ticker.upper()
        if ticker_upper in all_data:
            d = all_data[ticker_upper]
            result[ticker] = ShortInterestData(
                ticker=ticker_upper,
                short_percent_of_float=d["short_percent_of_float"],
                short_volume_ratio=d["short_volume_ratio"],
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
        else:
            result[ticker] = ShortInterestData(
                ticker=ticker_upper,
                short_percent_of_float=0.0,
                short_volume_ratio=0.0,
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
    return result
