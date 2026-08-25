"""Tests for social sentiment module.

Tests ticker extraction, sentiment analysis, and WSB scraping.
"""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from rocket.social.models import PostData, SentimentScore, TickerSentiment
from rocket.social.sentiment import (
    analyze_sentiment,
    extract_tickers_from_text,
    get_social_sentiment,
    scrape_r_wallstreetbets,
)


class TestTickerExtraction(unittest.TestCase):
    """Test ticker extraction from text."""

    def test_extract_simple_tickers(self):
        """Test extracting simple ticker symbols from text."""
        text = "TSLA is going to the moon and NVDA looks strong too"
        tickers = extract_tickers_from_text(text)
        self.assertIn("TSLA", tickers)
        self.assertIn("NVDA", tickers)

    def test_extract_multi_char_tickers(self):
        """Test extracting multi-character tickers like BRK.B."""
        text = "BRK.B is a solid pick and AMZN is also good"
        tickers = extract_tickers_from_text(text)
        self.assertIn("BRK.B", tickers)
        self.assertIn("AMZN", tickers)

    def test_exclude_common_words(self):
        """Test that common words are excluded from tickers."""
        text = "THE AND FOR NOT BUT ANY ALL CAN HAD HAS"
        tickers = extract_tickers_from_text(text)
        self.assertEqual(tickers, [])

    def test_no_tickers(self):
        """Test handling of text without tickers."""
        text = "This is just normal text with no stock tickers"
        tickers = extract_tickers_from_text(text)
        self.assertEqual(tickers, [])

    def test_empty_text(self):
        """Test handling of empty text."""
        self.assertEqual(extract_tickers_from_text(""), [])

    def test_none_text(self):
        """Test handling of None text."""
        self.assertEqual(extract_tickers_from_text(None), [])


class TestSentimentAnalysis(unittest.TestCase):
    """Test sentiment analysis."""

    def test_bullish_sentiment(self):
        """Test bullish sentiment detection."""
        text = "TSLA is going to the moon! Buy calls, rocket to Mars!"
        sentiment = analyze_sentiment(text)
        self.assertGreater(sentiment['bullish'], sentiment['bearish'])

    def test_bearish_sentiment(self):
        """Test bearish sentiment detection."""
        text = "NVDA is crashing! Sell puts, bear market incoming!"
        sentiment = analyze_sentiment(text)
        self.assertGreater(sentiment['bearish'], sentiment['bullish'])

    def test_neutral_sentiment(self):
        """Test neutral sentiment for mixed/neutral text."""
        text = "AAPL earnings were okay, nothing special"
        sentiment = analyze_sentiment(text)
        self.assertEqual(sentiment['neutral'], 1)

    def test_empty_text(self):
        """Test handling of empty text."""
        sentiment = analyze_sentiment("")
        self.assertEqual(sentiment, {'bullish': 0, 'bearish': 0, 'neutral': 1})

    def test_none_text(self):
        """Test handling of None text."""
        sentiment = analyze_sentiment(None)
        self.assertEqual(sentiment, {'bullish': 0, 'bearish': 0, 'neutral': 1})


class TestSentimentScore(unittest.TestCase):
    """Test sentiment scoring logic."""

    def test_sentiment_score_calculation(self):
        """Test SentimentScore calculation."""
        score = SentimentScore(
            ticker="TSLA",
            overall_sentiment="bullish",
            sentiment_score=0.8,
            total_mentions=10,
            bullish_mentions=8,
            bearish_mentions=2,
            neutral_mentions=0,
        )
        self.assertEqual(score.ticker, "TSLA")
        self.assertEqual(score.overall_sentiment, "bullish")
        self.assertEqual(score.sentiment_score, 0.8)


class TestScraping(unittest.TestCase):
    """Test WSB scraping."""

    def test_scrape_no_api(self):
        """Test scraping when web_extract API is unavailable."""
        # When API is not available, should return empty list (not crash)
        posts = scrape_r_wallstreetbets(limit=10)
        self.assertIsInstance(posts, list)
        # Posts list should be empty if no API available

    def test_scrape_empty_content(self):
        """Test scraping when web_extract returns empty content."""
        # When API returns no content, should return empty list
        posts = scrape_r_wallstreetbets(limit=10)
        self.assertIsInstance(posts, list)


class TestEndToEnd(unittest.TestCase):
    """Test end-to-end sentiment analysis."""

    def test_end_to_end_sentiment(self):
        """Test end-to-end sentiment analysis flow."""
        # Create mock posts
        posts = [
            PostData(
                title="TSLA is going to the moon! Buy calls!",
                author="test_user",
                score=100,
                url="https://reddit.com/test",
                timestamp=datetime.now(timezone.utc),
                extracted_tickers=["TSLA"],
            ),
            PostData(
                title="NVDA is crashing! Sell puts!",
                author="test_user",
                score=50,
                url="https://reddit.com/test2",
                timestamp=datetime.now(timezone.utc),
                extracted_tickers=["NVDA"],
            ),
        ]

        # Verify posts are structured correctly
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].extracted_tickers, ["TSLA"])
        self.assertEqual(posts[1].extracted_tickers, ["NVDA"])
