"""Sentiment data models."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class NewsArticle:
    """A single news article."""
    title: str
    summary: str = ""
    url: str = ""
    published: Optional[datetime] = None
    source: str = ""
    ticker: str = ""


@dataclass
class SentimentScore:
    """Overall sentiment score for a set of articles."""
    ticker: str
    score: float               # -1.0 (very negative) to +1.0 (very positive)
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    total_articles: int = 0
    articles: List[NewsArticle] = field(default_factory=list)


@dataclass
class SocialSentiment:
    """Social media sentiment data."""
    ticker: str
    platform: str = ""
    score: float = 0.0
    mention_count: int = 0
    posts: List[str] = field(default_factory=list)


@dataclass
class CorrelationResult:
    """Correlation between sentiment and price."""
    ticker: str
    correlation: float = 0.0
    p_value: float = 1.0
    data_points: int = 0
    interpretation: str = "no data"
