"""Portfolio — SQLite-based user portfolio management.

Usage:
    portfolio = Portfolio("my_portfolio.db")
    portfolio.add_ticker("AAPL", quantity=10, price=150.0)
    portfolio.remove_ticker("AAPL")
    holdings = portfolio.get_holdings()
    changes = portfolio.detect_signal_changes(portfolio, daily_scores)
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Portfolio:
    """SQLite-based portfolio for user ticker holdings."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).parent / "data" / "portfolio.db"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize portfolio database with required tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    ticker TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    added_date TEXT NOT NULL,
                    added_timestamp TEXT NOT NULL,
                    region TEXT DEFAULT 'unknown',
                    exchange TEXT DEFAULT 'unknown'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    old_signal TEXT NOT NULL,
                    new_signal TEXT NOT NULL,
                    old_score REAL NOT NULL,
                    new_score REAL NOT NULL,
                    detected_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_history_ticker
                ON signal_history(ticker)
            """)
            conn.commit()
        finally:
            conn.close()

    def add_ticker(
        self,
        ticker: str,
        quantity: int,
        price: float,
        region: str = "unknown",
        exchange: str = "unknown",
    ) -> dict[str, Any]:
        """Add or update a ticker in the portfolio.

        If the ticker already exists, the average price is recalculated
        and the quantity is increased.
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT quantity, avg_price FROM holdings WHERE ticker = ?",
                (ticker.upper(),)
            )
            row = cursor.fetchone()

            now = datetime.now(timezone.utc)
            added_timestamp = now.isoformat()

            if row:
                old_qty, old_price = row
                # Weighted average
                total_qty = old_qty + quantity
                avg_price = (old_price * old_qty + price * quantity) / total_qty
                cursor.execute(
                    "UPDATE holdings SET quantity = ?, avg_price = ?, added_date = ?, added_timestamp = ? WHERE ticker = ?",
                    (total_qty, round(avg_price, 2), now.strftime("%Y-%m-%d"), added_timestamp, ticker.upper())
                )
            else:
                cursor.execute(
                    "INSERT INTO holdings (ticker, quantity, avg_price, added_date, added_timestamp, region, exchange) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ticker.upper(), quantity, round(price, 2), now.strftime("%Y-%m-%d"), added_timestamp, region, exchange)
                )

            conn.commit()
            return {
                "ticker": ticker.upper(),
                "quantity": quantity,
                "price": price,
                "added_timestamp": added_timestamp,
            }
        finally:
            conn.close()

    def remove_ticker(self, ticker: str) -> bool:
        """Remove a ticker from the portfolio."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            conn.close()

    def get_holdings(self) -> list[dict[str, Any]]:
        """Return all current holdings."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM holdings ORDER BY ticker")
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_total_value(self, current_prices: dict[str, float]) -> float:
        """Calculate total portfolio value using current prices."""
        holdings = self.get_holdings()
        total = 0.0
        for h in holdings:
            price = current_prices.get(h["ticker"], 0.0)
            total += h["quantity"] * price
        return total

    def get_holding(self, ticker: str) -> dict[str, Any] | None:
        """Get a single holding by ticker."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM holdings WHERE ticker = ?", (ticker.upper(),))
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None
        finally:
            conn.close()

    def record_signal_change(
        self,
        ticker: str,
        old_signal: str,
        new_signal: str,
        old_score: float,
        new_score: float,
    ) -> None:
        """Record a signal change for historical tracking."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO signal_history (ticker, old_signal, new_signal, old_score, new_score, detected_at) VALUES (?, ?, ?, ?, ?, ?)",
                (ticker.upper(), old_signal, new_signal, old_score, new_score, now)
            )
            conn.commit()
        finally:
            conn.close()

    def get_signal_history(
        self,
        ticker: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get signal change history for a ticker or all tickers."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            if ticker:
                cursor.execute(
                    "SELECT * FROM signal_history WHERE ticker = ? ORDER BY detected_at DESC LIMIT ?",
                    (ticker.upper(), limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM signal_history ORDER BY detected_at DESC LIMIT ?",
                    (limit,)
                )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def detect_signal_changes(
        self,
        daily_scores: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect signal changes for portfolio holdings.

        Compares daily_scores with historical signal data and records
        changes. Returns a list of changed signals.
        """
        holdings = self.get_holdings()
        if not holdings:
            return []

        ticker_map = {h["ticker"]: h for h in holdings}
        changes = []

        for score_entry in daily_scores:
            ticker = score_entry.get("ticker", "").upper()
            if ticker not in ticker_map:
                continue

            old_signal = self._get_last_signal(ticker)
            new_signal = score_entry.get("signal", "HOLD")
            new_score = score_entry.get("composite_score", 0)

            if old_signal and old_signal != new_signal:
                old_score = score_entry.get("tech_score", 0)
                self.record_signal_change(
                    ticker=ticker,
                    old_signal=old_signal,
                    new_signal=new_signal,
                    old_score=old_score,
                    new_score=new_score,
                )
                changes.append({
                    "ticker": ticker,
                    "old_signal": old_signal,
                    "new_signal": new_signal,
                    "old_score": old_score,
                    "new_score": new_score,
                    "quantity": ticker_map[ticker]["quantity"],
                })

        return changes

    def _get_last_signal(self, ticker: str) -> str | None:
        """Get the last recorded signal for a ticker."""
        history = self.get_signal_history(ticker=ticker, limit=1)
        if history:
            return history[0].get("new_signal")
        return None

    def clear_history(self) -> int:
        """Clear all signal history. Returns number of deleted rows."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM signal_history")
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()

    def __repr__(self) -> str:
        holdings = self.get_holdings()
        return f"Portfolio({len(holdings)} holdings)"
