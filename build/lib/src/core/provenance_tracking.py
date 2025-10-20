"""Provenance-aware wrappers for pipeline components.

This module provides wrapper functions that add provenance tracking
to existing feature extraction and scoring operations.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.core.features import (
    MarketSnapshot,
    compute_time_series_features,
    build_feature_vector,
)
from src.core.safety import (
    evaluate_contract,
    liquidity_guardrail,
    apply_penalties,
)
from src.core.scoring import compute_gem_score, should_flag_asset
from src.core.provenance import (
    ArtifactType,
    TransformationType,
    Transformation,
    get_provenance_tracker,
)


def track_market_snapshot(
    snapshot: MarketSnapshot,
    data_source: str = "manual",
    parent_ids: Optional[List[str]] = None,
) -> str:
    """Register a MarketSnapshot with provenance tracking.
    
    Parameters
    ----------
    snapshot : MarketSnapshot
        The market snapshot to track.
    data_source : str
        Source of the data (e.g., 'etherscan', 'dexscreener').
    parent_ids : Optional[List[str]]
        IDs of parent artifacts if this was derived.
        
    Returns
    -------
    str
        Artifact ID for the tracked snapshot.
    """
    tracker = get_provenance_tracker()
    
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.MARKET_SNAPSHOT,
        name=f"MarketSnapshot[{snapshot.symbol}]",
        data=snapshot,
        parent_ids=parent_ids,
        data_source=data_source,
        tags={"symbol", snapshot.symbol},
        custom_attributes={
            "symbol": snapshot.symbol,
            "timestamp": snapshot.timestamp.isoformat(),
            "price": snapshot.price,
            "liquidity_usd": snapshot.liquidity_usd,
        },
    )
    
    # Add quality metrics
    tracker.add_quality_metrics(
        artifact_id,
        {
            "holders": snapshot.holders,
            "volume_24h": snapshot.volume_24h,
            "liquidity_usd": snapshot.liquidity_usd,
        },
    )
    
    return artifact_id


def track_price_series(
    price_series: pd.Series,
    symbol: str,
    data_source: str = "manual",
    parent_ids: Optional[List[str]] = None,
) -> str:
    """Register a price series with provenance tracking.
    
    Parameters
    ----------
    price_series : pd.Series
        Time series of prices.
    symbol : str
        Token symbol.
    data_source : str
        Source of the data.
    parent_ids : Optional[List[str]]
        IDs of parent artifacts.
        
    Returns
    -------
    str
        Artifact ID for the tracked price series.
    """
    tracker = get_provenance_tracker()
    
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.PRICE_SERIES,
        name=f"PriceSeries[{symbol}]",
        data=price_series.to_dict(),
        parent_ids=parent_ids,
        data_source=data_source,
        tags={"symbol", symbol, "timeseries"},
        custom_attributes={
            "symbol": symbol,
            "start_date": price_series.index.min().isoformat() if not price_series.empty else None,
            "end_date": price_series.index.max().isoformat() if not price_series.empty else None,
            "data_points": len(price_series),
        },
    )
    
    # Add quality metrics
    if not price_series.empty:
        tracker.add_quality_metrics(
            artifact_id,
            {
                "data_points": len(price_series),
                "missing_values": price_series.isna().sum(),
                "mean_price": float(price_series.mean()),
                "std_price": float(price_series.std()),
            },
        )
    
    return artifact_id


def compute_time_series_features_tracked(
    price_series: pd.Series,
    symbol: str = "UNKNOWN",
    price_series_id: Optional[str] = None,
) -> tuple[Dict[str, float], str]:
    """Compute time series features with provenance tracking.
    
    Parameters
    ----------
    price_series : pd.Series
        Time series of prices.
    symbol : str
        Token symbol for naming.
    price_series_id : Optional[str]
        ID of the price series artifact if already tracked.
        
    Returns
    -------
    tuple[Dict[str, float], str]
        Computed features and artifact ID.
    """
    tracker = get_provenance_tracker()
    
    # Track the input if not already tracked
    if price_series_id is None:
        price_series_id = track_price_series(price_series, symbol)
    
    start_time = time.time()
    
    # Compute features
    features = compute_time_series_features(price_series)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Track the transformation
    transformation = Transformation(
        transformation_type=TransformationType.FEATURE_EXTRACTION,
        function_name="compute_time_series_features",
        parameters={"symbol": symbol},
        duration_ms=duration_ms,
    )
    
    # Register the feature artifact
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name=f"TimeSeriesFeatures[{symbol}]",
        data=features,
        parent_ids=[price_series_id],
        transformation=transformation,
        tags={"features", "timeseries", symbol},
        custom_attributes={
            "symbol": symbol,
            "feature_count": len(features),
        },
    )
    
    # Add quality metrics
    tracker.add_quality_metrics(
        artifact_id,
        {
            "rsi": features.get("rsi", 0.0),
            "macd": features.get("macd", 0.0),
            "volatility": features.get("volatility", 0.0),
        },
    )
    
    tracker.add_annotation(
        artifact_id,
        f"Computed RSI, MACD, and volatility from {len(price_series)} price points",
    )
    
    return features, artifact_id


def build_feature_vector_tracked(
    snapshot: MarketSnapshot,
    price_features: Dict[str, float],
    narrative_embedding_score: float,
    contract_safety: Dict[str, Any],
    narrative_momentum: float,
    snapshot_id: Optional[str] = None,
    price_features_id: Optional[str] = None,
) -> tuple[Dict[str, float], str]:
    """Build feature vector with provenance tracking.
    
    Parameters
    ----------
    snapshot : MarketSnapshot
        Market snapshot data.
    price_features : Dict[str, float]
        Computed price features.
    narrative_embedding_score : float
        Narrative alignment score.
    contract_safety : Dict[str, Any]
        Contract safety metrics.
    narrative_momentum : float
        Narrative momentum score.
    snapshot_id : Optional[str]
        ID of snapshot artifact if already tracked.
    price_features_id : Optional[str]
        ID of price features artifact if already tracked.
        
    Returns
    -------
    tuple[Dict[str, float], str]
        Feature vector and artifact ID.
    """
    tracker = get_provenance_tracker()
    
    # Track inputs if not already tracked
    parent_ids = []
    if snapshot_id:
        parent_ids.append(snapshot_id)
    if price_features_id:
        parent_ids.append(price_features_id)
    
    start_time = time.time()
    
    # Build feature vector
    features = build_feature_vector(
        snapshot,
        price_features,
        narrative_embedding_score,
        contract_safety,
        narrative_momentum=narrative_momentum,
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Track the transformation
    transformation = Transformation(
        transformation_type=TransformationType.AGGREGATION,
        function_name="build_feature_vector",
        parameters={
            "symbol": snapshot.symbol,
            "narrative_embedding_score": narrative_embedding_score,
        },
        duration_ms=duration_ms,
    )
    
    # Register the feature vector
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name=f"FeatureVector[{snapshot.symbol}]",
        data=features,
        parent_ids=parent_ids,
        transformation=transformation,
        tags={"features", "complete", snapshot.symbol},
        custom_attributes={
            "symbol": snapshot.symbol,
            "feature_count": len(features),
        },
    )
    
    # Add quality metrics
    tracker.add_quality_metrics(artifact_id, features)
    
    return features, artifact_id


def apply_penalties_tracked(
    base_vector: Dict[str, float],
    contract_report: Any,
    liquidity_ok: bool,
    symbol: str = "UNKNOWN",
    base_vector_id: Optional[str] = None,
) -> tuple[Dict[str, float], str]:
    """Apply penalties with provenance tracking.
    
    Parameters
    ----------
    base_vector : Dict[str, float]
        Base feature vector.
    contract_report : Any
        Contract safety report.
    liquidity_ok : bool
        Whether liquidity passes guardrail.
    symbol : str
        Token symbol.
    base_vector_id : Optional[str]
        ID of base vector artifact.
        
    Returns
    -------
    tuple[Dict[str, float], str]
        Penalized features and artifact ID.
    """
    tracker = get_provenance_tracker()
    
    parent_ids = [base_vector_id] if base_vector_id else []
    
    start_time = time.time()
    
    # Apply penalties
    features = apply_penalties(base_vector, contract_report, liquidity_ok=liquidity_ok)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Track the transformation
    transformation = Transformation(
        transformation_type=TransformationType.PENALTY_APPLICATION,
        function_name="apply_penalties",
        parameters={
            "symbol": symbol,
            "liquidity_ok": liquidity_ok,
            "contract_safety_score": getattr(contract_report, "score", 0.0),
        },
        duration_ms=duration_ms,
    )
    
    # Register the penalized features
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name=f"PenalizedFeatures[{symbol}]",
        data=features,
        parent_ids=parent_ids,
        transformation=transformation,
        tags={"features", "penalized", symbol},
        custom_attributes={
            "symbol": symbol,
            "liquidity_ok": liquidity_ok,
        },
    )
    
    tracker.add_annotation(
        artifact_id,
        f"Applied safety penalties based on contract report and liquidity guardrail",
    )
    
    return features, artifact_id


def compute_gem_score_tracked(
    features: Dict[str, float],
    symbol: str = "UNKNOWN",
    features_id: Optional[str] = None,
) -> tuple[Any, str]:
    """Compute GemScore with provenance tracking.
    
    Parameters
    ----------
    features : Dict[str, float]
        Feature vector.
    symbol : str
        Token symbol.
    features_id : Optional[str]
        ID of feature vector artifact.
        
    Returns
    -------
    tuple[GemScoreResult, str]
        GemScore result and artifact ID.
    """
    tracker = get_provenance_tracker()
    
    parent_ids = [features_id] if features_id else []
    
    start_time = time.time()
    
    # Compute score
    result = compute_gem_score(features)
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Track the transformation
    transformation = Transformation(
        transformation_type=TransformationType.SCORING,
        function_name="compute_gem_score",
        parameters={"symbol": symbol},
        duration_ms=duration_ms,
    )
    
    # Register the score
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.GEM_SCORE,
        name=f"GemScore[{symbol}]",
        data=result,
        parent_ids=parent_ids,
        transformation=transformation,
        tags={"score", symbol},
        custom_attributes={
            "symbol": symbol,
            "score": result.score,
            "confidence": result.confidence,
        },
    )
    
    # Add quality metrics
    tracker.add_quality_metrics(
        artifact_id,
        {
            "score": result.score,
            "confidence": result.confidence,
            **result.contributions,
        },
    )
    
    tracker.add_annotation(
        artifact_id,
        f"GemScore: {result.score:.2f} (confidence: {result.confidence:.2f})",
    )
    
    return result, artifact_id


def complete_pipeline_tracked(
    snapshot: MarketSnapshot,
    price_series: pd.Series,
    narrative_embedding_score: float,
    contract_report: Any,
    data_source: str = "manual",
) -> Dict[str, Any]:
    """Execute complete analysis pipeline with full provenance tracking.
    
    Parameters
    ----------
    snapshot : MarketSnapshot
        Market snapshot data.
    price_series : pd.Series
        Historical price data.
    narrative_embedding_score : float
        Narrative alignment score.
    contract_report : Any
        Contract safety report.
    data_source : str
        Data source identifier.
        
    Returns
    -------
    Dict[str, Any]
        Complete analysis results with provenance IDs.
    """
    # Track inputs
    snapshot_id = track_market_snapshot(snapshot, data_source)
    price_series_id = track_price_series(price_series, snapshot.symbol, data_source)
    
    # Compute features
    price_features, price_features_id = compute_time_series_features_tracked(
        price_series, snapshot.symbol, price_series_id
    )
    
    # Build feature vector
    contract_safety = {"score": contract_report.score}
    base_vector, base_vector_id = build_feature_vector_tracked(
        snapshot,
        price_features,
        narrative_embedding_score,
        contract_safety,
        narrative_momentum=narrative_embedding_score,  # Use narrative_embedding_score as momentum
        snapshot_id=snapshot_id,
        price_features_id=price_features_id,
    )
    
    # Apply penalties
    liquidity_ok = liquidity_guardrail(snapshot.liquidity_usd)
    features, features_id = apply_penalties_tracked(
        base_vector,
        contract_report,
        liquidity_ok,
        snapshot.symbol,
        base_vector_id,
    )
    
    # Compute score
    result, score_id = compute_gem_score_tracked(
        features,
        snapshot.symbol,
        features_id,
    )
    
    # Check flagging
    flagged, debug = should_flag_asset(result, features)
    
    # Get lineage
    tracker = get_provenance_tracker()
    lineage = tracker.get_lineage(score_id)
    
    return {
        "snapshot": snapshot,
        "price_features": price_features,
        "features": features,
        "result": result,
        "flagged": flagged,
        "debug": debug,
        "provenance": {
            "snapshot_id": snapshot_id,
            "price_series_id": price_series_id,
            "price_features_id": price_features_id,
            "base_vector_id": base_vector_id,
            "features_id": features_id,
            "score_id": score_id,
            "lineage": lineage,
        },
    }
