"""Development deployment harness for the pump & dump detector."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Sequence

from ..data.collectors.base import BaseCollector, StaticSampleCollector
from ..data.storage.feature_store import FeatureRecord, InMemoryFeatureStore
from ..inference.realtime_pipeline import Detection, RealtimePumpDetector
from ..models.ensemble import ExplainablePumpDetector
from ..models.supervised.xgboost_detector import TrainingSample
from ..models.unsupervised.isolation_forest import FeatureSample
from ..models.deep_learning.lstm_temporal import SequenceSample
from ..training.baseline import train_baseline

__all__ = [
    "DevDeployment",
    "DevDeploymentConfig",
    "DevDeploymentResult",
    "build_dev_deployment",
    "run_dev_deployment",
]


@dataclass
class DevDeploymentConfig:
    """Configuration payload for constructing a development deployment."""

    collectors: Sequence[BaseCollector]
    detector: ExplainablePumpDetector
    feature_store: InMemoryFeatureStore
    probability_threshold: float


@dataclass
class DevDeployment:
    """Container returned by :func:`build_dev_deployment`."""

    config: DevDeploymentConfig
    pipeline: RealtimePumpDetector

    async def detect(self) -> "DevDeploymentResult":
        detections = list(await self.pipeline.process_events())
        return DevDeploymentResult(
            detections=detections,
            feature_records=list(self.config.feature_store.snapshot()),
        )


@dataclass
class DevDeploymentResult:
    """Result from executing :meth:`DevDeployment.detect`."""

    detections: Sequence[Detection]
    feature_records: Sequence[FeatureRecord]


def _default_training_data() -> tuple[
    Sequence[TrainingSample],
    Sequence[FeatureSample],
    Sequence[SequenceSample],
]:
    """Provide light-weight defaults mirroring the baseline trainer tests."""

    supervised = [
        TrainingSample(features={"momentum": 0.3, "volume_anomaly": 0.4}, label=1),
        TrainingSample(features={"momentum": -0.1, "volume_anomaly": -0.3}, label=0),
        TrainingSample(features={"momentum": 0.5, "volume_anomaly": 0.6}, label=1),
        TrainingSample(features={"momentum": -0.2, "volume_anomaly": -0.4}, label=0),
    ]
    unsupervised = [
        FeatureSample(token_id="token", values={"momentum": 0.1, "volume_anomaly": 0.05}),
        FeatureSample(token_id="token", values={"momentum": 0.0, "volume_anomaly": 0.0}),
    ]
    temporal = [
        SequenceSample(series=[0.1, 0.2, 0.5], label=1),
        SequenceSample(series=[0.1, 0.05, 0.02], label=0),
    ]
    return supervised, unsupervised, temporal


def build_dev_deployment(
    *,
    market_events: Sequence[dict[str, float | int | str]],
    social_events: Sequence[dict[str, float | int | str]] | None = None,
    probability_threshold: float = 0.5,
    collectors: Sequence[BaseCollector] | None = None,
    training_data: tuple[
        Sequence[TrainingSample],
        Sequence[FeatureSample],
        Sequence[SequenceSample],
    ] | None = None,
) -> DevDeployment:
    """Construct a :class:`DevDeployment` with sensible defaults."""

    supervised, unsupervised, temporal = training_data or _default_training_data()
    detector = train_baseline(
        supervised_samples=supervised,
        unsupervised_samples=unsupervised,
        temporal_samples=temporal,
    ).detector

    feature_store = InMemoryFeatureStore()
    if collectors is None:
        collectors = [
            StaticSampleCollector("market", list(market_events)),
        ]
        if social_events:
            collectors.append(StaticSampleCollector("social", list(social_events)))

    pipeline = RealtimePumpDetector(
        collectors=collectors,
        detector=detector,
        feature_store=feature_store,
        probability_threshold=probability_threshold,
    )

    config = DevDeploymentConfig(
        collectors=collectors,
        detector=detector,
        feature_store=feature_store,
        probability_threshold=probability_threshold,
    )
    return DevDeployment(config=config, pipeline=pipeline)


def run_dev_deployment(deployment: DevDeployment) -> DevDeploymentResult:
    """Execute a deployment synchronously using :func:`asyncio.run`."""

    return asyncio.run(deployment.detect())
