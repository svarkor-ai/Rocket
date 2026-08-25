"""
OpenAvanza fetcher — Swedish stocks.

OpenAvanza (https://github.com/paulhagskall/openavanza) provides a public,
no-auth API for Swedish stock data. Much more reliable than Yahoo for SE market.

API endpoints (all public, no key needed):
  GET /history?symbol={TICKER}   → JSON OHLCV data
  GET /companyinfo               → list of all available tickers

Usage:
    from data_fetcher.openavanza import fetch_se_stocks
    df = fetch_se_stocks("VOLVO-A", days=365)
    # Returns pd.DataFrame with OHLCV columns
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from .common import save_parquet, throttle_request, ProgressTracker, ensure_ohlcv_format
from .config import OPENAVANGA_API, DEFAULT_SE_TICKERS, SE_EXTENDED, REQUEST_DELAY, DATA_DIR

logger = logging.getLogger(__name__)

# OpenAvanza base URL
BASE_URL = OPENAVANGA_API  # "https://api.openavanza.se"


def get_available_symbols() -> list:
    """
    Fetch list of all available Swedish stock symbols from OpenAvanza.
    Returns list of ticker strings.
    """
    try:
        resp = requests.get(f"{BASE_URL}/companyinfo", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        symbols = [item.get("symbol", "").upper() for item in data if item.get("symbol")]
        logger.info(f"OpenAvanza returned {len(symbols)} available symbols")
        return symbols
    except Exception as e:
        logger.error(f"Failed to get available symbols from OpenAvanza: {e}")
        return []


def fetch_single_stock(
    symbol: str,
    days: int = 365,
    source: str = "openavanza"
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a single Swedish stock.

    Args:
        symbol: Stock symbol (e.g. "VOLVO-A", "ERIC-B")
        days: Number of days of history
        source: Source label for parquet file

    Returns:
        pd.DataFrame with OHLCV columns, indexed by timestamp
    """
    url = f"{BASE_URL}/history"
    params = {
        "symbol": symbol.upper(),
        "range": "day",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data or "candles" not in data:
            logger.warning(f"No data for {symbol}")
            return pd.DataFrame()

        # Parse candles: [timestamp_ms, open, high, low, close, volume]
        candles = data["candles"]
        rows = []
        for candle in candles:
            if len(candle) >= 5:
                rows.append({
                    "timestamp": pd.Timestamp(candle[0], unit="ms"),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": int(candle[5]) if len(candle) > 5 else 0,
                })

        df = pd.DataFrame(rows)
        df = ensure_ohlcv_format(df, source)
        return df

    except requests.exceptions.RequestException as e:
        logger.warning(f"Request failed for {symbol}: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"Unexpected error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_se_stocks(
    symbols: Optional[list] = None,
    days: int = 365,
    max_workers: int = 5,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> list:
    """
    Fetch OHLCV data for multiple Swedish stocks.

    Args:
        symbols: List of symbols to fetch. Defaults to DEFAULT_SE_TICKERS.
        days: Number of days of history
        max_workers: Not used in single-thread version; for future parallel
        limit: Max number of tickers to fetch (for testing)
        dry_run: If True, just return first N symbols without fetching

    Returns:
        list of (ticker, filepath, success) tuples
    """
    if symbols is None:
        symbols = list(DEFAULT_SE_TICKERS)

    if limit:
        symbols = symbols[:limit]

    tracker = ProgressTracker(len(symbols), "OpenAvanza-SE")

    for i, symbol in enumerate(symbols):
        filepath = ""
        success = False

        if dry_run:
            tracker.update(symbol, "", True)
            continue

        try:
            df = fetch_single_stock(symbol, days=days)
            if not df.empty:
                filepath = save_parquet(df, symbol.upper(), "openavanza", DATA_DIR)
                success = len(filepath) > 0
            tracker.update(symbol.upper(), filepath, success)
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            tracker.update(symbol.upper(), "", False)

        # Throttle to be polite to the API
        if i < len(symbols) - 1:
            throttle_request(REQUEST_DELAY)

    logger.info(f"OpenAvanza complete: {tracker.summary()}")
    return tracker.results


def fetch_and_save_batch(
    batch: list,
    days: int = 365,
) -> list:
    """
    Fetch a batch of stocks and save to parquet.
    Can be called from a parallel worker.

    Args:
        batch: List of symbol strings
        days: Number of days of history

    Returns:
        list of (ticker, filepath, success) tuples
    """
    results = []
    for symbol in batch:
        filepath = ""
        try:
            df = fetch_single_stock(symbol, days=days)
            if not df.empty:
                filepath = save_parquet(df, symbol.upper(), "openavanza", DATA_DIR)
                results.append((symbol.upper(), filepath, True))
            else:
                results.append((symbol.upper(), "", False))
        except Exception as e:
            logger.error(f"Failed {symbol}: {e}")
            results.append((symbol.upper(), "", False))
        throttle_request(REQUEST_DELAY)
    return results
