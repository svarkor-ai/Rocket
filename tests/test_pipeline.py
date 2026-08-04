"""Tests for rocket.dataquality.pipeline.

6 tests covering:
1. validate_ohlcv: normal data passes
2. validate_ohlcv: empty data fails
3. validate_ohlcv: missing columns fails
4. clean_ohlcv: normal data cleaned
5. clean_ohlcv: rejected data
6. build_pipeline_config: returns config dict
"""

import pytest
import pandas as pd
from datetime import timedelta

from rocket.dataquality.pipeline import (
    validate_ohlcv,
    clean_ohlcv,
    build_pipeline_config,
)


# === Test validate_ohlcv ===


def test_validate_ohlcv_normal():
    """Test: validate_ohlcv passes for good data."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Open": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        "High": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
        "Low": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
        "Close": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        "Volume": [1000000] * 10,
    }, index=dates)

    result = validate_ohlcv(df, "TEST")
    assert result["pass"] is True or result["pass"] == True
    assert result["ticker"] == "TEST"
    assert result["issues"] == []


def test_validate_ohlcv_empty():
    """Test: validate_ohlcv rejects empty data."""
    df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    result = validate_ohlcv(df, "EMPTY")
    assert result["pass"] is False or result["pass"] == False
    assert "Empty DataFrame" in result["issues"]


def test_validate_ohlcv_missing_columns():
    """Test: validate_ohlcv detects missing columns."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "Close": [10, 11, 12, 13, 14],
    }, index=dates)

    result = validate_ohlcv(df, "INCOMPLETE")
    assert result["pass"] is False or result["pass"] == False
    assert len(result["issues"]) > 0


# === Test clean_ohlcv ===


def test_clean_ohlcv_normal():
    """Test: clean_ohlcv produces cleaned data for normal input."""
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    df = pd.DataFrame({
        "Open": [100 + i * 0.5 for i in range(20)],
        "High": [102 + i * 0.5 for i in range(20)],
        "Low": [98 + i * 0.5 for i in range(20)],
        "Close": [100 + i * 0.5 for i in range(20)],
        "Volume": [1000000] * 20,
    }, index=dates)

    cleaned, metadata = clean_ohlcv(df, "TEST")
    assert len(cleaned) == 20
    assert "Close" in cleaned.columns


def test_clean_ohlcv_rejected():
    """Test: clean_ohlcv rejects invalid data."""
    df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    cleaned, metadata = clean_ohlcv(df, "EMPTY")
    assert metadata["rejected"] is True or metadata["rejected"] == True
    assert metadata["rejection_reason"] is not None


# === Test build_pipeline_config ===


def test_build_pipeline_config():
    """Test: build_pipeline_config returns a dict with expected keys."""
    config = build_pipeline_config()
    assert isinstance(config, dict)
    assert "split_threshold" in config
    assert "outlier_k" in config
    assert "winsor_pct" in config
    assert config["split_threshold"] == 0.30
    assert config["outlier_k"] == 1.5
    assert config["winsor_pct"] == 0.01
