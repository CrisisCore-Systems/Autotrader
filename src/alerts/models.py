"""Data models for alert rules and alerts inbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status in inbox."""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"


@dataclass
class AlertRuleModel:
    """Alert rule with full configuration."""
    
    id: str
    description: str
    enabled: bool = True
    condition: Dict[str, Any] = field(default_factory=dict)
    where: Dict[str, Any] = field(default_factory=dict)
    severity: AlertSeverity = AlertSeverity.INFO
    channels: List[str] = field(default_factory=list)
    suppression_duration: int = 3600  # seconds
    tags: List[str] = field(default_factory=list)
    version: str = "v2"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "enabled": self.enabled,
            "condition": self.condition,
            "where": self.where,
            "severity": self.severity.value if isinstance(self.severity, AlertSeverity) else self.severity,
            "channels": self.channels,
            "suppression_duration": self.suppression_duration,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AlertRuleModel:
        """Create from dictionary."""
        severity = data.get("severity", "info")
        if isinstance(severity, str):
            severity = AlertSeverity(severity)
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        
        return cls(
            id=data["id"],
            description=data["description"],
            enabled=data.get("enabled", True),
            condition=data.get("condition", {}),
            where=data.get("where", {}),
            severity=severity,
            channels=data.get("channels", []),
            suppression_duration=data.get("suppression_duration", 3600),
            tags=data.get("tags", []),
            version=data.get("version", "v2"),
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass
class AlertInboxItem:
    """Alert in the inbox awaiting action."""
    
    id: str
    rule_id: str
    token_symbol: str
    message: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    provenance_links: Dict[str, str] = field(default_factory=dict)
    triggered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.triggered_at is None:
            self.triggered_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "token_symbol": self.token_symbol,
            "message": self.message,
            "severity": self.severity.value if isinstance(self.severity, AlertSeverity) else self.severity,
            "status": self.status.value if isinstance(self.status, AlertStatus) else self.status,
            "metadata": self.metadata,
            "labels": self.labels,
            "provenance_links": self.provenance_links,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "snoozed_until": self.snoozed_until.isoformat() if self.snoozed_until else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AlertInboxItem:
        """Create from dictionary."""
        severity = data.get("severity", "info")
        if isinstance(severity, str):
            severity = AlertSeverity(severity)
        
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = AlertStatus(status)
        
        # Parse timestamps
        triggered_at = data.get("triggered_at")
        if isinstance(triggered_at, str):
            triggered_at = datetime.fromisoformat(triggered_at.replace('Z', '+00:00'))
        
        acknowledged_at = data.get("acknowledged_at")
        if isinstance(acknowledged_at, str):
            acknowledged_at = datetime.fromisoformat(acknowledged_at.replace('Z', '+00:00'))
        
        snoozed_until = data.get("snoozed_until")
        if isinstance(snoozed_until, str):
            snoozed_until = datetime.fromisoformat(snoozed_until.replace('Z', '+00:00'))
        
        resolved_at = data.get("resolved_at")
        if isinstance(resolved_at, str):
            resolved_at = datetime.fromisoformat(resolved_at.replace('Z', '+00:00'))
        
        return cls(
            id=data["id"],
            rule_id=data["rule_id"],
            token_symbol=data["token_symbol"],
            message=data["message"],
            severity=severity,
            status=status,
            metadata=data.get("metadata", {}),
            labels=data.get("labels", []),
            provenance_links=data.get("provenance_links", {}),
            triggered_at=triggered_at,
            acknowledged_at=acknowledged_at,
            snoozed_until=snoozed_until,
            resolved_at=resolved_at,
        )


@dataclass
class AlertAnalytics:
    """Analytics data for alert performance."""
    
    total_alerts: int = 0
    alerts_by_severity: Dict[str, int] = field(default_factory=dict)
    alerts_by_rule: Dict[str, int] = field(default_factory=dict)
    average_delivery_latency_ms: float = 0.0
    dedupe_rate: float = 0.0
    acknowledgement_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_alerts": self.total_alerts,
            "alerts_by_severity": self.alerts_by_severity,
            "alerts_by_rule": self.alerts_by_rule,
            "average_delivery_latency_ms": self.average_delivery_latency_ms,
            "dedupe_rate": self.dedupe_rate,
            "acknowledgement_rate": self.acknowledgement_rate,
        }


__all__ = [
    "AlertSeverity",
    "AlertStatus",
    "AlertRuleModel",
    "AlertInboxItem",
    "AlertAnalytics",
]
