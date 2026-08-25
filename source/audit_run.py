#!/usr/bin/env python3
"""Full audit runner: fetch AMC, run indicators, score, backtest, sentiment."""
import sys, os, traceback, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs('/tmp/rocket-audit', exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

results = {}

def section(name):
    log.info("="*60 + f"\n  {name}\n" + "="*60)

def mark(name, status, detail=""):
    results[name] = {'status': status, 'detail': detail}
    log.info(f"  [{status}] {name}: {detail}")

# ─── 1. FETCH ───
section("1. FETCH OHLCV — AMC")
try:
    from rocket.data.fetcher import fetch_ohlcv
    data = fetch_ohlcv(['AMC'], period='2y', interval='1d')
    if 'AMC' in data:
        df = data['AMC']
        info = f"OK | Shape={df.shape} | Range: {df['close'].min():.2f}-{df['close'].max():.2f} | NaN: {df.isna().sum().to_dict()}"
        mark("fetch-ohlcv", "PASS", info)
        results['_df_shape'] = df.shape
        results['_df_columns'] = list(df.columns)
    else:
        mark("fetch-ohlcv", "FAIL", f"Not in results. Keys: {list(data.keys())}")
        df = None
except Exception as e:
    mark("fetch-ohlcv", "FAIL", str(e))
    df = None

# ─── 2. UNIVERSE ───
section("2. UNIVERSE")
try:
    from rocket.data.universe import get_universe, get_all_universes, REGION_DEFAULTS
    for r in ['us', 'smid', 'eu', 'asia']:
        t = get_universe(r)
        log.info(f"  {r}: {len(t)} tickers, AMC: {'AMC' in t}")
    all_u = get_all_universes()
    info = f"regions: {list(all_u.keys())}, total: {sum(len(v) for v in all_u.values())}"
    mark("universe", "PASS", info)
except Exception as e:
    mark("universe", "FAIL", str(e))

# ─── 3. INDICATORS ───
if df is not None and len(df) > 50:
    section("3. INDICATORS (22 st) on AMC")
    try:
        from rocket.technical.momentum import RSI, MACD, Stochastic, WilliamsR, ROC, CCI
        from rocket.technical.trend import EMA9, EMA21, EMA50, EMA200, EMACrossover, ADX
        from rocket.technical.volatility import BollingerBands, ATR, DonchianChannel
        from rocket.technical.volume import OBV, MFI, VWAPIndicator
        from rocket.technical.advanced import IchimokuCloud, Supertrend, ParabolicSAR
        from rocket.technical.models import IndicatorResult
        from rocket.technical.signal_combiner import SignalCombiner

        indicators = [
            ('RSI', RSI()), ('MACD', MACD()), ('Stoch', Stochastic()),
            ('WilliamsR', WilliamsR()), ('ROC', ROC()), ('CCI', CCI()),
            ('EMA9', EMA9()), ('EMA21', EMA21()), ('EMA50', EMA50()), ('EMA200', EMA200()),
            ('EMACross', EMACrossover()), ('ADX', ADX()),
            ('BB', BollingerBands()), ('ATR', ATR()), ('Donchian', DonchianChannel()),
            ('OBV', OBV()), ('MFI', MFI()), ('VWAP', VWAPIndicator()),
            ('Ichimoku', IchimokuCloud()), ('Supertrend', Supertrend()),
            ('PSAR', ParabolicSAR()),
        ]
        
        ok_count = 0
        fail_count = 0
        failed_names = []
        sample_values = {}
        
        for name, ind in indicators:
            try:
                r = ind.calculate(df)
                if r and isinstance(r, IndicatorResult):
                    ok_count += 1
                    sample_values[name] = {
                        'signal': r.signal.value if hasattr(r, 'signal') else 'N/A',
                        'score': round(r.score, 2) if hasattr(r, 'score') else 'N/A'
                    }
                else:
                    fail_count += 1
                    failed_names.append(f"{name}: returned {type(r)}")
            except Exception as e:
                fail_count += 1
                failed_names.append(f"{name}: {e}")
        
        info = f"OK={ok_count}/{len(indicators)} Fail={fail_count}"
        if failed_names:
            info += f" | Failed: {failed_names}"
        mark("indicators", "PASS" if fail_count == 0 else "PARTIAL", info)
        results['_indicator_values'] = sample_values
        log.info(f"  Sample values: {sample_values}")
    except Exception as e:
        mark("indicators", "FAIL", f"{e}\n{traceback.format_exc()}")
else:
    mark("indicators", "BLOCKED", "No OHLCV data")

# ─── 4. SCORING ───
if df is not None and len(df) > 50:
    section("4. ROCKET SCORING — AMC")
    try:
        from rocket.data.models import TickerInfo, Region
        from rocket.data.fetcher import fetch_ohlcv
        from rocket.scoring.rocket_score import compute_rocket_score
        from rocket.scoring.weighter import weight_scores
        from rocket.scoring.filter import apply_filters
        from rocket.technical.signal_combiner import SignalCombiner
        
        ticker_info = TickerInfo(ticker='AMC')
        close_prices = df['close']
        current_price = float(close_prices.iloc[-1])
        avg_vol = float(df['volume'].mean()) if len(df) > 0 else 0.0
        ticker_info.avg_volume = avg_vol
        
        filter_result = apply_filters(ticker_info, current_price=current_price)
        log.info(f"  Filters: passed={filter_result.passed}, reasons={filter_result.reasons}")
        
        # Rebuild indicators
        from rocket.technical.momentum import RSI, MACD, Stochastic, WilliamsR, ROC, CCI
        from rocket.technical.trend import EMA9, EMA21, EMA50, EMA200, EMACrossover, ADX
        from rocket.technical.volatility import BollingerBands, ATR, DonchianChannel
        from rocket.technical.volume import OBV, MFI, VWAPIndicator
        from rocket.technical.advanced import IchimokuCloud, Supertrend, ParabolicSAR
        
        indicators = [
            RSI(), MACD(), Stochastic(), WilliamsR(), ROC(), CCI(),
            EMA9(), EMA21(), EMA50(), EMA200(), EMACrossover(), ADX(),
            BollingerBands(), ATR(), DonchianChannel(),
            OBV(), MFI(), VWAPIndicator(),
            IchimokuCloud(), Supertrend(), ParabolicSAR(),
        ]
        results_list = [ind.calculate(df) for ind in indicators]
        
        combiner = SignalCombiner()
        signal_summary = combiner.combine(results_list)
        log.info(f"  Signals: buy={signal_summary.buy_count}, sell={signal_summary.sell_count}, hold={signal_summary.hold_count}")
        
        rocket_score = weight_scores(signal_summary, filter_result, ticker='AMC')
        info = (
            f"OK | Overall={rocket_score.overall_score:.1f}/100 | "
            f"Momentum={rocket_score.momentum_score:.1f} | "
            f"Trend={rocket_score.trend_score:.1f} | "
            f"Volatility={rocket_score.volatility_score:.1f} | "
            f"Volume={rocket_score.volume_score:.1f} | "
            f"Buy={rocket_score.buy_count} Sell={rocket_score.sell_count} Hold={rocket_score.hold_count} | "
            f"FilterPassed={rocket_score.filter_passed} | "
            f"Region={rocket_score.region} Sector={rocket_score.sector}"
        )
        mark("scoring", "PASS", info)
    except Exception as e:
        mark("scoring", "FAIL", f"{e}\n{traceback.format_exc()}")

# ─── 5. SENTIMENT ───
section("5. SENTIMENT (RSS)")
try:
    import feedparser
    rss_url = "https://feeds.financial.yahoo.com/rss/headline?s=AMC"
    feed = feedparser.parse(rss_url)
    entries = feed.entries[:5]
    if entries:
        titles = [e.get('title', 'N/A') for e in entries]
        bullish = sum(1 for e in entries if any(w in e.get('title','').lower() for w in ['upgrade','buy','growth','surge','profit','record']))
        bearish = sum(1 for e in entries if any(w in e.get('title','').lower() for w in ['downgrade','sell','loss','decline','warning','risk']))
        total = len(entries)
        sentiment = ((bullish - bearish) / total * 100) if total > 0 else 0
        mark("sentiment-news", "PASS", f"{total} articles | bullish={bullish} bearish={bearish} | sentiment={sentiment:+.0f}%")
    else:
        mark("sentiment-news", "WARN", "No articles fetched (RSS may be down)")
except Exception as e:
    mark("sentiment-news", "FAIL", str(e))

# ─── 6. BACKTEST ───
if df is not None and len(df) > 60:
    section("6. BACKTEST — AMC EMA9/21")
    try:
        import plotly.graph_objects as go
        fast_period = 9
        slow_period = 21
        
        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
        
        cash = 100000.0
        position = 0
        equity_curve = [cash]
        commission = 0.001
        
        for i in range(1, len(df)):
            close = df.iloc[i]['close']
            
            if position == 0 and ema_fast.iloc[i] > ema_slow.iloc[i] and ema_fast.iloc[i-1] <= ema_slow.iloc[i-1]:
                qty = int(cash * 0.95 / close)
                if qty > 0:
                    cash -= qty * close * (1 + commission)
                    position = qty
            
            elif position > 0 and ema_fast.iloc[i] < ema_slow.iloc[i] and ema_fast.iloc[i-1] >= ema_slow.iloc[i-1]:
                cash += position * close * (1 - commission)
                position = 0
            
            equity = cash + position * close
            equity_curve.append(equity)
        
        total_return = ((equity_curve[-1] - cash) / cash) * 100
        max_equity = max(equity_curve)
        max_drawdown = ((max_equity - min(equity_curve)) / max_equity) * 100 if max_equity > 0 else 0
        
        # Buy & hold for comparison
        bh_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
        
        info = (
            f"OK | Strategy: {total_return:+.1f}% | Buy&Hold: {bh_return:+.1f}% | "
            f"MaxDD: {max_drawdown:.1f}% | Final: ${equity_curve[-1]:,.0f}"
        )
        mark("backtest-ema", "PASS", info)
    except Exception as e:
        mark("backtest-ema", "FAIL", f"{e}\n{traceback.format_exc()}")

# ─── 7. DATA STORAGE ───
section("7. DATA STORAGE")
try:
    from rocket.data.storage import save_ohlcv, load_ohlcv
    save_ohlcv('/tmp/rocket-audit', 'AMC', df)
    loaded = load_ohlcv('/tmp/rocket-audit', 'AMC')
    if loaded is not None and len(loaded) > 0:
        info = f"OK | Saved {len(loaded)} rows, reloaded {len(loaded)} rows"
        mark("storage", "PASS", info)
    else:
        mark("storage", "FAIL", "Reloaded data is None or empty")
except Exception as e:
    mark("storage", "FAIL", str(e))

# ─── SUMMARY ───
section("AUDIT SUMMARY")
for k, v in results.items():
    if not k.startswith('_'):
        log.info(f"  [{v['status']}] {k}: {v['detail']}")

# Save summary
with open('/tmp/rocket-audit/summary.json', 'w') as f:
    import json
    json.dump(results, f, indent=2, default=str)
log.info("\nAudit complete. Summary saved to /tmp/rocket-audit/summary.json")
