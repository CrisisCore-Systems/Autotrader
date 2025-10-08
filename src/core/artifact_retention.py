"""Artifact retention and classification policies.

This module provides configurable policies for artifact lifecycle management:
1. Classification - Categorize artifacts by importance and type
2. Retention - Define how long to keep artifacts
3. Archival - Move old artifacts to cold storage
4. Cleanup - Remove expired artifacts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Callable
import json
from pathlib import Path

from src.core.provenance import (
    ProvenanceTracker,
    ProvenanceRecord,
    ArtifactType,
    get_provenance_tracker,
)


class ArtifactClassification(Enum):
    """Classification levels for artifacts."""
    
    CRITICAL = "critical"       # Production results, regulatory data
    IMPORTANT = "important"     # Analysis results, reports
    STANDARD = "standard"       # Intermediate computations
    TRANSIENT = "transient"     # Temporary, can be recomputed
    EPHEMERAL = "ephemeral"     # Very short-lived, immediate use only


class StorageTier(Enum):
    """Storage tiers for artifact lifecycle."""
    
    HOT = "hot"           # Frequently accessed, fast storage
    WARM = "warm"         # Occasional access, standard storage
    COLD = "cold"         # Rare access, archival storage
    DELETED = "deleted"   # Marked for deletion


@dataclass
class RetentionPolicy:
    """Defines retention rules for artifacts."""
    
    classification: ArtifactClassification
    hot_retention_days: int                    # Days to keep in hot storage
    warm_retention_days: int                   # Days to keep in warm storage
    cold_retention_days: Optional[int] = None  # Days in cold (None = indefinite)
    archive_enabled: bool = True               # Whether to archive or delete directly
    
    def get_total_retention_days(self) -> Optional[int]:
        """Get total retention period in days."""
        if self.cold_retention_days is None:
            return None  # Indefinite
        return self.hot_retention_days + self.warm_retention_days + self.cold_retention_days


@dataclass
class ClassificationRule:
    """Rule for classifying artifacts."""
    
    name: str
    artifact_types: Set[ArtifactType]
    classification: ArtifactClassification
    conditions: Optional[Dict[str, any]] = None  # Additional conditions
    priority: int = 0  # Higher priority rules are evaluated first
    
    def matches(self, record: ProvenanceRecord) -> bool:
        """Check if this rule matches the given artifact."""
        # Check artifact type
        if record.artifact.artifact_type not in self.artifact_types:
            return False
        
        # Check additional conditions
        if self.conditions:
            # Check tags
            if "tags" in self.conditions:
                required_tags = set(self.conditions["tags"])
                if not required_tags.issubset(record.artifact.tags):
                    return False
            
            # Check custom attributes
            if "attributes" in self.conditions:
                for key, value in self.conditions["attributes"].items():
                    if record.artifact.custom_attributes.get(key) != value:
                        return False
        
        return True


@dataclass
class ArtifactLifecycle:
    """Tracks the lifecycle state of an artifact."""
    
    artifact_id: str
    classification: ArtifactClassification
    created_at: datetime
    current_tier: StorageTier = StorageTier.HOT
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    moved_to_warm: Optional[datetime] = None
    moved_to_cold: Optional[datetime] = None
    marked_for_deletion: Optional[datetime] = None
    
    def age_days(self) -> int:
        """Get artifact age in days."""
        now = datetime.now(timezone.utc)
        # Handle both timezone-aware and naive datetimes
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (now - created).days
    
    def days_in_tier(self) -> int:
        """Get days in current tier."""
        now = datetime.now(timezone.utc)
        
        def _make_aware(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        
        if self.current_tier == StorageTier.COLD and self.moved_to_cold:
            moved = _make_aware(self.moved_to_cold)
            return (now - moved).days if moved else 0
        elif self.current_tier == StorageTier.WARM and self.moved_to_warm:
            moved = _make_aware(self.moved_to_warm)
            return (now - moved).days if moved else 0
        else:
            return self.age_days()


class RetentionPolicyManager:
    """Manages artifact retention and classification policies."""
    
    def __init__(self):
        """Initialize the policy manager."""
        self.classification_rules: List[ClassificationRule] = []
        self.retention_policies: Dict[ArtifactClassification, RetentionPolicy] = {}
        self.artifact_lifecycles: Dict[str, ArtifactLifecycle] = {}
        
        # Set default policies
        self._set_default_policies()
    
    def _set_default_policies(self):
        """Set default retention policies."""
        # Critical artifacts - keep indefinitely
        self.retention_policies[ArtifactClassification.CRITICAL] = RetentionPolicy(
            classification=ArtifactClassification.CRITICAL,
            hot_retention_days=90,
            warm_retention_days=365,
            cold_retention_days=None,  # Indefinite
            archive_enabled=True,
        )
        
        # Important artifacts - 2 years
        self.retention_policies[ArtifactClassification.IMPORTANT] = RetentionPolicy(
            classification=ArtifactClassification.IMPORTANT,
            hot_retention_days=30,
            warm_retention_days=180,
            cold_retention_days=520,  # ~1.5 years in cold
            archive_enabled=True,
        )
        
        # Standard artifacts - 6 months
        self.retention_policies[ArtifactClassification.STANDARD] = RetentionPolicy(
            classification=ArtifactClassification.STANDARD,
            hot_retention_days=7,
            warm_retention_days=60,
            cold_retention_days=113,  # ~4 months in cold
            archive_enabled=True,
        )
        
        # Transient artifacts - 30 days
        self.retention_policies[ArtifactClassification.TRANSIENT] = RetentionPolicy(
            classification=ArtifactClassification.TRANSIENT,
            hot_retention_days=1,
            warm_retention_days=7,
            cold_retention_days=22,
            archive_enabled=False,  # Delete directly
        )
        
        # Ephemeral artifacts - 1 day
        self.retention_policies[ArtifactClassification.EPHEMERAL] = RetentionPolicy(
            classification=ArtifactClassification.EPHEMERAL,
            hot_retention_days=0,
            warm_retention_days=0,
            cold_retention_days=1,
            archive_enabled=False,
        )
        
        # Default classification rules
        self.add_classification_rule(ClassificationRule(
            name="gem_scores",
            artifact_types={ArtifactType.GEM_SCORE},
            classification=ArtifactClassification.IMPORTANT,
            priority=10,
        ))
        
        self.add_classification_rule(ClassificationRule(
            name="reports",
            artifact_types={ArtifactType.REPORT},
            classification=ArtifactClassification.IMPORTANT,
            priority=10,
        ))
        
        self.add_classification_rule(ClassificationRule(
            name="production_data",
            artifact_types={ArtifactType.MARKET_SNAPSHOT, ArtifactType.PRICE_SERIES},
            classification=ArtifactClassification.STANDARD,
            conditions={"tags": ["production"]},
            priority=5,
        ))
        
        self.add_classification_rule(ClassificationRule(
            name="feature_vectors",
            artifact_types={ArtifactType.FEATURE_VECTOR},
            classification=ArtifactClassification.TRANSIENT,
            priority=3,
        ))
        
        self.add_classification_rule(ClassificationRule(
            name="default",
            artifact_types=set(ArtifactType),
            classification=ArtifactClassification.STANDARD,
            priority=0,
        ))
    
    def add_classification_rule(self, rule: ClassificationRule):
        """Add a classification rule."""
        self.classification_rules.append(rule)
        # Sort by priority (descending)
        self.classification_rules.sort(key=lambda r: r.priority, reverse=True)
    
    def classify_artifact(self, record: ProvenanceRecord) -> ArtifactClassification:
        """Classify an artifact based on rules."""
        for rule in self.classification_rules:
            if rule.matches(record):
                return rule.classification
        
        # Default to standard if no rule matches
        return ArtifactClassification.STANDARD
    
    def register_artifact(
        self,
        artifact_id: str,
        record: ProvenanceRecord,
        classification: Optional[ArtifactClassification] = None,
    ):
        """Register an artifact for lifecycle management."""
        if classification is None:
            classification = self.classify_artifact(record)
        
        lifecycle = ArtifactLifecycle(
            artifact_id=artifact_id,
            classification=classification,
            created_at=record.artifact.created_at,
            last_accessed=datetime.now(timezone.utc),
        )
        
        self.artifact_lifecycles[artifact_id] = lifecycle
    
    def record_access(self, artifact_id: str):
        """Record an access to an artifact."""
        if artifact_id in self.artifact_lifecycles:
            lifecycle = self.artifact_lifecycles[artifact_id]
            lifecycle.last_accessed = datetime.now(timezone.utc)
            lifecycle.access_count += 1
    
    def get_tier_transition_due(
        self,
        artifact_id: str,
    ) -> Optional[StorageTier]:
        """Check if artifact should transition to a different tier."""
        if artifact_id not in self.artifact_lifecycles:
            return None
        
        lifecycle = self.artifact_lifecycles[artifact_id]
        policy = self.retention_policies[lifecycle.classification]
        age_days = lifecycle.age_days()
        
        # Check for deletion
        if policy.cold_retention_days is not None:
            total_retention = policy.get_total_retention_days()
            if age_days >= total_retention:
                return StorageTier.DELETED
        
        # Check for cold storage
        warm_threshold = policy.hot_retention_days + policy.warm_retention_days
        if age_days >= warm_threshold and lifecycle.current_tier != StorageTier.COLD:
            return StorageTier.COLD
        
        # Check for warm storage
        if age_days >= policy.hot_retention_days and lifecycle.current_tier == StorageTier.HOT:
            return StorageTier.WARM
        
        return None
    
    def transition_artifact(self, artifact_id: str, new_tier: StorageTier):
        """Transition artifact to a new storage tier."""
        if artifact_id not in self.artifact_lifecycles:
            return
        
        lifecycle = self.artifact_lifecycles[artifact_id]
        old_tier = lifecycle.current_tier
        lifecycle.current_tier = new_tier
        
        now = datetime.now(timezone.utc)
        if new_tier == StorageTier.WARM:
            lifecycle.moved_to_warm = now
        elif new_tier == StorageTier.COLD:
            lifecycle.moved_to_cold = now
        elif new_tier == StorageTier.DELETED:
            lifecycle.marked_for_deletion = now
    
    def run_lifecycle_management(
        self,
        tracker: Optional[ProvenanceTracker] = None,
    ) -> Dict[str, any]:
        """Run lifecycle management on all tracked artifacts.
        
        Returns statistics about transitions performed.
        """
        if tracker is None:
            tracker = get_provenance_tracker()
        
        stats = {
            "total_artifacts": len(self.artifact_lifecycles),
            "transitioned_to_warm": 0,
            "transitioned_to_cold": 0,
            "marked_for_deletion": 0,
            "by_classification": {},
        }
        
        for artifact_id, lifecycle in self.artifact_lifecycles.items():
            # Update classification stats
            classification = lifecycle.classification.value
            if classification not in stats["by_classification"]:
                stats["by_classification"][classification] = {
                    "count": 0,
                    "hot": 0,
                    "warm": 0,
                    "cold": 0,
                    "deleted": 0,
                }
            
            stats["by_classification"][classification]["count"] += 1
            stats["by_classification"][classification][lifecycle.current_tier.value] += 1
            
            # Check for tier transition
            new_tier = self.get_tier_transition_due(artifact_id)
            if new_tier and new_tier != lifecycle.current_tier:
                self.transition_artifact(artifact_id, new_tier)
                
                if new_tier == StorageTier.WARM:
                    stats["transitioned_to_warm"] += 1
                elif new_tier == StorageTier.COLD:
                    stats["transitioned_to_cold"] += 1
                elif new_tier == StorageTier.DELETED:
                    stats["marked_for_deletion"] += 1
        
        return stats
    
    def get_artifacts_for_archival(self) -> List[str]:
        """Get list of artifact IDs ready for archival."""
        artifacts = []
        for artifact_id, lifecycle in self.artifact_lifecycles.items():
            if lifecycle.current_tier == StorageTier.COLD:
                artifacts.append(artifact_id)
        return artifacts
    
    def get_artifacts_for_deletion(self) -> List[str]:
        """Get list of artifact IDs marked for deletion."""
        artifacts = []
        for artifact_id, lifecycle in self.artifact_lifecycles.items():
            if lifecycle.current_tier == StorageTier.DELETED:
                artifacts.append(artifact_id)
        return artifacts
    
    def export_lifecycle_report(self, output_path: Optional[Path] = None) -> str:
        """Export lifecycle management report."""
        report_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_artifacts": len(self.artifact_lifecycles),
            "policies": {
                classification.value: {
                    "hot_retention_days": policy.hot_retention_days,
                    "warm_retention_days": policy.warm_retention_days,
                    "cold_retention_days": policy.cold_retention_days,
                    "total_retention_days": policy.get_total_retention_days(),
                }
                for classification, policy in self.retention_policies.items()
            },
            "artifacts": {},
        }
        
        # Group by classification and tier
        for artifact_id, lifecycle in self.artifact_lifecycles.items():
            classification = lifecycle.classification.value
            tier = lifecycle.current_tier.value
            
            if classification not in report_data["artifacts"]:
                report_data["artifacts"][classification] = {}
            
            if tier not in report_data["artifacts"][classification]:
                report_data["artifacts"][classification][tier] = []
            
            report_data["artifacts"][classification][tier].append({
                "artifact_id": artifact_id,
                "age_days": lifecycle.age_days(),
                "access_count": lifecycle.access_count,
                "last_accessed": lifecycle.last_accessed.isoformat() if lifecycle.last_accessed else None,
            })
        
        # Convert to JSON
        report_json = json.dumps(report_data, indent=2)
        
        if output_path:
            output_path.write_text(report_json)
        
        return report_json
    
    def cleanup_deleted_artifacts(
        self,
        tracker: Optional[ProvenanceTracker] = None,
    ) -> int:
        """Remove artifacts marked for deletion.
        
        Returns the number of artifacts removed.
        """
        if tracker is None:
            tracker = get_provenance_tracker()
        
        deleted_artifacts = self.get_artifacts_for_deletion()
        
        for artifact_id in deleted_artifacts:
            # Remove from tracker
            if artifact_id in tracker.records:
                del tracker.records[artifact_id]
            
            # Remove from lifecycle tracking
            if artifact_id in self.artifact_lifecycles:
                del self.artifact_lifecycles[artifact_id]
        
        return len(deleted_artifacts)


# Global policy manager instance
_global_policy_manager = RetentionPolicyManager()


def get_policy_manager() -> RetentionPolicyManager:
    """Get the global policy manager instance."""
    return _global_policy_manager


def reset_policy_manager() -> None:
    """Reset the global policy manager (useful for testing)."""
    global _global_policy_manager
    _global_policy_manager = RetentionPolicyManager()
