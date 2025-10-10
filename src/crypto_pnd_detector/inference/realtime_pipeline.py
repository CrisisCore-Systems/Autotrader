"""Realtime detection pipeline orchestrating streaming, feature store and ensemble."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from ..data.collectors.base import BaseCollector
from ..data.collectors.streaming import StreamingIngestionOrchestrator
from ..data.preprocessing.feature_engineering import (
    FeatureVector,
    build_market_features,
    build_social_features,
    combine_features,
)
from ..data.storage.feature_store import FeatureRecord, InMemoryFeatureStore
from ..models.ensemble import EnsemblePrediction, ExplainablePumpDetector


@dataclass
class Detection:
    token_id: str
    prediction: EnsemblePrediction


class RealtimePumpDetector:
    """Coordinates collectors, features and ensemble inference."""

    def __init__(
        self,
        collectors: Sequence[BaseCollector],
        detector: ExplainablePumpDetector,
        feature_store: InMemoryFeatureStore | None = None,
        *,
        probability_threshold: float = 0.8,
    ) -> None:
        self.collectors = collectors
        self.detector = detector
        self.feature_store = feature_store or InMemoryFeatureStore()
        self.probability_threshold = probability_threshold

    async def process_events(self) -> Iterable[Detection]:
        orchestrator = StreamingIngestionOrchestrator(self.collectors, batch_size=16)
        detections: list[Detection] = []
        async for batch in orchestrator.batches():
            grouped = batch.by_source()
            market_events = [event.payload for event in grouped.get("market", [])]
            social_events = [event.payload for event in grouped.get("social", [])]
            if not market_events:
                continue
            token_id = str(market_events[-1].get("token_id", "unknown"))
            market_features = build_market_features(market_events, token_id=token_id)
            social_features = build_social_features(social_events, token_id=token_id)
            combined = combine_features((market_features, social_features))
            self.feature_store.put(FeatureRecord(token_id=token_id, values=combined))
            temporal_sequence = [event["price"] for event in market_events if "price" in event]
            prediction = self.detector.predict(features=combined, sequence=temporal_sequence)
            if prediction.probability >= self.probability_threshold:
                detections.append(Detection(token_id=token_id, prediction=prediction))
        return detections


def build_realtime_detector(*, collectors: Sequence[BaseCollector], detector: ExplainablePumpDetector) -> RealtimePumpDetector:
    return RealtimePumpDetector(collectors=collectors, detector=detector)
