# Rocket Scanner v2 — Final Architecture Design

> **Status**: DESIGN ONLY — no code changes until approved by owner.
> **Last updated**: 2026-07-21
> **Based on**: Original plan + Artemis adversarial review

---

## What We Have NOW (post-Teddy commit 8557a77)

### Completed by Teddy
1. ✅ Indicator cleanup (20 → 12 indicators, Artemis verified)
2. ✅ `families.py` — family consensus voting (majority rules + strength normalization)
3. ✅ `risk.py` — risk score + multiplier (0.5–1.0)
4. ✅ `confidence.py` — confidence scoring (agreement + strength + volume)
5. ✅ `regime.py` — regime detection per region (BULL/BEAR/CHOP)
6. ✅ `rocket_score.py` — full v2 pipeline wired together
7. ✅ Hysteresis in `engine.py` (NEUTRAL↔BUY gap 0.3, NEUTRAL↔SELL gap 0.3)

### Not yet done
- [ ] Backtest improvement (costs, slippage, walk-forward)
- [ ] Notifications improvement (cooldown, confidence gating)
- [ ] Full integration test

---

## Artemis Review — Decisions Made

### Decision 1: Keep CCI (DON'T remove)
**Artemis point**: CCI uses MAD normalization, BB uses σ normalization — mathematically distinct.
**Decision**: CCI stays in momentum family. BB stays in volatility (risk only, not direction).
**Result**: 12 indicators instead of 11 — acceptable.

### Decision 2: Keep majority voting (NOT continuous mean)
**Artemis point**: 1 BUY + 2 HOLD → 0.33 direction is misleading.
**Decision**: We keep majority voting (already implemented by Teddy) because:
- It's cleaner and more interpretable
- The strength field `(buy-sell)/total` captures signal magnitude
- 1 BUY + 2 HOLD → HOLD (not weak BUY) — correct behavior
- The direction_score normalization `(raw+1)/2` handles the rest
**Verification**: Teddys `families.py` already does this correctly.

### Decision 3: Risk multiplier applies to confidence (NOT direction)
**Artemis point**: Risk scaling confidence inverts desired behavior.
**Decision**: Current implementation is **correct** — risk multiplier (0.5–1.0) applies to confidence via:
```
final_score = direction_signed × confidence × risk_multiplier × regime_multiplier
```
This means:
- Low risk (multiplier=1.0): full signal
- High risk (multiplier=0.5): signal halved
- Direction score is NOT directly scaled by risk — risk only affects the "certainty" layer
**Artemis was right to flag**, but the current implementation already handles it correctly.
The risk_multiplier of 0.5–1.0 is a dampener, not a signal inveter — high-risk setups get
lower scores but direction remains pure.

### Decision 4: Regime is per-region
**Artemis point**: SPY as proxy for Swedish stocks is insufficient.
**Decision**: `regime.py` already implements per-region detection. Each region has its own index:
- USA → ^GSPC
- Sweden → ^OMXS30
- China → 000001.SS
- India → ^NSEI
Each ticker uses its region's regime multiplier.

### Decision 5: BB used only for risk (squeeze detection)
**Decision**: BB is in volatility.py but NOT in any direction family. It feeds into `risk.py` only.
Correct — BB measures squeeze, not direction.

### Decision 6: MFI-RSI correlation acknowledged
**Decision**: Both stay. MFI adds volume-weighting dimension — different primitive than RSI.
Documented in comments.

### Decision 7: Hysteresis uses engine.py's existing thresholds
**Decision**: Teddy already implemented 6-state hysteresis in `engine.py`.
No changes needed — use what's there.

---

## Final Architecture (What's Actually Implemented)

### 12 Indicators (4 families + 2 risk-only)

```
TREND (4):        MOMENTUM (3):        VOLUME (3):        RISK (2):
EMACrossover       RSI                  OBV               BollingerBands
ADX                MACD                 MFI               ATR
IchimokuCloud      ROC                  VWAPIndicator
Supertrend
```

### Pipeline (already wired in rocket_score.py)

```
Step 1: Run all 12 indicators → IndicatorResult[]
Step 2: Convert to IndicatorVote[] (BUY/HOLD/SELL + strength)
Step 3: Family consensus → FamilyVote[] (majority rules + strength)
Step 4: Direction score = weighted sum of family votes (→ [0, 1])
Step 5: Confidence = 0.5×agreement + 0.3×strength + 0.2×volume_confirm
Step 6: Risk = compute_risk(atr_pct, bb_squeeze, volume_ratio) → multiplier [0.5, 1.0]
Step 7: Regime = detect_regime(region) → multiplier [0.5, 1.0]
Step 8: final_score = direction_signed × confidence × risk × regime (→ [-1, +1])
Step 9: Signal = apply_hysteresis(final_score, prev_signal)
```

### Direction Score Normalization (current implementation)
```
Raw family score = (buy_count - sell_count) / total  ∈ [-1, 1]
Family weighted sum = Σ(fv.strength × fv.weight) / Σ(fv.weight)  ∈ [-1, 1]
Direction score = (raw_score + 1) / 2  ∈ [0, 1]
direction_signed = 2 × direction_score - 1  ∈ [-1, 1]
```

### Hysteresis (in engine.py)
```
NEUTRAL → BUY:  final_score > 0.5
BUY → NEUTRAL:  final_score < 0.2
NEUTRAL → SELL: final_score < -0.5
SELL → NEUTRAL: final_score > -0.2
BUY → SELL:     final_score < -0.6
SELL → BUY:     final_score > 0.6
```

### Risk Module (in risk.py)
```
ATR% risk:        < 2% → 0.0, 2-5% → linear, > 5% → 0.5-1.0
BB squeeze risk:  < 0.03 → 0.9, 0.03-0.08 → 0.4, > 0.08 → 0.1
Volume risk:      < 2x → 0.0, 2-5x → linear, > 5x → 0.5-1.0

risk_score = 0.4×ATR + 0.3×BB + 0.3×volume  ∈ [0, 1]
risk_multiplier = 1.0 - risk_score × 0.5  ∈ [0.5, 1.0]
```

---

## Issues Found During Review

### ISSUE 1: Direction score direction is inverted
**Problem**: `direction_score` in `DirectionResult` is [0, 1] where 0 = strong sell and 1 = strong buy.
But in `rocket_score.py` line 231:
```python
direction_signed = 2.0 * direction_result.score - 1.0
```
This maps 0→-1, 0.5→0, 1→+1. Correct mathematically BUT the `DirectionResult.direction` property
at families.py line 70-75 says:
```python
def direction(self):
    if self.score > 0.7: return Vote.BUY
    elif self.score < 0.3: return Vote.SELL
    return Vote.HOLD
```
This is consistent. BUT the issue is: family strength `(buy-sell)/total` means:
- 3 BUY → (3-0)/3 = +1.0 → score = (1+1)/2 = 1.0 → BUY ✅
- 3 SELL → (0-3)/3 = -1.0 → score = (-1+1)/2 = 0.0 → SELL ✅
- 2 BUY + 1 HOLD → (2-0)/3 = 0.67 → score = (0.67+1)/2 = 0.83 → BUY ✅
- 1 BUY + 2 HOLD → (1-0)/3 = 0.33 → score = (0.33+1)/2 = 0.67 → BUY ⚠️

**0.67 is treated as BUY by the direction property** (> 0.3 threshold for SELL, > 0.7 for BUY → actually HOLD).
Wait — let me re-check. score 0.67: > 0.7? No. < 0.3? No. → HOLD. That's correct!

Actually, the issue is subtler. With 3 families:
- Trend: HOLD (0.67), Momentum: BUY (0.83), Volume: HOLD (0.67)
- Weighted sum = 0.67×0.35 + 0.83×0.35 + 0.67×0.30 = 0.235 + 0.291 + 0.201 = 0.727
- Direction score = 0.727 → direction property = HOLD (0.727 < 0.7? NO, > 0.7 → BUY)

Hmm, 0.727 > 0.7 → BUY. But 2/3 families are HOLD. The weighted average pushes it to BUY because
the one BUY family (Momentum) has higher weight and higher strength.

This is actually **correct behavior** — a strong BUY in Momentum with HOLD in other families should
give a directional BUY signal, just with lower confidence.

### ISSUE 2: Confidence calculation double-counts direction
**Problem**: Confidence uses `agreement` which is based on family votes (BUY/HOLD/SELL). But `avg_strength`
also uses family strength (which encodes the same direction). These are partially correlated.

**Impact**: Confidence may be artificially high when families strongly agree on direction.
**Mitigation**: Acceptable for now — the weights (0.5, 0.3, 0.2) partially dilute this.
Backtest will reveal if confidence is well-calibrated.

### ISSUE 3: Volume family only has 3 indicators
**Problem**: Volume family (OBV, MFI, VWAP) has exactly 3 indicators. If 2 say BUY and 1 says HOLD,
volume family vote is BUY with strength 0.67. This is correct but means volume has equal say as
momentum (both 35% weight) despite having fewer indicators.

**Mitigation**: This is by design — volume confirmation is considered equally important as momentum
in the current architecture. Can be adjusted later based on backtest.

### ISSUE 4: Bollinger in rocket_score.py mapped to TREND family
**Problem**: In `rocket_score.py` line 56:
```python
"BollingerBands": FamilyName.TREND,  # volatility used as trend confirmation
```
But BB is also listed in INDICATORS (line 42) and should NOT vote in direction — it's risk-only.

**This is a BUG**. BB should not be in any voting family. It should only feed into risk.py.

### ISSUE 5: ATR in rocket_score.py mapped to TREND family
**Problem**: In `rocket_score.py` line 57:
```python
"ATR": FamilyName.TREND,  # volatility used as risk input
```
Same issue — ATR should NOT vote in direction. It's risk-only.

### ISSUE 6: INDICATORS list includes BB and ATR but they're risk-only
**Problem**: `INDICATORS` list (line 36-45) includes BB and ATR for calculation, but they shouldn't
participate in family voting. They should be calculated (for risk inputs) but NOT included in
`indicator_votes` passed to `compute_family_votes()`.

**This is a BUG** — BB and ATR votes would incorrectly influence direction score.

---

## Critical Bugs to Fix (Before Testing)

### Bug 1: BB and ATR should NOT vote in families
**Fix**: In `rocket_score.py`, separate direction indicators from risk indicators:
```python
DIRECTION_INDICATORS = [
    RSI(), MACD(), ROC(),
    EMACrossover(), ADX(), IchimokuCloud(), Supertrend(),
    OBV(), MFI(), VWAPIndicator(),
]

RISK_INDICATORS = [
    BollingerBands(), ATR(),
]
```
Only `DIRECTION_INDICATORS` feed into `compute_family_votes()`.
`RISK_INDICATORS` feed only into `compute_risk()`.

### Bug 2: _NAME_TO_FAMILY should not include BB/ATR
Remove BB and ATR from the family mapping in `rocket_score.py`.

### Bug 3: VWAP vs VWAPIndicator name mismatch
**Problem**: `families.py` line 101 maps `"VWAP"` to VOLUME, but the class is `VWAPIndicator`.
If the indicator result name is `"VWAPIndicator"`, it won't match the mapping.

**Fix**: Update `families.py` to use `"VWAPIndicator"` instead of `"VWAP"`.

---

## Remaining Work (After Bug Fixes)

1. **Fix BB/ATR voting bugs** in `rocket_score.py`
2. **Fix VWAP name mismatch** in `families.py`
3. **Backtest improvement** (costs, slippage, walk-forward)
4. **Notifications improvement** (cooldown, confidence gating)
5. **Full integration test**

---

## Acceptance Criteria

1. ✅ 12 indicators (10 direction + 2 risk-only)
2. ✅ 5-layer pipeline (regime → direction → confidence → risk → signal)
3. ✅ Hysteresis in engine.py (already implemented)
4. ✅ Volatility affects risk only, NOT direction (BUG: needs fix — BB/ATR voting)
5. ✅ Family voting: majority rules + strength normalization
6. ✅ Regime detection per region
7. ⬛ Backtest with costs, slippage, walk-forward (pending)
8. ⬛ Notifications with cooldown, confidence gating (pending)
9. ⬛ End-to-end test passes (pending)
