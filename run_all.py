"""Full script to fetch data and compute rocket scores for ALL tickers."""
import sys
import os
import json
import time
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, '/home/svarkor/svarkor/builds/rocket-stock-scanner')
os.chdir('/home/svarkor/svarkor/builds/rocket-stock-scanner')

from rocket.data.universe import get_universe, get_all_tickers, REGIONS, get_region_count
from rocket.data import fetch_ohlcv
from rocket.data.models import TickerInfo, Region
from rocket.scoring.rocket_score import compute_rocket_score
from rocket.technical.models import SignalCategory

# Map region enum to string
REGION_MAP = {
    'sweden': (Region.US, 'sweden'),
    'usa': (Region.US, 'us'),
    'china': (Region.US, 'china'),
    'india': (Region.US, 'india'),
}

def get_ticker_region(ticker: str) -> str:
    """Determine region from ticker."""
    if ticker.endswith('.ST') or (not any(ticker.endswith(s) for s in ['.SS', '.SZ', '.HK', '.NS', '.AX', '.DE', '.PA', '.AS', '.BR', '.MD', '.FI', '.CO', '.OS', '.SA', '.KH', '.TO', '.KS', '.TW', '.BA']) and '-' in ticker):
        return 'sweden'
    if ticker.endswith('.SS') or ticker.endswith('.SZ'):
        return 'china'
    if ticker.endswith('.HK'):
        return 'china'
    if ticker.endswith('.NS'):
        return 'india'
    return 'usa'

def get_region_for_ticker(ticker: str):
    """Get (region_enum, region_str) for a ticker."""
    r = get_ticker_region(ticker)
    # We need to check the actual Region enum values
    return r

def main():
    print("="*60)
    print("ROCKET SCANNER — FULL UNIVERSE ANALYSIS")
    print("="*60)
    
    # Get all tickers
    all_tickers = get_all_tickers()
    region_counts = get_region_count()
    print(f"\nTotal tickers: {len(all_tickers)}")
    print(f"By region: {region_counts}")
    
    # Fetch OHLCV data for ALL tickers
    print("\nFetching OHLCV data for all tickers...")
    print("(This may take 10-15 minutes...)")
    start_time = time.time()
    
    # yfinance can handle multiple tickers at once, but let's do batches
    # to avoid rate limits
    batch_size = 50
    all_data = {}
    
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        print(f"  Batch {i//batch_size + 1} ({len(batch)} tickers)...")
        try:
            batch_data = fetch_ohlcv(batch, period="5y", interval="1d")
            all_data.update(batch_data)
        except Exception as e:
            print(f"    Error in batch: {e}")
        time.sleep(0.5)  # Be nice to Yahoo
    
    fetch_time = time.time() - start_time
    print(f"\nFetch completed in {fetch_time:.1f}s — got {len(all_data)} tickers")
    
    # Compute scores
    print("\nComputing rocket scores...")
    print("(This may take 5-10 minutes...)")
    scores = []
    failures = []
    no_data = []  # tickers with insufficient data
    
    score_start = time.time()
    total = len(all_data)
    
    for idx, (ticker, df) in enumerate(all_data.items(), 1):
        if idx % 25 == 0:
            print(f"  Progress: {idx}/{total} ({idx*100//total}%)")
        
        if len(df) < 50:
            no_data.append((ticker, len(df)))
            continue
            
        region_str = get_ticker_region(ticker)
        
        try:
            ticker_info = TickerInfo(
                ticker=ticker,
                region=Region.US,  # all regions use same enum for now
                sector="N/A"
            )
            
            current_price = float(df['close'].iloc[-1])
            result = compute_rocket_score(df, ticker_info, current_price)
            
            overall = result['rocket_score'].overall_score
            
            scores.append({
                'ticker': ticker,
                'score': round(overall, 2),
                'region': region_str,
                'sector': 'N/A',
                'momentum': result['rocket_score'].momentum_score,
                'trend': result['rocket_score'].trend_score,
                'volatility': result['rocket_score'].volatility_score,
                'volume': result['rocket_score'].volume_score,
                'buy_count': result['rocket_score'].buy_count,
                'sell_count': result['rocket_score'].sell_count,
                'hold_count': result['rocket_score'].hold_count,
                'filter_passed': result['rocket_score'].filter_passed,
                'rows': len(df)
            })
        except Exception as e:
            failures.append((ticker, str(e)[:100]))
            
    score_time = time.time() - score_start
    print(f"\nScore computation completed in {score_time:.1f}s")
    print(f"Success: {len(scores)}, Failures: {len(failures)}, Low data: {len(no_data)}")
    
    # Sort by score descending
    scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Print top 20
    print("\n" + "="*90)
    print("TOP 20 ROCKET SCORES (FULL UNIVERSE)")
    print("="*90)
    print(f"{'Rank':<5}{'Ticker':<18}{'Score':<8}{'Momentum':<10}{'Trend':<10}{'Vol':<8}{'Volume':<8}{'Buy/Sell/Hold':<18}{'Filter':<10}{'Region':<12}")
    print("-"*90)
    
    for i, s in enumerate(scores[:20], 1):
        bs = f"{s['buy_count']}/{s['sell_count']}/{s['hold_count']}"
        print(f"{i:<5}{s['ticker']:<18}{s['score']:<8.2f}{s['momentum']:<10.1f}{s['trend']:<10.1f}{s['volatility']:<8.1f}{s['volume']:<8.1f}{bs:<18}{str(s['filter_passed']):<10}{s['region']:<12}")
    
    # Save full results
    output_path = '/home/svarkor/svarkor/builds/rocket-stock-scanner/data/scores/full_scores.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_in_universe': len(all_tickers),
        'total_analyzed': len(scores),
        'total_failures': len(failures),
        'total_low_data': len(no_data),
        'fetch_seconds': round(fetch_time, 1),
        'score_seconds': round(score_time, 1),
        'top_10': scores[:10],
        'top_20': scores[:20],
        'all_scores': scores
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nFull results saved to {output_path}")
    
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for t, e in failures[:10]:
            print(f"  {t}: {e}")
    
    if no_data:
        print(f"\nLow data tickers (< 50 rows): {len(no_data)}")
        for t, rows in no_data[:10]:
            print(f"  {t}: {rows} rows")

if __name__ == "__main__":
    main()
