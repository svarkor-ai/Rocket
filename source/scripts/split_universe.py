"""Split the full universe into batch files for parallel/night scanning.

Usage:
    python scripts/split_universe.py --batch-size 2500 --output-dir data/batches

Outputs:
    data/batches/batch_000.json — 2500 tickers (region, ticker)
    data/batches/batch_001.json — next 2500 tickers
    ...
    data/batches/metadata.json — total tickers, batch size, count
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rocket.data.universe_builder import get_universe  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Split universe into batch files")
    parser.add_argument("--batch-size", type=int, default=2500, help="Tickers per batch")
    parser.add_argument("--output-dir", type=str, default="data/batches", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load full universe
    universe = get_universe()
    tickers = []
    for region, symbols in universe.items():
        for sym in symbols:
            tickers.append({"region": region, "ticker": sym})

    # Filter out invalid entries
    tickers = [t for t in tickers if isinstance(t.get("ticker"), str) and len(t["ticker"]) > 0]

    total = len(tickers)
    print(f"📊 Total tickers: {total}")

    # Split into batches
    batches = []
    for i in range(0, total, args.batch_size):
        batch = tickers[i : i + args.batch_size]
        batches.append(batch)

    # Write batch files
    for idx, batch in enumerate(batches):
        path = output_dir / f"batch_{idx:04d}.json"
        with open(path, "w") as f:
            json.dump(batch, f)
        print(f"  ✅ batch_{idx:04d}.json — {len(batch)} tickers")

    # Write metadata
    meta = {
        "total_tickers": total,
        "batch_size": args.batch_size,
        "num_batches": len(batches),
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n✅ Done: {len(batches)} batches × {args.batch_size} tickers = {total} total")
    return total, len(batches)


if __name__ == "__main__":
    main()
