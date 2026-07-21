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

