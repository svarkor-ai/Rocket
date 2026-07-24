"""Options-based market microstructure for Rocket Scanner.

Computes Max Pain, Gamma Exposure, Put/Call Ratio, and
Days-to-Expiration from yfinance options chains.

Design:
  - No paid API needed — uses yfinance which is already installed.
  - Options data is US-equity only; Swedish tickers get neutral default.
  - All calculations are deterministic, no ML, no external dependencies.
  - Returns a lightweight OptionsResult with bias (-1 to +1),
    confidence (0 to 1), and a breakdown dict for logging.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OptionsResult:
    """Options-derived price bias for a single ticker."""
    bias: float  # -1.0 (downward pressure) to +1.0 (upward pressure)
    confidence: float  # 0.0 to 1.0 — how reliable is this signal
    max_pain_distance: float  # % distance from current price to max pain
    gamma_exposure: float  # net GEX sign (+ = stabilizing, - = amplifying)
    put_call_ratio: float  # puts_vol / calls_vol
    dte: int  # days to nearest weekly expiration
    is_options_enabled: bool  # True if this ticker has active options market
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def _build_oi_map(df) -> dict:
    """Build {strike: openInterest} from a calls/puts DataFrame."""
    return dict(zip(df["strike"], df["openInterest"].astype(float)))


def compute_max_pain(
    calls_df,
    puts_df,
    current_price: float,
) -> float:
    """Compute Max Pain strike.

    Max Pain = strike price where total option value (calls + puts)
    at expiration is minimized → maximum loss for option buyers.
    """
    strikes = set(calls_df["strike"].unique()) | set(puts_df["strike"].unique())
    if not strikes:
        return current_price

    # Filter out extreme/outlier strikes (beyond 200% of current price)
    # These are usually low-OI noise that distort Max Pain
    strike_range = (current_price * 0.1, current_price * 3.0)
    strikes = {s for s in strikes if strike_range[0] <= s <= strike_range[1]}
    if not strikes:
        return current_price

    pains = {}
    call_oi_map = _build_oi_map(calls_df)
    put_oi_map = _build_oi_map(puts_df)

    for strike in strikes:
        # Total intrinsic value if underlying closes at THIS strike:
        #   calls: max(0, strike - call_strike) × call_OI
        #   puts:  max(0, put_strike - strike) × put_OI
        # Max Pain = strike that MINIMIZES this total value
        total_value = 0.0
        for ck, co in call_oi_map.items():
            if co > 0:
                total_value += max(0.0, strike - ck) * co
        for pk, po in put_oi_map.items():
            if po > 0:
                total_value += max(0.0, pk - strike) * po
        pains[strike] = total_value

    # Strike with minimum total loss for buyers = Max Pain
    min_pain_strike = min(pains.items(), key=lambda x: x[1])[0]
    return float(min_pain_strike)


def compute_gamma_exposure(
    calls_df,
    puts_df,
    current_price: float,
) -> tuple[float, float]:
    """Compute net Gamma Exposure.

    Gamma ≈ how much market makers' delta exposure changes
    per $1 move in the underlying.

    Positive GEX → market makers hedge stabilizing → mean-reverting price action
    Negative GEX → market makers hedge amplifying → trend-accelerating price action

    Parameters
    ----------
    calls_df, puts_df : DataFrames from yfinance options chain
    current_price : float

    Returns
    -------
    (net_gex, gamma_flip_strike)
      net_gex : float — +ve = stabilizing, -ve = amplifying
      gamma_flip_strike : float — strike where GEX flips sign (0.0 if no flip)
    """
    all_strikes = sorted(set(calls_df["strike"].unique()) | set(puts_df["strike"].unique()))
    if not all_strikes:
        return 0.0, 0.0

    # Filter extreme strikes (noise)
    strike_range = (current_price * 0.1, current_price * 3.0)
    all_strikes = sorted(s for s in all_strikes if strike_range[0] <= s <= strike_range[1])
    if not all_strikes:
        return 0.0, 0.0

    # Simple gamma approximation using OI and distance from ATM
    # Actual gamma = N'(d1) / (S * σ * sqrt(T))
    # We approximate: gamma ∝ OI * N'(distance_in_sigma)
    # where distance = |strike - S| / S (simplified, no IV needed for direction)

    net_gamma = 0.0
    call_gamma_by_strike = {}
    put_gamma_by_strike = {}

    for _, row in calls_df.iterrows():
        strike = row["strike"]
        oi = row["openInterest"]
        if oi <= 0:
            continue
        distance = abs(strike - current_price) / current_price
        # Simple Gaussian kernel as gamma approximation
        # Closer strikes have higher gamma
        gamma_approx = oi * np.exp(-0.5 * (distance * 10) ** 2)
        call_gamma_by_strike[strike] = gamma_approx

    for _, row in puts_df.iterrows():
        strike = row["strike"]
        oi = row["openInterest"]
        if oi <= 0:
            continue
        distance = abs(strike - current_price) / current_price
        gamma_approx = oi * np.exp(-0.5 * (distance * 10) ** 2)
        put_gamma_by_strike[strike] = gamma_approx

    # Net GEX: call gamma is positive for MM, put gamma is negative (short put = long delta)
    # Simplified: net GEX = Σ(call_γ - put_γ)
    for strike in all_strikes:
        cg = call_gamma_by_strike.get(strike, 0.0)
        pg = put_gamma_by_strike.get(strike, 0.0)
        net_gamma += (cg - pg)

    # Gamma flip: first strike where cumulative GEX goes from + to -
    gamma_flip_strike = 0.0
    cum_gex = 0.0
    flip_found = False
    for strike in all_strikes:
        cg = call_gamma_by_strike.get(strike, 0.0)
        pg = put_gamma_by_strike.get(strike, 0.0)
        cum_gex += (cg - pg)
        if cum_gex > 0 and not flip_found and cum_gex + (cg - pg) <= 0:
            gamma_flip_strike = strike
            flip_found = True
        elif cum_gex < 0 and not flip_found and cum_gex + (cg - pg) >= 0:
            gamma_flip_strike = strike
            flip_found = True

    return net_gamma, gamma_flip_strike


def compute_put_call_ratio(calls_df, puts_df) -> float:
    """Compute Put/Call Volume Ratio.

    PCR > 1.0 → more puts → bearish sentiment (contrarian buy signal)
    PCR < 0.7 → more calls → bullish sentiment (contrarian sell signal)

    Returns
    -------
    float : puts_volume / calls_volume (0.0 if no volume)
    """
    puts_vol = puts_df["volume"].sum()
    calls_vol = calls_df["volume"].sum()
    if calls_vol == 0:
        return 0.0
    return float(puts_vol / calls_vol)


def compute_days_to_expiration(expiration_date_str: str) -> int:
    """Compute days until a specific expiration date.

    Returns
    -------
    int : days to expiration (0 = today or past)
    """
    try:
        exp = dt.datetime.strptime(expiration_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 999
    today = dt.date.today()
    dte = (exp - today).days
    return max(0, dte)


def _nearest_weekly_expiration(ticker: str) -> tuple[str, int] | None:
    """Find nearest weekly expiration and its DTE.

    Weekly expirations are typically Fridays.
    Returns (expiration_date_str, dte) or None if not found.
    """
    if not _HAS_YF:
        return None
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return None

        # Weekly expirations are usually within 30 days
        # Look for Fridays (standard weekly expiration)
        nearest_weekly = None
        for exp_str in expirations:
            try:
                exp_date = dt.datetime.strptime(exp_str, "%Y-%m-%d").date()
                if exp_date <= dt.date.today():
                    continue
                dte = (exp_date - dt.date.today()).days
                if dte <= 30:
                    # Weekly expirations are on Fridays — check the weekday
                    # Monday=0, Friday=4
                    if exp_date.weekday() == 4:  # Friday
                        if nearest_weekly is None or dte < nearest_weekly[1]:
                            nearest_weekly = (exp_str, dte)
            except ValueError:
                continue

        if nearest_weekly is None:
            # Fallback: nearest expiration (monthly)
            exp_str = expirations[0]
            dte = compute_days_to_expiration(exp_str)
            return (exp_str, dte)

        return nearest_weekly
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_options_factor(
    ticker: str,
    current_price: float,
    social_sentiment_score: float = 0.0,
) -> OptionsResult:
    """Compute the options-derived price bias for a ticker.

    This is the main entry point called from rocket_score.py.
    It fetches options chain data via yfinance, computes Max Pain,
    Gamma Exposure, and Put/Call Ratio, then combines them into
    a single bias score.

    Parameters
    ----------
    ticker : str  — ticker symbol (e.g. "TSLA")
    current_price : float  — current stock price
    social_sentiment_score : float  — existing social sentiment for cross-reference

    Returns
    -------
    OptionsResult with bias, confidence, and breakdown
    """
    if not _HAS_YF or current_price <= 0:
        return OptionsResult(
            bias=0.0,
            confidence=0.0,
            max_pain_distance=0.0,
            gamma_exposure=0.0,
            put_call_ratio=0.0,
            dte=999,
            is_options_enabled=False,
            details={"reason": "no yfinance or invalid price"},
        )

    # Check if ticker has options (US-only)
    # Swedish tickers, non-US, and illiquid tickers won't have options
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return OptionsResult(
                bias=0.0,
                confidence=0.0,
                max_pain_distance=0.0,
                gamma_exposure=0.0,
                put_call_ratio=0.0,
                dte=999,
                is_options_enabled=False,
                details={"reason": "no options chain (likely non-US or illiquid)"},
            )

        # Get nearest weekly expiration
        nearest = _nearest_weekly_expiration(ticker)
        if nearest is None:
            # Fallback: first expiration
            exp_str = expirations[0]
            dte = compute_days_to_expiration(exp_str)
        else:
            exp_str, dte = nearest

        # Fetch options chain
        chain = t.option_chain(exp_str)
        calls = chain.calls
        puts = chain.puts

        # Validate we have data
        if calls is None or calls.empty or puts is None or puts.empty:
            return OptionsResult(
                bias=0.0,
                confidence=0.0,
                max_pain_distance=0.0,
                gamma_exposure=0.0,
                put_call_ratio=0.0,
                dte=dte,
                is_options_enabled=False,
                details={"reason": "empty options chain"},
            )

    except Exception:
        return OptionsResult(
            bias=0.0,
            confidence=0.0,
            max_pain_distance=0.0,
            gamma_exposure=0.0,
            put_call_ratio=0.0,
            dte=999,
            is_options_enabled=False,
            details={"reason": "yfinance fetch failed"},
        )

    # ─── Compute components ───

    # 1. Max Pain
    max_pain = compute_max_pain(calls, puts, current_price)
    mpd = abs(current_price - max_pain) / current_price * 100  # % distance

    # 2. Gamma Exposure
    net_gex, gamma_flip = compute_gamma_exposure(calls, puts, current_price)

    # 3. Put/Call Ratio
    pcr = compute_put_call_ratio(calls, puts)

    # ─── Combine into bias ───

    bias = 0.0
    confidence = 0.0

    # Component 1: Max Pain Distance bias (weight: 0.4)
    # If price > Max Pain → downward pull (negative bias)
    # If price < Max Pain → upward pull (positive bias)
    # Weighted by how far we are from Max Pain
    if mpd > 0:
        mpd_bias = (max_pain - current_price) / current_price
        # Normalize: at 10% distance, bias ≈ ±0.1
        mpd_component = mpd_bias * min(mpd / 10.0, 1.0)
        bias += mpd_component * 0.4
        confidence += 0.1

    # Component 2: Gamma Exposure regime (weight: 0.35)
    # Negative GEX → amplifies trend (if bias from MPD is positive, amplify it)
    # Positive GEX → stabilizes (reduces absolute bias toward 0)
    # We encode as: negative GEX = trend-accelerating
    # But for direction, we just note the regime
    if abs(net_gex) > 0:
        gex_component = np.sign(net_gex) * 0.05  # small directional hint
        bias += gex_component * 0.35
        confidence += 0.1

    # Component 3: Put/Call Ratio (weight: 0.25)
    # PCR > 1.5 → extreme fear → contrarian buy (+bias)
    # PCR < 0.4 → extreme greed → contrarian sell (-bias)
    if pcr > 0:
        # Normalize: PCR=1.0 → neutral, PCR=2.0 → strong buy bias, PCR=0.2 → strong sell bias
        pcr_bias = (1.0 - pcr) / 1.0  # inverted: high PCR = positive bias
        pcr_component = pcr_bias * 0.15  # max ±0.15
        bias += pcr_component * 0.25
        confidence += 0.1

    # Time decay factor: DTE < 7 → Max Pain effect is strongest
    if dte <= 7:
        confidence += 0.2  # higher confidence near expiration
    elif dte <= 14:
        confidence += 0.1

    # Clamp
    confidence = min(confidence, 1.0)
    bias = max(-1.0, min(1.0, bias))

    return OptionsResult(
        bias=round(bias, 4),
        confidence=round(confidence, 4),
        max_pain_distance=round(mpd, 2),
        gamma_exposure=round(net_gex, 2),
        put_call_ratio=round(pcr, 4),
        dte=dte,
        is_options_enabled=True,
        details={
            "max_pain_strike": round(max_pain, 2),
            "gamma_flip_strike": round(gamma_flip, 2) if gamma_flip > 0 else None,
            "expiration": exp_str,
            "dte": dte,
        },
    )
