"""Feature engineering utilities for market, social and graph signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass
class FeatureVector:
    """Container for engineered features ready for modeling."""

    token_id: str
    values: Dict[str, float]


def _safe_pct_change(values: Sequence[float]) -> List[float]:
    changes: List[float] = []
    previous = None
    for value in values:
        if previous in (None, 0):
            changes.append(0.0)
        else:
            changes.append((value - previous) / previous)
        previous = value
    return changes


def build_market_features(events: Sequence[Dict[str, float]], *, token_id: str) -> FeatureVector:
    """Compute simple market features including momentum and volume anomalies."""

    if not events:
        return FeatureVector(token_id=token_id, values={"momentum": 0.0, "volume_anomaly": 0.0, "gas_spike": 0.0})

    ordered = sorted(events, key=lambda item: item.get("timestamp", 0))
    prices = [float(item.get("price", 0.0)) for item in ordered]
    volumes = [float(item.get("volume", 0.0)) for item in ordered]
    gas_fees = [float(item.get("gas_fee", 0.0)) for item in ordered]

    price_changes = _safe_pct_change(prices)
    price_momentum = sum(price_changes[-5:]) / max(len(price_changes[-5:]) or 1, 1)

    window = volumes[-10:]
    avg_volume = sum(window) / (len(window) or 1)
    latest_volume = volumes[-1] if volumes else 0.0
    volume_anomaly = (latest_volume - avg_volume) / (avg_volume or 1.0)

    gas_changes = _safe_pct_change(gas_fees)
    window_changes = gas_changes[-3:]
    gas_spike = sum(window_changes) / (len(window_changes) or 1)

    return FeatureVector(
        token_id=token_id,
        values={
            "momentum": float(price_momentum),
            "volume_anomaly": float(volume_anomaly),
            "gas_spike": float(gas_spike),
        },
    )


def build_social_features(posts: Sequence[Dict[str, float]], *, token_id: str) -> FeatureVector:
    """Derive simple sentiment metrics and bot amplification scores."""

    if not posts:
        return FeatureVector(token_id=token_id, values={"avg_sentiment": 0.0, "bot_ratio": 0.0, "hype": 0.0})

    sentiments = [float(post.get("sentiment", 0.0)) for post in posts]
    avg_sentiment = sum(sentiments) / len(sentiments)
    bot_flags = [float(post.get("is_bot", 0.0)) for post in posts]
    bot_ratio = sum(bot_flags) / len(bot_flags)
    reaches = [float(post.get("reach", 0.0)) for post in posts if "reach" in post]
    hype = (sum(reaches) / len(reaches)) if reaches else 0.0

    return FeatureVector(
        token_id=token_id,
        values={
            "avg_sentiment": float(avg_sentiment),
            "bot_ratio": bot_ratio,
            "hype": hype,
        },
    )


def combine_features(feature_vectors: Iterable[FeatureVector]) -> Dict[str, float]:
    """Merge feature vectors into a single feature dictionary."""

    merged: Dict[str, float] = {}
    for feature_vector in feature_vectors:
        merged.update(feature_vector.values)
    return merged


def derive_coordinated_hype_metric(mentions: Sequence[Tuple[str, str]]) -> float:
    """Compute a basic coordination score from influencer-token pairs."""

    if not mentions:
        return 0.0

    influencers: Dict[str, int] = {}
    for influencer, token in mentions:
        key = f"{influencer}:{token}"
        influencers[key] = influencers.get(key, 0) + 1

    repetitions = [count for count in influencers.values() if count > 1]
    if not repetitions:
        return 0.0
    return float(sum(repetitions) / len(repetitions) / len(mentions))
