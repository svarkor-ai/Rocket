"""Run all momentum indicators on a DataFrame."""

from .base import BaseIndicator
from .models import IndicatorResult
from .momentum import (calc_rsi, calc_macd, calc_stochastic,
                       calc_williams_r, calc_roc, calc_cci)


def run_momentum_indicators(df) -> list[IndicatorResult]:
    """Execute every momentum indicator and return results."""
    return [
        calc_rsi(df),
        calc_macd(df),
        calc_stochastic(df),
        calc_williams_r(df),
        calc_roc(df),
        calc_cci(df),
    ]
