"""GemScore calculation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from src.core.logging_config import get_logger
from src.core.metrics import record_gem_score, record_confidence_score, record_flagged_token
from src.core.tracing import trace_operation, add_span_attributes

# Initialize logger
logger = get_logger(__name__)

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
    
    with trace_operation("compute_gem_score") as span:
        contributions = {}
        total = 0.0
        
        logger.debug("compute_gem_score_start", feature_count=len(features))
        
        for key, weight in WEIGHTS.items():
            value = float(np.clip(features.get(key, 0.0), 0.0, 1.0))
            contribution = weight * value
            contributions[key] = contribution
            total += contribution

        score = float(np.clip(total, 0.0, 1.0)) * 100
        confidence = compute_confidence(features)
        
        # Add span attributes
        add_span_attributes(
            gem_score=score,
            confidence=confidence,
            total_contribution=total,
        )
        
        logger.info(
            "compute_gem_score_complete",
            score=score,
            confidence=confidence,
            contributions=contributions,
        )
        
        return GemScoreResult(score=score, confidence=confidence, contributions=contributions)


def compute_confidence(features: Dict[str, float]) -> float:
    """Confidence = 0.5 * Recency + 0.5 * DataCompleteness."""

    recency = float(np.clip(features.get("Recency", 0.0), 0.0, 1.0))
    completeness = float(np.clip(features.get("DataCompleteness", 0.0), 0.0, 1.0))
    return (0.5 * recency + 0.5 * completeness) * 100


def should_flag_asset(result: GemScoreResult, features: Dict[str, float]) -> Tuple[bool, Dict[str, float]]:
    """Determine if an asset should enter the review queue."""
    
    with trace_operation("should_flag_asset") as span:
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
        
        # Add span attributes
        add_span_attributes(
            flagged=meets_threshold,
            safety_pass=safety_pass,
            signal_count=signals,
        )
        
        logger.info(
            "asset_flag_evaluation",
            flagged=meets_threshold,
            score=result.score,
            confidence=result.confidence,
            safety_pass=safety_pass,
            signals=signals,
        )
        
        return meets_threshold, debug
