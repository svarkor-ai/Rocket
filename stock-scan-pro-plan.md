# Stock Scan Pro Plan Mode Architecture

## Overview

Stock Scan Pro extends the existing rocket-stock-scanner with three new subsystems:

1. Signal Engine - a long-running daemon that periodically scores tickers and emits SignalEvents when signals change.
2. Telegram Bot - a python-telegram-bot bot that accepts user commands, stores subscriptions, and delivers push notifications on signal changes.
3. REST API - a FastAPI service exposing signal data and subscription management for programmatic access.

All three subsystems share a single persistent store (SQLite) for subscriptions, signal history, and a signal-change cache. They all reuse the existing rocket.scoring.compute_rocket_score() pipeline - no duplication of indicators or scoring logic.

---

## New File Structure

rocket/
  engine/                         # NEW: Signal Engine subsystem
    __init__.py
    event.py                      # SignalEvent dataclass + event enum
    scorer.py                     # Core scan loop: fetch, score, compare, emit
    engine.py                     # Async SignalEngine daemon (main entry point)
    store.py                      # SQLite store for signal history and change cache

  telegram/                       # NEW: Telegram Bot subsystem
    __init__.py
    bot.py                        # Bot dispatcher with commands
    handler.py                    # Command handlers + inline reply logic
    push.py                       # Push notification sender (hooks into engine events)
    store.py                      # SQLite store for user subscriptions and per-user thresholds

  api/                            # NEW: FastAPI REST subsystem
    __init__.py
    main.py                       # FastAPI app, lifespan, startup hooks
    routes.py                     # POST /signals, POST /subscriptions, GET /health
    schemas.py                    # Pydantic models for request/response

  config/                         # NEW: Configuration subsystem
    __init__.py
    loader.py                     # YAML/JSON config loader with defaults
    settings.py                   # Typed settings dataclass (Pydantic BaseModel)

  signals/                        # NEW: Shared signal-domain module
    __init__.py
    registry.py                   # Ticker allowlist + region-to-interval mapping

Top-level files:
  stock-scan-pro.yml              # NEW: Default YAML config
  run_engine.py                   # NEW: CLI entry point for the signal engine daemon
  run_bot.py                      # NEW: CLI entry point for the Telegram bot
  run_api.py                      # NEW: CLI entry point for the FastAPI server (uvicorn)

---

## File-Level Descriptions

### 1. rocket/config/settings.py

Responsibility: Define the entire configuration schema as a typed Pydantic BaseModel. Provides Settings.load(path) classmethod that reads a YAML file and falls back to environment-variable overrides.

Fields:
  telegram.bot_token: str - BotFather token (required for bot mode)
  telegram.push_enabled: bool - Enable/disable push notifications
  scan.intervals: dict[str, int] - Region to scan interval in minutes (e.g. usa: 30, sweden: 60)
  scan.default_days: int - OHLCV lookback period (default 180)
  scan.ticker_allowlist: list[str] or None - None = scan full universe
  signals.thresholds: dict[str, float] - Signal change detection thresholds (e.g. buy: 0.7, sell: 0.3)
  signals.hold_duration_sec: int - Cooldown window after a notification
  store.db_path: str - SQLite database path for all three subsystems
  api.host: str, api.port: int - FastAPI bind address

Integration: Read by all three subsystems at startup. The rocket package own code (indicators, scoring) has no dependency on config - it simply accepts pd.DataFrame inputs.

---

### 2. rocket/config/loader.py

Responsibility: Load the YAML config, validate it, and merge in environment variable overrides. Exposes a singleton get_settings() function.

Integration: Imported by engine.py, bot.py, main.py, and run_engine.py / run_bot.py / run_api.py.

---

### 3. rocket/engine/event.py

Responsibility: Define the core event type that flows between all subsystems.

SignalEvent(dataclass):
  ticker: str
  region: str
  signal: Signal            # BUY | SELL | HOLD (from rocket.technical.models.Signal)
  previous_signal: Signal
  score: RocketScore        # from rocket.scoring.models.RocketScore
  summary: SignalSummary    # from rocket.technical.signal_combiner.SignalSummary
  timeframe: str            # e.g. "1d"
  timestamp: datetime
  reason: str               # Human-readable explanation

Integration: Consumed by the engine emitter, the Telegram bot push handler, and the REST API signal endpoint.

---

### 4. rocket/engine/scorer.py

Responsibility: The core scoring worker. Takes a list of tickers, fetches OHLCV via rocket.data.fetcher.fetch_ohlcv(), runs the full scoring pipeline via rocket.scoring.compute_rocket_score(), compares the result against the previous signal for that ticker, and yields a list of SignalEvents when a change is detected.

Key logic:
  1. Fetch OHLCV for the requested tickers using existing fetcher.fetch_ohlcv().
  2. For each ticker, call compute_rocket_score(df, ticker_info) from existing rocket.scoring.rocket_score.
  3. Derive the dominant signal: BUY if buy_count > sell_count + hold_count else SELL if sell_count > buy_count + hold_count else HOLD.
  4. Compare against the cached previous signal (from engine.store).
  5. If signal changed AND score exceeds the configured threshold for that direction:
     - Build a reason string from the SignalSummary.details (top contributors).
     - Emit a SignalEvent.
  6. Update the previous-signal cache in engine.store.

Integration: Imports rocket.data.fetcher.fetch_ohlcv, rocket.data.universe.get_universe, rocket.scoring.compute_rocket_score, rocket.data.models.TickerInfo, rocket.technical.models.Signal, and writes events to engine.store.

---

### 5. rocket/engine/store.py

Responsibility: SQLite-based persistence for the signal engine. Two tables:

  signal_history - ticker, region, signal, overall_score, timestamp (append-only log of every scan)
  signal_cache - ticker (PK), region, signal, score, timestamp (latest signal per ticker for change detection)

Integration: Read/written exclusively by scorer.py. Also readable by the REST API (api/routes.py) to serve current signals.

---

### 6. rocket/engine/engine.py

Responsibility: The long-running daemon. Orchestrates region-level scan loops using asyncio (or threading with concurrent.futures).

Architecture:
  - One asyncio event loop.
  - For each region configured, spawn a PeriodicScanner that:
    1. Gets the ticker list for the region (from rocket.data.universe).
    2. Optionally filters by config.scan.ticker_allowlist.
    3. Calls scorer.py to score all tickers.
    4. On each emit of SignalEvent, fires a callback into the Telegram push system and writes to the REST API event bus.
  - Regions are scanned in parallel (different intervals per region).
  - Graceful shutdown on SIGINT/SIGTERM.

Entry point: run_engine.py calls engine.start() which blocks until shutdown.

Integration: Core imports: rocket.config.settings, rocket.engine.scorer, rocket.engine.store, rocket.data.universe.

---

### 7. rocket/telegram/bot.py

Responsibility: python-telegram-bot Application that registers all command handlers and the push notification callback.

Commands:
  /start - Welcome message, instruct user to subscribe tickers
  /signal <TICKER> - Immediately fetch and send the current signal for a single ticker
  /subscribe <TICKER> - Subscribe user to push notifications for a ticker
  /unsubscribe <TICKER> - Unsubscribe
  /list - List all subscribed tickers with current signals
  /status - Show user notification threshold setting

Integration: Imports rocket.telegram.store (for subscription CRUD), rocket.telegram.push (for sending), rocket.config.settings, rocket.data.universe (ticker validation), rocket.engine.scorer (for on-demand queries).

---

### 8. rocket/telegram/handler.py

Responsibility: Individual command handler functions. Each receives the update and context from python-telegram-bot, validates input (e.g. ticker format), interacts with stores, and returns appropriate responses.

Handlers:
  handle_start(update, context) - Sends welcome + usage instructions
  handle_signal(update, context) - Triggers scorer.py for one ticker, sends inline result
  handle_subscribe(update, context) - Persists subscription + confirms
  handle_unsubscribe(update, context) - Removes subscription
  handle_list(update, context) - Fetches current signals for user subscriptions
  handle_status(update, context) - Returns current threshold setting

Integration: Pure handlers - no side effects beyond calling telegram.store and engine.scorer.

---

### 9. rocket/telegram/push.py

Responsibility: Sends push notifications to subscribed Telegram users when a SignalEvent fires.

Logic:
  1. On each SignalEvent, look up all users subscribed to that ticker in telegram.store.
  2. Filter by each user personal threshold (e.g. only notify if score > 0.7).
  3. Check cooldown: do not send duplicate notifications within config.signals.hold_duration_sec.
  4. Format a Telegram message with signal info, scores, and reason.
  5. Send via python-telegram-bot Bot.send_message().

Integration: Called from engine.py event callback. Imports telegram.store, rocket.telegram.bot (for the Bot instance), rocket.config.settings.

---

### 10. rocket/telegram/store.py

Responsibility: SQLite store for Telegram bot state. Three tables:

  subscriptions - telegram_user_id (PK), ticker, created_at (one row per user-ticker pair)
  user_settings - telegram_user_id (PK), threshold (float, default 0.5), language (str, default en)
  push_log - id (PK), user_id, ticker, signal, timestamp (append-only send log for dedup)

Integration: Written by handler.py (subscribe/unsubscribe), read by push.py (find subscribers), read by bot.py (list command).

---

### 11. rocket/api/main.py

Responsibility: FastAPI application instance. Sets up lifespan (startup/shutdown hooks), CORS middleware, and mounts the router.

Lifespan:
  - On startup: loads config, initializes SQLite stores (all three subsystems share one DB), starts the engine daemon in the background, starts the Telegram bot polling loop in the background.
  - On shutdown: stops engine, stops bot, closes DB connections.

Integration: Imports rocket.config.settings, rocket.engine.engine, rocket.telegram.bot, rocket.telegram.store, rocket.api.routes.

---

### 12. rocket/api/routes.py

Responsibility: FastAPI route handlers.

Endpoints:

  GET /health - Returns status, engine state, bot state
  POST /signals - Request body: tickers list, regions list -> Returns current signals for those tickers (scans if stale)
  POST /subscriptions - Request body: telegram_user_id, ticker, action (subscribe/unsubscribe) -> Add/remove/confirm subscription

Integration: Reads from engine.store (signal cache), writes to telegram.store (subscriptions). Uses rocket.engine.scorer for on-demand scans.

---

### 13. rocket/api/schemas.py

Responsibility: Pydantic request/response models for the REST API.

Schemas:
  SignalRequest - tickers: list[str], regions: list[str] or None
  SignalResponse - ticker: str, signal: str, score: float, details: dict
  SubscriptionRequest - telegram_user_id: int, ticker: str, action: str (subscribe/unsubscribe)
  HealthResponse - status: str, engine: str, bot: str

---

### 14. rocket/signals/registry.py

Responsibility: Central registry for the ticker-to-region mapping and scan interval policy. Bridges the existing rocket.data.universe with the new scan engine needs.

Functions:
  get_region_intervals() -> dict[str, int] - Returns region to interval mapping from config
  get_tickers_for_region(region: str) -> list[str] - Wraps rocket.data.universe.get_universe() with optional allowlist filtering
  get_all_tickers() -> list[str] - All tickers across all regions, optionally filtered

Integration: Used by engine.py and api/routes.py. No imports from rocket own scoring/indicators - pure registry.

---

### 15. stock-scan-pro.yml

Responsibility: Default YAML configuration file with all options documented as comments.

Contents: A YAML file mirroring the Settings dataclass structure - telegram.*, scan.*, signals.*, store.*, api.* sections, with descriptive comments explaining each field. The token field is a placeholder to be replaced by the operator.

---

### 16. run_engine.py, run_bot.py, run_api.py

Responsibility: CLI entry points.

  run_engine.py - Parses args (--config, --regions), loads settings, calls engine.start().
  run_bot.py - Loads settings, starts Telegram bot polling. If the token is empty, prints a warning but still runs (for API-only mode).

---

## Integration Points with Existing Modules

rocket.data.fetcher              ->  engine/scorer.py             ->  fetch_ohlcv() returns dict[ticker, DataFrame]
rocket.data.universe             ->  engine/engine.py             ->  get_universe(region) returns ticker list
rocket.data.models.TickerInfo    ->  engine/scorer.py             ->  Passed to compute_rocket_score
rocket.data.storage              ->  (unchanged)                  ->  Dash app and existing scheduler
rocket.data.scheduler            ->  (unchanged)                  ->  Existing cron-based data updates
rocket.technical.models          ->  engine/event.py              ->  Signal, SignalCategory enums
rocket.technical.signal_combiner ->  engine/scorer.py             ->  Direct import (already used by scoring)
rocket.technical.base            ->  (unchanged)                  ->  BaseIndicator abstract class
rocket.scoring.rocket_score      ->  engine/scorer.py             ->  compute_rocket_score(df, ticker_info)
rocket.scoring.models            ->  engine/event.py              ->  RocketScore, ScoreBreakdown dataclasses
rocket.scoring.weighter          ->  (unchanged by engine)        ->  Called internally by compute_rocket_score
rocket.scoring.filter            ->  (unchanged by engine)        ->  Called internally by compute_rocket_score
rocket.plotting.*                ->  (unchanged)                  ->  Dash UI only
rocket.backtest.*                ->  (unchanged)                  ->  Dash UI only
rocket.sentiment.*               ->  (unchanged)                  ->  Dash UI only
rocket.routes.*                  ->  (unchanged)                  ->  Dash UI only

---

## Shared SQLite Database Schema

All three subsystems share one SQLite database (stock-scan-pro.db):

  CREATE TABLE signal_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT NOT NULL,
      region TEXT NOT NULL,
      signal TEXT NOT NULL,       -- BUY/SELL/HOLD
      overall_score REAL NOT NULL,
      timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE signal_cache (
      ticker TEXT PRIMARY KEY,
      region TEXT NOT NULL,
      signal TEXT NOT NULL,
      overall_score REAL NOT NULL,
      timestamp DATETIME NOT NULL
  );

  CREATE TABLE subscriptions (
      telegram_user_id INTEGER NOT NULL,
      ticker TEXT NOT NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (telegram_user_id, ticker)
  );

  CREATE TABLE user_settings (
      telegram_user_id INTEGER PRIMARY KEY,
      threshold REAL NOT NULL DEFAULT 0.5,
      language TEXT NOT NULL DEFAULT 'en'
  );

  CREATE TABLE push_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      telegram_user_id INTEGER NOT NULL,
      ticker TEXT NOT NULL,
      signal TEXT NOT NULL,
      sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

---

## Data Flow Diagram

  Signal Engine Daemon
    fetcher -> scorer -> event emit (SignalEvent)
      |
      v
  +---+-----------------+-----------------+
  |                   |                 |
  v                   v                 v
Telegram Bot Push   REST API          Local DB
/signals            stores

---

## Dependency Additions

New Python dependencies (add to pyproject.toml / requirements.txt):

  python-telegram-bot>=21.0  - Telegram bot framework (async)
  fastapi>=0.104             - REST API framework
  uvicorn[standard]>=0.24    - ASGI server for FastAPI
  pyyaml>=6.0                - YAML config loading
  aiosqlite>=0.19            - Async SQLite (optional; can use sqlite3 directly)

No changes needed for existing dependencies (yfinance, pandas, numpy, dash, plotly, pydantic).

---

## Security and Operational Notes

1. Bot token - never committed to version control. Loaded from YAML config or env var override.
2. Database - single SQLite file; file locks handled by python-telegram-bot and FastAPI async I/O. Use check_same_thread=False for SQLite if needed.
3. Rate limiting - yfinance has rate limits; the engine should throttle fetches (already present in fetcher.py via time.sleep(0.3)).
4. Backwards compatibility - the Dash UI (app.py, rocket/routes/) is completely unaffected. The new modules live in their own subpackages.
5. No god files - each module has exactly one responsibility. The engine orchestrates; scorer computes; bot handles Telegram; API handles HTTP; config handles settings.

---

## Implementation Order (Recommended)

1. config/ - Settings + loader (needed by everything else)
2. signals/registry.py - Ticker registry (needed by engine)
3. engine/store.py - SQLite store
4. engine/event.py - SignalEvent dataclass
5. engine/scorer.py - Core scoring worker
6. engine/engine.py - Daemon loop
7. telegram/store.py - Telegram subscriptions store
8. telegram/handler.py - Command handlers
9. telegram/push.py - Push notification sender
10. telegram/bot.py - Bot app assembly
11. api/schemas.py - Pydantic models
12. api/routes.py - REST endpoints
13. api/main.py - FastAPI app + lifespan
14. run_engine.py, run_bot.py, run_api.py - CLI entry points
15. stock-scan-pro.yml - Default config file
