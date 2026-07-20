"""Stock Scan Pro — main entry point."""
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application

from rocket.telegram_bot.bot import create_application, register_handlers

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the bot and the scan loop."""
    # Load .env BEFORE importing modules that read env vars
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "scan_pro.env")
    load_dotenv(env_path)

    application = create_application()
    register_handlers(application)

    logger.info("Stock Scan Pro starting...")
    await application.initialize()
    await application.start()

    # Start background polling
    async with application:
        logger.info("Bot is polling Telegram...")
        await application.post_init(None)
        await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
