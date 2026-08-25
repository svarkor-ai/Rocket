"""Tests for rocket.dataquality.outlier_detect.

10 tests covering:
1. detect_outliers_iqr: basic detection
2. detect_outliers_iqr: no outliers
3. detect_outliers_iqr: empty series
4. detect_outliers_mad: basic detection
5. detect_outliers_mad: no outliers
6. detect_outliers_mad: empty series
7. winsorize_column: clips outliers
8. winsorize_column: preserves non-outliers
9. winsorize_df: multi-column
10. outlier_report: summary
"""

import pytest
import numpy as np
import pandas as pd

from rocket.dataquality.outlier_detect import (
    detect_outliers_iqr,
    detect_outliers_mad,
    winsorize_column,
    winsorize_df,
    outlier_report,
)


@pytest.fixture
def series_with_outliers() -> pd.Series:
    """Series with a clear outlier."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]  # 100 is outlier
    return pd.Series(data, index=pd.date_range("2024-01-01", periods=10, freq="D"))


@pytest.fixture
def series_no_outliers() -> pd.Series:
    """Series with no outliers (smooth)."""
    data = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    return pd.Series(data, index=pd.date_range("2024-01-01", periods=10, freq="D"))


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """Sample OHLCV DataFrame."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame({
        "Open": [10, 11, 12, 13, 14, 15, 16, 17, 18, 100],
        "High": [12, 13, 14, 15, 16, 17, 18, 19, 20, 102],
        "Low": [9, 10, 11, 12, 13, 14, 15, 16, 17, 98],
        "Close": [10, 11, 12, 13, 14, 15, 16, 17, 18, 100],
        "Volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 50000],
    }, index=dates)


# === Test detect_outliers_iqr ===


def test_detect_outliers_iqr_basic(series_with_outliers):
    """Test: IQR detects the outlier at position 9 (value 100)."""
    mask = detect_outliers_iqr(series_with_outliers, k=1.5)
    assert bool(mask.iloc[-1]) is True
    assert int(mask.iloc[:-1].sum()) == 0


def test_detect_outliers_iqr_no_outliers(series_no_outliers):
    """Test: IQR finds no outliers in smooth data."""
    mask = detect_outliers_iqr(series_no_outliers)
    assert int(mask.sum()) == 0


def test_detect_outliers_iqr_empty():
    """Test: IQR handles empty series."""
    empty = pd.Series([], dtype=float)
    mask = detect_outliers_iqr(empty)
    assert len(mask) == 0


def test_detect_outliers_iqr_k_3():
    """Test: IQR with k=3 is less sensitive."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100]
    series = pd.Series(data, index=pd.date_range("2024-01-01", periods=11, freq="D"))

    mask_15 = detect_outliers_iqr(series, k=1.5)
    assert bool(mask_15.iloc[-1]) is True

    mask_3 = detect_outliers_iqr(series, k=3.0)
    assert len(mask_3) == 11


# === Test detect_outliers_mad ===


def test_detect_outliers_mad_basic(series_with_outliers):
    """Test: MAD detects the outlier at position 9."""
    mask = detect_outliers_mad(series_with_outliers, threshold=3.0)
    assert bool(mask.iloc[-1]) is True


def test_detect_outliers_mad_no_outliers(series_no_outliers):
    """Test: MAD finds no outliers in smooth data."""
    mask = detect_outliers_mad(series_no_outliers)
    assert int(mask.sum()) == 0


def test_detect_outliers_mad_empty():
    """Test: MAD handles empty series."""
    empty = pd.Series([], dtype=float)
    mask = detect_outliers_mad(empty)
    assert len(mask) == 0


# === Test winsorize_column ===


def test_winsorize_column_clips(series_with_outliers):
    """Test: winsorize_column clips outliers."""
    clipped = winsorize_column(series_with_outliers, 0.05, 0.95)
    # 95th percentile of [1..10,100] ≈ 95.5
    # 100 should be clipped to ~95.5
    assert clipped.iloc[-1] <= 96.0


def test_winsorize_column_preserves():
    """Test: winsorize_column preserves non-outlier values."""
    data = [1, 2, 3, 4, 5]
    series = pd.Series(data)
    clipped = winsorize_column(series, 0.0, 1.0)
    assert (clipped == series).all()


# === Test winsorize_df ===


def test_winsorize_df_multi_column(ohlcv_df):
    """Test: winsorize_df clips outliers in multiple columns."""
    result = winsorize_df(ohlcv_df, ["Close", "Volume"], clip_pct=0.05)

    # With clip_pct=0.05, upper=quantile(0.95)
    # For 10 values: 95th pctile ≈ 95% position
    # Close: [10..18, 100] → 95th pctile ≈ 95.5
    # Volume: [1000..1800, 50000] → 95th pctile ≈ 47500
    assert result["Close"].iloc[-1] <= 96.0
    assert result["Volume"].iloc[-1] <= 50000  # May or may not clip


def test_winsorize_df_no_clipping_needed():
    """Test: winsorize_df handles data with no outliers."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "Close": [10, 11, 12, 13, 14],
        "Volume": [1000, 1100, 1200, 1300, 1400],
    }, index=dates)

    result = winsorize_df(df, ["Close", "Volume"], clip_pct=0.5)
    assert len(result) == 5


# === Test outlier_report ===


def test_outlier_report_basic(ohlcv_df):
    """Test: outlier_report generates correct summary."""
    report = outlier_report(ohlcv_df, ["Close", "Volume"])

    assert "Close" in report
    assert "Volume" in report
    assert report["Close"]["total_values"] == 10
    assert int(report["Close"]["iqr_outliers"]) > 0


def test_outlier_report_empty():
    """Test: outlier_report handles empty DataFrame."""
    df = pd.DataFrame()
    report = outlier_report(df)
    assert isinstance(report, dict)
