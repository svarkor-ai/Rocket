#!/usr/bin/env python3
"""Fetch crypto OHLCV data for 45 coins via CoinGecko API and save as CSV files.

Uses raw requests to the CoinGecko /api/v3/coins/{id}/ohlc endpoint.
Two-phase approach: phase 1 normal requests with delay, phase 2 retries
only the coins that hit 429.
"""

import csv
import os
import sys
import time
import logging

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Coin IDs mapped to their actual CoinGecko IDs
COIN_ID_MAP = {
    "bitcoin": "bitcoin",
    "ethereum": "ethereum",
    "binancecoin": "binancecoin",
    "solana": "solana",
    "ripple": "ripple",
    "cardano": "cardano",
    "dogecoin": "dogecoin",
    "polkadot": "polkadot",
    "litecoin": "litecoin",
    "chainlink": "chainlink",
    "uniswap": "uniswap",
    "stellar": "stellar",
    "cosmos": "cosmos",
    "monero": "monero",
    "ethereum-classic": "ethereum-classic",
    "avalanche": "avalanche-2",
    "tron": "tron",
    "matic-network": "matic-network",
    "aave": "aave",
    "algorand": "algorand",
    "filecoin": "filecoin",
    "hedera": "hedera-hashgraph",
    "vechain": "vechain",
    "tezos": "tezos",
    "multiversx": "multiversx-egld",
    "theta": "theta-token",
    "axie-infinity": "axie-infinity",
    "flow": "flow",
    "gala": "gala",
    "sandbox": "the-sandbox",
    "decentraland": "decentraland",
    "shiba-inu": "shiba-inu",
    "polygon": "matic-network",
    "internet-computer": "internet-computer",
    "sui": "sui",
    "sei": "sei-network",
    "kaspa": "kaspa",
    "aptos": "aptos",
    "celestia": "celestia",
    "injective": "injective-protocol",
    "render-token": "render-token",
    "fantom": "fantom",
    "sonic": "sonic",
    "optimism": "optimism",
    "arbitrum": "arbitrum",
}

OUTPUT_DIR = "/srv/svarkor/builds/rocket-stock-scanner/data"
BASE_URL = "https://api.coingecko.com/api/v3"
NORMAL_DELAY = 2.0  # between normal requests
RETRY_DELAY = 15.0  # delay before retrying failed coins


def fetch_one(display_id: str, coin_id: str, output_dir: str, attempt: int = 1) -> dict:
    """Fetch OHLC for a single coin. Returns stats dict."""
    stats = {"coin_id": display_id, "rows": 0, "errors": None, "duration": 0.0}
    start = time.time()

    try:
        params = {"vs_currency": "usd", "days": 365}
        url = f"{BASE_URL}/coins/{coin_id}/ohlc"
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            if not data:
                stats["errors"] = "No data returned"
                stats["duration"] = time.time() - start
                return stats

            csv_path = os.path.join(output_dir, f"crypto_{display_id}.csv")
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
                for entry in data:
                    writer.writerow([entry[0], entry[1], entry[2], entry[3], entry[4], ""])

            stats["rows"] = len(data)
            stats["duration"] = time.time() - start
            logger.info(
                f"{display_id} (attempt {attempt}): {stats['rows']} rows -> {csv_path} "
                f"({stats['duration']:.1f}s)"
            )
        elif resp.status_code == 404:
            stats["errors"] = f"Coin '{coin_id}' not found (HTTP 404)"
            stats["duration"] = time.time() - start
        elif resp.status_code == 429:
            stats["errors"] = "Rate limited (429)"
            stats["duration"] = time.time() - start
        else:
            stats["errors"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            stats["duration"] = time.time() - start

    except Exception as e:
        stats["errors"] = f"{type(e).__name__}: {e}"
        stats["duration"] = time.time() - start

    return stats


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    display_ids = list(COIN_ID_MAP.keys())
    total = len(display_ids)
    logger.info(f"Phase 1: Fetching {total} coins (normal delay={NORMAL_DELAY}s)...")

    # Phase 1: initial fetch
    all_stats = []
    failed = []

    for i, display_id in enumerate(display_ids):
        coin_id = COIN_ID_MAP[display_id]
        logger.info(f"[{i + 1}/{total}] {display_id}...")
        stats = fetch_one(display_id, coin_id, OUTPUT_DIR, attempt=1)
        all_stats.append(stats)

        if stats["errors"]:
            failed.append(stats)
        else:
            logger.info(f"  ✓ {stats['rows']} rows")

        if i < total - 1:
            time.sleep(NORMAL_DELAY)

    # Phase 2: retry failed coins
    if failed:
        logger.info(f"\nPhase 2: Retrying {len(failed)} failed coins (delay={RETRY_DELAY}s)...")
        time.sleep(RETRY_DELAY)

        retry_failed = []
        for stats in failed:
            display_id = stats["coin_id"]
            coin_id = COIN_ID_MAP[display_id]
            logger.info(f"[retry] {display_id}...")
            stats = fetch_one(display_id, coin_id, OUTPUT_DIR, attempt=2)
            all_stats[display_ids.index(display_id)] = stats

            if stats["errors"]:
                retry_failed.append(stats)
            else:
                logger.info(f"  ✓ {stats['rows']} rows")

            time.sleep(NORMAL_DELAY)

        # Phase 3: final retry
        if retry_failed:
            logger.info(f"\nPhase 3: Final retry for {len(retry_failed)} coins (delay=30s)...")
            time.sleep(30)

            for stats in retry_failed:
                display_id = stats["coin_id"]
                coin_id = COIN_ID_MAP[display_id]
                logger.info(f"[final] {display_id}...")
                stats = fetch_one(display_id, coin_id, OUTPUT_DIR, attempt=3)
                all_stats[display_ids.index(display_id)] = stats
                time.sleep(NORMAL_DELAY)

    # Summary
    successes = [s for s in all_stats if s["errors"] is None]
    failures = [s for s in all_stats if s["errors"]]
    total_duration = sum(s["duration"] for s in all_stats)
    total_rows = sum(s["rows"] for s in all_stats)

    logger.info("")
    logger.info("=" * 70)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Succeeded: {len(successes)}/{total}")
    logger.info(f"Failed:    {len(failures)}/{total}")
    logger.info(f"Total rows: {total_rows}")
    logger.info(f"Total time: {total_duration:.1f}s")

    if failures:
        logger.info("\nFailed coins:")
        for s in failures:
            logger.info(f"  - {s['coin_id']}: {s['errors']}")

    # List generated files
    logger.info(f"\nCSV files in {OUTPUT_DIR}:")
    csv_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.startswith("crypto_") and f.endswith(".csv")])
    for f in csv_files:
        fpath = os.path.join(OUTPUT_DIR, f)
        size = os.path.getsize(fpath)
        logger.info(f"  {f} ({size:,} bytes)")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
