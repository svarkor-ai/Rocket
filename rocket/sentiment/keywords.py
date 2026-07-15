"""Keyword-based sentiment analysis for news articles."""
import re
from typing import List, Tuple
from .models import NewsArticle, SentimentScore

# Positive and negative keywords (case-insensitive matching)
POSITIVE_KEYWORDS = [
    "growth", "beat", "upgrade", "bullish", "tillväxt", "ökade", "uppgång",
    "revenue", "profit", "gain", "strong", "outperform", "rally",
    "optimistic", "record", "surge", "momentum", "breakout",
    "expansion", "innovation", "acquisition", "partnership", "dividend",
    "increase", "rises", "surpasses", "exceeds", "positive",
    "tillväxt", "tillväxt", "ökade", "uppgång", "rekord",
    "bullish", "strong", "outperform", "rally",
]

NEGATIVE_KEYWORDS = [
    "loss", "downgrade", "bearish", "nedgång", "förlust", "kritik",
    "decline", "drop", "crash", "weak", "underperform", "sell-off",
    "pessimistic", "miss", "layoff", "bankruptcy", "recession",
    "warning", "lawsuit", "fraud", "scandal", "regulatory",
    "decrease", "falls", "misses", "underperforms", "negative",
    "nedgång", "förlust", "kritik", "bearish", "weak",
]


def _count_keywords(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
    """Count keyword matches in text. Returns (count, matched_keywords)."""
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text_lower):
            matched.append(kw)
    return len(matched), matched


def analyze_sentiment(
    articles: List[NewsArticle]
) -> SentimentScore:
    """Analyze sentiment from articles using keyword matching.
    
    Returns a SentimentScore with overall score per ticker.
    """
    ticker_sentiments = {}

    for article in articles:
        text = f"{article.title} {article.summary}".lower()
        pos_count, pos_matched = _count_keywords(text, POSITIVE_KEYWORDS)
        neg_count, neg_matched = _count_keywords(text, NEGATIVE_KEYWORDS)

        ticker = article.ticker or "unknown"
        if ticker not in ticker_sentiments:
            ticker_sentiments[ticker] = {
                "positive": 0, "negative": 0, "neutral": 0,
                "total": 0, "articles": [],
            }

        ts = ticker_sentiments[ticker]
        ts["total"] += 1

        if pos_count > neg_count:
            ts["positive"] += 1
        elif neg_count > pos_count:
            ts["negative"] += 1
        else:
            ts["neutral"] += 1

        ts["articles"].append(article)

    # Build result per ticker
    results = []
    for ticker, data in ticker_sentiments.items():
        total = data["total"]
        if total == 0:
            score = 0.0
        else:
            # Score: (positive - negative) / total, clamped to [-1, 1]
            score = (data["positive"] - data["negative"]) / total

        sentiment = SentimentScore(
            ticker=ticker,
            score=round(float(score), 4),
            positive_count=data["positive"],
            negative_count=data["negative"],
            neutral_count=data["neutral"],
            total_articles=total,
            articles=data["articles"],
        )
        results.append(sentiment)

    return results[0] if results else SentimentScore(ticker="", score=0.0)
