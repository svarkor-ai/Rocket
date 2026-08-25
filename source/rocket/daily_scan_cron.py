#!/usr/bin/env python3
"""Daily scan cron job — runs nightly to score universe tickers.

Usage:
    python3 rocket/daily_scan_cron.py [--regions usa,sweden] [--limit 25]

This script is designed to be run via cron/systemd timer at midnight UTC.
It produces a daily_signals.json file with top N buy signals.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rocket.daily_scoring import DailyScoring
from rocket.universe_db import UniverseDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_scan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily ticker scanning and scoring")
    parser.add_argument(
        "--regions",
        type=str,
        default="",
        help="Comma-separated regions to scan (e.g. usa,sweden,usa)",
    )
    parser.add_argument("--limit", type=int, default=25, help="Max tickers to return")
    args = parser.parse_args()

    regions = [r.strip().lower() for r in args.regions.split(",") if r.strip()] if args.regions else None

    logger.info("Starting daily scan...")
    logger.info("Regions: %s", regions or "ALL")
    logger.info("Limit: %d", args.limit)

    # Initialize components
    universe_db = UniverseDB()
    logger.info("Loaded %d tickers from universe", len(universe_db))

    if regions:
        valid_regions = universe_db.get_all_regions()
        invalid = [r for r in regions if r not in valid_regions]
        if invalid:
            logger.warning("Unknown regions: %s", ", ".join(invalid))
            logger.warning("Valid regions: %s", ", ".join(valid_regions))

    scorer = DailyScoring(universe_db=universe_db)

    # Run scoring
    top_signals = scorer.get_daily_top(
        regions=regions,
        limit=args.limit,
    )

    logger.info("Generated %d daily signals", len(top_signals))

    # Save results
    output_path = scorer.save_results(top_signals)
    logger.info("Results saved to %s", output_path)

    # Log top 5 for cron output
    if top_signals:
        logger.info("Top 5 signals:")
        for i, sig in enumerate(top_signals[:5], 1):
            logger.info(
                "  %d. %s (%s) score=%.2f signal=%s",
                i, sig["ticker"], sig["region"],
                sig["composite_score"], sig["signal"],
            )
    else:
        logger.warning("No signals generated!")

    logger.info("Daily scan complete!")


if __name__ == "__main__":
    main()
