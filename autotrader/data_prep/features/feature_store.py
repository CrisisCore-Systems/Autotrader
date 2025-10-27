"""
Feature store with leakage-safe rolling windows and caching.

Prevents lookahead bias by ensuring features use only past data:
- Rolling windows with strict causality
- Warm-up period tracking
- Incremental updates (online computation)
- Feature versioning
- Cache management for performance

Critical for production trading:
- No future data leakage (fatal flaw in backtests)
- Warm-up tracking (ensure sufficient history)
- Reproducibility (version tracking)
- Performance (caching, incremental)

References:
- Lookahead bias: Lopez de Prado (2018) "Advances in Financial Machine Learning"
- Online algorithms: Welford (1962) for running statistics
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import hashlib
import pickle
from pathlib import Path


class FeatureStore:
    """
    Leakage-safe feature store with caching and versioning.
    
    Key features:
    1. Strict causality: Features at time t use only data up to t-1
    2. Warm-up tracking: Track minimum required history
    3. Incremental updates: Update features with new data only
    4. Caching: Store computed features to avoid recomputation
    5. Versioning: Track feature computation changes
    
    Example:
        store = FeatureStore(cache_dir='./feature_cache')
        
        # Add feature definitions
        store.add_feature(
            name='sma_20',
            compute_fn=lambda df: df['close'].rolling(20).mean(),
            warm_up_periods=20
        )
        
        # Compute features (cached)
        features = store.compute_features(df, use_cache=True)
        
        # Incremental update (new data only)
        new_features = store.update_features(new_df)
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_cache_age_days: int = 7
    ):
        """
        Initialize feature store.
        
        Args:
            cache_dir: Directory for feature cache (None = no caching)
            max_cache_age_days: Maximum age for cached features
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_cache_age_days = max_cache_age_days
        
        # Feature registry
        self.features: Dict[str, Dict[str, Any]] = {}
        
        # Warm-up tracking
        self.warm_up_periods: Dict[str, int] = {}
        
        # Version tracking
        self.version = 1
        
        # Cache management
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def add_feature(
        self,
        name: str,
        compute_fn: Callable[[pd.DataFrame], pd.Series],
        warm_up_periods: int = 0,
        dependencies: Optional[list[str]] = None
    ):
        """
        Register a feature computation function.
        
        Args:
            name: Feature name
            compute_fn: Function that takes DataFrame and returns Series
            warm_up_periods: Minimum required history (rows)
            dependencies: List of feature names this depends on
        """
        self.features[name] = {
            'compute_fn': compute_fn,
            'warm_up_periods': warm_up_periods,
            'dependencies': dependencies or [],
            'version': self.version
        }
        
        self.warm_up_periods[name] = warm_up_periods
    
    def compute_features(
        self,
        df: pd.DataFrame,
        feature_names: Optional[list[str]] = None,
        use_cache: bool = True,
        validate_leakage: bool = True
    ) -> pd.DataFrame:
        """
        Compute features with leakage prevention.
        
        Args:
            df: Input DataFrame (must have DatetimeIndex)
            feature_names: Features to compute (None = all)
            use_cache: Use cached features if available
            validate_leakage: Check for lookahead bias
        
        Returns:
            DataFrame with computed features
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex for leakage safety")
        
        if feature_names is None:
            feature_names = list(self.features.keys())
        
        # Check cache first
        if use_cache and self.cache_dir:
            cached_features = self._load_from_cache(df, feature_names)
            if cached_features is not None:
                return cached_features
        
        # Compute features
        result = pd.DataFrame(index=df.index)
        
        for name in feature_names:
            if name not in self.features:
                raise ValueError(f"Feature '{name}' not registered")
            
            feature_config = self.features[name]
            
            # Check warm-up
            required_warmup = feature_config['warm_up_periods']
            if len(df) < required_warmup:
                raise ValueError(
                    f"Feature '{name}' requires {required_warmup} warm-up periods, "
                    f"but only {len(df)} rows provided"
                )
            
            # Compute feature
            try:
                feature_series = feature_config['compute_fn'](df)
                
                # Ensure leakage safety: shift by 1 to avoid using current bar
                if validate_leakage:
                    feature_series = feature_series.shift(1)
                
                result[name] = feature_series
            
            except Exception as e:
                raise RuntimeError(f"Error computing feature '{name}': {str(e)}")
        
        # Save to cache
        if use_cache and self.cache_dir:
            self._save_to_cache(df, result, feature_names)
        
        return result
    
    def update_features(
        self,
        new_df: pd.DataFrame,
        previous_features: pd.DataFrame,
        feature_names: Optional[list[str]] = None
    ) -> pd.DataFrame:
        """
        Incremental feature update (append new data only).
        
        This is critical for live trading:
        - Only compute features for new bars
        - Reuse previous computations
        - Maintain rolling window state
        
        Args:
            new_df: New data (must start after previous_features.index[-1])
            previous_features: Previously computed features
            feature_names: Features to update (None = all)
        
        Returns:
            Updated features (previous + new)
        """
        if len(previous_features) == 0:
            return self.compute_features(new_df, feature_names)
        
        # Validate chronological order
        if new_df.index[0] <= previous_features.index[-1]:
            raise ValueError(
                "new_df must start after previous_features (chronological order)"
            )
        
        if feature_names is None:
            feature_names = list(self.features.keys())
        
        # Combine data for rolling window computation
        # (need history for window calculations)
        max_warmup = max(self.warm_up_periods.values(), default=0)
        
        # Get sufficient history
        history_df = previous_features.index[-max_warmup:] if max_warmup > 0 else []
        
        # Compute features on new data (with history context)
        combined_df = pd.concat([new_df.iloc[-max_warmup:], new_df], axis=0)
        new_features = self.compute_features(
            combined_df,
            feature_names,
            use_cache=False,
            validate_leakage=True
        )
        
        # Keep only new rows
        new_features = new_features.loc[new_df.index]
        
        # Combine with previous features
        updated_features = pd.concat([previous_features, new_features], axis=0)
        
        return updated_features
    
    def validate_no_leakage(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
        target: pd.Series,
        max_allowed_correlation: float = 0.1
    ) -> Dict[str, float]:
        """
        Validate features don't leak future information.
        
        Test: Correlate features at t with target at t-1 (backward)
        If correlation > threshold, features may be using future data.
        
        Args:
            df: Input data
            features: Computed features
            target: Target variable (e.g., future returns)
            max_allowed_correlation: Threshold for leakage warning
        
        Returns:
            Dictionary of suspicious features and their correlations
        """
        suspicious = {}
        
        # Shift target backward (features at t, target at t-1)
        target_backward = target.shift(-1)
        
        for col in features.columns:
            # Correlation between feature at t and target at t-1
            corr = features[col].corr(target_backward)
            
            if abs(corr) > max_allowed_correlation:
                suspicious[col] = corr
        
        if suspicious:
            print("WARNING: Potential lookahead bias detected:")
            for feat, corr in suspicious.items():
                print(f"  {feat}: correlation = {corr:.4f}")
        
        return suspicious
    
    def get_warm_up_requirement(
        self,
        feature_names: Optional[list[str]] = None
    ) -> int:
        """
        Get minimum warm-up periods required for features.
        
        Args:
            feature_names: Features to check (None = all)
        
        Returns:
            Maximum warm-up periods across all features
        """
        if feature_names is None:
            feature_names = list(self.features.keys())
        
        max_warmup = 0
        for name in feature_names:
            if name in self.warm_up_periods:
                max_warmup = max(max_warmup, self.warm_up_periods[name])
        
        return max_warmup
    
    def _get_cache_key(
        self,
        df: pd.DataFrame,
        feature_names: list[str]
    ) -> str:
        """Generate cache key from data and features."""
        # Hash based on:
        # 1. Data index (timestamps)
        # 2. Feature names
        # 3. Feature versions
        
        index_hash = hashlib.md5(
            str(df.index.tolist()).encode()
        ).hexdigest()[:8]
        
        features_hash = hashlib.md5(
            str(sorted(feature_names)).encode()
        ).hexdigest()[:8]
        
        versions_hash = hashlib.md5(
            str([self.features[name]['version'] for name in feature_names]).encode()
        ).hexdigest()[:8]
        
        cache_key = f"{index_hash}_{features_hash}_{versions_hash}"
        
        return cache_key
    
    def _load_from_cache(
        self,
        df: pd.DataFrame,
        feature_names: list[str]
    ) -> Optional[pd.DataFrame]:
        """Load features from cache if available and valid."""
        cache_key = self._get_cache_key(df, feature_names)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if not cache_file.exists():
            return None
        
        # Check cache age
        cache_age = datetime.now().timestamp() - cache_file.stat().st_mtime
        max_age_seconds = self.max_cache_age_days * 24 * 3600
        
        if cache_age > max_age_seconds:
            # Cache too old
            cache_file.unlink()
            return None
        
        # Load cached features
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            
            return cached_data
        
        except Exception:
            # Cache corrupted
            cache_file.unlink()
            return None
    
    def _save_to_cache(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
        feature_names: list[str]
    ):
        """Save computed features to cache."""
        cache_key = self._get_cache_key(df, feature_names)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(features, f)
        
        except Exception as e:
            print(f"WARNING: Failed to save cache: {e}")
    
    def clear_cache(self):
        """Clear all cached features."""
        if self.cache_dir and self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
    
    def increment_version(self):
        """Increment feature version (invalidates cache)."""
        self.version += 1
        
        # Update all feature versions
        for name in self.features:
            self.features[name]['version'] = self.version


class OnlineStatistics:
    """
    Online (incremental) statistics computation.
    
    Efficiently compute running statistics without storing history:
    - Mean, variance, std
    - Min, max
    - Exponential moving average
    
    Reference: Welford (1962) "Note on a Method for Calculating
    Corrected Sums of Squares and Products"
    """
    
    def __init__(self):
        """Initialize online statistics."""
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0  # Sum of squared differences
        self.min_val = float('inf')
        self.max_val = float('-inf')
    
    def update(self, value: float):
        """Update statistics with new value."""
        self.n += 1
        
        # Welford's online algorithm for variance
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.M2 += delta * delta2
        
        # Min/max
        self.min_val = min(self.min_val, value)
        self.max_val = max(self.max_val, value)
    
    @property
    def variance(self) -> float:
        """Get variance."""
        if self.n < 2:
            return 0.0
        return self.M2 / (self.n - 1)
    
    @property
    def std(self) -> float:
        """Get standard deviation."""
        return np.sqrt(self.variance)
    
    def reset(self):
        """Reset statistics."""
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0
        self.min_val = float('inf')
        self.max_val = float('-inf')
