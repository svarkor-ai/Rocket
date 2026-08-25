"""Social sentiment module for Rocket Scanner.

Scrapes r/wallstreetbets for stock-related sentiment using web_extract (Firecrawl).
Also provides StockTwits API client, meme stock detection, and FINVIZ short interest.
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
from .short_interest import (
    ShortInterestData,
    get_short_interest,
    scrape_short_interest,
)
from .stocktwits import (
    get_available_symbols,
    get_bullish_pct,
    get_sentiment,
    get_trending,
    get_volume_analytics,
)
from .meme_score import (
    MemeSignal,
    compute_meme_score,
    meme_score_from_defaults,
    meme_score_from_stocktwits,
)

__all__ = [
    # Models
    "PostData",
    "SentimentScore",
    "ShortInterestData",
    "TickerSentiment",
    "MemeSignal",
    # WSB sentiment
    "analyze_sentiment",
    "extract_tickers_from_text",
    "get_social_score",
    "get_social_sentiment",
    "scrape_r_wallstreetbets",
    # Short interest
    "get_short_interest",
    "scrape_short_interest",
    # StockTwits
    "get_available_symbols",
    "get_bullish_pct",
    "get_sentiment",
    "get_trending",
    "get_volume_analytics",
    # Meme detection
    "compute_meme_score",
    "meme_score_from_defaults",
    "meme_score_from_stocktwits",
]
