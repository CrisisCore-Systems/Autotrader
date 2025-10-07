"""GemScore calculation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

WEIGHTS = {
    "SentimentScore": 0.15,
    "AccumulationScore": 0.20,
    "OnchainActivity": 0.15,
    "LiquidityDepth": 0.10,
    "TokenomicsRisk": 0.12,
    "ContractSafety": 0.12,
    "NarrativeMomentum": 0.08,
    "CommunityGrowth": 0.08,
}


@dataclass
class GemScoreResult:
    score: float
    confidence: float
    contributions: Dict[str, float]


def compute_gem_score(features: Dict[str, float]) -> GemScoreResult:
    """Compute the weighted GemScore and contribution breakdown."""

    contributions = {}
    total = 0.0
    for key, weight in WEIGHTS.items():
        value = float(np.clip(features.get(key, 0.0), 0.0, 1.0))
        contribution = weight * value
        contributions[key] = contribution
        total += contribution

    score = float(np.clip(total, 0.0, 1.0)) * 100
    confidence = compute_confidence(features)
    return GemScoreResult(score=score, confidence=confidence, contributions=contributions)


def compute_confidence(features: Dict[str, float]) -> float:
    """Confidence = 0.5 * Recency + 0.5 * DataCompleteness."""

    recency = float(np.clip(features.get("Recency", 0.0), 0.0, 1.0))
    completeness = float(np.clip(features.get("DataCompleteness", 0.0), 0.0, 1.0))
    return (0.5 * recency + 0.5 * completeness) * 100


def should_flag_asset(result: GemScoreResult, features: Dict[str, float]) -> Tuple[bool, Dict[str, float]]:
    """Determine if an asset should enter the review queue."""

    safety_pass = features.get("ContractSafety", 0.0) >= 0.7
    signals = sum(
        1 for key in ("AccumulationScore", "NarrativeMomentum", "OnchainActivity") if features.get(key, 0.0) >= 0.6
    )
    meets_threshold = result.score >= 70 and safety_pass and signals >= 3
    debug = {
        "safety_pass": safety_pass,
        "signals": signals,
        "score": result.score,
        "confidence": result.confidence,
    }
    return meets_threshold, debug
