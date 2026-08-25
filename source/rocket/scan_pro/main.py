"""Stock Scan Pro — main entry point."""
from __future__ import annotations

import logging
import os
from dotenv import load_dotenv

# Load .env BEFORE importing modules that read env vars
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "scan_pro.env")
load_dotenv(_env_path)

from rocket.telegram_bot.bot import create_application, register_handlers

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    application = create_application()
    register_handlers(application)

    logger.info("Stock Scan Pro starting...")

    # Start portfolio scan in a background daemon thread (non-blocking)
    from rocket.scan_pro.portfolio_scan import start_portfolio_scan
    start_portfolio_scan()

    application.run_polling()
