"""Ensemble predictor combining multiple model families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from .supervised.xgboost_detector import TrainingSample, XGBoostBaselineDetector
from .unsupervised.isolation_forest import FeatureSample, SimpleIsolationForest
from .deep_learning.lstm_temporal import SequenceSample, TemporalPumpLSTM
from .explainability.shap_explainer import SimpleFeatureExplainer


@dataclass
class EnsemblePrediction:
    probability: float
    anomaly_score: float
    temporal_score: float
    explanation: Tuple[Tuple[str, float], ...]


class ExplainablePumpDetector:
    """Hybrid ensemble aligning with the roadmap specification."""

    def __init__(self) -> None:
        self._xgboost = XGBoostBaselineDetector()
        self._isolation = SimpleIsolationForest()
        self._lstm = TemporalPumpLSTM()
        self._explainer = SimpleFeatureExplainer()

    def fit(
        self,
        *,
        supervised_samples: Iterable[TrainingSample],
        unsupervised_samples: Iterable[FeatureSample],
        temporal_samples: Iterable[SequenceSample],
    ) -> None:
        supervised_samples = list(supervised_samples)
        unsupervised_samples = list(unsupervised_samples)
        temporal_samples = list(temporal_samples)
        if supervised_samples:
            self._xgboost.fit(supervised_samples)
        if unsupervised_samples:
            self._isolation.fit(unsupervised_samples)
        if temporal_samples:
            self._lstm.fit(temporal_samples)

    def predict(self, *, features: Dict[str, float], sequence: Iterable[float]) -> EnsemblePrediction:
        probability = self._xgboost.predict_proba(features)
        anomaly_score = self._isolation.score(features)
        temporal_score = self._lstm.predict_proba(list(sequence))
        explanation = tuple(self._explainer.explain(features))
        return EnsemblePrediction(
            probability=probability,
            anomaly_score=anomaly_score,
            temporal_score=temporal_score,
            explanation=explanation,
        )
