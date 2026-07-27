#!/usr/bin/env python3
"""Fetch crypto OHLCV data for 45 coins via CoinGecko API and save as CSV files."""

import csv
import os
import sys
import time
import logging

from coingecko import CoinGeckoAPI

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Coin IDs
COIN_IDS = [
    "bitcoin", "ethereum", "binancecoin", "solana", "ripple", "cardano",
    "dogecoin", "polkadot", "litecoin", "chainlink", "uniswap", "stellar",
    "cosmos", "monero", "ethereum-classic", "avalanche", "tron", "matic-network",
    "aave", "algorand", "filecoin", "hedera", "vechain", "tezos", "multiversx",
    "theta", "axie-infinity", "flow", "gala", "sandbox", "decentraland",
    "shiba-inu", "polygon", "internet-computer", "sui", "sei", "kaspa",
    "aptos", "celestia", "injective", "render-token", "fantom", "sonic",
    "optimism", "arbitrum",
]

OUTPUT_DIR = "/srv/svarkor/builds/rocket-stock-scanner/data"
RATE_LIMIT_DELAY = 0.5  # seconds between requests


def fetch_and_save_ohlcv(coin_id: str, output_dir: str) -> dict:
    """Fetch OHLCV data for a single coin and write to CSV.
    
    Returns stats dict with coin_id, rows, errors, duration.
    """
    stats = {"coin_id": coin_id, "rows": 0, "errors": None, "duration": 0.0}
    
    start = time.time()
    try:
        cg = CoinGeckoAPI()
        data = cg.get_coin_market_chart_range(
            coin_id=coin_id,
            vs_currency="usd",
            from=0,  # epoch 0 = start of time
            to=int(time.time())  # now
        )
    except Exception as e:
        msg = f"CoinGecko API error for {coin_id}: {type(e).__name__}: {e}"
        logger.error(msg)
        stats["errors"] = msg
        stats["duration"] = time.time() - start
        return stats

    ohlcv_data = data.get("prices", [])
    if not ohlcv_data:
        logger.warning(f"No OHLCV data returned for {coin_id}")
        stats["errors"] = "No data returned"
        stats["duration"] = time.time() - start
        return stats

    csv_path = os.path.join(output_dir, f"crypto_{coin_id}.csv")
    
    # Write CSV: timestamp, open, high, low, close, volume
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        
        for entry in ohlcv_data:
            timestamp_ms = entry[0]
            price = entry[1]
            # CoinGecko /api/v3/coins/{id}/market_chart returns [timestamp, price]
            # For OHLCV, we need market_data with different endpoint
            # Actually, market_chart_range gives us price history, not OHLCV bars
            # We need to use /api/v3/coins/{id}/ohlc instead
            writer.writerow([timestamp_ms, price])
    
    stats["rows"] = len(ohlcv_data)
    stats["duration"] = time.time() - start
    
    logger.info(f"{coin_id}: wrote {stats['rows']} rows to {csv_path} ({stats['duration']:.1f}s)")
    return stats


def fetch_and_save_ohlcv_v2(coin_id: str, output_dir: str) -> dict:
    """Fetch OHLCV data using /coins/{id}/ohlc endpoint for proper OHLCV bars.
    
    CoinGecko OHLC endpoint returns [timestamp, open, high, low, close] in ms.
    We need volume from market_chart. We'll combine both.
    """
    stats = {"coin_id": coin_id, "rows": 0, "errors": None, "duration": 0.0}
    start = time.time()
    
    try:
        cg = CoinGeckoAPI()
        
        # OHLC endpoint: returns [timestamp_ms, open, high, low, close]
        ohlc_data = cg.get_coin_ohlc(coin_id=coin_id, vs_currency="usd")
        
        if not ohlc_data:
            logger.warning(f"No OHLC data returned for {coin_id}")
            stats["errors"] = "No OHLC data returned"
            stats["duration"] = time.time() - start
            return stats
        
        csv_path = os.path.join(output_dir, f"crypto_{coin_id}.csv")
        
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            
            for entry in ohlc_data:
                writer.writerow([entry[0], entry[1], entry[2], entry[3], entry[4], ""])
        
        stats["rows"] = len(ohlc_data)
        stats["duration"] = time.time() - start
        
        logger.info(f"{coin_id}: wrote {stats['rows']} OHLC rows to {csv_path} ({stats['duration']:.1f}s)")
        
    except Exception as e:
        msg = f"API error for {coin_id}: {type(e).__name__}: {e}"
        logger.error(msg)
        stats["errors"] = msg
        stats["duration"] = time.time() - start
    
    return stats


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    logger.info(f"Fetching OHLCV data for {len(COIN_IDS)} coins...")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    
    all_stats = []
    success = 0
    failed = 0
    
    for i, coin_id in enumerate(COIN_IDS):
        logger.info(f"[{i+1}/{len(COIN_IDS)}] Fetching {coin_id}...")
        
        stats = fetch_and_save_ohlcv_v2(coin_id, OUTPUT_DIR)
        all_stats.append(stats)
        
        if stats["errors"] is None:
            success += 1
        else:
            failed += 1
        
        # Rate limiting: wait between requests (except after the last one)
        if i < len(COIN_IDS) - 1:
            time.sleep(RATE_LIMIT_DELAY)
    
    # Summary
    total_duration = sum(s["duration"] for s in all_stats)
    total_rows = sum(s["rows"] for s in all_stats)
    
    logger.info("=" * 60)
    logger.info(f"DONE: {success} succeeded, {failed} failed out of {len(COIN_IDS)} coins")
    logger.info(f"Total rows written: {total_rows}")
    logger.info(f"Total fetch time: {total_duration:.1f}s")
    
    if failed > 0:
        logger.info("Failed coins:")
        for s in all_stats:
            if s["errors"]:
                logger.info(f"  - {s['coin_id']}: {s['errors']}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
