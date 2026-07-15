"""Social sentiment — Reddit scraping via feedparser."""
import logging
import feedparser
import re
from typing import List, Dict
from .models import SocialSentiment

logger = logging.getLogger(__name__)

# Keywords for social media sentiment
POSITIVE_WORDS = ["bullish", "buy", "moon", "long", "accumulate",
                  "tillväxt", "rekord", "bra"]
NEGATIVE_WORDS = ["bearish", "sell", "crash", "short", "dump",
                  "nedgång", "dåligt", "rädsla"]


def _analyze_posts(posts: List[str]) -> Dict[str, int]:
    """Analyze a list of posts for positive/negative keywords."""
    positive = 0
    negative = 0
    for post in posts:
        text = post.lower()
        for pw in POSITIVE_WORDS:
            if pw in text:
                positive += 1
                break
        for nw in NEGATIVE_WORDS:
            if nw in text:
                negative += 1
                break
    return {"positive": positive, "negative": negative}


def fetch_reddit_sentiment(
    tickers: List[str],
    subreddits: List[str] = None
) -> Dict[str, SocialSentiment]:
    """Fetch Reddit sentiment for tickers from specified subreddits.
    
    Uses Reddit's RSS feeds. Returns dict ticker → SocialSentiment.
    """
    if subreddits is None:
        subreddits = ["r/investing", "r/stocks", "r/sweconomy", "r/swedstocks"]

    results = {}
    for ticker in tickers:
        all_posts = []
        for sub in subreddits:
            try:
                # Search Reddit via RSS
                search_url = (
                    f"https://www.reddit.com/{sub}/search.rss"
                    f"?q={ticker.strip().upper()}&restrict_sr=on"
                )
                feed = feedparser.parse(search_url)
                for entry in feed.entries:
                    title = entry.get('title', '')
                    if ticker.upper().replace('.', '') in title.upper() or \
                       ticker.upper() in title.upper():
                        all_posts.append(f"{title} {entry.get('summary', '')[:200]}")
            except Exception as e:
                logger.warning(f"Reddit search failed for {ticker} in {sub}: {e}")

        # Analyze posts
        counts = _analyze_posts(all_posts)
        total = counts["positive"] + counts["negative"]
        if total > 0:
            score = (counts["positive"] - counts["negative"]) / total
        else:
            score = 0.0

        results[ticker] = SocialSentiment(
            ticker=ticker,
            platform="reddit",
            score=round(float(score), 4),
            mention_count=len(all_posts),
            posts=all_posts[:10],  # Store up to 10
        )

    return results
