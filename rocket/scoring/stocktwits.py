#!/usr/bin/env python3
"""StockTwits sentiment module — uses stocktwitsapi.com (third-party).

Free tier: ~3-4 queries/minute, 7-day lookback, no AI sentiment.
We do our own keyword-based sentiment scoring from raw message text.
"""
import os
from datetime import datetime, timedelta

import requests

def _get_api_key():
    """Lazy-load API key from env or secrets file."""
    key = os.getenv("STOCKTWITS_API_KEY", "")
    if not key:
        try:
            import dotenv
            dotenv.load_dotenv("/home/svarkor/.hermes/.secrets/stocktwits-api.env")
            key = os.getenv("STOCKTWITS_API_KEY", "")
        except Exception:
            pass
    if not key:
        # Also try direct file read as fallback
        try:
            with open("/home/svarkor/.hermes/.secrets/stocktwits-api.env") as f:
                for line in f:
                    if line.startswith("STOCKTWITS_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return key

def _get_base_url():
    """Lazy-load base URL."""
    return os.getenv("STOCKTWITS_API_BASE", "https://api.stocktwitsapi.com/v1")

BULLISH = {"moon", "bull", "long", "buy", "call", "rally", "surge", "rocket",
           "bullish", "uptrend", "breakout", "growth", "strong", "bought",
           "pumping", "green", "up", "gains", "diamond hands", "hodl",
           "🚀", "📈", "💎", "🟢", "accumulate", "loading"}

BEARISH = {"dump", "sell", "short", "put", "crash", "bear", "drop",
           "bearish", "downtrend", "loss", "weak", "overvalued", "bubble",
           "margin call", "selling", "crushing", "red", "down", "losses",
           "bad", "fear", "panic", "📉", "🔴", "💀", "doom", "dead"}


def _score_text(text: str) -> tuple:
    """Score message as (label, strength 0-1)."""
    lower = text.lower()
    bull_count = sum(1 for w in BULLISH if w in lower)
    bear_count = sum(1 for w in BEARISH if w in lower)
    total = bull_count + bear_count
    if total == 0:
        return "neutral", 0.5
    elif bull_count > bear_count:
        return "bullish", bull_count / total
    else:
        return "bearish", bear_count / total


def fetch_messages(symbol: str, days: int = 1, max_retries: int = 2) -> list:
    """Fetch StockTwits messages for a symbol."""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    url = f"{_get_base_url()}/messages"
    params = {
        "symbol": symbol,
        "start": yesterday,
        "end": today,
        "limit": 100,
    }
    api_key = _get_api_key()
    if not api_key:
        print(f"  StockTwits: No API key set, skipping")
        return []
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("messages", [])
            elif resp.status_code == 429:
                wait = min(int(resp.headers.get("Retry-After", "30")), 60)
                if attempt < max_retries:
                    print(f"  Rate limited, waiting {wait}s...")
                    import time
                    time.sleep(wait)
                    continue
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                print(f"  StockTwits error for {symbol}: {e}, retry {attempt+1}/{max_retries}")
                import time
                time.sleep(5)
                continue

    return []


def compute_stocktwits_score(ticker: str, days: int = 1) -> float:
    """Compute StockTwits sentiment score for a ticker.

    Returns:
        float between -1.0 (very bearish) and +1.0 (very bullish)
        0.0 if no messages or API failure
    """
    msgs = fetch_messages(ticker, days)
    if not msgs:
        return 0.0

    bullish = bearish = neutral = 0
    total_weighted = 0.0

    for m in msgs[:100]:
        body = m.get("body", "")
        label, strength = _score_text(body)

        if label == "bullish":
            bullish += 1
            total_weighted += strength
        elif label == "bearish":
            bearish += 1
            total_weighted += (1 - strength)
        else:
            neutral += 1
            total_weighted += 0.5

    analyzed = bullish + bearish + neutral
    if analyzed == 0:
        return 0.0

    avg_sentiment = total_weighted / analyzed
    # Convert 0-1 scale to -1 to +1 scale
    score = (avg_sentiment - 0.5) * 2
    return round(score, 3)
