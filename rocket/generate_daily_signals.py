"""Generate daily_signals.json for the Top 10-25 tab in dashboard.

Usage:
    python3 rocket/generate_daily_signals.py [--regions usa,sweden,international]

This script:
1. Runs DailyScoring on the specified regions
2. Saves top 100 results to data/daily_signals.json
3. Returns exit code 0 on success

The dashboard reads this file to populate the Top 10-25 tab.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from rocket.daily_scoring import DailyScoring

logger = logging.getLogger(__name__)


def main(
    regions: list[str] | None = None,
    output: Path | None = None,
    top_n: int = 100,
) -> list[dict]:
    """Run scoring and save results.

    Args:
        regions: List of region filters (usa, sweden, international, global).
            Defaults to ['global'] which scans all tickers.
        output: Path to save JSON output. Defaults to data/daily_signals.json.
        top_n: Number of top signals to save. Defaults to 100.

    Returns:
        The list of signal dicts.
    """
    if output is None:
        output = Path(__file__).parent.parent / "data" / "daily_signals.json"

    if regions is None:
        regions = ["global"]

    # "global" means all regions
    if regions == ["global"]:
        regions = None  # Pass None to get_daily_top to scan all regions

    logger.info("Running daily scoring for regions: %s", regions or "all")
    scorer = DailyScoring()

    # Run scan with fast_only=False for full scoring
    signals = scorer.get_daily_top(limit=top_n, regions=regions, fast_only=False)

    # Save to JSON
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(signals, f, indent=2, default=str)

    logger.info("Saved %d signals to %s", len(signals), output)
    return signals


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate daily_signals.json")
    parser.add_argument(
        "--regions",
        type=str,
        default="global",
        help='Comma-separated list of regions (usa,sweden,international,global)',
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Number of top signals to save",
    )
    args = parser.parse_args()

    regions = [r.strip() for r in args.regions.split(",")]
    output = Path(args.output) if args.output else None

    signals = main(regions=regions, output=output, top_n=args.top_n)
    print(f"Generated {len(signals)} signals")
    print(f"Saved to {output or 'data/daily_signals.json'}")
