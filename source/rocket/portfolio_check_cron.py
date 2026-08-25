#!/usr/bin/env python3
"""Portfolio check cron job — runs every 5 minutes to check for signal changes.

Usage:
    python3 rocket/portfolio_check_cron.py [--regions usa,sweden]

Checks the portfolio for any new signals and sends Telegram notifications
if there are any signal changes since the last run.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rocket.daily_scoring import DailyScoring
from rocket.telegram_notify import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("portfolio_check")


def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio signal check")
    parser.add_argument(
        "--regions",
        type=str,
        default="",
        help="Comma-separated regions to check (e.g. usa,sweden)",
    )
    args = parser.parse_args()

    regions = [r.strip().lower() for r in args.regions.split(",") if r.strip()] if args.regions else None

    logger.info("Starting portfolio check...")
    logger.info("Regions: %s", regions or "ALL")

    # Initialize components
    scorer = DailyScoring()

    # Run scoring
    top_signals = scorer.get_daily_top(
        regions=regions,
        limit=25,  # Check top 25 for signal changes
    )

    logger.info("Generated %d signals", len(top_signals))

    if not top_signals:
        logger.info("No signals to check")
        return

    # Load previous signals
    signals_file = scorer.output_dir / "daily_signals.json"
    prev_signals = []
    if signals_file.exists():
        try:
            with open(signals_file, "r") as f:
                prev_data = json.load(f)
                prev_signals = prev_data.get("signals", prev_data.get("results", []))
            logger.info("Loaded %d previous signals", len(prev_signals))
        except Exception as e:
            logger.warning("Failed to load previous signals: %s", e)

    # Compare with current signals
    current_tickers = {sig["ticker"] for sig in top_signals}
    prev_tickers = {sig["ticker"] for sig in prev_signals}

    # Find new signals
    new_signals = current_tickers - prev_tickers
    removed_signals = prev_tickers - current_tickers

    if new_signals or removed_signals:
        notifier = TelegramNotifier()

        # Send notification for new signals
        if new_signals:
            message = f"New Signals ({len(new_signals)})\n\n"
            for sig in top_signals[:5]:  # Top 5 new signals
                if sig["ticker"] in new_signals:
                    message += f"- {sig['ticker']} ({sig['region']}) score={sig['composite_score']:.2f}\n"
            message += f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            notifier.send(message)
            logger.info("Sent notification for %d new signals", len(new_signals))

        # Send notification for removed signals
        if removed_signals:
            message = f"Signals Removed ({len(removed_signals)})\n\n"
            for ticker in removed_signals:
                message += f"- {ticker}\n"
            message += f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            notifier.send(message)
            logger.info("Sent notification for %d removed signals", len(removed_signals))
    else:
        logger.info("No signal changes detected")


if __name__ == "__main__":
    main()
