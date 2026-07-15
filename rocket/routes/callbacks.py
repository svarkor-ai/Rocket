"""Dash callbacks for Rocket Stock Scanner."""
import logging
from datetime import datetime
from dash.dependencies import Input, Output, State
import dash
import pandas as pd
import numpy as np

from rocket.data.fetcher import fetch_ohlcv
from rocket.data.universe import get_universe
from rocket.data.storage import save_ohlcv, load_ohlcv, needs_update
from rocket.data.models import TickerInfo, Region
from rocket.scoring.rocket_score import compute_rocket_score
from rocket.scoring.ranking import rank_regions, top_overall
from rocket.scoring.filter import apply_filters
from rocket.technical.signal_combiner import SignalCombiner
from rocket.technical.momentum import RSI, MACD, Stochastic, WilliamsR, ROC, CCI
from rocket.technical.trend import EMA9, EMA21, EMA50, EMA200, EMACrossover, ADX
from rocket.technical.volatility import BollingerBands, ATR, DonchianChannel
from rocket.technical.volume import OBV, MFI, VWAPIndicator
from rocket.technical.advanced import IchimokuCloud, Supertrend, ParabolicSAR

logger = logging.getLogger(__name__)

# Cache for computed data
_computed_cache: dict = {}


def _build_indicator_results(df: pd.DataFrame) -> list:
    """Run all indicators on OHLCV data, return list of IndicatorResults."""
    indicators = [
        RSI(), MACD(), Stochastic(), WilliamsR(), ROC(), CCI(),
        EMA9(), EMA21(), EMA50(), EMA200(), EMACrossover(), ADX(),
        BollingerBands(), ATR(), DonchianChannel(),
        OBV(), MFI(), VWAPIndicator(),
        IchimokuCloud(), Supertrend(), ParabolicSAR(),
    ]
    results = []
    for ind in indicators:
        try:
            r = ind.calculate(df)
            results.append(r)
        except Exception as e:
            logger.warning(f"Indicator {ind.name if hasattr(ind, 'name') else 'unknown'} failed: {e}")
    return results


def _score_ticker(ticker: str, df: pd.DataFrame) -> dict:
    """Score a single ticker, return dict with scores and details."""
    ticker_info = TickerInfo(ticker=ticker)
    close_prices = df['close']
    current_price = float(close_prices.iloc[-1])
    avg_vol = float(df['volume'].mean()) if len(df) > 0 else 0.0
    ticker_info.avg_volume = avg_vol

    filter_result = apply_filters(ticker_info, current_price=current_price)
    results = _build_indicator_results(df)
    combiner = SignalCombiner()
    signal_summary = combiner.combine(results)

    # Import weighter with correct path
    from rocket.scoring.weighter import weight_scores
    rocket_score = weight_scores(signal_summary, filter_result, ticker=ticker)

    return {
        "ticker": ticker,
        "overall_score": rocket_score.overall_score,
        "momentum_score": rocket_score.momentum_score,
        "trend_score": rocket_score.trend_score,
        "volatility_score": rocket_score.volatility_score,
        "volume_score": rocket_score.volume_score,
        "buy_count": rocket_score.buy_count,
        "sell_count": rocket_score.sell_count,
        "hold_count": rocket_score.hold_count,
        "filter_passed": rocket_score.filter_passed,
        "filter_reasons": rocket_score.filter_result.reasons,
        "region": rocket_score.region,
        "sector": rocket_score.sector,
        "current_price": current_price,
        "avg_volume": avg_vol,
        "details": rocket_score.filter_result.reasons,
    }


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

        # Score each ticker
        all_scores = []
        for i, ticker in enumerate(tickers, 1):
            if ticker in ohlcv_data:
                df = ohlcv_data[ticker]
                score = _score_ticker(ticker, df)
                all_scores.append(score)

                # Save to parquet cache
                try:
                    save_ohlcv("/tmp/rocket-ohlcv", ticker, df)
                except Exception as e:
                    logger.debug(f"Save failed for {ticker}: {e}")

        # Rank regions
        region_scores = {region: all_scores}
        ranked = rank_regions(region_scores, top_n=20)
        top_all = top_overall(region_scores, top_n=20)

        # Build store data
        store_data = {
            "region": region,
            "ranked": [s for s in ranked.get(region, [])],
            "top_overall": [s for s in top_all],
            "tickers_fetched": len(ohlcv_data),
            "tickers_scored": len(all_scores),
            "timestamp": datetime.now().isoformat(),
        }

        _computed_cache[cache_key] = (store_data, store_data["timestamp"])

        return (
            store_data,
            f"✓ {len(all_scores)} tickers scored",
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
        if df is None and ticker in fetch_ohlcv([ticker]):
            df = fetch_ohlcv([ticker])[ticker]

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

        # Simple moving average crossover strategy
        fast_period = int(strategy.split(":")[0]) if ":" in strategy else 9
        slow_period = int(strategy.split(":")[1]) if ":" in strategy else 21

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
