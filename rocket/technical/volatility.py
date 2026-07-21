"""Volatility indicators — ATR, Bollinger Bands."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .base import BaseIndicator, normalize_score
from .models import IndicatorResult, Signal, SignalCategory


# ── Bollinger Bands ─────────────────────────────────────────────
@dataclass
class BollingerBands(BaseIndicator):
    period: int = 20
    std_dev: float = 2.0

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        sma = df['close'].rolling(self.period).mean()
        std = df['close'].rolling(self.period).std()
        upper = sma + self.std_dev * std
        lower = sma - self.std_dev * std

        close = self._last(df['close'])
        upper_val = self._last(upper)
        lower_val = self._last(lower)
        sma_val = self._last(sma)

        if upper_val == lower_val:
            return IndicatorResult(
                name="Bollinger Bands", score=0, signal=Signal.HOLD,
                category=SignalCategory.VOLATILITY,
                values={"upper": upper_val, "sma": sma_val, "lower": lower_val}
            )

        position = (close - lower_val) / (upper_val - lower_val)

        if close >= upper_val:
            score = normalize_score(-((close - upper_val) / (upper_val - lower_val)))
            signal = Signal.SELL
        elif close <= lower_val:
            score = normalize_score(((upper_val - close) / (upper_val - lower_val)))
            signal = Signal.BUY
        else:
            score = normalize_score(position - 0.5)
            signal = Signal.HOLD

        return IndicatorResult(
            name="Bollinger Bands", score=score, signal=signal,
            category=SignalCategory.VOLATILITY,
            values={
                "upper": upper_val, "sma": sma_val, "lower": lower_val,
                "position": position
            }
        )


# ── Donchian Channel ─────────────────────────────────────────────
@dataclass
class DonchianChannel(BaseIndicator):
    period: int = 20

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        if len(df) < self.period:
            return IndicatorResult(
                name="Donchian Channel", signal=Signal.HOLD, score=0.0,
                category=SignalCategory.VOLATILITY,
                values={"upper": 0.0, "middle": 0.0, "lower": 0.0, "price": 0.0},
            )
        upper = df['high'].rolling(self.period).max()
        lower = df['low'].rolling(self.period).min()
        middle = (upper + lower) / 2
        price = self._last(df['close'])
        upper_val = self._last(upper)
        lower_val = self._last(lower)
        middle_val = self._last(middle)

        channel_range = upper_val - lower_val
        if channel_range == 0:
            return IndicatorResult(
                name="Donchian Channel", signal=Signal.HOLD, score=0.0,
                category=SignalCategory.VOLATILITY,
                values={"upper": upper_val, "middle": middle_val,
                        "lower": lower_val, "price": price},
            )

        if price > upper_val:
            signal = Signal.BUY
            score = normalize_score(min((price - upper_val) / channel_range, 1.0))
        elif price < lower_val:
            signal = Signal.SELL
            score = normalize_score(max(-(upper_val - price) / channel_range, -1.0))
        else:
            signal = Signal.HOLD
            position = (price - lower_val) / channel_range - 0.5
            score = normalize_score(position * 2)

        return IndicatorResult(
            name="Donchian Channel", score=score, signal=signal,
            category=SignalCategory.VOLATILITY,
            values={"upper": upper_val, "middle": middle_val,
                    "lower": lower_val, "price": price},
        )


# ── ATR ─────────────────────────────────────────────────────────
@dataclass
class ATR(BaseIndicator):
    period: int = 14

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        high = df['high']
        low = df['low']
        close_prev = df['close'].shift(1)

        tr = pd.concat([
            high - low,
            (high - close_prev).abs(),
            (low - close_prev).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(self.period).mean()
        atr_val = self._last(atr)
        close = self._last(df['close'])
        atr_pct = atr_val / close if close else 0

        return IndicatorResult(
            name="ATR", score=0, signal=Signal.HOLD,
            category=SignalCategory.VOLATILITY,
            values={"atr": atr_val, "atr_pct": atr_pct}
        )



