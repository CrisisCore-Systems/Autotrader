"""Feature engineering pipelines for transforming raw data into features."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.core.feature_store import (
    FeatureStore,
    FeatureMetadata,
    FeatureType,
    FeatureCategory,
    FeatureVector,
)


@dataclass
class FeatureTransform:
    """A feature transformation definition."""

    name: str
    input_features: List[str]
    output_feature: str
    transform_func: Callable[[Dict[str, Any]], Any]
    description: str
    version: str = "1.0.0"


class FeatureEngineeringPipeline:
    """Pipeline for feature engineering and transformation."""

    def __init__(self, feature_store: FeatureStore) -> None:
        """Initialize pipeline.

        Args:
            feature_store: Feature store instance
        """
        self.feature_store = feature_store
        self._transforms: Dict[str, FeatureTransform] = {}

    def register_transform(self, transform: FeatureTransform) -> None:
        """Register a feature transformation.

        Args:
            transform: Feature transform to register
        """
        self._transforms[transform.name] = transform

    def apply_transform(
        self,
        transform_name: str,
        token_symbol: str,
        timestamp: Optional[float] = None,
    ) -> Optional[Any]:
        """Apply a transformation and store the result.

        Args:
            transform_name: Name of transform to apply
            token_symbol: Token symbol
            timestamp: Timestamp to use for feature lookup

        Returns:
            Transformed value or None if inputs missing
        """
        transform = self._transforms.get(transform_name)
        if not transform:
            raise ValueError(f"Transform '{transform_name}' not registered")

        # Read input features
        input_values = {}
        for feature_name in transform.input_features:
            feature_value = self.feature_store.read_feature(
                feature_name=feature_name,
                token_symbol=token_symbol,
                timestamp=timestamp,
            )

            if feature_value is None:
                return None

            input_values[feature_name] = feature_value.value

        # Apply transformation
        try:
            output_value = transform.transform_func(input_values)
        except Exception as exc:
            print(f"Transform '{transform_name}' failed: {exc}")
            return None

        # Store output feature
        if timestamp is None:
            timestamp = time.time()

        self.feature_store.write_feature(
            feature_name=transform.output_feature,
            value=output_value,
            token_symbol=token_symbol,
            timestamp=timestamp,
            confidence=1.0,
            metadata={"transform": transform_name, "version": transform.version},
        )

        return output_value

    def apply_pipeline(
        self,
        transform_names: List[str],
        token_symbol: str,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Apply multiple transformations in sequence.

        Args:
            transform_names: List of transform names
            token_symbol: Token symbol
            timestamp: Timestamp for feature lookup

        Returns:
            Dictionary of transform_name -> output_value
        """
        results = {}

        for transform_name in transform_names:
            result = self.apply_transform(transform_name, token_symbol, timestamp)
            results[transform_name] = result

        return results


# ============================================================================
# Pre-defined Feature Transforms
# ============================================================================

def register_standard_transforms(pipeline: FeatureEngineeringPipeline) -> None:
    """Register standard feature transformations.

    Args:
        pipeline: Feature engineering pipeline
    """
    fs = pipeline.feature_store

    # Register all output features in schema first
    _register_derived_features(fs)

    # Market transforms
    pipeline.register_transform(FeatureTransform(
        name="market_cap_to_volume_ratio",
        input_features=["market_cap_usd", "volume_24h_usd"],
        output_feature="market_cap_to_volume_ratio",
        transform_func=lambda inputs: inputs["market_cap_usd"] / inputs["volume_24h_usd"]
        if inputs["volume_24h_usd"] > 0 else 0.0,
        description="Market cap divided by 24h volume",
    ))

    pipeline.register_transform(FeatureTransform(
        name="price_momentum_1h",
        input_features=["price_usd", "price_usd_1h_ago"],
        output_feature="price_momentum_1h",
        transform_func=lambda inputs: (inputs["price_usd"] - inputs["price_usd_1h_ago"])
        / inputs["price_usd_1h_ago"] if inputs["price_usd_1h_ago"] > 0 else 0.0,
        description="1-hour price momentum (percentage change)",
    ))

    # Liquidity transforms
    pipeline.register_transform(FeatureTransform(
        name="bid_ask_spread",
        input_features=["best_bid_price", "best_ask_price"],
        output_feature="bid_ask_spread",
        transform_func=lambda inputs: (inputs["best_ask_price"] - inputs["best_bid_price"])
        / inputs["best_bid_price"] if inputs["best_bid_price"] > 0 else 0.0,
        description="Bid-ask spread as percentage of bid",
    ))

    pipeline.register_transform(FeatureTransform(
        name="orderbook_imbalance",
        input_features=["total_bid_volume", "total_ask_volume"],
        output_feature="orderbook_imbalance",
        transform_func=lambda inputs: (inputs["total_bid_volume"] - inputs["total_ask_volume"])
        / (inputs["total_bid_volume"] + inputs["total_ask_volume"])
        if (inputs["total_bid_volume"] + inputs["total_ask_volume"]) > 0 else 0.0,
        description="Order book imbalance (-1 to 1, positive = more bids)",
    ))

    # Sentiment transforms
    pipeline.register_transform(FeatureTransform(
        name="sentiment_momentum",
        input_features=["sentiment_score", "sentiment_score_1h_ago"],
        output_feature="sentiment_momentum",
        transform_func=lambda inputs: inputs["sentiment_score"] - inputs["sentiment_score_1h_ago"],
        description="Change in sentiment over 1 hour",
    ))

    pipeline.register_transform(FeatureTransform(
        name="engagement_to_followers_ratio",
        input_features=["total_engagement", "total_followers"],
        output_feature="engagement_to_followers_ratio",
        transform_func=lambda inputs: inputs["total_engagement"] / inputs["total_followers"]
        if inputs["total_followers"] > 0 else 0.0,
        description="Social engagement per follower",
    ))

    # Derivatives transforms
    pipeline.register_transform(FeatureTransform(
        name="funding_rate_momentum",
        input_features=["funding_rate", "funding_rate_1h_ago"],
        output_feature="funding_rate_momentum",
        transform_func=lambda inputs: inputs["funding_rate"] - inputs["funding_rate_1h_ago"],
        description="Change in funding rate over 1 hour",
    ))

    pipeline.register_transform(FeatureTransform(
        name="oi_to_volume_ratio",
        input_features=["open_interest_usd", "volume_24h_usd"],
        output_feature="oi_to_volume_ratio",
        transform_func=lambda inputs: inputs["open_interest_usd"] / inputs["volume_24h_usd"]
        if inputs["volume_24h_usd"] > 0 else 0.0,
        description="Open interest to 24h volume ratio",
    ))

    # Composite scoring transforms
    pipeline.register_transform(FeatureTransform(
        name="liquidity_score",
        input_features=["volume_24h_usd", "total_bid_volume", "total_ask_volume"],
        output_feature="liquidity_score",
        transform_func=lambda inputs: min(100.0, (
            (inputs["volume_24h_usd"] / 1_000_000) * 50 +  # Volume component
            (inputs["total_bid_volume"] / 100_000) * 25 +  # Bid depth
            (inputs["total_ask_volume"] / 100_000) * 25    # Ask depth
        )),
        description="Composite liquidity score (0-100)",
    ))

    pipeline.register_transform(FeatureTransform(
        name="momentum_score",
        input_features=["price_momentum_1h", "volume_24h_usd"],
        output_feature="momentum_score",
        transform_func=lambda inputs: min(100.0, max(0.0,
            50 + (inputs["price_momentum_1h"] * 100) +  # Price momentum
            (inputs["volume_24h_usd"] / 10_000_000) * 10  # Volume boost
        )),
        description="Composite momentum score (0-100)",
    ))


def _register_derived_features(fs: FeatureStore) -> None:
    """Register derived feature metadata in schema.

    Args:
        fs: Feature store
    """
    # Market derived features
    fs.register_feature(FeatureMetadata(
        name="market_cap_to_volume_ratio",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Market cap divided by 24h volume",
        source="derived",
        unit="ratio",
        tags=["derived", "market", "liquidity"],
    ))

    fs.register_feature(FeatureMetadata(
        name="price_momentum_1h",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="1-hour price momentum (percentage change)",
        source="derived",
        unit="%",
        tags=["derived", "momentum", "technical"],
    ))

    # Liquidity derived features
    fs.register_feature(FeatureMetadata(
        name="bid_ask_spread",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.LIQUIDITY,
        description="Bid-ask spread as percentage",
        source="derived",
        unit="%",
        min_value=0.0,
        tags=["derived", "liquidity", "orderflow"],
    ))

    fs.register_feature(FeatureMetadata(
        name="orderbook_imbalance",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Order book imbalance (-1 to 1)",
        source="derived",
        unit="ratio",
        min_value=-1.0,
        max_value=1.0,
        tags=["derived", "orderflow", "liquidity"],
    ))

    # Sentiment derived features
    fs.register_feature(FeatureMetadata(
        name="sentiment_momentum",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SENTIMENT,
        description="Change in sentiment over 1 hour",
        source="derived",
        unit="delta",
        tags=["derived", "sentiment", "momentum"],
    ))

    fs.register_feature(FeatureMetadata(
        name="engagement_to_followers_ratio",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SENTIMENT,
        description="Social engagement per follower",
        source="derived",
        unit="ratio",
        tags=["derived", "sentiment", "social"],
    ))

    # Derivatives derived features
    fs.register_feature(FeatureMetadata(
        name="funding_rate_momentum",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.DERIVATIVES,
        description="Change in funding rate over 1 hour",
        source="derived",
        unit="%",
        tags=["derived", "derivatives", "momentum"],
    ))

    fs.register_feature(FeatureMetadata(
        name="oi_to_volume_ratio",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.DERIVATIVES,
        description="Open interest to 24h volume ratio",
        source="derived",
        unit="ratio",
        tags=["derived", "derivatives", "leverage"],
    ))

    # Composite scores
    fs.register_feature(FeatureMetadata(
        name="liquidity_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SCORING,
        description="Composite liquidity score (0-100)",
        source="derived",
        unit="score",
        min_value=0.0,
        max_value=100.0,
        tags=["derived", "score", "liquidity"],
    ))

    fs.register_feature(FeatureMetadata(
        name="momentum_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SCORING,
        description="Composite momentum score (0-100)",
        source="derived",
        unit="score",
        min_value=0.0,
        max_value=100.0,
        tags=["derived", "score", "momentum"],
    ))


# ============================================================================
# Feature Vector Builder
# ============================================================================

def build_feature_vector(
    token_symbol: str,
    feature_store: FeatureStore,
    feature_names: List[str],
    timestamp: Optional[float] = None,
) -> Optional[FeatureVector]:
    """Build a feature vector from individual features.

    Args:
        token_symbol: Token symbol
        feature_store: Feature store instance
        feature_names: List of features to include
        timestamp: Point-in-time timestamp

    Returns:
        Feature vector or None if any required features missing
    """
    if timestamp is None:
        timestamp = time.time()

    features = {}
    confidence_scores = {}

    for feature_name in feature_names:
        feature_value = feature_store.read_feature(
            feature_name=feature_name,
            token_symbol=token_symbol,
            timestamp=timestamp,
        )

        if feature_value is None:
            # Missing required feature
            return None

        features[feature_name] = feature_value.value
        confidence_scores[feature_name] = feature_value.confidence

    return FeatureVector(
        token_symbol=token_symbol,
        timestamp=timestamp,
        features=features,
        confidence_scores=confidence_scores,
    )


def build_ml_ready_vector(
    token_symbol: str,
    feature_store: FeatureStore,
    timestamp: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Build an ML-ready feature vector with all standard features.

    Args:
        token_symbol: Token symbol
        feature_store: Feature store instance
        timestamp: Point-in-time timestamp

    Returns:
        Dictionary with ML-ready features or None if data incomplete
    """
    # Standard feature set for ML models
    ml_features = [
        # Market features
        "price_usd",
        "market_cap_usd",
        "volume_24h_usd",
        "price_momentum_1h",
        "market_cap_to_volume_ratio",

        # Liquidity features
        "best_bid_price",
        "best_ask_price",
        "total_bid_volume",
        "total_ask_volume",
        "bid_ask_spread",
        "orderbook_imbalance",

        # Sentiment features
        "sentiment_score",
        "sentiment_momentum",
        "tweet_volume",

        # Derivatives features (optional)
        "funding_rate",
        "open_interest_usd",

        # Composite scores
        "liquidity_score",
        "momentum_score",
    ]

    vector = build_feature_vector(
        token_symbol=token_symbol,
        feature_store=feature_store,
        feature_names=ml_features,
        timestamp=timestamp,
    )

    if vector is None:
        return None

    return {
        "token_symbol": vector.token_symbol,
        "timestamp": vector.timestamp,
        "features": vector.features,
        "confidence_scores": vector.confidence_scores,
    }


class FeatureTransformRegistry:
    """Registry for feature transformation functions."""

    def __init__(self) -> None:
        """Initialize the transform registry."""
        self._transforms: Dict[str, Callable] = {}
        self._register_standard_transforms()

    def _register_standard_transforms(self) -> None:
        """Register standard transformation functions."""
        import math

        # Log transform
        self._transforms["log"] = lambda x: math.log(x) if x > 0 else 0.0

        # Normalization (min-max scaling)
        self._transforms["normalize"] = lambda values: [
            (v - min(values)) / (max(values) - min(values)) if max(values) != min(values) else 0.5
            for v in values
        ]

        # Square root transform
        self._transforms["sqrt"] = lambda x: math.sqrt(x) if x >= 0 else 0.0

        # Exponential transform
        self._transforms["exp"] = lambda x: math.exp(x)

    def register_transform(self, name: str, transform_func: Callable) -> None:
        """Register a custom transform function.

        Args:
            name: Transform name
            transform_func: Function to apply
        """
        self._transforms[name] = transform_func

    def list_transforms(self) -> List[str]:
        """List all available transforms.

        Returns:
            List of transform names
        """
        return list(self._transforms.keys())

    def log_transform(self, value: float) -> float:
        """Apply logarithmic transform.

        Args:
            value: Input value

        Returns:
            Log-transformed value
        """
        return self._transforms["log"](value)

    def normalize(self, values: List[float]) -> List[float]:
        """Apply min-max normalization.

        Args:
            values: List of values to normalize

        Returns:
            Normalized values
        """
        return self._transforms["normalize"](values)

    def apply_transform(self, name: str, *args, **kwargs) -> Any:
        """Apply a registered transform.

        Args:
            name: Transform name
            *args: Arguments for transform
            **kwargs: Keyword arguments

        Returns:
            Transform result
        """
        if name not in self._transforms:
            raise ValueError(f"Transform '{name}' not registered")

        return self._transforms[name](*args, **kwargs)
