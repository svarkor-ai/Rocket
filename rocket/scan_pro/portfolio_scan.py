"""Portfolio scan — background loop that checks subscribed tickers for signal changes."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot

from rocket.scan_engine.engine import SignalEngine
from rocket.scan_engine.storage import SignalStorage
from rocket.telegram_bot.notifications import send_signal_notification
from rocket.users.store import UserStore

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = _REPO_ROOT / "data" / "users.db"
SIGNALS_DB_PATH = _REPO_ROOT / "data" / "signals.db"

MIN_SCORE = 0.0
REQUIRE_CHANGE = True
COOLDOWN_MINUTES = 10
SCAN_INTERVAL_SECONDS = 300   # 5 minutes


def _send_sync(bot, chat_id, event, loop):
    """Run an async notification in the event loop, suppressing errors."""
    try:
        coro = send_signal_notification(bot, chat_id, event)
        asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=10)
    except Exception:
        logger.exception("Failed to notify chat %s about %s", chat_id, event.ticker)


def _run_scan_loop(ctx):
    """Blocking scan loop — runs in a daemon thread."""
    bot = ctx["bot"]
    engine = ctx["engine"]
    store = ctx["store"]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while ctx["running"]:
        try:
            _do_one_scan(bot, engine, store, loop)
        except Exception:
            logger.exception("Portfolio scan error")

        # Sleep in small increments so we can exit quickly on shutdown
        for _ in range(SCAN_INTERVAL_SECONDS * 2):
            if not ctx["running"]:
                break
            time.sleep(0.5)

    loop.call_soon_threadsafe(loop.stop)
    loop.run_forever()
    loop.close()


def _do_one_scan(bot, engine, store, loop):
    """Run a single scan pass over all users with subscriptions."""
    user_count = 0
    ticker_count = 0
    event_count = 0

    # Get all users with subscriptions
    try:
        rows = store.db.execute(
            "SELECT DISTINCT chat_id FROM user_subscriptions"
        ).fetchall()
        all_users = [row["chat_id"] for row in rows]
    except Exception:
        logger.exception("Failed to query subscriptions")
        return

    for chat_id in all_users:
        subscriptions = store.list_subscriptions(chat_id)
        if not subscriptions:
            continue

        user_count += 1
        for ticker in subscriptions:
            ticker_count += 1
            try:
                event = engine.scan_ticker(ticker)
            except Exception:
                logger.exception("Portfolio scan error for %s", ticker)
                continue

            if event is not None:
                event_count += 1
                try:
                    _send_sync(bot, chat_id, event, loop)
                except Exception:
                    logger.exception(
                        "Notification failed for %s => chat %s", ticker, chat_id
                    )

    logger.info(
        "Portfolio scan: processed %d users, %d tickers, %d events",
        user_count, ticker_count, event_count,
    )


def start_portfolio_scan(bot_token=None):
    """Start the portfolio scan as a daemon thread.

    Creates its own Bot and Engine instances (shared with no other code).
    Gracefully exits on SIGTERM/SIGINT."""
    # Resolve token from environment
    _token = None
    if bot_token is not None:
        _token = bot_token
    else:
        _token = os.environ.get("SCAN_PRO_TELEGRAM_BOT_TOKEN", "")
        if not _token:
            _token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if _token is None or _token == "":
        logger.error("Bot token not set - skipping portfolio scan")
        return

    # Load .env for any other env vars
    env_path = Path(__file__).resolve().parent.parent.parent / "config" / "scan_pro.env"
    if env_path.exists():
        load_dotenv(env_path)

    # Build shared context
    ctx = {
        "bot": Bot(token=_token),
        "engine": SignalEngine(
            SignalStorage(str(SIGNALS_DB_PATH)),
            config={
                "min_score": MIN_SCORE,
                "require_change": REQUIRE_CHANGE,
                "cooldown_minutes": COOLDOWN_MINUTES,
            },
        ),
        "store": UserStore(str(DB_PATH)),
        "running": True,
    }

    # Set up graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Portfolio scan received shutdown signal")
        ctx["running"] = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Start scan loop in daemon thread
    thread = threading.Thread(target=_run_scan_loop, args=(ctx,), daemon=True)
    thread.start()
    logger.info("Portfolio scan started (every %ds)", SCAN_INTERVAL_SECONDS)
