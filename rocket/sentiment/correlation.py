"""Correlation between sentiment scores and price returns."""
import numpy as np
import pandas as pd
from typing import List, Optional
from .models import SentimentScore, CorrelationResult


def compute_sentiment_price_correlation(
    sentiment_scores: List[SentimentScore],
    price_data: Optional[pd.DataFrame] = None,
    ticker: str = ""
) -> CorrelationResult:
    """Compute correlation between sentiment and price movement.
    
    If price_data is None, returns a neutral result.
    price_data should be a DataFrame with a 'close' column indexed by date.
    """
    if not sentiment_scores or len(sentiment_scores) == 0:
        return CorrelationResult(
            ticker=ticker, correlation=0.0, p_value=1.0,
            data_points=0, interpretation="no data"
        )

    # Extract sentiment scores (normalized to -1, 0, 1)
    sentiments = [s.score for s in sentiment_scores]

    if price_data is not None and len(price_data) > 1:
        # Compute daily returns
        returns = price_data['close'].pct_change().dropna()

        # Use overlapping window approach: correlate sentiment with returns
        n = min(len(sentiments), len(returns))
        if n < 3:
            return CorrelationResult(
                ticker=ticker, correlation=0.0, p_value=1.0,
                data_points=n, interpretation="insufficient data"
            )

        s_arr = np.array(sentiments[:n])
        r_arr = returns.iloc[-n:].values

        # Pearson correlation
        if np.std(s_arr) == 0 or np.std(r_arr) == 0:
            corr = 0.0
        else:
            corr = np.corrcoef(s_arr, r_arr)[0, 1]

        if np.isnan(corr):
            corr = 0.0
    else:
        corr = 0.0
        n = 0

    # Interpret correlation
    abs_corr = abs(corr)
    if abs_corr >= 0.7:
        interp = "strong"
    elif abs_corr >= 0.4:
        interp = "moderate"
    elif abs_corr >= 0.2:
        interp = "weak"
    else:
        interp = "negligible"

    interp += " " + ("positive" if corr > 0 else "negative" if corr < 0 else "no") + " correlation"

    return CorrelationResult(
        ticker=ticker,
        correlation=round(float(corr), 4),
        p_value=1.0,  # Would need scipy for real p-value
        data_points=n,
        interpretation=interp,
    )
