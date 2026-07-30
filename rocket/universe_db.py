"""UniverseDB — Load and query ticker metadata from universe_cache.json.

Usage:
    db = UniverseDB()
    tickers = db.get_tickers(regions=["usa", "sweden"], limit=10)
    counts = db.count_by_region()
    db.save_enriched()  # saves to rocket/data/universe_enriched.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Region-to-exchange mapping for common regions
REGION_EXCHANGE: dict[str, str] = {
    "usa": "NYSE/NASDAQ",
    "sweden": "STO",
    "uk": "LSE",
    "germany": "XETRA",
    "france": "Euronext Paris",
    "japan": "TSE",
    "china": "SSE/SZSE",
    "india": "NSE/BSE",
    "australia": "ASX",
    "canada": "TSX",
    "brazil": "BOVESPA",
    "korea": "KRX",
    "singapore": "SGX",
    "switzerland": "SIX",
}


class UniverseDB:
    """Load and query ticker metadata from universe_cache.json.

    The cache file contains tickers organized by region (dict[str, list[str]]).
    Each entry has ticker symbol, region, and optional name/market_cap.
    This class enriches the data with exchange info.
    """

    def __init__(self, cache_path: str | None = None) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self._raw: dict[str, list[str]] = {}
        self._enriched: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_path is None:
            self.cache_path = Path(__file__).parent / "data" / "universe_cache.json"

        if not self.cache_path.exists():
            logger.warning("Cache file not found: %s", self.cache_path)
            return

        with open(self.cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Cache structure: {"tickers": {"usa": ["AAPL", ...], "sweden": [...], ...}, ...}
        raw_tickers = data.get("tickers", {})
        if not isinstance(raw_tickers, dict):
            logger.warning("Cache 'tickers' is not a dict: %s", type(raw_tickers))
            self._raw = {}
            return

        self._raw = raw_tickers

        # Build enriched dict: {ticker: {region, exchange, name, market_cap}}
        for region, ticker_list in raw_tickers.items():
            if not isinstance(ticker_list, list):
                continue
            for ticker in ticker_list:
                if not isinstance(ticker, str):
                    continue
                if ticker not in self._enriched:  # First region wins (dedup)
                    self._enriched[ticker] = {
                        "ticker": ticker,
                        "region": region,
                        "exchange": REGION_EXCHANGE.get(region, "unknown"),
                        "name": "",
                        "market_cap": 0.0,
                    }

    def get_tickers(
        self,
        regions: list[str] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return up to `limit` tickers filtered by `regions`.

        Args:
            regions: Filter by region names (e.g. ["usa", "sweden"]).
                     If None, returns all regions.
            limit: Maximum number of tickers to return.

        Returns:
            List of ticker dicts with ticker, region, exchange, name, market_cap.
        """
        results = []
        for ticker, info in self._enriched.items():
            if regions and info.get("region") not in regions:
                continue
            results.append(info)
            if len(results) >= limit:
                break
        return results

    def get_ticker_info(self, ticker: str) -> dict[str, Any]:
        """Return metadata for a single ticker, or empty dict if not found."""
        return self._enriched.get(ticker, {})

    def count_by_region(self) -> dict[str, int]:
        """Return dict mapping region names to ticker counts."""
        counts: dict[str, int] = {}
        for region in self._raw:
            ticker_list = self._raw.get(region, [])
            if isinstance(ticker_list, list):
                counts[region] = len(ticker_list)
        return counts

    def get_universe_list(self) -> list[str]:
        """Return list of all ticker symbols as strings."""
        return list(self._enriched.keys())

    def save_enriched(self, output_path: str | None = None) -> int:
        """Save enriched ticker data to JSON.

        Returns:
            Number of unique tickers written.
        """
        out = output_path or str(
            Path(__file__).parent / "data" / "universe_enriched.json"
        )
        Path(out).parent.mkdir(parents=True, exist_ok=True)

        with open(out, "w", encoding="utf-8") as f:
            json.dump(self._enriched, f, indent=2, ensure_ascii=False)

        logger.info("Saved %d enriched tickers to %s", len(self._enriched), out)
        return len(self._enriched)

    def get_all_regions(self) -> list[str]:
        """Return list of all region names."""
        return list(self._raw.keys())

    def __len__(self) -> int:
        return len(self._enriched)

    def __repr__(self) -> str:
        counts = self.count_by_region()
        return (
            f"UniverseDB({len(self._enriched)} tickers, "
            f"{len(counts)} regions)"
        )
