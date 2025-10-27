"""
Feature metadata tracking and management.

Provides metadata about features:
- Feature groups (technical, rolling, temporal, volume)
- Data requirements (minimum bars needed)
- Computation cost (relative speed)
- Feature importance (if model trained)

This enables:
- Smart feature selection based on data availability
- Cost-aware feature extraction
- Feature importance tracking
- Reproducibility (track what features were used)
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
import pandas as pd


@dataclass
class FeatureMetadata:
    """
    Metadata for a single feature.
    
    Attributes:
        name: Feature name
        group: Feature category (technical, rolling, temporal, volume, orderbook)
        min_bars: Minimum bars required to compute (e.g., RSI needs 14 bars)
        cost: Relative computation cost (1=cheap, 10=expensive)
        description: Human-readable description
        importance: Feature importance from model (optional)
    """
    name: str
    group: Literal["technical", "rolling", "temporal", "volume", "orderbook", "transformed"]
    min_bars: int
    cost: int = 1  # 1-10 scale
    description: str = ""
    importance: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "group": self.group,
            "min_bars": self.min_bars,
            "cost": self.cost,
            "description": self.description,
            "importance": self.importance
        }


class FeatureMetadataRegistry:
    """
    Central registry for feature metadata.
    
    Tracks all features and their properties. Enables:
    - Validation (do we have enough data?)
    - Cost analysis (what's expensive to compute?)
    - Feature selection (pick most important features)
    - Documentation (what does each feature mean?)
    
    Example:
        registry = FeatureMetadataRegistry()
        
        # Register features
        registry.register(FeatureMetadata(
            name="rsi_14",
            group="technical",
            min_bars=14,
            cost=2,
            description="Relative Strength Index (14 periods)"
        ))
        
        # Validate data requirements
        if registry.can_compute(bars_available=100):
            features = extract_features()
        
        # Get most important features
        top_features = registry.get_top_features(n=10)
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._metadata: dict[str, FeatureMetadata] = {}
    
    def register(self, metadata: FeatureMetadata):
        """
        Register feature metadata.
        
        Args:
            metadata: Feature metadata to register
        """
        self._metadata[metadata.name] = metadata
    
    def register_batch(self, metadata_list: list[FeatureMetadata]):
        """
        Register multiple features at once.
        
        Args:
            metadata_list: List of feature metadata
        """
        for metadata in metadata_list:
            self.register(metadata)
    
    def get(self, feature_name: str) -> Optional[FeatureMetadata]:
        """
        Get metadata for a feature.
        
        Args:
            feature_name: Name of feature
        
        Returns:
            Feature metadata or None if not registered
        """
        return self._metadata.get(feature_name)
    
    def get_by_group(self, group: str) -> list[FeatureMetadata]:
        """
        Get all features in a group.
        
        Args:
            group: Feature group name
        
        Returns:
            List of feature metadata in that group
        """
        return [m for m in self._metadata.values() if m.group == group]
    
    def get_min_bars_required(self, feature_names: list[str] = None) -> int:
        """
        Get minimum bars required to compute features.
        
        Args:
            feature_names: Specific features (None = all registered)
        
        Returns:
            Maximum min_bars across all features
        """
        if feature_names is None:
            feature_names = list(self._metadata.keys())
        
        if not feature_names:
            return 0
        
        return max(
            self._metadata[name].min_bars
            for name in feature_names
            if name in self._metadata
        )
    
    def can_compute(self, bars_available: int, feature_names: list[str] = None) -> bool:
        """
        Check if we have enough data to compute features.
        
        Args:
            bars_available: Number of bars in dataset
            feature_names: Specific features (None = all registered)
        
        Returns:
            True if enough data, False otherwise
        """
        min_required = self.get_min_bars_required(feature_names)
        return bars_available >= min_required
    
    def get_computation_cost(self, feature_names: list[str] = None) -> int:
        """
        Get total computation cost.
        
        Args:
            feature_names: Specific features (None = all registered)
        
        Returns:
            Sum of feature costs
        """
        if feature_names is None:
            feature_names = list(self._metadata.keys())
        
        return sum(
            self._metadata[name].cost
            for name in feature_names
            if name in self._metadata
        )
    
    def get_top_features(
        self,
        n: int = 10,
        group: Optional[str] = None
    ) -> list[FeatureMetadata]:
        """
        Get top N most important features.
        
        Args:
            n: Number of features to return
            group: Filter by group (None = all groups)
        
        Returns:
            List of top N features sorted by importance
        
        Raises:
            ValueError: If no features have importance scores
        """
        # Filter by group if specified
        features = self.get_by_group(group) if group else list(self._metadata.values())
        
        # Filter to features with importance scores
        scored_features = [f for f in features if f.importance is not None]
        
        if not scored_features:
            raise ValueError("No features have importance scores. Train a model first.")
        
        # Sort by importance (descending)
        scored_features.sort(key=lambda f: f.importance, reverse=True)
        
        return scored_features[:n]
    
    def update_importance(self, importance_dict: dict[str, float]):
        """
        Update feature importance scores from model.
        
        Args:
            importance_dict: Mapping of feature_name -> importance_score
        """
        for name, importance in importance_dict.items():
            if name in self._metadata:
                self._metadata[name].importance = importance
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Export metadata to DataFrame.
        
        Returns:
            DataFrame with one row per feature
        """
        return pd.DataFrame([m.to_dict() for m in self._metadata.values()])
    
    def get_summary(self) -> dict:
        """
        Get summary statistics about registered features.
        
        Returns:
            Dictionary with summary stats
        """
        if not self._metadata:
            return {
                "total_features": 0,
                "by_group": {},
                "min_bars_needed": 0,
                "total_cost": 0
            }
        
        # Group counts
        group_counts = {}
        for metadata in self._metadata.values():
            group_counts[metadata.group] = group_counts.get(metadata.group, 0) + 1
        
        return {
            "total_features": len(self._metadata),
            "by_group": group_counts,
            "min_bars_needed": max(m.min_bars for m in self._metadata.values()),
            "total_cost": sum(m.cost for m in self._metadata.values()),
            "features_with_importance": sum(
                1 for m in self._metadata.values() if m.importance is not None
            )
        }
    
    def clear(self):
        """Clear all registered metadata."""
        self._metadata.clear()


# Helper function to create metadata for common extractors
def create_technical_metadata(rsi_period: int = 14) -> list[FeatureMetadata]:
    """Create metadata for technical indicator features."""
    return [
        FeatureMetadata(
            name=f"rsi_{rsi_period}",
            group="technical",
            min_bars=rsi_period,
            cost=2,
            description=f"Relative Strength Index ({rsi_period} periods)"
        ),
        FeatureMetadata(
            name="macd_line",
            group="technical",
            min_bars=26,
            cost=2,
            description="MACD line (12/26 EMA difference)"
        ),
        FeatureMetadata(
            name="macd_signal",
            group="technical",
            min_bars=35,
            cost=2,
            description="MACD signal line (9 EMA of MACD)"
        ),
        FeatureMetadata(
            name="macd_histogram",
            group="technical",
            min_bars=35,
            cost=1,
            description="MACD histogram (line - signal)"
        ),
        FeatureMetadata(
            name="bb_upper_pct",
            group="technical",
            min_bars=20,
            cost=2,
            description="Bollinger Band upper percentage"
        ),
        FeatureMetadata(
            name="bb_lower_pct",
            group="technical",
            min_bars=20,
            cost=2,
            description="Bollinger Band lower percentage"
        ),
        FeatureMetadata(
            name="bb_width",
            group="technical",
            min_bars=20,
            cost=1,
            description="Bollinger Band width (normalized)"
        ),
        FeatureMetadata(
            name="atr",
            group="technical",
            min_bars=14,
            cost=2,
            description="Average True Range (14 periods)"
        )
    ]


def create_rolling_metadata(windows: list[int]) -> list[FeatureMetadata]:
    """Create metadata for rolling window features."""
    metadata = []
    
    for window in windows:
        prefix = f"roll_{window}"
        
        metadata.extend([
            FeatureMetadata(
                name=f"{prefix}_log_return",
                group="rolling",
                min_bars=window,
                cost=1,
                description=f"Log return over {window} bars"
            ),
            FeatureMetadata(
                name=f"{prefix}_simple_return",
                group="rolling",
                min_bars=window,
                cost=1,
                description=f"Simple return over {window} bars"
            ),
            FeatureMetadata(
                name=f"{prefix}_volatility",
                group="rolling",
                min_bars=window,
                cost=2,
                description=f"Realized volatility ({window} bars)"
            ),
            FeatureMetadata(
                name=f"{prefix}_parkinson_vol",
                group="rolling",
                min_bars=window,
                cost=2,
                description=f"Parkinson volatility ({window} bars)"
            ),
            FeatureMetadata(
                name=f"{prefix}_percentile",
                group="rolling",
                min_bars=window,
                cost=3,
                description=f"Percentile rank ({window} bars)"
            ),
            FeatureMetadata(
                name=f"{prefix}_zscore",
                group="rolling",
                min_bars=window,
                cost=2,
                description=f"Z-score ({window} bars)"
            )
        ])
    
    return metadata


def create_temporal_metadata() -> list[FeatureMetadata]:
    """Create metadata for temporal features."""
    return [
        FeatureMetadata(
            name="hour_sin",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Hour of day (sine encoding)"
        ),
        FeatureMetadata(
            name="hour_cos",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Hour of day (cosine encoding)"
        ),
        FeatureMetadata(
            name="minute_sin",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Minute of hour (sine encoding)"
        ),
        FeatureMetadata(
            name="minute_cos",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Minute of hour (cosine encoding)"
        ),
        FeatureMetadata(
            name="day_of_week_sin",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Day of week (sine encoding)"
        ),
        FeatureMetadata(
            name="day_of_week_cos",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Day of week (cosine encoding)"
        ),
        FeatureMetadata(
            name="is_market_open",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Market session (9:30-16:00 ET)"
        ),
        FeatureMetadata(
            name="is_pre_market",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Pre-market session (4:00-9:30 ET)"
        ),
        FeatureMetadata(
            name="is_after_hours",
            group="temporal",
            min_bars=1,
            cost=1,
            description="After-hours session (16:00-20:00 ET)"
        ),
        FeatureMetadata(
            name="is_weekend",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Weekend flag"
        ),
        FeatureMetadata(
            name="minutes_into_session",
            group="temporal",
            min_bars=1,
            cost=1,
            description="Minutes since session start"
        )
    ]


def create_volume_metadata(vwap_window: int = 20, volume_window: int = 20) -> list[FeatureMetadata]:
    """Create metadata for volume features."""
    return [
        FeatureMetadata(
            name="vwap",
            group="volume",
            min_bars=vwap_window,
            cost=2,
            description=f"Volume-Weighted Average Price ({vwap_window} bars)"
        ),
        FeatureMetadata(
            name="volume_ratio",
            group="volume",
            min_bars=volume_window,
            cost=2,
            description=f"Current volume / average volume ({volume_window} bars)"
        ),
        FeatureMetadata(
            name="volume_accel",
            group="volume",
            min_bars=3,
            cost=1,
            description="Volume acceleration (second derivative)"
        ),
        FeatureMetadata(
            name="relative_volume",
            group="volume",
            min_bars=volume_window,
            cost=3,
            description=f"Volume percentile rank ({volume_window} bars)"
        ),
        FeatureMetadata(
            name="volume_price_corr",
            group="volume",
            min_bars=50,
            cost=3,
            description="Correlation between |returns| and volume"
        ),
        FeatureMetadata(
            name="obv",
            group="volume",
            min_bars=1,
            cost=1,
            description="On-Balance Volume (cumulative)"
        ),
        FeatureMetadata(
            name="vw_return",
            group="volume",
            min_bars=vwap_window,
            cost=2,
            description=f"Volume-weighted return ({vwap_window} bars)"
        )
    ]
