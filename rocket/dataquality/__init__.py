"""Public API for Rocket Data Quality modules.

Exports all public functions so consumers can use:
    from rocket.dataquality import clean_ohlcv, detect_splits, winsorize_df, etc.
"""

from rocket.dataquality.split_adjust import adjust_splits, detect_splits
from rocket.dataquality.outlier_detect import (
    detect_outliers_iqr,
    detect_outliers_mad,
    winsorize_column,
    winsorize_df,
    outlier_report,
)
from rocket.dataquality.position_size import (
    compute_atr,
    atr_position_size,
    normalize_atr,
)
from rocket.dataquality.pipeline import clean_ohlcv, validate_ohlcv, build_pipeline_config

__all__ = [
    # split_adjust
    "adjust_splits",
    "detect_splits",
    # outlier_detect
    "detect_outliers_iqr",
    "detect_outliers_mad",
    "winsorize_column",
    "winsorize_df",
    "outlier_report",
    # position_size
    "compute_atr",
    "atr_position_size",
    "normalize_atr",
    # pipeline
    "clean_ohlcv",
    "validate_ohlcv",
    "build_pipeline_config",
]
