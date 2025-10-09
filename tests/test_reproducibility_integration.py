"""Integration test for reproducibility stamping.

This test verifies that:
1. Repro stamps are created correctly
2. Identical inputs produce identical stamps
3. Different inputs produce different stamps
4. Stamps can be validated
5. Stamps survive serialization/deserialization
6. Stamps integrate correctly with scan results

Run with: pytest tests/test_reproducibility_integration.py -v
"""

import hashlib
import json
import random
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest

from src.core.repro_stamper import (
    ReproStamp,
    ReproStamper,
    add_repro_stamp_to_output,
    create_repro_stamp,
)


# ============================================================================
# Synthetic Data Generators
# ============================================================================


def create_synthetic_price_data(
    seed: int, num_points: int = 100, base_price: float = 1.0
) -> Dict[str, Any]:
    """Create synthetic price time series data.
    
    Args:
        seed: Random seed for reproducibility
        num_points: Number of data points
        base_price: Base price to start from
    
    Returns:
        Dictionary with price data
    """
    random.seed(seed)
    prices = []
    timestamps = []
    
    current_price = base_price
    current_time = 1700000000  # Unix timestamp
    
    for _ in range(num_points):
        # Random walk with small steps
        change = random.uniform(-0.05, 0.05)
        current_price = current_price * (1 + change)
        
        prices.append(current_price)
        timestamps.append(current_time)
        current_time += 300  # 5 minute intervals
    
    return {
        "prices": prices,
        "timestamps": timestamps,
        "volume": [random.uniform(10000, 100000) for _ in range(num_points)],
    }


def create_synthetic_token_config(seed: int) -> Dict[str, Any]:
    """Create synthetic token configuration.
    
    Args:
        seed: Random seed for deterministic generation
    
    Returns:
        Token configuration dictionary
    """
    random.seed(seed)
    
    return {
        "symbol": f"TEST{seed}",
        "address": f"0x{hashlib.sha256(str(seed).encode()).hexdigest()[:40]}",
        "chain": "ethereum",
        "liquidity_threshold": random.choice([50000, 100000, 200000]),
        "min_holders": random.choice([100, 500, 1000]),
        "max_age_days": random.choice([30, 60, 90]),
        "strategies": ["momentum", "value", "technical"],
    }


def create_synthetic_scan_output(seed: int) -> Dict[str, Any]:
    """Create synthetic scan output data.
    
    Args:
        seed: Random seed for reproducibility
    
    Returns:
        Dictionary representing scan output
    """
    random.seed(seed)
    
    price_data = create_synthetic_price_data(seed)
    token_config = create_synthetic_token_config(seed)
    
    return {
        "token": token_config["symbol"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "price_data": price_data,
        "metrics": {
            "volatility": random.uniform(0.1, 0.5),
            "momentum": random.uniform(-0.2, 0.2),
            "liquidity_score": random.uniform(0.5, 1.0),
            "holder_count": random.randint(100, 10000),
        },
        "scores": {
            "gem_score": random.uniform(0.3, 0.9),
            "safety_score": random.uniform(0.6, 1.0),
            "confidence": random.uniform(0.4, 0.95),
        },
        "flags": {
            "is_flagged": random.choice([True, False]),
            "risk_level": random.choice(["low", "medium", "high"]),
        },
    }


# ============================================================================
# Basic Stamp Creation Tests
# ============================================================================


def test_basic_stamp_creation():
    """Test basic stamp creation with minimal parameters."""
    stamper = ReproStamper()
    stamp = stamper.create_stamp(random_seed=42)
    
    assert stamp is not None
    assert stamp.timestamp is not None
    assert stamp.stamp_version == "1.0.0"
    assert stamp.random_seed == 42
    assert isinstance(stamp.get_composite_hash(), str)
    assert len(stamp.get_composite_hash()) == 16  # First 16 chars of SHA256


def test_stamp_with_config():
    """Test stamp creation with configuration data."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    stamp = stamper.create_stamp(config_data=config, random_seed=42)
    
    assert stamp.config_hash is not None
    assert len(stamp.config_hash) == 16
    assert stamp.random_seed == 42


def test_stamp_with_input_files(tmp_path):
    """Test stamp creation with input files."""
    # Create test files
    file1 = tmp_path / "data1.json"
    file2 = tmp_path / "data2.json"
    
    file1.write_text(json.dumps({"data": "test1"}))
    file2.write_text(json.dumps({"data": "test2"}))
    
    stamper = ReproStamper()
    stamp = stamper.create_stamp(input_files=[file1, file2], random_seed=42)
    
    assert len(stamp.input_hashes) == 2
    assert str(file1) in stamp.input_hashes
    assert str(file2) in stamp.input_hashes
    assert all(len(h) == 16 for h in stamp.input_hashes.values())


# ============================================================================
# Determinism Tests
# ============================================================================


def test_identical_inputs_produce_identical_stamps():
    """Test that identical inputs always produce identical stamps."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    
    # Create two stamps with identical inputs
    stamp1 = stamper.create_stamp(config_data=config, random_seed=42)
    stamp2 = stamper.create_stamp(config_data=config, random_seed=42)
    
    # Timestamps will differ, but hashes should be identical
    assert stamp1.config_hash == stamp2.config_hash
    assert stamp1.random_seed == stamp2.random_seed
    assert stamp1.python_version == stamp2.python_version


def test_different_seeds_produce_different_stamps():
    """Test that different seeds produce different stamps."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    
    stamp1 = stamper.create_stamp(config_data=config, random_seed=42)
    stamp2 = stamper.create_stamp(config_data=config, random_seed=43)
    
    # Seeds differ, so composite hashes should differ
    assert stamp1.random_seed != stamp2.random_seed
    assert stamp1.get_composite_hash() != stamp2.get_composite_hash()


def test_different_configs_produce_different_stamps():
    """Test that different configurations produce different stamps."""
    config1 = create_synthetic_token_config(42)
    config2 = create_synthetic_token_config(43)
    stamper = ReproStamper()
    
    stamp1 = stamper.create_stamp(config_data=config1, random_seed=42)
    stamp2 = stamper.create_stamp(config_data=config2, random_seed=42)
    
    # Configs differ, so config hashes should differ
    assert stamp1.config_hash != stamp2.config_hash
    assert stamp1.get_composite_hash() != stamp2.get_composite_hash()


def test_file_content_changes_detected(tmp_path):
    """Test that changes to input file content are detected."""
    file1 = tmp_path / "data.json"
    stamper = ReproStamper()
    
    # Create stamp with original content
    file1.write_text(json.dumps({"data": "original"}))
    stamp1 = stamper.create_stamp(input_files=[file1], random_seed=42)
    
    # Modify file and create new stamp
    file1.write_text(json.dumps({"data": "modified"}))
    stamp2 = stamper.create_stamp(input_files=[file1], random_seed=42)
    
    # File hashes should differ
    hash1 = stamp1.input_hashes[str(file1)]
    hash2 = stamp2.input_hashes[str(file1)]
    assert hash1 != hash2


# ============================================================================
# Validation Tests
# ============================================================================


def test_stamp_validation_success():
    """Test successful stamp validation."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    
    stamp = stamper.create_stamp(config_data=config, random_seed=42)
    valid, errors = stamper.validate_stamp(stamp, config_data=config)
    
    assert valid is True
    assert len(errors) == 0


def test_stamp_validation_config_mismatch():
    """Test stamp validation detects config changes."""
    config1 = create_synthetic_token_config(42)
    config2 = create_synthetic_token_config(43)
    stamper = ReproStamper()
    
    # Create stamp with config1
    stamp = stamper.create_stamp(config_data=config1, random_seed=42)
    
    # Validate against config2 (should fail)
    valid, errors = stamper.validate_stamp(stamp, config_data=config2)
    
    assert valid is False
    assert len(errors) > 0
    assert any("Config hash mismatch" in e for e in errors)


def test_stamp_validation_file_mismatch(tmp_path):
    """Test stamp validation detects file changes."""
    file1 = tmp_path / "data.json"
    file1.write_text(json.dumps({"data": "original"}))
    
    stamper = ReproStamper()
    stamp = stamper.create_stamp(input_files=[file1], random_seed=42)
    
    # Modify file
    file1.write_text(json.dumps({"data": "modified"}))
    
    # Validate (should fail)
    valid, errors = stamper.validate_stamp(stamp, input_files=[file1])
    
    assert valid is False
    assert len(errors) > 0
    assert any("Input file hash mismatch" in e for e in errors)


# ============================================================================
# Serialization Tests
# ============================================================================


def test_stamp_serialization_to_dict():
    """Test stamp can be serialized to dictionary."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    stamp = stamper.create_stamp(config_data=config, random_seed=42)
    
    stamp_dict = stamp.to_dict()
    
    assert isinstance(stamp_dict, dict)
    assert stamp_dict["timestamp"] == stamp.timestamp
    assert stamp_dict["stamp_version"] == stamp.stamp_version
    assert stamp_dict["random_seed"] == stamp.random_seed
    assert stamp_dict["config_hash"] == stamp.config_hash


def test_stamp_serialization_to_json():
    """Test stamp can be serialized to JSON."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    stamp = stamper.create_stamp(config_data=config, random_seed=42)
    
    json_str = stamp.to_json()
    
    assert isinstance(json_str, str)
    
    # Verify it's valid JSON
    parsed = json.loads(json_str)
    assert parsed["timestamp"] == stamp.timestamp
    assert parsed["random_seed"] == stamp.random_seed


def test_stamp_roundtrip_serialization():
    """Test stamp survives serialization and deserialization."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    original_stamp = stamper.create_stamp(config_data=config, random_seed=42)
    
    # Serialize to JSON
    json_str = original_stamp.to_json()
    
    # Deserialize
    stamp_dict = json.loads(json_str)
    recreated_stamp = ReproStamp(**stamp_dict)
    
    # Verify key fields match
    assert recreated_stamp.timestamp == original_stamp.timestamp
    assert recreated_stamp.stamp_version == original_stamp.stamp_version
    assert recreated_stamp.random_seed == original_stamp.random_seed
    assert recreated_stamp.config_hash == original_stamp.config_hash
    assert recreated_stamp.get_composite_hash() == original_stamp.get_composite_hash()


# ============================================================================
# Integration with Scan Results
# ============================================================================


def test_add_stamp_to_scan_output():
    """Test adding stamp to scan output."""
    scan_output = create_synthetic_scan_output(42)
    config = create_synthetic_token_config(42)
    
    # Add repro stamp
    stamped_output = add_repro_stamp_to_output(
        scan_output, config_data=config, random_seed=42
    )
    
    assert "repro_stamp" in stamped_output
    assert "repro_hash" in stamped_output
    assert isinstance(stamped_output["repro_stamp"], dict)
    assert isinstance(stamped_output["repro_hash"], str)
    assert len(stamped_output["repro_hash"]) == 16


def test_scan_reproducibility_with_stamps():
    """Test that identical scans produce identical stamps."""
    seed = 42
    config = create_synthetic_token_config(seed)
    
    # Run two "scans" with identical inputs
    output1 = create_synthetic_scan_output(seed)
    output2 = create_synthetic_scan_output(seed)
    
    # Add stamps
    stamped1 = add_repro_stamp_to_output(output1, config_data=config, random_seed=seed)
    stamped2 = add_repro_stamp_to_output(output2, config_data=config, random_seed=seed)
    
    # Config hashes should match (same seed = same config)
    stamp1 = stamped1["repro_stamp"]
    stamp2 = stamped2["repro_stamp"]
    
    assert stamp1["config_hash"] == stamp2["config_hash"]
    assert stamp1["random_seed"] == stamp2["random_seed"]


def test_different_scans_produce_different_stamps():
    """Test that different scans produce different stamps."""
    config1 = create_synthetic_token_config(42)
    config2 = create_synthetic_token_config(43)
    
    output1 = create_synthetic_scan_output(42)
    output2 = create_synthetic_scan_output(43)
    
    stamped1 = add_repro_stamp_to_output(output1, config_data=config1, random_seed=42)
    stamped2 = add_repro_stamp_to_output(output2, config_data=config2, random_seed=43)
    
    # Should have different stamps
    assert stamped1["repro_hash"] != stamped2["repro_hash"]


# ============================================================================
# End-to-End Reproducibility Test
# ============================================================================


def test_end_to_end_reproducibility_pipeline(tmp_path):
    """End-to-end test of complete reproducibility workflow.
    
    This test simulates the full reproducibility workflow:
    1. Create input data files
    2. Create configuration
    3. Run synthetic "scan"
    4. Create stamp
    5. Serialize everything
    6. Verify stamp validation
    7. Modify inputs
    8. Verify stamp detects changes
    """
    # Step 1: Create input data files
    data_file = tmp_path / "market_data.json"
    price_data = create_synthetic_price_data(seed=42, num_points=100)
    data_file.write_text(json.dumps(price_data))
    
    # Step 2: Create configuration
    config = create_synthetic_token_config(seed=42)
    
    # Step 3: Run synthetic scan
    scan_output = create_synthetic_scan_output(seed=42)
    
    # Step 4: Create stamp with all components
    stamper = ReproStamper(workspace_root=tmp_path)
    stamp = stamper.create_stamp(
        input_files=[data_file],
        config_data=config,
        random_seed=42,
    )
    
    # Step 5: Serialize stamp to file
    stamp_file = tmp_path / "repro_stamp.json"
    stamp_file.write_text(stamp.to_json())
    
    # Step 6: Verify stamp validation passes
    valid, errors = stamper.validate_stamp(
        stamp, input_files=[data_file], config_data=config
    )
    assert valid is True
    assert len(errors) == 0
    
    # Step 7: Modify inputs
    modified_data = create_synthetic_price_data(seed=43, num_points=100)
    data_file.write_text(json.dumps(modified_data))
    
    # Step 8: Verify stamp detects changes
    valid, errors = stamper.validate_stamp(
        stamp, input_files=[data_file], config_data=config
    )
    assert valid is False
    assert len(errors) > 0
    assert any("Input file hash mismatch" in e for e in errors)


# ============================================================================
# Git Integration Tests
# ============================================================================


def test_stamp_includes_git_info():
    """Test that stamp includes git information when available."""
    stamper = ReproStamper()
    stamp = stamper.create_stamp(random_seed=42)
    
    # These fields may be None if not in git repo, but should exist
    assert hasattr(stamp, "git_commit")
    assert hasattr(stamp, "git_branch")
    assert hasattr(stamp, "git_dirty")
    
    # If in a git repo, these should be populated
    if stamp.git_commit:
        assert isinstance(stamp.git_commit, str)
        assert len(stamp.git_commit) == 40  # SHA1 hash
    
    if stamp.git_branch:
        assert isinstance(stamp.git_branch, str)


# ============================================================================
# Environment Info Tests
# ============================================================================


def test_stamp_includes_environment_info():
    """Test that stamp includes environment information."""
    stamper = ReproStamper()
    stamp = stamper.create_stamp(random_seed=42)
    
    assert stamp.python_version is not None
    assert isinstance(stamp.python_version, str)
    assert "." in stamp.python_version  # Should be version like "3.13.0"
    
    assert stamp.platform is not None
    assert isinstance(stamp.platform, str)
    
    assert stamp.hostname is not None
    assert isinstance(stamp.hostname, str)


# ============================================================================
# Convenience Function Tests
# ============================================================================


def test_create_repro_stamp_convenience():
    """Test convenience function for creating stamps."""
    config = create_synthetic_token_config(42)
    stamp = create_repro_stamp(config_data=config, random_seed=42)
    
    assert isinstance(stamp, ReproStamp)
    assert stamp.random_seed == 42
    assert stamp.config_hash is not None


# ============================================================================
# Performance Tests
# ============================================================================


def test_stamp_creation_performance():
    """Test that stamp creation is reasonably fast.
    
    Note: Git operations can be slow on some systems (especially Windows),
    so we test with a smaller sample and more generous timeout.
    """
    import time
    
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    
    start_time = time.time()
    
    # Create 10 stamps (reduced from 100 due to git performance on Windows)
    for i in range(10):
        stamper.create_stamp(config_data=config, random_seed=i)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Should be able to create 10 stamps in under 60 seconds
    # (git operations can be slow, especially on Windows)
    assert elapsed < 60.0, f"Stamp creation too slow: {elapsed:.2f}s for 10 stamps"


def test_stamp_validation_performance():
    """Test that stamp validation is reasonably fast."""
    import time
    
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    stamp = stamper.create_stamp(config_data=config, random_seed=42)
    
    start_time = time.time()
    
    # Validate 100 times
    for _ in range(100):
        stamper.validate_stamp(stamp, config_data=config)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Should be able to validate 100 stamps in under 5 seconds
    assert elapsed < 5.0, f"Stamp validation too slow: {elapsed:.2f}s for 100 validations"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_stamp_with_missing_files():
    """Test stamp creation with missing input files."""
    stamper = ReproStamper()
    missing_file = Path("/nonexistent/file.json")
    
    stamp = stamper.create_stamp(input_files=[missing_file], random_seed=42)
    
    assert str(missing_file) in stamp.input_hashes
    assert stamp.input_hashes[str(missing_file)] == "not_found"


def test_stamp_with_empty_config():
    """Test stamp creation with empty configuration."""
    stamper = ReproStamper()
    stamp = stamper.create_stamp(config_data={}, random_seed=42)
    
    # Empty config should still produce a hash
    assert stamp.config_hash is not None
    # Hash of empty dict should be consistent
    assert len(stamp.config_hash) == 16


def test_stamp_with_no_seed():
    """Test stamp creation without random seed."""
    stamper = ReproStamper()
    stamp = stamper.create_stamp()
    
    assert stamp.random_seed is None
    assert stamp.timestamp is not None


def test_stamp_composite_hash_uniqueness():
    """Test that composite hashes are unique for different inputs."""
    stamper = ReproStamper()
    hashes = set()
    
    # Create 50 stamps with different seeds
    for i in range(50):
        stamp = stamper.create_stamp(random_seed=i)
        composite_hash = stamp.get_composite_hash()
        
        # Should not have collisions
        assert composite_hash not in hashes
        hashes.add(composite_hash)
    
    # Should have 50 unique hashes
    assert len(hashes) == 50


# ============================================================================
# Documentation Tests
# ============================================================================


def test_stamp_documentation_completeness():
    """Test that stamp includes comprehensive documentation fields."""
    config = create_synthetic_token_config(42)
    stamper = ReproStamper()
    stamp = stamper.create_stamp(config_data=config, random_seed=42)
    
    # Core fields
    assert stamp.timestamp is not None
    assert stamp.stamp_version is not None
    
    # Code version fields
    assert hasattr(stamp, "git_commit")
    assert hasattr(stamp, "git_branch")
    assert hasattr(stamp, "git_dirty")
    assert hasattr(stamp, "code_hash")
    
    # Input fields
    assert hasattr(stamp, "input_hashes")
    assert hasattr(stamp, "config_hash")
    
    # Environment fields
    assert stamp.python_version is not None
    assert stamp.platform is not None
    assert stamp.hostname is not None
    
    # Execution fields
    assert hasattr(stamp, "random_seed")
    assert hasattr(stamp, "dependency_hashes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
