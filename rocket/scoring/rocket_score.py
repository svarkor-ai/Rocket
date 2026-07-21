"""Compute full RocketScore for a single ticker using the v2 pipeline.

Pipeline:
  1. Run all 11 indicators
  2. Convert indicator results → IndicatorVotes
  3. Compute family consensus → DirectionResult
  4. Compute confidence from family agreement + signal strength
  5. Compute risk from ATR + Bollinger squeeze + volume anomaly
  6. Apply regime multiplier
  7. Final score = direction × confidence × risk_multiplier × regime_multiplier
  8. Apply hysteresis thresholds
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..data.models import TickerInfo
from ..technical.families import IndicatorVote, FamilyVote, Vote, FamilyName, combine, compute_family_votes
from ..technical.signal_combiner import SignalSummary, SignalCombiner  # kept for backward compat
from ..technical.momentum import RSI, MACD, ROC
from ..technical.trend import EMACrossover, ADX
from ..technical.volatility import BollingerBands, ATR
from ..technical.volume import OBV, MFI, VWAPIndicator
from ..technical.advanced import IchimokuCloud, Supertrend, AutoTrend, RubeGoldberg
from ..technical.patterns import (
    DoubleTopBottom, HeadShoulders, WedgePattern,
    AutoFractal, CupAndHandle, PatternDetectorCombined,
)
from .filter import apply_filters
from .risk import compute_risk, RiskResult
from .confidence import compute_confidence, ConfidenceResult
from ..technical.regime import detect_regime, RegimeResult, Regime


# All indicator instances (direction + risk)
INDICATORS = [
    # Momentum (3)
    RSI(), MACD(), ROC(),
    # Trend (9)
    EMACrossover(), ADX(), IchimokuCloud(), Supertrend(),
    AutoTrend(), RubeGoldberg(),
    DoubleTopBottom(), HeadShoulders(),
    WedgePattern(), AutoFractal(), CupAndHandle(),
    PatternDetectorCombined(),
    # Volatility (2) — risk-only, NOT in direction voting
    BollingerBands(), ATR(),
    # Volume (3)
    OBV(), MFI(), VWAPIndicator(),
]

# Direction indicators ONLY — used for family consensus voting
# BB and ATR are risk-only and must NOT vote in direction pipeline
DIRECTION_INDICATORS = [
    # Momentum (3)
    RSI(), MACD(), ROC(),
    # Trend (9)
    EMACrossover(), ADX(), IchimokuCloud(), Supertrend(),
    AutoTrend(), RubeGoldberg(),
    DoubleTopBottom(), HeadShoulders(),
    WedgePattern(), AutoFractal(), CupAndHandle(),
    PatternDetectorCombined(),
    # Volume (3)
    OBV(), MFI(), VWAPIndicator(),
]

# Mapping from indicator name → family
# BB and ATR intentionally NOT included — they are risk-only
_NAME_TO_FAMILY = {
    "RSI": FamilyName.MOMENTUM,
    "MACD": FamilyName.MOMENTUM,
    "ROC": FamilyName.MOMENTUM,
    "EMACrossover": FamilyName.TREND,
    "ADX": FamilyName.TREND,
    "Ichimoku": FamilyName.TREND,
    "IchimokuCloud": FamilyName.TREND,
    "Supertrend": FamilyName.TREND,
    "AutoTrend": FamilyName.TREND,
    "RubeGoldberg": FamilyName.TREND,
    "DoubleTopBottom": FamilyName.TREND,
    "HeadShoulders": FamilyName.TREND,
    "WedgePattern": FamilyName.TREND,
    "AutoFractal": FamilyName.TREND,
    "CupAndHandle": FamilyName.TREND,
    "PatternDetector": FamilyName.TREND,
    "PatternDetectorCombined": FamilyName.TREND,
    "OBV": FamilyName.VOLUME,
    "MFI": FamilyName.VOLUME,
    "VWAPIndicator": FamilyName.VOLUME,
}


class SignalStrength(str, Enum):
    STRONG_BULLISH = "Strong Bullish"
    BULLISH = "Bullish"
    MODERATE = "Moderate"
    NEUTRAL = "Neutral"
    WEAK = "Weak"
    STRONG_BEARISH = "Strong Bearish"
    BEARISH = "Bearish"


@dataclass
class RocketSignal:
    """Final output of the v2 scoring pipeline."""
    final_score: float  # -1.0 → +1.0 (direction × confidence × risk × regime)
    direction_score: float  # 0.0 → 1.0 (raw direction from family consensus)
    confidence: float  # 0.0 → 1.0
    risk_multiplier: float  # 0.5 → 1.0
    regime_multiplier: float  # 0.5 → 1.0
    signal: SignalStrength
    strength: str
    direction: str  # "BULLISH" or "BEARISH"
    regime: str  # "BULL", "BEAR", "CHOP"
    family_votes: list[dict] | None = None  # detail per family
    reason: str = ""  # human-readable reason


def _indicator_result_to_vote(
    result,  # IndicatorResult
) -> IndicatorVote | None:
    """Convert an IndicatorResult to an IndicatorVote."""
    signal = result.signal.value.lower() if hasattr(result, 'signal') else result.get('signal', 'HOLD')
    vote = Vote.HOLD
    if signal in ("buy", "bullish"):
        vote = Vote.BUY
    elif signal in ("sell", "bearish"):
        vote = Vote.SELL

    strength = abs(result.score) if hasattr(result, 'score') else abs(result.get('score', 0.0))

    family_name_str = result.category.value.lower() if hasattr(result, 'category') else result.get('category', 'trend')
    # Map category to family
    cat_to_family = {
        "momentum": FamilyName.MOMENTUM,
        "trend": FamilyName.TREND,
        "volatility": FamilyName.TREND,  # volatility maps to trend family for voting
        "volume": FamilyName.VOLUME,
    }
    family = cat_to_family.get(family_name_str, FamilyName.TREND)

    return IndicatorVote(
        name=result.name if hasattr(result, 'name') else result.get('name', 'Unknown'),
        vote=vote,
        strength=strength,
        family=family,
    )


def _strength_from_score(final_score: float, confidence: float) -> tuple[str, str]:
    """Determine signal strength from final score and confidence."""
    abs_score = abs(final_score)

    if abs_score < 0.2:
        return SignalStrength.NEUTRAL.value, "Neutral"
    if confidence < 0.4:
        return SignalStrength.WEAK.value, "Weak"
    if abs_score < 0.4:
        return SignalStrength.MODERATE.value, "Moderate"
    if abs_score < 0.6:
        if final_score > 0:
            return SignalStrength.BULLISH.value, "Bullish"
        return SignalStrength.BEARISH.value, "Bearish"
    if final_score > 0:
        return SignalStrength.STRONG_BULLISH.value, "Strong Bullish"
    return SignalStrength.STRONG_BEARISH.value, "Strong Bearish"


def compute_rocket_score(
    df,
    ticker_info: TickerInfo,
    current_price: float = 0.0,
    index_df=None,  # optional: regional index data for regime
    index_name: str = "^GSPC",  # regional index ticker
) -> dict:
    """Run all indicators, compute v2 pipeline scores, return dict."""
    # ─── Step 1: Run ALL indicators (direction + risk) ───
    results = []
    for indicator in INDICATORS:
        try:
            r = indicator.calculate(df)
            results.append(r)
        except Exception:
            pass

    # ─── Step 1b: Run direction indicators only for voting ───
    # BB and ATR are risk-only — they must NOT vote in family consensus
    direction_results = []
    for indicator in DIRECTION_INDICATORS:
        try:
            r = indicator.calculate(df)
            direction_results.append(r)
        except Exception:
            pass

    # ─── Step 2: Convert direction results to IndicatorVotes ───
    indicator_votes = []
    indicator_strengths = []
    for r in direction_results:
        try:
            vote = _indicator_result_to_vote(r)
            if vote:
                indicator_votes.append(vote)
                indicator_strengths.append(vote.strength)
        except Exception:
            pass

    # ─── Step 3: Family consensus → Direction ───
    direction_result, family_votes = combine(indicator_votes)

    # Separate volume family for confidence calc
    volume_families = [fv for fv in family_votes if fv.family == FamilyName.VOLUME]

    # ─── Step 4: Confidence ───
    confidence = compute_confidence(
        family_votes=family_votes,
        volume_votes=volume_families,
        indicator_strengths=indicator_strengths,
    )

    # ─── Step 5: Risk ───
    # Extract ATR and Bollinger values from results
    atr_val = 0.0
    bb_upper = bb_lower = bb_sma = 0.0
    vol_ratio = 1.0

    for r in results:
        name = r.name if hasattr(r, 'name') else r.get('name', '')
        vals = r.values if hasattr(r, 'values') else r.get('values', {})
        if name == "ATR":
            atr_val = r.score if hasattr(r, 'score') else r.get('score', 0.0)
        elif name in ("BollingerBands", "Bollinger Bands"):
            bb_upper = vals.get('upper', 0.0) or vals.get('upper_band', 0.0)
            bb_lower = vals.get('lower', 0.0) or vals.get('lower_band', 0.0)
            bb_sma = vals.get('sma', 0.0)
        elif name == "VWAPIndicator":
            # Volume info from VWAP indicator
            vol_data = vals.get('volume_ratio', None)
            if vol_data is not None:
                vol_ratio = vol_data

    # Calculate ATR% and Bollinger squeeze
    atr_pct = (atr_val / current_price * 100) if current_price > 0 else 0.0
    bb_squeeze = (bb_upper - bb_lower) / bb_sma if bb_sma > 0 else 0.05

    # Volume anomaly
    if vol_ratio == 1.0:
        vol_ratio = 1.0  # default if no data

    risk = compute_risk(
        atr_pct=atr_pct,
        bb_squeeze=bb_squeeze,
        volume_ratio=vol_ratio,
    )

    # ─── Step 6: Regime ───
    if index_df is not None and not index_df.empty:
        regime = detect_regime(index_df, index_name)
    else:
        regime = RegimeResult(
            regime=Regime.CHOP,
            score=0.0,
            multiplier=0.5,
            index_trend="no index data",
            factors=["no index data"],
        )

    # ─── Step 7: Final score ───
    # direction_score: 0.0→1.0, convert to -1.0→+1.0
    direction_signed = 2.0 * direction_result.score - 1.0  # normalize to [-1, 1]

    final_score = (
        direction_signed
        * confidence.confidence_score
        * risk.risk_multiplier
        * regime.multiplier
    )

    # Clamp to [-1, 1]
    final_score = max(-1.0, min(1.0, final_score))

    # ─── Step 8: Signal strength ───
    strength, strength_label = _strength_from_score(final_score, confidence.confidence_score)
    direction = "BULLISH" if final_score > 0 else "BEARISH"

    # Build reason string
    family_details = [
        f"{fv.family.value}: {fv.vote.value} ({fv.strength:+.2f})"
        for fv in family_votes
    ]
    reason = (
        f"{strength_label} ({direction}) | "
        f"dir={direction_result.score:.2f} conf={confidence.confidence_score:.2f} "
        f"risk={risk.risk_score:.2f} regime={regime.regime.value}"
    )

    # Convert family_votes to dicts for serialization
    family_vote_dicts = []
    for fv in family_votes:
        family_vote_dicts.append({
            "family": fv.family.value,
            "vote": fv.vote.value,
            "strength": round(fv.strength, 4),
            "count": fv.indicators_count,
        })

    rocket_signal = RocketSignal(
        final_score=round(final_score, 4),
        direction_score=round(direction_result.score, 4),
        confidence=round(confidence.confidence_score, 4),
        risk_multiplier=round(risk.risk_multiplier, 4),
        regime_multiplier=round(regime.multiplier, 4),
        signal=SignalStrength(strength),
        strength=strength_label,
        direction=direction,
        regime=regime.regime.value,
        family_votes=family_vote_dicts,
        reason=reason,
    )

    # Keep old SignalSummary for backward compatibility
    combiner = SignalCombiner()
    old_summary = combiner.combine(results)

    # Keep old weighter for backward compatibility
    filter_result = apply_filters(ticker_info, current_price)

    return {
        "rocket_score": round(final_score, 4),
        "signal_summary": old_summary,
        "filter_result": filter_result,
        "rocket_signal": rocket_signal,
        "direction_result": direction_result,
        "risk_result": risk,
        "confidence_result": confidence,
        "regime_result": regime,
    }
