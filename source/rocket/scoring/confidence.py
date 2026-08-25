"""Confidence module — measures how reliable the direction signal is.

Confidence factors:
  1. Family agreement — how many families vote the same?
  2. Signal strength — how strong are the individual signals?
  3. Volume confirmation — does volume support the price direction?

Output: confidence_score (0.0 → 1.0)
  1.0 = all families agree + strong signals + volume confirms
  0.0 = families disagree + weak signals + volume contradicts
"""

from __future__ import annotations

from dataclasses import dataclass

from ..technical.families import FamilyVote, Vote


@dataclass
class ConfidenceResult:
    confidence_score: float  # 0.0 → 1.0
    agreement: float  # 0.0–1.0
    avg_strength: float  # 0.0–1.0
    volume_confirmed: bool
    factors: list[str] | None = None


def compute_confidence(
    family_votes: list[FamilyVote],
    volume_votes: list[FamilyVote],
    indicator_strengths: list[float] | None = None,
) -> ConfidenceResult:
    """Compute confidence from family votes and signal characteristics.

    Confidence = 0.5 × agreement + 0.3 × avg_strength + 0.2 × volume_confirmed

    Agreement (0.0–1.0):
      All 3 families agree → 1.0
      2 agree, 1 different → 0.6 (the 2/3 ratio)
      All different → 0.0

    Average Strength (0.0–1.0):
      Average of |family.strength| across all families

    Volume Confirmation (0.0–1.0):
      Volume family vote matches overall direction → 1.0
      Volume disagrees → 0.2
      Volume absent → 0.5 (neutral)
    """
    if not family_votes:
        return ConfidenceResult(
            confidence_score=0.0,
            agreement=0.0,
            avg_strength=0.0,
            volume_confirmed=False,
            factors=["no data"],
        )

    # --- Factor 1: Agreement ---
    if len(family_votes) >= 3:
        buy_count = sum(1 for fv in family_votes if fv.vote == Vote.BUY)
        sell_count = sum(1 for fv in family_votes if fv.vote == Vote.SELL)
        if buy_count >= 2:
            agreement = buy_count / len(family_votes)  # 1.0 if all BUY
        elif sell_count >= 2:
            agreement = sell_count / len(family_votes)  # 1.0 if all SELL
        else:
            # Mixed — partial agreement
            max_any = max(buy_count, sell_count)
            agreement = max_any / len(family_votes)  # e.g., 2/3 = 0.67
    else:
        # Fewer families — partial credit
        votes = [fv.vote for fv in family_votes]
        if len(set(votes)) == 1:
            agreement = 1.0
        else:
            agreement = 0.5  # some agreement, some not

    # --- Factor 2: Average Signal Strength ---
    if indicator_strengths:
        avg_strength = sum(indicator_strengths) / len(indicator_strengths)
    else:
        # Fall back to family-level strengths
        avg_strength = sum(abs(fv.strength) for fv in family_votes) / len(family_votes)

    # --- Factor 3: Volume Confirmation ---
    if volume_votes:
        overall_vote = _overall_vote(family_votes)
        vol_vote = volume_votes[0].vote
        volume_confirmed = (vol_vote == overall_vote)
        volume_factor = 1.0 if volume_confirmed else 0.2
    else:
        volume_confirmed = False
        volume_factor = 0.5  # no volume data → neutral

    # --- Combined confidence ---
    confidence = 0.5 * agreement + 0.3 * avg_strength + 0.2 * volume_factor
    confidence = max(0.0, min(1.0, confidence))

    factors = [
        f"Agreement:{agreement:.2f}",
        f"Strength:{avg_strength:.2f}",
        f"Volume confirm:{'yes' if volume_confirmed else 'no'}:{volume_factor:.2f}",
    ]

    return ConfidenceResult(
        confidence_score=confidence,
        agreement=agreement,
        avg_strength=avg_strength,
        volume_confirmed=volume_confirmed,
        factors=factors,
    )


def _overall_vote(family_votes: list[FamilyVote]) -> Vote:
    """Determine the overall direction from family votes."""
    buy_count = sum(1 for fv in family_votes if fv.vote == Vote.BUY)
    sell_count = sum(1 for fv in family_votes if fv.vote == Vote.SELL)

    if buy_count > sell_count:
        return Vote.BUY
    elif sell_count > buy_count:
        return Vote.SELL
    return Vote.HOLD
