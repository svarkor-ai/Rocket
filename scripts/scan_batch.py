"""Scan a single batch of tickers from a JSON file.

Usage:
    python scripts/scan_batch.py --batch data/batches/batch_000.json

Outputs:
    data/batches/batch_000_results.json — scored results for this batch only
    appends to /tmp/scanall.log for real-time monitoring
"""
import argparse
import json
import logging
import os
import random
import sqlite3
import sys
import threading
import time
import traceback
import warnings
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

warnings.filterwarnings('ignore')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

LOG_FILE = '/tmp/scanall.log'
_log_fh = open(LOG_FILE, 'a')

def _log(msg, flush=True):
    """Print to stdout AND file simultaneously."""
    line = msg if isinstance(msg, str) else str(msg)
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        _log_fh.write(line + '\n')
        if flush:
            _log_fh.flush()
    except Exception:
        pass


def _fetch_with_thread_timeout(func, *args, timeout):
    """Run func in a thread, kill if it exceeds timeout."""
    result = [None]
    error = [None]

    def _run():
        try:
            result[0] = func(*args)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        raise TimeoutError(f"{func.__name__} timed out after {timeout}s")

    if error[0] is not None:
        raise error[0]

    return result[0]


def fetch_history_with_retry(ticker, max_retries=3, base_delay=1.0):
    """Fetch history with retry and hard timeout."""
    last_err = None
    for attempt in range(max_retries):
        try:
            hist = _fetch_with_thread_timeout(
                yf.Ticker(ticker).history,
                period='1y',
                timeout=12,
            )
            if hist is not None and len(hist) > 0:
                return hist
        except TimeoutError:
            last_err = TimeoutError(f"History timeout for {ticker}")
        except Exception as e:
            last_err = e

        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)

    if last_err:
        return None
    return None


def compute_score(ticker_symbol, hist, info):
    """Compute a composite score from technical indicators."""
    score = 0.0
    factors = 0

    if hist is None or len(hist) < 20:
        return 0.0, {'status': 'insufficient_data'}

    prices = hist['Close'].dropna()
    if len(prices) < 20:
        return 0.0, {'status': 'insufficient_data'}

    # 1. Momentum (40% weight) — 20-day return
    if len(prices) >= 20 and prices.iloc[-1] > 0 and prices.iloc[-20] > 0:
        mom = (prices.iloc[-1] - prices.iloc[-20]) / prices.iloc[-20]
        score += max(-0.5, min(0.5, mom * 5))  # scale to ±0.5
        factors += 1

    # 2. Trend (30% weight) — EMA alignment
    if len(prices) >= 20:
        ema20 = prices.rolling(20).mean().iloc[-1]
        ema50 = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else ema20
        current = prices.iloc[-1]
        if ema20 > 0:
            if current > ema20:
                score += 0.15
            else:
                score -= 0.15
            if len(prices) >= 50 and ema20 > ema50:
                score += 0.15
            elif len(prices) >= 50:
                score -= 0.15
        factors += 1

    # 3. Volatility (20% weight) — low vol = more stable
    if len(prices) >= 20:
        vol = prices.pct_change().std()
        if vol > 0:
            vol_score = 0.3 - min(vol * 3, 0.3)  # high vol → lower score
            score += vol_score
        factors += 1

    # 4. Volume trend (10% weight)
    if 'Volume' in hist.columns and len(hist) >= 20:
        vol_series = hist['Volume'].dropna()
        if len(vol_series) >= 10:
            recent_vol = vol_series.iloc[-5:].mean()
            older_vol = vol_series.iloc[-20:-10].mean()
            if older_vol > 0:
                vol_ratio = recent_vol / older_vol
                if vol_ratio > 1.2:
                    score += 0.05  # rising volume = bullish
                elif vol_ratio < 0.8:
                    score -= 0.05
        factors += 1

    # Normalize: divide by number of factors used
    if factors > 0:
        score = score / factors

    # Clamp to [-1, 1]
    score = max(-1.0, min(1.0, score))

    details = {
        'factors_used': factors,
        'score': round(score, 4),
    }

    return score, details


def scan_single_ticker(region, ticker):
    """Scan one ticker: fetch data, compute score."""
    full_ticker = ticker
    if region != 'usa':
        full_ticker = f"{ticker}.{region.upper()}"

    result = {
        'region': region,
        'ticker': ticker,
        'full_ticker': full_ticker,
        'score': 0.0,
        'score_details': {},
        'name': '',
        'sector': 'Unknown',
        'price': 0.0,
        'volume': 0,
        'status': 'failed',
        'error': None,
    }

    try:
        # Fetch history with retry
        hist = fetch_history_with_retry(full_ticker)

        if hist is None or len(hist) < 10:
            result['status'] = 'insufficient_data'
            return result

        # Fetch info
        info = {}
        try:
            info_result = [None]

            def _fetch_info():
                try:
                    info_result[0] = yf.Ticker(full_ticker).info
                except Exception:
                    pass

            t = threading.Thread(target=_fetch_info, daemon=True)
            t.start()
            t.join(timeout=5)
            info = info_result[0] if not t.is_alive() else {}
        except Exception:
            info = {}

        # Extract fields
        result['name'] = info.get('shortName', '') or info.get('longName', ticker)
        result['sector'] = info.get('sector', 'Unknown')
        result['price'] = float(info.get('currentPrice', 0) or 0)
        result['volume'] = int(info.get('volume', 0) or 0)

        # Compute score
        score, details = compute_score(full_ticker, hist, info)
        result['score'] = score
        result['score_details'] = details
        result['status'] = 'scored'

    except TimeoutError:
        result['status'] = 'timeout'
        result['error'] = 'fetch timed out'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:200]

    return result


def main():
    parser = argparse.ArgumentParser(description="Scan a single batch of tickers")
    parser.add_argument("--batch", required=True, help="Path to batch JSON file")
    parser.add_argument("--batch-id", type=int, required=True, help="Batch ID number")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between calls (seconds)")
    parser.add_argument("--max-workers", type=int, default=1, help="Max concurrent workers (1 = sequential)")
    args = parser.parse_args()

    # Load batch
    with open(args.batch) as f:
        tickers = json.load(f)

    _log(f"🚀 Scan batch {args.batch_id}: {len(tickers)} tickers from {args.batch}", flush=True)

    results = []
    scored_count = 0
    start_time = time.time()

    for i, t in enumerate(tickers):
        region = t['region']
        ticker = t['ticker']

        try:
            r = scan_single_ticker(region, ticker)
            results.append(r)

            if r['status'] == 'scored':
                scored_count += 1

            # Progress report every 500 tickers
            if (i + 1) % 500 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                _log(f"  ✅ Batch {args.batch_id}: {i+1}/{len(tickers)}, "
                     f"{scored_count} scored, {elapsed:.0f}s ({rate:.1f} tickers/s)", flush=True)

        except Exception as e:
            _log(f"  ❌ Batch {args.batch_id}: ticker {ticker} failed: {e}", flush=True)
            results.append({
                'region': region,
                'ticker': ticker,
                'score': 0.0,
                'status': 'error',
                'error': str(e),
            })

        # Delay between calls to avoid rate limiting
        if i < len(tickers) - 1:
            time.sleep(args.delay)

    # Save results
    output_path = Path(args.batch).parent / f"batch_{args.batch_id}_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    elapsed = time.time() - start_time
    rate = len(tickers) / elapsed if elapsed > 0 else 0

    _log(f"  ✅ Batch {args.batch_id} COMPLETE: {scored_count}/{len(tickers)} scored, "
         f"{elapsed:.0f}s ({rate:.1f} tickers/s) → {output_path}", flush=True)

    # Save to SQLite for querying
    db_path = Path('data/signals.db')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS batch_results (
        batch_id INTEGER, ticker TEXT, region TEXT, full_ticker TEXT,
        score REAL, status TEXT, name TEXT, sector TEXT,
        price REAL, volume INTEGER, score_details TEXT, error TEXT,
        scanned_at TEXT
    )''')

    now = datetime.now(timezone.utc).isoformat()
    for r in results:
        c.execute(
            'INSERT OR REPLACE INTO batch_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (args.batch_id, r['ticker'], r.get('region',''), r.get('full_ticker',''),
             r['score'], r['status'], r.get('name',''), r.get('sector',''),
             r.get('price',0), r.get('volume',0),
             json.dumps(r.get('score_details',{})), r.get('error',''), now)
        )
    conn.commit()
    conn.close()

    _log(f"  💾 Batch {args.batch_id} saved to SQLite", flush=True)
    print(f"📊 Batch {args.batch_id} results: {len(results)} total, {scored_count} scored")


if __name__ == "__main__":
    main()
