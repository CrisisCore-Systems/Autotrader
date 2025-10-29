"""Model caching and persistence for BounceHunter."""

from __future__ import annotations

import hashlib
import pickle
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class ModelMetadata:
    """Metadata for cached model."""
    
    version: str
    created_at: datetime
    last_updated: datetime
    tickers: list[str]
    training_samples: int
    model_hash: str
    config_hash: str
    feature_columns: list[str]
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    
    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if model needs refresh."""
        age = datetime.now() - self.last_updated
        return age > timedelta(hours=max_age_hours)
    
    def matches_config(self, config_hash: str) -> bool:
        """Check if config has changed."""
        return self.config_hash == config_hash


@dataclass
class CachedModel:
    """Cached model with metadata and artifacts."""
    
    model: Any  # CalibratedClassifierCV
    metadata: ModelMetadata
    training_data: pd.DataFrame
    artifacts: Dict[str, Any]
    vix_cache: Optional[pd.Series] = None


class ModelCache:
    """Manages model persistence and versioning."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize model cache.
        
        Args:
            cache_dir: Directory for cached models. Defaults to ./model_cache
        """
        self.cache_dir = cache_dir or Path("./model_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Optional[CachedModel] = None
    
    def get_model_path(self, config_hash: str) -> Path:
        """Get path for model file."""
        return self.cache_dir / f"bouncehunter_{config_hash}.pkl"
    
    def get_metadata_path(self, config_hash: str) -> Path:
        """Get path for metadata file."""
        return self.cache_dir / f"bouncehunter_{config_hash}_meta.pkl"
    
    def compute_config_hash(self, config: Any) -> str:
        """Compute hash of config for versioning."""
        # Extract relevant config attributes
        config_dict = {
            "tickers": sorted(config.tickers),
            "start": config.start,
            "z_score_drop": config.z_score_drop,
            "rsi2_max": config.rsi2_max,
            "max_dist_200dma": config.max_dist_200dma,
            "bcs_threshold": config.bcs_threshold,
            "rebound_pct": config.rebound_pct,
            "stop_pct": config.stop_pct,
            "horizon_days": config.horizon_days,
            "min_event_samples": config.min_event_samples,
        }
        config_str = str(sorted(config_dict.items()))
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def compute_model_hash(self, model: Any) -> str:
        """Compute hash of trained model."""
        try:
            model_bytes = pickle.dumps(model)
            return hashlib.sha256(model_bytes).hexdigest()[:16]
        except Exception as exc:
            warnings.warn(f"Failed to hash model: {exc}")
            return "unknown"
    
    def load(
        self,
        config: Any,
        max_age_hours: int = 24,
        force_refresh: bool = False,
    ) -> Optional[CachedModel]:
        """Load cached model if available and valid.
        
        Args:
            config: BounceHunterConfig instance
            max_age_hours: Maximum age before model is considered stale
            force_refresh: Force retraining even if cache exists
            
        Returns:
            CachedModel if valid cache exists, None otherwise
        """
        if force_refresh:
            return None
        
        # Check memory cache first
        if self._memory_cache is not None:
            config_hash = self.compute_config_hash(config)
            if (
                self._memory_cache.metadata.matches_config(config_hash)
                and not self._memory_cache.metadata.is_stale(max_age_hours)
            ):
                return self._memory_cache
        
        # Check disk cache
        config_hash = self.compute_config_hash(config)
        model_path = self.get_model_path(config_hash)
        meta_path = self.get_metadata_path(config_hash)
        
        if not model_path.exists() or not meta_path.exists():
            return None
        
        try:
            # Load metadata first
            with open(meta_path, "rb") as f:
                metadata = pickle.load(f)
            
            # Check if stale
            if metadata.is_stale(max_age_hours):
                return None
            
            # Load full model
            with open(model_path, "rb") as f:
                cached = pickle.load(f)
            
            # Update memory cache
            self._memory_cache = cached
            
            return cached
            
        except Exception as exc:
            warnings.warn(f"Failed to load cached model: {exc}")
            return None
    
    def save(
        self,
        model: Any,
        training_data: pd.DataFrame,
        artifacts: Dict[str, Any],
        config: Any,
        feature_columns: list[str],
        vix_cache: Optional[pd.Series] = None,
        performance_metrics: Optional[Dict[str, float]] = None,
    ) -> ModelMetadata:
        """Save trained model to cache.
        
        Args:
            model: Trained CalibratedClassifierCV model
            training_data: Training dataset
            artifacts: TrainingArtifact dictionary
            config: BounceHunterConfig instance
            feature_columns: List of feature column names
            vix_cache: Cached VIX data
            performance_metrics: Optional performance metrics
            
        Returns:
            ModelMetadata for saved model
        """
        config_hash = self.compute_config_hash(config)
        model_hash = self.compute_model_hash(model)
        
        # Create metadata
        now = datetime.now()
        metadata = ModelMetadata(
            version="1.0",
            created_at=now,
            last_updated=now,
            tickers=list(config.tickers),
            training_samples=len(training_data),
            model_hash=model_hash,
            config_hash=config_hash,
            feature_columns=feature_columns,
            performance_metrics=performance_metrics or {},
        )
        
        # Create cached model
        cached = CachedModel(
            model=model,
            metadata=metadata,
            training_data=training_data,
            artifacts=artifacts,
            vix_cache=vix_cache,
        )
        
        # Save to disk
        try:
            model_path = self.get_model_path(config_hash)
            meta_path = self.get_metadata_path(config_hash)
            
            with open(model_path, "wb") as f:
                pickle.dump(cached, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            with open(meta_path, "wb") as f:
                pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Update memory cache
            self._memory_cache = cached
            
        except Exception as exc:
            warnings.warn(f"Failed to save model cache: {exc}")
        
        return metadata
    
    def update_incremental(
        self,
        cached: CachedModel,
        new_training_data: pd.DataFrame,
        new_artifacts: Dict[str, Any],
        config: Any,
    ) -> CachedModel:
        """Incrementally update cached model with new data.
        
        Args:
            cached: Existing cached model
            new_training_data: New training samples to add
            new_artifacts: New artifacts to merge
            config: BounceHunterConfig instance
            
        Returns:
            Updated CachedModel
        """
        # Merge training data
        combined_training = pd.concat(
            [cached.training_data, new_training_data],
            ignore_index=True,
        )
        
        # Remove duplicates based on ticker and date
        if "ticker" in combined_training.columns and combined_training.index.name:
            combined_training = combined_training.drop_duplicates(
                subset=["ticker"],
                keep="last",
            )
        
        # Merge artifacts
        combined_artifacts = {**cached.artifacts, **new_artifacts}
        
        # Retrain model on combined data
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import TimeSeriesSplit
        
        feature_cols = cached.metadata.feature_columns
        X = combined_training[feature_cols].values
        y = combined_training["label"].values
        
        base_model = LogisticRegression(
            max_iter=300,
            solver="lbfgs",
            class_weight="balanced",
        )
        splits = max(2, min(5, max(1, len(combined_training) // 50)))
        cv = TimeSeriesSplit(n_splits=splits)
        updated_model = CalibratedClassifierCV(base_model, cv=cv, method="sigmoid")
        updated_model.fit(X, y)
        
        # Update metadata
        config_hash = self.compute_config_hash(config)
        model_hash = self.compute_model_hash(updated_model)
        
        updated_metadata = ModelMetadata(
            version=cached.metadata.version,
            created_at=cached.metadata.created_at,
            last_updated=datetime.now(),
            tickers=list(config.tickers),
            training_samples=len(combined_training),
            model_hash=model_hash,
            config_hash=config_hash,
            feature_columns=feature_cols,
            performance_metrics=cached.metadata.performance_metrics,
        )
        
        # Create updated cached model
        updated_cached = CachedModel(
            model=updated_model,
            metadata=updated_metadata,
            training_data=combined_training,
            artifacts=combined_artifacts,
            vix_cache=cached.vix_cache,
        )
        
        # Save updated model
        try:
            model_path = self.get_model_path(config_hash)
            meta_path = self.get_metadata_path(config_hash)
            
            with open(model_path, "wb") as f:
                pickle.dump(updated_cached, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            with open(meta_path, "wb") as f:
                pickle.dump(updated_metadata, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            self._memory_cache = updated_cached
            
        except Exception as exc:
            warnings.warn(f"Failed to save updated model: {exc}")
        
        return updated_cached
    
    def list_cached_models(self) -> list[ModelMetadata]:
        """List all cached models."""
        models = []
        for meta_path in self.cache_dir.glob("*_meta.pkl"):
            try:
                with open(meta_path, "rb") as f:
                    metadata = pickle.load(f)
                models.append(metadata)
            except Exception as exc:
                warnings.warn(f"Failed to load metadata from {meta_path}: {exc}")
        return models
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """Clear cached models.
        
        Args:
            older_than_days: Only clear models older than this many days.
                            If None, clears all.
        
        Returns:
            Number of models cleared
        """
        cleared = 0
        cutoff = datetime.now() - timedelta(days=older_than_days) if older_than_days else None
        
        for meta_path in self.cache_dir.glob("*_meta.pkl"):
            try:
                if cutoff:
                    with open(meta_path, "rb") as f:
                        metadata = pickle.load(f)
                    if metadata.last_updated > cutoff:
                        continue
                
                # Delete metadata and model files
                config_hash = meta_path.stem.replace("bouncehunter_", "").replace("_meta", "")
                model_path = self.get_model_path(config_hash)
                
                if model_path.exists():
                    model_path.unlink()
                meta_path.unlink()
                cleared += 1
                
            except Exception as exc:
                warnings.warn(f"Failed to clear {meta_path}: {exc}")
        
        # Clear memory cache
        if cleared > 0:
            self._memory_cache = None
        
        return cleared
    
    def get_cache_size(self) -> tuple[int, float]:
        """Get cache statistics.
        
        Returns:
            Tuple of (number_of_models, total_size_mb)
        """
        count = 0
        total_bytes = 0
        
        for path in self.cache_dir.glob("bouncehunter_*.pkl"):
            count += 1
            total_bytes += path.stat().st_size
        
        total_mb = total_bytes / (1024 * 1024)
        return count // 2, total_mb  # Divide by 2 because we have model + metadata files
