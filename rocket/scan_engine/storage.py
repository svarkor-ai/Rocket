"""SQLite-backed SignalStorage — persist ticker signal states."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .models import SignalState
from ..technical.models import Signal, SignalCategory

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_states (
    ticker      TEXT PRIMARY KEY,
    signal      TEXT    NOT NULL,
    score       REAL    NOT NULL,
    category    TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""


class SignalStorage:
    """Minimal SQLite store for SignalState records."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    # -- public API ----------------------------------------------------------

    def save_signal_state(self, state: SignalState) -> None:
        """Upsert the latest signal for *ticker*."""
        self._conn.execute(
            """
            INSERT INTO signal_states (ticker, signal, score, category, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                signal      = excluded.signal,
                score       = excluded.score,
                category    = excluded.category,
                updated_at  = excluded.updated_at
            """,
            (
                state.ticker,
                state.signal.value,
                state.score,
                state.category.value,
                state.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_signal_state(self, ticker: str) -> Optional[SignalState]:
        """Return the current state for *ticker*, or None."""
        row = self._conn.execute(
            "SELECT ticker, signal, score, category, updated_at FROM signal_states WHERE ticker = ?",
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
        )

    def get_all_states(self) -> list[SignalState]:
        """Return every tracked ticker state."""
        rows = self._conn.execute(
            "SELECT ticker, signal, score, category, updated_at FROM signal_states ORDER BY ticker"
        ).fetchall()
        return [
            SignalState(
                ticker=r[0], signal=Signal(r[1]), score=float(r[2]),
                category=SignalCategory(r[3]),
                updated_at=datetime.fromisoformat(r[4]),
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
