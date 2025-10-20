"""Unified feature store for centralized feature management and serving."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.feature_validation import (
    validate_feature,
    validate_features_batch,
    ValidationError,
    get_validator,
)


class FeatureType(Enum):
    """Feature data types."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    VECTOR = "vector"


class FeatureCategory(Enum):
    """Feature categories for organization."""
    MARKET = "market"  # Price, volume, market cap
    LIQUIDITY = "liquidity"  # Order book depth, pool liquidity
    ORDERFLOW = "orderflow"  # CEX/DEX orderflow metrics
    DERIVATIVES = "derivatives"  # Funding rates, open interest
    SENTIMENT = "sentiment"  # Twitter, news sentiment
    ONCHAIN = "onchain"  # Holder counts, transaction activity
    TECHNICAL = "technical"  # Indicators, patterns
    QUALITY = "quality"  # Data quality scores
    SCORING = "scoring"  # GemScore, confidence scores


@dataclass
class FeatureMetadata:
    """Metadata for a feature."""

    name: str
    feature_type: FeatureType
    category: FeatureCategory
    description: str
    version: str = "1.0.0"
    source: str = "unknown"  # Data source (e.g., "binance", "twitter")
    unit: Optional[str] = None  # Unit of measurement (e.g., "USD", "BTC", "%")
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    nullable: bool = True
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        data = asdict(self)
        data["feature_type"] = self.feature_type.value
        data["category"] = self.category.value
        return data


@dataclass
class FeatureValue:
    """A feature value with timestamp and metadata."""

    feature_name: str
    value: Any
    timestamp: float
    token_symbol: str
    version: str = "1.0.0"
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return asdict(self)

    def is_stale(self, max_age_seconds: float) -> bool:
        """Check if feature value is stale.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            True if stale
        """
        age = time.time() - self.timestamp
        return age > max_age_seconds


@dataclass
class FeatureVector:
    """A collection of feature values for a single entity at a point in time."""

    token_symbol: str
    timestamp: float
    features: Dict[str, Any]
    version: str = "1.0.0"
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return asdict(self)

    def get_feature(self, feature_name: str, default: Any = None) -> Any:
        """Get a feature value.

        Args:
            feature_name: Feature name
            default: Default value if not found

        Returns:
            Feature value or default
        """
        return self.features.get(feature_name, default)

    def set_feature(
        self,
        feature_name: str,
        value: Any,
        confidence: float = 1.0,
    ) -> None:
        """Set a feature value.

        Args:
            feature_name: Feature name
            value: Feature value
            confidence: Confidence score
        """
        self.features[feature_name] = value
        self.confidence_scores[feature_name] = confidence


class FeatureStore:
    """Unified feature store with versioning and time-series support."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        enable_validation: bool = True,
    ) -> None:
        """Initialize feature store.

        Args:
            storage_path: Path to store features (None for in-memory only)
            enable_validation: Enable feature validation on writes
        """
        self.storage_path = storage_path
        self.enable_validation = enable_validation
        self._schema: Dict[str, FeatureMetadata] = {}
        self._features: Dict[str, List[FeatureValue]] = {}  # feature_name -> [values]
        self._vectors: Dict[str, List[FeatureVector]] = {}  # token_symbol -> [vectors]
        self._snapshots: Dict[str, List[Any]] = {}  # token_symbol -> [GemScoreSnapshots]
        
        # Validation statistics
        self._validation_stats = {
            "total_validations": 0,
            "validation_failures": 0,
            "validation_warnings": 0,
        }

        if storage_path and storage_path.exists():
            self._load_schema()

    # ============================================================================
    # Schema Management
    # ============================================================================

    def register_feature(self, metadata: FeatureMetadata) -> None:
        """Register a feature in the schema.

        Args:
            metadata: Feature metadata
        """
        metadata.updated_at = time.time()
        self._schema[metadata.name] = metadata

        if self.storage_path:
            self._save_schema()

    def get_feature_metadata(self, feature_name: str) -> Optional[FeatureMetadata]:
        """Get feature metadata.

        Args:
            feature_name: Feature name

        Returns:
            Feature metadata or None
        """
        return self._schema.get(feature_name)

    def list_features(
        self,
        category: Optional[FeatureCategory] = None,
        tags: Optional[List[str]] = None,
    ) -> List[FeatureMetadata]:
        """List registered features.

        Args:
            category: Filter by category
            tags: Filter by tags

        Returns:
            List of feature metadata
        """
        features = list(self._schema.values())

        if category:
            features = [f for f in features if f.category == category]

        if tags:
            features = [f for f in features if any(t in f.tags for t in tags)]

        return features

    # ============================================================================
    # Feature Value Storage
    # ============================================================================

    def write_feature(
        self,
        feature_name: str,
        value: Any,
        token_symbol: str,
        timestamp: Optional[float] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        skip_validation: bool = False,
    ) -> FeatureValue:
        """Write a feature value.

        Args:
            feature_name: Feature name
            value: Feature value
            token_symbol: Token symbol
            timestamp: Timestamp (uses current time if not provided)
            confidence: Confidence score
            metadata: Additional metadata
            skip_validation: Skip validation checks (use with caution)

        Returns:
            Created feature value
        
        Raises:
            ValidationError: If validation fails
        """
        if feature_name not in self._schema:
            raise ValueError(f"Feature '{feature_name}' not registered in schema")

        if timestamp is None:
            timestamp = time.time()

        # Perform validation if enabled
        if self.enable_validation and not skip_validation:
            # Get historical values for monotonic validation
            history = None
            if feature_name in self._features:
                existing_values = [
                    (v.timestamp, v.value)
                    for v in self._features[feature_name]
                    if v.token_symbol == token_symbol
                ]
                if existing_values:
                    history = existing_values
            
            # Validate
            self._validation_stats["total_validations"] += 1
            result = validate_feature(
                feature_name=feature_name,
                value=value,
                timestamp=timestamp,
                history=history,
            )
            
            if not result.is_valid:
                self._validation_stats["validation_failures"] += 1
                raise ValidationError([result.error_message or "Validation failed"])
            
            if result.warnings:
                self._validation_stats["validation_warnings"] += len(result.warnings)
                # Log warnings but don't block write
                # In production, you might want to send these to a logging system

        feature_metadata = self._schema[feature_name]

        feature_value = FeatureValue(
            feature_name=feature_name,
            value=value,
            timestamp=timestamp,
            token_symbol=token_symbol,
            version=feature_metadata.version,
            confidence=confidence,
            metadata=metadata or {},
        )

        if feature_name not in self._features:
            self._features[feature_name] = []

        self._features[feature_name].append(feature_value)

        return feature_value

    def read_feature(
        self,
        feature_name: str,
        token_symbol: str,
        timestamp: Optional[float] = None,
        max_age_seconds: Optional[float] = None,
    ) -> Optional[FeatureValue]:
        """Read the latest feature value.

        Args:
            feature_name: Feature name
            token_symbol: Token symbol
            timestamp: Point-in-time timestamp (uses latest if not provided)
            max_age_seconds: Maximum age for staleness check

        Returns:
            Feature value or None
        """
        values = self._features.get(feature_name, [])

        # Filter by token
        values = [v for v in values if v.token_symbol == token_symbol]

        if not values:
            return None

        # Filter by timestamp
        if timestamp:
            values = [v for v in values if v.timestamp <= timestamp]

        if not values:
            return None

        # Get latest
        latest = max(values, key=lambda v: v.timestamp)

        # Check staleness
        if max_age_seconds and latest.is_stale(max_age_seconds):
            return None

        return latest

    def read_feature_history(
        self,
        feature_name: str,
        token_symbol: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[FeatureValue]:
        """Read feature value history.

        Args:
            feature_name: Feature name
            token_symbol: Token symbol
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of values to return

        Returns:
            List of feature values (sorted by timestamp descending)
        """
        values = self._features.get(feature_name, [])

        # Filter by token
        values = [v for v in values if v.token_symbol == token_symbol]

        # Filter by time range
        if start_time:
            values = [v for v in values if v.timestamp >= start_time]
        if end_time:
            values = [v for v in values if v.timestamp <= end_time]

        # Sort by timestamp descending
        values = sorted(values, key=lambda v: v.timestamp, reverse=True)

        # Limit results
        if limit:
            values = values[:limit]

        return values

    # ============================================================================
    # Feature Vector Storage
    # ============================================================================

    def write_vector(self, vector: FeatureVector) -> None:
        """Write a feature vector.

        Args:
            vector: Feature vector to write
        """
        if vector.token_symbol not in self._vectors:
            self._vectors[vector.token_symbol] = []

        self._vectors[vector.token_symbol].append(vector)

    def read_vector(
        self,
        token_symbol: str,
        timestamp: Optional[float] = None,
    ) -> Optional[FeatureVector]:
        """Read the latest feature vector.

        Args:
            token_symbol: Token symbol
            timestamp: Point-in-time timestamp (uses latest if not provided)

        Returns:
            Feature vector or None
        """
        vectors = self._vectors.get(token_symbol, [])

        if not vectors:
            return None

        # Filter by timestamp
        if timestamp:
            vectors = [v for v in vectors if v.timestamp <= timestamp]

        if not vectors:
            return None

        # Get latest
        return max(vectors, key=lambda v: v.timestamp)

    def read_vector_history(
        self,
        token_symbol: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[FeatureVector]:
        """Read feature vector history.

        Args:
            token_symbol: Token symbol
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of vectors to return

        Returns:
            List of feature vectors (sorted by timestamp descending)
        """
        vectors = self._vectors.get(token_symbol, [])

        # Filter by time range
        if start_time:
            vectors = [v for v in vectors if v.timestamp >= start_time]
        if end_time:
            vectors = [v for v in vectors if v.timestamp <= end_time]

        # Sort by timestamp descending
        vectors = sorted(vectors, key=lambda v: v.timestamp, reverse=True)

        # Limit results
        if limit:
            vectors = vectors[:limit]

        return vectors

    # ============================================================================
    # Batch Operations
    # ============================================================================

    def write_features_batch(
        self,
        features: List[tuple[str, Any, str]],  # (feature_name, value, token_symbol)
        timestamp: Optional[float] = None,
        confidence: float = 1.0,
        skip_validation: bool = False,
    ) -> List[FeatureValue]:
        """Write multiple features at once.

        Args:
            features: List of (feature_name, value, token_symbol) tuples
            timestamp: Timestamp (uses current time if not provided)
            confidence: Confidence score for all features
            skip_validation: Skip validation checks (use with caution)

        Returns:
            List of created feature values
        
        Raises:
            ValidationError: If validation fails for any feature
        """
        if timestamp is None:
            timestamp = time.time()

        # Perform batch validation if enabled
        if self.enable_validation and not skip_validation:
            # Build features dict and histories for validation
            features_dict = {}
            histories = {}
            
            for feature_name, value, token_symbol in features:
                # Use first occurrence for validation
                if feature_name not in features_dict:
                    features_dict[feature_name] = value
                    
                    # Get history for this feature
                    if feature_name in self._features:
                        existing_values = [
                            (v.timestamp, v.value)
                            for v in self._features[feature_name]
                            if v.token_symbol == token_symbol
                        ]
                        if existing_values:
                            histories[feature_name] = existing_values
            
            # Validate all features
            self._validation_stats["total_validations"] += len(features_dict)
            is_valid, errors, warnings = validate_features_batch(
                features=features_dict,
                timestamp=timestamp,
                histories=histories,
                raise_on_error=True,  # Will raise ValidationError if any fail
            )
            
            if warnings:
                self._validation_stats["validation_warnings"] += len(warnings)

        # Write all features
        feature_values = []
        for feature_name, value, token_symbol in features:
            fv = self.write_feature(
                feature_name=feature_name,
                value=value,
                token_symbol=token_symbol,
                timestamp=timestamp,
                confidence=confidence,
                skip_validation=True,  # Already validated above
            )
            feature_values.append(fv)

        return feature_values

    def read_features_batch(
        self,
        feature_names: List[str],
        token_symbol: str,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Optional[FeatureValue]]:
        """Read multiple features at once.

        Args:
            feature_names: List of feature names
            token_symbol: Token symbol
            timestamp: Point-in-time timestamp

        Returns:
            Dictionary of feature_name -> feature_value
        """
        return {
            name: self.read_feature(name, token_symbol, timestamp)
            for name in feature_names
        }

    # ============================================================================
    # Persistence
    # ============================================================================

    def _save_schema(self) -> None:
        """Save schema to disk."""
        if not self.storage_path:
            return

        self.storage_path.mkdir(parents=True, exist_ok=True)
        schema_path = self.storage_path / "schema.json"

        schema_data = {
            name: metadata.to_dict()
            for name, metadata in self._schema.items()
        }

        with open(schema_path, "w") as f:
            json.dump(schema_data, f, indent=2)

    def _load_schema(self) -> None:
        """Load schema from disk."""
        if not self.storage_path:
            return

        schema_path = self.storage_path / "schema.json"

        if not schema_path.exists():
            return

        with open(schema_path, "r") as f:
            schema_data = json.load(f)

        for name, data in schema_data.items():
            metadata = FeatureMetadata(
                name=data["name"],
                feature_type=FeatureType(data["feature_type"]),
                category=FeatureCategory(data["category"]),
                description=data["description"],
                version=data.get("version", "1.0.0"),
                source=data.get("source", "unknown"),
                unit=data.get("unit"),
                min_value=data.get("min_value"),
                max_value=data.get("max_value"),
                nullable=data.get("nullable", True),
                tags=data.get("tags", []),
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
            )
            self._schema[name] = metadata

    def clear_old_data(self, max_age_seconds: float) -> int:
        """Clear old feature data.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of values cleared
        """
        cutoff_time = time.time() - max_age_seconds
        cleared_count = 0

        # Clear old feature values
        for feature_name in list(self._features.keys()):
            values = self._features[feature_name]
            new_values = [v for v in values if v.timestamp > cutoff_time]
            cleared_count += len(values) - len(new_values)
            self._features[feature_name] = new_values

        # Clear old vectors
        for token_symbol in list(self._vectors.keys()):
            vectors = self._vectors[token_symbol]
            new_vectors = [v for v in vectors if v.timestamp > cutoff_time]
            cleared_count += len(vectors) - len(new_vectors)
            self._vectors[token_symbol] = new_vectors
        
        # Clear old snapshots
        for token_symbol in list(self._snapshots.keys()):
            snapshots = self._snapshots[token_symbol]
            new_snapshots = [s for s in snapshots if s.timestamp > cutoff_time]
            cleared_count += len(snapshots) - len(new_snapshots)
            self._snapshots[token_symbol] = new_snapshots

        return cleared_count

    def get_stats(self) -> Dict[str, Any]:
        """Get feature store statistics.

        Returns:
            Dictionary with stats
        """
        total_features = sum(len(values) for values in self._features.values())
        total_vectors = sum(len(vectors) for vectors in self._vectors.values())
        total_snapshots = sum(len(snapshots) for snapshots in self._snapshots.values())

        return {
            "schema_size": len(self._schema),
            "total_feature_values": total_features,
            "total_vectors": total_vectors,
            "total_snapshots": total_snapshots,
            "tokens_tracked": len(self._vectors),
            "features_by_category": {
                cat.value: len([f for f in self._schema.values() if f.category == cat])
                for cat in FeatureCategory
            },
            "validation_stats": self._validation_stats.copy(),
        }
    
    # ============================================================================
    # GemScore Snapshot Storage
    # ============================================================================
    
    def write_snapshot(self, snapshot: Any) -> None:
        """Write a GemScore snapshot.
        
        Args:
            snapshot: GemScoreSnapshot to write
        """
        token_symbol = snapshot.token_symbol
        
        if token_symbol not in self._snapshots:
            self._snapshots[token_symbol] = []
        
        self._snapshots[token_symbol].append(snapshot)
    
    def read_snapshot(
        self,
        token_symbol: str,
        timestamp: Optional[float] = None,
    ) -> Optional[Any]:
        """Read the latest GemScore snapshot.
        
        Args:
            token_symbol: Token symbol
            timestamp: Point-in-time timestamp (uses latest if not provided)
        
        Returns:
            GemScore snapshot or None
        """
        snapshots = self._snapshots.get(token_symbol, [])
        
        if not snapshots:
            return None
        
        # Filter by timestamp
        if timestamp:
            snapshots = [s for s in snapshots if s.timestamp <= timestamp]
        
        if not snapshots:
            return None
        
        # Get latest
        return max(snapshots, key=lambda s: s.timestamp)
    
    def read_snapshot_history(
        self,
        token_symbol: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Any]:
        """Read GemScore snapshot history.
        
        Args:
            token_symbol: Token symbol
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum number of snapshots to return
        
        Returns:
            List of snapshots (sorted by timestamp descending)
        """
        snapshots = self._snapshots.get(token_symbol, [])
        
        # Filter by time range
        if start_time:
            snapshots = [s for s in snapshots if s.timestamp >= start_time]
        if end_time:
            snapshots = [s for s in snapshots if s.timestamp <= end_time]
        
        # Sort by timestamp descending
        snapshots = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
        
        # Limit results
        if limit:
            snapshots = snapshots[:limit]
        
        return snapshots
    
    def compute_score_delta(
        self,
        token_symbol: str,
        current_snapshot: Optional[Any] = None,
    ) -> Optional[Any]:
        """Compute delta between current and previous snapshot.
        
        Args:
            token_symbol: Token symbol
            current_snapshot: Current snapshot (uses latest if not provided)
        
        Returns:
            ScoreDelta or None if insufficient history
        """
        from src.core.score_explainer import ScoreExplainer
        
        if current_snapshot is None:
            current_snapshot = self.read_snapshot(token_symbol)
        
        if current_snapshot is None:
            return None
        
        # Get previous snapshot (before current)
        history = self.read_snapshot_history(
            token_symbol=token_symbol,
            end_time=current_snapshot.timestamp - 0.001,  # Slightly before current
            limit=1,
        )
        
        if not history:
            return None
        
        previous_snapshot = history[0]
        
        # Compute delta
        explainer = ScoreExplainer()
        return explainer.compute_delta(previous_snapshot, current_snapshot)
    
    def get_validation_stats(self) -> Dict[str, int]:
        """Get validation statistics.
        
        Returns:
            Dictionary with validation stats
        """
        return self._validation_stats.copy()
