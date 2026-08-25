"""Candlestick chart creation with Plotly."""
import plotly.graph_objects as go
from .utils import get_dark_theme, get_color_palette


def create_candlestick(
    df,
    ticker: str = "SYNTH",
    title: str = "Candlestick Chart",
    width: int = 1200,
    height: int = 600,
) -> go.Figure:
    """Create a candlestick chart with volume bars.

    Parameters
    ----------
    df : DataFrame with columns [open, high, low, close, volume]
    ticker : Ticker symbol for title
    title : Chart title
    """
    palette = get_color_palette()

    # Normalize column names to lowercase (yfinance may return uppercase)
    col_map = {c.lower(): c for c in df.columns}
    o_col = col_map.get('open', 'open')
    h_col = col_map.get('high', 'high')
    l_col = col_map.get('low', 'low')
    c_col = col_map.get('close', 'close')
    v_col = col_map.get('volume', 'volume')

    fig = go.Figure(layout=go.Layout(
        template=get_dark_theme(),
        title=dict(
            text=f"{ticker} — {title}",
            font=dict(size=20, color='#cdd6f4'),
        ),
    ))

    # Candlestick
    def _hex_to_rgba(h: str, alpha: float = 0.8) -> str:
        """Convert hex color to rgba string for Plotly v5 compatibility."""
        h = h.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df[o_col],
        high=df[h_col],
        low=df[l_col],
        close=df[c_col],
        name='OHLC',
        increasing_line_color=palette['buy'],
        decreasing_line_color=palette['sell'],
        increasing_fillcolor=_hex_to_rgba(palette['buy'], 0.8),
        decreasing_fillcolor=_hex_to_rgba(palette['sell'], 0.8),
    ))

    # Volume bars
    def _hex_to_rgba(h: str, alpha: float = 0.5) -> str:
        h = h.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'

    colors = [
        _hex_to_rgba(palette['volume_buy'] if df[c_col].iloc[i] >= df[o_col].iloc[i]
                      else palette['volume_sell'], 0.5)
        for i in range(len(df))
    ]
    fig.add_trace(go.Bar(
        x=df.index,
        y=df[v_col],
        name='Volume',
        marker_color=colors,
        yaxis='y2',
        opacity=1.0,
    ))

    # Layout with shared x-axis
    fig.update_layout(
        xaxis=dict(title='Date', rangebreaks=[
            dict(bounds=["sat", "mon"])  # Hide weekends
        ]),
        yaxis=dict(title='Price ($)', side='right',
                   gridcolor='#313244'),
        yaxis2=dict(
            title='Volume', overlaying='y',
            side='left', showgrid=False,
            domain=[0, 0.15],
            gridcolor='#313244',
        ),
        height=height,
        width=width,
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='right', x=1),
        margin=dict(l=50, r=50, t=80, b=80),
    )

    return fig
