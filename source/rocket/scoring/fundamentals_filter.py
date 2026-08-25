"""Fundamental data scoring — integrates with the v2 pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..data.fundamentals import FundamentalData, get_fundamental_score

logger = logging.getLogger(__name__)


@dataclass
class FundamentalFilterResult:
    """Result of fundamental filtering."""
    score: float  # 0.0 (weak) → 1.0 (strong)
    quality: str  # "STRONG", "GOOD", "FAIR", "WEAK", "UNKNOWN"
    factors: list[str]
    rejection_reason: Optional[str] = None

    @property
    def is_pass(self) -> bool:
        """True if fundamental quality is acceptable."""
        return self.quality in ("STRONG", "GOOD", "FAIR")


def evaluate_fundamentals(
    fd: FundamentalData | None,
    min_score: float = 0.3,
) -> FundamentalFilterResult:
    """Evaluate fundamental data and return filter result.

    Args:
        fd: Fundamental data for the ticker.
        min_score: Minimum score to pass filter.

    Returns:
        FundamentalFilterResult with score and quality.
    """
    if fd is None:
        return FundamentalFilterResult(
            score=0.0,
            quality="UNKNOWN",
            factors=["no fundamental data available"],
            rejection_reason="no data",
        )

    if not fd.is_valid:
        return FundamentalFilterResult(
            score=0.0,
            quality="UNKNOWN",
            factors=["insufficient fundamental data"],
            rejection_reason="insufficient data",
        )

    score = get_fundamental_score(fd)

    # Determine quality label
    if score >= 0.7:
        quality = "STRONG"
    elif score >= 0.5:
        quality = "GOOD"
    elif score >= min_score:
        quality = "FAIR"
    else:
        quality = "WEAK"

    # Build factor list
    factors = []
    if fd.pe_ttm is not None:
        factors.append(f"P/E={fd.pe_ttm:.1f}")
    if fd.roe is not None:
        factors.append(f"ROE={fd.roe:.0%}")
    if fd.revenue_growth_ttm is not None:
        factors.append(f"RevGrowth={fd.revenue_growth_ttm:.0%}")
    if fd.profit_margin is not None:
        factors.append(f"Margin={fd.profit_margin:.0%}")
    if fd.debt_to_equity is not None:
        factors.append(f"D/E={fd.debt_to_equity:.1f}")
    if fd.peg_ratio is not None:
        factors.append(f"PEG={fd.peg_ratio:.1f}")

    rejection_reason = None
    if quality == "WEAK":
        rejection_reason = f"low fundamental score ({score:.2f})"

    return FundamentalFilterResult(
        score=score,
        quality=quality,
        factors=factors,
        rejection_reason=rejection_reason,
    )
