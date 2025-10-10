"""Lightweight baseline imitating the XGBoost contract using numpy."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Dict, Sequence


@dataclass
class TrainingSample:
    features: Dict[str, float]
    label: int


class SimpleGradientBooster:
    """Implements a tiny gradient boosting like learner for demonstration."""

    def __init__(self, *, learning_rate: float = 0.1, n_rounds: int = 100) -> None:
        self.learning_rate = learning_rate
        self.n_rounds = n_rounds
        self.feature_weights: Dict[str, float] = {}
        self.bias = 0.0

    def fit(self, samples: Sequence[TrainingSample]) -> None:
        if not samples:
            raise ValueError("No samples provided")
        feature_names = sorted({name for sample in samples for name in sample.features})
        weight_vector = {name: 0.0 for name in feature_names}
        bias = 0.0

        for _ in range(self.n_rounds):
            weight_gradients = {name: 0.0 for name in feature_names}
            bias_gradient = 0.0
            for sample in samples:
                logit = bias
                for name in feature_names:
                    logit += weight_vector[name] * sample.features.get(name, 0.0)
                pred = 1.0 / (1.0 + exp(-logit))
                error = pred - sample.label
                for name in feature_names:
                    weight_gradients[name] += error * sample.features.get(name, 0.0)
                bias_gradient += error
            for name in feature_names:
                weight_vector[name] -= self.learning_rate * (weight_gradients[name] / len(samples))
            bias -= self.learning_rate * (bias_gradient / len(samples))

        self.feature_weights = weight_vector
        self.bias = bias

    def predict_proba(self, features: Dict[str, float]) -> float:
        logit = self.bias
        for name, weight in self.feature_weights.items():
            logit += weight * features.get(name, 0.0)
        return float(1.0 / (1.0 + exp(-logit)))


class XGBoostBaselineDetector:
    """Wrapper around :class:`SimpleGradientBooster` to mimic XGBoost usage."""

    def __init__(self, *, recall_target: float = 0.93) -> None:
        self._booster = SimpleGradientBooster()
        self.recall_target = recall_target
        self.threshold = 0.5

    def fit(self, samples: Sequence[TrainingSample]) -> None:
        self._booster.fit(samples)
        positives = [sample for sample in samples if sample.label == 1]
        if not positives:
            return
        scores = sorted(self._booster.predict_proba(sample.features) for sample in positives)
        quantile = min(max(1.0 - self.recall_target, 0.0), 1.0)
        index = int(quantile * (len(scores) - 1)) if scores else 0
        self.threshold = float(scores[index])

    def predict(self, features: Dict[str, float]) -> int:
        return int(self._booster.predict_proba(features) >= self.threshold)

    def predict_proba(self, features: Dict[str, float]) -> float:
        return self._booster.predict_proba(features)
