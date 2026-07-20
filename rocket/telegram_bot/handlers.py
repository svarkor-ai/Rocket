"""Handler coroutines for Telegram /commands."""
from __future__ import annotations

import concurrent.futures
import os
import logging
from datetime import datetime, timezone

from telegram import Bot, Update
from telegram.ext import ContextTypes

from rocket.scan_engine.engine import SignalEngine
from rocket.scan_engine.storage import SignalStorage
from rocket.telegram_bot.notifications import (
    send_signal_notification,
    send_subscribed_signal,
)

USERS_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.db")
SIGNALS_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "signals.db")

logger = logging.getLogger(__name__)

# Shared caches — initialised on first use
_engine_cache: object | None = None
_storage_cache: object | None = None
_user_store_cache: object | None = None
def _get_user_store() -> "UserStore":
    global _user_store_cache
    if _user_store_cache is None:
        from rocket.users.store import UserStore
        _user_store_cache = UserStore(USERS_DB_PATH)
    return _user_store_cache


def _get_engine() -> SignalEngine:
    global _engine_cache, _storage_cache
    if _engine_cache is None:
        _storage_cache = SignalStorage(SIGNALS_DB_PATH)
        _engine_cache = SignalEngine(
            _storage_cache, config={"min_score": 0.5, "require_change": False}
        )
    return _engine_cache


async def _send_signal_from_history(
    bot: "Bot",
    chat_id: int,
    ticker: str,
    signal: str,
    score: float,
    category: str,
    reason: str | None = None,
) -> None:
    """Send a signal notification built from a scan_history row."""
    emoji = {"BUY": "📈", "SELL": "📉", "HOLD": "➡️"}
    e = emoji.get(signal, "📊")
    lines = [
        f"{e} *{ticker}*: {signal} (score={score:.2f})",
        f"Category: {category}",
    ]
    if reason:
        lines.append(f"_{reason}_")
    lines.append(f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    await bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome user, register chat_id, show commands."""
    chat_id = update.effective_user.id
    username = update.effective_user.username

    # Register user in the user store (auto-creates with free tier)
    store = _get_user_store()
    store.create_user(chat_id, username)

    help_text = (
        "🚀 *Stock Scan Pro Bot*\n\n"
        "📊 *Trading*\n"
        "• /subscribe <ticker> — get signal alerts (max 3 free)\n"
        "• /unsubscribe <ticker> — stop alerts\n"
        "• /signal <ticker> — scan now\n"
        "• /status <ticker> — check signal\n"
        "• /scanall — show top 10 from last scan (admin only)\n"
        "• /history — view last 5 scans (admin only)\n\n"
        "📋 *Portfolio*\n"
        "• /list — show all subscriptions\n\n"
        "👤 *Account*\n"
        "• /plan — view available plans\n"
        "• /userstatus — view your status\n\n"
        "ℹ️ *Help*\n"
        "• /help — this message\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
    logger.info(f"User {chat_id} (/start)")


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe to ticker notifications (cache-based from nightly scan)."""
    chat_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /subscribe <ticker>")
        return
    ticker = args[0].upper()
    store = _get_user_store()

    # Check free-tier limit (add_subscription enforces it and raises ValueError)
    try:
        store.add_subscription(chat_id, ticker)
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return

    # Look up ticker in the latest scan from scan_history
    storage = _get_engine().storage
    row = storage._conn.execute(
        """SELECT signal, score, category FROM scan_history
           WHERE ticker = ? AND timestamp = (
               SELECT MAX(timestamp) FROM scan_history)""",
        (ticker,),
    ).fetchone()

    if row is None:
        # Ticker not in latest scan — try full scan_history for any past signal
        row = storage._conn.execute(
            """SELECT signal, score, category, reason FROM scan_history
               WHERE ticker = ?
               ORDER BY timestamp DESC
               LIMIT 1""",
            (ticker,),
        ).fetchone()

        if row is None:
            # Ticker never scanned — do a live fallback scan
            event = _get_engine().scan_ticker(ticker)
            if event:
                await send_signal_notification(context.bot, chat_id, event)
            else:
                state = storage.get_signal_state(ticker)
                if state:
                    await send_subscribed_signal(
                        context.bot, chat_id, ticker,
                        state.signal, state.category, state.score,
                    )
                else:
                    await update.message.reply_text(
                        f"📋 Subscribed to {ticker}. No active signal right now."
                    )
        else:
            signal, score, category, reason = row
            await _send_signal_from_history(
                context.bot, chat_id, ticker,
                signal, score, category, reason,
            )
    else:
        signal, score, category = row
        await _send_signal_from_history(
            context.bot, chat_id, ticker,
            signal, score, category,
        )

    logger.info(f"User {chat_id} subscribed to {ticker}")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe from ticker notifications."""
    chat_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /unsubscribe <ticker>")
        return
    ticker = args[0].upper()
    store = _get_user_store()
    count_before = store.count_subscriptions(chat_id)
    store.remove_subscription(chat_id, ticker)
    count_after = store.count_subscriptions(chat_id)
    if count_before > count_after:
        await update.message.reply_text(f"🗑 Unsubscribed from {ticker}")
    else:
        await update.message.reply_text(f"Not subscribed to {ticker}")
    logger.info(f"User {chat_id} unsubscribed from {ticker}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all subscribed tickers with current signals."""
    chat_id = update.effective_user.id
    store = _get_user_store()
    tickers = store.list_subscriptions(chat_id)
    if not tickers:
        await update.message.reply_text("No subscriptions yet. Use /subscribe <ticker>.")
        return
    user = store.get_user(chat_id) or store.create_user(chat_id)
    max_subs = user.max_subscriptions
    limit_icon = "∞" if max_subs == 999 else str(max_subs)

    engine = _get_engine()
    lines = [f"📋 *Your Subscriptions ({len(tickers)}/{limit_icon}):*\n"]
    for t in tickers:
        state = engine.storage.get_signal_state(t)
        if state:
            lines.append(f"  {t}: {state.signal.value} (score={state.score:.2f})")
        else:
            lines.append(f"  {t}: no signal yet")
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )
    logger.info(f"User {chat_id} listed subscriptions")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed status for a ticker."""
    chat_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /status <ticker>")
        return
    ticker = args[0].upper()
    store = _get_user_store()
    tickers = store.list_subscriptions(chat_id)
    if ticker not in tickers:
        await update.message.reply_text(f"Not subscribed to {ticker}. Use /subscribe first.")
        return
    engine = _get_engine()
    state = engine.storage.get_signal_state(ticker)
    if not state:
        await update.message.reply_text(f"{ticker}: no signal data yet.")
        return
    lines = [
        f"📊 *{ticker}*",
        f"Signal: {state.signal.value}",
        f"Score: {state.score:.2f}",
        f"Category: {state.category.value}",
        f"Updated: {state.updated_at.strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger immediate scan for a ticker."""
    chat_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /signal <ticker>")
        return
    ticker = args[0].upper()
    engine = _get_engine()
    await update.message.reply_text(f"🔍 Scanning {ticker}…")
    event = engine.scan_ticker(ticker)
    if event:
        await send_signal_notification(context.bot, chat_id, event)
    else:
        state = engine.storage.get_signal_state(ticker)
        if state:
            await update.message.reply_text(
                f"{ticker}: {state.signal.value} (score={state.score:.2f}, no change)"
            )
        else:
            await update.message.reply_text(f"{ticker}: no signal detected.")
    logger.info(f"User {chat_id} triggered manual scan for {ticker}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help text."""
    await start_command(update, context)


_scan_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def _run_scan_region(region: str):
    engine = _get_engine()
    return engine.scan_region(region)


async def scanall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: show Top 10 from the latest scan in scan_history (non-blocking)."""
    chat_id = update.effective_user.id
    admin_chat_id = int(os.environ.get("SCAN_PRO_ADMIN_CHAT_ID", "0"))
    if chat_id != admin_chat_id:
        await update.message.reply_text("🔒 Admin only")
        return

    await update.message.reply_chat_action(action="typing")

    async def _get_top_signals():
        top_10 = _storage_cache.get_top_signals(10)
        total_row = _storage_cache._conn.execute(
            "SELECT COUNT(*) FROM scan_history"
        ).fetchone()
        total = total_row[0] if total_row else 0
        return top_10, total

    top_10, total = await _get_top_signals()

    if not top_10:
        await update.message.reply_text(
            "⚠️ No scan data yet. Run a scan first (e.g. nightly_scan)."
        )
        return

    buy_count = sum(1 for row in top_10 if row[1] == "BUY")
    sell_count = sum(1 for row in top_10 if row[1] == "SELL")
    hold_count = sum(1 for row in top_10 if row[1] == "HOLD")

    lines = [
        "🌍 *Top 10 Signals (latest scan)*",
        f"Total events in history: {total}",
        f"BUY: {buy_count}  SELL: {sell_count}  HOLD: {hold_count}",
        "",
        "*Top 10 signals:*",
    ]
    for rank, (ticker, signal, score, category, buy_c, sell_c, reason) in enumerate(
        top_10, start=1
    ):
        lines.append(
            f"{rank}. *{ticker}*: {signal} (score={score:.2f})"
        )
        if reason:
            lines.append(f"   ↳ {reason}")

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )
    logger.info(f"Admin {chat_id} ran /scanall — top {len(top_10)} signals shown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the last 5 scans with signal counts per scan."""
    chat_id = update.effective_user.id
    admin_chat_id = int(os.environ.get("SCAN_PRO_ADMIN_CHAT_ID", "0"))
    if chat_id != admin_chat_id:
        await update.message.reply_text("🔒 Admin only")
        return

    storage = _get_engine().storage

    # Query the last 5 distinct scan timestamps with their total signal counts.
    rows = storage._conn.execute(
        """
        SELECT timestamp,
               COUNT(*)       AS total,
               SUM(CASE WHEN signal='BUY'   THEN 1 ELSE 0 END) AS buys,
               SUM(CASE WHEN signal='SELL'  THEN 1 ELSE 0 END) AS sells,
               SUM(CASE WHEN signal='HOLD'  THEN 1 ELSE 0 END) AS holds
        FROM scan_history
        GROUP BY timestamp
        ORDER BY timestamp DESC
        LIMIT 5
        """
    ).fetchall()

    if not rows:
        await update.message.reply_text(
            "No scan history yet — run /scanall first"
        )
        return

    lines = ["🕓 *Scan History (last 5)*", ""]
    for ts, total, buys, sells, holds in rows:
        dt = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"📅 {dt}  —  "
            f"Total: {total}  |  "
            f"BUY: {buys}  SELL: {sells}  HOLD: {holds}"
        )

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )
    logger.info(f"Admin {chat_id} viewed /history")
