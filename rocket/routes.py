"""5-tab Dash layout: Rankings, Ticker Detail, Backtest, Sentiment, Settings."""
from dash import html, dcc


def _tab_style(active=False):
    return {
        'padding': '12px 24px',
        'borderRadius': '8px',
        'backgroundColor': '#313244' if active else '#1e1e2e',
        'color': '#cdd6f4' if active else '#6c7086',
        'cursor': 'pointer',
        'transition': 'all 0.2s',
        'fontSize': '14px',
        'fontWeight': 'bold' if active else 'normal',
    }


def _build_rankings_tab():
    """Rankings tab — top tickers per region in tables."""
    regions = ["us", "smid", "eu", "asia"]
    tables = []
    for region in regions:
        tickers = get_universe(region)
        rows = []
        for t in tickers[:10]:
            rows.append(html.Tr([
                html.Td(t, style={'color': '#89b4fa', 'fontWeight': 'bold'}),
                html.Td("—"),
                html.Td("—", style={'textAlign': 'center'}),
            ], style={'borderBottom': '1px solid #313244'}))
        table = html.Table([
            html.Tr([
                html.Th("Ticker", style={'color': '#f9e2af', 'padding': '8px'}),
                html.Th("Sector", style={'color': '#f9e2af', 'padding': '8px'}),
                html.Th("Score", style={'color': '#f9e2af', 'padding': '8px'}),
            ]),
        ] + rows, style={
            'width': '100%', 'borderCollapse': 'collapse',
            'color': '#cdd6f4', 'fontSize': '13px',
        })
        tables.append(html.Div([
            html.H3(region.upper(), style={
                'color': '#89b4fa', 'marginBottom': '10px',
                'marginTop': '0', 'fontSize': '18px',
            }),
            table,
        ], style={'marginBottom': '25px'}))
    return html.Div(tables, style={'padding': '20px', 'maxWidth': '900px', 'margin': '0 auto'})


def _build_ticker_detail_tab():
    """Ticker Detail tab — chart + indicator breakdown."""
    return html.Div([
        html.Div([
            html.Label("Select Ticker", style={'color': '#a6adc8', 'display': 'block', 'marginBottom': '6px'}),
            dcc.Dropdown(
                id='ticker-detail-dropdown',
                options=[{'label': t, 'value': t} for t in get_universe('us')[:20]],
                value='AAPL', clearable=False,
                style={'width': '300px'},
            ),
        ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center'}),
        html.Div(id='ticker-chart-output', style={'height': '500px', 'width': '100%'}),
        html.Div(id='ticker-indicators-output', style={
            'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)',
            'gap': '10px', 'marginTop': '15px',
        }),
    ], style={'padding': '20px', 'maxWidth': '1200px', 'margin': '0 auto'})


def _build_backtest_tab():
    """Backtest tab — strategy selection + results."""
    return html.Div([
        html.Div([
            html.Label("Strategy", style={'color': '#a6adc8', 'display': 'block', 'marginBottom': '4px'}),
            dcc.Dropdown(
                id='bt-strategy',
                options=[
                    {'label': 'Buy & Hold', 'value': 'buy_hold'},
                    {'label': 'EMA Crossover 9/21', 'value': 'ema_crossover'},
                    {'label': 'RSI Reversal', 'value': 'rsi'},
                    {'label': 'Rocket Combo', 'value': 'rocket_combo'},
                ],
                value='rocket_combo', style={'width': '250px'},
            ),
            html.Label("Ticker", style={'color': '#a6adc8', 'display': 'block', 'marginBottom': '4px', 'marginTop': '10px'}),
            dcc.Dropdown(
                id='bt-ticker',
                options=[{'label': t, 'value': t} for t in get_universe('us')[:10]],
                value='AAPL', clearable=False, style={'width': '200px'},
            ),
            html.Button("Run Backtest", id='bt-run', n_clicks=0,
                        style={'padding': '10px 24px', 'backgroundColor': '#89b4fa',
                               'color': '#1e1e2e', 'border': 'none',
                               'borderRadius': '6px', 'cursor': 'pointer',
                               'fontWeight': 'bold', 'marginTop': '18px'}),
        ], style={'marginBottom': '20px', 'display': 'flex', 'gap': '20px',
                  'alignItems': 'flex-end'}),
        html.Div(id='bt-results', style={
            'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)', 'gap': '10px',
        }),
        html.Div(id='bt-chart-output', style={
            'height': '400px', 'width': '100%', 'marginTop': '20px',
        }),
    ], style={'padding': '20px', 'maxWidth': '1200px', 'margin': '0 auto'})


def _build_sentiment_tab():
    """Sentiment tab — news + social sentiment cards."""
    return html.Div([
        html.H3("News Sentiment", style={'color': '#f9e2af', 'marginBottom': '15px'}),
        html.Div([
            html.Div([
                html.H4("Latest News", style={'color': '#cdd6f4', 'marginTop': '0'}),
                html.P("No articles loaded yet.", style={'color': '#6c7086'}),
            ], style={'padding': '15px', 'backgroundColor': '#313244',
                      'borderRadius': '8px', 'marginBottom': '20px'}),
            html.Div([
                html.H4("Sentiment Score", style={'color': '#cdd6f4', 'marginTop': '0'}),
                html.P("—", style={'color': '#a6adc8', 'fontSize': '24px'}),
            ], style={'padding': '15px', 'backgroundColor': '#313244',
                      'borderRadius': '8px'}),
        ], style={'display': 'grid', 'gridTemplateColumns': '2fr 1fr',
                  'gap': '15px', 'marginBottom': '30px'}),
        html.H3("Social Sentiment (Reddit)", style={'color': '#f9e2af', 'marginBottom': '15px'}),
        html.Div(id='sentiment-social-output', style={
            'display': 'grid', 'gridTemplateColumns': 'repeat(3, 1fr)', 'gap': '10px',
        }),
    ], style={'padding': '20px', 'maxWidth': '1200px', 'margin': '0 auto'})


def _build_settings_tab():
    """Settings tab — data and configuration options."""
    return html.Div([
        html.H3("Data Settings", style={'color': '#f9e2af', 'marginBottom': '20px'}),
        html.Div([
            html.Label("Data Directory", style={'color': '#cdd6f4'}),
            dcc.Input(id='settings-data-dir', value='data',
                      style={'padding': '8px 12px', 'width': '350px',
                             'backgroundColor': '#313244', 'color': '#cdd6f4',
                             'border': '1px solid #45475a', 'borderRadius': '4px',
                             'marginBottom': '15px'}),
        ], style={'marginBottom': '20px'}),
        html.Div([
            html.Label("Max Age (days)", style={'color': '#cdd6f4'}),
            dcc.Input(id='settings-max-age', value='1', type='number',
                      style={'padding': '8px 12px', 'width': '100px',
                             'backgroundColor': '#313244', 'color': '#cdd6f4',
                             'border': '1px solid #45475a', 'borderRadius': '4px',
                             'marginBottom': '15px'}),
        ], style={'marginBottom': '20px'}),
        html.H3("Enable Regions", style={'color': '#f9e2af', 'marginBottom': '10px'}),
        html.Div([
            html.Label(html.Input(type='checkbox', id='reg-us', defaultChecked=True),
                       style={'marginRight': '8px', 'color': '#cdd6f4'}), "US ",
            html.Label(html.Input(type='checkbox', id='reg-smid', defaultChecked=True),
                       style={'marginRight': '8px', 'color': '#cdd6f4'}), "SMID ",
            html.Label(html.Input(type='checkbox', id='reg-eu', defaultChecked=True),
                       style={'marginRight': '8px', 'color': '#cdd6f4'}), "EU ",
            html.Label(html.Input(type='checkbox', id='reg-asia', defaultChecked=True),
                       style={'color': '#cdd6f4'}), "Asia",
        ], style={'marginBottom': '30px'}),
        html.Button("Save Settings", id='settings-save', n_clicks=0,
                    style={'padding': '10px 24px', 'backgroundColor': '#a6e3a1',
                           'color': '#1e1e2e', 'border': 'none',
                           'borderRadius': '6px', 'cursor': 'pointer',
                           'fontWeight': 'bold'}),
        html.Div(id='settings-status', style={'marginTop': '15px', 'color': '#a6e3a1'}),
    ], style={'padding': '20px', 'maxWidth': '700px', 'margin': '0 auto'})


def build_layout():
    """Build the complete 5-tab layout for the Dash app."""
    return html.Div([
        html.H1("Rocket Stock Scanner", style={
            'textAlign': 'center', 'color': '#cdd6f4',
            'padding': '20px', 'marginBottom': '5px', 'fontSize': '28px',
        }),
        html.P("Multi-region stock scoring, sentiment analysis & backtesting", style={
            'textAlign': 'center', 'color': '#6c7086',
            'marginBottom': '15px', 'fontSize': '14px',
        }),
        html.Div([
            html.Div('Rankings', id='tab-rankings', style=_tab_style(active=True)),
            html.Div('Ticker Detail', id='tab-detail', style=_tab_style(active=False)),
            html.Div('Backtest', id='tab-backtest', style=_tab_style(active=False)),
            html.Div('Sentiment', id='tab-sentiment', style=_tab_style(active=False)),
            html.Div('Settings', id='tab-settings', style=_tab_style(active=False)),
        ], id='tab-nav', style={
            'display': 'flex', 'gap': '5px',
            'padding': '10px 20px', 'justifyContent': 'center',
        }),
        html.Div(id='tab-content', style={
            'padding': '10px 30px', 'minHeight': '700px',
            'backgroundColor': '#181825',
        }),
        dcc.Store(id='tab-store', data='rankings'),
        dcc.Interval(id='refresh-interval', interval=5*60*1000, n_intervals=0),
    ], style={
        'backgroundColor': '#1e1e2e', 'minHeight': '100vh',
        'fontFamily': 'Inter, -apple-system, sans-serif',
    })


def setup_callbacks(app):
    """Register all tab-switching callbacks."""
    tab_names = ['rankings', 'detail', 'backtest', 'sentiment', 'settings']

    @app.callback(
        [Output(f'tab-{n}', 'style') for n in tab_names]
        + [Output('tab-content', 'children')]
        + [Output('tab-store', 'data')],
        [Input(f'tab-{n}', 'n_clicks') for n in tab_names],
        State('tab-store', 'data'),
        prevent_initial_call=True,
    )
    def switch_tabs(*click_counts):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise dash.no_update
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
        tab_map = dict(zip([f'tab-{n}' for n in tab_names], tab_names))
        active = tab_map.get(triggered_id, 'rankings')
        tab_styles = {n: _tab_style(active=(n == active)) for n in tab_names}
        content = {
            'rankings': _build_rankings_tab(),
            'detail': _build_ticker_detail_tab(),
            'backtest': _build_backtest_tab(),
            'sentiment': _build_sentiment_tab(),
            'settings': _build_settings_tab(),
        }
        return (
            [tab_styles[n] for n in tab_names],
            content[active],
            active,
        )
