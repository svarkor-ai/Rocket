#!/usr/bin/env python3
"""
Backtest engine — RSI(14) + MACD(12,26,9) + OBV across 25k tickers.
Buys when RSI<30 & MACD-signal>histogram; sells when RSI>70 or after 5 days.
Costs: 0.1% commission + 0.05% slippage.

Data quality filters applied:
  - Reject files with <50 rows
  - Reject files with >3% of days having >100% absolute price moves
  - Reject files where max single-day move >500%
  - Reject files where price range (max/min) > 100x (split/capital change indicator)
"""
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger('backtest_all')

BASE_DIR = Path(__file__).resolve().parent
OHLCV_DIR = BASE_DIR / 'data' / 'ohlcv'
OUTPUT_PATH = BASE_DIR / 'data' / 'backtest_results.json'

COMMISSION = 0.001
SLIPPAGE = 0.0005
HOLD_DAYS = 5

RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

BUY_RSI = 30
SELL_RSI = 70


def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0.0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.finfo(float).eps)
    return 100.0 - (100.0 / (1.0 + rs))


def compute_macd(close):
    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _execute_trade(entry_price, exit_price, entry_date, exit_date):
    if entry_price <= 0 or exit_price <= 0:
        return None
    effective_entry = entry_price * (1 + SLIPPAGE + COMMISSION)
    effective_exit = exit_price * (1 - SLIPPAGE - COMMISSION)
    raw_ret = (effective_exit - effective_entry) / effective_entry * 100.0
    return {
        'entry_date': entry_date,
        'exit_date': exit_date,
        'entry_price': round(entry_price, 4),
        'exit_price': round(exit_price, 4),
        'raw_return_pct': round(raw_ret, 4),
    }


def backtest_ticker(df, rsi, macd_line, signal_line, histogram):
    n = len(df)
    trades = []
    min_idx = max(RSI_PERIOD, MACD_SLOW) + HOLD_DAYS + 2
    if min_idx >= n:
        return trades
    in_position = False
    entry_price = 0.0
    entry_date = ''
    for i in range(min_idx, n):
        cur_rsi = rsi.iloc[i]
        cur_signal = signal_line.iloc[i]
        cur_hist = histogram.iloc[i]
        if pd.isna(cur_rsi) or pd.isna(cur_signal) or pd.isna(cur_hist):
            continue
        if not in_position:
            if cur_rsi < BUY_RSI and cur_signal > cur_hist:
                entry_price = df['Close'].iloc[i]
                entry_date = df.index[i].strftime('%Y-%m-%d')
                in_position = True
        else:
            if i - min_idx >= HOLD_DAYS or cur_rsi > SELL_RSI:
                exit_price = df['Close'].iloc[i]
                exit_date = df.index[i].strftime('%Y-%m-%d')
                if entry_price > 0 and exit_price > 0:
                    trade = _execute_trade(entry_price, exit_price, entry_date, exit_date)
                    if trade is not None:
                        trades.append(trade)
                in_position = False
    return trades


def calc_metrics(trades):
    if not trades:
        return {'total_return': 0.0, 'win_rate': 0.0, 'max_drawdown': 0.0,
                'sharpe_ratio': 0.0, 'total_trades': 0}
    returns = np.array([t['raw_return_pct'] for t in trades])
    # Cap extreme returns at +/-200% to prevent blow-up from bad data
    returns = np.clip(returns, -99.5, 199.5)
    compound = 1.0
    for r in returns:
        compound *= (1 + r / 100.0)
    total_return = (compound - 1) * 100.0
    wins = int(np.sum(returns > 0))
    win_rate = wins / len(returns) * 100.0
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100.0))
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
    sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) >= 2 and np.std(returns) > 0 else 0.0
    return {
        'total_return': round(total_return, 2),
        'win_rate': round(win_rate, 2),
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': round(sharpe, 4),
        'total_trades': len(trades),
    }


def load_ohlcv(filepath):
    import pyarrow.parquet as pq
    basename = os.path.basename(filepath)
    ticker = os.path.splitext(basename)[0]
    try:
        pf = pq.read_table(filepath)
        df = pf.to_pandas()
    except Exception:
        return None
    col_map = {}
    has_tuples = any(isinstance(c, tuple) for c in df.columns)
    for c in df.columns:
        name = c[0] if isinstance(c, tuple) else str(c)
        cl = name.lower().strip()
        if 'close' in cl: col_map[c] = 'Close'
        elif 'open' in cl: col_map[c] = 'Open'
        elif 'high' in cl: col_map[c] = 'High'
        elif 'low' in cl: col_map[c] = 'Low'
        elif 'volume' in cl: col_map[c] = 'Volume'
    if col_map:
        if has_tuples:
            new_df = pd.DataFrame()
            for old_c, new_c in col_map.items():
                new_df[new_c] = df[old_c]
            new_df.index = df.index
            df = new_df
        else:
            df = df.rename(columns=col_map)
    if not all(c in df.columns for c in ['Open','High','Low','Close','Volume']):
        return None
    df = df.sort_index()
    if len(df) < 50:
        return None
    # --- DATA QUALITY FILTERS ---
    pct_change = df['Close'].pct_change().dropna()
    if len(pct_change) < 20:
        return None
    # Filter 1: Reject if >3% of days have >100% absolute moves
    extreme_ratio = (pct_change.abs() > 1.0).sum() / len(pct_change)
    if extreme_ratio > 0.03:
        return None
    # Filter 2: Reject if any single day has >500% move
    max_move = pct_change.abs().max()
    if max_move > 5.0:
        return None
    # Filter 3: Reject if price range (max/min) > 100x
    close_min = df['Close'].clip(lower=0.001).min()
    close_max = df['Close'].max()
    price_range = close_max / close_min if close_min > 0 else 999.0
    if price_range > 100.0:
        return None
    return df, ticker


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not OHLCV_DIR.is_dir():
        logger.error('OHLCV dir not found: %s', OHLCV_DIR)
        sys.exit(1)
    parquet_files = sorted([str(OHLCV_DIR / f) for f in os.listdir(OHLCV_DIR) if f.endswith('.parquet')])
    total_files = len(parquet_files)
    logger.info('Found %d parquet files in %s', total_files, OHLCV_DIR)
    results = {'tickers': {}, 'aggregate': {}}
    processed = skipped = errors = 0
    data_filtered = 0  # track how many were rejected by quality filters
    all_metrics = []
    for fpath in parquet_files:
        maybe = load_ohlcv(fpath)
        if maybe is None:
            skipped += 1
            continue
        df, ticker = maybe
        # Check if it passed quality filters (load_ohlcv returns None if not)
        # If we got here, it passed — but let's track how many were filtered
        processed += 1
        try:
            close = df['Close']
            rsi = compute_rsi(close)
            macd_line, signal_line, histogram = compute_macd(close)
            trades = backtest_ticker(df, rsi, macd_line, signal_line, histogram)
            metrics = calc_metrics(trades)
            all_metrics.append((ticker, metrics))
        except Exception as e:
            errors += 1
            logger.error('Error processing %s: %s', ticker, e)
            metrics = {'total_return': 0.0, 'win_rate': 0.0, 'max_drawdown': 0.0,
                       'sharpe_ratio': 0.0, 'total_trades': 0}
        results['tickers'][ticker] = metrics
        if processed % 1000 == 0:
            logger.info('Processed %d / %d files (skipped=%d errors=%d) ...', processed, total_files, skipped, errors)
    all_returns = [m[1]['total_return'] for m in all_metrics]
    all_win_rates = [m[1]['win_rate'] for m in all_metrics]
    profitable = sum(1 for r in all_returns if r > 0)
    sorted_metrics = sorted(all_metrics, key=lambda x: x[1]['total_return'], reverse=True)
    results['aggregate'] = {
        'total_tickers': len(all_metrics),
        'total_files': total_files,
        'files_skipped': skipped,
        'files_processed': processed,
        'files_filtered_quality': skipped - errors,  # approximate
        'avg_return': round(float(np.mean(all_returns)) if all_returns else 0.0, 2),
        'median_return': round(float(np.median(all_returns)) if all_returns else 0.0, 2),
        'avg_win_rate': round(float(np.mean(all_win_rates)) if all_win_rates else 0.0, 2),
        'percent_profitable': round(profitable / len(all_metrics) * 100 if all_metrics else 0.0, 2),
        'top_20': [{'ticker': t, **m} for t, m in sorted_metrics[:20]],
        'bottom_20': [{'ticker': t, **m} for t, m in sorted_metrics[-20:]],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info('Results written to %s', OUTPUT_PATH)
    agg = results['aggregate']
    print()
    print('=' * 60)
    print('BACKTEST SUMMARY')
    print('=' * 60)
    print(f'Total parquet files: {agg["total_files"]}')
    print(f'Tickers processed: {agg["files_processed"]}')
    print(f'Tickers filtered (quality): {agg["files_filtered_quality"]}')
    print(f'Files errored: {agg["files_skipped"] - agg["files_filtered_quality"]}')
    print(f'Average return: {agg["avg_return"]:>+12.4f}%')
    print(f'Median return: {agg["median_return"]:>+12.4f}%')
    print(f'Average win rate: {agg["avg_win_rate"]:.1f}%')
    print(f'% profitable: {agg["percent_profitable"]:.1f}%')
    print()
    print('TOP 10 PERFORMERS:')
    print('-' * 60)
    hdr = f'{"Ticker":<12} {"Return":>12} {"Win%":>7} {"Trades":>6} {"Sharpe":>8}'
    print(hdr)
    print('-' * 60)
    for t, m in sorted_metrics[:10]:
        print(f'{t:<12} {m["total_return"]:>+11.2f}% {m["win_rate"]:>6.1f}% {m["total_trades"]:>4} {m["sharpe_ratio"]:>8.3f}')
    print('=' * 60)


if __name__ == '__main__':
    main()