"""Tests for experiment tracking functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.utils.experiment_tracker import (
    ExperimentConfig,
    ExperimentRegistry,
    create_experiment_from_scoring_config,
)


class TestExperimentConfig:
    """Tests for ExperimentConfig class."""
    
    def test_basic_creation(self):
        """Test basic experiment config creation."""
        config = ExperimentConfig(
            feature_names=["price", "volume", "sentiment"],
            feature_weights={"price": 0.3, "volume": 0.4, "sentiment": 0.3},
            description="Test experiment",
            tags=["test", "baseline"],
        )
        
        assert len(config.feature_names) == 3
        assert config.feature_weights["price"] == 0.3
        assert config.description == "Test experiment"
        assert "test" in config.tags
        assert config.config_hash is not None
        assert len(config.config_hash) == 64  # SHA256 hex
        assert config.created_at is not None
    
    def test_hash_determinism(self):
        """Test that same config produces same hash."""
        config1 = ExperimentConfig(
            feature_names=["a", "b", "c"],
            feature_weights={"a": 0.5, "b": 0.3, "c": 0.2},
            hyperparameters={"k": 10, "seed": 42},
        )
        
        config2 = ExperimentConfig(
            feature_names=["a", "b", "c"],
            feature_weights={"a": 0.5, "b": 0.3, "c": 0.2},
            hyperparameters={"k": 10, "seed": 42},
        )
        
        assert config1.config_hash == config2.config_hash
    
    def test_hash_independence_of_description(self):
        """Test that description doesn't affect hash."""
        config1 = ExperimentConfig(
            feature_names=["a"],
            feature_weights={"a": 1.0},
            description="Description 1",
        )
        
        config2 = ExperimentConfig(
            feature_names=["a"],
            feature_weights={"a": 1.0},
            description="Description 2",
        )
        
        # Hash should be the same despite different descriptions
        assert config1.config_hash == config2.config_hash
    
    def test_hash_sensitivity_to_weights(self):
        """Test that weight changes affect hash."""
        config1 = ExperimentConfig(
            feature_names=["a", "b"],
            feature_weights={"a": 0.5, "b": 0.5},
        )
        
        config2 = ExperimentConfig(
            feature_names=["a", "b"],
            feature_weights={"a": 0.6, "b": 0.4},
        )
        
        assert config1.config_hash != config2.config_hash
    
    def test_hash_sensitivity_to_features(self):
        """Test that feature set changes affect hash."""
        config1 = ExperimentConfig(
            feature_names=["a", "b"],
            feature_weights={"a": 0.5, "b": 0.5},
        )
        
        config2 = ExperimentConfig(
            feature_names=["a", "b", "c"],
            feature_weights={"a": 0.5, "b": 0.5, "c": 0.0},
        )
        
        assert config1.config_hash != config2.config_hash
    
    def test_serialization_roundtrip(self):
        """Test JSON serialization and deserialization."""
        original = ExperimentConfig(
            feature_names=["x", "y", "z"],
            feature_weights={"x": 0.2, "y": 0.3, "z": 0.5},
            hyperparameters={"threshold": 0.7, "k": 5},
            feature_transformations={"x": "log", "y": "zscore"},
            description="Test config",
            tags=["test", "production"],
        )
        
        # Serialize to JSON
        json_str = original.to_json()
        
        # Deserialize from JSON
        restored = ExperimentConfig.from_json(json_str)
        
        # Compare
        assert restored.feature_names == original.feature_names
        assert restored.feature_weights == original.feature_weights
        assert restored.hyperparameters == original.hyperparameters
        assert restored.feature_transformations == original.feature_transformations
        assert restored.description == original.description
        assert restored.tags == original.tags
        assert restored.config_hash == original.config_hash
    
    def test_summary_output(self):
        """Test summary generation."""
        config = ExperimentConfig(
            feature_names=["feature1", "feature2"],
            feature_weights={"feature1": 0.6, "feature2": 0.4},
            hyperparameters={"k": 10},
            description="Test summary",
            tags=["tag1"],
        )
        
        summary = config.summary()
        
        assert "Experiment Configuration" in summary
        assert config.config_hash[:12] in summary
        assert "Test summary" in summary
        assert "feature1" in summary
        assert "feature2" in summary
        assert "0.6000" in summary
        assert "k: 10" in summary


class TestExperimentRegistry:
    """Tests for ExperimentRegistry class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = Path(f.name)
        
        yield db_path
        
        # Cleanup
        if db_path.exists():
            db_path.unlink()
    
    def test_register_and_retrieve(self, temp_db):
        """Test registering and retrieving experiments."""
        registry = ExperimentRegistry(temp_db)
        
        config = ExperimentConfig(
            feature_names=["a", "b"],
            feature_weights={"a": 0.5, "b": 0.5},
            description="Test experiment",
        )
        
        # Register
        config_hash = registry.register(config)
        assert config_hash == config.config_hash
        
        # Retrieve
        retrieved = registry.get(config_hash)
        assert retrieved is not None
        assert retrieved.config_hash == config.config_hash
        assert retrieved.description == "Test experiment"
    
    def test_partial_hash_lookup(self, temp_db):
        """Test retrieving by partial hash."""
        registry = ExperimentRegistry(temp_db)
        
        config = ExperimentConfig(
            feature_names=["x"],
            feature_weights={"x": 1.0},
        )
        
        registry.register(config)
        
        # Retrieve with partial hash
        partial_hash = config.config_hash[:12]
        retrieved = registry.get(partial_hash)
        
        assert retrieved is not None
        assert retrieved.config_hash == config.config_hash
    
    def test_list_all(self, temp_db):
        """Test listing all experiments."""
        registry = ExperimentRegistry(temp_db)
        
        # Register multiple configs
        configs = []
        for i in range(3):
            config = ExperimentConfig(
                feature_names=[f"feature_{i}"],
                feature_weights={f"feature_{i}": 1.0},
                description=f"Experiment {i}",
            )
            registry.register(config)
            configs.append(config)
        
        # List all
        all_configs = registry.list_all(limit=10)
        
        assert len(all_configs) == 3
        
        # Check they're returned in reverse chronological order
        hashes = [c.config_hash for c in all_configs]
        original_hashes = [c.config_hash for c in reversed(configs)]
        assert hashes == original_hashes
    
    def test_search_by_tag(self, temp_db):
        """Test searching by tag."""
        registry = ExperimentRegistry(temp_db)
        
        # Register configs with different tags
        config1 = ExperimentConfig(
            feature_names=["a"],
            feature_weights={"a": 1.0},
            tags=["baseline", "production"],
        )
        
        config2 = ExperimentConfig(
            feature_names=["b"],
            feature_weights={"b": 1.0},
            tags=["experimental"],
        )
        
        config3 = ExperimentConfig(
            feature_names=["c"],
            feature_weights={"c": 1.0},
            tags=["baseline", "test"],
        )
        
        registry.register(config1)
        registry.register(config2)
        registry.register(config3)
        
        # Search for "baseline" tag
        baseline_configs = registry.search_by_tag("baseline")
        
        assert len(baseline_configs) == 2
        hashes = {c.config_hash for c in baseline_configs}
        assert config1.config_hash in hashes
        assert config3.config_hash in hashes
    
    def test_compare_experiments(self, temp_db):
        """Test comparing two experiments."""
        registry = ExperimentRegistry(temp_db)
        
        config1 = ExperimentConfig(
            feature_names=["a", "b", "c"],
            feature_weights={"a": 0.3, "b": 0.4, "c": 0.3},
            hyperparameters={"k": 10},
        )
        
        config2 = ExperimentConfig(
            feature_names=["a", "b", "d"],
            feature_weights={"a": 0.5, "b": 0.4, "d": 0.1},
            hyperparameters={"k": 15},
        )
        
        registry.register(config1)
        registry.register(config2)
        
        comparison = registry.compare(config1.config_hash, config2.config_hash)
        
        assert "error" not in comparison
        assert comparison["features"]["only_in_config1"] == ["c"]
        assert comparison["features"]["only_in_config2"] == ["d"]
        assert "b" in comparison["features"]["common"]
        assert "a" in comparison["weight_differences"]
        assert comparison["weight_differences"]["a"]["diff"] == 0.2  # 0.5 - 0.3
    
    def test_delete_experiment(self, temp_db):
        """Test deleting an experiment."""
        registry = ExperimentRegistry(temp_db)
        
        config = ExperimentConfig(
            feature_names=["x"],
            feature_weights={"x": 1.0},
        )
        
        config_hash = registry.register(config)
        
        # Verify it exists
        assert registry.get(config_hash) is not None
        
        # Delete
        deleted = registry.delete(config_hash)
        assert deleted is True
        
        # Verify it's gone
        assert registry.get(config_hash) is None
        
        # Delete again should return False
        deleted = registry.delete(config_hash)
        assert deleted is False
    
    def test_update_experiment(self, temp_db):
        """Test updating an experiment (same hash)."""
        registry = ExperimentRegistry(temp_db)
        
        config1 = ExperimentConfig(
            feature_names=["a"],
            feature_weights={"a": 1.0},
            description="Original description",
            tags=["v1"],
        )
        
        registry.register(config1)
        
        # Create updated version with same hash but different metadata
        config2 = ExperimentConfig(
            feature_names=["a"],
            feature_weights={"a": 1.0},
            description="Updated description",
            tags=["v2"],
        )
        
        # Force same hash (in practice, hash is same if config is same)
        assert config1.config_hash == config2.config_hash
        
        registry.register(config2)
        
        # Retrieve should get updated version
        retrieved = registry.get(config1.config_hash)
        assert retrieved.description == "Updated description"
        assert "v2" in retrieved.tags


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_create_from_scoring_config(self):
        """Test creating config from scoring parameters."""
        weights = {
            "SentimentScore": 0.15,
            "AccumulationScore": 0.20,
            "OnchainActivity": 0.15,
        }
        
        features = list(weights.keys())
        
        config = create_experiment_from_scoring_config(
            weights=weights,
            features=features,
            hyperparameters={"k": 10, "threshold": 0.7},
            description="GemScore baseline",
            tags=["gemscore", "baseline"],
        )
        
        assert config.feature_names == features
        assert config.feature_weights == weights
        assert config.hyperparameters["k"] == 10
        assert config.description == "GemScore baseline"
        assert "gemscore" in config.tags


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_features(self):
        """Test config with no features."""
        config = ExperimentConfig(
            feature_names=[],
            feature_weights={},
        )
        
        assert config.config_hash is not None
        assert len(config.feature_names) == 0
    
    def test_missing_weight_for_feature(self):
        """Test feature without corresponding weight."""
        config = ExperimentConfig(
            feature_names=["a", "b"],
            feature_weights={"a": 0.5},  # b is missing
        )
        
        # Should not raise error
        assert config.config_hash is not None
    
    def test_extra_weight_without_feature(self):
        """Test weight without corresponding feature."""
        config = ExperimentConfig(
            feature_names=["a"],
            feature_weights={"a": 0.5, "b": 0.5},  # b not in features
        )
        
        # Should not raise error
        assert config.config_hash is not None
    
    def test_unicode_in_description(self):
        """Test unicode characters in description."""
        config = ExperimentConfig(
            feature_names=["x"],
            feature_weights={"x": 1.0},
            description="Test with emoji 🚀 and unicode: αβγ",
        )
        
        json_str = config.to_json()
        restored = ExperimentConfig.from_json(json_str)
        
        assert restored.description == config.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
