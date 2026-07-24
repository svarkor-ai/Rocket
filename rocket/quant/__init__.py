"""Options-based market microstructure for Rocket Scanner.

Computes Max Pain, Gamma Exposure, Put/Call Ratio, and
Days-to-Expiration from yfinance options chains.
"""
from .options import (
    compute_max_pain,
    compute_gamma_exposure,
    compute_put_call_ratio,
    compute_days_to_expiration,
    compute_options_factor,
    OptionsResult,
)

__all__ = [
    "compute_max_pain",
    "compute_gamma_exposure",
    "compute_put_call_ratio",
    "compute_days_to_expiration",
    "compute_options_factor",
    "OptionsResult",
]
