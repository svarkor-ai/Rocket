"""FastAPI REST API for Stock Scan Pro."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..scan_engine.engine import SignalEngine
from ..scan_engine.storage import SignalStorage
from ..technical.models import Signal, SignalCategory

logger = logging.getLogger(__name__)

# Dedicated JSON file for subscriptions (separate from signal_states SQLite)
_SUBSCRIPTIONS_FILE = Path("subscriptions.json")


# ── Pydantic schemas ────────────────────────────────────────────────────────


class SignalResponse(BaseModel):
    """Single signal result returned by the API."""
    ticker: str
    signal: str            # "BUY" / "SELL" / "HOLD"
    score: float           # 0.0 – 1.0
    category: str          # "momentum" / "trend" / "volatility" / "volume"
    reason: str
    timestamp: str         # ISO-8601 UTC


class SubscribeRequest(BaseModel):
    chat_id: int
    ticker: str


class SubscriptionResponse(BaseModel):
    chat_id: int
    ticker: str


class ScanRequest(BaseModel):
    ticker: str
    region: str = "usa"
    timeframe: str = "daily"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _load_subscriptions() -> dict[int, list[str]]:
    """Load {chat_id: [ticker, ...]} from the subscriptions JSON file."""
    if not _SUBSCRIPTIONS_FILE.exists():
        return {}
    try:
        with open(_SUBSCRIPTIONS_FILE) as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}
    except (json.JSONDecodeError, ValueError):
        return {}


def _save_subscriptions(data: dict[int, list[str]]) -> None:
    """Persist {chat_id: [ticker, ...]} to disk."""
    with open(_SUBSCRIPTIONS_FILE, "w") as f:
        json.dump({str(k): v for k, v in data.items()}, f, indent=2)


# ── App factory ─────────────────────────────────────────────────────────────


def create_app(
    engine: Optional[SignalEngine] = None,
    storage: Optional[SignalStorage] = None,
) -> FastAPI:
    """Build and configure the FastAPI application.

    If *engine* and *storage* are not provided, the factory creates default
    instances.  Dependency injection of pre-wired instances is recommended
    for production.
    """

    if engine is None or storage is None:
        storage = storage or SignalStorage("stock_scan_pro.db")
        engine = engine or SignalEngine(storage, config={
            "min_score": 0.5,
            "require_change": False,
            "cooldown_minutes": 1,
        })

    app = FastAPI(title="Stock Scan Pro", version="0.1.0")

    # CORS — allow any origin for Telegram bot web-app integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach shared instances for direct endpoint access
    app.state.engine = engine
    app.state.storage = storage

    # ── Routes ────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> dict:
        """Health check — returns {"status": "ok"}."""
        return {"status": "ok"}

    # -- /signals ------------------------------------------------------------

    @app.get("/signals", response_model=list[SignalResponse])
    async def get_signals(
        ticker: Optional[str] = Query(None, description="Filter by single ticker"),
        region: Optional[str] = Query(None, description="Filter by region key (e.g. 'usa')"),
        min_score: Optional[float] = Query(
            None, ge=0.0, le=1.0, description="Minimum score (0.0–1.0)"
        ),
    ) -> list[SignalResponse]:
        """Return current signals, optionally filtered."""
        storage: SignalStorage = app.state.storage

        states = storage.get_all_states()

        # Filter by ticker (uppercase comparison)
        if ticker is not None:
            states = [s for s in states if s.ticker.upper() == ticker.upper()]

        # region filter: pass-through placeholder
        # (region metadata not stored in signal_states; would require universe lookup)

        # Filter by min_score (state.score is [-1, 1]; normalize to [0, 1])
        if min_score is not None:
            states = [s for s in states if (s.score + 1.0) / 2.0 >= min_score]

        results: list[SignalResponse] = []
        for st in states:
            norm = (st.score + 1.0) / 2.0
            results.append(SignalResponse(
                ticker=st.ticker,
                signal=st.signal.value,
                score=round(norm, 4),
                category=st.category.value,
                reason="",  # reason only available at event emission time
                timestamp=st.updated_at.isoformat(),
            ))
        return results

    # -- /scan ---------------------------------------------------------------

    @app.post("/scan", response_model=Optional[SignalResponse])
    async def scan_ticker(req: ScanRequest) -> Optional[SignalResponse]:
        """Trigger a scan for one ticker and return the resulting signal event."""
        engine: SignalEngine = app.state.engine

        event = engine.scan_ticker(req.ticker.upper(), timeframe=req.timeframe)
        if event is None:
            return None

        return SignalResponse(
            ticker=event.ticker,
            signal=event.new_signal.value,
            score=event.score,
            category=event.category.value,
            reason=event.reason,
            timestamp=event.timestamp.isoformat(),
        )

    # -- /ticker/{ticker} ───────────────────────────────────────────────────

    @app.get("/ticker/{ticker}", response_model=SignalResponse)
    async def get_ticker(ticker: str) -> SignalResponse:
        """Return the latest signal state for a single ticker."""
        storage: SignalStorage = app.state.storage

        state = storage.get_signal_state(ticker.upper())
        if state is None:
            raise HTTPException(status_code=404, detail=f"No signal found for {ticker}")

        norm = (state.score + 1.0) / 2.0
        return SignalResponse(
            ticker=state.ticker,
            signal=state.signal.value,
            score=round(norm, 4),
            category=state.category.value,
            reason="",
            timestamp=state.updated_at.isoformat(),
        )

    # -- /subscriptions (list + add + remove) ───────────────────────────────

    @app.get("/subscriptions/{chat_id}", response_model=list[SubscriptionResponse])
    async def list_subscriptions(chat_id: int) -> list[SubscriptionResponse]:
        """Return all ticker subscriptions for a given chat_id."""
        data = _load_subscriptions()
        tickers = data.get(chat_id, [])
        return [SubscriptionResponse(chat_id=chat_id, ticker=t) for t in tickers]

    @app.post("/subscriptions", response_model=SubscriptionResponse)
    async def add_subscription(req: SubscribeRequest) -> SubscriptionResponse:
        """Add a new subscription (chat_id + ticker)."""
        data = _load_subscriptions()
        tickers = data.setdefault(req.chat_id, [])
        ticker_upper = req.ticker.upper()
        if ticker_upper not in tickers:
            tickers.append(ticker_upper)
        _save_subscriptions(data)

        return SubscriptionResponse(chat_id=req.chat_id, ticker=ticker_upper)

    @app.delete("/subscriptions/{chat_id}/{ticker}")
    async def remove_subscription(
        chat_id: int, ticker: str
    ) -> dict:
        """Remove a subscription."""
        data = _load_subscriptions()
        ticker_upper = ticker.upper()
        tickers = data.get(chat_id, [])
        if ticker_upper in tickers:
            tickers.remove(ticker_upper)
        _save_subscriptions(data)

        return {"status": "deleted"}

    return app
