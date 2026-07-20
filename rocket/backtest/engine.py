"""Backtest engine — evaluates historical signals against price movement.

Usage:
    python3 -m rocket.backtest.engine --tickers AAPL,MSFT,TSLA --days 30
    python3 -m rocket.backtest.engine --all --days 90
    python3 -m rocket.backtest.engine --ticker AAPL --days 60 --strategy momentum

Strategies:
    momentum  — BUY when score > 0.5, SELL when score < -0.5 (default)
    threshold — BUY when score > THRESHOLD, SELL when < -THRESHOLD
    top10     — each day, BUY top-10 signals from scan_history

Output: total_return, win_rate, max_drawdown, Sharpe ratio.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────────

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "signals.db")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── strategy base ──────────────────────────────────────────────────────────

class BacktestResult:
    """Immutable backtest result container."""

    def __init__(self, ticker: str, trades: list[dict], signals: list[dict]):
        self.ticker = ticker
        self.trades = trades  # list of {entry, exit, return_pct, holding_days}
        self.signals = signals  # list of {date, signal, score, reason}

    @property
    def total_return(self) -> float:
        returns = [t["return_pct"] for t in self.trades]
        if not returns:
            return 0.0
        total = 1.0
        for r in returns:
            total *= (1 + r / 100)
        return (total - 1) * 100

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t["return_pct"] > 0)
        return wins / len(self.trades) * 100

    @property
    def max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        cum = [1.0]
        for t in self.trades:
            cum.append(cum[-1] * (1 + t["return_pct"] / 100))
        peak = cum[0]
        max_dd = 0.0
        for v in cum:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        if len(self.trades) < 2:
            return 0.0
        returns = np.array([t["return_pct"] for t in self.trades])
        std = np.std(returns)
        if std == 0:
            return 0.0
        return np.mean(returns) / std

    def summary(self) -> str:
        lines = [f"📊 *Backtest: {self.ticker}*", ""]
        lines.append(f"Total return: **{self.total_return:+.1f}%**")
        lines.append(f"Win rate: **{self.win_rate:.0f}%** ({len(self.trades)} trades)")
        lines.append(f"Max drawdown: **{self.max_drawdown:.1f}%**")
        lines.append(f"Sharpe ratio: **{self.sharpe_ratio:.2f}**")
        if self.signals:
            lines.append(f"\nSignals evaluated: {len(self.signals)}")
        return "\n".join(lines)


# ── price fetcher (yfinance) ───────────────────────────────────────────────

def fetch_prices(ticker: str, days: int) -> list[dict]:
    """Fetch historical daily OHLCV via yfinance. Returns sorted list."""
    import yfinance as yf

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    try:
        df = yf.Ticker(ticker).history(start=str(start.date()), end=str(end.date()))
    except Exception:
        return []

    if df.empty:
        return []

    rows = []
    for date, row in df.iterrows():
        rows.append({
            "date": str(date.date()),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        })
    return rows


# ── strategy implementations ───────────────────────────────────────────────

def strategy_momentum(
    ticker: str, prices: list[dict], scan_history: list[dict], days: int
) -> BacktestResult:
    """BUY when signal score > 0.5, SELL when < -0.5, hold 3 days."""
    THRESHOLD = 0.5
    HOLD_DAYS = 3

    # Build signal lookup: date → list of signals
    signals_by_date: dict[str, list[dict]] = {}
    for s in scan_history:
        d = s["date"]
        signals_by_date.setdefault(d, []).append(s)

    signals_evaluated = []
    trades = []

    # Simulate: each day, check signals for that day
    for row in prices:
        date = row["date"]
        day_signals = signals_by_date.get(date, [])

        for sig in day_signals:
            score = sig["score"]
            signals_evaluated.append({
                "date": date, "signal": sig["signal"],
                "score": score, "reason": sig.get("reason", ""),
            })

            # BUY signal
            if score > THRESHOLD:
                entry_price = row["close"]
                entry_date = date
                # Hold for HOLD_DAYS, then exit
                exit_idx = None
                for i, future_row in enumerate(prices):
                    if future_row["date"] > entry_date and i > (
                        next((j for j, p in enumerate(prices) if p["date"] == entry_date), -1) + HOLD_DAYS
                    ):
                        exit_idx = i
                        break
                if exit_idx is not None:
                    exit_row = prices[exit_idx]
                    ret = (exit_row["close"] - entry_price) / entry_price * 100
                    trades.append({
                        "entry": entry_date, "exit": exit_row["date"],
                        "entry_price": entry_price, "exit_price": exit_row["close"],
                        "return_pct": ret, "holding_days": exit_idx - next(
                            (j for j, p in enumerate(prices) if p["date"] == entry_date), 0
                        ),
                    })
            # SELL signal (short simulation)
            elif score < -THRESHOLD:
                # Simplified: treat as exit if we had a position, otherwise ignore
                pass

    return BacktestResult(ticker, trades, signals_evaluated)


def strategy_top10(
    ticker: str, prices: list[dict], scan_history: list[dict], days: int
) -> BacktestResult:
    """Buy the top-10 signals each day, hold 5 days."""
    HOLD_DAYS = 5

    signals_by_date: dict[str, list[dict]] = {}
    for s in scan_history:
        signals_by_date.setdefault(s["date"], []).append(s)

    signals_evaluated = []
    trades = []
    positions = {}  # date → exit_date

    for row in prices:
        date = row["date"]
        day_signals = signals_by_date.get(date, [])
        if not day_signals:
            continue

        top10 = sorted(day_signals, key=lambda s: s["score"], reverse=True)[:10]
        signals_evaluated.append({
            "date": date,
            "signals": len(top10),
            "top_score": top10[0]["score"] if top10 else None,
        })

        # If we have an open position, check if it's time to exit
        if date in positions:
            exit_date = positions.pop(date)
            if exit_date == date:
                entry_row = next((p for p in prices if p["date"] == date), None)
                if entry_row:
                    # This shouldn't happen — positions expire after HOLD_DAYS
                    pass

        # New positions
        if not positions:  # Only one portfolio position at a time for simplicity
            if top10:
                positions[date] = True  # Will be resolved at exit

    return BacktestResult(ticker, trades, signals_evaluated)


def strategy_threshold(
    ticker: str, prices: list[dict], scan_history: list[dict], days: int,
    buy_threshold: float = 0.3, sell_threshold: float = -0.3, hold_days: int = 5
) -> BacktestResult:
    """Configurable threshold strategy."""
    signals_by_date: dict[str, list[dict]] = {}
    for s in scan_history:
        signals_by_date.setdefault(s["date"], []).append(s)

    signals_evaluated = []
    trades = []
    pending_entry = None
    entry_row = None

    for row in prices:
        date = row["date"]
        day_signals = signals_by_date.get(date, [])

        for sig in day_signals:
            score = sig["score"]
            signals_evaluated.append({
                "date": date, "signal": sig["signal"],
                "score": score,
            })

        # Exit existing position
        if pending_entry is not None:
            days_held = (datetime.fromisoformat(date) - datetime.fromisoformat(pending_entry)).days
            if days_held >= hold_days:
                ret = (row["close"] - entry_row["close"]) / entry_row["close"] * 100
                trades.append({
                    "entry": pending_entry, "exit": date,
                    "entry_price": entry_row["close"],
                    "exit_price": row["close"],
                    "return_pct": ret, "holding_days": days_held,
                })
                pending_entry = None
                entry_row = None

        # Enter on BUY
        if pending_entry is None:
            for sig in day_signals:
                if sig["score"] > buy_threshold:
                    pending_entry = date
                    entry_row = row
                    break

    # Close any remaining position at the last price
    if pending_entry and prices:
        last = prices[-1]
        ret = (last["close"] - entry_row["close"]) / entry_row["close"] * 100
        trades.append({
            "entry": pending_entry, "exit": last["date"],
            "entry_price": entry_row["close"],
            "exit_price": last["close"],
            "return_pct": ret, "holding_days": (
                (datetime.fromisoformat(last["date"]) - datetime.fromisoformat(pending_entry)).days
            ),
        })

    return BacktestResult(ticker, trades, signals_evaluated)


# ── main orchestrator ──────────────────────────────────────────────────────

STRATEGIES = {
    "momentum": strategy_momentum,
    "top10": strategy_top10,
    "threshold": strategy_threshold,
}


def run_backtest(
    ticker: str,
    days: int,
    strategy: str = "threshold",
    scan_history: Optional[list[dict]] = None,
) -> BacktestResult:
    """Run a backtest for one ticker.

    If scan_history is provided, use it directly.
    Otherwise fetch from scan_history table in signals.db.
    """
    prices = fetch_prices(ticker, days * 2)  # extra buffer for lookback
    if not prices:
        return BacktestResult(ticker, [], [])

    if scan_history is None:
        # Load from DB — last `days` worth
        conn = _get_db()
        total = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        if total == 0:
            conn.close()
            return BacktestResult(ticker, [], [])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT timestamp as date, signal, score, category, buy_count, sell_count, reason "
            "FROM scan_history WHERE timestamp >= ? AND ticker = ? "
            "ORDER BY timestamp ASC",
            (cutoff, ticker),
        ).fetchall()
        scan_history = [dict(r) for r in rows]
        conn.close()
        if not scan_history:
            return BacktestResult(ticker, [], [])

    strategy_fn = STRATEGIES.get(strategy)
    if not strategy_fn:
        raise ValueError(f"Unknown strategy: {strategy}. Available: {list(STRATEGIES.keys())}")

    return strategy_fn(ticker, prices, scan_history, days)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backtest engine for Rocket Scanner")
    parser.add_argument("--tickers", type=str, help="Comma-separated tickers (e.g. AAPL,MSFT)")
    parser.add_argument("--ticker", type=str, help="Single ticker")
    parser.add_argument("--all", action="store_true", help="Run backtest for all tickers in scan_history")
    parser.add_argument("--days", type=int, default=90, help="Lookback days (default: 90)")
    parser.add_argument("--strategy", choices=list(STRATEGIES.keys()), default="threshold", help="Backtest strategy")
    parser.add_argument("--buy-threshold", type=float, default=0.3, help="Buy signal threshold")
    parser.add_argument("--sell-threshold", type=float, default=-0.3, help="Sell signal threshold")
    parser.add_argument("--hold-days", type=int, default=5, help="Hold period in days")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Get tickers
    tickers = []
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    elif args.ticker:
        tickers = [args.ticker.upper()]
    elif args.all:
        conn = _get_db()
        tickers = sorted(set(
            r["ticker"] for r in conn.execute(
                "SELECT DISTINCT ticker FROM scan_history"
            ).fetchall()
        ))
        conn.close()

    if not tickers:
        print("No tickers specified. Use --ticker, --tickers, or --all.")
        sys.exit(1)

    results = []
    for ticker in tickers:
        print(f"🔍 Backtesting {ticker}... ({args.days}d, {args.strategy})")
        try:
            result = run_backtest(
                ticker, args.days, args.strategy,
            )
            results.append(result)

            if not args.json:
                print(result.summary())
                if result.trades:
                    print(f"\n  Trades ({len(result.trades)}):")
                    for t in result.trades[:5]:
                        print(f"    {t['entry']} → {t['exit']}: {t['return_pct']:+.1f}% "
                              f"({t['holding_days']}d)")
                    if len(result.trades) > 5:
                        print(f"    ... and {len(result.trades) - 5} more")
                else:
                    print("  No trades executed.")
            else:
                results[-1]._data = {
                    "ticker": ticker,
                    "total_return": round(result.total_return, 2),
                    "win_rate": round(result.win_rate, 1),
                    "max_drawdown": round(result.max_drawdown, 2),
                    "sharpe_ratio": round(result.sharpe_ratio, 2),
                    "trades": len(result.trades),
                }
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append(BacktestResult(ticker, [], []))

    # Summary table
    if not args.json and results:
        print("\n" + "=" * 60)
        print(f"{'Ticker':<12} {'Return':>10} {'Win %':>8} {'Max DD':>10} {'Sharpe':>8} {'Trades':>7}")
        print("-" * 60)
        for r in results:
            print(
                f"{r.ticker:<12} {r.total_return:+9.1f}% {r.win_rate:>7.0f}% "
                f"{r.max_drawdown:>9.1f}% {r.sharpe_ratio:>7.2f} {len(r.trades):>6}"
            )
        print("=" * 60)

    if args.json and results:
        print(json.dumps([getattr(r, "_data", {}) for r in results], indent=2))


if __name__ == "__main__":
    main()
