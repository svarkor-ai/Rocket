"""Fetch news articles using feedparser from Google News RSS."""
import feedparser
import logging
from typing import List
from datetime import datetime
from .models import NewsArticle

logger = logging.getLogger(__name__)


def fetch_news(tickers: List[str], max_articles: int = 10) -> List[NewsArticle]:
    """Fetch recent news articles for a list of tickers via Google News RSS.

    Returns a list of NewsArticle objects.
    """
    articles = []
    for ticker in tickers:
        rss_url = (
            f"https://news.google.com/rss/search?"
            f"q={ticker}&"
            f"hl=en&gl=US&ceid=US:en"
        )
        try:
            feed = feedparser.parse(rss_url)
            if not feed.entries:
                logger.info(f"No news found for {ticker} (Google News)")
                continue
            entries = feed.entries[:max_articles]
            for entry in entries:
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])

                article = NewsArticle(
                    title=entry.get('title', ''),
                    summary=entry.get('summary', '')[:300],
                    url=entry.get('link', ''),
                    published=published,
                    source=feed.get('feed', {}).get('title', 'Google News'),
                    ticker=ticker,
                )
                articles.append(article)
        except Exception:
            logger.warning(f"Failed to fetch news for {ticker}")
    return articles
