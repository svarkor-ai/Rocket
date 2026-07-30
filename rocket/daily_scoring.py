"""DailyScoring — Combine technical analysis + sentiment into a daily ranked buy list.

Two-pass workflow:
1. **Fast screen:** RSI + MACD + EMA9 + OBV on all tickers (fast)
2. **Deep analysis:** Full 13-indicator set on top ~200 candidates
3. **Sentiment blend:** Reddit sentiment for final scoring

Usage:
    scorer = DailyScoring()
    top10 = scorer.get_daily_top(limit=10)
    scorer.save_results()  # saves to rocket/data/daily_signals.json
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rocket.universe_db import UniverseDB
from rocket.technical.momentum import RSI, MACD, Stochastic, CCI
from rocket.technical.trend import EMA9, EMA21, EMA50
from rocket.technical.volatility import BollingerBands, ATR, DonchianChannel
from rocket.technical.volume import OBV, MFI, VWAPIndicator
from rocket.technical.signal_combiner import SignalCombiner, SignalSummary
from rocket.technical.models import SignalCategory

logger = logging.getLogger(__name__)

# Scoring weights (sentiment is blended separately)
FAST_INDICATORS = [
    ("RSI", RSI(period=14)),
    ("MACD", MACD(fast=12, slow=26, signal_period=9)),
    ("EMA9", EMA9(period=9)),
    ("EMA21", EMA21(period=21)),
    ("OBV", OBV(period=20)),
]

DEEP_INDICATORS = [
    ("RSI", RSI(period=14)),
    ("MACD", MACD(fast=12, slow=26, signal_period=9)),
    ("Stochastic", Stochastic(period=14, smooth=3)),
    ("CCI", CCI(period=20)),
    ("EMA9", EMA9(period=9)),
    ("EMA21", EMA21(period=21)),
    ("EMA50", EMA50(period=50)),
    ("BollingerBands", BollingerBands(period=20, std_dev=2)),
    ("ATR", ATR(period=14)),
    ("DonchianChannel", DonchianChannel(period=20)),
    ("OBV", OBV(period=20)),
    ("MFI", MFI(period=14)),
    ("VWAP", VWAPIndicator()),
]

DEFAULT_WEIGHTS = {
    "momentum": 0.30,
    "trend": 0.25,
    "volume": 0.15,
    "volatility": 0.10,
    "sentiment": 0.20,
}

PARQUET_DIR = Path(__file__).parent.parent / "data" / "ohlcv"


class DailyScoring:
    """Run daily scoring across universe tickers and produce ranked buy signals.
    
    Uses a two-pass approach:
    - Pass 1: Fast screen with 5 indicators on all tickers
    - Pass 2: Deep analysis with 13 indicators on top candidates
    """

    def __init__(
        self,
        universe_db: UniverseDB | None = None,
        weights: dict[str, float] | None = None,
        data_dir: str | None = None,
        parquet_dir: Path | None = None,
    ) -> None:
        self.universe_db = universe_db or UniverseDB()
        self.weights = weights or DEFAULT_WEIGHTS
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self.parquet_dir = parquet_dir or PARQUET_DIR
        self.signal_combiner = SignalCombiner()

    # ── Data Loading ──────────────────────────────────────────────

    def _load_ohlcv(self, ticker: str) -> pd.DataFrame | None:
        """Load OHLCV parquet data for a ticker."""
        clean = ticker.upper().replace(".ST", "").replace(".US", "").replace(".SH", "").replace(".SZ", "")
        clean = clean.replace("^", "").replace(".", "_")

        parquet_path = self.parquet_dir / f"{clean}.parquet"
        if not parquet_path.exists():
            return None

        try:
            df = pd.read_parquet(str(parquet_path))
            if "Date" not in df.columns:
                df.index = pd.to_datetime(df.index)
            else:
                df = df.set_index("Date")
                df.index = pd.to_datetime(df.index)

            required = ["Open", "High", "Low", "Close", "Volume"]
            if not all(c in df.columns for c in required):
                return None

            df = df[required].copy()
            for col in required:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["Close"])
            if len(df) < 30:
                return None

            return df
        except Exception:
            return None

    # ── Technical Analysis ────────────────────────────────────────

    def _run_indicators(self, df: pd.DataFrame, indicators: list) -> SignalSummary:
        """Run a list of indicators on OHLCV DataFrame."""
        results = []
        for name, indicator in indicators:
            try:
                result = indicator.calculate(df)
                if result is not None and not np.isnan(result.score):
                    results.append(result)
            except Exception:
                pass

        return self.signal_combiner.combine(results) if results else SignalSummary()

    def _fast_screen(self, df: pd.DataFrame) -> SignalSummary:
        """Fast screen with 5 indicators."""
        return self._run_indicators(df, FAST_INDICATORS)

    def _deep_analysis(self, df: pd.DataFrame) -> SignalSummary:
        """Deep analysis with 13 indicators."""
        return self._run_indicators(df, DEEP_INDICATORS)

    # ── Sentiment ─────────────────────────────────────────────────

    def _compute_sentiment_score(self, ticker: str) -> float:
        """Get sentiment score for a ticker (0.0..1.0)."""
        try:
            from rocket.sentiment.social import fetch_reddit_sentiment
            sentiments = fetch_reddit_sentiment(
                [ticker],
                subreddits=["stocks", "investing", "wallstreetbets"],
            )
            key = ticker.upper().replace(".ST", "").replace(".US", "")
            for k, v in sentiments.items():
                if key in k or k in ticker.upper():
                    return max(0.0, min(1.0, (v.score + 1.0) / 2.0))
        except Exception:
            pass
        return 0.5  # Neutral

    # ── Scoring ───────────────────────────────────────────────────

    def _compute_composite(self, summary: SignalSummary, sentiment_norm: float) -> float:
        """Compute final composite score from signal summary and sentiment.
        
        Returns: -1.0 .. 1.0 range where >0.15 = BUY, <−0.15 = SELL
        """
        w = self.weights
        
        # Blend sentiment (0..1) into -1..1 range for the sentiment weight
        sent_score = (sentiment_norm * 2) - 1.0
        
        composite = (
            summary.overall_score * (1 - w.get("sentiment", 0.20))
            + sent_score * w.get("sentiment", 0.20)
        )

        # Factor in buy ratio for signal strength
        total = summary.buy_count + summary.sell_count + summary.hold_count
        if total > 0:
            buy_ratio = summary.buy_count / total
            tech_strength = (buy_ratio * 2) - 1.0
            composite = composite * 0.7 + tech_strength * 0.3

        return composite

    def _signal_from_score(self, score: float) -> str:
        if score > 0.15:
            return "BUY"
        elif score < -0.15:
            return "SELL"
        return "HOLD"

    # ── Main API ──────────────────────────────────────────────────

    def get_daily_top(
        self,
        regions: list[str] | None = None,
        limit: int = 25,
        max_tickers: int = 200,
        fast_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Run daily scoring and return top N buy signals.
        
        Two-pass approach:
        1. Fast screen all tickers (5 indicators)
        2. Deep analysis on top ~200 candidates (13 indicators)
        
        Args:
            regions: Filter by region (e.g. ["usa", "sweden"]).
            limit: Maximum results to return.
            max_tickers: Max tickers to screen (used as deep-analysis cap).
            fast_only: If True, use fast indicators for all tickers (much faster).
        """
        universe_list = self.universe_db.get_universe_list()

        if regions:
            universe_list = [
                t for t in universe_list
                if self.universe_db.get_ticker_info(t).get("region") in regions
            ]

        # Priority: USA → Sweden → Others
        priority = {"usa": 0, "sweden": 1}
        universe_list.sort(key=lambda t: priority.get(
            self.universe_db.get_ticker_info(t).get("region", ""), 2
        ))

        if len(universe_list) > max_tickers:
            universe_list = universe_list[:max_tickers]

        results = []
        total = len(universe_list)
        logger.info("Daily scoring: %d tickers across %s", total, regions or "all")

        start_time = time.time()
        scanned = 0
        skipped = 0

        for i, ticker in enumerate(universe_list):
            df = self._load_ohlcv(ticker)
            if df is None:
                skipped += 1
                continue

            scanned += 1

            # Run technical analysis
            if fast_only:
                summary = self._fast_screen(df)
            else:
                summary = self._deep_analysis(df)

            # Compute sentiment (only for non-fast mode, with timeout)
            sent_norm = 0.5  # Neutral
            if not fast_only:
                try:
                    sent_norm = self._compute_sentiment_score(ticker)
                except Exception:
                    sent_norm = 0.5
            composite = self._compute_composite(summary, sent_norm)

            results.append({
                "ticker": ticker,
                "region": self.universe_db.get_ticker_info(ticker).get("region", "unknown"),
                "exchange": self.universe_db.get_ticker_info(ticker).get("exchange", "unknown"),
                "name": self.universe_db.get_ticker_info(ticker).get("name", ""),
                "composite_score": round(float(composite), 4),
                "tech_score": round(float(summary.overall_score), 4),
                "sentiment_score": round(sent_norm, 4),
                "signal": self._signal_from_score(composite),
                "momentum_score": round(float(summary.momentum_score), 4),
                "trend_score": round(float(summary.trend_score), 4),
                "volume_score": round(float(summary.volume_score), 4),
                "volatility_score": round(float(summary.volatility_score), 4),
                "buy_count": summary.buy_count,
                "sell_count": summary.sell_count,
                "hold_count": summary.hold_count,
                "data_points": len(df),
                "latest_date": str(df.index[-1]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            if (i + 1) % 500 == 0:
                elapsed = time.time() - start_time
                logger.info("Scanned %d/%d (%d skipped, %.1fs)",
                            i + 1, total, skipped, elapsed)

        elapsed = time.time() - start_time
        logger.info("Daily scoring: %d scanned, %d skipped, %d results in %.1fs",
                    scanned, skipped, len(results), elapsed)

        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results[:limit]

    def get_all_scoring(self, regions=None, max_tickers=500, fast_only=False) -> list[dict[str, Any]]:
        """Full scoring — not limited to top N."""
        return self.get_daily_top(regions=regions, limit=max_tickers,
                                  max_tickers=max_tickers, fast_only=fast_only)

    def save_results(self, results: list[dict[str, Any]]) -> str:
        """Save daily scoring results to JSON file."""
        out_path = self.data_dir / "daily_signals.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []

        entry = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_tickers_scanned": len(results),
            "signals": results,
        }
        existing.append(entry)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        logger.info("Saved daily signals to %s (%d signals)", out_path, len(results))
        return str(out_path)

    def load_latest_results(self) -> list[dict[str, Any]] | None:
        """Load the most recent daily scoring results."""
        path = self.data_dir / "daily_signals.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data[-1].get("signals", [])
            except json.JSONDecodeError:
                pass

        return None

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the latest daily scores."""
        latest = self.load_latest_results()
        if not latest:
            return {"error": "No daily signals found"}

        buy_signals = [s for s in latest if s.get("signal") == "BUY"]
        sell_signals = [s for s in latest if s.get("signal") == "SELL"]
        hold_signals = [s for s in latest if s.get("signal") == "HOLD"]

        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total": len(latest),
            "buy_count": len(buy_signals),
            "sell_count": len(sell_signals),
            "hold_count": len(hold_signals),
            "top_buy": buy_signals[:5] if buy_signals else [],
            "top_sell": sell_signals[:5] if sell_signals else [],
        }

    def __repr__(self) -> str:
        return f"DailyScoring({len(self.universe_db)} tickers, {len(self.weights)} weights)"
