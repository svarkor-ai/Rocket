"""Tests for rocket.data.bulk_fetcher — bulk OHLCV downloader."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rocket.data.bulk_fetcher import (
    _fetch_batch,
    fetch_all,
    load_checkpoint,
    load_existing_count,
    save_checkpoint,
    save_parquet,
)

# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_ohlcv_dir(tmp_path):
    """Temporary OHLCV directory for testing."""
    ohlcv = tmp_path / "data" / "ohlcv"
    ohlcv.mkdir(parents=True)
    return ohlcv


# ── save_parquet tests ────────────────────────────────────────────────────

def test_save_parquet_creates_files(tmp_ohlcv_dir):
    """Test that save_parquet creates year-partitioned parquet files."""
    import pandas as pd
    
    # Create dummy data with date index (like yfinance output)
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    df = pd.DataFrame({
        "open": [100.0] * len(dates),
        "high": [110.0] * len(dates),
        "low": [90.0] * len(dates),
        "close": [105.0] * len(dates),
        "volume": [1_000_000] * len(dates),
    }, index=dates)
    df.index.name = "date"
    
    with patch("rocket.data.bulk_fetcher.OHLCV_DIR", tmp_ohlcv_dir):
        save_parquet("TEST", df)
    
    # Verify parquet files exist
    test_dir = tmp_ohlcv_dir / "TEST"
    assert test_dir.is_dir()
    assert (test_dir / "2020.parquet").exists()
    assert (test_dir / "2021.parquet").exists()
    assert (test_dir / "2022.parquet").exists()
    
    # Verify data is correct
    df_2021 = pd.read_parquet(test_dir / "2021.parquet")
    dates_2021 = pd.date_range("2021-01-01", "2021-12-31", freq="D")
    assert len(df_2021) == len(dates_2021)
    assert list(df_2021.columns) == ["open", "high", "low", "close", "volume"]


# ── load_existing_count tests ─────────────────────────────────────────────

def test_load_existing_count_empty(tmp_ohlcv_dir):
    """Test that load_existing_count returns empty for non-existent dir."""
    with patch("rocket.data.bulk_fetcher.OHLCV_DIR", tmp_ohlcv_dir):
        result = load_existing_count()
    
    assert result["ok"] == set()
    assert result["incomplete"] == set()


def test_load_existing_count_with_files(tmp_ohlcv_dir):
    """Test that load_existing_count correctly counts years per ticker."""
    import pandas as pd
    
    # Create TEST ticker with 12 years (should be in "ok")
    dates = pd.date_range("2010-01-01", "2021-12-31", freq="D")
    df = pd.DataFrame({
        "open": [100.0] * len(dates),
        "high": [110.0] * len(dates),
        "low": [90.0] * len(dates),
        "close": [105.0] * len(dates),
        "volume": [1_000_000] * len(dates),
    }, index=dates)
    df.index.name = "date"
    
    with patch("rocket.data.bulk_fetcher.OHLCV_DIR", tmp_ohlcv_dir):
        save_parquet("TEST", df)
        result = load_existing_count()
    
    assert "TEST" in result["ok"]
    assert "TEST" not in result["incomplete"]


def test_load_existing_count_incomplete(tmp_ohlcv_dir):
    """Test that load_existing_count puts <10 year tickers in incomplete."""
    import pandas as pd
    
    # Create SHORT ticker with 3 years (should be in "incomplete")
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    df = pd.DataFrame({
        "open": [100.0] * len(dates),
        "high": [110.0] * len(dates),
        "low": [90.0] * len(dates),
        "close": [105.0] * len(dates),
        "volume": [1_000_000] * len(dates),
    }, index=dates)
    df.index.name = "date"
    
    with patch("rocket.data.bulk_fetcher.OHLCV_DIR", tmp_ohlcv_dir):
        save_parquet("SHORT", df)
        result = load_existing_count()
    
    assert "SHORT" in result["incomplete"]
    assert "SHORT" not in result["ok"]


# ── checkpoint tests ──────────────────────────────────────────────────────

def test_checkpoint_roundtrip(tmp_path):
    """Test that checkpoint can be saved and loaded correctly."""
    checkpoint_file = tmp_path / "checkpoint.json"
    
    state = {
        "completed": {"tickers": ["AAPL", "MSFT"], "failed": ["XYZ"]},
        "failed": {},
        "started_at": "2025-01-01T00:00:00+00:00",
        "last_updated": "2025-01-01T01:00:00+00:00",
    }
    
    with patch("rocket.data.bulk_fetcher.CHECKPOINT_FILE", checkpoint_file):
        save_checkpoint(state)
        loaded = load_checkpoint()
    
    assert set(loaded["completed"]["tickers"]) == {"AAPL", "MSFT"}
    assert set(loaded["completed"]["failed"]) == {"XYZ"}
    assert loaded["started_at"] == state["started_at"]


# ── _fetch_batch tests ────────────────────────────────────────────────────

@patch("rocket.data.bulk_fetcher.yf.download")
def test_fetch_batch_success(mock_download, tmp_ohlcv_dir):
    """Test that _fetch_batch correctly processes successful downloads."""
    import pandas as pd
    
    # Mock yfinance response
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")
    mock_df = pd.DataFrame({
        ("AAPL", "Open"): [150.0] * len(dates),
        ("AAPL", "High"): [155.0] * len(dates),
        ("AAPL", "Low"): [145.0] * len(dates),
        ("AAPL", "Close"): [152.0] * len(dates),
        ("AAPL", "Volume"): [1_000_000] * len(dates),
        ("MSFT", "Open"): [300.0] * len(dates),
        ("MSFT", "High"): [310.0] * len(dates),
        ("MSFT", "Low"): [290.0] * len(dates),
        ("MSFT", "Close"): [305.0] * len(dates),
        ("MSFT", "Volume"): [500_000] * len(dates),
    }, index=dates)
    mock_download.return_value = mock_df
    
    with patch("rocket.data.bulk_fetcher.OHLCV_DIR", tmp_ohlcv_dir):
        results = _fetch_batch(["AAPL", "MSFT"], "1y")
    
    assert "AAPL" in results
    assert "MSFT" in results
    assert len(results["AAPL"]) > 0
    assert list(results["AAPL"].columns) == ["open", "high", "low", "close", "volume"]


@patch("rocket.data.bulk_fetcher.yf.download")
def test_fetch_batch_empty(mock_download):
    """Test that _fetch_batch handles empty responses."""
    mock_download.return_value = None
    
    results = _fetch_batch(["INVALID"], "1y")
    assert results == {}


# ── fetch_all tests ───────────────────────────────────────────────────────

@patch("rocket.data.bulk_fetcher._fetch_batch")
@patch("rocket.data.bulk_fetcher.save_parquet")
@patch("rocket.data.bulk_fetcher.save_checkpoint")
def test_fetch_all_empty(mock_checkpoint, mock_save_parquet, mock_fetch, tmp_path):
    """Test that fetch_all returns correctly for empty input."""
    summary = fetch_all([], period="1y")
    assert summary["completed"] == 0
    assert summary["failed"] == 0
    assert summary["remaining"] == 0


@patch("rocket.data.bulk_fetcher._fetch_batch")
@patch("rocket.data.bulk_fetcher.save_parquet")
@patch("rocket.data.bulk_fetcher.save_checkpoint")
def test_fetch_all_success(mock_checkpoint, mock_save_parquet, mock_fetch, tmp_path):
    """Test that fetch_all processes all tickers correctly."""
    import pandas as pd
    
    # Mock successful fetch for all 3 tickers
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")
    mock_df = pd.DataFrame({
        ("AAPL", "Open"): [150.0] * len(dates),
        ("AAPL", "High"): [155.0] * len(dates),
        ("AAPL", "Low"): [145.0] * len(dates),
        ("AAPL", "Close"): [152.0] * len(dates),
        ("AAPL", "Volume"): [1_000_000] * len(dates),
    }, index=dates)
    mock_fetch.return_value = {"AAPL": mock_df}
    
    summary = fetch_all(["AAPL"], period="1y")
    assert summary["newly_fetched"] == 1
    assert summary["completed"] == 1


@patch("rocket.data.bulk_fetcher._fetch_batch")
@patch("rocket.data.bulk_fetcher.save_parquet")
@patch("rocket.data.bulk_fetcher.save_checkpoint")
def test_fetch_all_with_resume(mock_checkpoint, mock_save_parquet, mock_fetch, tmp_path):
    """Test that fetch_all with resume skips already completed tickers."""
    checkpoint_file = tmp_path / "checkpoint.json"
    checkpoint_data = {
        "completed": {"tickers": ["AAPL"], "failed": []},
        "failed": {},
        "started_at": "2025-01-01T00:00:00+00:00",
        "last_updated": "2025-01-01T01:00:00+00:00",
    }
    with open(checkpoint_file, "w") as f:
        json.dump(checkpoint_data, f)
    
    with patch("rocket.data.bulk_fetcher.CHECKPOINT_FILE", checkpoint_file):
        # AAPL is already completed, so only MSFT should be fetched
        summary = fetch_all(["AAPL", "MSFT"], period="1y", resume=True)
        assert summary["completed"] == 1  # Only MSFT fetched (AAPL was completed)
        assert summary["newly_fetched"] == 0  # Nothing new (mock_fetch returns nothing)
