# 🚀 Rocket Stock Scanner — Full Architecture

## Mål
Ett **enormt** projekt som skannar **25.000+ tickers** med **10+ års historik**, kör **20+ indikatorer** vetenskapligt viktade, inkluderar **alternativa data** (social sentiment, options, short interest, meme signals), **backtestar** viktningsstrategier, och skickar **10 dagliga rekommendationer** via Telegram.

---

## 🏗️ Arkitektur översikt

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT                            │
│  /scan, /subscribe, /unsubscribe, /top10, /status           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   DAILY SCHEDULE                            │
│  Cron-job: 06:00 UTC → fetch → score → backtest → report  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  UNIVERSE BUILDER                           │
│  25k+ tickers: USA, Sweden, China, India                    │
│  Data: index constituents + exchange listings               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              DATA FETCHER (10y OHLCV)                       │
│  yfinance → parallel batch (264 tickers/thread)             │
│  Cache: Parquet files + universe_cache.json                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              INDICATORS (20+)                               │
│  Momentum: RSI, MACD, Stochastic, Williams %R, CCI, ROC   │
│  Trend: EMA 9/21/50/200, EMACrossover, ADX                 │
│  Volatility: Bollinger, ATR, Donchian, Regime              │
│  Volume: OBV, MFI, VWAP                                    │
│  Advanced: Ichimoku, Supertrend, Parabolic SAR             │
│  Patterns: 20+ candlestick patterns                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              SOCIAL SENTIMENT                               │
│  StockTwits API → keyword sentiment → meme_score           │
│  Short Interest % (from fundamentals)                      │
│  General sentiment (news/social)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              OPTIONS DATA                                   │
│  Max Pain, GEX, PCR, DTE bias                              │
│  Data source: Third-party API or scrape                    │
│  (Requires paid tier or alternative data source)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              SCORING ENGINE                                 │
│  Weighted composite score:                                  │
│  - Momentum: 50% (scientifically optimized)                │
│  - Trend: 35%                                               │
│  - Volatility: 5%                                           │
│  - Volume: 10%                                              │
│  - Social: 15% (StockTwits + meme)                         │
│  - Options: 15% (Max Pain + GEX)                           │
│  - Short Interest: 10%                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              BACKTEST ENGINE                                │
│  Auto-optimize weights on 10y history                       │
│  Sensitivity analysis → robust weight sets                  │
│  Validate: Sharpe, Sortino, Max Drawdown, CAGR             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              TELEGRAM REPORT                                │
│  Top 10 recommendations daily                               │
│  Subscription management                                    │
│  Alert system (breakouts, volume spikes, sentiment)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Modulstruktur

```
rocket/
├── __init__.py
├── data/
│   ├── fetcher.py          # OHLCV fetcher (yfinance)
│   ├── fundamentals.py     # Fundamental data
│   ├── models.py           # Data models (OHLCV, Fundamentals)
│   ├── scheduler.py        # Data fetch scheduler
│   ├── storage.py          # Parquet/cache storage
│   ├── universe_builder.py # 25k+ ticker universe builder
│   ├── universe.py         # Universe definitions (regions)
│   ├── us_tickers.csv      # 7036 US tickers
│   ├── intl_tickers.txt    # 3712 intl tickers
│   ├── index_constituents.json  # 18851 index tickers
│   └── universe_cache.json # Cached universe data
├── technical/
│   ├── base.py             # Indicator base class
│   ├── models.py           # Indicator result models
│   ├── momentum.py         # RSI, MACD, Stochastic, Williams %R, CCI, ROC
│   ├── trend.py            # EMA 9/21/50/200, EMACrossover, ADX
│   ├── volatility.py       # Bollinger, ATR, Donchian, Regime
│   ├── volume.py           # OBV, MFI, VWAP
│   ├── advanced.py         # Ichimoku, Supertrend, Parabolic SAR (657 lines)
│   ├── patterns.py         # 20+ candlestick patterns (806 lines)
│   ├── families.py         # Indicator families grouping
│   ├── signal_combiner.py  # Combine multiple signals
│   ├── momentum_runner.py  # Batch momentum runner
│   └── regime.py           # Market regime detection
├── social/
│   ├── models.py           # Social sentiment models
│   ├── stocktwits.py       # StockTwits API integration
│   ├── sentiment.py        # General sentiment analysis
│   ├── meme_score.py       # Meme stock scoring
│   ├── short_interest.py   # Short interest data
│   └── __init__.py         # Exports
├── scoring/
│   ├── models.py           # Scoring models
│   ├── rocket_score.py     # Main composite scoring (455 lines)
│   ├── weighter.py         # Indicator weight optimization
│   ├── confidence.py       # Score confidence scoring
│   ├── ranking.py          # Ranking engine
│   ├── filter.py           # Pre-scan filters
│   ├── fundamentals_filter.py # Fundamental filters
│   ├── momentum_social.py  # Momentum + social combined (407 lines)
│   └── risk.py             # Risk metrics
├── backtest/
│   ├── models.py           # Backtest models
│   ├── engine.py           # Main backtest engine
│   ├── strategy.py         # Strategy definitions
│   ├── metrics.py          # Performance metrics
│   ├── sensitivity.py      # Weight sensitivity analysis
│   └── meme_backtest.py    # Meme-specific backtesting
├── scan_engine/
│   ├── engine.py           # Scan orchestration
│   ├── models.py           # Scan result models
│   └── storage.py          # Scan result storage
├── scan_pro/
│   ├── main.py             # Scan Pro main logic
│   └── portfolio_scan.py   # Portfolio scan
├── api/
│   └── app.py              # REST API
├── plotting/
│   ├── candlestick.py      # Candlestick visualization
│   └── equity.py           # Equity curve visualization
└── routes/
    └── layout.py           # Dashboard layout (Dash)
```

---

## 🔑 Nyckelfunktioner

### 1. Universe Builder (25k+ tickers)
- **USA**: 7036 tickers (us_tickers.csv)
- **International**: 3712 tickers (intl_tickers.txt)
- **Index constituents**: 18851 tickers (S&P 500, NASDAQ, Russell 2000, etc.)
- **Total potential**: ~29.600 tickers
- **Regions**: usa, sweden, china, india

### 2. Data Fetcher (10y history)
- **Source**: yfinance
- **History**: 10 years (upgraded from 3mo → 10y)
- **Parallel**: ThreadPoolExecutor (264 tickers/thread, 10 workers)
- **Cache**: Parquet files + universe_cache.json

### 3. Indicators (20+)
- **Momentum (6)**: RSI, MACD, Stochastic, Williams %R, CCI, ROC
- **Trend (3)**: EMA 9/21/50/200, EMACrossover, ADX
- **Volatility (4)**: Bollinger Bands, ATR, Donchian Channel, Regime
- **Volume (3)**: OBV, MFI, VWAP
- **Advanced (3)**: Ichimoku Cloud, Supertrend, Parabolic SAR
- **Patterns (20+)**: Candlestick patterns
- **Weighting**: Tier 1: 3x, Tier 2: 1.5x, Tier 3: 0.5x

### 4. Social Sentiment
- **StockTwits API**: Keyword-based sentiment analysis
- **Meme Score**: Meme stock detection algorithm
- **Short Interest**: Short % of float
- **General Sentiment**: News/social sentiment

### 5. Options Data
- **Max Pain**: Max Pain calculation
- **GEX**: Gamma Exposure
- **PCR**: Put/Call Ratio
- **DTE**: Days to Expiration bias
- **Status**: Code exists but needs data source

### 6. Scoring Engine
- **Weighted Composite**:
  - Momentum: 50%
  - Trend: 35%
  - Volatility: 5%
  - Volume: 10%
  - Social: 15%
  - Options: 15%
  - Short Interest: 10%
- **Optimization**: weighter.py + backtest sensitivity

### 7. Backtest Engine
- **10y history**: Full historical backtesting
- **Sensitivity**: Weight sensitivity analysis
- **Metrics**: Sharpe, Sortino, Max Drawdown, CAGR
- **Auto-optimization**: Find best weight sets

### 8. Telegram Bot (TODO)
- **Commands**: /scan, /subscribe, /unsubscribe, /top10, /status
- **Daily**: 10 recommendations at 06:00 UTC
- **Alerts**: Breakouts, volume spikes, sentiment changes

---

## ⚠️ Kritiska Problem

### 1. Telegram Bot saknas
- `python-telegram-bot` i requirements men ingen implementation
- **Lösning**: Bygg bot-modul från scratch

### 2. Options Data-källa saknas
- Har Max Pain/GEX/PCR-kod men ingen data-källa
- **Lösning**: Använd third-party API (t.ex. CBOE, ORATS) eller scrape

### 3. Backtesting-optimisering saknas
- Har `sensitivity.py` men ingen auto-optimerings-loop
- **Lösning**: Bygg loop som testar olika vikter på 10y data

### 4. 25k tickers behöver 10y fetch
- Har universumslista men ingen fetcher för 10y för alla
- **Lösning**: Skala upp fetcher med parallelisering + cache

### 5. Social data är begränsad
- StockTwits API har rate limits (3-4 req/min)
- **Lösning**: Batch-fetch + cache + smart rate limiting

---

## 🎯 Prioritering

### Phase 1: Foundation (Vecka 1-2)
1. [ ] Bygg Telegram bot med subscriptions
2. [ ] Skala upp universe till 25k+ tickers
3. [ ] Uppgradera fetcher för 10y history
4. [ ] Testa alla indikatorer mot real data

### Phase 2: Scoring & Backtest (Vecka 3-4)
5. [ ] Omskriv weighter.py med vetenskaplig grund
6. [ ] Bygg backtest-optimiseringsloop
7. [ ] Validera mot historisk data
8. [ ] Optima lera vikter

### Phase 3: Alternative Data (Vecka 5-6)
9. [ ] Uppgradera StockTwits integration
10. [ ] Bygg meme score module
11. [ ] Implementera short interest
12. [ ] Lös options data-källa

### Phase 4: Integration (Vecka 7-8)
13. [ ] Integrera alla moduler
14. [ ] Bygg daily schedule
15. [ ] Testa full pipeline
16. [ ] Pusha till GitHub

---

## 📊 Måttenheter

| Mätare | Target |
|---|---|
| Tickers | 25.000+ |
| Historik | 10+ år |
| Indikatörer | 20+ |
| Datakällor | 4+ (price, social, options, short) |
| Rekommendationer | 10 dagliga |
| Subscribers | Obegränsad |
| Batch-storlek | 264 tickers/thread |
| Rate limit | 3-4 req/min (StockTwits) |

---

## 🔒 Security

- **API Keys**: Alla nycklar i `~/.hermes/.secrets/`
- **GitHub**: SSH-nyckel `~/.ssh/id_ed25519_github`
- **Telegram Bot Token**: Sparad i `.secrets`
- **Ingen data**: Aldrig skriv secrets till filer eller loggar
- **Ingen exposure**: Aldrig printa tokens i terminal eller chat

---

*Skapad: 2026-07-24*
*Status: Arkitekturplan — implementering påbörjas*
