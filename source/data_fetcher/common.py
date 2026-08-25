"""
Common utilities: parquet I/O, throttling, logging.
"""
import time
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Parquet column schema for OHLCV data
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def ensure_ohlcv_format(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """
    Normalize any OHLCV DataFrame to standard column names.
    
    Handles different data source formats:
    - yfinance: index=datetime, columns=Open/High/Low/Close/Volume
    - OpenAvanza/CoinGecko: column="timestamp", columns=open/high/low/close/volume
    """
    if df.empty or df is None:
        return df

    df = df.copy()

    # Case 1: Index is already datetime (yfinance format)
    if pd.api.types.is_datetime64_any_dtype(df.index):
        df.index.name = "timestamp"
        df = df.reset_index()
    
    # Case 2: "timestamp" column exists
    # (already handled above if index was datetime; if not, keep as-is)

    # Standardize price columns (case-sensitive match)
    col_map = {
        "Open": "open", "HIGH": "high", "High": "high",
        "LOW": "low", "Low": "low",
        "Close": "close", "CLOSE": "close",
        "Volume": "volume", "VOLUME": "volume",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Drop non-OHLCV columns (Dividends, Stock Splits, etc.)
    for col in list(df.columns):
        if col not in OHLCV_COLUMNS and col != "timestamp":
            df = df.drop(columns=[col])

    # Ensure required OHLCV columns exist
    for col in OHLCV_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0

    # Ensure timestamp column is datetime
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Sort by timestamp
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
    else:
        df["timestamp"] = pd.to_datetime("2000-01-01")

    # Drop duplicates (keep first)
    df = df.drop_duplicates(subset=["timestamp"], keep="first")

    # Set timestamp as index
    df = df.set_index("timestamp")

    return df


def save_parquet(df: pd.DataFrame, ticker: str, source: str, data_dir: Path) -> str:
    """
    Save a DataFrame to parquet, partitioned by source + ticker.
    Returns the file path.
    """
    df = ensure_ohlcv_format(df, source)
    if df.empty:
        logger.warning(f"Empty data for {ticker} ({source}), skipping save")
        return ""

    # Create ticker-specific directory
    ticker_dir = data_dir / source / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    # File path with date range in name
    start = df.index.min().strftime("%Y%m%d")
    end = df.index.max().strftime("%Y%m%d")
    filename = f"{ticker}_{start}_{end}.parquet"
    filepath = ticker_dir / filename

    df.to_parquet(filepath, engine="pyarrow")
    logger.info(f"Saved {len(df)} rows for {ticker} ({source}) -> {filepath}")
    return str(filepath)


def load_existing_tickers(data_dir: Path, source: str) -> set:
    """
    Load set of already-fetched tickers from parquet files.
    Returns set of ticker strings.
    """
    source_dir = data_dir / source
    if not source_dir.exists():
        return set()

    tickers = set()
    for f in source_dir.glob("**/*.parquet"):
        ticker = f.parent.name
        tickers.add(ticker)
    return tickers


def throttle_request(delay: float = 0.5):
    """Simple request throttler."""
    time.sleep(delay)
    return True


class ProgressTracker:
    """Track progress across fetch operations."""

    def __init__(self, total: int, label: str = "fetching"):
        self.total = total
        self.done = 0
        self.failed = 0
        self.label = label
        self.results = []  # list of (ticker, filepath, success)

    def update(self, ticker: str, filepath: str, success: bool):
        if success:
            self.done += 1
        else:
            self.failed += 1
        self.results.append((ticker, filepath, success))
        if self.total > 0:
            pct = (self.done + self.failed) / self.total * 100
            logger.info(
                f"[{self.label}] {self.done + self.failed}/{self.total} ({pct:.0f}%) "
                f"v={self.done} x={self.failed}"
            )

    def summary(self) -> dict:
        return {
            "total": self.total,
            "fetched": self.done,
            "failed": self.failed,
            "success_rate": self.done / max(1, self.done + self.failed) * 100,
        }
