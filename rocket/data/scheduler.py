"""Data update scheduler — fetch → save loop."""
import time
import logging
from typing import Dict, List

from .fetcher import fetch_ohlcv
from .storage import save_ohlcv, needs_update
from .universe import get_all_universes

logger = logging.getLogger(__name__)


def run_update_cycle(
    data_dir: str,
    regions: List[str] = None,
    max_age_days: int = 1,
    delay_sec: float = 1.0
) -> Dict[str, int]:
    """Fetch and save data for each region. Returns counts per region."""
    all_universes = get_all_universes()
    if regions is None:
        regions = list(all_universes.keys())

    counts = {}
    for region in regions:
        tickers = all_universes.get(region, [])
        if not tickers:
            continue
        to_fetch = [t for t in tickers if needs_update(data_dir, t, max_age_days)]
        if not to_fetch:
            counts[region] = 0
            logger.info(f"[{region}] All data up-to-date ({len(tickers)} tickers)")
            continue

        logger.info(f"[{region}] Updating {len(to_fetch)}/{len(tickers)} tickers")
        result = fetch_ohlcv(to_fetch)
        saved = 0
        for ticker, df in result.items():
            try:
                save_ohlcv(ticker, df, base_dir=data_dir)
                saved += 1
            except Exception:
                logger.error(f"Failed to save {ticker}")
        counts[region] = saved
        time.sleep(delay_sec)

    return counts


def run_cron(data_dir: str, regions: List[str] = None, interval_min: int = 60):
    """Run update_cycle every interval_min minutes (blocking)."""
    logger.info(f"Cron started: interval={interval_min}min")
    while True:
        try:
            counts = run_update_cycle(data_dir, regions)
            logger.info(f"Cron cycle done: {counts}")
        except Exception:
            logger.error("Cron cycle failed")
        time.sleep(interval_min * 60)
