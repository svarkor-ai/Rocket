"""Notification helpers for Telegram Bot."""
from __future__ import annotations

from datetime import datetime, timezone

from telegram import Bot

from rocket.scan_engine.models import SignalEvent
from rocket.technical.models import Signal, SignalCategory


async def send_signal_notification(bot: Bot, chat_id: int, event: SignalEvent) -> None:
    """Push a signal-change alert to a Telegram chat."""
    emoji = {"BUY": "📈", "SELL": "📉", "HOLD": "➡️"}
    e = emoji.get(event.new_signal.value, "📊")
    prev = event.prev_signal.value
    new = event.new_signal.value
    msg = (
        f"{e} *{event.ticker}*: {new} ({event.score:.2f})\n"
        f"{prev} → {new} (score={event.score:.2f})\n"
        f"_{event.reason}_\n"
        f"🕒 {event.timestamp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")


async def send_subscribed_signal(
    bot: Bot,
    chat_id: int,
    ticker: str,
    signal: Signal,
    category: SignalCategory,
    score: float,
) -> None:
    """Initial-scan notification for a newly subscribed ticker."""
    emoji = {"BUY": "📈", "SELL": "📉", "HOLD": "➡️"}
    e = emoji.get(signal.value, "📊")
    msg = (
        f"{e} *{ticker}*: {signal.value} (score={score:.2f})\n"
        f"Category: {category.value}\n"
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
    lines = ["📋 *Your Subscriptions:*"]
    for t in tickers:
        st = states.get(t)
        if st is not None:
            lines.append(f"  {t}: {st.signal.value} (score={st.score:.2f})")
        else:
            lines.append(f"  {t}: no signal yet")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")
