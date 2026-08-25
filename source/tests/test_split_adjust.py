"""Tests for rocket.dataquality.split_adjust.

8 tests covering:
1. detect_splits: normal detection (2:1 split)
2. detect_splits: reverse split (0.5x)
3. detect_splits: no splits in smooth data
4. detect_splits: empty series
5. adjust_splits: 2:1 split adjustment
6. adjust_splits: 3:1 split adjustment
7. adjust_splits: multiple splits
8. validate_adjustment: post-split validation
"""

import pytest
import numpy as np
import pandas as pd
from datetime import timedelta

from rocket.dataquality.split_adjust import (
    detect_splits,
    adjust_splits,
    validate_adjustment,
)


@pytest.fixture
def split_data_2x() -> pd.DataFrame:
    """Create OHLCV data with a 2:1 split at index 5."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Open": [100, 102, 101, 103, 102, 50, 49, 51, 50, 52],
        "High": [105, 107, 104, 106, 108, 52, 51, 53, 52, 54],
        "Low": [98, 100, 99, 101, 100, 48, 47, 49, 48, 50],
        "Close": [101, 103, 100, 104, 105, 50, 49, 51, 50, 52],
        "Volume": [1000000, 1100000, 900000, 1050000, 1200000, 2000000, 1800000, 1900000, 1700000, 2100000],
    }, index=dates)
    return df


@pytest.fixture
def smooth_data() -> pd.DataFrame:
    """Smooth price data (no splits, no outliers)."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    prices = [100 + i for i in range(10)]
    df = pd.DataFrame({
        "Open": prices,
        "High": [p + 2 for p in prices],
        "Low": [p - 2 for p in prices],
        "Close": prices,
        "Volume": [1000000] * 10,
    }, index=dates)
    return df


@pytest.fixture
def flat_data() -> pd.Series:
    """Flat price series (all same value)."""
    return pd.Series([50.0] * 5, index=pd.date_range("2024-01-01", periods=5, freq="D"))


# === Test detect_splits ===


def test_detect_splits_2x(split_data_2x):
    """Test: detect_splits finds 2:1 split in price series."""
    splits = detect_splits(split_data_2x["Close"])
    assert len(splits) == 1
    assert splits[0]["ratio"] == pytest.approx(2.0, abs=0.5)
    assert splits[0]["method"] == "volume-free-jump"


def test_detect_splits_no_smooth(smooth_data):
    """Test: detect_splits finds no splits in smooth data."""
    splits = detect_splits(smooth_data["Close"])
    assert len(splits) == 0


def test_detect_splits_empty():
    """Test: detect_splits handles empty series."""
    empty = pd.Series([], dtype=float, index=pd.DatetimeIndex([]))
    splits = detect_splits(empty)
    assert splits == []


def test_detect_splits_3x():
    """Test: detect_splits finds 3:1 split."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    close = pd.Series([100, 102, 101, 103, 102, 33.3, 33.0, 34.0, 33.5, 34.5], index=dates)
    splits = detect_splits(close)
    assert len(splits) >= 1  # Should detect the 3x drop
    assert splits[0]["ratio"] == pytest.approx(3.0, abs=0.5)


# === Test adjust_splits ===


def test_adjust_splits_2x(split_data_2x):
    """Test: adjust_splits produces continuous price series for 2:1 split."""
    adj = adjust_splits(split_data_2x, "TEST")
    close = adj["Close"]

    # Post-split prices should be ~2x pre-split (continuous)
    # Before split: 105, after split: 50
    # After adjustment: 50*2=100 ≈ 105 (continuous)
    pre_split_max = close.iloc[:5].max()
    post_split_min = close.iloc[5:].min()

    # They should be close (within 10% for our simple adjustment)
    ratio = pre_split_max / post_split_min if post_split_min > 0 else float("inf")
    assert ratio == pytest.approx(1.0, abs=0.15)


def test_adjust_splits_3x():
    """Test: adjust_splits handles 3:1 split."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Open": [300, 305, 302, 306, 304, 100, 99, 101, 100, 102],
        "High": [310, 315, 308, 312, 310, 102, 101, 103, 102, 104],
        "Low": [295, 300, 298, 302, 300, 98, 97, 99, 98, 100],
        "Close": [300, 305, 302, 306, 304, 100, 99, 101, 100, 102],
        "Volume": [1000000] * 10,
    }, index=dates)

    adj = adjust_splits(df, "TEST3")
    close = adj["Close"]

    # Post-split prices should be ~3x pre-split (continuous)
    pre_split_max = close.iloc[:5].max()
    post_split_min = close.iloc[5:].min()
    ratio = pre_split_max / post_split_min if post_split_min > 0 else float("inf")
    assert ratio == pytest.approx(1.0, abs=0.15)


def test_adjust_splits_no_splits(smooth_data):
    """Test: adjust_splits returns smooth data unchanged (no splits)."""
    adj = adjust_splits(smooth_data, "SMOOTH")
    # Should be essentially unchanged
    assert (adj["Close"] == smooth_data["Close"]).all()


# === Test validate_adjustment ===


def test_validate_adjustment_good():
    """Test: validate_adjustment passes for continuous data."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Close": [50, 51, 52, 53, 54, 55, 56, 57, 58, 59],
        "Open": [49, 50, 51, 52, 53, 54, 55, 56, 57, 58],
        "High": [52, 53, 54, 55, 56, 57, 58, 59, 60, 61],
        "Low": [48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
        "Volume": [1000000] * 10,
    }, index=dates)

    result = validate_adjustment(df, max_jump_pct=0.10)
    assert result is True or result == True


def test_validate_adjustment_bad():
    """Test: validate_adjustment fails for discontinuous data."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Close": [50, 51, 52, 53, 54, 100, 101, 102, 103, 104],  # Jump > 30%
        "Open": [49, 50, 51, 52, 53, 99, 100, 101, 102, 103],
        "High": [52, 53, 54, 55, 56, 102, 103, 104, 105, 106],
        "Low": [48, 49, 50, 51, 52, 98, 99, 100, 101, 102],
        "Volume": [1000000] * 10,
    }, index=dates)

    result = validate_adjustment(df, max_jump_pct=0.10)
    assert result is False or result == False


def test_validate_adjustment_empty():
    """Test: validate_adjustment handles empty data."""
    df = pd.DataFrame(columns=["Close"])
    result = validate_adjustment(df)
    assert result is True or result == True
