"""Volume indicators — OBV, MFI, VWAP."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .base import BaseIndicator, normalize_score
from .models import IndicatorResult, Signal, SignalCategory


# ── OBV ──────────────────────────────────────────────────────────
@dataclass
class OBV(BaseIndicator):
    period: int = 20

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        direction = np.sign(df['close'].diff())
        direction = direction.fillna(0).astype(int)
        obv = (direction * df['volume']).cumsum()

        obv_trend = obv.diff(self.period)
        obv_val = self._last(obv)
        obv_trend_val = self._last(obv_trend)

        if obv_trend_val > 0:
            score = normalize_score(min(obv_trend_val / (abs(obv_val) + 1), 0.7))
            signal = Signal.BUY
        elif obv_trend_val < 0:
            score = normalize_score(max(obv_trend_val / (abs(obv_val) + 1), -0.7))
            signal = Signal.SELL
        else:
            score = 0.0
            signal = Signal.HOLD

        return IndicatorResult(
            name="OBV", score=score, signal=signal,
            category=SignalCategory.VOLUME,
            values={"obv": obv_val, "obv_trend": obv_trend_val}
        )


# ── MFI ─────────────────────────────────────────────────────────
@dataclass
class MFI(BaseIndicator):
    period: int = 14

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        tp = (df['high'] + df['low'] + df['close']) / 3
        raw_money_flow = tp * df['volume']

        direction = tp.diff()
        pos_flow = raw_money_flow.where(direction > 0, 0.0)
        neg_flow = raw_money_flow.where(direction < 0, 0.0)

        pos_avg = pos_flow.rolling(self.period).mean()
        neg_avg = neg_flow.rolling(self.period).mean()

        mr = pos_avg / (neg_avg + np.finfo(float).eps)
        mfi = 100 - (100 / (1 + mr))

        mfi_val = self._last(mfi)

        if mfi_val > 80:
            score = normalize_score(-(mfi_val - 80) / 20)
            signal = Signal.SELL
        elif mfi_val < 20:
            score = normalize_score((20 - mfi_val) / 20)
            signal = Signal.BUY
        else:
            score = normalize_score((mfi_val - 50) / 50)
            signal = Signal.HOLD

        return IndicatorResult(
            name="MFI", score=score, signal=signal,
            category=SignalCategory.VOLUME,
            values={"mfi": mfi_val}
        )


# ── VWAP ─────────────────────────────────────────────────────────
@dataclass
class VWAPIndicator(BaseIndicator):
    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        tp = (df['high'] + df['low'] + df['close']) / 3
        cum_tp_vol = (tp * df['volume']).cumsum()
        cum_vol = df['volume'].cumsum()
        vwap = cum_tp_vol / (cum_vol + np.finfo(float).eps)

        close = self._last(df['close'])
        vwap_val = self._last(vwap)

        if close > vwap_val:
            score = normalize_score(min((close - vwap_val) / close, 0.7))
            signal = Signal.BUY
        else:
            score = normalize_score(max(-((vwap_val - close) / close), -0.7))
            signal = Signal.SELL

        return IndicatorResult(
            name="VWAP", score=score, signal=signal,
            category=SignalCategory.VOLUME,
            values={"vwap": vwap_val, "price": close}
        )
