"""Quick script to fetch data and compute rocket scores for a set of tickers."""
import sys
import os
import json
import time
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, '/home/svarkor/svarkor/builds/rocket-stock-scanner')
os.chdir('/home/svarkor/svarkor/builds/rocket-stock-scanner')

from rocket.data.universe import get_universe, get_all_tickers, REGIONS
from rocket.data import fetch_ohlcv
from rocket.data.models import TickerInfo, Region
from rocket.scoring.rocket_score import compute_rocket_score

def ticker_to_region(ticker: str) -> str:
    """Determine region from ticker suffix."""
    if ticker.endswith('.ST') or '-' in ticker:  # Swedish suffix or Swedish-style
        return 'sweden'
    if ticker.endswith('.SS') or ticker.endswith('.SZ'):
        return 'china'
    if ticker.endswith('.HK'):
        return 'china'
    if ticker.endswith('.NS'):
        return 'india'
    # USA tickers have no suffix or US-style suffixes like .DE .PA
    return 'usa'

def get_region_str(ticker: str) -> str:
    """Map region to string."""
    r = ticker_to_region(ticker)
    if r == 'sweden':
        return 'sweden'
    elif r == 'usa':
        return 'us'
    elif r == 'china':
        return 'china'
    elif r == 'india':
        return 'india'
    return 'us'

def get_sector(ticker: str, region: str) -> str:
    """Simplified sector based on ticker."""
    return "N/A"

def main():
    # Limit to a reasonable subset for the first run
    # Start with USA large cap + some Sweden tickers
    us_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD',
                  'AAPL', 'AAP', 'ABBV', 'ABT', 'ADBE', 'ADI', 'AEP', 'AFL', 'AIG',
                  'AMGN', 'AMZN', 'ANSS', 'AXP', 'BA', 'BAC', 'BBY', 'BMY', 'BRK-B',
                  'CAT', 'CCI', 'CDNS', 'CDW', 'CEG', 'CHD', 'CINF', 'CL', 'CMG',
                  'CME', 'COP', 'COST', 'CRM', 'CSCO', 'CTAS', 'CVS', 'D', 'DASH',
                  'DE', 'DIS', 'DXCM', 'EA', 'EBAY', 'EMN', 'ETN', 'EW', 'EXC',
                  'FAST', 'FDX', 'FISV', 'FLT', 'FRC', 'FTNT', 'GD', 'GE', 'GILD',
                  'GIS', 'GPC', 'GPN', 'GS', 'HAL', 'HON', 'HPE', 'IBM', 'ICE',
                  'IDXX', 'INTU', 'IP', 'IPG', 'ISG', 'JNJ', 'JPM', 'KDP', 'KEY',
                  'KHC', 'KMI', 'KR', 'LMT', 'LRCX', 'LLY', 'LOW', 'LULU', 'LUV',
                  'MA', 'MAR', 'MCD', 'MCHP', 'MCO', 'MDLZ', 'MDT', 'MPC', 'MRVL',
                  'MSFT', 'MU', 'NEM', 'NEE', 'NFLX', 'NKE', 'NOC', 'NOW', 'ORCL',
                  'ORLY', 'OTIS', 'PANW', 'PAYC', 'PCG', 'PEP', 'PFE', 'PG', 'PGR',
                  'PPL', 'PSA', 'PYPL', 'REGN', 'RF', 'RMD', 'ROP', 'ROST', 'RTX',
                  'SBUX', 'SCHW', 'SNPS', 'SPG', 'SWK', 'SYK', 'TDG', 'TER', 'TGT',
                  'TJX', 'TMO', 'TPR', 'TRV', 'TT', 'TTWO', 'TXN', 'UAL', 'UDR',
                  'V', 'VICI', 'VNO', 'VMC', 'VRSN', 'WAB', 'WDAY', 'WFC', 'WM',
                  'WMT', 'XEL', 'ZBRA', 'ZBH', 'ZTS']
    
    swedish_tickers = ['ASSA-B', 'ATCO-A', 'AXA', 'BEKOA', 'BOLB', 'CAST', 'ELMOB',
                       'EQT', 'ESSITY-B', 'GETINGE', 'HUSQVARNB', 'ISSB', 'ITAB',
                       'KINNEVIK-B', 'KORSN-B', 'MIND', 'NIBE', 'NORDEA', 'PEAB',
                       'PEPP', 'PINEB', 'SCA-B', 'SEB-A', 'SEB-B', 'SELSB', 'SKF-B',
                       'SKILB', 'SKOLDB', 'STHCB', 'SWECHO', 'SWEDB', 'SWEDMON',
                       'TORN-B', 'TELIA', 'TEL2B', 'TSLB', 'TUCAB', 'VOLV-B']
    
    # Combine
    tickers_to_analyze = list(set(us_tickers + swedish_tickers))
    print(f"Total tickers to analyze: {len(tickers_to_analyze)}")
    
    # Fetch OHLCV data
    print("\nFetching OHLCV data...")
    start_time = time.time()
    ohlcv_data = fetch_ohlcv(tickers_to_analyze, period="5y", interval="1d")
    fetch_time = time.time() - start_time
    print(f"Fetch completed in {fetch_time:.1f}s — got {len(ohlcv_data)} tickers")
    
    # Compute scores
    print("\nComputing rocket scores...")
    scores = []
    failures = []
    score_start = time.time()
    
    for ticker, df in ohlcv_data.items():
        if len(df) < 50:
            continue
            
        region_str = get_region_str(ticker)
        region_enum = Region.US  # default
        if region_str == 'sweden':
            region_enum = Region.US  # need to check
        elif region_str == 'china':
            region_enum = Region.US
        elif region_str == 'india':
            region_enum = Region.US
        else:
            region_enum = Region.US
            
        try:
            ticker_info = TickerInfo(
                ticker=ticker,
                region=region_enum,
                sector=get_sector(ticker, region_str)
            )
            
            current_price = float(df['close'].iloc[-1])
            result = compute_rocket_score(df, ticker_info, current_price)
            
            overall = result['rocket_score'].overall_score
            
            scores.append({
                'ticker': ticker,
                'score': round(overall, 2),
                'region': region_str,
                'sector': ticker_info.sector,
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
            failures.append((ticker, str(e)))
            
    score_time = time.time() - score_start
    print(f"Score computation completed in {score_time:.1f}s")
    print(f"Success: {len(scores)}, Failures: {len(failures)}")
    
    # Sort by score descending
    scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Print top 20
    print("\n" + "="*80)
    print("TOP 20 ROCKET SCORES")
    print("="*80)
    print(f"{'Rank':<5}{'Ticker':<15}{'Score':<8}{'Momentum':<10}{'Trend':<10}{'Vol':<8}{'Volume':<8}{'Buy/Sell/Hold':<20}{'Filter':<10}{'Region':<10}")
    print("-"*80)
    
    for i, s in enumerate(scores[:20], 1):
        bs = f"{s['buy_count']}/{s['sell_count']}/{s['hold_count']}"
        print(f"{i:<5}{s['ticker']:<15}{s['score']:<8.2f}{s['momentum']:<10.1f}{s['trend']:<10.1f}{s['volatility']:<8.1f}{s['volume']:<8.1f}{bs:<20}{str(s['filter_passed']):<10}{s['region']:<10}")
    
    # Save full results
    output_path = '/home/svarkor/svarkor/builds/rocket-stock-scanner/data/scores/top_scores.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    output = {
        'generated_at': datetime.now().isoformat(),
        'total_analyzed': len(scores),
        'total_failures': len(failures),
        'fetch_seconds': fetch_time,
        'score_seconds': score_time,
        'top_10': scores[:10],
        'all_scores': scores
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nFull results saved to {output_path}")
    
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for t, e in failures[:10]:
            print(f"  {t}: {e}")

if __name__ == "__main__":
    main()
