"""Tests for fundamental data layer."""
import sys
sys.path.insert(0, '/srv/svarkor/builds/rocket-stock-scanner')

import pytest
from unittest.mock import MagicMock, patch

from rocket.data.fundamentals import (
    FundamentalData,
    fetch_fundamentals,
    get_fundamental_score,
    _safe_get,
)
from rocket.data.models import Region
from rocket.scoring.fundamentals_filter import (
    FundamentalFilterResult,
    evaluate_fundamentals,
)


# ── _safe_get tests ──
class TestSafeGet:
    def test_normal_float(self):
        assert _safe_get({"x": 42.5}, "x") == 42.5

    def test_none_returns_none(self):
        assert _safe_get({}, "x") is None

    def test_inf_returns_none(self):
        assert _safe_get({"x": float('inf')}, "x") is None

    def test_string_returns_none(self):
        assert _safe_get({"x": "abc"}, "x") is None


# ── FundamentalData tests ──
class TestFundamentalData:
    def test_is_valid_with_data(self):
        fd = FundamentalData(ticker="AAPL", region=Region.US, pe_ttm=25.0)
        assert fd.is_valid is True

    def test_is_valid_empty(self):
        fd = FundamentalData(ticker="UNKNOWN", region=Region.US)
        assert fd.is_valid is False

    def test_coverage_score_full(self):
        fd = FundamentalData(
            ticker="AAPL", region=Region.US,
            pe_ttm=25.0, pe_forward=22.0, pb=30.0,
            roe=0.35, profit_margin=0.25,
            revenue_growth_ttm=0.15, earnings_growth_ttm=0.10,
            debt_to_equity=0.5, current_ratio=2.0,
            eps_ttm=5.0, market_cap=3e12,
            dividend_yield=0.005, peg_ratio=1.5,
            ev_ebitda=18.0, roa=0.15,
            free_cash_flow_per_share=4.0,
            analyst_target_mean=200.0, analyst_rating="Buy",
        )
        assert fd.coverage_score == 1.0

    def test_coverage_score_empty(self):
        fd = FundamentalData(ticker="X", region=Region.US)
        assert fd.coverage_score == 0.0


# ── get_fundamental_score tests ──
class TestFundamentalScore:
    def test_strong_fundamentals(self):
        """Low P/E, high ROE, high growth = strong score."""
        fd = FundamentalData(
            ticker="STRONG", region=Region.US,
            pe_ttm=12.0, roe=0.25, revenue_growth_ttm=0.25,
            profit_margin=0.20, debt_to_equity=0.2, peg_ratio=0.5,
        )
        score = get_fundamental_score(fd)
        assert score >= 0.75  # all 6 factors are maxed

    def test_weak_fundamentals(self):
        """High P/E, low/no growth = weak score."""
        fd = FundamentalData(
            ticker="WEAK", region=Region.US,
            pe_ttm=60.0, roe=0.05, revenue_growth_ttm=0.02,
            profit_margin=0.03, debt_to_equity=2.0, peg_ratio=3.0,
        )
        score = get_fundamental_score(fd)
        assert score < 0.2

    def test_no_data_returns_zero(self):
        fd = FundamentalData(ticker="EMPTY", region=Region.US)
        assert get_fundamental_score(fd) == 0.0

    def test_partial_data(self):
        """Only P/E provided — partial score."""
        fd = FundamentalData(
            ticker="PARTIAL", region=Region.US,
            pe_ttm=20.0,
        )
        score = get_fundamental_score(fd)
        # With only P/E provided and P/E=20 → "GOOD" bucket (0.15/0.20 = 0.75)
        assert 0.6 < score < 0.9


# ── evaluate_fundamentals tests ──
class TestFundamentalFilter:
    def test_none_fundamentals(self):
        result = evaluate_fundamentals(None)
        assert result.score == 0.0
        assert result.quality == "UNKNOWN"
        assert result.is_pass is False
        assert result.rejection_reason == "no data"

    def test_empty_fundamentals(self):
        fd = FundamentalData(ticker="EMPTY", region=Region.US)
        result = evaluate_fundamentals(fd)
        assert result.quality == "UNKNOWN"
        assert result.rejection_reason == "insufficient data"

    def test_strong_quality(self):
        fd = FundamentalData(
            ticker="STRONG", region=Region.US,
            pe_ttm=12.0, roe=0.25, revenue_growth_ttm=0.25,
            profit_margin=0.20, debt_to_equity=0.2, peg_ratio=0.5,
        )
        result = evaluate_fundamentals(fd)
        assert result.quality == "STRONG"
        assert result.is_pass is True
        assert "P/E=12.0" in result.factors
        assert "ROE=25%" in result.factors

    def test_weak_quality(self):
        fd = FundamentalData(
            ticker="WEAK", region=Region.US,
            pe_ttm=60.0, roe=0.05, revenue_growth_ttm=0.02,
            profit_margin=0.03, debt_to_equity=2.0, peg_ratio=3.0,
        )
        result = evaluate_fundamentals(fd)
        assert result.quality == "WEAK"
        assert result.rejection_reason is not None

    def test_factors_list_populated(self):
        fd = FundamentalData(
            ticker="FACTORS", region=Region.US,
            pe_ttm=22.0, roe=0.18, revenue_growth_ttm=0.12,
            profit_margin=0.15, debt_to_equity=0.6, peg_ratio=1.2,
        )
        result = evaluate_fundamentals(fd)
        assert len(result.factors) >= 5
        # Check factor format
        assert any("P/E=" in f for f in result.factors)
        assert any("ROE=" in f for f in result.factors)
        assert any("RevGrowth=" in f for f in result.factors)


# ── Integration tests ──
class TestIntegration:
    @patch('rocket.data.fundamentals.yf.Ticker')
    def test_fetch_single_ticker(self, mock_ticker_cls):
        """Test fetching a single ticker with mocked yfinance."""
        mock_info = {
            "trailingPE": 25.0,
            "returnOnEquity": 0.30,
            "revenueGrowth": 0.15,
            "profitMargins": 0.18,
            "debtToEquity": 0.4,
            "pegRatio": 1.0,
            "marketCap": 2e12,
            "epsTTM": 4.5,
            "priceToBook": 8.0,
        }
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_ticker_cls.return_value = mock_ticker

        funds = fetch_fundamentals(["TEST.T"], cache=False)
        assert "TEST.T" in funds
        fd = funds["TEST.T"]
        assert fd.pe_ttm == 25.0
        assert fd.roe == 0.30
        assert fd.is_valid is True

    def test_fundamentals_filter_in_pipeline(self):
        """Test that fundamentals filter can be used alongside other filters."""
        from rocket.scoring.fundamentals_filter import evaluate_fundamentals

        fd = FundamentalData(
            ticker="PIPELINE", region=Region.US,
            pe_ttm=20.0, roe=0.20, revenue_growth_ttm=0.10,
            profit_margin=0.15, debt_to_equity=0.6, peg_ratio=1.5,
        )
        result = evaluate_fundamentals(fd)
        assert result.is_pass is True
        assert result.score > 0.3
