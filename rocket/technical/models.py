from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalCategory(str, Enum):
    MOMENTUM = "momentum"
    TREND = "trend"
    VOLATILITY = "volatility"
    VOLUME = "volume"


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStrength(str, Enum):
    VERY_BEARISH = "Very Bearish"
    BEARISH = "Bearish"
    HOLD = "Hold"
    BULLISH = "Bullish"
    VERY_BULLISH = "Very Bullish"


@dataclass
class IndicatorResult:
    """Result from a single technical indicator."""
    name: str
    score: float           # -1.0 (strong sell) to +1.0 (strong buy)
    signal: Signal = Signal.HOLD
    category: SignalCategory = SignalCategory.MOMENTUM
    values: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
