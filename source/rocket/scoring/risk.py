"""Risk module — volatility-based risk assessment only.

Risk does NOT affect direction. It ONLY modulates confidence.
High risk = lower confidence (more uncertainty in signals).
Low risk = full confidence (signals are more reliable).

Inputs:
  - ATR%: absolute volatility (ATR / close × 100)
  - Bollinger squeeze: (upper - lower) / SMA
  - Volume anomaly: current_volume / avg_volume

Output:
  - risk_score: 0.0 (very low risk) → 1.0 (very high risk)
  - risk_multiplier: 1.0 (low risk, full confidence) → 0.5 (high risk, halved)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskResult:
    risk_score: float  # 0.0–1.0
    risk_multiplier: float  # 0.5–1.0
    atr_pct: float = 0.0
    bb_squeeze: float = 0.0
    volume_anomaly: float = 0.0
    factors: list[str] | None = None  # list of "factor: score" strings


def compute_risk(
    atr_pct: float,
    bb_squeeze: float,
    volume_ratio: float = 1.0,
) -> RiskResult:
    """Compute risk from ATR, Bollinger squeeze, and volume anomaly.

    Risk factors:
      1. ATR%: high absolute volatility → higher risk
         < 2% → 0.0, 2-5% → 0.5, > 5% → 1.0
      2. Bollinger squeeze: narrow bands → potential explosion → higher risk
         < 0.03 → 0.9, 0.03-0.08 → 0.4, > 0.08 → 0.1
      3. Volume anomaly: extreme volume → higher uncertainty
         < 2x → 0.0, 2-5x → 0.5, > 5x → 1.0

    Risk multiplier = 1.0 - weighted_risk_score × 0.5
      Low risk (0.0) → multiplier = 1.0 (full confidence)
      High risk (1.0) → multiplier = 0.5 (halved confidence)
    """
    # Factor 1: ATR% (higher = more risky)
    if atr_pct < 2.0:
        atr_risk = 0.0
    elif atr_pct < 5.0:
        atr_risk = (atr_pct - 2.0) / 3.0  # 0.0–1.0 linearly between 2 and 5
    else:
        atr_risk = min(1.0, (atr_pct - 5.0) / 5.0 + 0.5)  # 0.5–1.0 for > 5%

    # Factor 2: Bollinger squeeze (narrower = more risky)
    if bb_squeeze < 0.03:
        bb_risk = 0.9  # extreme squeeze → high risk
    elif bb_squeeze < 0.08:
        bb_risk = 0.4  # moderate
    else:
        bb_risk = 0.1  # wide bands → low risk

    # Factor 3: Volume anomaly (extreme = more risky)
    if volume_ratio < 2.0:
        vol_risk = 0.0
    elif volume_ratio < 5.0:
        vol_risk = (volume_ratio - 2.0) / 6.0  # 0.0–0.5 linearly between 2 and 5
    else:
        vol_risk = min(1.0, (volume_ratio - 5.0) / 10.0 + 0.5)  # 0.5–1.0 for > 5x

    # Weighted risk score (ATR is most important)
    weighted_risk = 0.4 * atr_risk + 0.3 * bb_risk + 0.3 * vol_risk

    # Clamp to [0, 1]
    risk_score = max(0.0, min(1.0, weighted_risk))

    # Risk multiplier: 1.0 (safe) → 0.5 (risky)
    risk_multiplier = 1.0 - risk_score * 0.5

    factors = [
        f"ATR%:{atr_pct:.2f}→{atr_risk:.2f}",
        f"BB squeeze:{bb_squeeze:.3f}→{bb_risk:.2f}",
        f"Vol ratio:{volume_ratio:.1f}×→{vol_risk:.2f}",
    ]

    return RiskResult(
        risk_score=risk_score,
        risk_multiplier=risk_multiplier,
        atr_pct=atr_pct,
        bb_squeeze=bb_squeeze,
        volume_anomaly=volume_ratio,
        factors=factors,
    )
