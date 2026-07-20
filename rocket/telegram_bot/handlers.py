"""Handler coroutines for Telegram /commands."""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sqlite3
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from rocket.scan_engine.engine import SignalEngine
from rocket.scan_engine.storage import SignalStorage
from rocket.telegram_bot.notifications import (
    send_signal_notification,
    send_subscribed_signal,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scan_pro_subscriptions.db")
USERS_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.db")

logger = logging.getLogger(__name__)

# Shared engine/storage — initialised on first use via _get_engine()
_engine_cache: object | None = None
_storage_cache: object | None = None
_user_store_cache: object | None = None


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            chat_id    INTEGER PRIMARY KEY,
            username   TEXT,
            created_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS subscriptions (
            chat_id    INTEGER NOT NULL,
            ticker     TEXT    NOT NULL,
            PRIMARY KEY (chat_id, ticker)
        )"""
    )
    conn.commit()
    return conn


def _get_user_store() -> "UserStore":
    global _user_store_cache
    if _user_store_cache is None:
        from rocket.users.store import UserStore
        _user_store_cache = UserStore(USERS_DB_PATH)
    return _user_store_cache


def _get_engine() -> SignalEngine:
    global _engine_cache, _storage_cache
    if _engine_cache is None:
        _storage_cache = SignalStorage(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "signals.db")
        )
        _engine_cache = SignalEngine(
            _storage_cache, config={"min_score": 0.5, "require_change": False}
        )
    return _engine_cache


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome user, save chat_id, show commands."""
    chat_id = update.effective_user.id
    username = update.effective_user.username
    db = _get_db()
    db.execute(
        "INSERT OR IGNORE INTO users (chat_id, username, created_at) VALUES (?, ?, ?)",
        (chat_id, username, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    db.close()

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
        "• /scanall — scan all tickers, show top 10 (admin only)\n"
        "• /history — view last 5 scans (admin only)\n\n"
        "📋 *Portfolio*\n"
        "• /list — show all subscriptions\n\n"
        "👤 *Account*\n"
        "• /plan — view plans and prices\n"
        "• /userstatus — view your status\n\n"
        "ℹ️ *Help*\n"
        "• /help — this message\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
    logger.info(f"User {chat_id} (/start)")


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe to ticker notifications."""
    chat_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /subscribe <ticker>")
        return
    ticker = args[0].upper()
    db = _get_db()
    store = _get_user_store()

    # Check free-tier limit
    try:
        store.add_subscription(chat_id, ticker)
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}")
        db.close()
        return

    try:
        db.execute(
            "INSERT INTO subscriptions (chat_id, ticker) VALUES (?, ?)",
            (chat_id, ticker),
        )
        db.commit()
    except sqlite3.IntegrityError:
        await update.message.reply_text(f"Already subscribed to {ticker}")
        db.close()
        return
    db.close()

    engine = _get_engine()
    event = engine.scan_ticker(ticker)
    if event:
        await send_signal_notification(context.bot, chat_id, event)
    else:
        state = engine.storage.get_signal_state(ticker)
        if state:
            await send_subscribed_signal(
                context.bot, chat_id, ticker,
                state.signal, state.category, state.score,
            )
        else:
            await update.message.reply_text(
                f"📋 Subscribed to {ticker}. No active signal right now."
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
    db = _get_db()
    store = _get_user_store()
    cur = db.execute(
        "DELETE FROM subscriptions WHERE chat_id = ? AND ticker = ?",
        (chat_id, ticker),
    )
    db.commit()
    # Also remove from user store
    store.remove_subscription(chat_id, ticker)
    db.close()
    if cur.rowcount:
        await update.message.reply_text(f"🗑 Unsubscribed from {ticker}")
    else:
        await update.message.reply_text(f"Not subscribed to {ticker}")
    logger.info(f"User {chat_id} unsubscribed from {ticker}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all subscribed tickers with current signals."""
    chat_id = update.effective_user.id
    db = _get_db()
    store = _get_user_store()
    rows = db.execute(
        "SELECT ticker FROM subscriptions WHERE chat_id = ? ORDER BY ticker",
        (chat_id,),
    ).fetchall()
    db.close()
    if not rows:
        await update.message.reply_text("No subscriptions yet. Use /subscribe <ticker>.")
        return
    tickers = [r[0] for r in rows]
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
    db = _get_db()
    sub = db.execute(
        "SELECT 1 FROM subscriptions WHERE chat_id = ? AND ticker = ?",
        (chat_id, ticker),
    ).fetchone()
    db.close()
    if not sub:
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


async def _do_scanall(update: Update):
    """Run the full multi-region scan and return (top_10, total_count)."""
    storage = _get_engine().storage

    for region in ["usa", "sweden", "china", "india"]:
        await update.message.reply_chat_action(action="typing")
        await asyncio.get_event_loop().run_in_executor(
            _scan_executor, _run_scan_region, region
        )

    top_10 = storage.get_top_signals(10)
    # Total rows in scan_history = all signals across all scans
    row = storage._conn.execute(
        "SELECT COUNT(*) FROM scan_history"
    ).fetchone()
    total = row[0] if row else 0
    return top_10, total


async def scanall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: scan all tickers across all regions (non-blocking).
    Shows Top 10 from scan_history by score after scan completes."""
    chat_id = update.effective_user.id
    admin_chat_id = int(os.environ.get("SCAN_PRO_ADMIN_CHAT_ID", "0"))
    if chat_id != admin_chat_id:
        await update.message.reply_text("🔒 Admin only")
        return

    await update.message.reply_text("🌍 Scanning all regions… This will take a few minutes.")

    top_10, total = await _do_scanall(update)

    if not top_10:
        await update.message.reply_text(
            "No scan data yet — run /scanall first"
        )
        return

    buy_count = sum(1 for row in top_10 if row[1] == "BUY")
    sell_count = sum(1 for row in top_10 if row[1] == "SELL")
    hold_count = sum(1 for row in top_10 if row[1] == "HOLD")

    lines = [
        "📊 *TOP 10 FROM LAST SCAN*",
        f"Total events scanned: {total}",
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
