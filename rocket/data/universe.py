"""Universe — ticker provider for the rocket stock scanner.

Primary source: dynamic builder (universe_builder) which fetches
30 k+ tickers from yfinance indices with 12-hour caching.

Fallback: static list (universe_static) used only when yfinance
fetch fails or the cache is stale.

Public API
----------
get_universe() -> dict[str, list[str]]
    Returns {"usa": [...], "sweden": [...], "china": [...],
             "india": [...], "international": [...]}.

get_universe_count() -> dict[str, int]
    Returns region → ticker count for the current universe.
"""

from .universe_builder import get_universe, get_universe_count

__all__ = ["get_universe", "get_universe_count"]
