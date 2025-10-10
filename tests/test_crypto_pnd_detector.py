import asyncio

from src.crypto_pnd_detector.data.collectors.base import StaticSampleCollector
from src.crypto_pnd_detector.data.preprocessing.feature_engineering import (
    FeatureVector,
    build_market_features,
    build_social_features,
    combine_features,
)
from src.crypto_pnd_detector.inference.realtime_pipeline import RealtimePumpDetector
from src.crypto_pnd_detector.models.ensemble import ExplainablePumpDetector
from src.crypto_pnd_detector.models.supervised.xgboost_detector import TrainingSample
from src.crypto_pnd_detector.models.unsupervised.isolation_forest import FeatureSample
from src.crypto_pnd_detector.models.deep_learning.lstm_temporal import SequenceSample
from src.crypto_pnd_detector.training.baseline import train_baseline


def _build_detector() -> ExplainablePumpDetector:
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
    trained = train_baseline(
        supervised_samples=supervised,
        unsupervised_samples=unsupervised,
        temporal_samples=temporal,
    )
    return trained.detector


def test_feature_engineering_combines_market_and_social_metrics():
    market_events = [
        {"timestamp": 1, "price": 10.0, "volume": 100.0, "gas_fee": 1.0},
        {"timestamp": 2, "price": 11.0, "volume": 180.0, "gas_fee": 1.5},
        {"timestamp": 3, "price": 13.0, "volume": 250.0, "gas_fee": 2.0},
    ]
    social_events = [
        {"sentiment": 0.6, "is_bot": 0.0, "reach": 1000},
        {"sentiment": 0.8, "is_bot": 1.0, "reach": 1500},
    ]

    market_features = build_market_features(market_events, token_id="XYZ")
    social_features = build_social_features(social_events, token_id="XYZ")
    combined = combine_features((market_features, social_features))

    assert set(combined.keys()) == {
        "momentum",
        "volume_anomaly",
        "gas_spike",
        "avg_sentiment",
        "bot_ratio",
        "hype",
    }
    assert combined["bot_ratio"] == 0.5
    assert combined["hype"] > 0


def test_realtime_pipeline_flags_high_probability_events():
    detector = _build_detector()

    market_collector = StaticSampleCollector(
        "market",
        [
            {"timestamp": 1, "token_id": "XYZ", "price": 1.0, "volume": 100.0, "gas_fee": 1.0},
            {"timestamp": 2, "token_id": "XYZ", "price": 2.0, "volume": 220.0, "gas_fee": 1.5},
            {"timestamp": 3, "token_id": "XYZ", "price": 3.2, "volume": 340.0, "gas_fee": 1.8},
        ],
    )
    social_collector = StaticSampleCollector(
        "social",
        [
            {"timestamp": 1, "token_id": "XYZ", "sentiment": 0.6, "is_bot": 0.0, "reach": 1200},
            {"timestamp": 2, "token_id": "XYZ", "sentiment": 0.75, "is_bot": 0.0, "reach": 1500},
        ],
    )

    pipeline = RealtimePumpDetector(
        collectors=[market_collector, social_collector],
        detector=detector,
        probability_threshold=0.5,
    )

    detections = asyncio.run(pipeline.process_events())
    assert detections, "Expected at least one detection"
    assert detections[0].token_id == "XYZ"
    assert detections[0].prediction.probability >= 0.5
    assert detections[0].prediction.explanation
