"""Dash callbacks for Rocket Stock Scanner."""
import logging
from datetime import datetime
from dash.dependencies import Input, Output, State
import dash
import pandas as pd
import numpy as np
from dash import html
from dash_bootstrap_components import Table as dbc

from rocket.data.fetcher import fetch_ohlcv
from rocket.data.universe import get_universe
from rocket.data.storage import save_ohlcv, load_ohlcv, needs_update
from rocket.data.models import TickerInfo, Region
from rocket.scoring.rocket_score import compute_rocket_score
from rocket.scoring.ranking import rank_regions, top_overall
from rocket.scoring.models import RocketScore
from rocket.technical.momentum import RSI, MACD, ROC
from rocket.technical.trend import EMACrossover, ADX
from rocket.technical.volatility import BollingerBands, ATR
from rocket.technical.volume import OBV, MFI, VWAPIndicator
from rocket.technical.advanced import IchimokuCloud, Supertrend

# For Top Signals callback
import json
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

# Cache for computed data
_computed_cache: dict = {}


def _build_indicator_results(df: pd.DataFrame) -> list:
    """Run all indicators on OHLCV data, return list of IndicatorResults."""
    indicators = [
        RSI(), MACD(), ROC(),
        EMACrossover(), ADX(),
        BollingerBands(), ATR(),
        OBV(), MFI(), VWAPIndicator(),
        IchimokuCloud(), Supertrend(),
    ]
    results = []
    for ind in indicators:
        try:
            r = ind.calculate(df)
            results.append(r)
        except Exception as e:
            logger.warning(f"Indicator {ind.name if hasattr(ind, 'name') else 'unknown'} failed")
    return results


def _rocket_to_dict(rs: RocketScore) -> dict:
    """Convert a RocketScore dataclass to a flat dict for Dash storage."""
    return {
        "ticker": rs.ticker,
        "overall_score": rs.overall_score,
        "momentum_score": rs.momentum_score,
        "trend_score": rs.trend_score,
        "volatility_score": rs.volatility_score,
        "volume_score": rs.volume_score,
        "buy_count": rs.buy_count,
        "sell_count": rs.sell_count,
        "hold_count": rs.hold_count,
        "filter_passed": rs.filter_passed,
        "filter_reason": rs.filter_reason,
        "region": rs.region,
        "sector": rs.sector,
        "current_price": rs.current_price,
        "avg_volume": rs.avg_volume,
    }


def _score_ticker(ticker: str, df: pd.DataFrame) -> tuple:
    """Score a single ticker using compute_rocket_score.
    
    Returns (RocketScore, dict) — RocketScore for ranking, dict for Dash storage.
    """
    ticker_info = TickerInfo(ticker=ticker)
    current_price = float(df['close'].iloc[-1])
    avg_vol = float(df['volume'].mean()) if len(df) > 0 else 0.0
    ticker_info.avg_volume = avg_vol

    result = compute_rocket_score(df, ticker_info, current_price=current_price)
    rocket_score = result["rocket_score"]
    rocket_score.current_price = current_price  # for display
    rocket_score.avg_volume = avg_vol  # for display
    
    return rocket_score, _rocket_to_dict(rocket_score)


def setup_callbacks(app):
    """Register all Dash callbacks."""

    # ── Region dropdown: update ticker dropdown ────────────────────
    @app.callback(
        Output("ticker-dropdown", "options"),
        Output("ticker-dropdown", "value"),
        Input("region-dropdown", "value"),
    )
    def update_ticker_options(region):
        if not region:
            return [], []
        tickers = get_universe(region)
        return [{"label": t, "value": t} for t in tickers], tickers[0] if tickers else None

    # ── Refresh / Compute scores ──────────────────────────────────
    @app.callback(
        Output("data-store", "data"),
        Output("settings-status", "children"),
        Output("last-update", "children"),
        Input("refresh-btn", "n_clicks"),
        State("update-interval", "value"),
        State("region-dropdown", "value"),
    )
    def refresh_scores(n_clicks, interval, region):
        if n_clicks is None or not region:
            return None, "No region selected", "—"
        if n_clicks == 0:
            return None, "Ready", "—"

        cache_key = f"{region}:{interval}"
        if cache_key in _computed_cache:
            data, ts = _computed_cache[cache_key]
            return data, f"Loaded {len(data)} tickers from cache", ts

        tickers = get_universe(region)
        if not tickers:
            return None, "No tickers in region", "—"

        status_text = f"Fetching {len(tickers)} tickers…"
        logger.info(f"Starting refresh: {len(tickers)} tickers in {region}")

        # Fetch OHLCV data
        ohlcv_data = fetch_ohlcv(tickers, period="2y", interval="1d")

        # Score each ticker (RocketScore for ranking, dict for Dash)
        rocket_scores = []  # RocketScore dataclass objects for ranking
        all_score_dicts = []  # dicts for Dash storage
        for i, ticker in enumerate(tickers, 1):
            if ticker in ohlcv_data:
                df = ohlcv_data[ticker]
                rocket_score, score_dict = _score_ticker(ticker, df)
                rocket_scores.append(rocket_score)
                all_score_dicts.append(score_dict)

                # Save to parquet cache
                try:
                    save_ohlcv("/tmp/rocket-ohlcv", ticker, df)
                except Exception as e:
                    logger.debug(f"Save failed for {ticker}")

        # Rank regions using RocketScore objects
        region_scores = {region: rocket_scores}
        ranked = rank_regions(region_scores, top_n=20)
        top_all = top_overall(region_scores, top_n=20)

        # Convert ranked results to dicts for Dash storage
        ranked_dicts = [_rocket_to_dict(rs) for rs in ranked.get(region, [])]
        top_overall_dicts = [_rocket_to_dict(rs) for rs in top_all]

        # Build store data
        store_data = {
            "region": region,
            "ranked": ranked_dicts,
            "top_overall": top_overall_dicts,
            "tickers_fetched": len(ohlcv_data),
            "tickers_scored": len(all_score_dicts),
            "timestamp": datetime.now().isoformat(),
        }

        _computed_cache[cache_key] = (store_data, store_data["timestamp"])

        return (
            store_data,
            f"✓ {len(all_score_dicts)} tickers scored",
            f"Updated: {store_data['timestamp'][:19]}",
        )

    # ── Select ticker: show details ───────────────────────────────
    @app.callback(
        Output("candlestick-chart", "figure"),
        Output("score-breakdown", "children"),
        Input("ticker-dropdown", "value"),
        State("data-store", "data"),
    )
    def show_ticker_detail(ticker, store_data):
        from dash import dash_table
        from dash import dcc

        if not ticker or not store_data:
            return {}, "No data available"

        # Try to load data
        df = load_ohlcv("/tmp/rocket-ohlcv", ticker)
        if df is None and ticker in fetch_ohlcv([ticker], period="2y"):
            df = fetch_ohlcv([ticker], period="2y")[ticker]

        if df is None or df.empty:
            return {}, f"Ticker: {ticker}\nNo data available"

        # Build candlestick figure
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name="Candlestick"
        )])
        fig.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
        )

        # Find this ticker in store data
        for entry in store_data.get("ranked", []) + store_data.get("top_overall", []):
            if entry.get("ticker") == ticker:
                breakdown_text = (
                    f"Rocket Score: {entry['overall_score']:.1f}/100\n"
                    f"  Momentum:   {entry['momentum_score']:.1f}\n"
                    f"  Trend:      {entry['trend_score']:.1f}\n"
                    f"  Volatility: {entry['volatility_score']:.1f}\n"
                    f"  Volume:     {entry['volume_score']:.1f}\n"
                    f"  Buy: {entry['buy_count']} | Sell: {entry['sell_count']} | Hold: {entry['hold_count']}"
                )
                return fig, breakdown_text

        # If not in rankings, still show price info
        return fig, f"Ticker: {ticker}\nPrice: ${df['close'].iloc[-1]:.2f}"

    # ── Backtest: generate and show results ────────────────────────
    @app.callback(
        Output("equity-chart", "figure"),
        Output("bt-metrics", "children"),
        Input("strategy-dropdown", "value"),
        Input("ticker-dropdown", "value"),
        State("data-store", "data"),
    )
    def run_backtest(strategy, ticker, store_data):
        from dash import dcc
        import plotly.graph_objects as go

        if not ticker or not strategy:
            return {}, "Select a ticker and strategy"

        df = load_ohlcv("/tmp/rocket-ohlcv", ticker)
        if df is None or df.empty or len(df) < 60:
            return {}, "Not enough data for backtest"

        # Map dropdown strategy values to actual EMA crossover parameters
        strategy_map = {
            "buy_hold": ("buy_hold", 1, 1),    # special flag: no crossover
            "ema": ("ema", 9, 21),
            "rsi": ("rsi", 14, 21),            # placeholder EMA params for RSI backtest
            "combo": ("combo", 9, 21),
        }
        params = strategy_map.get(strategy, ("ema", 9, 21))
        strategy_type = params[0]
        fast_period = params[1]
        slow_period = params[2]

        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()

        # Generate signals
        cash = 100000.0
        position = 0
        equity_curve = [cash]
        dates = []
        commission = 0.001

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            close = row['close']
            date = row.name if hasattr(row.name, 'strftime') else str(row.name)

            if strategy_type == "buy_hold":
                # Buy immediately and hold
                if i == 1 and position == 0:
                    qty = int(cash * 0.99 / close)
                    if qty > 0:
                        cash -= qty * close * (1 + commission)
                        position = qty
            elif strategy_type == "rsi":
                # RSI mean-reversion: buy RSI<30, sell RSI>70
                delta = df['close'].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.finfo(float).eps)
                rsi = 100 - (100 / (1 + rs))
                rsi_val = rsi.iloc[i] if i < len(rsi) else 50

                if position == 0 and rsi_val < 30:
                    qty = int(cash * 0.95 / close)
                    if qty > 0:
                        cash -= qty * close * (1 + commission)
                        position = qty
                elif position > 0 and rsi_val > 70:
                    cash += position * close * (1 - commission)
                    position = 0
            else:
                # Normal EMA crossover (ema, combo)
                # Buy signal: fast crosses above slow
                if position == 0 and ema_fast.iloc[i] > ema_slow.iloc[i] and ema_fast.iloc[i - 1] <= ema_slow.iloc[i - 1]:
                    qty = int(cash * 0.95 / close)
                    if qty > 0:
                        cash -= qty * close * (1 + commission)
                        position = qty

                # Sell signal: fast crosses below slow
                elif position > 0 and ema_fast.iloc[i] < ema_slow.iloc[i] and ema_fast.iloc[i - 1] >= ema_slow.iloc[i - 1]:
                    cash += position * close * (1 - commission)
                    position = 0

            equity = cash + position * close
            equity_curve.append(equity)
            dates.append(date)

        # Build equity chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=equity_curve, mode='lines', name='Equity'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            template="plotly_dark",
            title=f"Backtest: {ticker} ({strategy})",
        )

        # Calculate metrics
        total_return = ((equity_curve[-1] - cash) / cash) * 100
        max_equity = max(equity_curve)
        max_drawdown = ((max_equity - min(equity_curve)) / max_equity) * 100 if max_equity > 0 else 0

        metrics_text = (
            f"Total Return: {total_return:.2f}%\n"
            f"Max Drawdown: {max_drawdown:.2f}%\n"
            f"Final Value: ${equity_curve[-1]:,.2f}\n"
            f"Initial Value: ${cash:,.2f}"
        )

        return fig, metrics_text

    # ── Sentiment: display news feed ───────────────────────────────
    @app.callback(
        Output("news-feed", "children"),
        Output("sentiment-score", "children"),
        Input("ticker-dropdown", "value"),
    )
    def show_news(ticker):
        if not ticker:
            return "No ticker selected", "—"

        # Fetch news via RSS
        try:
            import feedparser
            rss_url = f"https://feeds.financial.yahoo.com/rss/headline?s={ticker}"
            feed = feedparser.parse(rss_url)
            entries = feed.entries[:10]

            if not entries:
                return "No news articles found", "No data"

            items = []
            for entry in entries:
                items.append(f"• {entry.get('title', 'No title')[:100]}")

            # Simple sentiment score based on title keywords
            bullish = sum(1 for e in entries if any(w in e.get('title', '').lower() for w in ['upgrade', 'buy', 'growth', 'surge', 'profit', 'record']))
            bearish = sum(1 for e in entries if any(w in e.get('title', '').lower() for w in ['downgrade', 'sell', 'loss', 'decline', 'warning', 'risk']))
            total = len(entries)
            sentiment = ((bullish - bearish) / total * 100) if total > 0 else 0

            news_text = "\n".join(items) if items else "No news available"
            sentiment_text = f"Sentiment: {sentiment:+.0f}%"

            return news_text, sentiment_text

        except Exception as e:
            return f"Error fetching news: {e}", "Error"

    # ── Tab navigation ─────────────────────────────────────────────
    @app.callback(
        Output("main-tabs", "value"),
        Input("nav-dashboard", "n_clicks"),
        Input("nav-settings", "n_clicks"),
        State("main-tabs", "value"),
    )
    def navigate_tabs(nav_clicks, settings_clicks, current_tab):
        ctx = dash.callback_context
        if not ctx.triggered:
            return "tab-rankings"
        trigger = ctx.triggered[0]['prop_id']
        if 'nav-dashboard' in trigger:
            return "tab-detail"
        elif 'nav-settings' in trigger:
            return "tab-settings"
        return current_tab

    # ── Auto-refresh ───────────────────────────────────────────────
    @app.callback(
        Output("update-interval", "disabled"),
        Input("refresh-btn", "n_clicks"),
    )
    def toggle_auto_refresh(n_clicks):
        # Disable auto-refresh when user manually clicks refresh
        return n_clicks is not None and n_clicks > 0

    # ── Export scores to CSV ───────────────────────────────────────
    @app.callback(
        Output("data-store", "data", allow_duplicate=True),
        Input("export-btn", "n_clicks"),
        State("data-store", "data"),
        prevent_initial_call=True,
    )
    def export_scores(n_clicks, store_data):
        if not store_data or n_clicks is None:
            return store_data

        ranked = store_data.get("ranked", [])
        if not ranked:
            return store_data

        # Convert to DataFrame and save
        df = pd.DataFrame([
            {
                "ticker": s["ticker"],
                "overall_score": s["overall_score"],
                "momentum": s["momentum_score"],
                "trend": s["trend_score"],
                "volatility": s["volatility_score"],
                "volume": s["volume_score"],
                "buy": s["buy_count"],
                "sell": s["sell_count"],
                "hold": s["hold_count"],
                "filter_passed": s["filter_passed"],
            }
            for s in ranked
        ])

        export_path = f"/tmp/rocket-export-{store_data['region']}-{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(export_path, index=False)
        logger.info(f"Exported {len(df)} scores to {export_path}")

        return store_data

    # ── Top Signals: load from daily_signals.json ──────────────────
    @app.callback(
        Output("top-signals-status", "children"),
        Output("top-signals-content", "children"),
        Input("main-tabs", "active_tab"),
    )
    def load_top_signals(active_tab):
        """Load and display top signals from daily_signals.json."""
        if active_tab != "tab-top-signals":
            return "Not active", "Switch to this tab to view signals"

        signals_file = Path(__file__).parents[2] / "data" / "daily_signals.json"
        if not signals_file.exists():
            return "No data file found", html.P(
                "No daily_signals.json found. Run daily scoring to generate data.",
                className="text-muted text-center",
            )

        try:
            with open(signals_file, "r") as f:
                data = json.load(f)
            signals = data.get("signals", data.get("results", []))
        except Exception as e:
            return f"Error: {e}", html.P("Failed to load signals.", className="text-muted text-center")

        if not signals:
            return "No signals", html.P("No signals in data file.", className="text-muted text-center")

        # Sort by composite score
        signals = sorted(signals, key=lambda s: s.get("composite_score", 0), reverse=True)

        # Count signals
        buy_count = sum(1 for s in signals if s.get("signal") == "BUY")
        sell_count = sum(1 for s in signals if s.get("signal") == "SELL")
        hold_count = sum(1 for s in signals if s.get("signal") == "HOLD")
        total = len(signals)

        status = (
            f"Loaded {total} signals: "
            f"BUY: {buy_count} | SELL: {sell_count} | HOLD: {hold_count} | "
            f"Generated: {signals[0].get('timestamp', 'N/A')[:19]}"
        )

        # Build table
        cols = [{"name": str(k), "id": str(k)} for k in signals[0].keys()]
        import pandas as pd
        table = dbc.Table.from_dataframe(
            pd.DataFrame(signals),
            striped=True, dark=True, bordered=True, hover=True, responsive=True,
            style_header={"backgroundColor": "#16213e", "color": "#e0e0e0", "fontWeight": "bold"},
            style_cell={"backgroundColor": "#1a1a2e", "color": "#e0e0e0", "padding": "10px"},
        )

        return status, table
