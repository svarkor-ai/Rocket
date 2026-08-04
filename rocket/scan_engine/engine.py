"""Scan engine — orchestrates universe fetching and scanning."""

from rocket.data import universe
from rocket.scan_engine.models import TickerInfo


def get_universe_tickers() -> dict[str, list[str]]:
    """Return the full ticker universe from the universe module."""
    return universe.get_universe()


def build_ticker_infos(region: str, tickers: list[str]) -> list[TickerInfo]:
    """Build TickerInfo objects for a region's tickers."""
    return [TickerInfo(ticker=t, region=region) for t in tickers]


def scan() -> None:
    """Entry-point: load universe and print summary."""
    uv = get_universe_tickers()
    for region, tickers in uv.items():
        print(f"  {region}: {len(tickers)} tickers")
    total = sum(len(t) for t in uv.values())
    print(f"  TOTAL: {total} tickers")
