"""Core SignalEngine — scan tickers, detect signal changes, emit events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..technical.models import Signal, SignalCategory, SignalStrength
from ..technical.signal_combiner import SignalSummary
from ..data.fetcher import fetch_ohlcv
from ..data.models import TickerInfo, Region
from ..data.universe import get_universe
from ..scoring.rocket_score import compute_rocket_score
from .models import SignalEvent, SignalState
from .storage import SignalStorage

logger = logging.getLogger(__name__)

# Thresholds for signal classification
BUY_THRESHOLD = 4      # minimum buy_count to qualify as BUY (5 of 7 indicators agree)
SELL_THRESHOLD = 4     # minimum sell_count to qualify as SELL

# 5-level strength thresholds
# Score ranges: [-1.0, +1.0]
STRENGTH_LEVELS = [
    (SignalStrength.VERY_BEARISH, -1.0, -0.60),
    (SignalStrength.BEARISH,       -0.60, -0.20),
    (SignalStrength.HOLD,           -0.20,  0.20),
    (SignalStrength.BULLISH,        0.20,  0.60),
    (SignalStrength.VERY_BULLISH,   0.60,  1.00),
]

# Hysteresis thresholds per strength transition
# Each level has: IN (enter), OUT (leave back to previous level)
HYSTERESIS = {
    SignalStrength.VERY_BEARISH: {"in": -1.00, "out": -0.50},  # V-Bearish → Bearish
    SignalStrength.BEARISH:      {"in": -0.60, "out": -0.15},  # Bearish → Hold
    SignalStrength.HOLD:         {"in": -0.20, "out": +0.20},  # Hold → Bearish/Bullish
    SignalStrength.BULLISH:      {"in": +0.60, "out": +0.50},  # Bullish → VeryBullish
    SignalStrength.VERY_BULLISH: {"in": +1.00, "out": +0.55},  # V-Bullish → Bullish
}


def _derive_strength(score: float) -> SignalStrength:
    """Map score [-1,1] to SignalStrength (5 levels).

    Score ≤ -0.60 → Very Bearish
    -0.60 < score ≤ -0.20 → Bearish
    -0.20 < score < +0.20 → Hold
    +0.20 ≤ score < +0.60 → Bullish
    Score ≥ +0.60 → Very Bullish
    """
    for strength, lo, hi in STRENGTH_LEVELS:
        if lo <= score <= hi:
            return strength
    # Edge cases — should be covered above
    if score < -1.0:
        return SignalStrength.VERY_BEARISH
    return SignalStrength.VERY_BULLISH


def _derive_signal(summary: SignalSummary) -> tuple[Signal, SignalCategory]:
    """Map SignalSummary counts to a single Signal + category.

    BUY  — buy_count > sell_count AND buy_count >= BUY_THRESHOLD
    SELL — sell_count > buy_count AND sell_count >= SELL_THRESHOLD
    HOLD — otherwise
    """
    if summary.buy_count > summary.sell_count and summary.buy_count >= BUY_THRESHOLD:
        return Signal.BUY, SignalCategory.MOMENTUM
    if summary.sell_count > summary.buy_count and summary.sell_count >= SELL_THRESHOLD:
        return Signal.SELL, SignalCategory.VOLATILITY
    return Signal.HOLD, SignalCategory.TREND


def _apply_strength_hysteresis(
    new_strength: SignalStrength,
    score: float,
    prev_strength: SignalStrength,
) -> SignalStrength:
    """Apply hysteresis to strength transitions.

    Prevents rapid flapping near thresholds.
    """
    h = HYSTERESIS

    # Stay in same level unless crossing out threshold
    if new_strength == prev_strength:
        out_threshold = h[prev_strength]["out"]
        # Check if we've drifted below the OUT threshold
        if prev_strength == SignalStrength.VERY_BEARISH:
            # Already V-Bearish — stay unless score > -0.50
            if score > out_threshold:
                return SignalStrength.BEARISH
        elif prev_strength == SignalStrength.BEARISH:
            # Already Bearish — stay unless score > -0.15
            if score > out_threshold:
                return SignalStrength.HOLD
        elif prev_strength == SignalStrength.HOLD:
            # Already Hold — if score moved into Bearish/Bullish zone, upgrade/downgrade
            if score <= -0.15:
                return SignalStrength.BEARISH
            if score >= +0.15:
                return SignalStrength.BULLISH
        elif prev_strength == SignalStrength.BULLISH:
            # Already Bullish — stay unless score < +0.50
            if score < out_threshold:
                return SignalStrength.HOLD
        elif prev_strength == SignalStrength.VERY_BULLISH:
            # Already V-Bullish — stay unless score < +0.55
            if score < out_threshold:
                return SignalStrength.BULLISH
    else:
        # Transitioning — check if we crossed the IN threshold
        in_threshold = h[new_strength]["in"]
        if new_strength == SignalStrength.VERY_BEARISH:
            if score > -0.55:  # didn't cross into V-Bearish zone
                return SignalStrength.BEARISH
        elif new_strength == SignalStrength.BEARISH:
            if score > -0.25:  # didn't cross into Bearish zone
                return SignalStrength.HOLD
        elif new_strength == SignalStrength.HOLD:
            if score <= -0.15:
                return SignalStrength.BEARISH
            if score >= +0.15:
                return SignalStrength.BULLISH
        elif new_strength == SignalStrength.BULLISH:
            if score < 0.25:  # didn't cross into Bullish zone
                return SignalStrength.HOLD
        elif new_strength == SignalStrength.VERY_BULLISH:
            if score < +0.55:  # didn't cross into V-Bullish zone
                return SignalStrength.BULLISH

    return new_strength


def _make_reason(summary: SignalSummary, new_sig: Signal, prev_sig: Signal) -> str:
    """Human-readable explanation for the signal event."""
    score = summary.overall_score
    if new_sig == prev_sig:
        return f"{new_sig.value} (score={score:.2f}, buy={summary.buy_count}, sell={summary.sell_count})"
    return (
        f"{prev_sig.value} → {new_sig.value} (score={score:.2f}, "
        f"buy={summary.buy_count}, sell={summary.sell_count})"
    )


class SignalEngine:
    """Runs the scanning loop and detects signal changes."""

    def __init__(self, storage: SignalStorage, config: dict) -> None:
        """
        storage: SignalStorage instance
        config: dict with keys:
            min_score (float): 0-1 — threshold to emit signal
            require_change (bool): only emit on signal change
            cooldown_minutes (int): min time between same-ticker events
        """
        self.storage = storage
        self.require_change = bool(config.get("require_change", True))
        self.cooldown_minutes = int(config.get("cooldown_minutes", 5))
        # min_score is configured in [0,1] — convert to [-1,+1]
        self.min_score = 2.0 * float(config.get("min_score", 0.5)) - 1.0
        # Region key lookup (universe keys are lowercase: 'usa', 'sweden'…)
        self._region_key = str(config.get("region", "usa")).lower()
        # Region enum for TickerInfo (enum values: 'us', 'smid', 'eu', 'asia')
        region_map = {
            "usa": "us", "us": "us", "sweden": "eu", "eu": "eu",
            "china": "asia", "india": "asia", "asia": "asia",
            "international": "us",
        }
        self._region_enum = region_map.get(self._region_key, "us")

    # -- single ticker scan ---------------------------------------------------

    def scan_ticker(self, ticker: str, timeframe: str = "daily") -> Optional[SignalEvent]:
        """Fetch OHLCV, score, detect signal change.

        Returns SignalEvent if a new signal should be emitted, else None.
        """
        # 1. Fetch OHLCV
        ohlcv = fetch_ohlcv([ticker])
        df = ohlcv.get(ticker)
        if df is None or df.empty:
            logger.warning(f"{ticker}: no OHLCV data")
            return None

        # 2. Get TickerInfo
        universe = get_universe(self._region_key)
        ticker_upper = ticker.upper()
        if ticker_upper in universe:
            ticker_info = TickerInfo(
                ticker=ticker, name=ticker, region=Region(self._region_enum),
                sector="", market_cap=0.0, avg_volume=0.0,
            )
        else:
            ticker_info = TickerInfo(
                ticker=ticker, name=ticker, region=Region(self._region_enum),
                sector="", market_cap=0.0, avg_volume=0.0,
            )

        # 3. Compute rocket score
        current_price = float(df["close"].iloc[-1])
        result = compute_rocket_score(df, ticker_info, current_price=current_price)

        # 4. Derive signal from SignalSummary
        summary = result["signal_summary"]
        new_signal, category = _derive_signal(summary)
        score = float(summary.overall_score)  # [-1, 1]

        # 4.5. Derive strength (5 levels)
        new_strength = _derive_strength(score)

        # 4.6. Hysteresis on strength — prevents flapping
        prev_state_raw = self.storage.get_signal_state(ticker)
        prev_strength = prev_state_raw.strength if prev_state_raw else SignalStrength.HOLD
        final_strength = _apply_strength_hysteresis(new_strength, score, prev_strength)

        # 5. Apply BUY/SELL hysteresis on score in [-1, +1]
        buy_in = 0.60    # score threshold to enter BUY
        buy_out = 0.35   # score threshold to exit BUY
        sell_in = -0.60  # score threshold to enter SELL
        sell_out = -0.35 # score threshold to exit SELL
        prev_sig_for_hysteresis = prev_state_raw.signal if prev_state_raw else Signal.HOLD

        # Apply BUY/SELL hysteresis (keeps internal Signal logic stable)
        if prev_sig_for_hysteresis == Signal.BUY:
            if score < buy_out:
                new_signal = Signal.HOLD
                category = SignalCategory.TREND
        elif prev_sig_for_hysteresis == Signal.SELL:
            if score > sell_out:
                new_signal = Signal.HOLD
                category = SignalCategory.TREND
        else:
            if new_signal == Signal.BUY and score <= buy_in:
                new_signal = Signal.HOLD
                category = SignalCategory.TREND
            if new_signal == Signal.SELL and score >= sell_in:
                new_signal = Signal.HOLD
                category = SignalCategory.TREND

        # Min score gate — only emit for notable signals
        if new_signal == Signal.BUY and score < self.min_score:
            prev_state = self.storage.get_signal_state(ticker)
            if prev_state is None:
                state = SignalState(
                    ticker=ticker, signal=new_signal, score=score, category=category,
                    updated_at=datetime.now(timezone.utc), strength=final_strength,
                )
                self.storage.save_signal_state(state)
            return None
        if new_signal == Signal.SELL and abs(score) < self.min_score:
            prev_state = self.storage.get_signal_state(ticker)
            if prev_state is None:
                state = SignalState(
                    ticker=ticker, signal=new_signal, score=score, category=category,
                    updated_at=datetime.now(timezone.utc), strength=final_strength,
                )
                self.storage.save_signal_state(state)
            return None

        # 6. Check require_change on signal
        prev_state = self.storage.get_signal_state(ticker)
        prev_signal = prev_state.signal if prev_state else Signal.HOLD
        if prev_state and self.require_change and new_signal == prev_signal:
            return None

        # 7. Check cooldown
        if prev_state:
            elapsed = datetime.now(timezone.utc) - prev_state.updated_at
            if elapsed < timedelta(minutes=self.cooldown_minutes):
                logger.debug(
                    f"{ticker}: cooldown not elapsed "
                    f"({elapsed.total_seconds() / 60:.1f}m < {self.cooldown_minutes}m)"
                )
                return None

        # 8. Create event and persist state
        now = datetime.now(timezone.utc)
        reason = _make_reason(summary, new_signal, prev_signal)

        state = SignalState(
            ticker=ticker, signal=new_signal, score=score, category=category,
            updated_at=now, strength=final_strength,
        )
        self.storage.save_signal_state(state)

        event = SignalEvent(
            ticker=ticker, prev_signal=prev_signal, new_signal=new_signal,
            score=score, category=category, reason=reason,
            timestamp=now, timeframe=timeframe,
            buy_count=summary.buy_count, sell_count=summary.sell_count,
            strength=final_strength,
        )
        logger.info(f"{ticker}: {reason} (strength={final_strength.value})")
        return event

    # -- bulk scan ------------------------------------------------------------

    def scan_region(self, region: str, timeframe: str = "daily") -> list[SignalEvent]:
        """Scan all tickers in a region. Returns list of emitted events."""
        keys = {"usa": "us", "sweden": "eu", "china": "asia", "india": "asia"}.get(region, "us")
        tickers = get_universe(region.lower())
        events: list[SignalEvent] = []
        for t in tickers:
            try:
                ev = self.scan_ticker(t, timeframe=timeframe)
                if ev is not None:
                    events.append(ev)
            except (KeyError, IndexError, ValueError) as e:
                logger.error(f"{t}: scan error (invalid data)")
            except Exception as e:
                logger.error(f"{t}: scan error")
        return events
