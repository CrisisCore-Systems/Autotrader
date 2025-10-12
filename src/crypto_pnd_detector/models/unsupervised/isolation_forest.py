"""Simple density based anomaly scoring inspired by Isolation Forest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence


@dataclass
class FeatureSample:
    token_id: str
    values: Dict[str, float]


class SimpleIsolationForest:
    """Computes anomaly scores using feature z-scores."""

    def __init__(self) -> None:
        self._means: Dict[str, float] = {}
        self._stds: Dict[str, float] = {}

    def fit(self, samples: Sequence[FeatureSample]) -> None:
        if not samples:
            raise ValueError("Cannot fit isolation forest without samples")

        feature_names = {name for sample in samples for name in sample.values}
        for name in feature_names:
            column = [float(sample.values.get(name, 0.0)) for sample in samples]
            mean = sum(column) / len(column)
            variance = sum((value - mean) ** 2 for value in column) / len(column)
            std = variance ** 0.5 or 1.0
            self._means[name] = mean
            self._stds[name] = std

    def score(self, features: Dict[str, float]) -> float:
        z_scores = []
        for name, mean in self._means.items():
            std = self._stds.get(name, 1.0)
            z_scores.append(abs((features.get(name, 0.0) - mean) / std))
        if not z_scores:
            return 0.0
        return float(sum(z_scores) / len(z_scores))

    def is_anomaly(self, features: Dict[str, float], *, threshold: float = 2.5) -> bool:
        return self.score(features) >= threshold
