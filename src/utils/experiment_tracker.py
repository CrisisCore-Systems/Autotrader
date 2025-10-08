"""Experiment configuration tracking for reproducibility.

This module provides utilities for tracking experiment configurations,
including feature sets, weighting logic, and hyperparameters. Each
configuration is hashed for reproducibility and stored in a registry.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment.
    
    Captures all parameters needed to reproduce an experiment:
    - Feature set and transformations
    - Weighting logic for scoring
    - Hyperparameters (thresholds, k-values, etc.)
    - Metadata (description, tags)
    """
    
    # Core configuration
    feature_names: List[str]
    """List of feature names used in the experiment"""
    
    feature_weights: Dict[str, float]
    """Weights applied to each feature in scoring"""
    
    # Hyperparameters
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    """Additional hyperparameters (thresholds, k-values, etc.)"""
    
    # Feature engineering
    feature_transformations: Dict[str, str] = field(default_factory=dict)
    """Feature transformation definitions (e.g., 'log', 'zscore')"""
    
    # Metadata
    description: str = ""
    """Human-readable description of the experiment"""
    
    tags: List[str] = field(default_factory=list)
    """Tags for categorizing experiments"""
    
    created_at: Optional[str] = None
    """ISO timestamp when config was created"""
    
    config_hash: Optional[str] = None
    """SHA256 hash of the configuration for reproducibility"""
    
    def __post_init__(self):
        """Generate hash and timestamp after initialization."""
        if self.created_at is None:
            self.created_at = datetime.now(UTC).isoformat()
        if self.config_hash is None:
            self.config_hash = self.compute_hash()
    
    def compute_hash(self) -> str:
        """Compute SHA256 hash of the configuration.
        
        The hash is computed from:
        - Feature names (sorted)
        - Feature weights (sorted by key)
        - Feature transformations (sorted by key)
        - Hyperparameters (sorted by key)
        
        This ensures the hash is deterministic regardless of dict ordering.
        
        Returns:
            Hex string of SHA256 hash
        """
        # Create deterministic representation
        config_data = {
            "feature_names": sorted(self.feature_names),
            "feature_weights": {k: self.feature_weights[k] for k in sorted(self.feature_weights.keys())},
            "feature_transformations": {k: self.feature_transformations[k] for k in sorted(self.feature_transformations.keys())},
            "hyperparameters": {k: self.hyperparameters[k] for k in sorted(self.hyperparameters.keys())},
        }
        
        # Serialize to JSON with sorted keys
        config_json = json.dumps(config_data, sort_keys=True, default=str)
        
        # Compute SHA256 hash
        return hashlib.sha256(config_json.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperimentConfig:
        """Create from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ExperimentConfig instance
        """
        return cls(**data)
    
    def to_json(self) -> str:
        """Serialize to JSON.
        
        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> ExperimentConfig:
        """Deserialize from JSON.
        
        Args:
            json_str: JSON string
            
        Returns:
            ExperimentConfig instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Multi-line summary string
        """
        lines = [
            f"Experiment Configuration: {self.config_hash[:12]}",
            f"Created: {self.created_at}",
            f"Description: {self.description or '(none)'}",
            f"Tags: {', '.join(self.tags) or '(none)'}",
            "",
            f"Features ({len(self.feature_names)}):",
        ]
        
        for name in sorted(self.feature_names):
            weight = self.feature_weights.get(name, 0.0)
            transform = self.feature_transformations.get(name, "none")
            lines.append(f"  - {name}: weight={weight:.4f}, transform={transform}")
        
        if self.hyperparameters:
            lines.append("")
            lines.append("Hyperparameters:")
            for key, value in sorted(self.hyperparameters.items()):
                lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines)


class ExperimentRegistry:
    """Persistent storage for experiment configurations.
    
    Uses SQLite to store and query experiment configurations by hash.
    Supports tagging, searching, and comparison of experiments.
    """
    
    def __init__(self, db_path: Path | str = "experiments.sqlite"):
        """Initialize the registry.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create experiments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                config_hash TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                description TEXT,
                feature_names TEXT NOT NULL,
                feature_weights TEXT NOT NULL,
                feature_transformations TEXT,
                hyperparameters TEXT,
                tags TEXT,
                config_json TEXT NOT NULL
            )
        """)
        
        # Create index on created_at for temporal queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON experiments(created_at)
        """)
        
        # Create tags table for better searching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiment_tags (
                config_hash TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (config_hash, tag),
                FOREIGN KEY (config_hash) REFERENCES experiments(config_hash)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def register(self, config: ExperimentConfig) -> str:
        """Register an experiment configuration.
        
        Args:
            config: Experiment configuration to register
            
        Returns:
            Config hash of the registered experiment
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert experiment
        cursor.execute("""
            INSERT OR REPLACE INTO experiments 
            (config_hash, created_at, description, feature_names, 
             feature_weights, feature_transformations, hyperparameters, 
             tags, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config.config_hash,
            config.created_at,
            config.description,
            json.dumps(config.feature_names),
            json.dumps(config.feature_weights),
            json.dumps(config.feature_transformations),
            json.dumps(config.hyperparameters),
            json.dumps(config.tags),
            config.to_json(),
        ))
        
        # Insert tags
        if config.tags:
            cursor.execute(
                "DELETE FROM experiment_tags WHERE config_hash = ?",
                (config.config_hash,)
            )
            for tag in config.tags:
                cursor.execute(
                    "INSERT INTO experiment_tags (config_hash, tag) VALUES (?, ?)",
                    (config.config_hash, tag)
                )
        
        conn.commit()
        conn.close()
        
        return config.config_hash
    
    def get(self, config_hash: str) -> Optional[ExperimentConfig]:
        """Retrieve an experiment by hash.
        
        Args:
            config_hash: Full or partial config hash
            
        Returns:
            ExperimentConfig if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Try exact match first
        cursor.execute(
            "SELECT config_json FROM experiments WHERE config_hash = ?",
            (config_hash,)
        )
        row = cursor.fetchone()
        
        # Try partial match if no exact match
        if not row and len(config_hash) < 64:
            cursor.execute(
                "SELECT config_json FROM experiments WHERE config_hash LIKE ?",
                (config_hash + "%",)
            )
            row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return ExperimentConfig.from_json(row[0])
        return None
    
    def list_all(self, limit: int = 100) -> List[ExperimentConfig]:
        """List all experiments.
        
        Args:
            limit: Maximum number of experiments to return
            
        Returns:
            List of experiment configurations
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT config_json FROM experiments ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        
        configs = []
        for row in cursor.fetchall():
            configs.append(ExperimentConfig.from_json(row[0]))
        
        conn.close()
        return configs
    
    def search_by_tag(self, tag: str) -> List[ExperimentConfig]:
        """Search experiments by tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of matching experiment configurations
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT e.config_json 
            FROM experiments e
            JOIN experiment_tags t ON e.config_hash = t.config_hash
            WHERE t.tag = ?
            ORDER BY e.created_at DESC
        """, (tag,))
        
        configs = []
        for row in cursor.fetchall():
            configs.append(ExperimentConfig.from_json(row[0]))
        
        conn.close()
        return configs
    
    def compare(self, hash1: str, hash2: str) -> Dict[str, Any]:
        """Compare two experiments.
        
        Args:
            hash1: First experiment hash
            hash2: Second experiment hash
            
        Returns:
            Dictionary with comparison results
        """
        config1 = self.get(hash1)
        config2 = self.get(hash2)
        
        if not config1 or not config2:
            return {"error": "One or both experiments not found"}
        
        # Compare feature sets
        features1 = set(config1.feature_names)
        features2 = set(config2.feature_names)
        
        # Compare weights
        weight_diffs = {}
        all_features = features1 | features2
        for feature in all_features:
            w1 = config1.feature_weights.get(feature, 0.0)
            w2 = config2.feature_weights.get(feature, 0.0)
            if abs(w1 - w2) > 1e-9:
                weight_diffs[feature] = {"config1": w1, "config2": w2, "diff": w2 - w1}
        
        return {
            "config1_hash": config1.config_hash[:12],
            "config2_hash": config2.config_hash[:12],
            "features": {
                "only_in_config1": sorted(features1 - features2),
                "only_in_config2": sorted(features2 - features1),
                "common": sorted(features1 & features2),
            },
            "weight_differences": weight_diffs,
            "hyperparameters": {
                "config1": config1.hyperparameters,
                "config2": config2.hyperparameters,
            },
        }
    
    def delete(self, config_hash: str) -> bool:
        """Delete an experiment.
        
        Args:
            config_hash: Config hash to delete
            
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM experiment_tags WHERE config_hash = ?", (config_hash,))
        cursor.execute("DELETE FROM experiments WHERE config_hash = ?", (config_hash,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted


def create_experiment_from_scoring_config(
    weights: Dict[str, float],
    features: List[str],
    hyperparameters: Optional[Dict[str, Any]] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
) -> ExperimentConfig:
    """Create an experiment config from scoring parameters.
    
    Convenience function for creating experiment configs from
    the scoring module's weight configuration.
    
    Args:
        weights: Feature weights (e.g., from scoring.WEIGHTS)
        features: List of feature names
        hyperparameters: Optional hyperparameters
        description: Experiment description
        tags: Optional tags
        
    Returns:
        ExperimentConfig instance
    """
    return ExperimentConfig(
        feature_names=features,
        feature_weights=weights,
        hyperparameters=hyperparameters or {},
        description=description,
        tags=tags or [],
    )


__all__ = [
    "ExperimentConfig",
    "ExperimentRegistry",
    "create_experiment_from_scoring_config",
]
