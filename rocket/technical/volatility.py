"""Volatility indicators — Bollinger Bands, ATR, Donchian Channels."""
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


# ── Donchian Channels ───────────────────────────────────────────
@dataclass
class DonchianChannel(BaseIndicator):
    period: int = 20

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        upper = df['high'].rolling(self.period).max()
        lower = df['low'].rolling(self.period).min()
        midpoint = (upper + lower) / 2

        close = self._last(df['close'])
        upper_val = self._last(upper)
        lower_val = self._last(lower)

        if upper_val == lower_val:
            return IndicatorResult(
                name="Donchian", score=0, signal=Signal.HOLD,
                category=SignalCategory.VOLATILITY,
                values={"upper": upper_val, "lower": lower_val}
            )

        position = (close - lower_val) / (upper_val - lower_val)

        if close >= upper_val:
            score = normalize_score(1.0)
            signal = Signal.BUY
        elif close <= lower_val:
            score = normalize_score(-1.0)
            signal = Signal.SELL
        else:
            score = normalize_score(2 * position - 1)
            signal = Signal.HOLD

        return IndicatorResult(
            name="Donchian", score=score, signal=signal,
            category=SignalCategory.VOLATILITY,
            values={"upper": upper_val, "lower": lower_val, "position": position}
        )
