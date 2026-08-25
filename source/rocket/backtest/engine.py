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
Enhanced: annualized_return, sortino_ratio, commission, slippage,
          stop-loss/take-profit, position sizing, walk-forward validation.
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
TRADING_DAYS_PER_YEAR = 252


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── transaction cost helpers ───────────────────────────────────────────────

def _compute_entry_cost(
    price: float,
    commission: float,
    slippage_pct: float,
) -> tuple[float, float]:
    """Return (effective_entry_price, total_entry_cost_deducted)."""
    slip = price * slippage_pct
    comm = price * commission
    effective = price + slip  # we pay more on entry
    return effective, comm + slip


def _compute_exit_cost(
    price: float,
    commission: float,
    slippage_pct: float,
) -> tuple[float, float]:
    """Return (effective_exit_price, total_exit_cost_deducted)."""
    slip = price * slippage_pct
    comm = price * commission
    effective = price - slip  # we receive less on exit
    return effective, comm + slip


# ── BacktestResult ─────────────────────────────────────────────────────────

class BacktestResult:
    """Immutable backtest result container."""

    def __init__(
        self,
        ticker: str,
        trades: list[dict],
        signals: list[dict],
        total_commission: float = 0.0,
        position_size_pct: float = 1.0,
        capital: float = 1.0,
        trading_days: int = 0,
    ):
        self.ticker = ticker
        self.trades = trades  # list of {entry, exit, return_pct, holding_days,
                              #          entry_price, exit_price, raw_return_pct,
                              #          commission_cost}
        self.signals = signals  # list of {date, signal, score, reason}
        self.total_commission = total_commission
        self._position_size_pct = position_size_pct
        self._capital = capital
        self._trading_days = trading_days

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

    @property
    def annualized_return(self) -> float:
        """Geometric mean annualised return (percentage).

        Uses the number of trading days covered by the trades to
        annualise the compound return.
        """
        if not self.trades or self._trading_days <= 0:
            return 0.0
        compound = 1.0
        for t in self.trades:
            compound *= (1 + t["return_pct"] / 100)
        (compound - 1) * 100  # % over full period
        years = self._trading_days / TRADING_DAYS_PER_YEAR
        if years <= 0:
            return 0.0
        ar = (compound ** (1 / years) - 1) * 100
        return ar

    @property
    def sortino_ratio(self) -> float:
        """Sortino ratio using downside deviation of trade returns."""
        if len(self.trades) < 2:
            return 0.0
        returns = np.array([t["return_pct"] for t in self.trades])
        downside = returns[returns < 0]
        if len(downside) == 0:
            return 0.0
        downside_dev = np.sqrt(np.mean(downside ** 2))
        if downside_dev == 0:
            return 0.0
        return np.mean(returns) / downside_dev

    @property
    def avg_holding_days(self) -> float:
        """Average number of days positions were held."""
        if not self.trades:
            return 0.0
        return sum(t.get("holding_days", 0) for t in self.trades) / len(self.trades)

    def summary(self) -> str:
        lines = [f"📊 *Backtest: {self.ticker}*", ""]
        lines.append(f"Total return: **{self.total_return:+.1f}%**")
        lines.append(f"Annualised return: **{self.annualized_return:+.1f}%**")
        lines.append(f"Win rate: **{self.win_rate:.0f}%** ({len(self.trades)} trades)")
        lines.append(f"Max drawdown: **{self.max_drawdown:.1f}%**")
        lines.append(f"Sharpe ratio: **{self.sharpe_ratio:.2f}**")
        lines.append(f"Sortino ratio: **{self.sortino_ratio:.2f}**")
        lines.append(f"Avg holding days: **{self.avg_holding_days:.1f}**")
        if self.total_commission != 0:
            lines.append(f"Total commission: **{self.total_commission:+.2f}%**")
        if self._position_size_pct != 1.0:
            lines.append(f"Position size: **{self._position_size_pct * 100:.0f}%**")
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

def _execute_trade(
    entry_date: str,
    entry_price: float,
    exit_date: str,
    exit_price: float,
    commission: float,
    slippage_entry_pct: float,
    slippage_exit_pct: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    position_size_pct: float,
    holding_days: int,
) -> dict:
    """Apply costs, stop-loss/take-profit checks, and position sizing.

    Returns a trade dict suitable for BacktestResult.trades.
    """
    # Commission costs
    entry_comm = entry_price * commission
    exit_comm = exit_price * commission

    # Slippage: entry — we pay more (price + slip), exit — we get less
    entry_slip = entry_price * slippage_entry_pct
    exit_slip = exit_price * slippage_exit_pct

    effective_entry = entry_price + entry_slip
    effective_exit = exit_price - exit_slip

    # Raw return
    if effective_entry == 0:
        raw_ret = 0.0
    else:
        raw_ret = (effective_exit - effective_entry) / effective_entry * 100

    # Stop-loss / take-profit override (check on exit price, before costs)
    if stop_loss_pct > 0:
        if (exit_price - entry_price) / entry_price * 100 <= -stop_loss_pct:
            # Price dropped enough — force exit at stop level
            stop_price = entry_price * (1 - stop_loss_pct / 100)
            effective_exit = stop_price - exit_slip
            exit_price = stop_price
            raw_ret = (effective_exit - effective_entry) / effective_entry * 100

    if take_profit_pct > 0:
        if (exit_price - entry_price) / entry_price * 100 >= take_profit_pct:
            # Price rose enough — force exit at TP level
            tp_price = entry_price * (1 + take_profit_pct / 100)
            effective_exit = tp_price - exit_slip
            exit_price = tp_price
            raw_ret = (effective_exit - effective_entry) / effective_entry * 100

    # Position sizing: scale the return
    scaled_ret = raw_ret * position_size_pct

    # Total commission as % of notional at entry
    total_comm_pct = (entry_comm + exit_comm) / entry_price * 100 * position_size_pct

    return {
        "entry": entry_date,
        "exit": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "raw_return_pct": raw_ret,
        "return_pct": scaled_ret,
        "holding_days": holding_days,
        "commission_cost": total_comm_pct,
    }


def strategy_momentum(
    ticker: str,
    prices: list[dict],
    scan_history: list[dict],
    days: int,
    commission: float = 0.001,
    slippage_entry_pct: float = 0.0005,
    slippage_exit_pct: float = 0.0005,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
    position_size_pct: float = 1.0,
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
    total_commission = 0.0

    # Date-to-index lookup for efficient exit finding
    date_to_idx: dict[str, int] = {p["date"]: i for i, p in enumerate(prices)}

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
                entry_idx = date_to_idx[date]
                exit_idx = entry_idx + HOLD_DAYS
                if exit_idx < len(prices):
                    exit_row = prices[exit_idx]
                    holding = exit_idx - entry_idx
                    trade = _execute_trade(
                        entry_date=date,
                        entry_price=entry_price,
                        exit_date=exit_row["date"],
                        exit_price=exit_row["close"],
                        commission=commission,
                        slippage_entry_pct=slippage_entry_pct,
                        slippage_exit_pct=slippage_exit_pct,
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                        position_size_pct=position_size_pct,
                        holding_days=holding,
                    )
                    trades.append(trade)
                    total_commission += trade["commission_cost"]

            # SELL signal (short simulation)
            elif score < -THRESHOLD:
                pass

    return BacktestResult(
        ticker, trades, signals_evaluated,
        total_commission=total_commission,
        position_size_pct=position_size_pct,
        trading_days=len(prices),
    )


def strategy_top10(
    ticker: str,
    prices: list[dict],
    scan_history: list[dict],
    days: int,
    commission: float = 0.001,
    slippage_entry_pct: float = 0.0005,
    slippage_exit_pct: float = 0.0005,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
    position_size_pct: float = 1.0,
) -> BacktestResult:
    """Buy the top-10 signals each day, hold 5 days."""
    HOLD_DAYS = 5

    signals_by_date: dict[str, list[dict]] = {}
    for s in scan_history:
        signals_by_date.setdefault(s["date"], []).append(s)

    signals_evaluated = []
    trades = []
    total_commission = 0.0
    # positions: date → (entry_price, exit_date_idx)
    open_positions: list[tuple[str, float, int]] = []  # (date, price, hold_until_idx)

    date_to_idx: dict[str, int] = {p["date"]: i for i, p in enumerate(prices)}

    for idx, row in enumerate(prices):
        date = row["date"]

        # Check for positions to close
        to_remove = []
        for i, (p_date, p_price, hold_until) in enumerate(open_positions):
            if idx >= hold_until:
                exit_row = prices[idx]
                trade = _execute_trade(
                    entry_date=p_date,
                    entry_price=p_price,
                    exit_date=exit_row["date"],
                    exit_price=exit_row["close"],
                    commission=commission,
                    slippage_entry_pct=slippage_entry_pct,
                    slippage_exit_pct=slippage_exit_pct,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    position_size_pct=position_size_pct,
                    holding_days=idx - date_to_idx[p_date],
                )
                trades.append(trade)
                total_commission += trade["commission_cost"]
                to_remove.append(i)

        for i in sorted(to_remove, reverse=True):
            open_positions.pop(i)

        # New positions from top-10
        day_signals = signals_by_date.get(date, [])
        if not day_signals:
            continue

        top10 = sorted(day_signals, key=lambda s: s["score"], reverse=True)[:10]
        signals_evaluated.append({
            "date": date,
            "signals": len(top10),
            "top_score": top10[0]["score"] if top10 else None,
        })

        # Open position at close price
        if top10 and len(open_positions) == 0:  # one portfolio position at a time
            hold_until = idx + HOLD_DAYS
            open_positions.append((date, row["close"], hold_until))

    # Close any remaining position at the last price
    if open_positions and prices:
        last_idx = len(prices) - 1
        last_row = prices[last_idx]
        for p_date, p_price, _ in open_positions:
            trade = _execute_trade(
                entry_date=p_date,
                entry_price=p_price,
                exit_date=last_row["date"],
                exit_price=last_row["close"],
                commission=commission,
                slippage_entry_pct=slippage_entry_pct,
                slippage_exit_pct=slippage_exit_pct,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                position_size_pct=position_size_pct,
                holding_days=last_idx - date_to_idx[p_date],
            )
            trades.append(trade)
            total_commission += trade["commission_cost"]

    return BacktestResult(
        ticker, trades, signals_evaluated,
        total_commission=total_commission,
        position_size_pct=position_size_pct,
        trading_days=len(prices),
    )


def strategy_threshold(
    ticker: str,
    prices: list[dict],
    scan_history: list[dict],
    days: int,
    buy_threshold: float = 0.3,
    sell_threshold: float = -0.3,
    hold_days: int = 5,
    commission: float = 0.001,
    slippage_entry_pct: float = 0.0005,
    slippage_exit_pct: float = 0.0005,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
    position_size_pct: float = 1.0,
) -> BacktestResult:
    """Configurable threshold strategy."""
    signals_by_date: dict[str, list[dict]] = {}
    for s in scan_history:
        signals_by_date.setdefault(s["date"], []).append(s)

    signals_evaluated = []
    trades = []
    total_commission = 0.0
    pending_entry: Optional[tuple[str, float]] = None  # (date, price)

    date_to_idx: dict[str, int] = {p["date"]: i for i, p in enumerate(prices)}

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
            p_date, p_price = pending_entry
            entry_idx = date_to_idx[p_date]
            days_held = date_to_idx[date] - entry_idx
            if days_held >= hold_days:
                trade = _execute_trade(
                    entry_date=p_date,
                    entry_price=p_price,
                    exit_date=date,
                    exit_price=row["close"],
                    commission=commission,
                    slippage_entry_pct=slippage_entry_pct,
                    slippage_exit_pct=slippage_exit_pct,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    position_size_pct=position_size_pct,
                    holding_days=days_held,
                )
                trades.append(trade)
                total_commission += trade["commission_cost"]
                pending_entry = None

        # Enter on BUY
        if pending_entry is None:
            for sig in day_signals:
                if sig["score"] > buy_threshold:
                    pending_entry = (date, row["close"])
                    break

    # Close any remaining position at the last price
    if pending_entry and prices:
        last = prices[-1]
        p_date, p_price = pending_entry
        entry_idx = date_to_idx[p_date]
        trade = _execute_trade(
            entry_date=p_date,
            entry_price=p_price,
            exit_date=last["date"],
            exit_price=last["close"],
            commission=commission,
            slippage_entry_pct=slippage_entry_pct,
            slippage_exit_pct=slippage_exit_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            position_size_pct=position_size_pct,
            holding_days=len(prices) - 1 - entry_idx,
        )
        trades.append(trade)
        total_commission += trade["commission_cost"]

    return BacktestResult(
        ticker, trades, signals_evaluated,
        total_commission=total_commission,
        position_size_pct=position_size_pct,
        trading_days=len(prices),
    )


# ── walk-forward helper ────────────────────────────────────────────────────

def _run_single_backtest(
    ticker: str,
    prices: list[dict],
    strategy_fn,
    strategy_name: str,
    days: int,
    **kwargs,
) -> BacktestResult:
    """Run one backtest window with the given prices slice."""
    if not prices:
        return BacktestResult(ticker, [], [], trading_days=0)

    # Build scan_history from the price dates (strategy uses scan_history
    # for signal lookup — the real scan_history is passed via kwargs).
    result = strategy_fn(
        ticker=ticker,
        prices=prices,
        days=days,
        **kwargs,
    )
    return result


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
    *,
    commission: float = 0.001,
    slippage_entry_pct: float = 0.0005,
    slippage_exit_pct: float = 0.0005,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
    position_size_pct: float = 1.0,
    walk_forward: bool = False,
    walk_train_days: int = 60,
    walk_test_days: int = 20,
    **strategy_kwargs,
) -> BacktestResult:
    """Run a backtest for one ticker.

    If scan_history is provided, use it directly.
    Otherwise fetch from scan_history table in signals.db.

    Parameters
    ----------
    ticker : str
        Ticker symbol.
    days : int
        Lookback window in calendar days.
    strategy : str
        Strategy name (momentum, threshold, top10).
    scan_history : list[dict] or None
        Pre-loaded signal history; fetched from DB if None.
    commission : float
        Commission rate per trade (0.001 = 0.1%). Applied on both entry
        and exit. Default 0.001.
    slippage_entry_pct : float
        Slippage on entry (fraction of price). Default 0.0005 (0.05%).
    slippage_exit_pct : float
        Slippage on exit (fraction of price). Default 0.0005 (0.05%).
    stop_loss_pct : float
        Stop-loss threshold as % (e.g. 5.0 = 5%). Default 0.0 (disabled).
    take_profit_pct : float
        Take-profit threshold as % (e.g. 10.0 = 10%). Default 0.0 (disabled).
    position_size_pct : float
        Fraction of capital to allocate per trade (1.0 = 100%).
        Default 1.0.
    walk_forward : bool
        If True, run rolling walk-forward validation instead of a single
        backtest. See walk_train_days / walk_test_days.
    walk_train_days : int
        Length of the training window for walk-forward (default 60).
    walk_test_days : int
        Length of the testing window for walk-forward (default 20).
    **strategy_kwargs
        Additional keyword arguments forwarded to the strategy function
        (e.g. buy_threshold, sell_threshold, hold_days).

    Returns
    -------
    BacktestResult
        Aggregated result across all windows if walk_forward=True,
        otherwise a single-window result.
    """
    prices = fetch_prices(ticker, days * 2)  # extra buffer for lookback
    if not prices:
        return BacktestResult(ticker, [], [], trading_days=0)

    if scan_history is None:
        # Load from DB — last `days` worth
        conn = _get_db()
        total = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
        if total == 0:
            conn.close()
            return BacktestResult(ticker, [], [], trading_days=0)
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
            return BacktestResult(ticker, [], [], trading_days=0)

    strategy_fn = STRATEGIES.get(strategy)
    if not strategy_fn:
        raise ValueError(
            f"Unknown strategy: {strategy}. Available: {list(STRATEGIES.keys())}"
        )

    # Walk-forward validation
    if walk_forward:
        return _run_walk_forward(
            ticker=ticker,
            prices=prices,
            scan_history=scan_history,
            strategy_fn=strategy_fn,
            days=days,
            commission=commission,
            slippage_entry_pct=slippage_entry_pct,
            slippage_exit_pct=slippage_exit_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            position_size_pct=position_size_pct,
            walk_train_days=walk_train_days,
            walk_test_days=walk_test_days,
            **strategy_kwargs,
        )

    # Single backtest
    return strategy_fn(
        ticker=ticker,
        prices=prices,
        scan_history=scan_history,
        days=days,
        commission=commission,
        slippage_entry_pct=slippage_entry_pct,
        slippage_exit_pct=slippage_exit_pct,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        position_size_pct=position_size_pct,
        **strategy_kwargs,
    )


def _run_walk_forward(
    ticker: str,
    prices: list[dict],
    scan_history: list[dict],
    strategy_fn,
    days: int,
    commission: float,
    slippage_entry_pct: float,
    slippage_exit_pct: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    position_size_pct: float,
    walk_train_days: int,
    walk_test_days: int,
    **strategy_kwargs,
) -> BacktestResult:
    """Run walk-forward validation over rolling train/test windows.

    Uses only the price slice relevant to the test window for the
    strategy scan (since the strategy needs prices for the evaluation
    period). The full scan_history is passed through since the strategy
    looks up signals by date.

    All test-window trades are pooled into a single BacktestResult.
    """
    all_trades: list[dict] = []
    all_signals: list[dict] = []
    total_commission = 0.0

    # Build a date-to-index map for the full price series
    # We need to find which prices rows belong to each window
    full_dates = [p["date"] for p in prices]
    {d: i for i, d in enumerate(full_dates)}

    # We want to slide a test window of walk_test_days across the data.
    # Each window has walk_train_days of history before it.
    # The earliest valid test start is after walk_train_days of data.
    n = len(prices)
    earliest_test_start = walk_train_days  # index

    if earliest_test_start >= n:
        return BacktestResult(
            ticker, [], [],
            total_commission=0.0,
            position_size_pct=position_size_pct,
            trading_days=0,
        )

    test_start = earliest_test_start
    window_count = 0

    while test_start < n:
        test_end = min(test_start + walk_test_days, n)

        # The strategy needs:
        # - prices for the test window (+ some buffer for hold periods)
        # - scan_history for the test window dates
        prices[test_start:test_end]
        # Extend prices slightly to account for HOLD_DAYS exits
        hold_buffer = 10  # extra days for hold period exits
        end_idx = min(test_end + hold_buffer, n)
        test_prices_extended = prices[test_start:end_idx]

        # Filter scan_history to test window dates
        test_date_set = set(d["date"] for d in test_prices_extended)
        test_scan = [
            s for s in scan_history
            if s.get("date", "") in test_date_set
        ]

        result = strategy_fn(
            ticker=ticker,
            prices=test_prices_extended,
            scan_history=test_scan,
            days=days,
            commission=commission,
            slippage_entry_pct=slippage_entry_pct,
            slippage_exit_pct=slippage_exit_pct,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            position_size_pct=position_size_pct,
            **strategy_kwargs,
        )
        all_trades.extend(result.trades)
        all_signals.extend(result.signals)
        total_commission += result.total_commission
        window_count += 1

        test_start = test_end  # contiguous windows (no overlap)

    if window_count == 0:
        return BacktestResult(
            ticker, [], [],
            total_commission=0.0,
            position_size_pct=position_size_pct,
            trading_days=0,
        )

    # Total trading days = sum of test window sizes
    total_trading_days = sum(
        len(prices[test_start:test_start + walk_test_days])
        for test_start in range(earliest_test_start, n, walk_test_days)
    )

    return BacktestResult(
        ticker, all_trades, all_signals,
        total_commission=total_commission,
        position_size_pct=position_size_pct,
        trading_days=total_trading_days,
    )


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

    # Transaction costs
    parser.add_argument("--commission", type=float, default=0.001,
                        help="Commission rate per trade (default: 0.001 = 0.1%%)")
    parser.add_argument("--slippage-entry", type=float, default=0.0005,
                        help="Slippage on entry as fraction (default: 0.0005 = 0.05%%)")
    parser.add_argument("--slippage-exit", type=float, default=0.0005,
                        help="Slippage on exit as fraction (default: 0.0005 = 0.05%%)")

    # Stop-loss / take-profit
    parser.add_argument("--stop-loss", type=float, default=0.0,
                        help="Stop-loss threshold in %% (0 = disabled, e.g. 5.0 = 5%%)")
    parser.add_argument("--take-profit", type=float, default=0.0,
                        help="Take-profit threshold in %% (0 = disabled, e.g. 10.0 = 10%%)")

    # Position sizing
    parser.add_argument("--position-size", type=float, default=1.0,
                        help="Position size as fraction of capital (default: 1.0 = 100%%)")

    # Walk-forward validation
    parser.add_argument("--walk-forward", action="store_true",
                        help="Enable walk-forward validation")
    parser.add_argument("--walk-train", type=int, default=60,
                        help="Walk-forward training window in days (default: 60)")
    parser.add_argument("--walk-test", type=int, default=20,
                        help="Walk-forward test window in days (default: 20)")

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
        mode = "walk-forward" if args.walk_forward else "single"
        print(f"🔍 Backtesting {ticker}... ({args.days}d, {args.strategy}, {mode})")
        try:
            result = run_backtest(
                ticker,
                args.days,
                args.strategy,
                scan_history=None,
                commission=args.commission,
                slippage_entry_pct=args.slippage_entry,
                slippage_exit_pct=args.slippage_exit,
                stop_loss_pct=args.stop_loss,
                take_profit_pct=args.take_profit,
                position_size_pct=args.position_size,
                walk_forward=args.walk_forward,
                walk_train_days=args.walk_train,
                walk_test_days=args.walk_test,
                buy_threshold=args.buy_threshold,
                sell_threshold=args.sell_threshold,
                hold_days=args.hold_days,
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
                    "annualized_return": round(result.annualized_return, 2),
                    "sortino_ratio": round(result.sortino_ratio, 2),
                    "avg_holding_days": round(result.avg_holding_days, 1),
                    "total_commission": round(result.total_commission, 2),
                    "trades": len(result.trades),
                }
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append(BacktestResult(ticker, [], [], trading_days=0))

    # Summary table
    if not args.json and results:
        print("\n" + "=" * 60)
        print(f"{'Ticker':<12} {'Return':>10} {'Ann. Ret':>10} {'Win %':>8} "
              f"{'Max DD':>10} {'Sharpe':>8} {'Sortino':>8} {'Trades':>7}")
        print("-" * 60)
        for r in results:
            print(
                f"{r.ticker:<12} {r.total_return:+9.1f}% {r.annualized_return:+9.1f}% "
                f"{r.win_rate:>7.0f}% {r.max_drawdown:>9.1f}% "
                f"{r.sharpe_ratio:>7.2f} {r.sortino_ratio:>7.2f} {len(r.trades):>6}"
            )
        print("=" * 60)

    if args.json and results:
        print(json.dumps([getattr(r, "_data", {}) for r in results], indent=2))


if __name__ == "__main__":
    main()
