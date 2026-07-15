"""Fetch news articles using feedparser from Yahoo Finance RSS."""
import feedparser
import logging
from typing import List, Optional
from datetime import datetime
from .models import NewsArticle

logger = logging.getLogger(__name__)


def fetch_news(tickers: List[str], max_articles: int = 10) -> List[NewsArticle]:
    """Fetch recent news articles for a list of tickers via Yahoo RSS.
    
    Returns a list of NewsArticle objects.
    """
    articles = []
    for ticker in tickers:
        rss_url = (
            f"https://feeds.financial.yahoo.com/rss/headline?"
            f"s={ticker}"
        )
        try:
            feed = feedparser.parse(rss_url)
            entries = feed.entries[:max_articles]
            for entry in entries:
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                article = NewsArticle(
                    title=entry.get('title', ''),
                    summary=entry.get('summary', '')[:300],
                    url=entry.get('link', ''),
                    published=published,
                    source=feed.get('feed', {}).get('title', 'Yahoo Finance'),
                    ticker=ticker,
                )
                articles.append(article)
        except Exception as e:
            logger.warning(f"Failed to fetch news for {ticker}: {e}")
    return articles
