"""Minimal LSTM style temporal encoder built on numpy for deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class SequenceSample:
    series: Sequence[float]
    label: int


class TemporalPumpLSTM:
    """Imitates a simple LSTM using exponential smoothing heuristics."""

    def __init__(self, *, smoothing: float = 0.6) -> None:
        if not 0.0 < smoothing <= 1.0:
            raise ValueError("Smoothing factor must be within (0, 1]")
        self.smoothing = smoothing
        self.threshold = 0.5
        self._positives: list[float] = []

    def fit(self, samples: Iterable[SequenceSample]) -> None:
        positives = [sample for sample in samples if sample.label == 1]
        if not positives:
            self.threshold = 0.5
            return
        smoothed_values = sorted(self._smooth(sample.series) for sample in positives)
        mid = len(smoothed_values) // 2
        if len(smoothed_values) % 2 == 0:
            median = (smoothed_values[mid - 1] + smoothed_values[mid]) / 2
        else:
            median = smoothed_values[mid]
        self._positives = list(smoothed_values)
        self.threshold = float(median)

    def predict_proba(self, series: Sequence[float]) -> float:
        return float(self._smooth(series))

    def predict(self, series: Sequence[float]) -> int:
        return int(self.predict_proba(series) >= self.threshold)

    def _smooth(self, series: Sequence[float]) -> float:
        smoothed = 0.0
        for value in series:
            smoothed = self.smoothing * value + (1 - self.smoothing) * smoothed
        return smoothed
