"""Tests for artifact retention and classification policies."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))

from src.core.provenance import (
    ArtifactType,
    get_provenance_tracker,
    reset_provenance_tracker,
)
from src.core.artifact_retention import (
    ArtifactClassification,
    StorageTier,
    RetentionPolicy,
    ClassificationRule,
    get_policy_manager,
    reset_policy_manager,
)
from src.core.provenance_tracking import track_market_snapshot
from src.core.features import MarketSnapshot


def test_classification():
    """Test artifact classification."""
    print("=" * 60)
    print("Testing Artifact Classification")
    print("=" * 60)
    
    reset_policy_manager()
    reset_provenance_tracker()
    
    manager = get_policy_manager()
    tracker = get_provenance_tracker()
    
    # Test GemScore classification (should be IMPORTANT)
    score_id = tracker.register_artifact(
        artifact_type=ArtifactType.GEM_SCORE,
        name="Test GemScore",
        data={"score": 75},
        tags={"test"}
    )
    
    record = tracker.get_record(score_id)
    classification = manager.classify_artifact(record)
    assert classification == ArtifactClassification.IMPORTANT
    print("✓ GemScore classified as IMPORTANT")
    
    # Test Report classification (should be IMPORTANT)
    report_id = tracker.register_artifact(
        artifact_type=ArtifactType.REPORT,
        name="Test Report",
        data={"tokens": 10},
        tags={"test"}
    )
    
    record = tracker.get_record(report_id)
    classification = manager.classify_artifact(record)
    assert classification == ArtifactClassification.IMPORTANT
    print("✓ Report classified as IMPORTANT")
    
    # Test production data (should be STANDARD)
    snapshot_id = tracker.register_artifact(
        artifact_type=ArtifactType.MARKET_SNAPSHOT,
        name="Test Snapshot",
        data={},
        tags={"production"}
    )
    
    record = tracker.get_record(snapshot_id)
    classification = manager.classify_artifact(record)
    assert classification == ArtifactClassification.STANDARD
    print("✓ Production snapshot classified as STANDARD")
    
    # Test feature vector (should be TRANSIENT)
    feature_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name="Test Features",
        data={},
        tags={"test"}
    )
    
    record = tracker.get_record(feature_id)
    classification = manager.classify_artifact(record)
    assert classification == ArtifactClassification.TRANSIENT
    print("✓ Feature vector classified as TRANSIENT")
    
    print("\n✅ All classification tests passed!\n")
    return True


def test_retention_policies():
    """Test retention policies."""
    print("=" * 60)
    print("Testing Retention Policies")
    print("=" * 60)
    
    manager = get_policy_manager()
    
    # Test CRITICAL policy
    critical_policy = manager.retention_policies[ArtifactClassification.CRITICAL]
    assert critical_policy.hot_retention_days == 90
    assert critical_policy.cold_retention_days is None  # Indefinite
    print("✓ CRITICAL policy: indefinite retention")
    
    # Test IMPORTANT policy
    important_policy = manager.retention_policies[ArtifactClassification.IMPORTANT]
    assert important_policy.hot_retention_days == 30
    assert important_policy.get_total_retention_days() == 730  # ~2 years
    print(f"✓ IMPORTANT policy: {important_policy.get_total_retention_days()} days total")
    
    # Test STANDARD policy
    standard_policy = manager.retention_policies[ArtifactClassification.STANDARD]
    assert standard_policy.hot_retention_days == 7
    assert standard_policy.get_total_retention_days() == 180  # ~6 months
    print(f"✓ STANDARD policy: {standard_policy.get_total_retention_days()} days total")
    
    # Test TRANSIENT policy
    transient_policy = manager.retention_policies[ArtifactClassification.TRANSIENT]
    assert transient_policy.hot_retention_days == 1
    assert transient_policy.get_total_retention_days() == 30  # 30 days
    assert not transient_policy.archive_enabled
    print(f"✓ TRANSIENT policy: {transient_policy.get_total_retention_days()} days, no archival")
    
    # Test EPHEMERAL policy
    ephemeral_policy = manager.retention_policies[ArtifactClassification.EPHEMERAL]
    assert ephemeral_policy.get_total_retention_days() == 1  # 1 day
    assert not ephemeral_policy.archive_enabled
    print(f"✓ EPHEMERAL policy: {ephemeral_policy.get_total_retention_days()} day")
    
    print("\n✅ All retention policy tests passed!\n")
    return True


def test_lifecycle_management():
    """Test artifact lifecycle management."""
    print("=" * 60)
    print("Testing Lifecycle Management")
    print("=" * 60)
    
    reset_policy_manager()
    reset_provenance_tracker()
    
    manager = get_policy_manager()
    tracker = get_provenance_tracker()
    
    # Create artifact with old timestamp
    now = datetime.now()
    old_date = now - timedelta(days=10)
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name="Old Feature Vector",
        data={},
        tags={"test"}
    )
    
    record = tracker.get_record(artifact_id)
    record.artifact.created_at = old_date  # Simulate old artifact
    
    # Register for lifecycle management
    manager.register_artifact(artifact_id, record)
    
    lifecycle = manager.artifact_lifecycles[artifact_id]
    lifecycle.created_at = old_date  # Update lifecycle timestamp too
    assert lifecycle.current_tier == StorageTier.HOT
    assert lifecycle.classification == ArtifactClassification.TRANSIENT
    print(f"✓ Artifact registered: {lifecycle.classification.value}, {lifecycle.current_tier.value}")
    
    # Check for tier transition (TRANSIENT: 1d hot, 7d warm, 22d cold)
    new_tier = manager.get_tier_transition_due(artifact_id)
    assert new_tier == StorageTier.COLD  # Should transition to cold after 8 days (1+7)
    print(f"✓ Tier transition due: HOT -> {new_tier.value if new_tier else 'NONE'}")
    
    # Perform transition
    manager.transition_artifact(artifact_id, new_tier)
    assert lifecycle.current_tier == new_tier
    assert lifecycle.moved_to_cold is not None
    print(f"✓ Transitioned to {new_tier.value}")
    
    # Test access tracking
    manager.record_access(artifact_id)
    assert lifecycle.access_count == 1
    assert lifecycle.last_accessed is not None
    print(f"✓ Access recorded")
    
    print("\n✅ All lifecycle management tests passed!\n")
    return True


def test_lifecycle_automation():
    """Test automated lifecycle management."""
    print("=" * 60)
    print("Testing Automated Lifecycle Management")
    print("=" * 60)
    
    reset_policy_manager()
    reset_provenance_tracker()
    
    manager = get_policy_manager()
    tracker = get_provenance_tracker()
    
    # Create artifacts with different ages and classifications
    now = datetime.now(timezone.utc)
    
    # Recent artifact (stays in HOT)
    recent_id = tracker.register_artifact(
        artifact_type=ArtifactType.GEM_SCORE,
        name="Recent Score",
        data={},
    )
    record = tracker.get_record(recent_id)
    manager.register_artifact(recent_id, record)
    
    # Old artifact (should move to WARM)
    old_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name="Old Features",
        data={},
    )
    record = tracker.get_record(old_id)
    record.artifact.created_at = now - timedelta(days=5)
    manager.register_artifact(old_id, record)
    
    # Very old artifact (should move to COLD or DELETE)
    very_old_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name="Very Old Features",
        data={},
    )
    record = tracker.get_record(very_old_id)
    record.artifact.created_at = now - timedelta(days=20)
    manager.register_artifact(very_old_id, record)
    
    # Run lifecycle management
    stats = manager.run_lifecycle_management(tracker)
    
    print(f"✓ Total artifacts: {stats['total_artifacts']}")
    print(f"✓ Transitioned to WARM: {stats['transitioned_to_warm']}")
    print(f"✓ Transitioned to COLD: {stats['transitioned_to_cold']}")
    print(f"✓ Marked for deletion: {stats['marked_for_deletion']}")
    
    assert stats['total_artifacts'] == 3
    assert stats['transitioned_to_warm'] + stats['transitioned_to_cold'] + stats['marked_for_deletion'] > 0
    
    # Check classification breakdown
    print("\n✓ Classification breakdown:")
    for classification, breakdown in stats['by_classification'].items():
        print(f"  - {classification}: {breakdown['count']} total, "
              f"{breakdown['hot']} hot, {breakdown['warm']} warm, "
              f"{breakdown['cold']} cold, {breakdown['deleted']} deleted")
    
    print("\n✅ All automation tests passed!\n")
    return True


def test_export_and_cleanup():
    """Test lifecycle reporting and cleanup."""
    print("=" * 60)
    print("Testing Export and Cleanup")
    print("=" * 60)
    
    reset_policy_manager()
    reset_provenance_tracker()
    
    manager = get_policy_manager()
    tracker = get_provenance_tracker()
    
    # Create some artifacts
    for i in range(5):
        artifact_id = tracker.register_artifact(
            artifact_type=ArtifactType.FEATURE_VECTOR,
            name=f"Feature {i}",
            data={},
        )
        record = tracker.get_record(artifact_id)
        manager.register_artifact(artifact_id, record)
    
    # Export report
    report_json = manager.export_lifecycle_report()
    assert "generated_at" in report_json
    assert "total_artifacts" in report_json
    assert "policies" in report_json
    print(f"✓ Lifecycle report exported: {len(report_json)} chars")
    
    # Mark some for deletion
    very_old_id = tracker.register_artifact(
        artifact_type=ArtifactType.FEATURE_VECTOR,
        name="To Delete",
        data={},
    )
    record = tracker.get_record(very_old_id)
    record.artifact.created_at = datetime.now(timezone.utc) - timedelta(days=100)
    manager.register_artifact(very_old_id, record)
    manager.run_lifecycle_management(tracker)
    
    # Get deletion list
    to_delete = manager.get_artifacts_for_deletion()
    print(f"✓ Artifacts marked for deletion: {len(to_delete)}")
    
    # Perform cleanup
    deleted_count = manager.cleanup_deleted_artifacts(tracker)
    print(f"✓ Artifacts deleted: {deleted_count}")
    
    # Verify deletion
    for artifact_id in to_delete:
        assert artifact_id not in tracker.records
        assert artifact_id not in manager.artifact_lifecycles
    print(f"✓ Cleanup verified")
    
    print("\n✅ All export and cleanup tests passed!\n")
    return True


def main():
    """Run all retention policy tests."""
    print("\n" + "=" * 60)
    print("RETENTION POLICY TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("Artifact Classification", test_classification),
        ("Retention Policies", test_retention_policies),
        ("Lifecycle Management", test_lifecycle_management),
        ("Automated Lifecycle", test_lifecycle_automation),
        ("Export and Cleanup", test_export_and_cleanup),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 All tests passed successfully!\n")
    else:
        print(f"\n⚠️ {failed} test(s) failed\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
