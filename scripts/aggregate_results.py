"""Aggregate batch scan results and produce the top 10 report.

Usage:
    python scripts/aggregate_results.py [--top 10] [--output results.json]

Reads:
    data/batches/batch_*.json — all batch results
    data/signals.db — SQLite batch results

Outputs:
    results.json — top 10 tickers with full details
    Prints a Telegram-formatted report
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json_results(batches_dir='data/batches'):
    """Load all batch result JSON files."""
    all_results = []
    batch_dir = Path(batches_dir)

    result_files = sorted(batch_dir.glob('batch_*_results.json'))
    print(f"📂 Found {len(result_files)} batch result files")

    for rf in result_files:
        with open(rf) as f:
            data = json.load(f)
        all_results.extend(data)

    return all_results


def load_db_results(db_path='data/signals.db'):
    """Load batch results from SQLite."""
    all_results = []
    db = Path(db_path)

    if not db.exists():
        return all_results, []

    conn = sqlite3.connect(str(db))
    c = conn.cursor()
    c.execute('''SELECT batch_id, ticker, region, score, status, name, sector, price, volume, score_details, scanned_at
                 FROM batch_results ORDER BY score DESC''')
    rows = c.fetchall()
    conn.close()

    for row in rows:
        all_results.append({
            'batch_id': row[0],
            'ticker': row[1],
            'region': row[2],
            'score': row[3],
            'status': row[4],
            'name': row[5],
            'sector': row[6],
            'price': row[7],
            'volume': row[8],
            'score_details': row[9],
            'scanned_at': row[10],
        })

    return all_results, rows


def generate_report(top_tickers, total_scanned, total_scored):
    """Generate a Telegram-formatted report."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    report = f"🚀 **Rocket Scanner — {now}**\n\n"
    report += f"📊 **Total scanned:** {total_scanned}\n"
    report += f"✅ **Scored:** {total_scored}\n\n"
    report += f"🏆 **Top 10:**\n\n"

    for i, t in enumerate(top_tickers, 1):
        score = t['score']
        # Emoji based on score
        if score >= 0.60:
            emoji = "🚀"
            label = "Very Bullish"
        elif score >= 0.20:
            emoji = "📈"
            label = "Bullish"
        elif score >= -0.20:
            emoji = "⚖️"
            label = "Hold"
        elif score >= -0.60:
            emoji = "📉"
            label = "Bearish"
        else:
            emoji = "💀"
            label = "Very Bearish"

        report += f"{emoji} **{i}.** {t['ticker']} ({t['name'] or t['ticker']})\n"
        report += f"    Score: {score:+.4f} [{label}] | Price: ${t['price']:.2f} | {t['sector']}\n\n"

    report += f"---\n_Rocket Scanner v2 — nightly scan_ 🚀"
    return report


def main():
    parser = argparse.ArgumentParser(description="Aggregate batch results → top 10")
    parser.add_argument("--top", type=int, default=10, help="Number of top tickers")
    parser.add_argument("--output", type=str, default="results.json", help="Output file path")
    parser.add_argument("--report", type=str, default="report.txt", help="Report text file")
    args = parser.parse_args()

    print("🔍 Loading batch results...")

    # Load JSON results
    json_results = load_json_results()
    total_from_json = len(json_results)

    # Also load DB (in case JSON files are missing)
    db_results, db_rows = load_db_results()
    total_from_db = len(db_rows)

    print(f"  JSON: {total_from_json} results")
    print(f"  DB: {total_from_db} results")

    # Use whichever source has more data
    if total_from_db > total_from_json:
        all_results = db_results
        print(f"  → Using DB ({total_from_db} results)")
    else:
        # Deduplicate JSON results (same ticker might appear in multiple batches if split overlapped)
        seen = {}
        for r in json_results:
            key = r.get('full_ticker') or r.get('ticker', '')
            if key not in seen or r.get('score', 0) != 0:
                seen[key] = r
        all_results = list(seen.values())
        print(f"  → Using JSON ({len(all_results)} results, deduped)")

    # Filter to scored tickers only
    scored = [r for r in all_results if r.get('status') == 'scored' and r.get('score', 0) != 0]
    total_scanned = len(all_results)

    print(f"\n🏆 Top {args.top} scored tickers:")

    # Sort by score (highest first) and take top N
    scored.sort(key=lambda x: x.get('score', 0), reverse=True)
    top = scored[:args.top]

    # Generate report
    report = generate_report(top, total_scanned, len(scored))

    # Save JSON
    output = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_scanned': total_scanned,
        'total_scored': len(scored),
        'top_tickers': top,
    }
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"💾 Saved to {args.output}")

    # Save report text
    with open(args.report, 'w') as f:
        f.write(report)
    print(f"📝 Saved report to {args.report}")

    # Print report to stdout
    print(f"\n{report}")

    return output


if __name__ == "__main__":
    main()
