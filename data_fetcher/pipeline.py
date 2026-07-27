#!/usr/bin/env python3
"""
Pipeline orchestrator — runs all data sources in sequence (or parallel with --parallel).

Usage:
    # Dry run — just shows what would be fetched
    python -m src.data_fetcher.pipeline --dry-run

    # Fetch Swedish stocks only
    python -m src.data_fetcher.pipeline --universe se --limit 10

    # Fetch crypto only (top 20)
    python -m src.data_fetcher.pipeline --universe crypto --limit 20

    # Fetch US stocks (first 50)
    python -m src.data_fetcher.pipeline --universe us --limit 50

    # Fetch all (will take time due to rate limits)
    python -m src.data_fetcher.pipeline --universe us,se,crypto,intl

    # Fetch all in parallel mode (multi-threaded)
    python -m src.data_fetcher.pipeline --universe us,se,crypto --parallel

    # Resume — skip tickers we already have
    python -m src.data_fetcher.pipeline --resume

    # Show stats on what we already have
    python -m src.data_fetcher.pipeline --stats
"""
import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from data_fetcher.config import DATA_DIR
from data_fetcher.common import load_existing_tickers, ProgressTracker
from data_fetcher.openavanza import fetch_se_stocks, get_available_symbols
from data_fetcher.coingecko import fetch_crypto, get_available_coins
from data_fetcher.yfinance_fetcher import fetch_us_stocks, fetch_international, fetch_bulk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DATA_DIR / "pipeline.log", mode="a"),
    ],
)
logger = logging.getLogger("pipeline")


def show_stats(data_dir: Path):
    """Show stats on already-fetched data."""
    sources = ["openavanza", "yfinance_us", "yfinance_intl", "coingecko"]
    print("\n=== DATA STATS ===\n")
    total_files = 0
    total_rows = 0

    for source in sources:
        source_dir = data_dir / source
        if not source_dir.exists():
            print(f"  {source:20s}: NO DATA")
            continue

        tickers = list(source_dir.glob("*"))
        n_tickers = len(tickers)
        n_files = sum(1 for t in tickers for _ in t.glob("*.parquet"))
        n_rows = 0
        for t in tickers:
            for f in t.glob("*.parquet"):
                import pandas as pd
                try:
                    df = pd.read_parquet(f)
                    n_rows += len(df)
                except Exception:
                    pass

        total_files += n_files
        total_rows += n_rows
        print(f"  {source:20s}: {n_tickers:4d} tickers, {n_files:5d} files, {n_rows:8d} rows")

    print(f"\n  {'TOTAL':20s}: {len(tickers) if 'tickers' in dir() else 0:4d} tickers, {total_files:5d} files, {total_rows:8d} rows\n")


def run_single_source(source: str, limit: Optional[int], dry_run: bool, resume: bool) -> dict:
    """
    Run a single data source and return results.

    Args:
        source: Source name ("openavanza", "coingecko", "us", "intl")
        limit: Max tickers to fetch
        dry_run: Dry run mode
        resume: Resume mode (skip existing)

    Returns:
        dict with source name, results, and summary
    """
    if resume:
        existing = load_existing_tickers(DATA_DIR, source)
        logger.info(f"Skipping {len(existing)} already-fetched tickers (resume mode)")
    else:
        existing = set()

    start_time = time.time()
    results = []
    summary = {"source": source, "fetched": 0, "failed": 0, "skipped": 0}

    try:
        if source == "openavanza":
            symbols = get_available_symbols()
            if not symbols:
                # Fallback to default list
                from data_fetcher.config import DEFAULT_SE_TICKERS
                symbols = DEFAULT_SE_TICKERS

            if limit:
                symbols = symbols[:limit]

            # Filter resume
            if resume:
                symbols = [s for s in symbols if s.upper() not in existing]

            results = fetch_se_stocks(symbols=symbols, limit=None, dry_run=dry_run)
            summary["fetched"] = sum(1 for _, _, s in results if s)
            summary["failed"] = sum(1 for _, _, s in results if not s)

        elif source == "coingecko":
            coins = get_available_coins()
            if not coins:
                from data_fetcher.config import DEFAULT_CRYPTO_COINS
                coins = DEFAULT_CRYPTO_COINS

            if limit:
                coins = coins[:limit]

            if resume:
                coins = [c for c in coins if c.lower() not in existing]

            results = fetch_crypto(coin_ids=coins, limit=None, dry_run=dry_run)
            summary["fetched"] = sum(1 for _, _, s in results if s)
            summary["failed"] = sum(1 for _, _, s in results if not s)

        elif source == "us":
            if resume:
                from data_fetcher.config import DEFAULT_US_TICKERS
                tickers = [t for t in DEFAULT_US_TICKERS if t not in existing]
                if limit:
                    tickers = tickers[:limit]
                results = fetch_us_stocks(tickers=tickers, limit=None, dry_run=dry_run)
            else:
                results = fetch_us_stocks(limit=limit, dry_run=dry_run)

            summary["fetched"] = sum(1 for _, _, s in results if s)
            summary["failed"] = sum(1 for _, _, s in results if not s)

        elif source == "intl":
            if resume:
                from data_fetcher.config import COUNTRY_CODES
                tickers = {k: v for k, v in COUNTRY_CODES.items()}
                if limit:
                    tickers = dict(list(tickers.items())[:limit])
                results = fetch_international(tickers_with_suffix=tickers, limit=None, dry_run=dry_run)
            else:
                results = fetch_international(limit=limit, dry_run=dry_run)

            summary["fetched"] = sum(1 for _, _, s in results if s)
            summary["failed"] = sum(1 for _, _, s in results if not s)

    except Exception as e:
        logger.error(f"Source {source} failed: {e}")
        summary["error"] = str(e)

    elapsed = time.time() - start_time
    summary["elapsed_seconds"] = round(elapsed, 1)
    summary["results"] = results

    logger.info(f"Source {source} done: {summary['fetched']} fetched, {summary['failed']} failed, {elapsed:.1f}s")
    return summary


def run_parallel(sources: list, limits: dict, dry_run: bool, resume: bool, max_workers: int = 3):
    """
    Run multiple sources in parallel using ThreadPoolExecutor.

    Args:
        sources: List of source names
        limits: Dict of source → limit
        dry_run: Dry run mode
        resume: Resume mode
        max_workers: Max concurrent threads
    """
    logger.info(f"=== PARALLEL MODE: {len(sources)} sources, {max_workers} workers ===")

    all_summaries = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for source in sources:
            limit = limits.get(source)
            future = executor.submit(run_single_source, source, limit, dry_run, resume)
            futures[future] = source

        for future in as_completed(futures):
            source = futures[future]
            try:
                summary = future.result()
                all_summaries.append(summary)
            except Exception as e:
                logger.error(f"Source {source} raised: {e}")
                all_summaries.append({"source": source, "error": str(e)})

    return all_summaries


def main():
    parser = argparse.ArgumentParser(description="Multi-source OHLCV data fetcher pipeline")
    parser.add_argument(
        "--universe",
        type=str,
        default="us,se,crypto",
        help="Comma-separated list of sources: us, se, crypto, intl"
    )
    parser.add_argument("--limit", type=int, default=None, help="Max tickers per source (global)")
    parser.add_argument("--per-source-limit", type=int, default=None,
                        help="Max tickers per source (overrides --limit)")
    parser.add_argument("--days", type=int, default=365, help="Days of history")
    parser.add_argument("--dry-run", action="store_true", help="List tickers without fetching")
    parser.add_argument("--resume", action="store_true", help="Skip already-fetched tickers")
    parser.add_argument("--parallel", action="store_true", help="Run sources in parallel")
    parser.add_argument("--workers", type=int, default=3, help="Max parallel workers")
    parser.add_argument("--stats", action="store_true", help="Show stats on existing data")
    parser.add_argument("--output", type=str, default=None, help="Output summary JSON file")
    parser.add_argument("--source-limit", type=str, default=None,
                        help="Per-source limits as JSON: '{\"us\": 50, \"se\": 20}'")

    args = parser.parse_args()

    # Stats mode
    if args.stats:
        show_stats(DATA_DIR)
        return

    # Parse per-source limits
    per_source_limits = {}
    if args.source_limit:
        per_source_limits = json.loads(args.source_limit)
    elif args.per_source_limit:
        per_source_limits = {s: args.per_source_limit for s in args.universe.split(",")}

    # Map universe keys
    universe_map = {
        "us": "us",
        "usa": "us",
        "se": "openavanza",
        "sweden": "openavanza",
        "crypto": "coingecko",
        "bitcoin": "coingecko",
        "intl": "intl",
        "international": "intl",
    }

    sources = []
    limits = {}
    for key in args.universe.split(","):
        key = key.strip().lower()
        mapped = universe_map.get(key, key)
        if mapped:
            sources.append(mapped)
            limits[mapped] = per_source_limits.get(mapped, args.limit)

    logger.info(f"Sources: {sources}")
    logger.info(f"Limits: {limits}")

    # Run
    if args.parallel:
        summaries = run_parallel(sources, limits, args.dry_run, args.resume, args.workers)
    else:
        summaries = []
        for source in sources:
            summary = run_single_source(source, limits.get(source), args.dry_run, args.resume)
            summaries.append(summary)

    # Print final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)

    total_fetched = 0
    total_failed = 0
    for s in summaries:
        fetched = s.get("fetched", 0)
        failed = s.get("failed", 0)
        elapsed = s.get("elapsed_seconds", 0)
        total_fetched += fetched
        total_failed += failed
        print(f"  {s.get('source', '?'):20s}: {fetched:5d} ✓  {failed:4d} ✗  ({elapsed:.1f}s)")

    total = total_fetched + total_failed
    rate = total_fetched / max(1, total) * 100
    print(f"\n  {'TOTAL':20s}: {total_fetched:5d} ✓  {total_failed:4d} ✗  ({rate:.0f}% success)\n")

    # Save summary JSON
    if args.output:
        with open(args.output, "w") as f:
            json.dump({"summaries": summaries, "total_fetched": total_fetched,
                       "total_failed": total_failed}, f, indent=2, default=str)
        logger.info(f"Summary saved to {args.output}")


if __name__ == "__main__":
    main()
