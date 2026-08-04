#!/usr/bin/env python3
"""Scan all regions and return top meme stocks."""
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, "/home/svarkor/builds/rocket-stock-scanner")

from rocket.data import universe
from rocket.scan_engine.models import TickerInfo
from rocket.scoring.rocket_score import compute_scores


def load_env():
    """Load environment variables from .env files."""
    import dotenv
    dotenv.load_dotenv("/home/svarkor/builds/rocket-stock-scanner/.env")
    dotenv.load_dotenv("/home/svarkor/.hermes/.secrets/rocket.env")


def main():
    load_env()

    regions = ["usa", "sweden", "china", "india"]
    limit = 10
    days = 1

    all_scores = []
    total_tickers = 0

    for region in regions:
        try:
            tickers = universe.get_universe()[region]
        except KeyError:
            print(f"  Region '{region}' not found in universe, skipping")
            continue

        print(f"\n  Scanning {region}: {len(tickers)} tickers...")
        scores = compute_scores(tickers, days)
        all_scores.extend(scores)
        total_tickers += len(tickers)

    # Sort all results and take top N
    all_scores.sort(key=lambda x: -x["score"])
    top = all_scores[:limit]

    print("\n" + "=" * 70)
    print("ROCKET SCANNER — TOP MEME STOCKS")
    print("=" * 70)
    print(f"  Scanned {total_tickers} tickers across {len(regions)} regions")
    print(f"  Top {limit} by composite score (range: -1.0 to +1.0)")
    print(f"  {'Ticker':<10} {'Score':<8} {'Social':<8} {'Volume':<8} {'Momentum':<10} {'Options':<10} {'Price'}")
    print("  " + "-" * 70)
    for item in top:
        score = item["score"]
        emoji = "🚀" if score > 0.3 else ("🔥" if score > 0.1 else ("⚪" if score > 0 else "📉"))
        price = item["details"].get("price")
        price_str = f"${price:,.2f}" if price else "N/A"
        print(f"  {emoji} {item['ticker']:<8} {score:<8.3f} {item['social']:<8.2f} {item['volume']:<8.2f} {item['momentum']:<10.2f} {item['options']:<10.2f} {price_str}")

    # Telegram notification (optional)
    if os.getenv("ROCKET_TELEGRAM_BOT_TOKEN") and os.getenv("ROCKET_TELEGRAM_CHAT_ID"):
        send_telegram(top)

    return top


def send_telegram(top_results: list):
    """Send top results to Telegram."""
    import requests

    bot_token = os.getenv("ROCKET_TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("ROCKET_TELEGRAM_CHAT_ID")

    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"🚀 *Rocket Scanner — {now}*", ""]

    for i, item in enumerate(top_results):
        emoji = "🚀" if item["score"] > 0.3 else ("🔥" if item["score"] > 0.1 else "⚪")
        lines.append(
            f"{emoji} {i+1}. *{item['ticker']}* — Score: {item['score']:.3f}\n"
            f"   Social: {item['social']:.2f} | Volume: {item['volume']:.2f} | "
            f"Momentum: {item['momentum']:.2f} | Options: {item['options']:.2f}"
        )

    message = "\n".join(lines)

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"\n  ✅ Telegram notification sent")
        else:
            print(f"\n  ❌ Telegram send failed: {resp.text}")
    except Exception as e:
        print(f"\n  ❌ Telegram send error: {e}")


if __name__ == "__main__":
    results = main()
