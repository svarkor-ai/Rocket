"""Main Telegram Bot Application — python-telegram-bot v20+."""
from __future__ import annotations

import logging
import os

from telegram.ext import ApplicationBuilder, CommandHandler

from .handlers import (
    start_command,
    subscribe_command,
    unsubscribe_command,
    list_command,
    status_command,
    signal_command,
    help_command,
)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("SCAN_PRO_TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("SCAN_PRO_ADMIN_CHAT_ID", "")


def create_application() -> Application:
    """Build and return the telegram-bot Application."""
    return (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )


def register_handlers(application: Application) -> None:
    """Wire every /command to its handler coroutine."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("signal", signal_command))
    application.add_handler(CommandHandler("help", help_command))

    # Register handlers that need bot/chat_id context
    from .handlers import register_callback_handlers
    register_callback_handlers(application)
    logger.info("Telegram bot handlers registered")
