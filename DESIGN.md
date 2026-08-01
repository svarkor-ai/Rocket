# Rocket Scout Engine Architecture — DESIGN.md (REALITY-CHECK)

**Created:** 2026-08-01
**Phase:** Architecture (Fas 3)
**Status:** FINAL — Documents what the code actually does
**Last updated:** 2026-08-01 (post-review reality check)

## Overview

Scout Engine (`rocket/scan_engine/`) is the real-time signal processing core that:
- Accepts technical indicator data from `rocket/technical/`
- Scores signals with configurable thresholds
- Manages signal state with hysteresis (both strength and BUY/SELL levels)
- Emits `SignalEvent` objects to SQLite storage

**DISTINCTION:** Scout Engine = real-time/alerting (portfolio scans, live signals). 
`rocket/data/scheduler.py` = batch/data-collection (nightly OHLCV updates).

## Actual Module Design

### 1. `rocket/scan_engine/models.py`
- **Concern:** Signal data structures
- **Data classes:**
  - `SignalEvent`: ticker, prev_signal, new_signal, score, category, reason, timestamp, timeframe, buy_count, sell_count, strength
  - `SignalState`: ticker, signal, score, category, updated_at, strength
- **Imports from `rocket/technical/models.py`:** `Signal`, `SignalCategory`, `SignalStrength`

### 2. `rocket/scan_engine/engine.py`
- **Concern:** Signal processing, scoring, emission logic
- **Class `SignalEngine`:**
  - `__init__(self, storage, config)` — config is a raw dict (NOT TypedDict)
  - `scan_ticker(self, ticker, timeframe)` — fetch OHLCV, score, detect signal change
  - `scan_region(self, region, timeframe)` — bulk scan
- **Functions:**
  - `_derive_strength(score)` — maps [-1,1] to 5-level SignalStrength
  - `_derive_signal(summary)` — maps SignalSummary to (Signal, category) using BUY_THRESHOLD/SELL_THRESHOLD
  - `_apply_strength_hysteresis(new, score, prev)` — hysteresis on strength transitions
  - `_make_reason(summary, new_sig, prev_sig)` — human-readable explanation
- **Thresholds:**
  - `BUY_THRESHOLD = 4` (4 of 7 indicators agree)
  - `SELL_THRESHOLD = 4`
  - `STRENGTH_LEVELS` — 5 levels: VERY_BEARISH(-1.0,-0.60), BEARISH(-0.60,-0.20), HOLD(-0.20,0.20), BULLISH(0.20,0.60), VERY_BULLISH(0.60,1.00)
  - `HYSTERESIS` — dict with "in"/"out" per strength level
- **Dual hysteresis layers (NOT collapsed):**
  1. Strength hysteresis via `_apply_strength_hysteresis()`
  2. BUY/SELL signal hysteresis via inline buy_in/buy_out/sell_in/sell_out (lines 220-241)

### 3. `rocket/scan_engine/storage.py`
- **Concern:** Signal state persistence (SQLite)
- **Class `SignalStorage`:**
  - `save_signal_state(state)` — upsert ticker state
  - `get_signal_state(ticker)` — current state for ticker
  - `get_all_states()` — all tracked ticker states
  - `get_all_tracked_tickers()` — alias for `get_all_states()` (renamed from `get_all_subscriptions`)
  - `save_scan_history(records)` — bulk insert scan history
  - `get_top_signals(limit)` — top N signals from latest scan
  - `get_last_scan_timestamp()` — most recent scan time
  - `clear_signal_state(ticker)` — remove ticker

## Key Invariants (What the code actually does)

1. **Two SignalStrength enums exist (naming collision):**
   - `rocket/technical/models.py`: 5-value (VERY_BEARISH..VERY_BULLISH) — used by scan_engine
   - `rocket/scoring/rocket_score.py`: 7-value (STRONG_BULLISH..BEARISH) — used by scoring pipeline
   - Both named `SignalStrength`. Engine imports from technical/models only.
2. **Dual hysteresis (NOT collapsed):** Strength hysteresis + BUY/SELL signal hysteresis are separate
3. **Config is raw dict (NOT TypedDict):** `SignalEngine.__init__` takes `config: dict`
4. **HYSTERESIS dict values are authoritative** for strength transitions
5. **BUY/SELL hysteresis uses hardcoded thresholds** (buy_in=0.60, buy_out=0.35, sell_in=-0.60, sell_out=-0.35)
6. **No dead code** — all expressions have a purpose (verified by Artemis)
7. **State saved AFTER emission** — correct ordering

## Testing
- 125 tests pass (as of 2026-08-01)
- No tests explicitly test hysteresis behavior (gap identified in review)
- All 5 bugs in engine.py fixed (c9dafa5)

## Gate Verdict
**REALITY-CHECK** — Documents actual code, not aspirational design:
1. ✅ SignalStrength collision documented (two enums, different values)
2. ✅ Dual hysteresis layers acknowledged (not collapsed)
3. ✅ Config is raw dict (not TypedDict)
4. ✅ `get_all_tracked_tickers()` renamed (not `get_all_subscriptions`)
5. ✅ No dead code (verified)
6. ✅ All bugs fixed and committed

## Outstanding Items (Low Priority)
1. ~~`get_all_subscriptions`~~ → Renamed to `get_all_tracked_tickers()` ✅
2. Stale comment on line 20 → Fixed: "4 of 7 indicators agree" ✅
3. SignalStrength naming collision → Documented in DESIGN.md
4. Hysteresis testability → No explicit hysteresis tests exist (gap)
5. Config TypedDict → Not implemented (raw dict is current state)
6. Unified SignalStrength → Not implemented (two enums exist)
