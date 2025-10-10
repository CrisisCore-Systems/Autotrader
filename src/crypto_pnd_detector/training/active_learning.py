"""Active learning utilities for uncertainty based sampling."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2
from typing import Iterable, List, Sequence


@dataclass
class UnlabeledSample:
    identifier: str
    probabilities: Sequence[float]


class ActiveLabelingSystem:
    """Selects samples with highest predictive entropy."""

    def __init__(self, *, budget: int = 10) -> None:
        if budget <= 0:
            raise ValueError("Budget must be positive")
        self.budget = budget

    def select_samples_for_labeling(self, pool: Iterable[UnlabeledSample]) -> List[str]:
        scored: List[tuple[str, float]] = []
        for sample in pool:
            probs = list(sample.probabilities)
            total = sum(probs)
            if total == 0:
                probs = [1.0 / len(probs) for _ in probs]
            else:
                probs = [value / total for value in probs]
            entropy = 0.0
            for prob in probs:
                prob = max(prob, 1e-12)
                entropy -= prob * log2(prob)
            scored.append((sample.identifier, entropy))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [identifier for identifier, _ in scored[: self.budget]]
