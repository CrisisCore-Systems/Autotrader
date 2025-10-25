"""
Feature transformation and post-processing.

Provides scalable feature transformations:
- Scaling (StandardScaler, MinMaxScaler, RobustScaler)
- Lagging (create historical features)
- Differencing (create change features)
- Outlier clipping
- Feature interactions (polynomial features)

These transformations prepare features for ML models and can significantly
improve model performance.
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from dataclasses import dataclass, field


@dataclass
class TransformerConfig:
    """
    Configuration for feature transformations.
    
    Attributes:
        scale_method: Scaling method ('standard', 'minmax', 'robust', None)
        add_lags: List of lag periods to add (e.g., [1, 2, 3])
        add_diffs: Whether to add differenced features
        clip_std: Clip outliers beyond N standard deviations (None = no clipping)
        add_interactions: Whether to add pairwise feature interactions
        interaction_pairs: Specific feature pairs to interact (None = all pairs)
    """
    scale_method: Optional[Literal["standard", "minmax", "robust"]] = None
    add_lags: Optional[list[int]] = None
    add_diffs: bool = False
    clip_std: Optional[float] = None
    add_interactions: bool = False
    interaction_pairs: Optional[list[tuple[str, str]]] = None


class FeatureTransformer:
    """
    Transform features for machine learning.
    
    Provides scaling, lagging, differencing, and interaction terms.
    Maintains fit state for consistent train/test transformation.
    
    Example:
        # Configure transformations
        config = TransformerConfig(
            scale_method="standard",
            add_lags=[1, 2, 3],
            add_diffs=True,
            clip_std=5.0
        )
        
        # Fit on training data
        transformer = FeatureTransformer(config)
        train_transformed = transformer.fit_transform(train_features)
        
        # Transform test data with same parameters
        test_transformed = transformer.transform(test_features)
    """
    
    def __init__(self, config: TransformerConfig = None):
        """
        Initialize feature transformer.
        
        Args:
            config: Transformation configuration (default: no transformations)
        """
        self.config = config or TransformerConfig()
        self.scaler = None
        self.clip_values = None
        self._is_fitted = False
    
    def fit_transform(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Fit transformer and transform features.
        
        Args:
            features: Input features
        
        Returns:
            Transformed features
        """
        # 1. Add lags (before scaling to preserve temporal structure)
        if self.config.add_lags:
            features = self._add_lags(features, self.config.add_lags)
        
        # 2. Add differences
        if self.config.add_diffs:
            features = self._add_diffs(features)
        
        # 3. Fit and apply outlier clipping
        if self.config.clip_std is not None:
            features = self._fit_clip_outliers(features)
        
        # 4. Fit and apply scaling
        if self.config.scale_method is not None:
            features = self._fit_scale(features)
        
        # 5. Add interactions (after scaling for numerical stability)
        if self.config.add_interactions:
            features = self._add_interactions(features)
        
        self._is_fitted = True
        return features
    
    def transform(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Transform features using fitted parameters.
        
        Args:
            features: Input features
        
        Returns:
            Transformed features
        
        Raises:
            ValueError: If transformer not fitted
        """
        if not self._is_fitted:
            raise ValueError("Transformer not fitted. Call fit_transform() first.")
        
        # Apply same transformations in same order
        if self.config.add_lags:
            features = self._add_lags(features, self.config.add_lags)
        
        if self.config.add_diffs:
            features = self._add_diffs(features)
        
        if self.config.clip_std is not None:
            features = self._apply_clip_outliers(features)
        
        if self.config.scale_method is not None:
            features = self._apply_scale(features)
        
        if self.config.add_interactions:
            features = self._add_interactions(features)
        
        return features
    
    def _add_lags(self, features: pd.DataFrame, lags: list[int]) -> pd.DataFrame:
        """Add lagged features."""
        lagged = features.copy()
        
        for lag in lags:
            for col in features.columns:
                lagged[f"{col}_lag{lag}"] = features[col].shift(lag)
        
        return lagged
    
    def _add_diffs(self, features: pd.DataFrame) -> pd.DataFrame:
        """Add differenced features (change from previous period)."""
        diffed = features.copy()
        
        for col in features.columns:
            # Skip already-differenced features and binary features
            if '_diff' in col or '_lag' in col or col.startswith('is_'):
                continue
            
            diffed[f"{col}_diff"] = features[col].diff()
        
        return diffed
    
    def _fit_clip_outliers(self, features: pd.DataFrame) -> pd.DataFrame:
        """Fit outlier clipping thresholds and apply."""
        # Calculate mean and std for each feature
        self.clip_values = {}
        
        for col in features.columns:
            mean = features[col].mean()
            std = features[col].std()
            
            lower = mean - self.config.clip_std * std
            upper = mean + self.config.clip_std * std
            
            self.clip_values[col] = (lower, upper)
        
        return self._apply_clip_outliers(features)
    
    def _apply_clip_outliers(self, features: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted outlier clipping."""
        clipped = features.copy()
        
        for col in features.columns:
            if col in self.clip_values:
                lower, upper = self.clip_values[col]
                clipped[col] = clipped[col].clip(lower, upper)
        
        return clipped
    
    def _fit_scale(self, features: pd.DataFrame) -> pd.DataFrame:
        """Fit scaler and apply."""
        # Initialize scaler
        if self.config.scale_method == "standard":
            self.scaler = StandardScaler()
        elif self.config.scale_method == "minmax":
            self.scaler = MinMaxScaler()
        elif self.config.scale_method == "robust":
            self.scaler = RobustScaler()
        else:
            raise ValueError(f"Unknown scale_method: {self.config.scale_method}")
        
        # Fit and transform
        scaled_values = self.scaler.fit_transform(features)
        
        return pd.DataFrame(
            scaled_values,
            index=features.index,
            columns=features.columns
        )
    
    def _apply_scale(self, features: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted scaler."""
        scaled_values = self.scaler.transform(features)
        
        return pd.DataFrame(
            scaled_values,
            index=features.index,
            columns=features.columns
        )
    
    def _add_interactions(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Add pairwise feature interactions.
        
        If interaction_pairs specified, only create those pairs.
        Otherwise, create all pairs (can be many!).
        """
        interacted = features.copy()
        
        if self.config.interaction_pairs:
            # Create only specified pairs
            for feat1, feat2 in self.config.interaction_pairs:
                if feat1 in features.columns and feat2 in features.columns:
                    interacted[f"{feat1}_x_{feat2}"] = features[feat1] * features[feat2]
        else:
            # Create all pairs (warning: O(N^2) features!)
            cols = features.columns.tolist()
            for i, feat1 in enumerate(cols):
                for feat2 in cols[i+1:]:  # Only upper triangle
                    interacted[f"{feat1}_x_{feat2}"] = features[feat1] * features[feat2]
        
        return interacted
    
    def get_feature_count(self, base_features: int) -> dict[str, int]:
        """
        Estimate feature count after transformation.
        
        Args:
            base_features: Number of input features
        
        Returns:
            Dictionary with feature counts by transformation type
        """
        counts = {"base": base_features}
        
        if self.config.add_lags:
            counts["lagged"] = base_features * len(self.config.add_lags)
        
        if self.config.add_diffs:
            # Estimate ~80% of features will be differenced (skip binary/already diffed)
            counts["differenced"] = int(base_features * 0.8)
        
        if self.config.add_interactions:
            if self.config.interaction_pairs:
                counts["interactions"] = len(self.config.interaction_pairs)
            else:
                # All pairs: n*(n-1)/2
                total = base_features
                if self.config.add_lags:
                    total += counts.get("lagged", 0)
                if self.config.add_diffs:
                    total += counts.get("differenced", 0)
                counts["interactions"] = (total * (total - 1)) // 2
        
        counts["total"] = sum(counts.values()) - counts["base"] + base_features
        
        return counts
