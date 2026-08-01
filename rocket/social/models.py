"""Social sentiment data models for Reddit r/wallstreetbets analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PostData:
    """A single scraped Reddit post from r/wallstreetbets."""
    title: str
    author: str
    score: int
    url: str
    timestamp: datetime
    extracted_tickers: list[str] = field(default_factory=list)


@dataclass
class TickerSentiment:
    """Sentiment analysis for a single ticker from Reddit posts."""
    ticker: str
    total_mentions: int
    bullish_mentions: int
    bearish_mentions: int
    neutral_mentions: int
    sentiment_score: float  # -1.0 to +1.0
    sentiment_label: str  # 'bullish', 'bearish', 'neutral'
    sample_titles: list[str] = field(default_factory=list)


@dataclass
class SentimentScore:
    """Social sentiment score for Rocket Scanner integration."""
    ticker: str
    overall_sentiment: str  # 'bullish', 'bearish', 'neutral'
    sentiment_score: float  # 0.0 to 1.0 (for Rocket scoring)
    total_mentions: int
    bullish_mentions: int
    bearish_mentions: int
    neutral_mentions: int
    sample_titles: list[str] = field(default_factory=list)
