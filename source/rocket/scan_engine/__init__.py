"""Signal Engine — scan tickers, detect signal changes, persist state."""
from .models import SignalEvent, SignalState
from .storage import SignalStorage
from .engine import SignalEngine

__all__ = ["SignalEvent", "SignalState", "SignalStorage", "SignalEngine"]
