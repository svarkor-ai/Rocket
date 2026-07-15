"""Compute full RocketScore for a single ticker."""
from ..data.models import TickerInfo
from ..technical.signal_combiner import SignalSummary
from ..technical.signal_combiner import SignalCombiner
from ..technical.momentum import RSI, MACD, Stochastic, WilliamsR, ROC, CCI
from ..technical.trend import EMA9, EMA21, EMA50, EMA200, EMACrossover, ADX
from ..technical.volatility import BollingerBands, ATR, DonchianChannel
from ..technical.volume import OBV, MFI, VWAPIndicator
from ..technical.advanced import IchimokuCloud, Supertrend, ParabolicSAR
from .filter import apply_filters
from .weighter import weight_scores


# All indicator instances
INDICATORS = [
    # Momentum
    RSI(), MACD(), Stochastic(), WilliamsR(), ROC(), CCI(),
    # Trend
    EMA9(), EMA21(), EMA50(), EMA200(), EMACrossover(), ADX(),
    # Volatility
    BollingerBands(), ATR(), DonchianChannel(),
    # Volume
    OBV(), MFI(), VWAPIndicator(),
    # Advanced
    IchimokuCloud(), Supertrend(), ParabolicSAR(),
]


def compute_rocket_score(
    df,
    ticker_info: TickerInfo,
    current_price: float = 0.0,
) -> dict:
    """Run all indicators, compute signals, return dict of score + details."""
    # Run all indicators
    results = []
    for indicator in INDICATORS:
        try:
            r = indicator.calculate(df)
            results.append(r)
        except Exception as e:
            print(f"Indicator {indicator} failed: {e}")

    # Combine signals
    combiner = SignalCombiner()
    summary = combiner.combine(results)

    # Apply filters
    filter_result = apply_filters(ticker_info, current_price)

    # Weight scores
    rocket_score = weight_scores(
        signal_summary=summary,
        filter_result=filter_result,
        ticker=ticker_info.ticker,
        region=ticker_info.region.value,
        sector=ticker_info.sector,
    )

    return {
        "rocket_score": rocket_score,
        "signal_summary": summary,
        "filter_result": filter_result,
    }
