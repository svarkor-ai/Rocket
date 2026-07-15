"""Run all momentum indicators on a DataFrame."""

from .models import IndicatorResult
from .momentum import (RSI, MACD, Stochastic, WilliamsR, ROC, CCI)

# Map of indicator names → class instances
_MOMENTUM_INDICATORS = [
    ('RSI', RSI()),
    ('MACD', MACD()),
    ('Stochastic', Stochastic()),
    ('WilliamsR', WilliamsR()),
    ('ROC', ROC()),
    ('CCI', CCI()),
]


def run_momentum_indicators(df) -> list[IndicatorResult]:
    """Execute every momentum indicator and return results."""
    results = []
    for name, ind in _MOMENTUM_INDICATORS:
        r = ind.calculate(df)
        if r:
            results.append(r)
    return results
