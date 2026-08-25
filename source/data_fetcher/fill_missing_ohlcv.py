#!/usr/bin/env python3
"""
Fill missing OHLCV data for tickers that don't have it.

Fetches OHLCV data with period='max' for tickers that don't have data yet.
Saves per-year parquet files in the EXACT same format as existing data:
  data/ohlcv/{ticker}/{year}.parquet

Usage:
    python -m data_fetcher.fill_missing_ohlcv              # fill all missing
    python -m data_fetcher.fill_missing_ohlcv --dry-run    # list what would be fetched
    python -m data_fetcher.fill_missing_ohlcv --limit 100  # limit to first 100 tickers
    python -m data_fetcher.fill_missing_ohlcv --ticker AAPL --ticker MSFT  # specific tickers
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/ohlcv/fill_missing.log", mode="a"),
    ],
)
logger = logging.getLogger("fill_missing")

DATA_DIR = Path("data")
OHLCV_DIR = DATA_DIR / "ohlcv"
UNIVERSE_FILE = DATA_DIR / "rocket_us_tickers.json"
RESULTS_FILE = OHLCV_DIR / "fill_missing_results.json"
CHECKPOINT_FILE = OHLCV_DIR / "fill_missing_checkpoint.json"

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests
BATCH_SIZE = 50
BATCH_PAUSE = 5.0  # seconds between batches


def get_existing_tickers() -> set:
    """Get set of ticker symbols that already have OHLCV data in data/ohlcv/."""
    tickers = set()
    if OHLCV_DIR.exists():
        for item in os.listdir(OHLCV_DIR):
            full = os.path.join(OHLCV_DIR, item)
            if os.path.isdir(full):
                parquet_files = [f for f in os.listdir(full) if f.endswith('.parquet')]
                if parquet_files:
                    tickers.add(item)
    return tickers


def load_universe() -> list:
    """Load US ticker universe from JSON file."""
    with open(UNIVERSE_FILE) as f:
        tickers = json.load(f)
    
    symbols = []
    for t in tickers:
        if isinstance(t, dict):
            symbols.append(t.get('ticker', ''))
        else:
            symbols.append(str(t))
    return symbols


def fetch_ohlcv(ticker: str, max_retries: int = 3) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data for a single ticker using yfinance with period='max'."""
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='max', interval='1d', auto_adjust=True)
            
            if df is None or df.empty or len(df) < 10:
                return None
            
            # Normalize columns (yfinance: Open, High, Low, Close, Volume)
            df = df.copy()
            df.index.name = 'timestamp'
            df = df.reset_index()
            
            col_map = {
                'Open': 'open', 'HIGH': 'high', 'High': 'high',
                'LOW': 'low', 'Low': 'low',
                'Close': 'close', 'CLOSE': 'close',
                'Volume': 'volume', 'VOLUME': 'volume',
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            
            # Ensure required columns exist
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col not in df.columns:
                    df[col] = 0.0
            
            # Convert prices to float
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            # Filter out rows with zero/negative prices
            df = df[(df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0) & (df['close'] > 0)]
            
            if df.empty or len(df) < 10:
                return None
            
            # Set timestamp as index and sort
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='first')
            df = df.set_index('timestamp')
            
            return df
        
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.debug(f"Failed to fetch {ticker}: {e}")
                return None


def save_yearly_parquet(df: pd.DataFrame, ticker: str) -> dict:
    """Save OHLCV data split by year into data/ohlcv/{ticker}/{year}.parquet.
    
    Returns dict with years saved and total rows.
    """
    df = df.copy()
    df['year'] = df.index.year
    ticker_dir = OHLCV_DIR / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)
    
    years_saved = {}
    total_rows = 0
    
    for year, group in df.groupby('year'):
        yearly = group.drop(columns=['year'])
        # Ensure columns are in correct order: open, high, low, close, volume
        cols = ['open', 'high', 'low', 'close', 'volume']
        yearly = yearly[cols]
        
        filepath = ticker_dir / f"{year}.parquet"
        yearly.to_parquet(filepath, engine="pyarrow")
        years_saved[year] = {
            'rows': len(yearly),
            'start': yearly.index.min().strftime('%Y-%m-%d'),
            'end': yearly.index.max().strftime('%Y-%m-%d'),
        }
        total_rows += len(yearly)
    
    return {'years_saved': years_saved, 'total_rows': total_rows}


def load_checkpoint() -> dict:
    """Load checkpoint from previous run."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {
        'completed': [],
        'failed': [],
        'started_at': None,
        'last_updated': None,
        'completed_count': 0,
        'failed_count': 0,
        'stats': {
            'total_rows_saved': 0,
            'total_years_saved': 0,
            'max_years_per_ticker': 0,
        }
    }


def save_checkpoint(checkpoint: dict):
    """Save checkpoint to disk."""
    checkpoint['last_updated'] = datetime.now(timezone.utc).isoformat()
    checkpoint['completed_at'] = checkpoint['last_updated']
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2)


def save_results(results: list, total_processed: int, total_universe: int):
    """Save final results to JSON file."""
    stats = {
        'total_rows_saved': 0,
        'total_years_saved': 0,
        'max_years_per_ticker': 0,
        'ok_10plus_years': 0,
        'incomplete_less_than_10y': 0,
        'empty_responses': 0,
        'errors': 0,
    }
    
    for r in results:
        if r.get('success'):
            years = len(r.get('years_saved', {}))
            stats['total_rows_saved'] += r.get('total_rows', 0)
            stats['total_years_saved'] += years
            if years >= 10:
                stats['ok_10plus_years'] += 1
            elif years > 0:
                stats['incomplete_less_than_10y'] += 1
            else:
                stats['empty_responses'] += 1
        else:
            stats['errors'] += 1
    
    # Also count existing tickers from prior runs
    existing = get_existing_tickers()
    
    summary = {
        'tickers_processed': total_processed,
        'total_universe_size': total_universe,
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'data_stats': stats,
        'summary': {
            'ok_10plus_years': stats['ok_10plus_years'],
            'incomplete_less_than_10y': stats['incomplete_less_than_10y'],
            'empty_responses': stats['empty_responses'],
            'errors': stats['errors'],
        },
    }
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(summary, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Fill missing OHLCV data for US tickers")
    parser.add_argument("--dry-run", action="store_true", help="List tickers without fetching")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers to fetch")
    parser.add_argument("--ticker", action="append", default=[], help="Specific ticker(s) to fetch")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size for fetching")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests")
    args = parser.parse_args()
    
    # Load universe
    logger.info(f"Loading US ticker universe from {UNIVERSE_FILE}...")
    all_tickers = load_universe()
    logger.info(f"Loaded {len(all_tickers)} tickers")
    
    # Get existing tickers
    existing = get_existing_tickers()
    logger.info(f"Already have data for {len(existing)} tickers")
    
    # Determine which tickers to fetch
    if args.ticker:
        tickers_to_fetch = args.ticker
    elif args.resume:
        checkpoint = load_checkpoint()
        already_done = set(checkpoint.get('completed', []) + checkpoint.get('failed', []))
        tickers_to_fetch = [t for t in all_tickers if t not in already_done and t not in existing]
        logger.info(f"Resuming: skipping {len(already_done)} already processed")
    else:
        tickers_to_fetch = [t for t in all_tickers if t not in existing]
    
    logger.info(f"Tickers to fetch: {len(tickers_to_fetch)}")
    
    # Dry run
    if args.dry_run:
        logger.info("=== DRY RUN ===")
        logger.info(f"Would fetch {len(tickers_to_fetch)} tickers")
        if tickers_to_fetch:
            logger.info(f"First 20: {tickers_to_fetch[:20]}")
        return
    
    # Limit
    if args.limit:
        tickers_to_fetch = tickers_to_fetch[:args.limit]
    
    # Start fetching
    logger.info(f"Starting OHLCV fetch for {len(tickers_to_fetch)} tickers...")
    start_time = time.time()
    completed = []
    failed = []
    results = []
    checkpoint = load_checkpoint()
    
    if checkpoint.get('started_at'):
        # Resume: keep existing completed/failed lists and stats
        logger.info(f"Resuming from checkpoint: {len(checkpoint.get('completed', []))} completed, {len(checkpoint.get('failed', []))} failed")
        completed = checkpoint.get('completed', [])
        failed = checkpoint.get('failed', [])
    else:
        checkpoint['started_at'] = datetime.now(timezone.utc).isoformat()
        checkpoint['completed'] = []
        checkpoint['failed'] = []
        checkpoint['stats'] = {
            'total_rows_saved': 0,
            'total_years_saved': 0,
            'max_years_per_ticker': 0,
        }
        completed = []
        failed = []
    
    batch_count = 0
    for i, ticker in enumerate(tickers_to_fetch):
        # Fetch data
        df = fetch_ohlcv(ticker)
        
        if df is None or df.empty or len(df) < 10:
            failed.append(ticker)
            results.append({'ticker': ticker, 'success': False, 'error': 'No data or too few rows'})
        else:
            # Save yearly parquet files
            save_result = save_yearly_parquet(df, ticker)
            years_count = len(save_result['years_saved'])
            total_rows = save_result['total_rows']
            
            completed.append(ticker)
            stats = checkpoint['stats']
            stats['total_rows_saved'] += total_rows
            stats['total_years_saved'] += years_count
            stats['max_years_per_ticker'] = max(
                stats['max_years_per_ticker'],
                years_count,
            )
            
            results.append({
                'ticker': ticker,
                'success': True,
                'years': years_count,
                'years_saved': save_result['years_saved'],
                'total_rows': total_rows,
            })
        
        # Save checkpoint every batch
        batch_count += 1
        if batch_count % args.batch_size == 0:
            checkpoint['completed'] = completed
            checkpoint['failed'] = failed
            save_checkpoint(checkpoint)
            elapsed = time.time() - start_time
            done = len(completed) + len(failed)
            logger.info(f"Checkpoint [{batch_count}/{len(tickers_to_fetch)}]: "
                       f"done={len(completed)}, failed={len(failed)} in {elapsed:.0f}s "
                       f"({elapsed/max(1,done):.1f}s/ticker)")
        
        # Rate limiting
        if i < len(tickers_to_fetch) - 1:
            time.sleep(args.delay)
    
    elapsed = time.time() - start_time
    total_processed = len(completed) + len(failed)
    
    # Save final results
    checkpoint['completed'] = completed
    checkpoint['failed'] = failed
    save_checkpoint(checkpoint)
    save_results(results, total_processed, len(tickers_to_fetch))
    
    # Print summary
    print("\n" + "=" * 60)
    print("FILL MISSING OHLCV — SUMMARY")
    print("=" * 60)
    print(f"  Total tickers to fetch: {len(tickers_to_fetch)}")
    print(f"  Completed: {len(completed):,}")
    print(f"  Failed: {len(failed):,}")
    print(f"  Success rate: {len(completed)/max(1,total_processed)*100:.0f}%")
    print(f"  Elapsed: {elapsed:.0f}s ({elapsed/max(1,total_processed):.1f}s/ticker)")
    
    if results:
        ok_10y = sum(1 for r in results if r.get('success') and len(r.get('years_saved', {})) >= 10)
        incomplete = sum(1 for r in results if r.get('success') and 0 < len(r.get('years_saved', {})) < 10)
        empty = sum(1 for r in results if r.get('success') and len(r.get('years_saved', {})) == 0)
        print(f"  ≥10 years: {ok_10y:,}")
        print(f"  <10 years: {incomplete:,}")
        print(f"  Empty/0 years: {empty:,}")
    
    print(f"  Total rows saved: {checkpoint['stats']['total_rows_saved']:,}")
    print(f"  Total years saved: {checkpoint['stats']['total_years_saved']:,.0f}")
    print(f"  Max years per ticker: {checkpoint['stats']['max_years_per_ticker']}")
    print(f"\n  Results saved to: {RESULTS_FILE}")
    print(f"  Checkpoint saved to: {CHECKPOINT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
