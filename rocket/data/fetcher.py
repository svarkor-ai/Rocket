"""Fetch OHLCV data via yfinance."""
import yfinance as yf
import pandas as pd
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def fetch_ohlcv(
    tickers: list,
    period: str = "5y",
    interval: str = "1d"
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV for a list of tickers. Returns dict ticker→DataFrame."""
    result = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        try:
            data = yf.download(
                ticker, period=period, interval=interval, progress=False,
                threads=True, timeout=20
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
                        result[ticker] = data
            logger.debug(
                f"[{i}/{total}] Fetched {ticker}: "
                f"{len(result.get(ticker, []))} rows"
            )
        except Exception as e:
            logger.warning(f"[{i}/{total}] Failed to fetch {ticker}: {e}")
        time.sleep(0.3)
    return result
