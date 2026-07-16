"""Momentum indicators — RSI, MACD, Stochastic, Williams %R, ROC, CCI."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .base import BaseIndicator, normalize_score
from .models import IndicatorResult, Signal, SignalCategory


# ── RSI ──────────────────────────────────────────────────────────
@dataclass
class RSI(BaseIndicator):
    period: int = 14

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / loss.replace(0, np.finfo(float).eps)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = self._last(rsi)

        if rsi_val > 70:
            signal = Signal.SELL
            score = normalize_score(-(rsi_val - 70) / 30)
        elif rsi_val < 30:
            signal = Signal.BUY
            score = normalize_score((30 - rsi_val) / 30)
        else:
            signal = Signal.HOLD
            score = normalize_score((rsi_val - 50) / 50)

        return IndicatorResult(
            name="RSI", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"rsi": rsi_val}
        )


# ── MACD ─────────────────────────────────────────────────────────
@dataclass
class MACD(BaseIndicator):
    fast: int = 12
    slow: int = 26
    signal_period: int = 9

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        ema_fast = df['close'].ewm(span=self.fast).mean()
        ema_slow = df['close'].ewm(span=self.slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period).mean()
        histogram = macd_line - signal_line

        macd_v = self._last(macd_line)
        sig_v = self._last(signal_line)
        hist_v = self._last(histogram)

        if hist_v > 0:
            score = normalize_score(min(hist_v / abs(macd_v + sig_v), 1.0) if (macd_v + sig_v) != 0 else 0.5)
            signal = Signal.BUY
        elif hist_v < 0:
            score = normalize_score(max(hist_v / abs(macd_v + sig_v), -1.0) if (macd_v + sig_v) != 0 else -0.5)
            signal = Signal.SELL
        else:
            score = 0.0
            signal = Signal.HOLD

        return IndicatorResult(
            name="MACD", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"macd": macd_v, "signal": sig_v, "histogram": hist_v}
        )


# ── Stochastic ───────────────────────────────────────────────────
@dataclass
class Stochastic(BaseIndicator):
    k_period: int = 14
    d_period: int = 3

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        low_min = df['low'].rolling(self.k_period).min()
        high_max = df['high'].rolling(self.k_period).max()
        k = 100 * (df['close'] - low_min) / (high_max - low_min + np.finfo(float).eps)
        d = k.rolling(self.d_period).mean()

        k_v = self._last(k)
        d_v = self._last(d)

        if k_v < 20:
            signal = Signal.BUY
            score = normalize_score((20 - k_v) / 20)
        elif k_v > 80:
            signal = Signal.SELL
            score = normalize_score((k_v - 80) / 20)
        else:
            signal = Signal.HOLD
            score = normalize_score((k_v - 50) / 50)

        return IndicatorResult(
            name="Stochastic", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"k": k_v, "d": d_v}
        )


# ── Williams %R ──────────────────────────────────────────────────
@dataclass
class WilliamsR(BaseIndicator):
    period: int = 14

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        high_max = df['high'].rolling(self.period).max()
        low_min = df['low'].rolling(self.period).min()
        wr = -100 * (high_max - df['close']) / (high_max - low_min + np.finfo(float).eps)

        wr_v = self._last(wr)
        # Williams %R ranges from 0 to -100
        if wr_v > -20:
            signal = Signal.SELL
            score = normalize_score((wr_v + 20) / 80)
        elif wr_v < -80:
            signal = Signal.BUY
            score = normalize_score((-80 - wr_v) / 80)
        else:
            signal = Signal.HOLD
            score = normalize_score(-(wr_v + 50) / 100)

        return IndicatorResult(
            name="Williams %R", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"wr": wr_v}
        )


# ── ROC ──────────────────────────────────────────────────────────
@dataclass
class ROC(BaseIndicator):
    period: int = 10

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        roc = 100 * (df['close'] / df['close'].shift(self.period) - 1)
        roc_v = self._last(roc)

        if roc_v > 0:
            signal = Signal.BUY
            score = normalize_score(min(roc_v / 20, 1.0))
        elif roc_v < 0:
            signal = Signal.SELL
            score = normalize_score(max(roc_v / 20, -1.0))
        else:
            signal = Signal.HOLD
            score = 0.0

        return IndicatorResult(
            name="ROC", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"roc": roc_v}
        )


# ── CCI ──────────────────────────────────────────────────────────
@dataclass
class CCI(BaseIndicator):
    period: int = 20

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        tp = (df['high'] + df['low'] + df['close']) / 3
        ma = tp.rolling(self.period).mean()
        mad = tp.rolling(self.period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        cci = (tp - ma) / (0.015 * mad + np.finfo(float).eps)

        cci_v = self._last(cci)

        if cci_v > 100:
            signal = Signal.SELL  # Overbought
            score = normalize_score(max(-cci_v / 300, -1.0))  # Negative of positive CCI → negative score
        elif cci_v < -100:
            signal = Signal.BUY  # Oversold
            score = normalize_score(-cci_v / 300)  # Negative of negative CCI → positive score
        else:
            signal = Signal.HOLD
            score = normalize_score(cci_v / 100)

        return IndicatorResult(
            name="CCI", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"cci": cci_v}
        )
