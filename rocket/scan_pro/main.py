"""Stock Scan Pro — main entry point."""
from __future__ import annotations

import asyncio
import logging
import os
from dotenv import load_dotenv

# Load .env BEFORE importing modules that read env vars
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "scan_pro.env")
load_dotenv(_env_path)

from telegram.ext import Application
from rocket.telegram_bot.bot import create_application, register_handlers
from threading import Thread

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the bot and the scan loop."""
    application = create_application()
    register_handlers(application)

    logger.info("Stock Scan Pro starting...")

    # Start polling in a background thread so the main loop stays alive
    def run_bot():
        application.run_polling()

    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Keep main thread alive
    try:
        while bot_thread.is_alive():
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
