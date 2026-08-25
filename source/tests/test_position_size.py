"""Tests for rocket.dataquality.position_size.

6 tests covering:
1. compute_atr: basic calculation
2. compute_atr: empty series
3. atr_position_size: normal calculation
4. atr_position_size: capped at max
5. normalize_atr: min-max scaling
6. compute_atr_from_df: single float
"""

import pytest
import numpy as np
import pandas as pd

from rocket.dataquality.position_size import (
    compute_atr,
    atr_position_size,
    normalize_atr,
    compute_atr_from_df,
)


@pytest.fixture
def ohlcv_df_20() -> pd.DataFrame:
    """OHLCV DataFrame with 20 days of smooth data."""
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    base = 100.0
    df = pd.DataFrame({
        "Open": [base + i * 0.5 for i in range(20)],
        "High": [base + i * 0.5 + 2 for i in range(20)],
        "Low": [base + i * 0.5 - 2 for i in range(20)],
        "Close": [base + i * 0.5 for i in range(20)],
        "Volume": [1000000] * 20,
    }, index=dates)
    return df


# === Test compute_atr ===


def test_compute_atr_basic(ohlcv_df_20):
    """Test: compute_atr returns correct length with expected NaN count.

    With 20 values and period=14 (min_periods=14):
    - Indices 0-12 (13 values): NaN (not enough data)
    - Index 13: first valid ATR
    - Indices 14-19 (6 values): valid ATR
    """
    atr = compute_atr(ohlcv_df_20["High"], ohlcv_df_20["Low"], ohlcv_df_20["Close"], period=14)
    assert len(atr) == 20
    nan_count = int(atr.isna().sum())
    # First 13 values (indices 0-12) are NaN: need 14 values, first valid at index 13
    assert nan_count == 13


def test_compute_atr_empty():
    """Test: compute_atr handles empty series."""
    high = pd.Series([], dtype=float)
    low = pd.Series([], dtype=float)
    close = pd.Series([], dtype=float)
    atr = compute_atr(high, low, close, period=14)
    assert len(atr) == 0


def test_compute_atr_insufficient_data():
    """Test: compute_atr returns all NaN when data < period+1."""
    n = 5  # less than 14+1=15
    index = pd.date_range("2024-01-01", periods=n, freq="D")
    high = pd.Series([100.0] * n, index=index)
    low = pd.Series([98.0] * n, index=index)
    close = pd.Series([99.0] * n, index=index)

    atr = compute_atr(high, low, close, period=14)
    assert all(atr.isna())


# === Test atr_position_size ===


def test_atr_position_size_normal(ohlcv_df_20):
    """Test: atr_position_size returns reasonable value."""
    size = atr_position_size(ohlcv_df_20, atr_period=14,
                             risk_per_trade_pct=1.0, max_position_pct=5.0)
    assert 0.0 < size <= 0.05


def test_atr_position_size_capped():
    """Test: atr_position_size caps at max_position_pct."""
    # Create data with very large ATR → small position
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    df = pd.DataFrame({
        "Open": [100, 102, 101, 103, 102, 105, 104, 106, 105, 107,
                 106, 108, 107, 109, 108, 110, 109, 111, 110, 112],
        "High": [105, 107, 104, 106, 108, 110, 109, 111, 110, 112,
                 111, 113, 112, 114, 113, 115, 114, 116, 115, 117],
        "Low": [95, 97, 96, 98, 97, 100, 99, 101, 100, 102,
                101, 103, 102, 104, 103, 105, 104, 106, 105, 107],
        "Close": [100, 102, 101, 103, 102, 105, 104, 106, 105, 107,
                  106, 108, 107, 109, 108, 110, 109, 111, 110, 112],
        "Volume": [1000000] * 20,
    }, index=dates)

    size = atr_position_size(df, atr_period=14,
                             risk_per_trade_pct=1.0, max_position_pct=5.0)
    assert 0.0 < size <= 0.05


# === Test normalize_atr ===


def test_normalize_atr_min_max(ohlcv_df_20):
    """Test: normalize_atr produces values in [0, 1]."""
    atr = compute_atr(ohlcv_df_20["High"], ohlcv_df_20["Low"], ohlcv_df_20["Close"], period=14)
    normalized = normalize_atr(atr)
    valid = normalized.dropna()
    assert len(valid) > 0
    assert valid.min() >= 0.0
    assert valid.max() <= 1.0


def test_normalize_atr_constant():
    """Test: normalize_atr handles constant ATR (all same value)."""
    atr = pd.Series([5.0] * 10, index=pd.date_range("2024-01-01", periods=10, freq="D"))
    normalized = normalize_atr(atr)
    assert all(normalized == 0.0)


# === Test compute_atr_from_df ===


def test_compute_atr_from_df(ohlcv_df_20):
    """Test: compute_atr_from_df returns a float for valid data."""
    atr_val = compute_atr_from_df(ohlcv_df_20, period=14)
    assert atr_val is not None
    assert atr_val > 0


def test_compute_atr_from_df_empty():
    """Test: compute_atr_from_df returns None for empty DataFrame."""
    df = pd.DataFrame()
    assert compute_atr_from_df(df) is None
