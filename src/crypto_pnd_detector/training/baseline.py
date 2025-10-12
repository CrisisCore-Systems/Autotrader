"""Baseline training workflow joining collectors, features and models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from ..models.ensemble import ExplainablePumpDetector
from ..models.supervised.xgboost_detector import TrainingSample
from ..models.unsupervised.isolation_forest import FeatureSample
from ..models.deep_learning.lstm_temporal import SequenceSample


@dataclass
class TrainingArtifacts:
    detector: ExplainablePumpDetector


def train_baseline(
    *,
    supervised_samples: Sequence[TrainingSample],
    unsupervised_samples: Sequence[FeatureSample],
    temporal_samples: Sequence[SequenceSample],
) -> TrainingArtifacts:
    detector = ExplainablePumpDetector()
    detector.fit(
        supervised_samples=supervised_samples,
        unsupervised_samples=unsupervised_samples,
        temporal_samples=temporal_samples,
    )
    return TrainingArtifacts(detector=detector)
