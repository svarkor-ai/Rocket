"""Notification helpers for Telegram Bot."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import Bot

from rocket.scan_engine.models import SignalEvent
from rocket.technical.models import Signal, SignalCategory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CooldownManager
# ---------------------------------------------------------------------------

class CooldownManager:
    """Track last notification timestamps per ticker for cooldown enforcement.

    Single-threaded, in-memory dict keyed by ticker.  Configurable cooldown
    period (default 30 minutes).
    """

    def __init__(self, cooldown_seconds: float = 1800) -> None:
        """Initialise with the cooldown period in seconds.

        Args:
            cooldown_seconds: Minimum seconds between two notifications for
                the same ticker.
        """
        self._cooldown: timedelta = timedelta(seconds=cooldown_seconds)
        self._last: dict[str, datetime] = {}

    def is_cooldown(self, ticker: str, now: datetime | None = None) -> bool:
        """Return True if *ticker* is still in cooldown.

        Args:
            ticker: The ticker symbol to check.
            now: Optional timestamp to use as "now" (useful for testing).

        Returns:
            True if the ticker was notified within the cooldown window.
        """
        now = now or datetime.now(timezone.utc)
        last = self._last.get(ticker)
        if last is None:
            return False
        return (now - last) < self._cooldown

    def record(self, ticker: str, ts: datetime | None = None) -> None:
        """Record that *ticker* was notified at *ts*."""
        self._last[ticker] = ts or datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _score_emoji(s: float) -> str:
    """Return a strength emoji based on score in [-1, +1]."""
    if s >= 0.60:
        return "🟣"   # Very Bullish
    elif s >= 0.20:
        return "🟢"   # Bullish
    elif s <= -0.60:
        return "🔴"   # Very Bearish
    elif s <= -0.20:
        return "🟠"   # Bearish
    else:
        return "⚪"   # Hold


# ---------------------------------------------------------------------------
# Signal-state deduplication
# ---------------------------------------------------------------------------

@dataclass
class _SignalState:
    """Internal tracker for the last signal sent per ticker."""
    signal: str          # Signal value, e.g. "BUY"
    score: float         # The score at time of last send


class SignalDedupTracker:
    """Track the last signal sent per ticker for duplicate suppression.

    If a new signal has the same direction (BUY→BUY, HOLD→HOLD, SELL→SELL)
    AND the score is within 0.05 of the last score, skip the notification.
    """

    def __init__(self, max_entries: int = 500) -> None:
        """Initialise.

        Args:
            max_entries: Soft cap on tracked tickers to prevent unbounded
                memory growth.  Oldest entries are not evicted; this is a
                soft guard.
        """
        self._last: dict[str, _SignalState] = {}
        self._max_entries = max_entries

    def should_skip(self, ticker: str, signal: Signal, score: float) -> bool:
        """Return True if this signal is a near-duplicate of the last one.

        Args:
            ticker: The ticker symbol.
            signal: The new signal direction.
            score: The new score.

        Returns:
            True if the signal and score are effectively unchanged.
        """
        prev = self._last.get(ticker)
        if prev is None:
            return False
        # Same direction and score within 0.05
        return (prev.signal == signal.value and
                abs(prev.score - score) <= 0.05)

    def record(self, ticker: str, signal: Signal, score: float) -> None:
        """Record that this signal was sent for *ticker*."""
        self._last[ticker] = _SignalState(
            signal=signal.value,
            score=score,
        )


# ---------------------------------------------------------------------------
# Module-level managers (singletons)
# ---------------------------------------------------------------------------

# These are intentionally module-level so that callers don't need to thread
# them through — the bot itself is single-threaded.
_cooldown = CooldownManager()
_dedup = SignalDedupTracker()


# ---------------------------------------------------------------------------
# Public notification helpers
# ---------------------------------------------------------------------------

async def send_signal_notification(
    bot: Bot,
    chat_id: int,
    event: SignalEvent,
    *,
    min_confidence: float = 0.4,
    min_score_change: float = 0.15,
    summary_mode: bool = False,
) -> None:
    """Push a signal-change alert to a Telegram chat.

    Applies cooldown, confidence gating, score-change threshold, and
    signal-state deduplication before sending.

    Args:
        bot: Telegram Bot instance.
        chat_id: Target chat ID.
        event: The signal event to report.
        min_confidence: Skip notifications when event confidence < this
            value.  If the event lacks a ``confidence`` attribute, gating
            is skipped (graceful degradation).  Default 0.4.
        min_score_change: Skip when ``abs(score - prev_score)`` is below
            this.  If ``event.prev_score`` is absent, gating is skipped.
            Default 0.15.
        summary_mode: If True, caller is expected to use
            ``send_notification_batch`` instead — this parameter is
            ignored here and exists only for API consistency with the
            batch helper.
    """
    # --- confidence gating ------------------------------------------------
    event_confidence = getattr(event, "confidence", None)
    if event_confidence is not None and event_confidence < min_confidence:
        logger.info(
            "Skipped %s: low confidence (%.3f < %.2f)",
            event.ticker, event_confidence, min_confidence,
        )
        return

    # --- score-change threshold -------------------------------------------
    prev_score = getattr(event, "prev_score", None)
    if prev_score is not None and abs(event.score - prev_score) < min_score_change:
        logger.info(
            "Skipped %s: small score change (%.3f → %.3f, delta=%.3f)",
            event.ticker, prev_score, event.score,
            abs(event.score - prev_score),
        )
        return

    # --- cooldown ---------------------------------------------------------
    if _cooldown.is_cooldown(event.ticker, event.timestamp):
        last_time = _cooldown._last[event.ticker]
        logger.info(
            "Skipped %s: cooldown (last %s)",
            event.ticker, last_time,
        )
        return

    # --- signal-state deduplication ---------------------------------------
    if _dedup.should_skip(event.ticker, event.new_signal, event.score):
        logger.info(
            "Skipped %s: duplicate signal (same direction, score within tolerance)",
            event.ticker,
        )
        return

    # --- build & send message ---------------------------------------------
    s = event.score
    emoji = _score_emoji(s)
    prev = event.prev_signal.value
    new = event.new_signal.value
    msg = (
        f"{emoji} *{event.ticker}*: {new} ({event.score:.2f})\n"
        f"{prev} → {new} (score={event.score:.2f})\n"
        f"_{event.reason}_\n"
        f"🕒 {event.timestamp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    # --- record -----------------------------------------------------------
    _cooldown.record(event.ticker, event.timestamp)
    _dedup.record(event.ticker, event.new_signal, event.score)


async def send_subscribed_signal(
    bot: Bot,
    chat_id: int,
    ticker: str,
    signal: Signal,
    category: SignalCategory,
    score: float,
) -> None:
    """Initial-scan notification for a newly subscribed ticker."""
    e = _score_emoji(score)

    msg = (
        f"{e} *{ticker}* — {signal.value}\n"
        f"Score: {score:.2f}  •  Category: {category.value}\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")


async def send_list(
    bot: Bot,
    chat_id: int,
    tickers: list[str],
    states: dict[str, object],
) -> None:
    """Send a formatted list of subscriptions with current signals."""
    lines = ["📋 *Your Subscriptions:*\\n"]
    for t in tickers:
        st = states.get(t)
        if st is not None:
            s = getattr(st, 'score', getattr(st, 'overall_score', 0.0))
            se = _score_emoji(s)
            strength = getattr(st, 'strength', None)
            str_text = f" ({strength.value})" if strength else ""
            lines.append(f"  {se} {t}: {st.signal.value}{str_text} (score={s:.2f})")
        else:
            lines.append(f"  {t}: no signal yet")
    await bot.send_message(chat_id=chat_id, text="".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Batch / summary notifications
# ---------------------------------------------------------------------------

async def send_notification_batch(
    bot: Bot,
    chat_id: int,
    events: list[SignalEvent],
    *,
    min_confidence: float = 0.4,
    min_score_change: float = 0.15,
    summary_mode: bool = True,
) -> None:
    """Send a single summary message with multiple ticker updates.

    Applies the same filtering (cooldown, confidence, score-change, dedup)
    per-event.  Only events that pass all filters are included in the
    summary message.

    Args:
        bot: Telegram Bot instance.
        chat_id: Target chat ID.
        events: List of signal events to batch.
        min_confidence: Confidence gating threshold (default 0.4).
        min_score_change: Minimum score-change threshold (default 0.15).
        summary_mode: Always True for this function; kept for API
            consistency.
    """
    if not events:
        return

    now = datetime.now(timezone.utc)
    lines = ["📊 *Portfolio Update:*\\n"]
    sent_count = 0

    for event in events:
        # --- confidence gating ---
        event_confidence = getattr(event, "confidence", None)
        if event_confidence is not None and event_confidence < min_confidence:
            logger.info(
                "Skipped %s: low confidence (%.3f < %.2f)",
                event.ticker, event_confidence, min_confidence,
            )
            continue

        # --- score-change threshold ---
        prev_score = getattr(event, "prev_score", None)
        if prev_score is not None and abs(event.score - prev_score) < min_score_change:
            logger.info(
                "Skipped %s: small score change (%.3f → %.3f, delta=%.3f)",
                event.ticker, prev_score, event.score,
                abs(event.score - prev_score),
            )
            continue

        # --- cooldown ---
        if _cooldown.is_cooldown(event.ticker, event.timestamp):
            last_time = _cooldown._last[event.ticker]
            logger.info(
                "Skipped %s: cooldown (last %s)",
                event.ticker, last_time,
            )
            continue

        # --- signal-state deduplication ---
        if _dedup.should_skip(event.ticker, event.new_signal, event.score):
            logger.info(
                "Skipped %s: duplicate signal (same direction, score within tolerance)",
                event.ticker,
            )
            continue

        # --- include in summary ---
        emoji = _score_emoji(event.score)
        lines.append(f"  {emoji} {event.ticker}: {event.new_signal.value} ({event.score:.2f})")
        _cooldown.record(event.ticker, event.timestamp)
        _dedup.record(event.ticker, event.new_signal, event.score)
        sent_count += 1

    if sent_count == 0:
        return

    await bot.send_message(chat_id=chat_id, text="".join(lines), parse_mode="Markdown")
