"""Rank tickers per region by overall score."""
from typing import Dict, List
from .models import RocketScore


def rank_regions(
    region_scores: Dict[str, List[RocketScore]],
    top_n: int = 20
) -> Dict[str, List[RocketScore]]:
    """Rank tickers within each region by overall_score descending.
    Returns new dict with sorted, truncated lists.
    """
    ranked = {}
    for region, scores in region_scores.items():
        # Only include tickers that passed filters
        filtered = [s for s in scores if s.filter_passed]
        # Sort by overall_score descending
        sorted_scores = sorted(filtered, key=lambda s: s.overall_score, reverse=True)
        ranked[region] = sorted_scores[:top_n]
    return ranked


def top_overall(
    region_scores: Dict[str, List[RocketScore]],
    top_n: int = 20
) -> List[RocketScore]:
    """Get top N tickers across all regions."""
    all_scores = []
    for scores in region_scores.values():
        all_scores.extend(scores)
    all_scores.sort(key=lambda s: s.overall_score, reverse=True)
    return all_scores[:top_n]
