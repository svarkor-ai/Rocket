"""Trend indicators — EMA, ADX, EMA crossover."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .base import BaseIndicator, normalize_score
from .models import IndicatorResult, Signal, SignalCategory


# ── EMAs ─────────────────────────────────────────────────────────
@dataclass
class EMA9(BaseIndicator):
    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        ema = df['close'].ewm(span=9, adjust=False).mean()
        ema_val = self._last(ema)
        close = self._last(df['close'])
        score = normalize_score((close - ema_val) / (close + np.finfo(float).eps))
        return IndicatorResult(
            name="EMA9", score=score,
            signal=Signal.BUY if close > ema_val else Signal.SELL,
            category=SignalCategory.TREND,
            values={"ema": ema_val, "price": close}
        )


@dataclass
class EMA21(BaseIndicator):
    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        ema = df['close'].ewm(span=21, adjust=False).mean()
        ema_val = self._last(ema)
        close = self._last(df['close'])
        score = normalize_score((close - ema_val) / (close + np.finfo(float).eps))
        return IndicatorResult(
            name="EMA21", score=score,
            signal=Signal.BUY if close > ema_val else Signal.SELL,
            category=SignalCategory.TREND,
            values={"ema": ema_val, "price": close}
        )


@dataclass
class EMA50(BaseIndicator):
    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        ema = df['close'].ewm(span=50, adjust=False).mean()
        ema_val = self._last(ema)
        close = self._last(df['close'])
        score = normalize_score((close - ema_val) / (close + np.finfo(float).eps))
        return IndicatorResult(
            name="EMA50", score=score,
            signal=Signal.BUY if close > ema_val else Signal.SELL,
            category=SignalCategory.TREND,
            values={"ema": ema_val, "price": close}
        )


@dataclass
class EMA200(BaseIndicator):
    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        ema = df['close'].ewm(span=200, adjust=False).mean()
        ema_val = self._last(ema)
        close = self._last(df['close'])
        if ema_val == 0:
            return IndicatorResult(name="EMA200", score=0, signal=Signal.HOLD,
                                   category=SignalCategory.TREND, values={"ema": 0, "price": close})
        score = normalize_score((close - ema_val) / (close + np.finfo(float).eps))
        return IndicatorResult(
            name="EMA200", score=score,
            signal=Signal.BUY if close > ema_val else Signal.SELL,
            category=SignalCategory.TREND,
            values={"ema": ema_val, "price": close}
        )


# ── EMACrossover ────────────────────────────────────────────────
@dataclass
class EMACrossover(BaseIndicator):
    fast: int = 9
    slow: int = 21

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        ema_fast = df['close'].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow, adjust=False).mean()

        fast_cur = self._last(ema_fast)
        slow_cur = self._last(ema_slow)
        fast_prev = self._prev(ema_fast, 1)
        slow_prev = self._prev(ema_slow, 1)

        if fast_prev is not None and slow_prev is not None:
            if fast_prev <= slow_prev and fast_cur > slow_cur:
                signal = Signal.BUY
                score = normalize_score(0.8)
            elif fast_prev >= slow_prev and fast_cur < slow_cur:
                signal = Signal.SELL
                score = normalize_score(-0.8)
            elif fast_cur > slow_cur:
                score = normalize_score(min((fast_cur - slow_cur) / (fast_cur + slow_cur) * 2, 0.6))
                signal = Signal.BUY
            else:
                score = normalize_score(max((fast_cur - slow_cur) / (fast_cur + slow_cur) * 2, -0.6))
                signal = Signal.SELL
        else:
            score = 0.0
            signal = Signal.HOLD

        return IndicatorResult(
            name=f"EMA{self.fast}/{self.slow}", score=score, signal=signal,
            category=SignalCategory.TREND,
            values={"ema_fast": fast_cur, "ema_slow": slow_cur}
        )


# ── ADX ──────────────────────────────────────────────────────────
@dataclass
class ADX(BaseIndicator):
    period: int = 14

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(self.period).mean()
        plus_di = 100 * plus_dm.rolling(self.period).mean() / (atr + np.finfo(float).eps)
        minus_di = 100 * minus_dm.rolling(self.period).mean() / (atr + np.finfo(float).eps)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + np.finfo(float).eps)
        adx = dx.rolling(self.period).mean()

        adx_val = self._last(adx)
        plus_di_val = self._last(plus_di)
        minus_di_val = self._last(minus_di)

        if adx_val > 25 and plus_di_val > minus_di_val:
            score = normalize_score(min(adx_val / 100, 1.0))
            signal = Signal.BUY
        elif adx_val > 25 and minus_di_val > plus_di_val:
            score = normalize_score(max(-adx_val / 100, -1.0))
            signal = Signal.SELL
        else:
            score = 0.0
            signal = Signal.HOLD

        return IndicatorResult(
            name="ADX", score=score, signal=signal,
            category=SignalCategory.TREND,
            values={"adx": adx_val, "plus_di": plus_di_val, "minus_di": minus_di_val}
        )
