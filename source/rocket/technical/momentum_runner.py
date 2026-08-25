"""Run all momentum indicators on a DataFrame."""

"""Quick momentum runner — returns list of dict scores for a single ticker."""
from ..technical.momentum import RSI, MACD, ROC
from ..technical.models import IndicatorResult

INDICATORS = [RSI(), MACD(), ROC()]
_MOMENTUM_INDICATORS = [
    ('RSI', RSI()),
    ('MACD', MACD()),
    ('ROC', ROC()),
]


def run_momentum_indicators(df) -> list[IndicatorResult]:
    """Execute every momentum indicator and return results."""
    results = []
    for name, ind in _MOMENTUM_INDICATORS:
        r = ind.calculate(df)
        if r:
            results.append(r)
    return results
