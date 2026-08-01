"""Add technical indicators to an existing candlestick chart."""
import plotly.graph_objects as go
from typing import Dict, Any, List


def add_indicators_to_chart(
    fig: go.Figure,
    indicators: List[Dict[str, Any]],
    df,
) -> go.Figure:
    """Add indicator overlays to a candlestick figure.

    Parameters
    ----------
    fig : Existing Plotly figure (candlestick)
    indicators : List of dicts with keys:
        - name: str (e.g., "EMA9")
        - values: dict (e.g., {"ema": series})
        - category: str (e.g., "trend")
    df : Original OHLCV DataFrame for reference
    """
    for ind in indicators:
        name = ind.get("name", "")
        values = ind.get("values", {})

        if "ema" in values and isinstance(values["ema"], (list,)):
            series = values["ema"]
            fig.add_trace(go.Scatter(
                x=df.index if hasattr(df.index, '__iter__') else range(len(series)),
                y=series,
                mode='lines',
                name=name,
                line=dict(width=1, opacity=0.7),
                legendgroup=name,
                showlegend=True,
            ))

        elif "ema_fast" in values and "ema_slow" in values:
            # EMA crossover
            fast = values.get("ema_fast", [])
            slow = values.get("ema_slow", [])
            if isinstance(fast, list) and isinstance(slow, list):
                x = df.index if hasattr(df.index, '__iter__') else range(len(fast))
                fig.add_trace(go.Scatter(
                    x=x, y=fast, mode='lines',
                    name=f"{name} fast", line=dict(width=1.5, color='#89b4fa'),
                    legendgroup=name, opacity=0.8,
                ))
                fig.add_trace(go.Scatter(
                    x=x, y=slow, mode='lines',
                    name=f"{name} slow", line=dict(width=1.5, color='#f38ba8'),
                    legendgroup=name, opacity=0.8,
                ))

        if "atr" in values:
            atr_val = values["atr"]
            if isinstance(atr_val, (int, float)):
                last_close = df['close'].iloc[-1] if len(df) else 0
                fig.add_hline(
                    y=last_close + atr_val,
                    line_dash="dash", line_color='#f9e2af',
                    line_width=1, opacity=0.6,
                    annotation_text=f"ATR={atr_val:.2f}",
                    annotation_position="top right",
                )

        if "bb_upper" in values and "bb_lower" in values:
            upper = values["bb_upper"]
            lower = values["bb_lower"]
            mid = values.get("bb_mid", upper)
            if isinstance(upper, list):
                x = df.index if hasattr(df.index, '__iter__') else range(len(upper))
                fig.add_trace(go.Scatter(
                    x=x, y=upper, mode='lines', name="BB Upper",
                    line=dict(width=1, color='#cba6f7'), opacity=0.4,
                ))
                fig.add_trace(go.Scatter(
                    x=x, y=lower, mode='lines', name="BB Lower",
                    line=dict(width=1, color='#cba6f7'), opacity=0.4,
                ))
                if isinstance(mid, list):
                    fig.add_trace(go.Scatter(
                        x=x, y=mid, mode='lines', name="BB Mid",
                        line=dict(width=1, color='#cba6f7'), opacity=0.6,
                    ))

    return fig
