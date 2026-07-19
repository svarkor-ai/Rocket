"""Core SignalEngine — scan tickers, detect signal changes, emit events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..technical.models import Signal, SignalCategory
from ..technical.signal_combiner import SignalSummary
from ..data.fetcher import fetch_ohlcv
from ..data.models import TickerInfo, Region
from ..data.universe import get_universe
from ..scoring.rocket_score import compute_rocket_score
from .models import SignalEvent, SignalState
from .storage import SignalStorage

logger = logging.getLogger(__name__)

# Thresholds for signal classification
BUY_THRESHOLD = 10     # minimum buy_count to qualify as BUY
SELL_THRESHOLD = 10    # minimum sell_count to qualify as SELL


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


def _make_reason(summary: SignalSummary, new_sig: Signal, prev_sig: Signal) -> str:
    """Human-readable explanation for the signal event."""
    score = summary.overall_score
    if new_sig == prev_sig:
        return f"{new_sig.value} (score={score:.1f}, buy={summary.buy_count}, sell={summary.sell_count})"
    return (
        f"{prev_sig.value} → {new_sig.value} (score={score:.1f}, "
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
        self.min_score = float(config.get("min_score", 0.5))
        self.require_change = bool(config.get("require_change", True))
        self.cooldown_minutes = int(config.get("cooldown_minutes", 5))
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

        # 2. Get TickerInfo — try universe first, fall back to mock
        universe = get_universe(self._region_key)
        ticker_upper = ticker.upper()
        if ticker_upper in universe:
            ticker_info = TickerInfo(
                ticker=ticker,
                name=ticker,
                region=Region(self._region_enum),
                sector="",
                market_cap=0.0,
                avg_volume=0.0,
            )
        else:
            ticker_info = TickerInfo(
                ticker=ticker,
                name=ticker,
                region=Region(self._region_enum),
                sector="",
                market_cap=0.0,
                avg_volume=0.0,
            )

        # 3. Compute rocket score
        current_price = float(df["close"].iloc[-1])
        result = compute_rocket_score(df, ticker_info, current_price=current_price)

        # 4. Derive signal from SignalSummary
        summary = result["signal_summary"]
        new_signal, category = _derive_signal(summary)
        score = float(summary.overall_score)  # [-1, 1] range from weight_scores

        # 5. Check min_score threshold (convert [-1,1] → [0,1])
        normalized_score = (score + 1.0) / 2.0
        if normalized_score < self.min_score:
            return None

        # 6. Load previous state
        prev_state = self.storage.get_signal_state(ticker)
        prev_signal = prev_state.signal if prev_state else Signal.HOLD

        # 7. Check require_change
        if self.require_change and new_signal == prev_signal:
            return None

        # 8. Check cooldown
        if prev_state:
            elapsed = datetime.now(timezone.utc) - prev_state.updated_at
            if elapsed < timedelta(minutes=self.cooldown_minutes):
                logger.debug(
                    f"{ticker}: cooldown not elapsed "
                    f"({elapsed.total_seconds() / 60:.1f}m < {self.cooldown_minutes}m)"
                )
                return None

        # 9. Create event and persist state
        now = datetime.now(timezone.utc)
        reason = _make_reason(summary, new_signal, prev_signal)

        state = SignalState(
            ticker=ticker,
            signal=new_signal,
            score=score,
            category=category,
            updated_at=now,
        )
        self.storage.save_signal_state(state)

        event = SignalEvent(
            ticker=ticker,
            prev_signal=prev_signal,
            new_signal=new_signal,
            score=normalized_score,
            category=category,
            reason=reason,
            timestamp=now,
            timeframe=timeframe,
        )
        logger.info(f"{ticker}: {reason}")
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
            except Exception as e:
                logger.error(f"{t}: scan error: {e}")
        return events
