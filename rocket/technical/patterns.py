"""Pattern detection engine — ZigZag-based pattern recognition.

Detects: Double Top/Bottom, Head & Shoulders, Wedges, Auto Fractals, Cup & Handle.

All patterns inherit BaseIndicator and return IndicatorResult.
Uses ZigZag pivot detection for robust pattern identification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .base import BaseIndicator
from .models import IndicatorResult, Signal, SignalCategory


# ─────────────────────────────────────────────
# ZigZag pivot detector
# ─────────────────────────────────────────────

@dataclass
class Pivot:
    """A single ZigZag pivot point."""
    index: int
    price: float
    is_high: bool  # True = high pivot, False = low pivot


class ZigZagDetector:
    """Detects pivots in OHLC data using ZigZag algorithm.

    Algorithm:
      1. Find local maxima/minima within a rolling window
      2. Filter by minimum price deviation (percent)
      3. Filter by minimum bar count between pivots
      4. Alternate high/low pivots only

    Usage:
        zz = ZigZagDetector(price_threshold=0.05, min_bar_count=3)
        pivots = zz.detect(df)  # returns List[Pivot]
    """

    def __init__(
        self,
        price_threshold: float = 0.05,
        min_bar_count: int = 3,
        window: int = 5,
    ):
        self.price_threshold = price_threshold
        self.min_bar_count = min_bar_count
        self.window = window

    def detect(self, df: pd.DataFrame) -> List[Pivot]:
        """Detect pivots from DataFrame with 'High' and 'Low' columns.

        Returns:
            List[Pivot] sorted by index (oldest first).
        """
        highs = np.asarray(df['High'].values, dtype=np.float64)
        lows = np.asarray(df['Low'].values, dtype=np.float64)

        # Step 1: Find local maxima/minima
        local_extrema: List[Tuple[int, float, bool]] = []

        for i in range(self.window, len(df) - self.window):
            high_window = highs[i - self.window:i + self.window + 1]
            if highs[i] == np.max(high_window) and highs[i] > np.mean(high_window):
                local_extrema.append((i, float(highs[i]), True))

            low_window = lows[i - self.window:i + self.window + 1]
            if lows[i] == np.min(low_window) and lows[i] < np.mean(low_window):
                local_extrema.append((i, float(lows[i]), False))

        if len(local_extrema) < 2:
            return []

        # Step 2 & 3: Filter by price deviation and min bar count
        pivots: List[Pivot] = []
        last_pivot: Optional[Pivot] = None

        for idx, price, is_high in local_extrema:
            if last_pivot is None:
                last_pivot = Pivot(index=idx, price=price, is_high=is_high)
                continue

            # Min bar count check
            if idx - last_pivot.index < self.min_bar_count:
                # Update last pivot if this one is more significant
                if (is_high and price > last_pivot.price) or \
                   (not is_high and price < last_pivot.price):
                    last_pivot = Pivot(index=idx, price=price, is_high=is_high)
                continue

            # Price deviation check
            deviation = abs(price - last_pivot.price) / last_pivot.price
            if deviation < self.price_threshold:
                continue

            # Alternate direction check (zigzag must alternate high/low)
            if is_high == last_pivot.is_high:
                if (is_high and price > last_pivot.price) or \
                   (not is_high and price < last_pivot.price):
                    last_pivot = Pivot(index=idx, price=price, is_high=is_high)
                continue

            pivots.append(last_pivot)
            last_pivot = Pivot(index=idx, price=price, is_high=is_high)

        # Append last pivot
        if last_pivot is not None:
            pivots.append(last_pivot)

        return pivots


# ─────────────────────────────────────────────
# Base pattern detector
# ─────────────────────────────────────────────

class PatternDetector(BaseIndicator):
    """Base class for pattern detection. Handles ZigZag preprocessing."""

    category_name = "trend"

    def __init__(
        self,
        name: str,
        price_threshold: float = 0.05,
        min_bar_count: int = 3,
        min_data_length: int = 20,
    ):
        self.name = name
        self.price_threshold = price_threshold
        self.min_bar_count = min_bar_count
        self.min_data_length = min_data_length
        self.zz = ZigZagDetector(
            price_threshold=price_threshold,
            min_bar_count=min_bar_count,
        )

    def _check_data_length(self, df: pd.DataFrame) -> bool:
        return len(df) >= self.min_data_length


# ─────────────────────────────────────────────
# 1. Double Top / Double Bottom
# ─────────────────────────────────────────────

class DoubleTopBottom(PatternDetector):
    """Detects Double Top and Double Bottom patterns.

    Double Top: Two consecutive high pivots within tolerance, with a valley between.
    Double Bottom: Two consecutive low pivots within tolerance, with a peak between.

    Signal:
      - Double Top → SELL (reversal at resistance)
      - Double Bottom → BUY (reversal at support)
    """

    def __init__(
        self,
        price_threshold: float = 0.05,
        min_bar_count: int = 3,
        tolerance: float = 0.02,
        valley_depth: float = 0.03,
    ):
        super().__init__(
            name="DoubleTopBottom",
            price_threshold=price_threshold,
            min_bar_count=min_bar_count,
            min_data_length=10,
        )
        self.tolerance = tolerance
        self.valley_depth = valley_depth

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        if len(df) < self.min_data_length:
            return IndicatorResult(
                name="DoubleTopBottom", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": 0},
            )

        pivots = self.zz.detect(df)

        if len(pivots) < 3:
            return IndicatorResult(
                name="DoubleTopBottom", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        # Check for Double Bottom: two consecutive low pivots
        for i in range(len(pivots) - 2):
            if pivots[i].is_high and not pivots[i + 1].is_high and pivots[i + 2].is_high:
                # H-L-H: valley between highs → Double Bottom
                valley_price = pivots[i + 1].price
                peak1 = pivots[i].price
                peak2 = pivots[i + 2].price
                avg_peak = (peak1 + peak2) / 2.0

                # Check tolerance between peaks
                if abs(peak1 - peak2) / avg_peak > self.tolerance:
                    continue

                # Check valley depth
                if (avg_peak - valley_price) / avg_peak < self.valley_depth:
                    continue

                # Check if current price is near the neckline (valley)
                close_price = float(df['Close'].iloc[-1])
                if valley_price <= close_price <= avg_peak * 1.01:
                    return IndicatorResult(
                        name="DoubleTopBottom", signal=Signal.BUY,
                        score=0.7, category=SignalCategory.TREND,
                        values={
                            "pattern": "double_bottom",
                            "peak1": peak1,
                            "peak2": peak2,
                            "valley": valley_price,
                            "neckline": avg_peak,
                            "pivots": len(pivots),
                        },
                    )

        # Check for Double Top: two consecutive high pivots
        for i in range(len(pivots) - 2):
            if not pivots[i].is_high and pivots[i + 1].is_high and not pivots[i + 2].is_high:
                # L-H-L: peak between lows → Double Top
                peak_price = pivots[i + 1].price
                valley1 = pivots[i].price
                valley2 = pivots[i + 2].price
                avg_valley = (valley1 + valley2) / 2.0

                if abs(valley1 - valley2) / avg_valley > self.tolerance:
                    continue

                if (peak_price - avg_valley) / peak_price < self.valley_depth:
                    continue

                close_price = float(df['Close'].iloc[-1])
                if avg_valley * 0.99 <= close_price <= peak_price:
                    return IndicatorResult(
                        name="DoubleTopBottom", signal=Signal.SELL,
                        score=0.7, category=SignalCategory.TREND,
                        values={
                            "pattern": "double_top",
                            "peak": peak_price,
                            "valley1": valley1,
                            "valley2": valley2,
                            "neckline": avg_valley,
                            "pivots": len(pivots),
                        },
                    )

        return IndicatorResult(
            name="DoubleTopBottom", signal=Signal.HOLD,
            score=0.0, category=SignalCategory.TREND,
            values={"pivots": len(pivots)},
        )


# ─────────────────────────────────────────────
# 2. Head & Shoulders / Inverse H&S
# ─────────────────────────────────────────────

class HeadShoulders(PatternDetector):
    """Detects Head & Shoulders and Inverse Head & Shoulders patterns.

    H&S: Three pivots — left shoulder, head (lower), right shoulder (similar to left).
         Neckline breakout (below valley) = SELL signal.
    Inverse H&S: Three pivots — L-S, H (higher), R-S.
                 Neckline breakout (above peak) = BUY signal.
    """

    def __init__(
        self,
        price_threshold: float = 0.06,
        min_bar_count: int = 5,
        tolerance: float = 0.03,
        min_neckline_breakout: float = 0.01,
    ):
        super().__init__(
            name="HeadShoulders",
            price_threshold=price_threshold,
            min_bar_count=min_bar_count,
            min_data_length=20,
        )
        self.tolerance = tolerance
        self.min_neckline_breakout = min_neckline_breakout

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        if len(df) < self.min_data_length:
            return IndicatorResult(
                name="HeadShoulders", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": 0},
            )

        pivots = self.zz.detect(df)

        if len(pivots) < 4:
            return IndicatorResult(
                name="HeadShoulders", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        # Check for regular H&S: H-L-H-L pattern with middle H being highest
        # Looking for: High(L-S) → Low(valley1) → High(Head) → Low(valley2) → High(R-S)
        for i in range(len(pivots) - 4):
            if not (pivots[i].is_high and not pivots[i + 1].is_high and
                    pivots[i + 2].is_high and not pivots[i + 3].is_high and
                    pivots[i + 4].is_high):
                continue

            left_shoulder = pivots[i].price
            valley1 = pivots[i + 1].price
            head = pivots[i + 2].price
            valley2 = pivots[i + 3].price
            right_shoulder = pivots[i + 4].price

            # Head must be highest
            if head <= left_shoulder or head <= right_shoulder:
                continue

            # Left and right shoulders should be similar
            avg_ls = (left_shoulder + right_shoulder) / 2.0
            if abs(left_shoulder - right_shoulder) / avg_ls > self.tolerance:
                continue

            # Neckline: average of valley1 and valley2
            neckline = (valley1 + valley2) / 2.0

            # Check breakout: close below neckline
            close_price = float(df['Close'].iloc[-1])
            if (neckline - close_price) / neckline >= self.min_neckline_breakout:
                return IndicatorResult(
                    name="HeadShoulders", signal=Signal.SELL,
                    score=0.8, category=SignalCategory.TREND,
                    values={
                        "pattern": "head_shoulders",
                        "left_shoulder": left_shoulder,
                        "head": head,
                        "right_shoulder": right_shoulder,
                        "neckline": neckline,
                        "pivots": len(pivots),
                    },
                )

        # Check for Inverse H&S: L-H-L-H-L pattern with middle L being lowest
        for i in range(len(pivots) - 4):
            if not (not pivots[i].is_high and pivots[i + 1].is_high and
                    not pivots[i + 2].is_high and pivots[i + 3].is_high and
                    not pivots[i + 4].is_high):
                continue

            left_shoulder = pivots[i].price
            peak1 = pivots[i + 1].price
            head = pivots[i + 2].price
            peak2 = pivots[i + 3].price
            right_shoulder = pivots[i + 4].price

            # Head must be lowest
            if head >= left_shoulder or head >= right_shoulder:
                continue

            # Left and right shoulders should be similar
            avg_ls = (left_shoulder + right_shoulder) / 2.0
            if abs(left_shoulder - right_shoulder) / avg_ls > self.tolerance:
                continue

            neckline = (peak1 + peak2) / 2.0

            close_price = float(df['Close'].iloc[-1])
            if (close_price - neckline) / neckline >= self.min_neckline_breakout:
                return IndicatorResult(
                    name="HeadShoulders", signal=Signal.BUY,
                    score=0.8, category=SignalCategory.TREND,
                    values={
                        "pattern": "inverse_head_shoulders",
                        "left_shoulder": left_shoulder,
                        "head": head,
                        "right_shoulder": right_shoulder,
                        "neckline": neckline,
                        "pivots": len(pivots),
                    },
                )

        return IndicatorResult(
            name="HeadShoulders", signal=Signal.HOLD,
            score=0.0, category=SignalCategory.TREND,
            values={"pivots": len(pivots)},
        )


# ─────────────────────────────────────────────
# 3. Wedge Patterns
# ─────────────────────────────────────────────

class WedgePattern(PatternDetector):
    """Detects Rising and Falling Wedge patterns.

    Rising Wedge: Two converging trendlines on highs and lows (both sloping up).
                  Breakout below lower trendline = SELL.
    Falling Wedge: Two converging trendlines (both sloping down).
                   Breakout above upper trendline = BUY.

    Uses linear regression on successive pivot points for trendlines.
    """

    def __init__(
        self,
        price_threshold: float = 0.05,
        min_bar_count: int = 4,
        min_pivots: int = 4,
    ):
        super().__init__(
            name="WedgePattern",
            price_threshold=price_threshold,
            min_bar_count=min_bar_count,
            min_data_length=20,
        )
        self.min_pivots = min_pivots

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        if len(df) < self.min_data_length:
            return IndicatorResult(
                name="WedgePattern", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": 0},
            )

        pivots = self.zz.detect(df)

        if len(pivots) < self.min_pivots:
            return IndicatorResult(
                name="WedgePattern", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        # Group pivots by type
        high_pivots = [(p.index, p.price) for p in pivots if p.is_high]
        low_pivots = [(p.index, p.price) for p in pivots if not p.is_high]

        if len(high_pivots) < 2 or len(low_pivots) < 2:
            return IndicatorResult(
                name="WedgePattern", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        # Use last 2 high pivots and last 2 low pivots for trendline slope
        last_highs = high_pivots[-3:] if len(high_pivots) >= 3 else high_pivots[-2:]
        last_lows = low_pivots[-3:] if len(low_pivots) >= 3 else low_pivots[-2:]

        # Fit trendlines
        if len(last_highs) >= 2:
            x_h = np.array([p[0] for p in last_highs], dtype=np.float64)
            y_h = np.array([p[1] for p in last_highs], dtype=np.float64)
            high_slope, _ = np.polyfit(x_h, y_h, 1)
        else:
            return IndicatorResult(
                name="WedgePattern", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        if len(last_lows) >= 2:
            x_l = np.array([p[0] for p in last_lows], dtype=np.float64)
            y_l = np.array([p[1] for p in last_lows], dtype=np.float64)
            low_slope, _ = np.polyfit(x_l, y_l, 1)
        else:
            return IndicatorResult(
                name="WedgePattern", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        close_price = float(df['Close'].iloc[-1])
        last_idx = pivots[-1].index

        # Rising Wedge: both slopes positive, converging
        if high_slope > 0 and low_slope > 0:
            # Check convergence: high_slope > low_slope (highs rise faster than lows)
            if high_slope > low_slope:
                # Check if price broke below lower trendline
                predicted_low = np.polyval([low_slope, 0.0], last_idx)
                if close_price < predicted_low * 0.99:
                    return IndicatorResult(
                        name="WedgePattern", signal=Signal.SELL,
                        score=0.75, category=SignalCategory.TREND,
                        values={
                            "pattern": "rising_wedge",
                            "high_slope": float(high_slope),
                            "low_slope": float(low_slope),
                            "pivots": len(pivots),
                        },
                    )

        # Falling Wedge: both slopes negative, converging
        if high_slope < 0 and low_slope < 0:
            # Check convergence: high_slope > low_slope (highs drop faster than lows)
            if high_slope > low_slope:
                # Check if price broke above upper trendline
                predicted_high = np.polyval([high_slope, 0.0], last_idx)
                if close_price > predicted_high * 1.01:
                    return IndicatorResult(
                        name="WedgePattern", signal=Signal.BUY,
                        score=0.75, category=SignalCategory.TREND,
                        values={
                            "pattern": "falling_wedge",
                            "high_slope": float(high_slope),
                            "low_slope": float(low_slope),
                            "pivots": len(pivots),
                        },
                    )

        return IndicatorResult(
            name="WedgePattern", signal=Signal.HOLD,
            score=0.0, category=SignalCategory.TREND,
            values={"pivots": len(pivots)},
        )


# ─────────────────────────────────────────────
# 4. Auto Fractals
# ─────────────────────────────────────────────

class AutoFractal(PatternDetector):
    """Detects Bill Williams Auto Fractals.

    Bullish fractal: Low is the lowest of 5 bars (2 before, 2 after).
    Bearish fractal: High is the highest of 5 bars (2 before, 2 after).

    Signal:
      - Most recent bullish fractal near current price → BUY (support)
      - Most recent bearish fractal near current price → SELL (resistance)
    """

    def __init__(self):
        super().__init__(
            name="AutoFractal",
            min_data_length=5,
        )

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        if len(df) < 5:
            return IndicatorResult(
                name="AutoFractal", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"fractals": 0},
            )

        highs = df['High'].values
        lows = df['Low'].values
        fractals: List[str] = []

        for i in range(2, len(df) - 2):
            # Bullish fractal: middle bar has lowest low
            if lows[i] == np.min(lows[i - 2:i + 3]) and \
               lows[i] < np.mean(lows[i - 2:i + 3]):
                fractals.append("bullish")

            # Bearish fractal: middle bar has highest high
            if highs[i] == np.max(highs[i - 2:i + 3]) and \
               highs[i] > np.mean(highs[i - 2:i + 3]):
                fractals.append("bearish")

        if not fractals:
            return IndicatorResult(
                name="AutoFractal", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"fractals": 0},
            )

        # Check if current price is near the most recent fractal level
        close_price = float(df['Close'].iloc[-1])
        most_recent = fractals[-1]

        # Find the fractal price level
        for i in range(len(df) - 1, 1, -1):
            if highs[i] == np.max(highs[i - 2:i + 3]) and \
               highs[i] > np.mean(highs[i - 2:i + 3]):
                if most_recent == "bearish":
                    # Check if close is near bearish fractal (resistance)
                    fractal_price = float(highs[i])
                    if abs(close_price - fractal_price) / fractal_price < 0.02:
                        return IndicatorResult(
                            name="AutoFractal", signal=Signal.SELL,
                            score=0.6, category=SignalCategory.TREND,
                            values={
                                "pattern": "bearish_fractal",
                                "fractal_price": fractal_price,
                                "fractals": len(fractals),
                            },
                        )
                    break

            if lows[i] == np.min(lows[i - 2:i + 3]) and \
               lows[i] < np.mean(lows[i - 2:i + 3]):
                if most_recent == "bullish":
                    fractal_price = float(lows[i])
                    if abs(close_price - fractal_price) / fractal_price < 0.02:
                        return IndicatorResult(
                            name="AutoFractal", signal=Signal.BUY,
                            score=0.6, category=SignalCategory.TREND,
                            values={
                                "pattern": "bullish_fractal",
                                "fractal_price": fractal_price,
                                "fractals": len(fractals),
                            },
                        )
                    break

        return IndicatorResult(
            name="AutoFractal", signal=Signal.HOLD,
            score=0.0, category=SignalCategory.TREND,
            values={"fractals": len(fractals)},
        )


# ─────────────────────────────────────────────
# 5. Cup & Handle
# ─────────────────────────────────────────────

class CupAndHandle(PatternDetector):
    """Detects Cup & Handle pattern.

    Cup: U-shaped curve (20-65 bars) with a trough.
    Handle: Small consolidation (5-10 bars) after the cup, slight downward drift.
    Breakout: Price above cup's right rim = BUY signal.
    """

    def __init__(
        self,
        price_threshold: float = 0.04,
        min_bar_count: int = 3,
        cup_min_bars: int = 20,
        cup_max_bars: int = 65,
        handle_min_bars: int = 5,
        handle_max_bars: int = 15,
        handle_depth: float = 0.03,
    ):
        super().__init__(
            name="CupAndHandle",
            price_threshold=price_threshold,
            min_bar_count=min_bar_count,
            min_data_length=40,
        )
        self.cup_min_bars = cup_min_bars
        self.cup_max_bars = cup_max_bars
        self.handle_min_bars = handle_min_bars
        self.handle_max_bars = handle_max_bars
        self.handle_depth = handle_depth
        self.tolerance = 0.02  # Cup rim tolerance

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        if len(df) < self.min_data_length:
            return IndicatorResult(
                name="CupAndHandle", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": 0},
            )

        pivots = self.zz.detect(df)

        if len(pivots) < 4:
            return IndicatorResult(
                name="CupAndHandle", signal=Signal.HOLD,
                score=0.0, category=SignalCategory.TREND,
                values={"pivots": len(pivots)},
            )

        # Look for: High → Low → High (cup) + small consolidation (handle) → breakout
        # pivots: H0(low) → L0(deep) → H1(similar to H0) → H2(slightly lower, handle)
        for i in range(len(pivots) - 3):
            if not (pivots[i].is_high and not pivots[i + 1].is_high and
                    pivots[i + 2].is_high):
                continue

            cup_left = pivots[i]
            cup_bottom = pivots[i + 1]
            cup_right = pivots[i + 2]

            # Cup size check (bars between left and right)
            cup_bars = cup_right.index - cup_left.index
            if cup_bars < self.cup_min_bars or cup_bars > self.cup_max_bars:
                continue

            # Cup depth (from left rim to bottom)
            cup_depth = (cup_left.price - cup_bottom.price) / cup_left.price
            if cup_depth < 0.05:  # Minimum 5% cup depth
                continue

            # Left and right rims should be similar (±tolerance)
            avg_rim = (cup_left.price + cup_right.price) / 2.0
            if abs(cup_left.price - cup_right.price) / avg_rim > self.tolerance:
                continue

            # Handle: last pivot should be slightly lower (slight downward drift)
            if i + 3 < len(pivots) and pivots[i + 3].is_high:
                handle = pivots[i + 3]
                handle_bars = handle.index - cup_right.index
                if self.handle_min_bars <= handle_bars <= self.handle_max_bars:
                    handle_drift = (cup_right.price - handle.price) / cup_right.price
                    if 0 <= handle_drift <= self.handle_depth:
                        # Check breakout
                        close_price = float(df['Close'].iloc[-1])
                        if close_price >= cup_right.price * 0.99:
                            return IndicatorResult(
                                name="CupAndHandle", signal=Signal.BUY,
                                score=0.85, category=SignalCategory.TREND,
                                values={
                                    "pattern": "cup_and_handle",
                                    "cup_left": cup_left.price,
                                    "cup_bottom": cup_bottom.price,
                                    "cup_right": cup_right.price,
                                    "handle": handle.price,
                                    "cup_bars": cup_bars,
                                    "handle_bars": handle_bars,
                                    "pivots": len(pivots),
                                },
                            )

        return IndicatorResult(
            name="CupAndHandle", signal=Signal.HOLD,
            score=0.0, category=SignalCategory.TREND,
            values={"pivots": len(pivots)},
        )


# ─────────────────────────────────────────────
# Combined Pattern Detector
# ─────────────────────────────────────────────

class PatternDetectorCombined(BaseIndicator):
    """Runs all pattern detectors and returns combined result.

    Uses the strongest pattern signal. If multiple patterns match,
    returns the one with the highest score.
    """

    def __init__(
        self,
        price_threshold: float = 0.05,
        min_bar_count: int = 3,
    ):
        self.name = "PatternDetector"
        self.detectors = [
            DoubleTopBottom(
                price_threshold=price_threshold,
                min_bar_count=min_bar_count,
            ),
            HeadShoulders(
                price_threshold=price_threshold,
                min_bar_count=min_bar_count,
            ),
            WedgePattern(
                price_threshold=price_threshold,
                min_bar_count=min_bar_count,
            ),
            AutoFractal(),
            CupAndHandle(
                price_threshold=price_threshold,
                min_bar_count=min_bar_count,
            ),
        ]

    def calculate(self, df: pd.DataFrame) -> IndicatorResult:
        best_signal = Signal.HOLD
        best_score = 0.0
        best_values: dict = {"active_patterns": 0, "all_signals": []}

        for detector in self.detectors:
            result = detector.calculate(df)
            best_values["all_signals"].append(
                f"{result.name}:{result.signal.value}({result.score:.2f})"
            )
            best_values["active_patterns"] += 1

            if abs(result.score) > abs(best_score):
                best_score = result.score
                best_signal = result.signal
                best_values.update(result.values)

        # Normalize score to [-1, 1]
        if best_signal == Signal.BUY:
            best_score = abs(best_score)
        elif best_signal == Signal.SELL:
            best_score = -abs(best_score)
        else:
            best_score = 0.0

        return IndicatorResult(
            name=self.name,
            signal=best_signal,
            score=best_score,
            category=SignalCategory.TREND,
            values=best_values,
        )
