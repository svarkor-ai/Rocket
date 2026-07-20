"""Nightly scanner — scans all regions, saves to signal_states + scan_history.

Usage:
    python3 -m rocket.nightly_scan          # full scan all regions
    python3 -m rocket.nightly_scan --test   # quick test (1 region, 5 tickers max)

Stores:
    - signal_states: latest signal per ticker (via SignalStorage)
    - scan_history:  ALL scan results with buy/sell/hold counts
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rocket.data.fetcher import fetch_ohlcv
from rocket.data.models import TickerInfo, Region
from rocket.data.universe import get_universe, get_region_count
from rocket.scoring.rocket_score import compute_rocket_score
from rocket.technical.signal_combiner import SignalSummary
from rocket.technical.models import Signal, SignalCategory
from rocket.scan_engine.models import SignalState
from rocket.scan_engine.storage import SignalStorage

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "signals.db")

BUY_THRESHOLD = 10
SELL_THRESHOLD = 10


def _derive_signal(summary: SignalSummary):
    """Map SignalSummary counts to (Signal, SignalCategory)."""
    if summary.buy_count > summary.sell_count and summary.buy_count >= BUY_THRESHOLD:
        return Signal.BUY, SignalCategory.MOMENTUM
    if summary.sell_count > summary.buy_count and summary.sell_count >= SELL_THRESHOLD:
        return Signal.SELL, SignalCategory.VOLATILITY
    return Signal.HOLD, SignalCategory.TREND


REGION_MAP = {
    "usa": "us", "sweden": "eu", "china": "asia",
    "india": "asia", "international": "us",
}


def _scan_one_ticker(ticker: str, region_key: str, storage: SignalStorage):
    """Run full analysis on one ticker. Returns (SignalState, SignalSummary) or None."""
    region_enum = REGION_MAP.get(region_key, "us")
    region = Region(region_enum)

    # Fetch OHLCV
    ohlcv = fetch_ohlcv([ticker])
    df = ohlcv.get(ticker)
    if df is None or df.empty:
        return None

    current_price = float(df["close"].iloc[-1])
    ticker_info = TickerInfo(
        ticker=ticker, name=ticker, region=region,
        sector="", market_cap=0.0, avg_volume=0.0,
    )

    # Compute full rocket score
    result = compute_rocket_score(df, ticker_info, current_price=current_price)
    summary: SignalSummary = result["signal_summary"]

    # Derive signal
    new_signal, category = _derive_signal(summary)
    score = float(summary.overall_score)

    # Normalize score to [0, 1]
    normalized_score = (score + 1.0) / 2.0
    if normalized_score < 0.5:
        return None

    # Save to signal_states
    now = datetime.now(timezone.utc)
    state = SignalState(
        ticker=ticker, signal=new_signal, score=score,
        category=category, updated_at=now,
    )
    storage.save_signal_state(state)
    return state, summary


def _bulk_insert_history(storage, records):
    """Insert many scan_history rows in one bulk operation."""
    if not records:
        return
    storage._conn.executemany(
        """INSERT INTO scan_history
           (timestamp, ticker, signal, score, category, buy_count, sell_count, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        records,
    )
    storage._conn.commit()


def run(regions: list, test: bool = False):
    """Run scan on given regions. Returns summary dict."""
    storage = SignalStorage(DB_PATH)
    all_states: list[tuple] = []
    records: list[tuple] = []

    for region in regions:
        tickers = get_universe(region)
        if test:
            tickers = tickers[:5]

        logger.info(f"Scanning region={region} ({len(tickers)} tickers)")

        for ticker in tickers:
            try:
                result = _scan_one_ticker(ticker, region, storage)
                if result is None:
                    continue

                state, summary = result
                now = datetime.now(timezone.utc)
                reason = (
                    f"{state.signal.value} (score={state.score:.2f}, "
                    f"buy={summary.buy_count}, sell={summary.sell_count})"
                )
                records.append((
                    now.isoformat(),
                    ticker,
                    state.signal.value,
                    state.score,
                    state.category.value,
                    summary.buy_count,
                    summary.sell_count,
                    reason,
                ))
                all_states.append(state)

            except Exception as e:
                logger.error(f"{ticker}: {e}")

        storage._conn.commit()

    # Bulk write history
    _bulk_insert_history(storage, records)

    buys = sum(1 for s in all_states if s.signal.value == "BUY")
    sells = sum(1 for s in all_states if s.signal.value == "SELL")
    holds = sum(1 for s in all_states if s.signal.value == "HOLD")

    storage.close()

    return {
        "regions": len(regions),
        "tickers": sum(len(get_universe(r)) for r in regions),
        "signals": len(all_states),
        "buys": buys, "sells": sells, "holds": holds,
    }


def main():
    parser = argparse.ArgumentParser(description="Nightly stock scanner")
    parser.add_argument("--test", action="store_true", help="Quick test (1 region, 5 tickers)")
    args = parser.parse_args()

    if args.test:
        regions = ["usa"]
    else:
        regions = ["usa", "sweden", "china", "india", "international"]

    summary = run(regions, test=args.test)

    print(f"\n{'='*60}")
    print(f"Nightly scan complete:")
    print(f"  Regions: {summary['regions']}")
    print(f"  Tickers scanned: {summary['tickers']}")
    print(f"  Signals emitted: {summary['signals']}")
    print(f"  BUY: {summary['buys']} | SELL: {summary['sells']} | HOLD: {summary['holds']}")
    print(f"  DB: {DB_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
