"""SQLite-backed SignalStorage — persist ticker signal states."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from .models import SignalState
from ..technical.models import Signal, SignalCategory, SignalStrength

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_states (
    ticker      TEXT PRIMARY KEY,
    signal      TEXT    NOT NULL,
    score       REAL    NOT NULL,
    category    TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    strength    TEXT    NOT NULL DEFAULT 'Hold'
);

CREATE TABLE IF NOT EXISTS scan_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    ticker      TEXT    NOT NULL,
    signal      TEXT    NOT NULL,
    score       REAL    NOT NULL,
    category    TEXT    NOT NULL,
    buy_count   INTEGER NOT NULL DEFAULT 0,
    sell_count  INTEGER NOT NULL DEFAULT 0,
    reason      TEXT,
    strength    TEXT    NOT NULL DEFAULT 'Hold'
);
"""


class SignalStorage:
    """Minimal SQLite store for SignalState records."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- public API ----------------------------------------------------------

    def save_signal_state(self, state: SignalState) -> None:
        """Upsert the latest signal for *ticker*."""
        self._conn.execute(
            """
            INSERT INTO signal_states (ticker, signal, score, category, updated_at, strength)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                signal      = excluded.signal,
                score       = excluded.score,
                category    = excluded.category,
                updated_at  = excluded.updated_at,
                strength    = excluded.strength
            """,
            (
                state.ticker,
                state.signal.value,
                state.score,
                state.category.value,
                state.updated_at.isoformat(),
                state.strength.value,
            ),
        )
        self._conn.commit()

    def save_scan_history(self, records: list[dict]) -> None:
        """Bulk-insert scan history records.

        Each record is a dict with keys:
            timestamp, ticker, signal, score, category, buy_count, sell_count, reason
        """
        self._conn.executemany(
            """
            INSERT INTO scan_history
                (timestamp, ticker, signal, score, category, buy_count, sell_count, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["timestamp"],
                    r["ticker"],
                    r["signal"],
                    r["score"],
                    r["category"],
                    r["buy_count"],
                    r["sell_count"],
                    r["reason"],
                )
                for r in records
            ],
        )
        self._conn.commit()

    def get_top_signals(self, limit: int = 10) -> list[tuple]:
        """Return the top *limit* signals from the most recent scan by score."""
        return self._conn.execute(
            """
            SELECT ticker, signal, score, category, buy_count, sell_count, reason
            FROM scan_history
            WHERE timestamp = (
                SELECT MAX(timestamp) FROM scan_history
            )
            ORDER BY score DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def get_last_scan_timestamp(self) -> Optional[str]:
        """Return the timestamp of the most recent scan, or None."""
        row = self._conn.execute(
            "SELECT MAX(timestamp) FROM scan_history"
        ).fetchone()
        return row[0] if row else None

    def get_signal_state(self, ticker: str) -> Optional[SignalState]:
        """Return the current state for *ticker*, or None."""
        row = self._conn.execute(
            "SELECT ticker, signal, score, category, updated_at, strength FROM signal_states WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if row is None:
            return None
        return SignalState(
            ticker=row[0],
            signal=Signal(row[1]),
            score=float(row[2]),
            category=SignalCategory(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            strength=SignalStrength(row[5]),
        )

    def get_all_states(self) -> list[SignalState]:
        """Return every tracked ticker state."""
        rows = self._conn.execute(
            "SELECT ticker, signal, score, category, updated_at, strength FROM signal_states ORDER BY ticker"
        ).fetchall()
        return [
            SignalState(
                ticker=r[0], signal=Signal(r[1]), score=float(r[2]),
                category=SignalCategory(r[3]),
                updated_at=datetime.fromisoformat(r[4]),
                strength=SignalStrength(r[5]),
            )
            for r in rows
        ]

    def get_all_subscriptions(self) -> list[SignalState]:
        """Alias for get_all_states — human-friendly name."""
        return self.get_all_states()

    def clear_signal_state(self, ticker: str) -> None:
        """Remove a ticker from tracking."""
        self._conn.execute("DELETE FROM signal_states WHERE ticker = ?", (ticker,))
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
