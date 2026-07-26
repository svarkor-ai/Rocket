# Rocket Stock Scanner - Plan & Spec V2 (2026-07-26)

> Status: 63 commits, ~13 000 LOC, 69 Python-filer, 115 tester passerar
> Arkitektur: Dash-baserad dashboard + Telegram-bot + CLI-scanner + backtest + options analytics

---

## 1. Nuvarande status - vad som ar DONE

### 1.1 Data Pipeline
- Universe: 1224+ tickers, 4 regioner (USA, Sverige, Kina, Indien) + CSV-kallor for UK/ASX/Tyskland
- Fetcher: Batch-yfinance med retry, timeout (12s history, 5s info), ThreadPoolExecutor (10 workers)
- Storage: SQLite (data/signals.db, 4 tables: signal_states, scan_history, batch_results) + JSON-cache
- Scheduler: rocket/data/scheduler.py + scripts/daily_push.py (batch-forbattring, ~50s totaltid)
- Fundamentals: P/E, ROE, revenue growth, profit margins integrerade i scoring

### 1.2 Technical Analysis Engine
- 12+ kategorier av indikatorer (totalt 20+ individer):
  - Momentum: RSI, Stochastic, ROC, Williams %R, CCI
  - Trend: EMA 9/21/50/200, ADX, AutoTrend (ZigZag-baserad)
  - Volatility: Bollinger Bands, ATR, Donchian Channels
  - Volume: OBV, MFI, VWAP
  - Advanced: Ichimoku Cloud, Supertrend, Parabolic SAR
  - Regime detection (market regime classification)
  - Pattern engine (ZigZag-baserad: 6 mronster)
- Signal combiner: Kombinerar alla signaler - category scores - overall signal
- Alla indikatorer har tests: 115 test, 115 pass, 1 skip

### 1.3 Rocket Score Engine
- Huvud-scoring: rocket_score.py (455 rader) - 0-100 skalan
- Weighter: Evidence-based (Tier 1: 3x, Tier 2: 1.5x, Tier 3: 0.5x)
- Vikter: MOMENTUM:50%, TREND:35%, VOLATILITY:5%, VOLUME:10%
- Filter: Likviditetsfilter, prisfilter, fundamentals filter
- Momentum Social: Kombinerar teknisk momentum med sentiment (StockTwits, Reddit meme-score)
- Risk scoring: Risk-adjusted scoring
- Confidence scoring: Tillfoljlighetsmat for varje signal
- Ranking: Top-N per region

### 1.4 Sentiment Engine
- News: RSS-hamtning (Google News, Yahoo Finance)
- Keywords: Keyword-baserad sentimentanalys (sv/en)
- Social sentiment: Reddit-kommunikation
- StockTwits: Real-time sentiment fran StockTwits API
- Meme score: FINVINS + StockTwits meme-stock detektion
- Short interest: Korta positioner data
- Correlation: Sentiment - prisrorelse-korrelation

### 1.5 Backtest Engine
- Engine: Hendarelse-driven simulering (per-dag trade-generering)
- Strategier: Buy&Hold, EMA-crossover, RSI-baserad, RocketCombo, meme-backtest
- Metrics: Win Rate, total return, Sharpe, Max DD, Sortino, Calmar
- Sensitivity: Parameter-sensitivity analysis
- 12/12 integrationstester passerar

### 1.6 Dash Dashboard
- app.py: Huvud-app (create_app)
- callbacks.py: Alla Dash callbacks (455 rader)
- layout.py: Tab-struktur, dashboard-layout
- Real-time data: SQLite-lasning for live-visning

### 1.7 Telegram Bot
- bot.py: Huvudbot med polling
- commands.py: /scan, /scanall, /history, /portfolio, /subscribe, /unsubscribe, /status, /plan, /om, /help
- handlers.py: Callback query handlers (ticker-detail, refresh)
- notifications.py: Telegram-notifikationer, top-10 visning
- User management: Free/premium tiers, subscribe/unsubscribe
- Portfolio scan: /portfolio command + background scan loop

### 1.8 Options Analytics
- quant/options.py (428 rader): Max Pain, GEX (Gamma Exposure), PCR (Put/Call Ratio), DTE bias

### 1.9 Scan Engine + Nightly Pipeline
- rocket/scan_engine/engine.py: Huvud scanner med batch-stod
- rocket/nightly_scan.py: Batch scanning med ThreadPoolExecutor

---

## 2. Vad som ar INCOMPLETE/TODO

### 2.1 Plotting/Dashboard
- Finns: plotting/ med candlestick.py, indicators.py, equity.py, utils.py
- TODO: Plotting-modulerna anvands inte i Dash (callbacks.py laser direkt fran SQLite)
- TODO: Inga candlestick charts, equity curves, sentiment charts, eller options charts i dashboarden
- Dashboard visar bara tabeller

### 2.2 Data/Storage
- SQLite: Anvands istallet for Parquet (originalplanen sa Parquet)
- Parquet: Bara 2 filer i data/ohlcv/
- batch_results: 7926 rader lagrade, men scan_history ar TOM (0 rader)
- OHLCV: Bara 2 filer i data/ohlcv/ — inga ticker-specifika filer

### 2.3 Tomma data-mappar
- data/backtest/ = TOM
- data/sentiment/ = TOM
- data/signals/ = TOM

### 2.4 API
- rocket/api/app.py (232 rader) finns men anvands inte fran Dash-dashboarden
- Inget API-dokumentation eller OpenAPI-spec

### 2.5 Scripts saknas
- scripts/run_cron.py: FINNS INTE (ersatt av daily_push.py)
- scripts/export_report.py: FINNS INTE
- scripts/fetch_history.py: FINNS men INTE versionerad

### 2.6 config.py
- Finns INTE: originalplanen sa config.py for central konfiguration
- Config: Spridd over multiple .env filer och hard-coded defaults

---

## 3. Prioriterade uppgifter

| Prioritet | Uppgift | Beskrivning |
|-----------|---------|-------------|
| P0 | Fyll data-lagring | Kors daily_push.py for att fylla data/ohlcv/, data/scores/, data/sentiment/ |
| P0 | Candlestick charts i Dash | Implementera Plotly candlestick med lagrad data |
| P1 | Equity curve charts | Implementera backtest equity curves i dashboarden |
| P1 | Sentiment charts | Implementera sentiment time-series charts |
| P2 | Parquet storage | Parquet istallet for SQLite (enligt originalplanen) |
| P2 | API-dokumentation | OpenAPI-spec for rocket/api/app.py |
| P2 | config.py | Central konfiguration enligt originalplanen |
| P3 | Custom CSS | static/custom.css for morkt tema |
| P3 | Scripts | Lagg till run_cron.py, export_report.py |

---

## 4. Kvalitet

- **115 tester, 115 pass, 1 skip**
- **0 TODOs/FIXMEs/HACKs/XXX/NotImplemented i kodbasen**
- **69 Python-filer, 16 modulpaket, ~13 000 LOC**
- **Max filstorlek**: universe_builder.py ~836 rader

### Kanda problem
- ~7 tickers fail consistently (delisted/rate-limited): BRK.B, NESN.ZU, ROG-DE, SAND-B.ST, ITU-A.ST, AGN-A.ST, SEC-A.ST, VOLVO-B.ST
- Scores ar naora noll (~0.2) — scoring engine producerar milda signaler
- Inga BUY/SELL-signaler genereras an

---

## 5. Sammanfattning

### Fardiga
- Technical analysis engine med 20+ indikatorer
- Rocket scoring engine med evidence-based weighting
- Telegram bot med 10+ kommandon
- Backtest engine med 4+ strategier
- Sentiment engine med nyheter, social media, meme scoring
- Options analytics (Max Pain, GEX, PCR, DTE)
- Nightly scan pipeline med ThreadPoolExecutor
- 115 tester, alla passerar
- 63 commits, ren kod

### Ofullstandigt
- Dashboard saknar visualiseringar (endast tabeller)
- Ingen OHLCV-data lagrad for dashboarden
- Inga sentiment/backtest-data lagrade
- Parquet-storage inte implementerad
- config.py saknas

### Siffror
- 63 git commits | 69 Python-filer | ~13 000 LOC | 115 tester (alla pass)
- 1224+ tickers | 4 regioner | 20+ indikatorer | 4 backtest-strategier | 10+ Telegram kommandon

---

Denna spec dokumenterar projektets faktiska tillstand per 2026-07-26, efter 63 commits och ~13 000 LOC.
Originalplanen fran juli 2025 har overtraffats med manga funktioner som inte fanns med i originalet (Telegram bot, options analytics, social sentiment, nightly pipeline).
