"""Social sentiment module for Rocket Scanner.

Scrapes r/wallstreetbets for stock-related sentiment using web_extract (Firecrawl).
"""
from .models import (
    PostData,
    SentimentScore,
    TickerSentiment,
)
from .sentiment import (
    analyze_sentiment,
    extract_tickers_from_text,
    get_social_score,
    get_social_sentiment,
    scrape_r_wallstreetbets,
)

__all__ = [
    "PostData",
    "SentimentScore",
    "TickerSentiment",
    "analyze_sentiment",
    "extract_tickers_from_text",
    "get_social_score",
    "get_social_sentiment",
    "scrape_r_wallstreetbets",
]
