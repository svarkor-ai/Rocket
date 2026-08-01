# Planner Design Brief: Rocket Scout Engine Architecture

**Target:** `rocket/scan_engine/` — Scout signal processing engine
**Repo:** /srv/svarkor/builds/rocket-stock-scanner

## Context
We have a signal processing engine that:
- Reads technical indicators from `rocket/technical/`
- Scores signals (BUY/SELL) with thresholds
- Manages signal state (previous signals, hysteresis)
- Emits `SignalEvent` objects to storage
- Integrates with notifications and data models

## Current State (as of commit c9dafa5)
- **engine.py**: Main processing logic, scoring, signal emission
- **models.py**: Signal data structures (SignalStrength, SignalEvent, etc.)
- **storage.py**: State persistence and event storage
- **4 critical bugs fixed**: dead code, wrong SELL gate, premature state save, dead dict
- **113 tests passing**, ruff clean

## Design Requirements

### 1. File-level design
For each module in `rocket/scan_engine/`, specify:
- **Path**: Full file path
- **Single concern**: One-sentence description
- **Interface**: Exact function signatures / class methods (not prose)
- **Data crossing boundaries**: What inputs/outputs each module receives
- **Trade-offs rejected**: Why not X approach?

### 2. Module boundaries
- Should `storage.py` be part of scan_engine or separate?
- How should `engine.py` interface with `rocket/technical/` for data?
- How should it interface with notifications?

### 3. State management design
- Current: `storage.py` manages signal state via save/get methods
- Question: Is this the right abstraction level?
- Should state be in-memory + persistent, or just persistent?

### 4. Testing strategy
- Current: Unit tests with mocked data
- Question: How to test signal emission pipeline end-to-end?
- Should we add integration tests for the full signal flow?

### 5. Integration design
- How does Scout integrate with Rocket's notification system?
- What's the contract between Scout and the main Rocket pipeline?
- Should Scout be a standalone service or part of the main app?

## Reuse-first Constraints
- **Existing**: `rocket/technical/` (indicators), `rocket/data/` (models, universe), `rocket/social/` (sentiment)
- **Must extend, not replace**: These existing modules
- **Pattern to follow**: Look at how other Rocket modules are structured

## Output Requirements
> A FILE-LEVEL design: each module, its single concern, its path, and the exact interface it exposes
> (function signatures / route shapes / table columns — not prose). Name the data that crosses each
> boundary. State the trade-offs you REJECTED and why. Name what already exists that this extends
> rather than replaces. No code. End with the RESULT block.

**DELIVERABLE:** Return RESULT block with design decisions, not code.
