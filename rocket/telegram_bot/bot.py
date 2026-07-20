"""Main Telegram Bot Application — python-telegram-bot v20+."""
from __future__ import annotations

import logging
import os

from telegram.ext import ApplicationBuilder, CommandHandler

from rocket.users.store import UserStore

from .handlers import (
    start_command,
    subscribe_command,
    unsubscribe_command,
    list_command,
    status_command,
    signal_command,
    help_command,
    scanall_command,
    history_command,
)
from .commands import (
    plan_command,
    user_status_command,
    admin_list_command,
    activate_command,
    deactivate_command,
)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("SCAN_PRO_TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("SCAN_PRO_ADMIN_CHAT_ID", "")

_user_store: UserStore | None = None


def _get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        db_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "data",
            "users.db",
        )
        _user_store = UserStore(db_path)
    return _user_store


def create_application() -> Application:
    """Build and return the telegram-bot Application."""
    return (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )


def _make_admin_wrapper(fn, store, admin_chat_id):
    """Wrap a function so only admin_chat_id can call it."""
    async def wrapper(update, context):
        if admin_chat_id is None or str(update.effective_user.id) != str(admin_chat_id):
            await update.message.reply_text("Du har inte behörighet.")
            return
        return await fn(update, context, store)
    return wrapper


def register_handlers(application: Application) -> None:
    """Wire every /command to its handler coroutine."""
    store = _get_user_store()
    admin_chat_id = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else None

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("signal", signal_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", plan_command))
    application.add_handler(CommandHandler("userstatus", lambda u, c: user_status_command(u, c, store)))
    application.add_handler(CommandHandler("adminlist", _make_admin_wrapper(admin_list_command, store, admin_chat_id)))
    application.add_handler(CommandHandler("adminactivate", _make_admin_wrapper(activate_command, store, admin_chat_id)))
    application.add_handler(CommandHandler("admindeactivate", _make_admin_wrapper(deactivate_command, store, admin_chat_id)))
    application.add_handler(CommandHandler("scanall", scanall_command))
    application.add_handler(CommandHandler("history", history_command))

    logger.info("Telegram bot handlers registered")
