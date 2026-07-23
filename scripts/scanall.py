"""Full universe scan — batch download for liveness, history for scoring.
Phase 1: yf.download() batch → detect live tickers
Phase 2: Sequential history() with retry + delay → compute scores
Phase 3: Save to SQLite + send to Telegram
"""
import sys, os, time, logging, asyncio, warnings, threading
from datetime import datetime, timezone
from pathlib import Path

# Suppress all warnings and noise
warnings.filterwarnings('ignore')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(message)s', force=True)

# Force file logging (works even when stdout is not a tty)
LOG_FILE = '/tmp/scanall.log'
_log_fh = open(LOG_FILE, 'a')

def _log(msg, flush=True):
    _log_fh.write(str(msg) + '\n')
    if flush:
        _log_fh.flush()

# Patch print to also write to log file
_orig_print = print
def _print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    _log(' '.join(str(a) for a in args), flush=kwargs.get('flush', True))
print = _print

sys.path.insert(0, '/srv/svarkor/builds/rocket-stock-scanner')
os.chdir('/srv/svarkor/builds/rocket-stock-scanner')

import yfinance as yf
import pandas as pd

from rocket.data.models import TickerInfo, Region
from rocket.data.universe_builder import get_universe
from rocket.scoring.rocket_score import compute_rocket_score
from dotenv import load_dotenv
from telegram import Bot

# Load config: try scan_pro.env first, fall back to main .env
load_dotenv('config/scan_pro.env')
BOT_TOKEN = os.environ.get('SCAN_PRO_TELEGRAM_BOT_TOKEN', '')
if not BOT_TOKEN:
    load_dotenv('/home/svarkor/.hermes/.env')
    BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

ADMIN_CHAT_ID = int(os.environ.get('SCAN_PRO_ADMIN_CHAT_ID', '7228171084'))

REGION_MAP = {
    'usa': Region.US, 'sweden': Region.EU, 'norway': Region.EU,
    'denmark': Region.EU, 'finland': Region.EU, 'germany': Region.EU,
    'france': Region.EU, 'other_eu': Region.EU,
    'uk': Region.US, 'australia': Region.US, 'canada': Region.US,
    'japan': Region.ASIA, 'hongkong': Region.ASIA, 'china': Region.ASIA,
    'india': Region.ASIA, 'korea': Region.ASIA, 'switzerland': Region.EU,
    'international': Region.US,
}

def is_real_ticker(ticker: str) -> bool:
    t = ticker.strip()
    if not t or len(t) == 1:
        return False
    if t.isdigit() or all(c.isdigit() or c == '.' for c in t):
        return False
    if t.startswith(('05', '10')) and len(t) >= 8 and not any(c.isalpha() for c in t[2:]):
        return False
    if t.startswith(('198', '199')) and len(t) >= 6:
        if len(t) <= 8 and not any(c.isalpha() for c in t[3:]):
            return False
    return True


def _fetch_with_thread_timeout(ticker, timeout):
    """Fetch history with hard timeout using threading."""
    result = [None]
    error = [None]
    def _fetch():
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period='3mo', interval='1d', timeout=8)
            result[0] = df
        except Exception as e:
            error[0] = e
    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return None  # timed out
    if error[0]:
        raise error[0]
    return result[0]

def fetch_history_with_retry(ticker, max_retries=3, base_delay=1.0):
    """Fetch 3mo history with hard thread timeout and backoff."""
    for attempt in range(max_retries):
        try:
            df = _fetch_with_thread_timeout(ticker, timeout=12)
            if df is not None and not df.empty:
                return df
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
    return None


def scan_single_ticker(region: str, ticker: str):
    """Scan one live ticker. Returns (ticker, signal, score, regime, buy_count, sell_count, reason) or None."""
    try:
        region_enum = REGION_MAP.get(region, Region.US)
        
        # Fetch history with retry
        df = fetch_history_with_retry(ticker)
        if df is None or df.empty or len(df) < 50:
            return None
        
        df = df.tail(60)
        if 'Close' not in df.columns:
            return None
        
        close_series = df['Close'].astype(float)
        if close_series.isna().all():
            return None
        close_series = close_series[close_series > 0]
        if len(close_series) < 50:
            return None
        
        price = float(close_series.iloc[-1])
        vol = df.get('Volume', pd.Series([0] * len(df)))
        avg_vol = float(vol.mean())
        
        info = {}
        try:
            stock = yf.Ticker(ticker)
            # Hard timeout for info fetch (prevents hanging forever)
            result = [None]
            def _fetch_info():
                try:
                    result[0] = (stock.info or {})
                except:
                    result[0] = {}
            t = threading.Thread(target=_fetch_info, daemon=True)
            t.start()
            t.join(timeout=5)
            info = result[0] if t.is_alive() else {}
        except Exception:
            info = {}
        
        name = info.get('shortName', '') or info.get('longName', ticker)
        sector = info.get('sector', 'Unknown')
        market_cap = info.get('marketCap', 0) or 0
        
        ti = TickerInfo(
            ticker=ticker, name=name if name else ticker,
            sector=sector, region=region_enum,
            market_cap=market_cap, avg_volume=avg_vol,
        )
        
        result = compute_rocket_score(df, ti, current_price=price, social_sentiment=False)
        if result is None:
            return None
        
        rocket_signal = result.get('rocket_signal')
        if rocket_signal:
            signal = rocket_signal.direction
            final_score = float(rocket_signal.final_score)
            regime = rocket_signal.regime
            reason = rocket_signal.reason
            family_votes = rocket_signal.family_votes or []
        else:
            dr = result.get('direction_result')
            final_score = float(getattr(dr, 'score', 0)) if dr else 0
            signal = "HOLD"
            regime = "UNKNOWN"
            reason = ""
            family_votes = []
        
        if signal == "BULLISH":
            signal = "BUY"
        elif signal == "BEARISH":
            signal = "SELL"
        
        buy_count = sum(1 for fv in family_votes if fv.get('vote') == 'BUY')
        sell_count = sum(1 for fv in family_votes if fv.get('vote') == 'SELL')
        return (ticker, signal, final_score, regime, buy_count, sell_count, reason)
    except Exception:
        return None


def send_telegram_report(top_10, total, live_count, bot_token, chat_id):
    """Send Top 10 report to Telegram."""
    if not bot_token or not chat_id:
        return False
    
    try:
        bot = Bot(token=bot_token)
        lines = [
            "🌍 *Top 10 Signals (Full Universe Scan)*",
            f"Total tickers: {total}",
            f"Live tickers: {live_count}",
            "",
            "📈 *Top 10 strongest signals:*",
        ]
        
        buy_count = sum(1 for _, s, _, _, _, _, _ in top_10 if s == 'BUY')
        sell_count = sum(1 for _, s, _, _, _, _, _ in top_10 if s == 'SELL')
        hold_count = sum(1 for _, s, _, _, _, _, _ in top_10 if s == 'HOLD')
        
        lines.append(f"BUY: {buy_count} | SELL: {sell_count} | HOLD: {hold_count}")
        lines.append("")
        
        for rank, (ticker, signal, score, regime, buy_c, sell_c, reason) in enumerate(top_10, 1):
            if score >= 0.60:
                se = "🟣"
            elif score >= 0.20:
                se = "🟢"
            elif score <= -0.60:
                se = "🔴"
            elif score <= -0.20:
                se = "🟠"
            else:
                se = "⚪"
            
            lines.append(f"{rank}. {se} *{ticker}* — {signal}")
            lines.append(f"   Score: {score:.2f}  |  Regime: {regime}")
            if reason and len(reason) < 80:
                lines.append(f"   ↳ {reason}")
            lines.append("")
        
        lines.append(f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")
        lines.append("⚠️ Scannerresultatet är en teknisk observation och ska inte")
        lines.append("tolkas som en prognos eller garanti för avkastning.")
        
        text = "\n".join(lines)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown'))
        finally:
            loop.close()
        
        return True
    except Exception as e:
        print(f"  ❌ Telegram send failed: {str(e)[:100]}")
        return False


def save_to_db(top_10, total, live_count):
    """Save top 10 to SQLite scan_history table."""
    import sqlite3
    db_path = Path('data/signals.db')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute('''CREATE TABLE IF NOT EXISTS scan_history (
        ticker TEXT, signal TEXT, score REAL, category TEXT,
        buy_count INTEGER, sell_count INTEGER, reason TEXT,
        timestamp TEXT
    )''')
    for ticker, signal, score, regime, buy_c, sell_c, reason in top_10:
        conn.execute(
            "INSERT INTO scan_history (ticker, signal, score, category, buy_count, sell_count, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, signal, score, regime, buy_c, sell_c, reason[:500], datetime.now(timezone.utc).isoformat())
        )
    conn.commit()
    conn.close()
    print(f"💾 Saved to {db_path}", flush=True)


def main():
    print("🚀 Loading universe...", flush=True)
    universe = get_universe()
    
    all_tickers = []
    for region, tickers in universe.items():
        for t in tickers:
            if is_real_ticker(t):
                all_tickers.append((region, t))
    
    total = len(all_tickers)
    print(f"📊 Total valid tickers: {total}", flush=True)
    
    # Phase 1: Batch download for liveness detection
    print("🔍 Phase 1: Batch liveness detection...", flush=True)
    start_time = time.time()
    live_tickers = []
    
    BATCH_SIZE = 1000
    batch_num = 0
    
    for i in range(0, len(all_tickers), BATCH_SIZE):
        batch = all_tickers[i:i+BATCH_SIZE]
        batch_names = [t[1] for t in batch]
        
        try:
            df = yf.download(batch_names, period='1mo', interval='1d',
                            progress=False, timeout=30, group_by='ticker')
            
            if df is not None and not df.empty and isinstance(df.columns, pd.MultiIndex):
                tickers_with_data = df.columns.get_level_values(0).unique()
                ticker_set = set(tickers_with_data)
                for region, ticker in batch:
                    if ticker in ticker_set:
                        live_tickers.append((region, ticker))
            
            batch_num += 1
            elapsed = time.time() - start_time
            if batch_num % 5 == 0:
                print(f"  ✅ Batch {batch_num}: {min(i+BATCH_SIZE, len(all_tickers))}/{total}, "
                      f"{len(live_tickers)} live, {elapsed:.0f}s", flush=True)
        except Exception as e:
            print(f"  ⚠️ Batch {batch_num} error: {str(e)[:50]}", flush=True)
    
    elapsed = time.time() - start_time
    print(f"\n✅ Phase 1 done: {len(live_tickers)} live tickers in {elapsed:.0f}s", flush=True)
    
    if not live_tickers:
        print("❌ No live tickers found!", flush=True)
        return
    
    # Phase 2: Sequential scan with retry + delay
    print("🔍 Phase 2: Scanning live tickers sequentially with retry...", flush=True)
    start_time = time.time()
    results = []
    scored = 0
    
    # Rate-limit protection: delay between history() calls
    DELAY_BETWEEN_CALLS = 1.5  # seconds
    
    for idx, (region, ticker) in enumerate(live_tickers, 1):
        result = scan_single_ticker(region, ticker)
        
        if result is not None:
            scored += 1
            if result[1] in ('BUY', 'SELL'):
                results.append(result)
        
        if idx % 500 == 0 or idx == len(live_tickers):
            elapsed = time.time() - start_time
            print(f"  ✅ Phase 2: {idx}/{len(live_tickers)}, "
                  f"{scored} scored ({len(results)} BUY/SELL), {elapsed:.0f}s", flush=True)
        
        # Rate-limit protection
        if idx < len(live_tickers):
            time.sleep(DELAY_BETWEEN_CALLS)
    
    elapsed = time.time() - start_time
    print(f"\n✅ Phase 2 done: {len(live_tickers)} tickers scanned, "
          f"{scored} scored, {len(results)} BUY/SELL signals in {elapsed:.0f}s", flush=True)
    
    if not results:
        print("❌ No BUY/SELL signals generated!", flush=True)
        save_to_db([], total, len(live_tickers))
        return
    
    # Sort by score descending
    sorted_results = sorted(results, key=lambda x: x[2], reverse=True)
    top_10 = sorted_results[:10]
    
    print(f"\n🏆 Top 10 Signals:", flush=True)
    print("=" * 80, flush=True)
    for rank, (ticker, signal, score, regime, buy_c, sell_c, reason) in enumerate(top_10, 1):
        emoji = "🟣" if score >= 0.60 else "🟢" if score >= 0.20 else "🔴" if score <= -0.60 else "🟠" if score <= -0.20 else "⚪"
        print(f"{rank}. {emoji} {ticker}: {signal} (score={score:.2f}, regime={regime})", flush=True)
        if reason and len(reason) < 100:
            print(f"   ↳ {reason}", flush=True)
    
    # Save to signals.db scan_history
    save_to_db(top_10, total, len(live_tickers))
    
    # Send to Telegram
    if BOT_TOKEN and ADMIN_CHAT_ID:
        print("📤 Sending to Telegram...", flush=True)
        ok = send_telegram_report(top_10, total, len(live_tickers), BOT_TOKEN, ADMIN_CHAT_ID)
        if ok:
            print("✅ Top 10 sent to Telegram!", flush=True)
        else:
            print("❌ Telegram send failed!", flush=True)
    else:
        print("⚠️ No Telegram config found.", flush=True)


if __name__ == '__main__':
    main()
