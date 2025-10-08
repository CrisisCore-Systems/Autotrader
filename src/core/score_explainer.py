"""GemScore delta explainability utilities.

This module provides functionality to explain what features contributed
most to GemScore changes between snapshots.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.core.scoring import GemScoreResult, WEIGHTS


@dataclass
class FeatureDelta:
    """Represents a change in a single feature."""

    feature_name: str
    previous_value: float
    current_value: float
    delta_value: float  # current - previous
    previous_contribution: float  # weight * previous_value
    current_contribution: float  # weight * current_value
    delta_contribution: float  # change in contribution to score
    percent_change: float  # percentage change in value
    weight: float  # feature weight in scoring formula


@dataclass
class ScoreDelta:
    """Represents a complete GemScore delta analysis."""

    token_symbol: str
    previous_score: float
    current_score: float
    delta_score: float  # current - previous
    percent_change: float  # percentage change in score
    previous_timestamp: float
    current_timestamp: float
    time_delta_hours: float
    
    # Feature deltas sorted by contribution impact (descending)
    feature_deltas: List[FeatureDelta] = field(default_factory=list)
    
    # Top positive contributors (features that increased score most)
    top_positive_contributors: List[FeatureDelta] = field(default_factory=list)
    
    # Top negative contributors (features that decreased score most)
    top_negative_contributors: List[FeatureDelta] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, object] = field(default_factory=dict)

    def get_summary(self, top_n: int = 5) -> Dict[str, object]:
        """Get a human-readable summary of the delta.

        Args:
            top_n: Number of top contributors to include

        Returns:
            Summary dictionary
        """
        return {
            "token": self.token_symbol,
            "score_change": {
                "previous": round(self.previous_score, 2),
                "current": round(self.current_score, 2),
                "delta": round(self.delta_score, 2),
                "percent_change": round(self.percent_change, 2),
            },
            "time_delta_hours": round(self.time_delta_hours, 2),
            "top_positive_contributors": [
                {
                    "feature": fd.feature_name,
                    "value_change": round(fd.delta_value, 4),
                    "percent_change": round(fd.percent_change, 2),
                    "contribution_impact": round(fd.delta_contribution * 100, 2),  # Scale to 0-100
                }
                for fd in self.top_positive_contributors[:top_n]
            ],
            "top_negative_contributors": [
                {
                    "feature": fd.feature_name,
                    "value_change": round(fd.delta_value, 4),
                    "percent_change": round(fd.percent_change, 2),
                    "contribution_impact": round(fd.delta_contribution * 100, 2),  # Scale to 0-100
                }
                for fd in self.top_negative_contributors[:top_n]
            ],
        }

    def get_narrative(self) -> str:
        """Generate a natural language narrative explaining the score change.

        Returns:
            Human-readable explanation
        """
        direction = "increased" if self.delta_score >= 0 else "decreased"
        magnitude = abs(self.delta_score)
        
        lines = [
            f"GemScore for {self.token_symbol} {direction} by {magnitude:.2f} points "
            f"({self.percent_change:+.1f}%) from {self.previous_score:.2f} to {self.current_score:.2f} "
            f"over {self.time_delta_hours:.1f} hours."
        ]
        
        if self.top_positive_contributors:
            lines.append("\nKey positive drivers:")
            for i, fd in enumerate(self.top_positive_contributors[:3], 1):
                impact_points = fd.delta_contribution * 100  # Scale to 0-100
                lines.append(
                    f"  {i}. {fd.feature_name}: {fd.percent_change:+.1f}% "
                    f"({impact_points:+.2f} points)"
                )
        
        if self.top_negative_contributors:
            lines.append("\nKey negative drivers:")
            for i, fd in enumerate(self.top_negative_contributors[:3], 1):
                impact_points = fd.delta_contribution * 100  # Scale to 0-100
                lines.append(
                    f"  {i}. {fd.feature_name}: {fd.percent_change:+.1f}% "
                    f"({impact_points:.2f} points)"
                )
        
        return "\n".join(lines)


@dataclass
class GemScoreSnapshot:
    """Complete snapshot of a GemScore calculation."""

    token_symbol: str
    timestamp: float
    score: float
    confidence: float
    features: Dict[str, float]  # Raw feature values (0-1 normalized)
    contributions: Dict[str, float]  # Feature contributions to score
    metadata: Dict[str, object] = field(default_factory=dict)


class ScoreExplainer:
    """Explains GemScore changes between snapshots."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """Initialize explainer.

        Args:
            weights: Feature weights (defaults to standard WEIGHTS)
        """
        self.weights = weights or WEIGHTS

    def compute_delta(
        self,
        previous_snapshot: GemScoreSnapshot,
        current_snapshot: GemScoreSnapshot,
    ) -> ScoreDelta:
        """Compute delta explanation between two snapshots.

        Args:
            previous_snapshot: Previous score snapshot
            current_snapshot: Current score snapshot

        Returns:
            Delta analysis
        """
        if previous_snapshot.token_symbol != current_snapshot.token_symbol:
            raise ValueError(
                f"Token symbol mismatch: {previous_snapshot.token_symbol} != {current_snapshot.token_symbol}"
            )

        # Calculate score delta
        delta_score = current_snapshot.score - previous_snapshot.score
        percent_change = (
            (delta_score / previous_snapshot.score * 100)
            if previous_snapshot.score > 0
            else 0.0
        )

        # Calculate time delta
        time_delta_seconds = current_snapshot.timestamp - previous_snapshot.timestamp
        time_delta_hours = time_delta_seconds / 3600.0

        # Compute feature deltas
        feature_deltas = []
        all_features = set(previous_snapshot.features.keys()) | set(current_snapshot.features.keys())

        for feature_name in all_features:
            prev_value = previous_snapshot.features.get(feature_name, 0.0)
            curr_value = current_snapshot.features.get(feature_name, 0.0)
            weight = self.weights.get(feature_name, 0.0)

            delta_value = curr_value - prev_value
            prev_contribution = weight * prev_value
            curr_contribution = weight * curr_value
            delta_contribution = curr_contribution - prev_contribution

            # Calculate percent change safely
            if prev_value > 0:
                pct_change = (delta_value / prev_value) * 100
            elif curr_value > 0:
                pct_change = 100.0  # From 0 to something positive
            else:
                pct_change = 0.0  # No change (0 to 0)

            feature_delta = FeatureDelta(
                feature_name=feature_name,
                previous_value=prev_value,
                current_value=curr_value,
                delta_value=delta_value,
                previous_contribution=prev_contribution,
                current_contribution=curr_contribution,
                delta_contribution=delta_contribution,
                percent_change=pct_change,
                weight=weight,
            )
            feature_deltas.append(feature_delta)

        # Sort by absolute contribution impact
        feature_deltas.sort(key=lambda fd: abs(fd.delta_contribution), reverse=True)

        # Separate positive and negative contributors
        positive_contributors = [fd for fd in feature_deltas if fd.delta_contribution > 0]
        negative_contributors = [fd for fd in feature_deltas if fd.delta_contribution < 0]

        # Sort by contribution impact (not absolute)
        positive_contributors.sort(key=lambda fd: fd.delta_contribution, reverse=True)
        negative_contributors.sort(key=lambda fd: fd.delta_contribution)  # Most negative first

        return ScoreDelta(
            token_symbol=current_snapshot.token_symbol,
            previous_score=previous_snapshot.score,
            current_score=current_snapshot.score,
            delta_score=delta_score,
            percent_change=percent_change,
            previous_timestamp=previous_snapshot.timestamp,
            current_timestamp=current_snapshot.timestamp,
            time_delta_hours=time_delta_hours,
            feature_deltas=feature_deltas,
            top_positive_contributors=positive_contributors,
            top_negative_contributors=negative_contributors,
        )

    def create_snapshot(
        self,
        token_symbol: str,
        gem_score_result: GemScoreResult,
        features: Dict[str, float],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> GemScoreSnapshot:
        """Create a snapshot from a GemScore result.

        Args:
            token_symbol: Token symbol
            gem_score_result: GemScore calculation result
            features: Feature values used in calculation
            timestamp: Timestamp (uses current time if not provided)
            metadata: Additional metadata

        Returns:
            Score snapshot
        """
        if timestamp is None:
            timestamp = time.time()

        return GemScoreSnapshot(
            token_symbol=token_symbol,
            timestamp=timestamp,
            score=gem_score_result.score,
            confidence=gem_score_result.confidence,
            features=features.copy(),
            contributions=gem_score_result.contributions.copy(),
            metadata=metadata or {},
        )

    def find_most_impactful_features(
        self,
        delta: ScoreDelta,
        top_n: int = 5,
    ) -> Tuple[List[str], List[str]]:
        """Find the most impactful features (positive and negative).

        Args:
            delta: Score delta analysis
            top_n: Number of top features to return

        Returns:
            Tuple of (positive_features, negative_features)
        """
        positive = [fd.feature_name for fd in delta.top_positive_contributors[:top_n]]
        negative = [fd.feature_name for fd in delta.top_negative_contributors[:top_n]]
        return positive, negative

    def explain_score_change(
        self,
        delta: ScoreDelta,
        threshold: float = 0.01,  # 1 point threshold
    ) -> Dict[str, object]:
        """Provide a detailed explanation of score change.

        Args:
            delta: Score delta analysis
            threshold: Minimum contribution change to report (in points)

        Returns:
            Detailed explanation dictionary
        """
        significant_changes = [
            fd for fd in delta.feature_deltas
            if abs(fd.delta_contribution * 100) >= threshold
        ]

        return {
            "overview": {
                "score_changed": delta.delta_score,
                "percent_change": delta.percent_change,
                "time_elapsed_hours": delta.time_delta_hours,
                "direction": "increase" if delta.delta_score >= 0 else "decrease",
            },
            "significant_changes": [
                {
                    "feature": fd.feature_name,
                    "value_change": {
                        "previous": fd.previous_value,
                        "current": fd.current_value,
                        "delta": fd.delta_value,
                        "percent": fd.percent_change,
                    },
                    "contribution_change": {
                        "previous": fd.previous_contribution * 100,
                        "current": fd.current_contribution * 100,
                        "delta": fd.delta_contribution * 100,
                    },
                    "weight": fd.weight,
                    "impact": "positive" if fd.delta_contribution > 0 else "negative",
                }
                for fd in significant_changes
            ],
            "narrative": delta.get_narrative(),
        }


def create_snapshot_from_result(
    token_symbol: str,
    gem_score_result: GemScoreResult,
    features: Dict[str, float],
    timestamp: Optional[float] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> GemScoreSnapshot:
    """Convenience function to create a snapshot.

    Args:
        token_symbol: Token symbol
        gem_score_result: GemScore result
        features: Feature dictionary
        timestamp: Timestamp (current time if None)
        metadata: Additional metadata

    Returns:
        GemScore snapshot
    """
    explainer = ScoreExplainer()
    return explainer.create_snapshot(
        token_symbol=token_symbol,
        gem_score_result=gem_score_result,
        features=features,
        timestamp=timestamp,
        metadata=metadata,
    )
