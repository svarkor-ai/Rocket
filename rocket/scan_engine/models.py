"""Data models for the rocket stock scanner."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TickerInfo:
    """Metadata for a single ticker in the universe."""
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    region: Optional[str] = None
