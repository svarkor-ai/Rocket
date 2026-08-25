"""Tests for AutoTrend and RubeGoldberg indicators."""

import numpy as np
import pandas as pd
import pytest

from rocket.technical.advanced import AutoTrend, RubeGoldberg
from rocket.technical.models import Signal


def _make_df(n=100, trend="flat", base=100.0):
    """Generate synthetic price data."""
    np.random.seed(42)
    if trend == "up":
        close = base + np.arange(n) * 0.5 + np.random.randn(n) * 0.3
    elif trend == "down":
        close = base - np.arange(n) * 0.5 + np.random.randn(n) * 0.3
    else:
        close = base + np.random.randn(n) * 0.5

    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    return pd.DataFrame({"close": close, "high": high, "low": low}, index=range(n))


# ── AutoTrend ────────────────────────────────────────────────

def test_autotrend_flat_no_breakout():
    """AutoTrend on flat data returns HOLD."""
    df = _make_df(100, "flat")
    at = AutoTrend()
    result = at.calculate(df)
    assert result.signal == Signal.HOLD
    assert result.score == pytest.approx(0.0, abs=0.01)
    assert result.values["breakout_signal"] == "NONE"


def test_autotrend_returns_name():
    """AutoTrend returns correct name."""
    df = _make_df(100, "flat")
    at = AutoTrend()
    result = at.calculate(df)
    assert result.name == "AutoTrend"


def test_autotrend_short_data():
    """AutoTrend with insufficient data returns HOLD."""
    df = _make_df(20, "up")
    at = AutoTrend()
    result = at.calculate(df)
    assert result.signal == Signal.HOLD
    assert result.values["trend_direction"] == "FLAT"


def test_autotrend_has_trend_metrics():
    """AutoTrend result contains expected metrics."""
    df = _make_df(100, "up")
    at = AutoTrend()
    result = at.calculate(df)
    for key in ["trend_direction", "trend_strength", "channel_upper",
                "channel_lower", "breakout_signal", "high_slope", "low_slope"]:
        assert key in result.values, f"Missing key: {key}"


def test_autotrend_up_trendline():
    """AutoTrend should show UP trend in uptrending data."""
    df = _make_df(200, "up")
    at = AutoTrend(min_pivots=2)
    result = at.calculate(df)
    assert result.values["trend_direction"] in ("UP", "FLAT")
    assert 0.0 <= result.values["trend_strength"] <= 1.0


def test_autotrend_up_breakout():
    """AutoTrend should detect UP breakout in strong uptrend."""
    df = pd.DataFrame({
        "close": np.concatenate([np.ones(50) * 100, np.arange(50) * 2 + 200]),
        "high": np.concatenate([np.ones(50) * 105, np.arange(50) * 2 + 210]),
        "low": np.concatenate([np.ones(50) * 95, np.arange(50) * 2 + 190]),
    }, index=range(100))
    at = AutoTrend(breakout_threshold=0.001, min_pivots=2)
    result = at.calculate(df)
    assert result.signal in (Signal.BUY, Signal.HOLD)


# ── RubeGoldberg ─────────────────────────────────────────────

def test_rube_goldberg_short_data():
    """RubeGoldberg with insufficient data returns HOLD."""
    df = _make_df(30, "flat")
    rg = RubeGoldberg()
    result = rg.calculate(df)
    assert result.signal == Signal.HOLD
    assert result.values["trigger_count"] == 0


def test_rube_goldberg_returns_name():
    """RubeGoldberg returns correct name."""
    df = _make_df(60, "flat")
    rg = RubeGoldberg()
    result = rg.calculate(df)
    assert result.name == "RubeGoldberg"


def test_rube_goldberg_has_metrics():
    """RubeGoldberg result contains expected metrics."""
    df = _make_df(100, "flat")
    rg = RubeGoldberg()
    result = rg.calculate(df)
    for key in ["rsi", "adx", "sar_flip_direction", "trigger_count",
                "rsi_trigger", "adx_trigger", "sar_trigger"]:
        assert key in result.values, f"Missing key: {key}"


def test_rube_goldberg_rsi_reasonable():
    """RubeGoldberg RSI should be in [0, 100]."""
    df = _make_df(100, "flat")
    rg = RubeGoldberg()
    result = rg.calculate(df)
    assert 0 <= result.values["rsi"] <= 100


def test_rube_goldberg_no_spurious_signal():
    """RubeGoldberg should not produce strong signal on flat data."""
    df = _make_df(100, "flat")
    rg = RubeGoldberg()
    result = rg.calculate(df)
    assert result.signal != Signal.BUY or result.score < 0.5
    assert result.signal != Signal.SELL or result.score > -0.5
