"""ATR-based volatility-adjusted position sizing.

Computes Average True Range (ATR) and uses it for position sizing — larger
ATR => smaller position (risk-per-trade fixed).

The ATR formula matches the existing one in rocket/technical/volatility.py
(if/when that module exists). This module is self-contained.

Public API
----------
compute_atr(high, low, close, period=14) -> pd.Series
atr_position_size(df, atr_period=14, risk_per_trade_pct=1.0, max_position_pct=5.0) -> float
normalize_atr(atr_values) -> pd.Series
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    """Compute Average True Range.

    True Range = max(H-L, |H-prevC|, |L-prevC|)
    ATR = SMA(TR, period)

    Parameters
    ----------
    high : pd.Series
        High prices.
    low : pd.Series
        Low prices.
    close : pd.Series
        Close prices (must be same index as high/low).
    period : int
        ATR period (default 14).

    Returns
    -------
    pd.Series
        ATR values (first period-1 values are NaN).
    """
    if len(high) < period + 1:
        return pd.Series(np.nan, index=high.index)

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period, min_periods=period).mean()

    return atr  # type: ignore[return-value]


def atr_position_size(df: pd.DataFrame,
                      atr_period: int = 14,
                      risk_per_trade_pct: float = 1.0,
                      max_position_pct: float = 5.0,
                      capital: float = 100_000.0) -> float:
    """Compute position size based on ATR.

    Position size = (capital * risk_pct) / (ATR * multiplier)
    where multiplier maps ATR to dollar value per share.

    For a stock priced at $100 with ATR $2.00, risk 1% on $100k capital:
      risk_amount = $1000
      position = $1000 / $2.00 = 500 shares
      position_pct = 500 * $100 / $100,000 = 5% (capped at max_position_pct)

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame with columns ['High', 'Low', 'Close'].
    atr_period : int
        ATR period (default 14).
    risk_per_trade_pct : float
        Risk per trade as fraction (default 1.0 = 1% of capital).
    max_position_pct : float
        Maximum position as fraction of capital (default 5.0 = 5%).
    capital : float
        Total capital (default $100,000).

    Returns
    -------
    float
        Position size as fraction of capital (0.01 = 1%, capped at max_position_pct).
    """
    if df.empty or len(df) < atr_period + 1:
        return 0.0

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    atr_series = compute_atr(high, low, close, period=atr_period)

    # Use the last (current) ATR value
    atr_value = atr_series.iloc[-1]

    if pd.isna(atr_value) or atr_value <= 0:
        return 0.0

    current_price = close.iloc[-1]
    if current_price <= 0:
        return 0.0

    # Risk amount in dollars
    risk_amount = capital * (risk_per_trade_pct / 100.0)

    # Position size: how many "ATR units" of risk fit in our risk budget
    # ATR is in dollar terms; position = risk_amount / ATR shares
    shares = risk_amount / atr_value

    # Convert to position percentage of capital
    position_value = shares * current_price
    position_pct = position_value / capital

    # Cap at max_position_pct
    position_pct = min(position_pct, max_position_pct / 100.0)

    return position_pct


def normalize_atr(atr_values: pd.Series) -> pd.Series:
    """Normalize ATR values to [0, 1] range using min-max scaling.

    Useful for combining ATR with other indicators in scoring.

    Parameters
    ----------
    atr_values : pd.Series
        Raw ATR values.

    Returns
    -------
    pd.Series
        Normalized ATR values (NaN preserved).
    """
    valid = atr_values.dropna()
    if valid.empty:
        return atr_values.copy()

    min_val = valid.min()
    max_val = valid.max()

    if max_val - min_val < 1e-10:
        return pd.Series(0.0, index=atr_values.index)

    normalized = (atr_values - min_val) / (max_val - min_val)
    return normalized


def compute_atr_from_df(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Compute ATR as a single float from OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame with ['High', 'Low', 'Close'].
    period : int
        ATR period.

    Returns
    -------
    float | None
        Last valid ATR value, or None if insufficient data.
    """
    if df.empty or len(df) < period + 1:
        return None

    atr_series = compute_atr(df["High"], df["Low"], df["Close"], period=period)
    last = atr_series.iloc[-1]

    if pd.isna(last):
        return None

    return float(last)
