"""Momentum indicators — RSI, MACD, ROC."""
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




# ── Stochastic ──────────────────────────────────────────────────
@dataclass
class Stochastic(BaseIndicator):
    period: int = 14
    smooth: int = 3

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        if len(df) < self.period + 1:
            return IndicatorResult(
                name="Stochastic", signal=Signal.HOLD, score=0.0,
                category=SignalCategory.MOMENTUM,
                values={"%K": 50.0, "%D": 50.0},
            )
        low_min = df['low'].rolling(self.period).min()
        high_max = df['high'].rolling(self.period).max()
        denom = high_max - low_min
        k = 100 * (df['close'] - low_min) / denom.replace(0, np.finfo(float).eps)
        d = k.rolling(self.smooth).mean()
        k_val = self._last(k)
        d_val = self._last(d)

        if k_val < 20 and k_val > d_val:
            signal = Signal.BUY
            score = normalize_score(min((20 - k_val) / 20, 1.0))
        elif k_val > 80 and k_val < d_val:
            signal = Signal.SELL
            score = normalize_score(max((80 - k_val) / 20, -1.0))
        else:
            signal = Signal.HOLD
            score = normalize_score((k_val - 50) / 50)

        return IndicatorResult(
            name="Stochastic", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"%K": k_val, "%D": d_val},
        )


# ── Williams %R ──────────────────────────────────────────────────
@dataclass
class WilliamsR(BaseIndicator):
    period: int = 14

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        if len(df) < self.period + 1:
            return IndicatorResult(
                name="Williams %R", signal=Signal.HOLD, score=0.0,
                category=SignalCategory.MOMENTUM,
                values={"williams_r": -50.0},
            )
        high_max = df['high'].rolling(self.period).max()
        low_min = df['low'].rolling(self.period).min()
        denom = high_max - low_min
        wr = (high_max - df['close']) / denom.replace(0, np.finfo(float).eps) * -100
        wr_val = self._last(wr)

        if wr_val > -20:
            signal = Signal.BUY
            score = normalize_score(min((wr_val + 20) / 60, 1.0))
        elif wr_val < -80:
            signal = Signal.SELL
            score = normalize_score(max((wr_val + 80) / 60, -1.0))
        else:
            signal = Signal.HOLD
            score = normalize_score((wr_val + 50) / 100)

        return IndicatorResult(
            name="Williams %R", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"williams_r": wr_val},
        )


# ── CCI ──────────────────────────────────────────────────────────
@dataclass
class CCI(BaseIndicator):
    period: int = 20

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        if len(df) < self.period + 1:
            return IndicatorResult(
                name="CCI", signal=Signal.HOLD, score=0.0,
                category=SignalCategory.MOMENTUM,
                values={"cci": 0.0},
            )
        tp = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = tp.rolling(self.period).mean()
        mad = tp.rolling(self.period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
        cci = (tp - sma_tp) / (0.015 * mad.replace(0, np.finfo(float).eps))
        cci_val = self._last(cci)

        if cci_val < -100:
            signal = Signal.BUY
            score = normalize_score(min((-100 - cci_val) / 200, 1.0))
        elif cci_val > 100:
            signal = Signal.SELL
            score = normalize_score(max((100 - cci_val) / 200, -1.0))
        else:
            signal = Signal.HOLD
            score = normalize_score(cci_val / 200)

        return IndicatorResult(
            name="CCI", score=score, signal=signal,
            category=SignalCategory.MOMENTUM,
            values={"cci": cci_val},
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

