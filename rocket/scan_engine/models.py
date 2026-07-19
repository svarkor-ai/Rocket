"""Data models for the Signal Engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..technical.models import Signal, SignalCategory


@dataclass
class SignalEvent:
    """Emitted when a signal change (or new signal) is detected."""
    ticker: str
    prev_signal: Signal
    new_signal: Signal
    score: float
    category: SignalCategory
    reason: str           # human-readable explanation
    timestamp: datetime
    timeframe: str        # "daily" or "intraday"


@dataclass
class SignalState:
    """Persistent state for a single ticker — used for change detection."""
    ticker: str
    signal: Signal
    score: float
    category: SignalCategory
    updated_at: datetime
