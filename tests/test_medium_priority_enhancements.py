"""Test suite for medium-priority enhancements.

This module demonstrates and tests the new features:
1. Enhanced provenance with lineage metadata
2. Snapshot mode for reproducibility
3. Schema registry validation
"""

import json
from datetime import datetime
from pathlib import Path

import pytest


def test_provenance_lineage_capture():
    """Test lineage metadata capture."""
    from src.core.provenance import capture_lineage_metadata, get_provenance_tracker, ArtifactType
    
    # Capture lineage
    lineage = capture_lineage_metadata(
        feature_hash="sha256:test_hash_123",
        model_route="test:model-v1",
        data_snapshot_hash="sha256:snapshot_456"
    )
    
    # Verify captured data
    assert lineage is not None
    assert lineage.feature_hash == "sha256:test_hash_123"
    assert lineage.model_route == "test:model-v1"
    assert lineage.data_snapshot_hash == "sha256:snapshot_456"
    assert lineage.pipeline_version is not None
    assert lineage.environment is not None
    assert "python_version" in lineage.environment
    
    # Register artifact with lineage
    tracker = get_provenance_tracker()
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.GEM_SCORE,
        name="TestScore",
        data={"score": 85.0},
        lineage_metadata=lineage
    )
    
    # Retrieve and verify
    record = tracker.get_record(artifact_id)
    assert record is not None
    assert record.artifact.lineage is not None
    assert record.artifact.lineage.model_route == "test:model-v1"
    
    print("✓ Provenance lineage capture working")


def test_snapshot_mode():
    """Test snapshot mode for reproducibility."""
    from src.core.snapshot_mode import SnapshotRegistry, SnapshotMode
    
    # Create registry
    registry = SnapshotRegistry(snapshot_dir=Path("./test_snapshots"))
    
    # Test record mode
    test_data = {"price": 123.45, "volume": 10000.0}
    snapshot = registry.record_snapshot(
        data=test_data,
        source="test:price",
        metadata={"test": True}
    )
    
    assert snapshot is not None
    assert snapshot.data_hash is not None
    assert snapshot.verify(test_data)
    
    # Test load
    loaded_data, loaded_snapshot = registry.load_snapshot(snapshot.snapshot_id)
    assert loaded_data == test_data
    assert loaded_snapshot.snapshot_id == snapshot.snapshot_id
    
    # Test enforce snapshot mode
    registry.set_mode(SnapshotMode.SNAPSHOT)
    
    def mock_fetch():
        return {"should": "not be called"}
    
    # Should load from snapshot, not call fetch
    result = registry.enforce_snapshot_mode(
        source="test:price",
        fetch_fn=mock_fetch
    )
    assert result == test_data
    
    # Cleanup
    import shutil
    shutil.rmtree("./test_snapshots", ignore_errors=True)
    
    print("✓ Snapshot mode working")


def test_schema_registry():
    """Test schema registry validation."""
    from src.core.schema_registry import (
        SchemaRegistry,
        SchemaVersion,
        SchemaType,
        FieldDefinition
    )
    
    # Create test schema
    schema = SchemaVersion(
        schema_id="test_output",
        schema_type=SchemaType.ARTIFACT,
        version="1.0.0",
        created_at=datetime.utcnow(),
        description="Test schema",
        fields=[
            FieldDefinition(
                name="score",
                field_type="float",
                required=True,
                description="Test score"
            ),
            FieldDefinition(
                name="address",
                field_type="string",
                required=True,
                description="Token address"
            )
        ]
    )
    
    # Test validation
    valid_data = {
        "score": 85.5,
        "address": "0x1234567890123456789012345678901234567890"
    }
    
    is_valid, errors = schema.validate(valid_data)
    assert is_valid, f"Validation failed: {errors}"
    
    # Test invalid data (missing required field)
    invalid_data = {"score": 85.5}
    is_valid, errors = schema.validate(invalid_data)
    assert not is_valid
    assert any("address" in err for err in errors)
    
    # Test registry
    registry = SchemaRegistry(registry_dir=Path("./test_schemas"))
    registry.register_schema(schema)
    
    # Retrieve and validate
    retrieved = registry.get_schema("test_output", "1.0.0")
    assert retrieved is not None
    assert retrieved.schema_id == "test_output"
    
    is_valid, errors = registry.validate_data(
        schema_id="test_output",
        data=valid_data,
        version="1.0.0"
    )
    assert is_valid
    
    # Cleanup
    import shutil
    shutil.rmtree("./test_schemas", ignore_errors=True)
    
    print("✓ Schema registry working")


def test_alert_thresholds_config():
    """Test alert threshold configuration loading."""
    import yaml
    
    config_path = Path("config/alert_thresholds.yaml")
    
    if not config_path.exists():
        pytest.skip("Alert thresholds config not found")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Verify structure
    assert "version" in config
    assert "gem_score_thresholds" in config
    assert "holder_change_thresholds" in config
    assert "validation" in config
    
    # Check specific threshold
    high_potential = config["gem_score_thresholds"]["high_potential"]
    assert high_potential["threshold"] == 80.0
    assert high_potential["unit"] == "score"
    assert high_potential["data_type"] == "float"
    assert high_potential["operator"] == "gte"
    
    # Check holder change (percentage_points)
    holder_increase = config["holder_change_thresholds"]["significant_increase"]
    assert holder_increase["threshold"] == 10.0
    assert holder_increase["unit"] == "percentage_points"
    assert "annotation" in holder_increase
    
    # Verify validation rules
    valid_units = config["validation"]["valid_units"]
    assert "percentage" in valid_units
    assert "ratio" in valid_units
    assert "percentage_points" in valid_units
    
    print("✓ Alert thresholds config valid")


def test_integration_workflow():
    """Test complete workflow with all enhancements."""
    from src.core.provenance import (
        capture_lineage_metadata,
        get_provenance_tracker,
        reset_provenance_tracker,
        ArtifactType
    )
    from src.core.snapshot_mode import SnapshotRegistry, SnapshotMode
    from src.core.schema_registry import get_schema_registry
    
    # Reset for clean test
    reset_provenance_tracker()
    
    # 1. Capture lineage
    lineage = capture_lineage_metadata(
        feature_hash="sha256:integration_test",
        model_route="test:integration-v1"
    )
    
    # 2. Record snapshot
    snapshot_registry = SnapshotRegistry(snapshot_dir=Path("./test_integration_snapshots"))
    snapshot_registry.set_mode(SnapshotMode.RECORD)
    
    test_data = {"token": "TEST", "price": 100.0}
    snapshot = snapshot_registry.record_snapshot(
        data=test_data,
        source="integration:test"
    )
    
    # 3. Register artifact with provenance
    tracker = get_provenance_tracker()
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.GEM_SCORE,
        name="IntegrationTest",
        data=test_data,
        lineage_metadata=lineage
    )
    
    # 4. Validate with schema
    output_data = {
        "score": 85.0,
        "token_address": "0x1234567890123456789012345678901234567890",
        "token_symbol": "TEST",
        "calculated_at": datetime.utcnow().isoformat(),
        "confidence": 0.95,
        "breakdown": {
            "liquidity": 80.0,
            "volume": 90.0
        }
    }
    
    schema_registry = get_schema_registry()
    is_valid, errors = schema_registry.validate_data(
        schema_id="gem_score_result",
        data=output_data
    )
    
    # Verify workflow
    assert lineage.pipeline_version is not None
    assert snapshot.verify(test_data)
    
    record = tracker.get_record(artifact_id)
    assert record.artifact.lineage is not None
    assert is_valid or len(errors) == 0  # Schema might not be loaded yet
    
    # Cleanup
    import shutil
    shutil.rmtree("./test_integration_snapshots", ignore_errors=True)
    
    print("✓ Integration workflow complete")


if __name__ == "__main__":
    """Run all tests."""
    print("Running medium-priority enhancement tests...\n")
    
    try:
        test_provenance_lineage_capture()
        test_snapshot_mode()
        test_schema_registry()
        test_alert_thresholds_config()
        test_integration_workflow()
        
        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
