"""Outlier detection and handling for OHLCV data.

Provides IQR-based, MAD-based outlier detection and winsorization (clipping
to specified percentiles).

Methods
-------
- IQR (Interquartile Range): Q1 - k*IQR, Q3 + k*IQR bounds (k=1.5 default)
- MAD (Median Absolute Deviation): median ± threshold * 1.4826 * MAD
- Winsorization: clip to specified percentiles (default 1st/99th)

Why IQR/MAD over z-score: z-score is sensitive to extreme outliers in meme
stocks; IQR/MAD are robust estimators.

Public API
----------
detect_outliers_iqr(series, k=1.5) -> pd.Series[bool]
detect_outliers_mad(series, threshold=3.0) -> pd.Series[bool]
winsorize_column(series, lower_pct, upper_pct) -> pd.Series
winsorize_df(df, columns, clip_pct=0.01) -> pd.DataFrame
outlier_report(df, columns) -> dict
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def detect_outliers_iqr(series: pd.Series, k: float = 1.5) -> pd.Series:
    """Detect outliers using the IQR method.

    Parameters
    ----------
    series : pd.Series
        Input data (numeric).
    k : float
        Multiplier for IQR (default 1.5). Typical values: 1.5 (mild), 3.0 (extreme).

    Returns
    -------
    pd.Series[bool]
        Boolean mask: True where outlier detected.
    """
    if series.empty or series.dropna().shape[0] < 4:
        return pd.Series(False, index=series.index)

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower_bound = q1 - k * iqr
    upper_bound = q3 + k * iqr

    return (series < lower_bound) | (series > upper_bound)


def detect_outliers_mad(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    """Detect outliers using the MAD (Median Absolute Deviation) method.

    MAD is more robust than IQR for heavily-tailed distributions (common in
    meme-stock price data).

    Parameters
    ----------
    series : pd.Series
        Input data (numeric).
    threshold : float
        Multiplier for MAD (default 3.0). Equivalent to ~3 sigma for normal data.

    Returns
    -------
    pd.Series[bool]
        Boolean mask: True where outlier detected.
    """
    if series.empty or series.dropna().shape[0] < 4:
        return pd.Series(False, index=series.index)

    median = series.median()
    mad = (series - median).abs().median()

    # Scale factor: 1.4826 makes MAD consistent with std for normal data
    scaled_mad = threshold * 1.4826 * mad

    return (series - median).abs() > scaled_mad


def winsorize_column(series: pd.Series, lower_pct: float, upper_pct: float) -> pd.Series:
    """Clip a series to specified percentiles (winsorization).

    Parameters
    ----------
    series : pd.Series
        Input data (numeric).
    lower_pct : float
        Lower percentile (e.g., 0.01 for 1st percentile).
    upper_pct : float
        Upper percentile (e.g., 0.99 for 99th percentile).

    Returns
    -------
    pd.Series
        Clipped series. Values outside [lower, upper] are clipped.
    """
    if series.empty:
        return series.copy()

    lower = series.quantile(lower_pct)
    upper = series.quantile(upper_pct)

    clipped = series.clip(lower=lower, upper=upper)
    clipped_count = (clipped != series).sum()

    if clipped_count > 0:
        log.debug("Winsorized %d values (clipped to [%.4f, %.4f]).",
                  clipped_count, lower, upper)

    return clipped


def winsorize_df(df: pd.DataFrame, columns: list[str], clip_pct: float = 0.01) -> pd.DataFrame:
    """Winsorize specified columns in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame (OHLCV).
    columns : list[str]
        Column names to winsorize (e.g., ['Close', 'High', 'Low', 'Open']).
    clip_pct : float
        Clip percentage (default 0.01 = 1st/99th percentile).

    Returns
    -------
    pd.DataFrame
        New DataFrame with winsorized columns.
    """
    df_adj = df.copy()
    total_clipped = 0

    for col in columns:
        if col not in df_adj.columns:
            continue

        lower = df_adj[col].quantile(clip_pct)
        upper = df_adj[col].quantile(1.0 - clip_pct)

        clipped = df_adj[col].clip(lower=lower, upper=upper)
        count = (clipped != df_adj[col]).sum()
        total_clipped += count

        df_adj[col] = clipped

    if total_clipped > 0:
        log.info("Winsorized %d values across columns %s.", total_clipped, columns)
    else:
        log.debug("No outliers found in columns %s.", columns)

    return df_adj


def outlier_report(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, Any]:
    """Generate a summary report of outlier counts per column.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame.
    columns : list[str] | None
        Columns to analyze. If None, uses all numeric columns.

    Returns
    -------
    dict
        {column_name: {"iqr_outliers": int, "mad_outliers": int,
                       "both_outliers": int, "total_values": int}}
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    report: dict[str, Any] = {}

    for col in columns:
        series = df[col].dropna()
        if series.empty:
            report[col] = {
                "iqr_outliers": 0,
                "mad_outliers": 0,
                "both_outliers": 0,
                "total_values": 0,
            }
            continue

        iqr_mask = detect_outliers_iqr(series)
        mad_mask = detect_outliers_mad(series)

        report[col] = {
            "iqr_outliers": int(iqr_mask.sum()),
            "mad_outliers": int(mad_mask.sum()),
            "both_outliers": int((iqr_mask & mad_mask).sum()),
            "total_values": len(series),
        }

    return report
