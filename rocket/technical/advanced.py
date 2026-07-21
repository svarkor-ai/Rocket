"""Advanced indicators — Ichimoku Cloud, Supertrend."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .base import BaseIndicator, normalize_score
from .models import IndicatorResult, Signal, SignalCategory


# ── Ichimoku Cloud ──────────────────────────────────────────────
@dataclass
class IchimokuCloud(BaseIndicator):
    conversion: int = 9
    base: int = 26
    lagging: int = 52
    span_b: int = 52

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        mid = (df['high'] + df['low']) / 2

        cl = (
            df['high'].rolling(self.conversion).max()
            + df['low'].rolling(self.conversion).min()
        ) / 2
        bl = (
            df['high'].rolling(self.base).max()
            + df['low'].rolling(self.base).min()
        ) / 2
        span_a = (cl + bl) / 2
        span_b = (
            df['high'].rolling(self.span_b).max()
            + df['low'].rolling(self.span_b).min()
        ) / 2

        close = self._last(df['close'])
        span_a_val = self._last(span_a)
        span_b_val = self._last(span_b)

        if close > span_a_val and close > span_b_val:
            score = normalize_score(min((close - max(span_a_val, span_b_val)) / close, 1.0))
            signal = Signal.BUY
        elif close < span_a_val and close < span_b_val:
            score = normalize_score(max(-(max(span_a_val, span_b_val) - close) / close, -1.0))
            signal = Signal.SELL
        else:
            score = 0.0
            signal = Signal.HOLD

        return IndicatorResult(
            name="Ichimoku", score=score, signal=signal,
            category=SignalCategory.TREND,
            values={
                "close": close, "span_a": span_a_val, "span_b": span_b_val
            }
        )


# ── Supertrend ──────────────────────────────────────────────────
@dataclass
class Supertrend(BaseIndicator):
    atr_period: int = 10
    multiplier: float = 3.0

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        # ATR
        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1)))
        )
        # Handle first element
        tr[0] = high[0] - low[0]
        atr = np.zeros(len(tr))
        atr[:self.atr_period] = np.mean(tr[:self.atr_period])
        for i in range(self.atr_period, len(tr)):
            atr[i] = (atr[i - 1] * (self.atr_period - 1) + tr[i]) / self.atr_period

        mid_upper = (high + low) / 2 + self.multiplier * atr
        mid_lower = (high + low) / 2 - self.multiplier * atr

        # Simplified supertrend
        close_val = close[-1]
        last_upper = mid_upper[-1]
        last_lower = mid_lower[-1]

        if close_val > last_lower:
            score = normalize_score(min((close_val - last_lower) / (last_upper - last_lower + 1), 1.0))
            signal = Signal.BUY
        else:
            score = normalize_score(max(-((last_upper - close_val) / (last_upper - last_lower + 1)), -1.0))
            signal = Signal.SELL

        return IndicatorResult(
            name="Supertrend", score=score, signal=signal,
            category=SignalCategory.TREND,
            values={"upper": last_upper, "lower": last_lower, "price": close_val}
        )


