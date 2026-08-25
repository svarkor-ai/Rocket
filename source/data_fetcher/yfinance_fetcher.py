"""
yFinance fetcher — US, European, and international stock data.

Uses yfinance library which wraps Yahoo Finance API.
Rate-limited to avoid 429 errors.

Usage:
    from data_fetcher.yfinance_fetcher import fetch_us_stocks
    df = fetch_us_stocks("AAPL", days=365)
    # Returns pd.DataFrame with OHLCV columns
"""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from .common import save_parquet, throttle_request, ProgressTracker, ensure_ohlcv_format
from .config import (
    DEFAULT_US_TICKERS, COUNTRY_CODES,
    REQUEST_DELAY, BATCH_SIZE, BATCH_PAUSE, DATA_DIR
)

logger = logging.getLogger(__name__)


def fetch_single_stock(
    ticker: str,
    days: int = 365,
    period: str = "max",
    suffix: str = "",
    source: str = "yfinance",
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a single stock via yfinance.

    Args:
        ticker: Stock ticker (e.g. "AAPL", "VOLTO.ST")
        days: Number of days of history
        period: Yahoo period string ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
        suffix: Suffix for ticker (e.g. ".ST" for Sweden)
        source: Source label for parquet file

    Returns:
        pd.DataFrame with OHLCV columns, indexed by timestamp
    """
    full_ticker = f"{ticker}{suffix}" if suffix else ticker

    try:
        # Use period parameter instead of days for more control
        ticker_obj = yf.Ticker(full_ticker)

        # Download data — prefer period for reliability
        df = ticker_obj.history(period=period)

        if df.empty:
            logger.debug(f"Empty history for {full_ticker}")
            return pd.DataFrame()

        df = ensure_ohlcv_format(df, source)
        return df

    except Exception as e:
        logger.warning(f"Failed to fetch {full_ticker}: {e}")
        return pd.DataFrame()


def fetch_us_stocks(
    tickers: Optional[list] = None,
    days: int = 365,
    period: str = "max",
    max_per_batch: int = BATCH_SIZE,
    batch_pause: int = BATCH_PAUSE,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> list:
    """
    Fetch OHLCV data for US stocks with rate limiting.

    Uses yfinance with built-in throttling.
    Processes in batches to avoid 429 errors.

    Args:
        tickers: List of tickers to fetch
        days: Number of days
        period: Yahoo period string
        max_per_batch: Max tickers per batch
        batch_pause: Seconds to wait between batches
        limit: Max tickers to process (for testing)
        dry_run: If True, return first N tickers without fetching

    Returns:
        list of (ticker, filepath, success) tuples
    """
    if tickers is None:
        tickers = list(DEFAULT_US_TICKERS)

    if limit:
        tickers = tickers[:limit]

    tracker = ProgressTracker(len(tickers), "yfinance-US")

    # Process in batches with pauses
    for batch_start in range(0, len(tickers), max_per_batch):
        batch = tickers[batch_start:batch_start + max_per_batch]

        for i, ticker in enumerate(batch):
            filepath = ""
            success = False

            if dry_run:
                tracker.update(ticker, "", True)
                continue

            try:
                df = fetch_single_stock(ticker, period=period)
                if not df.empty:
                    filepath = save_parquet(df, ticker, "yfinance_us", DATA_DIR)
                    success = len(filepath) > 0
                tracker.update(ticker, filepath, success)
            except Exception as e:
                logger.error(f"Failed {ticker}: {e}")
                tracker.update(ticker, "", False)

            # Throttle within batch
            if i < len(batch) - 1:
                throttle_request(REQUEST_DELAY)

        # Pause between batches
        if batch_start + max_per_batch < len(tickers):
            logger.info(f"Batch pause for {batch_pause}s...")
            throttle_request(batch_pause)

    logger.info(f"yfinance-US complete: {tracker.summary()}")
    return tracker.results


def fetch_international(
    tickers_with_suffix: Optional[dict] = None,
    days: int = 365,
    period: str = "max",
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> list:
    """
    Fetch OHLCV data for international stocks with market suffixes.

    Args:
        tickers_with_suffix: Dict of {ticker: suffix} e.g. {"VOLVO": ".ST", "SAP": ".DE"}
        days: Number of days
        period: Yahoo period string
        limit: Max tickers to fetch
        dry_run: If True, skip fetching

    Returns:
        list of (ticker, filepath, success) tuples
    """
    if tickers_with_suffix is None:
        # Default: try some major international tickers
        tickers_with_suffix = {
            "VOLVO-A": ".ST", "VOLVO-B": ".ST", "ESSITY-A": ".ST",
            "SEB-A": ".ST", "SEB-B": ".ST", "SWED-B": ".ST",
            "SAP": ".DE", "Siemens": ".DE", "ASML": ".AS",
            "Nestle": ".SW", "Novartis": ".SW", "Roche": ".SW",
            "LVMH": ".PA", "Total": ".PA",
            "Unilever": ".L", "BP": ".L", "Shell": ".L",
            "Toyota": ".T", "Sony": ".T", "Honda": ".T",
        }

    # Convert to flat list with suffixes
    items = list(tickers_with_suffix.items())
    if limit:
        items = items[:limit]

    tracker = ProgressTracker(len(items), "yfinance-Intl")

    for i, (ticker, suffix) in enumerate(items):
        filepath = ""
        success = False

        if dry_run:
            tracker.update(ticker, "", True)
            continue

        try:
            df = fetch_single_stock(ticker, period=period, suffix=suffix)
            if not df.empty:
                filepath = save_parquet(df, ticker, "yfinance_intl", DATA_DIR)
                success = len(filepath) > 0
            tracker.update(ticker, filepath, success)
        except Exception as e:
            logger.error(f"Failed {ticker}{suffix}: {e}")
            tracker.update(ticker, "", False)

        if i < len(items) - 1:
            throttle_request(REQUEST_DELAY)

    logger.info(f"yfinance-Intl complete: {tracker.summary()}")
    return tracker.results


def fetch_bulk(
    tickers: list,
    period: str = "max",
    batch_size: int = BATCH_SIZE,
    batch_pause: int = BATCH_PAUSE,
    source: str = "yfinance_bulk",
) -> dict:
    """
    Bulk fetch with yfinance download() for efficiency.
    Downloads multiple tickers in one HTTP request where possible.

    Args:
        tickers: List of ticker strings
        period: Yahoo period string
        batch_size: Max tickers per bulk download
        batch_pause: Pause between batches
        source: Source label for parquet files

    Returns:
        dict with "results" list and "summary" counts
    """
    all_results = []
    summary = {"fetched": 0, "failed": 0}

    for batch_start in range(0, len(tickers), batch_size):
        batch = tickers[batch_start:batch_start + batch_size]

        try:
            # yfinance.download() can handle multiple tickers at once
            df = yf.download(batch, period=period, progress=False)

            if df.empty:
                logger.warning(f"Empty bulk download for batch: {batch[:3]}...")
                for t in batch:
                    all_results.append((t, "", False))
                summary["failed"] += len(batch)
            else:
                # yfinance.download returns MultiIndex columns for multiple tickers
                for ticker in batch:
                    try:
                        if isinstance(df.columns, pd.MultiIndex):
                            ticker_df = df[ticker].dropna()
                        else:
                            ticker_df = df[ticker].to_frame()

                        if ticker_df.empty:
                            all_results.append((ticker, "", False))
                            summary["failed"] += 1
                        else:
                            ticker_df = ensure_ohlcv_format(ticker_df, source)
                            filepath = save_parquet(ticker_df, ticker, source, DATA_DIR)
                            all_results.append((ticker, filepath, True))
                            summary["fetched"] += 1
                    except Exception as e:
                        logger.error(f"Failed processing {ticker}: {e}")
                        all_results.append((ticker, "", False))
                        summary["failed"] += 1

            # Pause between batches
            if batch_start + batch_size < len(tickers):
                throttle_request(batch_pause)

        except Exception as e:
            logger.error(f"Bulk download failed: {e}")
            for t in batch:
                all_results.append((t, "", False))
            summary["failed"] += len(batch)
            throttle_request(batch_pause)

    return {"results": all_results, "summary": summary}
