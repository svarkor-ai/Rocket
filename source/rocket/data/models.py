from enum import Enum
from pydantic import BaseModel
from datetime import datetime


class Region(str, Enum):
    SMID = "smid"
    EU = "eu"
    US = "us"
    ASIA = "asia"


class TickerInfo(BaseModel):
    """Metadata about a single stock."""
    ticker: str
    name: str = ""
    region: Region = Region.US
    sector: str = ""
    market_cap: float = 0.0
    avg_volume: float = 0.0


class OhlcvRecord(BaseModel):
    """Single OHLCV data point."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
