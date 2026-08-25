"""Dash layout building functions (5 tabs, dark theme)."""

import dash_bootstrap_components as dbc
from dash import dcc, html


def _tab_icon(icon_name):
    return html.I(className=f"bi bi-{icon_name} me-2", style={"fontSize": "1.2em"})


def _build_table(scores):
    """Build a dash DataTable from a list of score dicts."""
    if not scores:
        return html.P("No scores available.", className="text-center text-muted")
    [{"name": str(k), "id": str(k)} for k in scores[0].keys()]
    import pandas as pd
    return dbc.Table.from_dataframe(
        pd.DataFrame(scores),
        striped=True, dark=True, bordered=True, hover=True, responsive=True,
        style_header={"backgroundColor": "#16213e", "color": "#e0e0e0", "fontWeight": "bold"},
        style_cell={"backgroundColor": "#1a1a2e", "color": "#e0e0e0", "padding": "10px"},
    )


def _build_tab_rankings(region_scores):
    """Tab 1: Top Rankings with region dropdown."""
    if not region_scores:
        return dbc.Card([
            dbc.CardBody([
                html.P("No data loaded. Click Refresh to compute scores.",
                       className="text-muted text-center"),
            ]),
        ], className="mb-3 border-0")
    options = [{"label": r.capitalize(), "value": r} for r in region_scores]
    rank_tables = {r: _build_table(s[:20]) for r, s in region_scores.items()}
    default_val = options[0]["value"] if options else "usa"
    return dbc.Card([
        dbc.CardHeader(
            html.H4(_tab_icon("rocket-takeoff"), "Top Rankings", className="mb-0"),
            className="bg-dark border-bottom border-secondary"),
        dbc.CardBody([
            dcc.Dropdown(id="region-dropdown", options=options,
                         value=default_val, clearable=False, className="mb-3",
                         style={"backgroundColor": "#1a1a2e", "color": "#e0e0e0"}),
            html.Div(id="ranking-table", children=[rank_tables.get("usa")]),
        ]),
    ], className="mb-3 border-0")


def _build_tab_detail(region_scores):
    """Tab 2: Ticker Detail with chart and score breakdown."""
    if not region_scores:
        return dbc.Card([
            dbc.CardBody([
                html.P("No data loaded. Click Refresh to compute scores.",
                       className="text-muted text-center"),
            ]),
        ], className="mb-3 border-0")
    tickers = region_scores.get("usa", [])
    return dbc.Card([
        dbc.CardHeader(
            html.H4(_tab_icon("search"), "Ticker Detail", className="mb-0"),
            className="bg-dark border-bottom border-secondary"),
        dbc.CardBody([
            dcc.Dropdown(id="ticker-dropdown",
                         options=[{"label": t, "value": t} for t in tickers],
                         placeholder="Select a ticker...", className="mb-3"),
            html.Div(id="candlestick-chart"),
            html.Hr(),
            html.H5("Score Breakdown", className="mt-3"),
            html.Div(id="score-breakdown"),
        ]),
    ], className="mb-3 border-0")


def _build_tab_backtest():
    """Tab 3: Backtest Results."""
    return dbc.Card([
        dbc.CardHeader(
            html.H4(_tab_icon("speedometer"), "Backtest Results", className="mb-0"),
            className="bg-dark border-bottom border-secondary"),
        dbc.CardBody([
            dcc.Dropdown(id="strategy-dropdown",
                         options=[
                             {"label": "Buy & Hold", "value": "buy_hold"},
                             {"label": "EMA Crossover", "value": "ema"},
                             {"label": "RSI Mean-Reversion", "value": "rsi"},
                             {"label": "Rocket Combo", "value": "combo"},
                         ], value="combo", className="mb-3"),
            html.Div(id="equity-chart"),
            html.Hr(),
            html.Div(id="bt-metrics"),
        ]),
    ], className="mb-3 border-0")


def _build_tab_sentiment():
    """Tab 4: Sentiment & News."""
    return dbc.Card([
        dbc.CardHeader(
            html.H4(_tab_icon("people"), "Sentiment & News", className="mb-0"),
            className="bg-dark border-bottom border-secondary"),
        dbc.CardBody([
            html.H5("News Feed", className="mt-3"),
            html.Div(id="news-feed", children=[
                html.P("No news data available.", className="text-muted")]),
            html.Hr(),
            html.H5("Sentiment Score", className="mt-3"),
            html.Div(id="sentiment-score", children=[
                html.H2("N/A", className="text-center text-secondary")]),
        ]),
    ], className="mb-3 border-0")


def _build_tab_top_signals():
    """Tab 5: Top Buy/Sell Signals from daily_signals.json."""
    return dbc.Card([
        dbc.CardHeader(
            html.H4(_tab_icon("star"), "Top 10-25 Signals", className="mb-0"),
            className="bg-dark border-bottom border-secondary"),
        dbc.CardBody([
            html.Div(id="top-signals-status", children=[
                html.P("Loading signals from daily scan...", className="text-muted text-center"),
            ]),
            html.Div(id="top-signals-content", children=[
                html.P("No data yet. Run daily scoring to populate signals.", className="text-muted text-center"),
            ]),
        ]),
    ], className="mb-3 border-0")


def _build_tab_settings():
    """Tab 5: Settings."""
    return dbc.Card([
        dbc.CardHeader(
            html.H4(_tab_icon("gear"), "Settings", className="mb-0"),
            className="bg-dark border-bottom border-secondary"),
        dbc.CardBody([
            html.Div([
                html.Label("Last Data Update", className="form-label"),
                html.Span("\u2014", id="last-update", className="text-secondary fs-5"),
            ], className="mb-3"),
            html.Div([
                html.Label("Update Interval (hours)", className="form-label"),
                dcc.Input(id="update-interval", type="number", value=24,
                          className="form-control", min=1, max=168),
            ], className="mb-3"),
            dbc.Button("Refresh Data", id="refresh-btn",
                       color="primary", className="mb-3", n_clicks=0),
            dbc.Button("Export Scores (CSV)", id="export-btn",
                       color="secondary", className="mb-3", n_clicks=0),
            html.Div(id="settings-status", className="text-muted mt-2"),
        ]),
    ], className="mb-3 border-0")


def build_layout(region_scores=None, news_articles=None, bt_result=None):
    """Build the full Dash layout tree.

    Parameters
    ----------
    region_scores : dict mapping region name to list of score dicts.
    news_articles : Optional list of news dicts.
    bt_result : Optional backtest result dict.

    Returns
    -------
    Dash layout tree.
    """
    nav = dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink("Dashboard", href="#", id="nav-dashboard")),
            dbc.NavItem(dbc.NavLink("Settings", href="#", id="nav-settings")),
        ],
        brand="Rocket Stock Scanner", brand_href="#",
        color="dark", dark=True,
    )

    tabs = dbc.Tabs([
        dbc.Tab(_build_tab_rankings(region_scores),
                label="Rankings", tab_id="tab-rankings"),
        dbc.Tab(_build_tab_detail(region_scores),
                label="Ticker Detail", tab_id="tab-detail"),
        dbc.Tab(_build_tab_backtest(),
                label="Backtest", tab_id="tab-backtest"),
        dbc.Tab(_build_tab_sentiment(),
                label="Sentiment", tab_id="tab-sentiment"),
        dbc.Tab(_build_tab_top_signals(),
                label="Top Signals", tab_id="tab-top-signals"),
        dbc.Tab(_build_tab_settings(),
                label="Settings", tab_id="tab-settings"),
    ], id="main-tabs", active_tab="tab-rankings")

    return html.Div([
        dcc.Store(id="data-store"),
        dcc.Location(id="url", refresh=False),
        nav,
        html.Br(),
        dbc.Container(
            dbc.Row(dbc.Col(tabs, width=12)),
            fluid=True, className="pt-3"),
        html.Footer(
            html.P("Rocket Stock Scanner v0.1.0",
                   className="text-center text-muted py-3"),
            className="bg-dark border-top border-secondary mt-4"),
    ], style={"backgroundColor": "#0f0f1a", "minHeight": "100vh"})
