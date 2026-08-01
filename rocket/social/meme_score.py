"""Meme stock detection for Rocket Scanner.

Combines social sentiment (StockTwits), short interest
(data from FINVIZ), and volume anomaly detection to identify
meme stocks.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MemeSignal:
    """Represents a meme stock signal for a ticker.

    Attributes:
        ticker: The ticker symbol.
        is_meme_stock: True if meme criteria are met.
        meme_score: Composite meme score (0-100).
        sentiment_bull_pct: StockTwits bullish percentage (100-based).
        short_interest_pct: Short percentage of float.
        short_ratio: Days to cover for short positions.
        volume_spike: Current volume divided by average volume.
        details: Additional metrics and context.
    """

    ticker: str
    is_meme_stock: bool
    meme_score: float
    sentiment_bull_pct: float
    short_interest_pct: float
    short_ratio: float
    volume_spike: float
    details: dict


def compute_meme_score(
    ticker: str,
    sentiment_score: float,  # 0-1 (StockTwits bullish %)
    short_interest: float,  # % of float
    current_volume: float,
    avg_volume: float,
    short_volume_ratio: float = 0.0,
) -> MemeSignal:
    """Compute meme stock signal.

    Scoring (0-100):
        - Bullish sentiment > 70%: +35 points
        - Short interest > 20%: +25 points
        - Short volume ratio > 5 (proxy for short ratio): +20 points
        - Volume spike > 3x avg: +20 points

    Args:
        ticker: Ticker symbol.
        sentiment_score: Bullish percentage as fraction (0.0 = 0%, 1.0 = 100%).
        short_interest: Short interest as percentage of float (e.g. 20.0 = 20%).
        current_volume: Current day's trading volume.
        avg_volume: Average daily trading volume.
        short_volume_ratio: Short volume / total volume ratio.

    Returns:
        MemeSignal dataclass with computed metrics.
    """
    # Fallback defaults when data is unavailable
    sent_bull = min(100.0, max(0.0, sentiment_score * 100.0))
    if short_interest < 0:
        short_interest = 0.0
    if avg_volume <= 0:
        avg_volume = current_volume if current_volume > 0 else 1.0

    volume_spike = current_volume / avg_volume if avg_volume > 0 else 0.0

    score = 0.0

    # Bullish sentiment > 70%: +35 points
    if sent_bull > 70.0:
        score += 35.0

    # Short interest > 20%: +25 points
    if short_interest > 20.0:
        score += 25.0

    # Short volume ratio > 5 (proxy for short ratio days-to-cover > 5): +20 points
    if short_volume_ratio > 5.0:
        score += 20.0

    # Volume spike > 3x avg: +20 points
    if volume_spike > 3.0:
        score += 20.0

    is_meme = score >= 50.0

    details = {
        "sentiment_score": round(sentiment_score, 3),
        "volume_current": current_volume,
        "volume_avg": avg_volume,
        "is_vigorous_short": short_interest > 50.0,
    }

    return MemeSignal(
        ticker=ticker.upper(),
        is_meme_stock=is_meme,
        meme_score=round(score, 1),
        sentiment_bull_pct=round(sent_bull, 1),
        short_interest_pct=round(short_interest, 1),
        short_ratio=round(short_volume_ratio, 1),
        volume_spike=round(volume_spike, 2),
        details=details,
    )


def meme_score_from_defaults(
    ticker: str,
    current_volume: float,
    avg_volume: float,
) -> MemeSignal:
    """Compute meme score with default (neutral) sentiment.

    Convenience function for use when StockTwits data is unavailable.
    Uses 0.5 (neutral) sentiment and 0 short interest.

    Args:
        ticker: Ticker symbol.
        current_volume: Current volume from yfinance.
        avg_volume: Average volume from yfinance.

    Returns:
        MemeSignal with neutral sentiment and any volume/short data available.
    """
    return compute_meme_score(
        ticker=ticker,
        sentiment_score=0.5,  # neutral default
        short_interest=0.0,   # no short interest data
        current_volume=current_volume,
        avg_volume=avg_volume,
        short_volume_ratio=0.0,
    )


def meme_score_from_stocktwits(
    ticker: str,
    current_volume: float,
    avg_volume: float,
) -> MemeSignal:
    """Fetch all data from StockTwits and compute meme score.

    Gracefully degrades if any data source is unavailable.

    Args:
        ticker: Ticker symbol.
        current_volume: Current volume from yfinance.
        avg_volume: Average volume from yfinance.

    Returns:
        MemeSignal dataclass.
    """
    # Fetch StockTwits sentiment
    try:
        from rocket.social.stocktwits import get_bullish_pct
        bull_pct = get_bullish_pct(ticker)
    except Exception:
        bull_pct = 0.5

    # Fetch short interest from FINVIZ
    try:
        from rocket.social.short_interest import get_short_interest as _get_si
        si_map = _get_si([ticker])
        si_obj = si_map.get(ticker)
        short_pct = si_obj.short_percent_of_float if si_obj else 0.0
        svi = si_obj.short_volume_ratio if si_obj else 0.0
    except Exception:
        short_pct = 0.0
        svi = 0.0

    return compute_meme_score(
        ticker=ticker,
        sentiment_score=bull_pct,
        short_interest=short_pct,
        current_volume=current_volume,
        avg_volume=avg_volume,
        short_volume_ratio=svi,
    )
