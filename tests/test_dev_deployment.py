import asyncio

from src.crypto_pnd_detector.deployment import (
    build_dev_deployment,
    run_dev_deployment,
)


def _sample_market_events():
    return [
        {"timestamp": 1, "token_id": "XYZ", "price": 1.0, "volume": 120.0, "gas_fee": 1.0},
        {"timestamp": 2, "token_id": "XYZ", "price": 1.6, "volume": 210.0, "gas_fee": 1.4},
        {"timestamp": 3, "token_id": "XYZ", "price": 2.2, "volume": 330.0, "gas_fee": 1.8},
    ]


def _sample_social_events():
    return [
        {"timestamp": 1, "token_id": "XYZ", "sentiment": 0.65, "is_bot": 0.0, "reach": 1000},
        {"timestamp": 2, "token_id": "XYZ", "sentiment": 0.8, "is_bot": 0.0, "reach": 1500},
    ]


def test_build_dev_deployment_with_defaults_runs_pipeline():
    deployment = build_dev_deployment(
        market_events=_sample_market_events(),
        social_events=_sample_social_events(),
        probability_threshold=0.5,
    )

    result = asyncio.run(deployment.detect())

    assert result.detections, "Expected detection output from dev deployment"
    assert result.feature_records, "Feature store snapshot should be populated"
    detection = result.detections[0]
    assert detection.token_id == "XYZ"
    assert detection.prediction.probability >= 0.5
    assert detection.prediction.explanation


def test_run_dev_deployment_wrapper_executes_event_loop():
    deployment = build_dev_deployment(
        market_events=_sample_market_events(),
        social_events=_sample_social_events(),
        probability_threshold=0.5,
    )

    result = run_dev_deployment(deployment)

    assert result.detections
    assert any(record.token_id == "XYZ" for record in result.feature_records)
