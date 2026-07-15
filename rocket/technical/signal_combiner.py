"""Combine individual indicator signals into a summary."""
import numpy as np
from dataclasses import dataclass, field
from typing import List
from .models import IndicatorResult, Signal, SignalCategory


@dataclass
class SignalSummary:
    """Aggregated signals grouped by category."""
    momentum_score: float = 0.0
    trend_score: float = 0.0
    volatility_score: float = 0.0
    volume_score: float = 0.0
    overall_score: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0
    details: list = field(default_factory=list)


class SignalCombiner:
    """Combine signals from multiple indicators by category."""

    CATEGORY_WEIGHTS = {
        SignalCategory.MOMENTUM: 0.40,
        SignalCategory.TREND: 0.30,
        SignalCategory.VOLATILITY: 0.20,
        SignalCategory.VOLUME: 0.10,
    }

    def combine(self, results: List[IndicatorResult]) -> SignalSummary:
        """Combine a list of IndicatorResults into a SignalSummary."""
        categories = {
            SignalCategory.MOMENTUM: [],
            SignalCategory.TREND: [],
            SignalCategory.VOLATILITY: [],
            SignalCategory.VOLUME: [],
        }

        buy_count = 0
        sell_count = 0
        hold_count = 0

        for r in results:
            categories[r.category].append(r)
            if r.signal == Signal.BUY:
                buy_count += 1
            elif r.signal == Signal.SELL:
                sell_count += 1
            else:
                hold_count += 1

        # Average score per category
        momentum_scores = [r.score for r in categories[SignalCategory.MOMENTUM]]
        trend_scores = [r.score for r in categories[SignalCategory.TREND]]
        vol_scores = [r.score for r in categories[SignalCategory.VOLATILITY]]
        volm_scores = [r.score for r in categories[SignalCategory.VOLUME]]

        momentum_avg = np.mean(momentum_scores) if momentum_scores else 0.0
        trend_avg = np.mean(trend_scores) if trend_scores else 0.0
        vol_avg = np.mean(vol_scores) if vol_scores else 0.0
        volm_avg = np.mean(volm_scores) if volm_scores else 0.0

        # Overall = weighted average
        weights = self.CATEGORY_WEIGHTS
        overall = (
            momentum_avg * weights[SignalCategory.MOMENTUM]
            + trend_avg * weights[SignalCategory.TREND]
            + vol_avg * weights[SignalCategory.VOLATILITY]
            + volm_avg * weights[SignalCategory.VOLUME]
        )

        summary = SignalSummary(
            momentum_score=round(float(momentum_avg), 4),
            trend_score=round(float(trend_avg), 4),
            volatility_score=round(float(vol_avg), 4),
            volume_score=round(float(volm_avg), 4),
            overall_score=round(float(overall), 4),
            buy_count=buy_count,
            sell_count=sell_count,
            hold_count=hold_count,
            details=[{"name": r.name, "score": r.score,
                      "signal": r.signal.value, "category": r.category.value}
                     for r in results]
        )

        return summary
