"""
CoinGecko fetcher — Cryptocurrency OHLCV data.

CoinGecko's public API requires NO API key for basic usage.
Free tier: 10-30 calls/min, sufficient for batch OHLCV fetching.

API endpoints (all public, no key needed):
  GET /coins/{id}/market_chart?vs_currency=usd&days={N}
  GET /coins/list                   → list of all tracked coins

Usage:
    from data_fetcher.coingecko import fetch_crypto
    df = fetch_crypto("bitcoin", days=365)
    # Returns pd.DataFrame with OHLCV columns
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from .common import save_parquet, throttle_request, ProgressTracker, ensure_ohlcv_format
from .config import DEFAULT_CRYPTO_COINS, REQUEST_DELAY, DATA_DIR

logger = logging.getLogger(__name__)

# CoinGecko API base URL
BASE_URL = "https://api.coingecko.com/api/v3"


def get_available_coins() -> list:
    """
    Fetch list of all available cryptocurrency IDs from CoinGecko.
    Returns list of coin ID strings.
    """
    try:
        resp = requests.get(f"{BASE_URL}/coins/list", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        coins = [item.get("id", "").lower() for item in data if item.get("id")]
        logger.info(f"CoinGecko returned {len(coins)} available coins")
        return coins
    except Exception as e:
        logger.error(f"Failed to get coin list from CoinGecko: {e}")
        return []


def fetch_single_coin(
    coin_id: str,
    days: int = 365,
    currency: str = "usd",
    source: str = "coingecko",
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a single cryptocurrency.

    Args:
        coin_id: CoinGecko coin ID (e.g. "bitcoin", "ethereum")
        days: Number of days of history (1, 7, 30, 90, 365, 365max, 999999)
        currency: vs_currency (default: "usd")
        source: Source label for parquet file

    Returns:
        pd.DataFrame with OHLCV columns, indexed by timestamp
    """
    url = f"{BASE_URL}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": currency,
        "days": str(days),
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if "prices" not in data or "total_volumes" not in data:
            logger.warning(f"No OHLCV data for {coin_id}")
            return pd.DataFrame()

        # CoinGecko returns: [[timestamp_ms, price], ...] for prices
        # and [[timestamp_ms, volume], ...] for volumes
        prices = data["prices"]
        volumes = data["total_volumes"]

        # Build OHLCV from price + volume data
        # Note: CoinGecko free tier only returns price + volume, not OHLC
        # We'll construct a basic OHLCV from price points
        rows = []
        for i, (ts, price) in enumerate(prices):
            vol = volumes[i][1] if i < len(volumes) else 0
            rows.append({
                "timestamp": pd.Timestamp(ts, unit="ms"),
                "open": float(price),
                "high": float(price),
                "low": float(price),
                "close": float(price),
                "volume": int(vol),
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df = ensure_ohlcv_format(df, source)
        return df

    except requests.exceptions.RequestException as e:
        logger.warning(f"Request failed for {coin_id}: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"Unexpected error for {coin_id}: {e}")
        return pd.DataFrame()


def fetch_crypto(
    coin_ids: Optional[list] = None,
    days: int = 365,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> list:
    """
    Fetch OHLCV data for multiple cryptocurrencies.

    Args:
        coin_ids: List of CoinGecko coin IDs
        days: Number of days of history
        limit: Max number of coins to fetch (for testing)
        dry_run: If True, just return first N IDs without fetching

    Returns:
        list of (coin_id, filepath, success) tuples
    """
    if coin_ids is None:
        coin_ids = list(DEFAULT_CRYPTO_COINS)

    if limit:
        coin_ids = coin_ids[:limit]

    tracker = ProgressTracker(len(coin_ids), "CoinGecko-Crypto")

    for i, coin_id in enumerate(coin_ids):
        filepath = ""
        success = False

        if dry_run:
            tracker.update(coin_id, "", True)
            continue

        try:
            df = fetch_single_coin(coin_id, days=days)
            if not df.empty:
                filepath = save_parquet(df, coin_id.lower(), "coingecko", DATA_DIR)
                success = len(filepath) > 0
            tracker.update(coin_id.lower(), filepath, success)
        except Exception as e:
            logger.error(f"Failed to fetch {coin_id}: {e}")
            tracker.update(coin_id.lower(), "", False)

        # Throttle — CoinGecko free tier: ~10-30 calls/min
        if i < len(coin_ids) - 1:
            throttle_request(max(REQUEST_DELAY, 2.5))  # generous spacing

    logger.info(f"CoinGecko complete: {tracker.summary()}")
    return tracker.results


def fetch_with_ohlcv(
    coin_id: str,
    days: int = 365,
    intervals: list = ["1d", "1h"],
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data with actual OHLC candles (requires API v3 /local endpoint).
    Falls back to price-only if that's all we get.

    Args:
        coin_id: CoinGecko coin ID
        days: Number of days
        intervals: List of intervals to try

    Returns:
        pd.DataFrame with proper OHLCV or None on failure
    """
    # Try the /local endpoint first (has real OHLCV)
    for interval in intervals:
        try:
            url = f"{BASE_URL}/coins/{coin_id}/ohlc"
            params = {"vs_currency": "usd", "days": str(days)}
            resp = requests.get(url, params=params, timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                # OHLCV format: [timestamp_ms, open, high, low, close]
                rows = []
                for candle in data:
                    if len(candle) >= 5:
                        rows.append({
                            "timestamp": pd.Timestamp(candle[0], unit="ms"),
                            "open": float(candle[1]),
                            "high": float(candle[2]),
                            "low": float(candle[3]),
                            "close": float(candle[4]),
                            "volume": 0,  # Not in /ohlc endpoint
                        })
                df = pd.DataFrame(rows)
                if not df.empty:
                    df = ensure_ohlcv_format(df, "coingecko")
                    return df
        except Exception:
            continue

    return None
