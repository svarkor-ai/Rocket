"""Plotly theme and color utilities."""
import plotly.graph_objects as go


def get_dark_theme() -> go.layout.Template:
    """Return a dark-themed Plotly layout template."""
    return go.layout.Template(
        layout=dict(
            paper_bgcolor='#1e1e2e',
            plot_bgcolor='#1e1e2e',
            font=dict(family='Inter, sans-serif', size=12, color='#cdd6f4'),
            title=dict(font=dict(size=18, color='#cdd6f4')),
            xaxis=dict(
                gridcolor='#313244',
                linecolor='#313244',
                ticks='',
                tickfont=dict(color='#a6adc8'),
            ),
            yaxis=dict(
                gridcolor='#313244',
                linecolor='#313244',
                ticks='',
                tickfont=dict(color='#a6adc8'),
            ),
            margin=dict(l=60, r=30, t=50, b=40),
        )
    )


def get_color_palette() -> dict:
    """Return a curated color palette (Catppuccin-inspired dark)."""
    return {
        'green': '#a6e3a1',
        'red': '#f38ba8',
        'blue': '#89b4fa',
        'yellow': '#f9e2af',
        'purple': '#cba6f7',
        'teal': '#94e2d5',
        'mauve': '#cba6f7',
        'peach': '#fab387',
        'overlay': '#6c7086',
        'buy': '#a6e3a1',
        'sell': '#f38ba8',
        'hold': '#94e2d5',
        'volume_buy': '#a6e3a166',
        'volume_sell': '#f38ba866',
    }


def format_axis(fig: go.Figure, y_label: str = "Price ($)",
                x_label: str = "Date") -> go.Figure:
    """Apply consistent axis formatting."""
    fig.update_yaxes(title_text=y_label, tickprefix='$' if 'Price' in y_label else '')
    fig.update_xaxes(title_text=x_label)
    return fig
