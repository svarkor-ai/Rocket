"""StockTwits API client for Rocket Scanner.

Uses stocktwitsapi.com free tier (third-party wrapper) to fetch sentiment,
volume analytics, trending symbols, and available tickers.

Rate limits (free tier): 10 req/min, 100 req/month.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

BASE_URL = "https://stocktwitsapi.com/api/v2"
API_KEY = os.environ.get("STOCKTWITS_API_KEY", "")
CACHE_TTL = 1800  # 30 minutes in seconds

# Simple in-memory cache: key -> (timestamp, value)
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    """Return cached value if still valid, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, val = entry
    if time.time() - ts < CACHE_TTL:
        return val
    _cache.pop(key, None)
    return None


def _cache_set(key: str, value: Any) -> None:
    """Store value in cache with current timestamp."""
    _cache[key] = (time.time(), value)


def _api_get(endpoint: str, timeout: float = 10.0, max_retries: int = 3) -> dict | list | None:
    """Make a GET request to StockTwits API with retry + exponential backoff.

    Args:
        endpoint: API path, e.g. "/sentiment-detail?symbol=AAPL".
        timeout: Request timeout in seconds (default 10).
        max_retries: Max retries on 429 rate limit.

    Returns:
        Parsed JSON on success, or None on failure.
    """
    if not API_KEY:
        return None

    for attempt in range(max_retries):
        try:
            resp = httpx.get(
                BASE_URL + endpoint,
                headers={"x-api-key": API_KEY},
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = (2 ** attempt) * 2  # 2, 4, 8 seconds
                time.sleep(wait)
                continue
            if resp.status_code == 200:
                return resp.json()
            return None
        except (httpx.TimeoutException, httpx.RequestError, Exception):
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None


def get_sentiment(symbol: str, timeframe: str = "1D") -> dict[str, Any]:
    """Get detailed sentiment for a single ticker.

    GET /api/v2/sentiment-detail?symbol=AAPL

    Args:
        symbol: Ticker symbol, e.g. "AAPL".
        timeframe: Time window, e.g. "1D", "7D", "30D".

    Returns:
        Dict with bull/bear/neutral/total/participation_score/timeframe,
        or neutral defaults if unavailable.
    """
    cache_key = f"sentiment:{symbol.upper()}:{timeframe}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = _api_get(f"/sentiment-detail?symbol={symbol.upper()}")

    if result is None:
        return {
            "bull": 0.0,
            "bear": 0.0,
            "neutral": 100.0,
            "total": 0,
            "participation_score": 0,
            "timeframe": timeframe,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    bull = result.get("bull", 0)
    bear = result.get("bear", 0)
    neutral = result.get("neutral", 0)
    total = result.get("total", 0)
    participation = result.get("participation_score", 0)

    data = {
        "bull": float(bull),
        "bear": float(bear),
        "neutral": float(neutral),
        "total": total,
        "participation_score": float(participation),
        "timeframe": result.get("timeframe", timeframe),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _cache_set(cache_key, data)
    return data


def get_volume_analytics(symbol: str, timeframe: str = "1D") -> list[dict[str, Any]]:
    """Get daily volume time series for a symbol.

    GET /api/v2/analytics/volume?symbol=AAPL&timeframe=1D

    Args:
        symbol: Ticker symbol.
        timeframe: Time window.

    Returns:
        List of dicts with date/volume data, or empty list if unavailable.
    """
    cache_key = f"volume:{symbol.upper()}:{timeframe}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = _api_get(f"/analytics/volume?symbol={symbol.upper()}&timeframe={timeframe}")

    if result is None:
        return []

    if isinstance(result, list):
        data = result
    elif isinstance(result, dict):
        data = result.get("data", result.get("analytics", []))
        if not isinstance(data, list):
            data = []
    else:
        data = []

    _cache_set(cache_key, data)
    return data


def get_trending(timeframe: str = "1D") -> list[dict[str, Any]]:
    """Get currently trending symbols ranked by score.

    GET /api/v2/trending

    Args:
        timeframe: Time window.

    Returns:
        List of trending symbol dicts, or empty list if unavailable.
    """
    cache_key = f"trending:{timeframe}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = _api_get("/trending")

    if result is None:
        return []

    if isinstance(result, list):
        data = result
    elif isinstance(result, dict):
        data = result.get("trending", result.get("data", []))
        if not isinstance(data, list):
            data = []
    else:
        data = []

    _cache_set(cache_key, data)
    return data


def get_available_symbols() -> list[str]:
    """Get list of all available ticker symbols.

    GET /api/v2/symbols

    Returns:
        List of ticker symbol strings, or empty list if unavailable.
    """
    cache_key = "symbols:all"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = _api_get("/symbols")

    if result is None:
        return []

    if isinstance(result, list):
        symbols = []
        for item in result:
            if isinstance(item, dict):
                symbols.append(item.get("symbol", item.get("ticker", "")))
            elif isinstance(item, str):
                symbols.append(item)
        data = [s.upper() for s in symbols if s]
    elif isinstance(result, dict):
        symbols_list = result.get("symbols", result.get("data", []))
        data = []
        for item in symbols_list:
            if isinstance(item, dict):
                data.append(item.get("symbol", item.get("ticker", "")))
            elif isinstance(item, str):
                data.append(item)
        data = [s.upper() for s in data if s]
    else:
        data = []

    _cache_set(cache_key, data)
    return data


def get_bullish_pct(symbol: str) -> float:
    """Get bullish percentage for a symbol (0.0 to 1.0).

    Convenience wrapper around get_sentiment for quick lookups.

    Args:
        symbol: Ticker symbol.

    Returns:
        Bullish percentage as a fraction (0.0 = 0%, 1.0 = 100%),
        or 0.5 (neutral default) if unavailable.
    """
    sentiment = get_sentiment(symbol)
    bull = sentiment.get("bull", 0.0)
    total = sentiment.get("total", 0)

    if total > 0 and bull > 0:
        return min(1.0, bull / 100.0)
    if bull > 0:
        return min(1.0, bull / 100.0)
    return 0.5
