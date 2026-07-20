"""Fetch OHLCV data via yfinance with bounded retry."""
import yfinance as yf
import pandas as pd
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY_S = 2  # base delay between retries


def _fetch_ticker(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """Download OHLCV for a single ticker with bounded retry."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            data = yf.download(
                ticker, period=period, interval=interval, progress=False,
                threads=False, timeout=20
            )
            if data is not None and not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)
                # Ensure required columns exist
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col not in data.columns:
                        data = None
                        break
                if data is not None:
                    data = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                    data.columns = ['open', 'high', 'low', 'close', 'volume']
                    data.index.name = 'date'
                    data = data.dropna()
                    if not data.empty:
                        return data
            break  # empty result is not retryable
        except (ConnectionError, OSError, ValueError) as e:
            if attempt < _MAX_RETRIES:
                wait = _RETRY_DELAY_S * attempt
                logger.warning(f"{ticker}: yfinance attempt {attempt} failed ({e}), retrying in {wait}s")
                time.sleep(wait)
            else:
                logger.warning(f"{ticker}: yfinance failed after {attempt} attempts: {e}")
        except Exception as e:
            # Non-retryable (e.g. parsing error) — break immediately
            logger.warning(f"{ticker}: non-retryable error: {type(e).__name__}: {e}")
            break
    return None


def fetch_ohlcv(
    tickers: list,
    period: str = "5y",
    interval: str = "1d"
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV for a list of tickers. Returns dict ticker->DataFrame."""
    result: Dict[str, pd.DataFrame] = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        data = _fetch_ticker(ticker, period, interval)
        if data is not None:
            result[ticker] = data
        logger.debug(
            f"[{i}/{total}] Fetched {ticker}: "
            f"{len(result.get(ticker, pd.DataFrame()))} rows"
        )
        time.sleep(0.3)
    return result
