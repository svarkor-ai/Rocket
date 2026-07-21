"""Advanced indicators — Ichimoku Cloud, Supertrend."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .base import BaseIndicator, normalize_score
from .models import IndicatorResult, Signal, SignalCategory
from .patterns import ZigZagDetector
from .momentum import RSI as RSIIndicator
from .trend import ADX as ADXIndicator


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


# ── AutoTrend ───────────────────────────────────────────────────
@dataclass
class AutoTrend(BaseIndicator):
    """AutoTrend: Linear regression trendlines with breakout detection.

    Uses ZigZag pivots to identify high/low pivot points, then fits
    linear regression lines through them. Detects breakouts when the
    current close price exceeds the projected trendlines.
    """
    high_window: int = 20
    low_window: int = 20
    min_pivots: int = 3
    breakout_threshold: float = 0.005  # 0.5% breakout

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Calculate trendlines and breakout signal.

        Returns:
            name="AutoTrend"
            signal=BUY/SELL/HOLD
            score in [-1, 1]
            category=SignalCategory.TREND
            values with trend_direction, trend_strength, channel metrics,
            breakout_signal, high_slope, low_slope.
        """
        df = self._normalize_columns(df)

        # Need enough data for pivots
        if len(df) < self.high_window + self.low_window:
            return IndicatorResult(
                name="AutoTrend", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={
                    "trend_direction": "FLAT",
                    "trend_strength": 0.0,
                    "channel_upper": 0.0,
                    "channel_lower": 0.0,
                    "channel_width": 0.0,
                    "breakout_signal": "NONE",
                    "high_slope": 0.0,
                    "low_slope": 0.0,
                },
            )

        # ZigZagDetector expects 'High'/'Low' (uppercase), so pass a copy
        zz_df = df.rename(columns={
            'high': 'High', 'low': 'Low', 'close': 'Close',
        })
        zz = ZigZagDetector(
            price_threshold=0.02,
            min_bar_count=3,
            window=3,
        )
        pivots = zz.detect(zz_df)

        # Need minimum pivots
        if len(pivots) < self.min_pivots:
            return IndicatorResult(
                name="AutoTrend", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={
                    "trend_direction": "FLAT",
                    "trend_strength": 0.0,
                    "channel_upper": 0.0,
                    "channel_lower": 0.0,
                    "channel_width": 0.0,
                    "breakout_signal": "NONE",
                    "high_slope": 0.0,
                    "low_slope": 0.0,
                },
            )

        # Group pivots by type
        high_pivots = [p for p in pivots if p.is_high]
        low_pivots = [p for p in pivots if not p.is_high]

        # Need enough of each type for regression
        if len(high_pivots) < self.min_pivots or len(low_pivots) < self.min_pivots:
            return IndicatorResult(
                name="AutoTrend", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={
                    "trend_direction": "FLAT",
                    "trend_strength": 0.0,
                    "channel_upper": 0.0,
                    "channel_lower": 0.0,
                    "channel_width": 0.0,
                    "breakout_signal": "NONE",
                    "high_slope": 0.0,
                    "low_slope": 0.0,
                },
            )

        # Use last 3+ high pivots for regression
        use_highs = high_pivots[-self.min_pivots:] if len(high_pivots) < self.min_pivots else high_pivots[-self.min_pivots:]
        x_h = np.array([p.index for p in use_highs], dtype=np.float64)
        y_h = np.array([p.price for p in use_highs], dtype=np.float64)
        high_deg = np.polyfit(x_h, y_h, 1)
        high_slope = float(high_deg[0])
        high_intercept = float(high_deg[1])
        high_r = self._pearson_r(x_h, y_h)

        # Use last 3+ low pivots for regression
        use_lows = low_pivots[-self.min_pivots:] if len(low_pivots) < self.min_pivots else low_pivots[-self.min_pivots:]
        x_l = np.array([p.index for p in use_lows], dtype=np.float64)
        y_l = np.array([p.price for p in use_lows], dtype=np.float64)
        low_deg = np.polyfit(x_l, y_l, 1)
        low_slope = float(low_deg[0])
        low_intercept = float(low_deg[1])
        low_r = self._pearson_r(x_l, y_l)

        # Trend direction
        if high_slope > 0.01 and low_slope > 0.01:
            trend_direction = "UP"
        elif high_slope < -0.01 and low_slope < -0.01:
            trend_direction = "DOWN"
        else:
            trend_direction = "FLAT"

        # Trend strength = average absolute correlation
        trend_strength = float((abs(high_r) + abs(low_r)) / 2.0)

        # Predict channel at the last index
        last_idx = len(df) - 1
        channel_upper = float(high_intercept + high_slope * last_idx)
        channel_lower = float(low_intercept + low_slope * last_idx)

        # Channel width
        if channel_upper > 0:
            channel_width = float((channel_upper - channel_lower) / channel_upper)
        else:
            channel_width = 0.0

        # Close price
        close = self._last(df['close'])

        # Breakout detection
        if close > channel_upper:
            if (close - channel_upper) / channel_upper >= self.breakout_threshold:
                breakout_signal = "UP"
            else:
                breakout_signal = "NONE"
        elif close < channel_lower:
            if (channel_lower - close) / channel_lower >= self.breakout_threshold:
                breakout_signal = "DOWN"
            else:
                breakout_signal = "NONE"
        else:
            breakout_signal = "NONE"

        # Signal and score
        if breakout_signal == "UP":
            breakout_direction = 1.0
            signal = Signal.BUY
        elif breakout_signal == "DOWN":
            breakout_direction = -1.0
            signal = Signal.SELL
        else:
            breakout_direction = 0.0
            signal = Signal.HOLD

        score = normalize_score(breakout_direction * trend_strength)

        return IndicatorResult(
            name="AutoTrend",
            score=score,
            signal=signal,
            category=SignalCategory.TREND,
            values={
                "trend_direction": trend_direction,
                "trend_strength": trend_strength,
                "channel_upper": channel_upper,
                "channel_lower": channel_lower,
                "channel_width": channel_width,
                "breakout_signal": breakout_signal,
                "high_slope": high_slope,
                "low_slope": low_slope,
            },
        )

    def _pearson_r(self, x: np.ndarray, y: np.ndarray) -> float:
        """Compute Pearson correlation coefficient r between two arrays."""
        if len(x) < 2:
            return 0.0
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        num = np.sum((x - x_mean) * (y - y_mean))
        den_x = np.sqrt(np.sum((x - x_mean) ** 2))
        den_y = np.sqrt(np.sum((y - y_mean) ** 2))
        if den_x == 0 or den_y == 0:
            return 0.0
        return float(num / (den_x * den_y))


# ── RubeGoldberg ────────────────────────────────────────────────
@dataclass
class RubeGoldberg(BaseIndicator):
    """RubeGoldberg: Multi-trigger reversal signal (RSI + ADX + SAR).

    Fires a strong BUY/SELL when three independent indicators
    simultaneously confirm a reversal zone:
      - RSI in extreme zone (oversold/overbought)
      - ADX spike (high trend strength)
      - Parabolic SAR flip (trend reversal)
    """
    rsi_period: int = 14
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    adx_period: int = 14
    adx_spike_threshold: float = 25
    sar_step: float = 0.02
    sar_max: float = 0.2
    sar_flip_bars: int = 3
    min_data_points: int = 50

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        """Return multi-trigger reversal signal.

        Returns:
            name="RubeGoldberg"
            signal=BUY/SELL/HOLD
            score in [-1, 1]
            category=SignalCategory.TREND
            values with RSI/ADX/SAR metrics and trigger booleans.
        """
        df = self._normalize_columns(df)

        # Data-length guard
        if len(df) < self.min_data_points:
            return IndicatorResult(
                name="RubeGoldberg", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={
                    "rsi": 0.0, "adx": 0.0,
                    "sar_flip_direction": "NONE",
                    "trigger_count": 0,
                    "rsi_trigger": False, "adx_trigger": False,
                    "sar_trigger": False,
                    "rsi_value": 0.0, "adx_value": 0.0,
                },
            )

        closes = df['close'].to_numpy(dtype=np.float64)
        highs = df['high'].to_numpy(dtype=np.float64)
        lows = df['low'].to_numpy(dtype=np.float64)

        # ── 1. RSI ──────────────────────────────────────────────
        rsi_series = RSIIndicator(period=self.rsi_period).calculate(df).extra.get(
            "rsi_values"
        )
        if rsi_series is None:
            # Fall back: compute inline
            rsi_series = self._compute_rsi(
                df['close'].to_numpy(dtype=np.float64), self.rsi_period
            )
        rsi_val = float(rsi_series[-1])

        bullish_rsi = rsi_val < self.rsi_oversold
        bearish_rsi = rsi_val > self.rsi_overbought

        # ── 2. ADX ──────────────────────────────────────────────
        adx_result = ADXIndicator(period=self.adx_period).calculate(df)
        adx_val = float(adx_result.values.get("adx", 0.0))
        adx_spike = adx_val > self.adx_spike_threshold

        # ── 3. Parabolic SAR ────────────────────────────────────
        sar_values = self._calculate_sar(highs, lows, closes)

        # Detect flips in the lookback window: last self.sar_flip_bars bars
        lookback = min(self.sar_flip_bars + 1, len(sar_values))
        sar_flip_direction = "NONE"
        bullish_sar_flip = False
        bearish_sar_flip = False

        for i in range(len(sar_values) - lookback, len(sar_values) - 1):
            sar_prev = sar_values[i]
            sar_cur = sar_values[i + 1]
            close_prev = closes[i]
            close_cur = closes[i + 1]

            # Bullish flip: SAR was above close, now below close
            if sar_prev > close_prev and sar_cur < close_cur:
                bullish_sar_flip = True
                sar_flip_direction = "UP"
            # Bearish flip: SAR was below close, now above close
            elif sar_prev < close_prev and sar_cur > close_cur:
                bearish_sar_flip = True
                sar_flip_direction = "DOWN"

        # ── 4. Trigger logic ────────────────────────────────────
        rsi_trigger = bool(bullish_rsi or bearish_rsi)
        adx_trigger = bool(adx_spike)
        sar_trigger = bool(bullish_sar_flip or bearish_sar_flip)

        trigger_count = int(rsi_trigger) + int(adx_trigger) + int(sar_trigger)

        # Determine signal direction
        bullish_triggered = bullish_rsi and adx_spike and bullish_sar_flip
        bearish_triggered = bearish_rsi and adx_spike and bearish_sar_flip

        if bullish_triggered:
            signal = Signal.BUY
            score = normalize_score(trigger_count / 3.0)
        elif bearish_triggered:
            signal = Signal.SELL
            score = normalize_score(-trigger_count / 3.0)
        elif trigger_count >= 2:
            # Weak signal: 2 of 3 triggers — side depends on net bias
            bullish_count = int(bullish_rsi) + int(bullish_sar_flip)
            bearish_count = int(bearish_rsi) + int(bearish_sar_flip)
            if bullish_count > bearish_count:
                signal = Signal.BUY
                score = normalize_score(trigger_count / 3.0)
            elif bearish_count > bullish_count:
                signal = Signal.SELL
                score = normalize_score(-trigger_count / 3.0)
            else:
                # Tie at 2 triggers
                score = 0.0
                signal = Signal.HOLD
        else:
            score = 0.0
            signal = Signal.HOLD

        return IndicatorResult(
            name="RubeGoldberg",
            score=score,
            signal=signal,
            category=SignalCategory.TREND,
            values={
                "rsi": rsi_val,
                "adx": adx_val,
                "sar_flip_direction": sar_flip_direction,
                "trigger_count": trigger_count,
                "rsi_trigger": rsi_trigger,
                "adx_trigger": adx_trigger,
                "sar_trigger": sar_trigger,
                "rsi_value": rsi_val,
                "adx_value": adx_val,
            },
        )

    # ── Internal helpers ──────────────────────────────────────
    @staticmethod
    def _compute_rsi(closes: np.ndarray, period: int) -> np.ndarray:
        """Compute RSI array inline (Wilder smoothing)."""
        n = len(closes)
        rsi_arr = np.full(n, np.nan)
        if n < period + 1:
            return rsi_arr

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        if avg_loss == 0:
            rsi_arr[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_arr[period] = 100.0 - (100.0 / (1.0 + rs))

        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
            if avg_loss == 0:
                rsi_arr[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_arr[i] = 100.0 - (100.0 / (1.0 + rs))

        return rsi_arr

    def _calculate_sar(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
    ) -> np.ndarray:
        """Standard Parabolic SAR (EP / AF / step / max accel)."""
        n = len(closes)
        if n == 0:
            return np.array([])

        sar = np.empty(n)
        step = self.sar_step
        max_accel = self.sar_max
        af = step

        # Determine initial trend from first few bars
        # Start in the direction of the initial price movement
        trend = 1  # default uptrend
        if n >= 3:
            # If close is declining for first few bars, start in downtrend
            if closes[2] < closes[0]:
                trend = -1

        if trend == 1:
            ep = highs[0]
            # SAR starts at EP but must be below the first close
            sar[0] = min(ep, lows[0])
            # Ensure SAR is below close[0] for uptrend
            if sar[0] >= closes[0]:
                sar[0] = closes[0] * 0.99
        else:
            ep = lows[0]
            sar[0] = max(ep, highs[0])
            if sar[0] <= closes[0]:
                sar[0] = closes[0] * 1.01

        for i in range(1, n):
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if trend == 1:
                # Uptrend: SAR tracks below price
                sar[i] = min(sar[i], sar[i - 1])
                sar[i] = min(sar[i], highs[i - 1])

                if closes[i] < sar[i]:
                    # Trend reversal to downtrend
                    new_sar = ep
                    ep = lows[i]
                    af = step
                    trend = -1
                    sar[i] = new_sar
                else:
                    if highs[i] > ep:
                        ep = highs[i]
                        af = min(af + step, max_accel)
            else:
                # Downtrend: SAR tracks above price
                sar[i] = max(sar[i], sar[i - 1])
                sar[i] = max(sar[i], lows[i - 1])

                if closes[i] > sar[i]:
                    # Trend reversal to uptrend
                    new_sar = ep
                    ep = highs[i]
                    af = step
                    trend = 1
                    sar[i] = new_sar
                else:
                    if lows[i] < ep:
                        ep = lows[i]
                        af = min(af + step, max_accel)

        return sar


# ── Parabolic SAR ────────────────────────────────────────────────
@dataclass
class ParabolicSAR(BaseIndicator):
    step: float = 0.02
    max_af: float = 0.2

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        df = self._normalize_columns(df)
        if len(df) < 5:
            return IndicatorResult(
                name="Parabolic SAR", signal=Signal.HOLD, score=0.0,
                category=SignalCategory.TREND,
                values={"sar": 0.0, "price": 0.0, "trend": "NONE"},
            )
        highs = df['high'].to_numpy(dtype=np.float64)
        lows = df['low'].to_numpy(dtype=np.float64)
        closes = df['close'].to_numpy(dtype=np.float64)
        sar_arr = self._calculate_sar(highs, lows, closes)

        price = closes[-1]
        sar_val = sar_arr[-1]
        # Determine trend: if price > SAR → uptrend (BUY)
        if price > sar_val:
            signal = Signal.BUY
            score = normalize_score(min((price - sar_val) / price, 1.0))
        elif price < sar_val:
            signal = Signal.SELL
            score = normalize_score(max(-(sar_val - price) / price, -1.0))
        else:
            signal = Signal.HOLD
            score = 0.0

        return IndicatorResult(
            name="Parabolic SAR", score=score, signal=signal,
            category=SignalCategory.TREND,
            values={"sar": sar_val, "price": price,
                    "trend": "UP" if price > sar_val else "DOWN"},
        )

    def _calculate_sar(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
    ) -> np.ndarray:
        """Standard Parabolic SAR (EP / AF / step / max accel)."""
        n = len(closes)
        if n == 0:
            return np.array([])

        sar = np.empty(n)
        step = self.step
        max_accel = self.max_af
        af = step

        # Determine initial trend from first few bars
        trend = 1  # default uptrend
        if n >= 3 and closes[2] < closes[0]:
            trend = -1

        if trend == 1:
            ep = highs[0]
            sar[0] = min(ep, lows[0])
            if sar[0] >= closes[0]:
                sar[0] = closes[0] * 0.99
        else:
            ep = lows[0]
            sar[0] = max(ep, highs[0])
            if sar[0] <= closes[0]:
                sar[0] = closes[0] * 1.01

        for i in range(1, n):
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if trend == 1:
                sar[i] = min(sar[i], sar[i - 1])
                sar[i] = min(sar[i], highs[i - 1])

                if closes[i] < sar[i]:
                    new_sar = ep
                    ep = lows[i]
                    af = step
                    trend = -1
                    sar[i] = new_sar
                else:
                    if highs[i] > ep:
                        ep = highs[i]
                        af = min(af + step, max_accel)
            else:
                sar[i] = max(sar[i], sar[i - 1])
                sar[i] = max(sar[i], lows[i - 1])

                if closes[i] > sar[i]:
                    new_sar = ep
                    ep = highs[i]
                    af = step
                    trend = 1
                    sar[i] = new_sar
                else:
                    if lows[i] < ep:
                        ep = lows[i]
                        af = min(af + step, max_accel)

        return sar


