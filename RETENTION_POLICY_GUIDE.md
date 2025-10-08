# Artifact Retention & Classification Policy

## Overview

The artifact retention system provides automated lifecycle management for all tracked artifacts in the Hidden-Gem Scanner. It classifies artifacts by importance, manages transitions through storage tiers, and automatically cleans up expired artifacts.

## Key Features

### 🏷️ Automatic Classification
- 5 classification levels (CRITICAL → EPHEMERAL)
- Rule-based classification using artifact type, tags, and attributes
- Customizable classification rules

### ⏱️ Lifecycle Management
- 4 storage tiers (HOT → WARM → COLD → DELETED)
- Automatic tier transitions based on age
- Configurable retention periods per classification

### 🧹 Automated Cleanup
- Periodic lifecycle management runs
- Automatic deletion of expired artifacts
- Garbage collection integration

### 📊 Monitoring & Reporting
- Lifecycle statistics by classification
- Storage tier distribution
- Export reports in JSON format

## Classification Levels

### CRITICAL (Indefinite Retention)
**Purpose:** Production-critical results and regulatory data

**Retention Policy:**
- Hot Storage: 90 days
- Warm Storage: 365 days
- Cold Storage: Indefinite
- Archive: Yes

**Auto-Classification Rules:**
- GemScore results with score > 90
- Artifacts tagged with "production"
- Model artifacts (trained models)

**Example:**
```python
# High-scoring gem identified in production
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.GEM_SCORE,
    name="PEPE Analysis",
    data={"score": 95, "confidence": 0.85},
    tags={"production"}
)
# Classified as CRITICAL → kept indefinitely
```

### IMPORTANT (2-Year Retention)
**Purpose:** Analysis results, reports, significant findings

**Retention Policy:**
- Hot Storage: 30 days
- Warm Storage: 180 days (6 months)
- Cold Storage: 520 days (~14 months)
- **Total:** 730 days (~2 years)
- Archive: Yes

**Auto-Classification Rules:**
- GemScore results (score ≤ 90)
- Contract reports
- Summary reports
- Analysis outputs

**Example:**
```python
# Regular analysis report
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.REPORT,
    name="Weekly Analysis",
    data={"tokens": 50, "findings": [...]}
)
# Classified as IMPORTANT → kept for 2 years
```

### STANDARD (6-Month Retention)
**Purpose:** Production data, operational logs

**Retention Policy:**
- Hot Storage: 7 days
- Warm Storage: 60 days
- Cold Storage: 113 days
- **Total:** 180 days (~6 months)
- Archive: Yes

**Auto-Classification Rules:**
- Production market snapshots
- Production price series
- Backtest results

**Example:**
```python
# Production market data
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.MARKET_SNAPSHOT,
    name="ETH Market Data",
    data={...},
    tags={"production"}
)
# Classified as STANDARD → kept for 6 months
```

### TRANSIENT (30-Day Retention)
**Purpose:** Intermediate calculations, feature vectors

**Retention Policy:**
- Hot Storage: 1 day
- Warm Storage: 7 days
- Cold Storage: 22 days
- **Total:** 30 days
- Archive: No

**Auto-Classification Rules:**
- Feature vectors
- Non-production market snapshots
- Non-production price series

**Example:**
```python
# Computed features
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.FEATURE_VECTOR,
    name="Token Features",
    data={"features": [...]}
)
# Classified as TRANSIENT → kept for 30 days
```

### EPHEMERAL (1-Day Retention)
**Purpose:** Temporary data, debugging artifacts

**Retention Policy:**
- Hot Storage: 0 days
- Warm Storage: 0 days
- Cold Storage: 1 day
- **Total:** 1 day
- Archive: No

**Auto-Classification Rules:**
- Raw data
- Temporary artifacts
- Debug outputs

**Example:**
```python
# Temporary debug data
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.RAW_DATA,
    name="Debug Snapshot",
    data={...},
    tags={"temporary"}
)
# Classified as EPHEMERAL → deleted after 1 day
```

## Storage Tiers

### HOT Storage
- **Access:** Immediate, in-memory
- **Use Case:** Active processing, recent results
- **Transition:** Age exceeds hot_retention_days

### WARM Storage
- **Access:** Fast, local disk
- **Use Case:** Recent history, occasional access
- **Transition:** Age exceeds (hot + warm) retention days

### COLD Storage
- **Access:** Slower, archived
- **Use Case:** Long-term retention, compliance
- **Transition:** Age exceeds total retention days

### DELETED
- **Access:** None (removed)
- **Use Case:** Expired artifacts
- **Cleanup:** Periodic garbage collection

## Usage

### Basic Lifecycle Management

```python
from src.core.provenance import get_provenance_tracker
from src.core.artifact_retention import get_policy_manager

# Get singletons
tracker = get_provenance_tracker()
manager = get_policy_manager()

# Track artifact
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.GEM_SCORE,
    name="Analysis Result",
    data={"score": 75}
)

# Register for lifecycle management
record = tracker.get_record(artifact_id)
manager.register_artifact(artifact_id, record)

# Get classification
lifecycle = manager.artifact_lifecycles[artifact_id]
print(f"Classification: {lifecycle.classification}")
print(f"Current tier: {lifecycle.current_tier}")
print(f"Age: {lifecycle.age_days()} days")
```

### Automated Lifecycle Management

```python
# Run lifecycle management (typically in background job)
stats = manager.run_lifecycle_management(tracker)

print(f"Total artifacts: {stats['total_artifacts']}")
print(f"Transitioned to WARM: {stats['transitioned_to_warm']}")
print(f"Transitioned to COLD: {stats['transitioned_to_cold']}")
print(f"Marked for deletion: {stats['marked_for_deletion']}")

# Check classification breakdown
for classification, breakdown in stats['by_classification'].items():
    print(f"{classification}:")
    print(f"  Total: {breakdown['count']}")
    print(f"  HOT: {breakdown['hot']}, WARM: {breakdown['warm']}")
    print(f"  COLD: {breakdown['cold']}, DELETED: {breakdown['deleted']}")
```

### Cleanup Operations

```python
# Get artifacts ready for deletion
to_delete = manager.get_artifacts_for_deletion()
print(f"Artifacts to delete: {len(to_delete)}")

# Perform cleanup
deleted_count = manager.cleanup_deleted_artifacts(tracker)
print(f"Deleted {deleted_count} artifacts")
```

### Custom Classification

```python
# Override automatic classification
manager.register_artifact(
    artifact_id,
    record,
    classification=ArtifactClassification.CRITICAL  # Force CRITICAL
)
```

### Export Lifecycle Report

```python
# Generate JSON report
report_json = manager.export_lifecycle_report()
print(report_json)

# Save to file
report_json = manager.export_lifecycle_report(
    output_path=Path("artifacts/lifecycle_report.json")
)
```

## Configuration

### Custom Retention Policies

```python
from src.core.artifact_retention import RetentionPolicy

# Create custom policy
custom_policy = RetentionPolicy(
    hot_retention_days=14,      # 2 weeks in HOT
    warm_retention_days=90,     # 3 months in WARM
    cold_retention_days=180,    # 6 months in COLD
    archive_enabled=True
)

# Update policy for classification
manager.retention_policies[ArtifactClassification.STANDARD] = custom_policy
```

### Custom Classification Rules

```python
from src.core.artifact_retention import ClassificationRule

# Create custom rule
high_value_rule = ClassificationRule(
    name="high_value_tokens",
    classification=ArtifactClassification.CRITICAL,
    condition=lambda record: (
        record.artifact.artifact_type == ArtifactType.GEM_SCORE
        and record.artifact.data.get("score", 0) > 80
        and "dex" in record.artifact.tags
    )
)

# Add rule (higher priority = checked first)
manager.classification_rules.insert(0, high_value_rule)
```

## Scheduled Jobs

### Cron-Style Scheduling

```python
import schedule
import time

def run_lifecycle_job():
    """Run lifecycle management and cleanup."""
    tracker = get_provenance_tracker()
    manager = get_policy_manager()
    
    # Run lifecycle management
    stats = manager.run_lifecycle_management(tracker)
    print(f"Lifecycle run: {stats['total_artifacts']} artifacts")
    
    # Cleanup if any deletions
    if stats['marked_for_deletion'] > 0:
        deleted = manager.cleanup_deleted_artifacts(tracker)
        print(f"Cleaned up {deleted} artifacts")

# Schedule daily at 3 AM
schedule.every().day.at("03:00").do(run_lifecycle_job)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

### Background Thread

```python
import threading
import time

def lifecycle_worker():
    """Background worker for lifecycle management."""
    while True:
        try:
            run_lifecycle_job()
        except Exception as e:
            print(f"Lifecycle job error: {e}")
        
        # Run every 6 hours
        time.sleep(6 * 60 * 60)

# Start background thread
worker = threading.Thread(target=lifecycle_worker, daemon=True)
worker.start()
```

## Monitoring

### Access Tracking

```python
# Record artifact access
manager.record_access(artifact_id)

# Check access statistics
lifecycle = manager.artifact_lifecycles[artifact_id]
print(f"Access count: {lifecycle.access_count}")
print(f"Last accessed: {lifecycle.last_accessed}")
```

### Tier Transition Checks

```python
# Check if transition is due
new_tier = manager.get_tier_transition_due(artifact_id)
if new_tier:
    print(f"Transition due: {lifecycle.current_tier} → {new_tier}")
    
    # Perform transition
    manager.transition_artifact(artifact_id, new_tier)
```

### Statistics

```python
# Get lifecycle statistics
stats = {
    "by_tier": {"hot": 0, "warm": 0, "cold": 0, "deleted": 0},
    "by_classification": {}
}

for lifecycle in manager.artifact_lifecycles.values():
    # Count by tier
    stats["by_tier"][lifecycle.current_tier.value] += 1
    
    # Count by classification
    classification = lifecycle.classification.value
    if classification not in stats["by_classification"]:
        stats["by_classification"][classification] = 0
    stats["by_classification"][classification] += 1

print(json.dumps(stats, indent=2))
```

## Integration with Observability

### Prometheus Metrics

```python
from prometheus_client import Gauge, Counter

# Define metrics
artifact_count = Gauge(
    'artifact_count_by_tier',
    'Number of artifacts per storage tier',
    ['tier']
)

transitions = Counter(
    'artifact_tier_transitions',
    'Number of tier transitions',
    ['from_tier', 'to_tier']
)

deletions = Counter(
    'artifact_deletions',
    'Number of artifacts deleted',
    ['classification']
)

# Update metrics after lifecycle run
def update_metrics():
    stats = manager.run_lifecycle_management(tracker)
    
    # Update tier counts
    for tier in ['hot', 'warm', 'cold', 'deleted']:
        count = sum(
            1 for lc in manager.artifact_lifecycles.values()
            if lc.current_tier.value == tier
        )
        artifact_count.labels(tier=tier).set(count)
    
    # Update transition counts
    transitions.labels(from_tier='hot', to_tier='warm').inc(
        stats['transitioned_to_warm']
    )
    transitions.labels(from_tier='warm', to_tier='cold').inc(
        stats['transitioned_to_cold']
    )
```

## Best Practices

### 1. Regular Lifecycle Runs
Run lifecycle management at least daily to prevent unbounded growth:
```python
# Daily at 3 AM
schedule.every().day.at("03:00").do(run_lifecycle_job)
```

### 2. Monitor Storage Usage
Track artifact counts and sizes per tier:
```python
total_size = sum(
    len(json.dumps(tracker.get_record(aid).to_dict()))
    for aid in manager.artifact_lifecycles
)
print(f"Total storage: {total_size / 1024 / 1024:.2f} MB")
```

### 3. Backup Before Cleanup
Always backup artifacts before deletion:
```python
# Export before cleanup
for artifact_id in manager.get_artifacts_for_deletion():
    record = tracker.get_record(artifact_id)
    # Save to backup location
    backup_artifact(record)

# Then cleanup
manager.cleanup_deleted_artifacts(tracker)
```

### 4. Custom Rules for Business Logic
Add domain-specific classification rules:
```python
# Keep high-liquidity tokens longer
high_liquidity_rule = ClassificationRule(
    name="high_liquidity",
    classification=ArtifactClassification.IMPORTANT,
    condition=lambda r: r.artifact.data.get("liquidity_usd", 0) > 1_000_000
)
manager.classification_rules.insert(0, high_liquidity_rule)
```

### 5. Test Retention Policies
Always test custom policies with synthetic data:
```python
# Create test artifact with backdated timestamp
artifact_id = tracker.register_artifact(...)
record = tracker.get_record(artifact_id)
record.artifact.created_at = datetime.now() - timedelta(days=100)

# Test lifecycle management
manager.register_artifact(artifact_id, record)
new_tier = manager.get_tier_transition_due(artifact_id)
assert new_tier == StorageTier.DELETED  # Should be deleted
```

## Troubleshooting

### Issue: Artifacts Not Transitioning
**Cause:** Retention periods too long or lifecycle management not running

**Solution:**
```python
# Check artifact age
lifecycle = manager.artifact_lifecycles[artifact_id]
print(f"Age: {lifecycle.age_days()} days")
print(f"Days in tier: {lifecycle.days_in_tier()} days")

# Check policy
policy = manager.retention_policies[lifecycle.classification]
print(f"Hot retention: {policy.hot_retention_days} days")

# Manually run lifecycle management
stats = manager.run_lifecycle_management(tracker)
```

### Issue: Too Many Artifacts Being Deleted
**Cause:** Retention periods too short

**Solution:**
```python
# Increase retention periods
policy = manager.retention_policies[ArtifactClassification.STANDARD]
policy.hot_retention_days = 14  # Increase from 7
policy.warm_retention_days = 90  # Increase from 60
policy.cold_retention_days = 180  # Increase from 113
```

### Issue: Memory Usage Growing
**Cause:** Too many artifacts in HOT tier

**Solution:**
```python
# Force transition to WARM for old artifacts
for artifact_id, lifecycle in manager.artifact_lifecycles.items():
    if lifecycle.current_tier == StorageTier.HOT and lifecycle.age_days() > 3:
        manager.transition_artifact(artifact_id, StorageTier.WARM)
```

## Testing

Run the complete test suite:
```powershell
python test_artifact_retention.py
```

Expected output:
```
============================================================
RETENTION POLICY TEST SUITE
============================================================

Testing Artifact Classification - ✓ PASSED
Testing Retention Policies - ✓ PASSED
Testing Lifecycle Management - ✓ PASSED
Testing Automated Lifecycle - ✓ PASSED
Testing Export and Cleanup - ✓ PASSED

RESULTS: 5 passed, 0 failed
🎉 All tests passed successfully!
```

## Related Documentation

- [Provenance & Glossary Guide](PROVENANCE_GLOSSARY_GUIDE.md) - Artifact tracking and documentation
- [Testing Summary](TESTING_SUMMARY.md) - Complete test coverage overview
- [Observability Quick Reference](OBSERVABILITY_QUICK_REF.md) - Monitoring integration
- [Architecture Overview](ARCHITECTURE.md) - System design

## Summary

The artifact retention system provides:
- ✅ Automatic classification (5 levels)
- ✅ Lifecycle management (4 tiers)
- ✅ Configurable retention periods
- ✅ Automated cleanup
- ✅ Monitoring and reporting
- ✅ Full integration with provenance tracker

This ensures efficient storage management while preserving critical data for compliance and analysis.
