"""Weight scoring — combine category scores into RocketScore."""
import numpy as np
from typing import List
from .models import RocketScore, ScoreBreakdown, FilterResult
from ..technical.models import SignalCategory
from ..technical.signal_combiner import SignalSummary


# Weights: momentum 40%, trend 30%, volatility 20%, volume 10%
WEIGHTS = {
    SignalCategory.MOMENTUM: 0.40,
    SignalCategory.TREND: 0.30,
    SignalCategory.VOLATILITY: 0.20,
    SignalCategory.VOLUME: 0.10,
}


def _to_0_100(score_11: float) -> float:
    """Convert from [-1, 1] to [0, 100]. Returns NaN if score is NaN."""
    if score_11 != score_11:  # NaN check: NaN != NaN is True
        return float('nan')
    return float(max(0.0, min(100.0, (score_11 + 1.0) / 2.0 * 100.0)))


def weight_scores(
    signal_summary: SignalSummary,
    filter_result: FilterResult,
    ticker: str = "",
    region: str = "us",
    sector: str = ""
) -> RocketScore:
    """Normalize category scores to 0-100, apply weights, return RocketScore."""

    momentum_raw = signal_summary.momentum_score
    trend_raw = signal_summary.trend_score
    vol_raw = signal_summary.volatility_score
    volm_raw = signal_summary.volume_score

    momentum_100 = _to_0_100(momentum_raw)
    trend_100 = _to_0_100(trend_raw)
    vol_100 = _to_0_100(vol_raw)
    volm_100 = _to_0_100(volm_raw)

    total = (
        momentum_100 * WEIGHTS[SignalCategory.MOMENTUM]
        + trend_100 * WEIGHTS[SignalCategory.TREND]
        + vol_100 * WEIGHTS[SignalCategory.VOLATILITY]
        + volm_100 * WEIGHTS[SignalCategory.VOLUME]
    )

    breakdown = ScoreBreakdown(
        momentum=momentum_100,
        trend=trend_100,
        volatility=vol_100,
        volume=volm_100,
        total=round(total, 2),
    )

    return RocketScore(
        ticker=ticker,
        overall_score=round(total, 2),
        momentum_score=momentum_100,
        trend_score=trend_100,
        volatility_score=vol_100,
        volume_score=volm_100,
        breakdown=breakdown,
        buy_count=signal_summary.buy_count,
        sell_count=signal_summary.sell_count,
        hold_count=signal_summary.hold_count,
        filter_passed=filter_result.passed,
        filter_reason=filter_result.reasons[0] if filter_result.reasons else "",
        region=region,
        sector=sector,
        filter_result=filter_result,
    )
