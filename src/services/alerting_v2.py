"""Advanced Alert Engine v2 with Compound Logic & Suppression.

Features:
- Compound conditions (AND, OR, NOT logic)
- Alert suppression and deduplication
- Alert escalation policies
- Time-based windowing
- Priority-based routing
- Alert history tracking
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.logging_config import get_logger
from src.core.metrics import Counter, Gauge

logger = get_logger(__name__)

# Metrics
ALERTS_FIRED = Counter(
    'alerts_fired_total',
    'Total alerts fired',
    ['rule_name', 'severity', 'status']
)

ALERTS_SUPPRESSED = Counter(
    'alerts_suppressed_total',
    'Total alerts suppressed',
    ['rule_name', 'reason']
)

ACTIVE_ALERTS = Gauge(
    'active_alerts',
    'Number of currently active alerts',
    ['severity']
)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(Enum):
    """Alert status."""
    FIRING = "firing"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"


class ConditionOperator(Enum):
    """Logical operators for compound conditions."""
    AND = "and"
    OR = "or"
    NOT = "not"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    IN = "in"
    CONTAINS = "contains"


@dataclass
class AlertCondition:
    """Single alert condition."""
    metric: str
    operator: ConditionOperator
    threshold: Any
    description: Optional[str] = None
    
    def _compare_values(self, value: Any) -> bool:
        """Compare value against threshold using operator.
        
        Args:
            value: Value to compare
            
        Returns:
            Comparison result
        """
        comparisons = {
            ConditionOperator.GT: lambda: value > self.threshold,
            ConditionOperator.LT: lambda: value < self.threshold,
            ConditionOperator.GTE: lambda: value >= self.threshold,
            ConditionOperator.LTE: lambda: value <= self.threshold,
            ConditionOperator.EQ: lambda: value == self.threshold,
            ConditionOperator.NEQ: lambda: value != self.threshold,
            ConditionOperator.IN: lambda: value in self.threshold,
            ConditionOperator.CONTAINS: lambda: self.threshold in value,
        }
        
        comparison_func = comparisons.get(self.operator)
        if comparison_func is None:
            logger.error("unknown_operator", operator=self.operator)
            return False
        
        return comparison_func()
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context.
        
        Args:
            context: Dictionary of metric values
            
        Returns:
            True if condition is met
        """
        if self.metric not in context:
            logger.warning(
                "condition_metric_missing",
                metric=self.metric,
                available_metrics=list(context.keys())
            )
            return False
        
        value = context[self.metric]
        
        try:
            return self._compare_values(value)
        except Exception as e:
            logger.error(
                "condition_evaluation_failed",
                metric=self.metric,
                operator=self.operator.value,
                error=str(e)
            )
            return False


@dataclass
class CompoundCondition:
    """Compound condition with logical operators."""
    operator: ConditionOperator
    conditions: List[AlertCondition | CompoundCondition]
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate compound condition.
        
        Args:
            context: Dictionary of metric values
            
        Returns:
            True if compound condition is met
        """
        results = [cond.evaluate(context) for cond in self.conditions]
        
        if self.operator == ConditionOperator.AND:
            return all(results)
        elif self.operator == ConditionOperator.OR:
            return any(results)
        elif self.operator == ConditionOperator.NOT:
            return not any(results)
        else:
            logger.error("invalid_compound_operator", operator=self.operator)
            return False


@dataclass
class SuppressionRule:
    """Alert suppression rule."""
    name: str
    conditions: List[AlertCondition]
    duration_seconds: int
    reason: str
    
    def should_suppress(self, context: Dict[str, Any]) -> bool:
        """Check if alert should be suppressed.
        
        Args:
            context: Alert context
            
        Returns:
            True if alert should be suppressed
        """
        return all(cond.evaluate(context) for cond in self.conditions)


@dataclass
class EscalationPolicy:
    """Alert escalation policy."""
    name: str
    levels: List[Dict[str, Any]]  # [{"delay_seconds": 300, "notify": ["team_lead"]}, ...]
    
    def get_current_level(self, alert_age_seconds: int) -> Optional[Dict[str, Any]]:
        """Get current escalation level based on alert age.
        
        Args:
            alert_age_seconds: Time since alert fired
            
        Returns:
            Current escalation level or None
        """
        for level in sorted(self.levels, key=lambda x: x.get("delay_seconds", 0)):
            if alert_age_seconds >= level.get("delay_seconds", 0):
                return level
        return None


@dataclass
class Alert:
    """Alert instance."""
    rule_name: str
    severity: AlertSeverity
    title: str
    message: str
    context: Dict[str, Any]
    fired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    status: AlertStatus = AlertStatus.FIRING
    fingerprint: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    suppression_until: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    escalation_level: int = 0
    
    def __post_init__(self):
        """Generate fingerprint for deduplication."""
        if self.fingerprint is None:
            # Generate unique fingerprint based on rule and key context
            key_values = sorted([
                f"{k}={v}" for k, v in self.context.items()
                if k in ['token', 'metric', 'source']
            ])
            self.fingerprint = f"{self.rule_name}:{'|'.join(key_values)}"
    
    def age_seconds(self) -> int:
        """Get alert age in seconds."""
        return int((datetime.now(timezone.utc) - self.fired_at).total_seconds())
    
    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)
        
        logger.info(
            "alert_resolved",
            rule_name=self.rule_name,
            severity=self.severity.value,
            duration_seconds=self.age_seconds(),
        )
    
    def suppress(self, duration_seconds: int, reason: str) -> None:
        """Suppress alert for duration.
        
        Args:
            duration_seconds: Suppression duration
            reason: Suppression reason
        """
        self.status = AlertStatus.SUPPRESSED
        self.suppression_until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        
        ALERTS_SUPPRESSED.labels(rule_name=self.rule_name, reason=reason).inc()
        
        logger.info(
            "alert_suppressed",
            rule_name=self.rule_name,
            duration_seconds=duration_seconds,
            reason=reason,
        )
    
    def acknowledge(self, acknowledged_by: str) -> None:
        """Acknowledge alert.
        
        Args:
            acknowledged_by: User/system acknowledging the alert
        """
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(timezone.utc)
        self.acknowledged_by = acknowledged_by
        
        logger.info(
            "alert_acknowledged",
            rule_name=self.rule_name,
            acknowledged_by=acknowledged_by,
        )


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: AlertCondition | CompoundCondition
    severity: AlertSeverity
    title: str
    message_template: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    evaluation_interval_seconds: int = 60
    for_duration_seconds: int = 0  # Alert must be true for this duration
    suppression_rules: List[SuppressionRule] = field(default_factory=list)
    escalation_policy: Optional[EscalationPolicy] = None
    enabled: bool = True
    
    def evaluate(self, context: Dict[str, Any]) -> Optional[Alert]:
        """Evaluate rule and create alert if triggered.
        
        Args:
            context: Evaluation context with metrics
            
        Returns:
            Alert if rule triggered, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            if self.condition.evaluate(context):
                # Format message with context
                message = self.message_template.format(**context)
                
                alert = Alert(
                    rule_name=self.name,
                    severity=self.severity,
                    title=self.title,
                    message=message,
                    context=context,
                    labels=self.labels.copy(),
                    annotations=self.annotations.copy(),
                )
                
                # Check suppression rules
                for suppression_rule in self.suppression_rules:
                    if suppression_rule.should_suppress(context):
                        alert.suppress(
                            suppression_rule.duration_seconds,
                            suppression_rule.reason
                        )
                        return None
                
                ALERTS_FIRED.labels(
                    rule_name=self.name,
                    severity=self.severity.value,
                    status="firing"
                ).inc()
                
                logger.info(
                    "alert_fired",
                    rule_name=self.name,
                    severity=self.severity.value,
                    title=self.title,
                    context=context,
                )
                
                return alert
            
        except Exception as e:
            logger.error(
                "alert_evaluation_failed",
                rule_name=self.name,
                error=str(e),
            )
        
        return None


class AlertManager:
    """Manages alert lifecycle and routing."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}  # fingerprint -> Alert
        self.alert_history: List[Alert] = []
        self.handlers: List[Callable[[Alert], None]] = []
        
        logger.info("alert_manager_initialized")
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add alert rule.
        
        Args:
            rule: Alert rule to add
        """
        self.rules[rule.name] = rule
        logger.info("alert_rule_added", rule_name=rule.name)
    
    def remove_rule(self, rule_name: str) -> None:
        """Remove alert rule.
        
        Args:
            rule_name: Name of rule to remove
        """
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info("alert_rule_removed", rule_name=rule_name)
    
    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add alert handler.
        
        Args:
            handler: Function to handle alerts
        """
        self.handlers.append(handler)
        logger.info("alert_handler_added", handler_name=handler.__name__)
    
    def evaluate_rules(self, context: Dict[str, Any]) -> List[Alert]:
        """Evaluate all rules against context.
        
        Args:
            context: Evaluation context
            
        Returns:
            List of triggered alerts
        """
        alerts = []
        
        for rule in self.rules.values():
            alert = rule.evaluate(context)
            if alert:
                # Check for duplicate
                if alert.fingerprint in self.active_alerts:
                    existing = self.active_alerts[alert.fingerprint]
                    logger.debug(
                        "alert_deduplicated",
                        fingerprint=alert.fingerprint,
                        age_seconds=existing.age_seconds(),
                    )
                    continue
                
                # Add to active alerts
                self.active_alerts[alert.fingerprint] = alert
                self.alert_history.append(alert)
                alerts.append(alert)
                
                # Update metrics
                ACTIVE_ALERTS.labels(severity=alert.severity.value).inc()
                
                # Notify handlers
                for handler in self.handlers:
                    try:
                        handler(alert)
                    except Exception as e:
                        logger.error(
                            "alert_handler_failed",
                            handler=handler.__name__,
                            error=str(e),
                        )
        
        return alerts
    
    def resolve_alert(self, fingerprint: str) -> bool:
        """Resolve an active alert.
        
        Args:
            fingerprint: Alert fingerprint
            
        Returns:
            True if resolved
        """
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.resolve()
            
            # Update metrics
            ACTIVE_ALERTS.labels(severity=alert.severity.value).dec()
            
            del self.active_alerts[fingerprint]
            return True
        
        return False
    
    def acknowledge_alert(self, fingerprint: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert.
        
        Args:
            fingerprint: Alert fingerprint
            acknowledged_by: User acknowledging
            
        Returns:
            True if acknowledged
        """
        if fingerprint in self.active_alerts:
            self.active_alerts[fingerprint].acknowledge(acknowledged_by)
            return True
        
        return False
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        rule_name: Optional[str] = None,
    ) -> List[Alert]:
        """Get active alerts.
        
        Args:
            severity: Filter by severity
            rule_name: Filter by rule name
            
        Returns:
            List of active alerts
        """
        alerts = list(self.active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if rule_name:
            alerts = [a for a in alerts if a.rule_name == rule_name]
        
        return alerts
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics.
        
        Returns:
            Summary dictionary
        """
        active = list(self.active_alerts.values())
        
        return {
            "total_active": len(active),
            "by_severity": {
                severity.value: len([a for a in active if a.severity == severity])
                for severity in AlertSeverity
            },
            "by_status": {
                status.value: len([a for a in active if a.status == status])
                for status in AlertStatus
            },
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "total_fired": len(self.alert_history),
        }
    
    def cleanup_resolved(self, max_age_seconds: int = 3600) -> int:
        """Remove old resolved alerts from history.
        
        Args:
            max_age_seconds: Maximum age to keep
            
        Returns:
            Number of alerts removed
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=max_age_seconds)
        
        before = len(self.alert_history)
        self.alert_history = [
            a for a in self.alert_history
            if a.status == AlertStatus.FIRING or
            (a.resolved_at and a.resolved_at > cutoff)
        ]
        removed = before - len(self.alert_history)
        
        if removed > 0:
            logger.info("alerts_cleaned_up", removed=removed)
        
        return removed


# Predefined alert handlers
def console_handler(alert: Alert) -> None:
    """Print alert to console."""
    print(f"\n{'='*80}")
    print(f"🚨 ALERT: {alert.title}")
    print(f"{'='*80}")
    print(f"Severity: {alert.severity.value.upper()}")
    print(f"Rule: {alert.rule_name}")
    print(f"Message: {alert.message}")
    print(f"Fired at: {alert.fired_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Status: {alert.status.value}")
    if alert.labels:
        print(f"Labels: {alert.labels}")
    print(f"{'='*80}\n")


def logging_handler(alert: Alert) -> None:
    """Log alert with structured logging."""
    logger.warning(
        "alert_triggered",
        rule_name=alert.rule_name,
        severity=alert.severity.value,
        title=alert.title,
        message=alert.message,
        context=alert.context,
        labels=alert.labels,
        fingerprint=alert.fingerprint,
    )
