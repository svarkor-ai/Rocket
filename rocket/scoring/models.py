from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreBreakdown:
    """Weighted score breakdown."""
    momentum: float = 0.0      # 40%
    trend: float = 0.0         # 30%
    volatility: float = 0.0    # 20%
    volume: float = 0.0        # 10%
    total: float = 0.0         # weighted sum (0-100)


@dataclass
class RocketScore:
    """Complete scoring result for one ticker."""
    ticker: str
    overall_score: float            # 0–100
    momentum_score: float           # 0–100
    trend_score: float              # 0–100
    volatility_score: float         # 0–100
    volume_score: float             # 0–100
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0
    filter_passed: bool = True
    filter_reason: str = ""
    region: str = "us"
    sector: str = ""
    filter_result: Optional[object] = None
    momentum_details: dict = field(default_factory=dict)
    trend_details: dict = field(default_factory=dict)
    volatility_details: dict = field(default_factory=dict)
    volume_details: dict = field(default_factory=dict)


@dataclass
class FilterResult:
    """Result of applying quality filters."""
    ticker: str
    passed: bool = True
    reasons: list = field(default_factory=list)
