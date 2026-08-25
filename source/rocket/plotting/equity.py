"""Equity curve chart creation."""
import plotly.graph_objects as go
from typing import List, Optional
from datetime import datetime
from .utils import get_dark_theme


def create_equity_curve(
    equity_curve: List[float],
    title: str = "Equity Curve",
    benchmark: Optional[List[float]] = None,
    dates: Optional[List[datetime]] = None,
    initial_capital: float = 100000.0,
    width: int = 1200,
    height: int = 500,
) -> go.Figure:
    """Create an equity curve chart with optional benchmark.

    Parameters
    ----------
    equity_curve : List of equity values over time
    title : Chart title
    benchmark : Optional list of benchmark values
    dates : Optional x-axis labels
    initial_capital : Starting value for reference line
    """
    theme = get_dark_theme()
    fig = go.Figure(layout=go.Layout(template=theme))

    x_axis = dates if dates else list(range(len(equity_curve)))

    # Equity line
    fig.add_trace(go.Scatter(
        x=x_axis, y=equity_curve,
        mode='lines',
        name='Portfolio',
        line=dict(color='#89b4fa', width=2.5),
        fill='tozeroy',
        fillcolor='rgba(137,180,250,0.2)',
    ))

    # Benchmark
    if benchmark:
        fig.add_trace(go.Scatter(
            x=x_axis[:len(benchmark)], y=benchmark,
            mode='lines',
            name='Benchmark',
            line=dict(color='#f9e2af', width=1.5, dash='dash'),
        ))

    # Initial capital reference
    fig.add_hline(
        y=initial_capital,
        line_dash="dot", line_color='#6c7086',
        line_width=1.5,
        annotation_text=f"Start: ${initial_capital:,.0f}",
        annotation_position="bottom left",
    )

    # Profit/Loss shading
    def _hex_to_rgba(h: str, alpha: float = 0.27) -> str:
        h = h.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'

    last_val = equity_curve[-1] if equity_curve else initial_capital
    if last_val > initial_capital:
        fig.add_vrect(
            x0=x_axis[0], x1=x_axis[-1],
            fillcolor=_hex_to_rgba('#a6e3a1', 0.27),
            line_width=0,
        )
    else:
        fig.add_vrect(
            x0=x_axis[0], x1=x_axis[-1],
            fillcolor=_hex_to_rgba('#f38ba8', 0.27),
            line_width=0,
        )

    # Layout
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=20, color='#cdd6f4'),
        ),
        xaxis=dict(title='Date'),
        yaxis=dict(title='Equity ($)', gridcolor='#313244'),
        height=height,
        width=width,
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='right', x=1),
        margin=dict(l=60, r=30, t=60, b=50),
    )

    return fig
