"""Integrated Data Drift and Freshness Monitoring.

This module combines drift detection with data freshness monitoring
and SLA enforcement for critical features.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

from src.core.logging_config import get_logger
from src.core.freshness import FreshnessTracker, FreshnessLevel
from src.monitoring.drift_monitor import (
    DriftMonitor,
    Baseline,
    DriftReport,
    DriftSeverity,
)

logger = get_logger(__name__)


class FeatureCriticality(Enum):
    """Criticality level for features."""
    CRITICAL = "critical"  # Must meet strict SLAs
    IMPORTANT = "important"  # Should meet SLAs
    STANDARD = "standard"  # Best effort monitoring


@dataclass
class FreshnessSLA:
    """SLA definition for feature freshness."""
    max_age_seconds: float
    criticality: FeatureCriticality
    alert_threshold_seconds: Optional[float] = None
    
    def __post_init__(self):
        """Set alert threshold if not specified."""
        if self.alert_threshold_seconds is None:
            # Alert at 80% of max age
            self.alert_threshold_seconds = self.max_age_seconds * 0.8


@dataclass
class FeatureHealth:
    """Health status for a monitored feature."""
    feature_name: str
    drift_detected: bool
    drift_severity: DriftSeverity
    freshness_level: FreshnessLevel
    data_age_seconds: float
    sla_violated: bool
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_name": self.feature_name,
            "drift_detected": self.drift_detected,
            "drift_severity": self.drift_severity.value,
            "freshness_level": self.freshness_level.value,
            "data_age_seconds": self.data_age_seconds,
            "sla_violated": self.sla_violated,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class MonitoringReport:
    """Comprehensive monitoring report for drift and freshness."""
    timestamp: datetime
    features_monitored: int
    features_drifted: int
    features_stale: int
    sla_violations: int
    feature_health: Dict[str, FeatureHealth]
    drift_reports: List[DriftReport]
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "features_monitored": self.features_monitored,
            "features_drifted": self.features_drifted,
            "features_stale": self.features_stale,
            "sla_violations": self.sla_violations,
            "feature_health": {
                name: health.to_dict() 
                for name, health in self.feature_health.items()
            },
            "drift_reports": [report.to_dict() for report in self.drift_reports],
            "recommendations": self.recommendations,
        }


class IntegratedMonitor:
    """Integrated monitor for data drift and freshness."""
    
    def __init__(
        self,
        name: str,
        drift_monitor: Optional[DriftMonitor] = None,
        freshness_tracker: Optional[FreshnessTracker] = None,
    ):
        """Initialize integrated monitor.
        
        Args:
            name: Monitor name
            drift_monitor: Drift monitor instance
            freshness_tracker: Freshness tracker instance
        """
        self.name = name
        self.drift_monitor = drift_monitor or DriftMonitor(name=f"{name}_drift")
        self.freshness_tracker = freshness_tracker or FreshnessTracker()
        
        # SLA definitions for features
        self.feature_slas: Dict[str, FreshnessSLA] = {}
        
        # Critical features that must meet SLAs
        self.critical_features: Set[str] = set()
        
        # Monitoring history
        self.reports: List[MonitoringReport] = []
        
        logger.info(
            "integrated_monitor_initialized",
            name=name,
        )
    
    def register_feature_sla(
        self,
        feature_name: str,
        max_age_seconds: float,
        criticality: FeatureCriticality = FeatureCriticality.STANDARD,
        alert_threshold_seconds: Optional[float] = None,
    ) -> None:
        """Register SLA for a feature.
        
        Args:
            feature_name: Feature name
            max_age_seconds: Maximum allowed age in seconds
            criticality: Feature criticality level
            alert_threshold_seconds: Optional custom alert threshold
        """
        sla = FreshnessSLA(
            max_age_seconds=max_age_seconds,
            criticality=criticality,
            alert_threshold_seconds=alert_threshold_seconds,
        )
        
        self.feature_slas[feature_name] = sla
        
        if criticality == FeatureCriticality.CRITICAL:
            self.critical_features.add(feature_name)
        
        logger.info(
            "feature_sla_registered",
            feature=feature_name,
            max_age_seconds=max_age_seconds,
            criticality=criticality.value,
        )
    
    def check_freshness_sla(
        self,
        feature_name: str,
        data_age_seconds: float,
    ) -> tuple[bool, bool]:
        """Check if feature meets freshness SLA.
        
        Args:
            feature_name: Feature name
            data_age_seconds: Current data age in seconds
            
        Returns:
            Tuple of (sla_violated, should_alert)
        """
        if feature_name not in self.feature_slas:
            return False, False
        
        sla = self.feature_slas[feature_name]
        sla_violated = data_age_seconds > sla.max_age_seconds
        should_alert = data_age_seconds > sla.alert_threshold_seconds
        
        return sla_violated, should_alert
    
    def monitor_features(
        self,
        features: Dict[str, np.ndarray],
        feature_timestamps: Optional[Dict[str, datetime]] = None,
    ) -> MonitoringReport:
        """Monitor features for drift and freshness.
        
        Args:
            features: Dictionary of feature name to current values
            feature_timestamps: Optional timestamps for each feature
            
        Returns:
            Monitoring report
        """
        if self.drift_monitor.baseline is None:
            raise ValueError("No baseline set for drift detection")
        
        timestamp = datetime.now(timezone.utc)
        feature_health: Dict[str, FeatureHealth] = {}
        drift_reports: List[DriftReport] = []
        recommendations: List[str] = []
        
        features_drifted = 0
        features_stale = 0
        sla_violations = 0
        
        # Check each feature
        for feature_name, feature_values in features.items():
            # Skip if not in baseline
            if feature_name not in self.drift_monitor.baseline.feature_distributions:
                logger.warning(
                    "feature_not_in_baseline",
                    feature=feature_name,
                )
                continue
            
            # Check drift
            drift_report = self.drift_monitor.detect_feature_drift(
                feature_name=feature_name,
                current_distribution=feature_values,
            )
            drift_reports.append(drift_report)
            
            if drift_report.drift_detected:
                features_drifted += 1
            
            # Check freshness
            feature_timestamp = (
                feature_timestamps.get(feature_name, timestamp)
                if feature_timestamps
                else timestamp
            )
            
            self.freshness_tracker.record_update(
                source_name=feature_name,
                timestamp=feature_timestamp,
            )
            
            freshness = self.freshness_tracker.get_freshness(feature_name)
            data_age_seconds = freshness.data_age_seconds
            freshness_level = freshness.freshness_level
            
            # Check SLA
            sla_violated, should_alert = self.check_freshness_sla(
                feature_name,
                data_age_seconds,
            )
            
            if sla_violated:
                sla_violations += 1
                logger.warning(
                    "feature_sla_violated",
                    feature=feature_name,
                    data_age_seconds=data_age_seconds,
                    max_age_seconds=self.feature_slas[feature_name].max_age_seconds,
                )
            
            if freshness_level in [FreshnessLevel.STALE, FreshnessLevel.OUTDATED]:
                features_stale += 1
            
            # Create feature health record
            feature_health[feature_name] = FeatureHealth(
                feature_name=feature_name,
                drift_detected=drift_report.drift_detected,
                drift_severity=drift_report.severity,
                freshness_level=freshness_level,
                data_age_seconds=data_age_seconds,
                sla_violated=sla_violated,
                last_updated=feature_timestamp,
            )
        
        # Generate recommendations
        if features_drifted > 0:
            recommendations.append(
                f"{features_drifted}/{len(features)} features show drift - "
                "consider model retraining"
            )
        
        if sla_violations > 0:
            recommendations.append(
                f"{sla_violations} SLA violation(s) detected - "
                "check data pipeline health"
            )
        
        critical_violations = sum(
            1 for name, health in feature_health.items()
            if name in self.critical_features and health.sla_violated
        )
        
        if critical_violations > 0:
            recommendations.append(
                f"CRITICAL: {critical_violations} critical feature(s) violating SLA - "
                "immediate action required"
            )
        
        if features_stale > 0:
            recommendations.append(
                f"{features_stale} feature(s) have stale data - "
                "verify data source connectivity"
            )
        
        # Create report
        report = MonitoringReport(
            timestamp=timestamp,
            features_monitored=len(features),
            features_drifted=features_drifted,
            features_stale=features_stale,
            sla_violations=sla_violations,
            feature_health=feature_health,
            drift_reports=drift_reports,
            recommendations=recommendations,
        )
        
        self.reports.append(report)
        
        logger.info(
            "monitoring_report_generated",
            features_monitored=len(features),
            features_drifted=features_drifted,
            features_stale=features_stale,
            sla_violations=sla_violations,
        )
        
        return report
    
    def save_report(self, report: MonitoringReport, path: Path) -> None:
        """Save monitoring report to disk.
        
        Args:
            report: Monitoring report
            path: Save path
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        
        logger.info("monitoring_report_saved", path=str(path))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of monitoring status.
        
        Returns:
            Summary dictionary
        """
        if not self.reports:
            return {
                "total_reports": 0,
                "current_status": "no_data",
            }
        
        latest = self.reports[-1]
        
        return {
            "total_reports": len(self.reports),
            "current_status": self._determine_overall_status(latest),
            "latest_report": latest.to_dict(),
            "features_monitored": latest.features_monitored,
            "critical_features": len(self.critical_features),
            "sla_definitions": len(self.feature_slas),
        }
    
    def _determine_overall_status(self, report: MonitoringReport) -> str:
        """Determine overall system status.
        
        Args:
            report: Latest monitoring report
            
        Returns:
            Status string
        """
        # Check for critical violations
        critical_violations = sum(
            1 for name, health in report.feature_health.items()
            if name in self.critical_features and health.sla_violated
        )
        
        if critical_violations > 0:
            return "critical"
        
        if report.sla_violations > 0:
            return "degraded"
        
        if report.features_drifted > report.features_monitored * 0.3:
            return "degraded"
        
        if report.features_stale > 0:
            return "warning"
        
        return "healthy"
