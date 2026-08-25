"""Parquet storage for OHLCV data."""
import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime


def get_ohlcv_path(data_dir: str, ticker: str) -> Path:
    """Return the parquet path for a ticker."""
    ohlcv_dir = Path(data_dir) / 'ohlcv'
    ohlcv_dir.mkdir(parents=True, exist_ok=True)
    safe = ticker.replace(':', '_').replace('/', '_')
    return ohlcv_dir / f"{safe}.parquet"


def save_ohlcv(data_dir: str, ticker: str, df: pd.DataFrame) -> None:
    """Save an OHLCV DataFrame to parquet."""
    path = get_ohlcv_path(data_dir, ticker)
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index.name = 'date'
    df.to_parquet(path, engine='pyarrow', index=True)


def load_ohlcv(data_dir: str, ticker: str) -> Optional[pd.DataFrame]:
    """Load OHLCV data from parquet. Returns None if not found."""
    path = get_ohlcv_path(data_dir, ticker)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, engine='pyarrow')
        df.index = pd.to_datetime(df.index)
        df.index.name = 'date'
        return df
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None


def needs_update(
    data_dir: str,
    ticker: str,
    max_age_days: int = 1
) -> bool:
    """Return True if data is missing or older than max_age_days."""
    path = get_ohlcv_path(data_dir, ticker)
    if not path.exists():
        return True
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        age = (datetime.now() - mtime).days
        return age > max_age_days
    except Exception:
        return True
