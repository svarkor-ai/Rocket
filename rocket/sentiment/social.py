"""Social sentiment — Reddit scraping with OAuth support.

Falls back to RSS-based scraping when OAuth credentials are not available.
"""
import logging
import re
from typing import List, Dict, Optional
from .models import SocialSentiment
from .reddit_auth import RedditSession

logger = logging.getLogger(__name__)

# ── Keywords ──────────────────────────────────────────────────────────────
POSITIVE_WORDS = [
    "bullish", "buy", "moon", "long", "accumulate",
    "tillväxt", "rekord", "bra", "strong", "breakout",
    "squeeze", "diamond hands", "dh", "hold", "buying",
    "up", "gain", "profit", "rally", "surge",
]
NEGATIVE_WORDS = [
    "bearish", "sell", "crash", "short", "dump",
    "nedgång", "dåligt", "rädsla", "weak", "resistance",
    "bear", "profit taking", "liquidation", "down", "loss",
    "fear", "panic", "sell-off", "cap", "ceiling",
]


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


def _try_rss_fallback(ticker: str, subreddits: List[str]) -> List[str]:
    """Try RSS-based scraping as fallback (no auth needed)."""
    try:
        import feedparser
    except ImportError:
        return []
    
    all_posts = []
    for sub in subreddits:
        try:
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
            logger.warning(f"RSS search failed for {ticker} in {sub}")
    
    return all_posts


def fetch_reddit_sentiment(
    tickers: List[str],
    subreddits: List[str] = None,
    session: RedditSession = None,
) -> Dict[str, SocialSentiment]:
    """Fetch Reddit sentiment for tickers from specified subreddits.
    
    Uses OAuth-based Reddit API when credentials are available.
    Falls back to RSS-based scraping when credentials are missing.
    
    Returns dict ticker → SocialSentiment.
    """
    if subreddits is None:
        subreddits = [
            "r/gamestop", "r/superstonk", "r/wallstreetbets",
            "r/sweconomy", "r/swedstocks",
        ]
    
    results = {}
    
    for ticker in tickers:
        all_posts = []
        
        # Try OAuth first, fallback to RSS
        if session is not None:
            for sub in subreddits:
                try:
                    data = session.search_subreddit(
                        sub.replace('r/', ''),
                        ticker.strip().upper(),
                        limit=25,
                        sort='top',
                        time_filter='week'
                    )
                    if data and isinstance(data, dict) and 'data' in data:
                        posts = data['data'].get('children', [])
                        for post in posts:
                            if isinstance(post, dict):
                                child = post.get('data', {})
                                title = child.get('title', '')
                                if ticker.upper().replace('.', '') in title.upper() or \
                                   ticker.upper() in title.upper():
                                    all_posts.append(
                                        f"{title} — score:{child.get('score', 0)}"
                                    )
                except Exception as e:
                    logger.warning(f"Reddit OAuth search failed for {ticker} in {sub}")
                    continue
        else:
            # RSS fallback
            all_posts = _try_rss_fallback(ticker, subreddits)
        
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
            posts=all_posts[:10],
        )
    
    return results


def fetch_subreddit_activity(
    subreddits: List[str] = None,
    session: RedditSession = None,
) -> Dict[str, Dict]:
    """Fetch overall subreddit activity (top posts, trending tickers).
    
    Useful for monitoring what's trending in meme stock communities.
    Returns dict subreddit → activity summary.
    """
    if subreddits is None:
        subreddits = [
            "r/gamestop", "r/superstonk", "r/wallstreetbets",
        ]
    
    results = {}
    
    for sub in subreddits:
        sub_name = sub.replace('r/', '')
        try:
            if session is not None:
                data = session.get_subreddit_posts(
                    sub_name,
                    limit=50,
                    sort='hot',
                    time_filter='day',
                )
                if data and isinstance(data, dict) and 'data' in data:
                    children = data['data'].get('children', [])
                    top_posts = []
                    tickers_mentioned = {}
                    
                    for child in children:
                        if isinstance(child, dict):
                            d = child.get('data', {})
                            title = d.get('title', '')
                            score = d.get('score', 0)
                            top_posts.append({
                                'title': title,
                                'score': score,
                                'ups': d.get('ups', 0),
                                'downs': d.get('downs', 0),
                                'num_comments': d.get('num_comments', 0),
                            })
                            
                            # Extract ticker symbols from title
                            found_tickers = re.findall(r'\b[A-Z]{1,5}\b', title)
                            for t in found_tickers:
                                tickers_mentioned[t] = tickers_mentioned.get(t, 0) + 1
                    
                    results[sub] = {
                        'top_posts': top_posts[:10],
                        'trending_tickers': dict(
                            sorted(tickers_mentioned.items(),
                                   key=lambda x: x[1], reverse=True)[:10]
                        ),
                        'total_posts_analyzed': len(children),
                    }
        except Exception as e:
            logger.warning(f"Reddit activity failed for {sub}")
            results[sub] = {'error': str(e)}
    
    return results


def monitor_user_activity(
    username: str,
    subreddits: List[str] = None,
    session: RedditSession = None,
) -> Dict:
    """Monitor a specific Reddit user's activity (e.g. ultimator5).
    
    Searches for the user's posts in specified subreddits.
    Returns user activity summary.
    """
    if subreddits is None:
        subreddits = ["r/superstonk", "r/gamestop", "r/wallstreetbets"]
    
    user_activity = {
        'username': username,
        'posts': [],
        'total_score': 0,
    }
    
    for sub in subreddits:
        try:
            if session is not None:
                data = session.search_subreddit(
                    sub.replace('r/', ''),
                    f'user:{username}',
                    limit=25,
                    sort='top',
                    time_filter='month',
                )
                if data and isinstance(data, dict) and 'data' in data:
                    children = data['data'].get('children', [])
                    for child in children:
                        if isinstance(child, dict):
                            d = child.get('data', {})
                            user_activity['posts'].append({
                                'subreddit': sub,
                                'title': d.get('title', ''),
                                'score': d.get('score', 0),
                                'created_utc': d.get('created_utc'),
                                'link_id': d.get('id'),
                            })
                            user_activity['total_score'] += d.get('score', 0)
            else:
                # RSS fallback — limited user search
                logger.info(f"OAuth not available, skipping user {username} search")
        except Exception as e:
            logger.warning(f"User monitor failed for {username} in {sub}")
    
    user_activity['posts'] = sorted(
        user_activity['posts'],
        key=lambda x: x['score'],
        reverse=True,
    )[:20]
    
    return user_activity
