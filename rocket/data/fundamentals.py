"""Fetch and cache fundamental data via yfinance.

Key metrics:
  - P/E (trailing + forward)
  - ROE (return on equity)
  - Revenue growth (TTM YoY)
  - Profit margins
  - Debt/equity ratio
  - Price-to-book
  - EPS growth
  - Free cash flow yield
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import yfinance as yf

from .models import Region

logger = logging.getLogger(__name__)

# Cache for fundamental data to avoid repeated API calls
_fund_cache: Dict[str, "FundamentalData"] = {}


@dataclass
class FundamentalData:
    """Fundamental data for a single ticker."""
    ticker: str
    region: Region

    # Valuation
    pe_ttm: Optional[float] = None
    pe_forward: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    ev_ebitda: Optional[float] = None
    peg_ratio: Optional[float] = None

    # Profitability
    roe: Optional[float] = None
    roa: Optional[float] = None
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    gross_margin: Optional[float] = None

    # Growth
    revenue_growth_ttm: Optional[float] = None
    earnings_growth_ttm: Optional[float] = None
    revenue_growth_quarterly: Optional[float] = None

    # Financial health
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    # Per-share
    eps_ttm: Optional[float] = None
    eps_forward: Optional[float] = None
    book_value_per_share: Optional[float] = None
    free_cash_flow_per_share: Optional[float] = None

    # Market
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None

    # Dividends
    dividend_yield: Optional[float] = None
    payout_ratio: Optional[float] = None

    # Analyst
    analyst_target_mean: Optional[float] = None
    analyst_rating: Optional[str] = None

    # Raw info (for debugging)
    raw_info: dict = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """True if we have at least some fundamental data."""
        return any([
            self.pe_ttm is not None,
            self.roe is not None,
            self.revenue_growth_ttm is not None,
            self.market_cap is not None,
        ])

    @property
    def coverage_score(self) -> float:
        """How many fields we have data for (0.0-1.0)."""
        total = 18  # key fields
        filled = sum([
            self.pe_ttm is not None,
            self.pe_forward is not None,
            self.pb is not None,
            self.roe is not None,
            self.profit_margin is not None,
            self.revenue_growth_ttm is not None,
            self.earnings_growth_ttm is not None,
            self.debt_to_equity is not None,
            self.current_ratio is not None,
            self.eps_ttm is not None,
            self.market_cap is not None,
            self.dividend_yield is not None,
            self.peg_ratio is not None,
            self.ev_ebitda is not None,
            self.roa is not None,
            self.free_cash_flow_per_share is not None,
            self.analyst_target_mean is not None,
            self.analyst_rating is not None,
        ])
        return filled / total


def _safe_get(info: dict, key: str) -> Optional[float]:
    """Safely get a float from yfinance info dict."""
    val = info.get(key)
    if val is None:
        return None
    try:
        f = float(val)
        if f == float('inf') or f == float('-inf'):
            return None
        return f
    except (ValueError, TypeError):
        return None


def fetch_fundamentals(
    tickers: list[str],
    cache: bool = True,
) -> Dict[str, FundamentalData]:
    """Fetch fundamental data for a list of tickers.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT"]).
        cache: If True, use in-memory cache to avoid duplicate calls.

    Returns:
        Dict mapping ticker -> FundamentalData.
    """
    result: Dict[str, FundamentalData] = {}

    for ticker in tickers:
        if cache and ticker in _fund_cache:
            result[ticker] = _fund_cache[ticker]
            continue

        try:
            data = _fetch_single_fundamentals(ticker)
            result[ticker] = data
            if cache:
                _fund_cache[ticker] = data
        except Exception:
            logger.warning(f"Failed to fetch fundamentals for {ticker}")

        # Rate limit
        time.sleep(0.3)

    return result


def _fetch_single_fundamentals(ticker: str) -> FundamentalData:
    """Fetch fundamentals for a single ticker."""
    t = yf.Ticker(ticker)
    info = t.info or {}

    fd = FundamentalData(
        ticker=ticker,
        region=Region.US,  # default; infer from exchange if needed
    )

    # ── Valuation ──
    fd.pe_ttm = _safe_get(info, "trailingPE")
    fd.pe_forward = _safe_get(info, "forwardPE")
    fd.pb = _safe_get(info, "priceToBook")
    fd.ps = _safe_get(info, "priceToSalesTrailing12Months")
    fd.ev_ebitda = _safe_get(info, "enterpriseToEbitda")
    fd.peg_ratio = _safe_get(info, "pegRatio")

    # ── Profitability ──
    fd.roe = _safe_get(info, "returnOnEquity")
    fd.roa = _safe_get(info, "returnOnAssets")
    fd.profit_margin = _safe_get(info, "profitMargins")
    fd.operating_margin = _safe_get(info, "operatingMargins")
    fd.gross_margin = _safe_get(info, "grossMargins")

    # ── Growth ──
    fd.revenue_growth_ttm = _safe_get(info, "revenueGrowth")
    fd.earnings_growth_ttm = _safe_get(info, "earningsGrowth")
    fd.revenue_growth_quarterly = _safe_get(info, "earningsQuarterlyGrowth")

    # ── Financial health ──
    fd.debt_to_equity = _safe_get(info, "debtToEquity")
    fd.current_ratio = _safe_get(info, "currentRatio")
    fd.quick_ratio = _safe_get(info, "quickRatio")

    # ── Per-share ──
    fd.eps_ttm = _safe_get(info, "trailingEps")
    fd.eps_forward = _safe_get(info, "forwardEps")
    fd.book_value_per_share = _safe_get(info, "bookValue")
    fd.free_cash_flow_per_share = _safe_get(info, "freeCashflow")

    # ── Market ──
    fd.market_cap = _safe_get(info, "marketCap")
    fd.enterprise_value = _safe_get(info, "enterpriseValue")

    # ── Dividends ──
    fd.dividend_yield = _safe_get(info, "dividendYield")
    fd.payout_ratio = _safe_get(info, "payoutRatio")

    # ── Analyst ──
    fd.analyst_target_mean = _safe_get(info, "targetMeanPrice")
    fd.analyst_rating = info.get("recommendationMean")

    fd.raw_info = info

    return fd


def get_fundamental_score(fd: FundamentalData) -> float:
    """Compute a composite fundamental score from 0.0 (weak) to 1.0 (strong).

    Factors:
      - P/E (lower is better, <15 = strong)
      - ROE (>15% = strong)
      - Revenue growth (>10% = strong)
      - Profit margin (>15% = strong)
      - Debt/equity (<0.5 = strong)
      - PEG ratio (<1.0 = strong)
    """
    if not fd.is_valid:
        return 0.0

    score = 0.0
    weights = 0.0

    # P/E (weight 0.20)
    if fd.pe_ttm is not None and fd.pe_ttm > 0:
        if fd.pe_ttm < 15:
            score += 0.20
        elif fd.pe_ttm < 25:
            score += 0.15
        elif fd.pe_ttm < 35:
            score += 0.08
        else:
            score += 0.02
        weights += 0.20

    # ROE (weight 0.20)
    if fd.roe is not None and fd.roe > 0:
        if fd.roe > 20:
            score += 0.20
        elif fd.roe > 15:
            score += 0.15
        elif fd.roe > 10:
            score += 0.08
        else:
            score += 0.02
        weights += 0.20

    # Revenue growth (weight 0.20)
    if fd.revenue_growth_ttm is not None:
        if fd.revenue_growth_ttm > 0.20:
            score += 0.20
        elif fd.revenue_growth_ttm > 0.10:
            score += 0.15
        elif fd.revenue_growth_ttm > 0.05:
            score += 0.08
        else:
            score += 0.02
        weights += 0.20

    # Profit margin (weight 0.15)
    if fd.profit_margin is not None and fd.profit_margin > 0:
        if fd.profit_margin > 0.20:
            score += 0.15
        elif fd.profit_margin > 0.15:
            score += 0.12
        elif fd.profit_margin > 0.10:
            score += 0.06
        else:
            score += 0.01
        weights += 0.15

    # Debt/equity (weight 0.15) — lower is better
    if fd.debt_to_equity is not None and fd.debt_to_equity >= 0:
        if fd.debt_to_equity < 0.3:
            score += 0.15
        elif fd.debt_to_equity < 0.5:
            score += 0.12
        elif fd.debt_to_equity < 1.0:
            score += 0.06
        else:
            score += 0.01
        weights += 0.15

    # PEG ratio (weight 0.10)
    if fd.peg_ratio is not None and fd.peg_ratio > 0:
        if fd.peg_ratio < 0.5:
            score += 0.10
        elif fd.peg_ratio < 1.0:
            score += 0.08
        elif fd.peg_ratio < 1.5:
            score += 0.04
        else:
            score += 0.01
        weights += 0.10

    return score / weights if weights > 0 else 0.0
