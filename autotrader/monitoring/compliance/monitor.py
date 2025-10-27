"""Compliance monitoring framework for Phase 12 governance requirements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence
import logging

from autotrader.audit.trail import (
    AuditTrailStore,
    EventType,
    get_audit_trail,
)
from autotrader.monitoring.anomaly.detector import Anomaly, AnomalyDetector

try:
    from prometheus_client import Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock implementations for when prometheus is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): pass
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
        def set(self, *args, **kwargs): pass
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
        def observe(self, *args, **kwargs): pass


logger = logging.getLogger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

COMPLIANCE_ISSUES_TOTAL = Counter(
    'compliance_issues_total',
    'Total number of compliance issues detected',
    ['severity', 'issue_code']
)

COMPLIANCE_CHECKS_TOTAL = Counter(
    'compliance_checks_total',
    'Total number of compliance checks performed',
    ['check_type', 'status']
)

COMPLIANCE_CHECK_DURATION = Histogram(
    'compliance_check_duration_seconds',
    'Duration of compliance checks',
    ['check_type']
)

RISK_CHECK_FAILURES = Counter(
    'risk_check_failures_total',
    'Total number of risk check failures',
    ['failure_type']
)

ALERT_DELIVERY_TOTAL = Counter(
    'alert_delivery_total',
    'Total number of alerts sent',
    ['channel', 'severity', 'status']
)

ACTIVE_VIOLATIONS = Gauge(
    'active_violations',
    'Number of active compliance violations',
    ['severity']
)


class ComplianceSeverity(str, Enum):
    """Severity levels for detected compliance issues."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ComplianceIssue:
    """Single compliance finding."""

    issue_code: str
    description: str
    severity: ComplianceSeverity
    signal_id: Optional[str] = None
    order_ids: Sequence[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_code": self.issue_code,
            "description": self.description,
            "severity": self.severity.value,
            "signal_id": self.signal_id,
            "order_ids": list(self.order_ids),
            "metadata": self.metadata,
        }


@dataclass
class CompliancePolicy:
    """Thresholds and behavioural policies for compliance checks."""

    require_risk_check: bool = True
    require_llm_review: bool = False
    max_risk_score: float = 0.75
    max_order_notional: Optional[float] = None
    forbidden_llm_decisions: Sequence[str] = field(
        default_factory=lambda: ("override_limits", "proceed_despite_reject")
    )


@dataclass
class ComplianceReport:
    """Aggregated compliance report for a period."""

    period_start: datetime
    period_end: datetime
    generated_at: datetime
    issues: List[ComplianceIssue]
    totals: Dict[str, int]
    audit_summary: Dict[str, Any]
    anomalies: List[Anomaly] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "issues": [issue.to_dict() for issue in self.issues],
            "totals": self.totals,
            "audit_summary": self.audit_summary,
            "anomalies": [anomaly.to_dict() for anomaly in self.anomalies],
        }


class ComplianceMonitor:
    """Run compliance checks on audit trail events and risk artefacts."""

    def __init__(
        self,
        audit_trail: Optional[AuditTrailStore] = None,
        policy: Optional[CompliancePolicy] = None,
        anomaly_detector: Optional[AnomalyDetector] = None,
    ) -> None:
        self._audit_trail = audit_trail or get_audit_trail()
        self._policy = policy or CompliancePolicy()
        self._anomaly_detector = anomaly_detector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze_period(
        self,
        period_start: datetime,
        period_end: datetime,
        timezone_: timezone = timezone.utc,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> ComplianceReport:
        """Analyze a period of activity and produce a compliance report."""
        if period_start >= period_end:
            raise ValueError("period_start must be before period_end")
        logger.info(
            "Running compliance checks for %s → %s",
            period_start,
            period_end,
        )

        signals = self._audit_trail.query_events(
            event_type=EventType.SIGNAL,
            start_time=period_start,
            end_time=period_end,
        )
        signal_ids = [event["data"]["signal_id"] for event in signals]

        issues: List[ComplianceIssue] = []
        for signal_id in signal_ids:
            issues.extend(self._evaluate_signal(signal_id))

        totals = self._summarise_issues(issues)
        audit_summary = self._audit_trail.generate_compliance_report(
            period_start,
            period_end,
        )
        anomalies: List[Anomaly] = []
        if self._anomaly_detector and metrics:
            anomalies = self._run_anomaly_checks(metrics)

        report = ComplianceReport(
            period_start=period_start.astimezone(timezone_),
            period_end=period_end.astimezone(timezone_),
            generated_at=datetime.now(tz=timezone_),
            issues=issues,
            totals=totals,
            audit_summary=audit_summary,
            anomalies=anomalies,
        )
        
        # Record Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            COMPLIANCE_CHECKS_TOTAL.labels(
                check_type='period_analysis',
                status='completed'
            ).inc()
            
            for severity, count in totals.items():
                if severity != 'total':
                    ACTIVE_VIOLATIONS.labels(severity=severity).set(count)
        
        logger.info(
            "Compliance report generated: %d issues (%d critical)",
            totals.get("total", 0),
            totals.get(ComplianceSeverity.CRITICAL.value, 0),
        )
        return report

    def check_signal(self, signal_id: str) -> List[ComplianceIssue]:
        """Expose single-signal compliance evaluation."""
        return self._evaluate_signal(signal_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _evaluate_signal(self, signal_id: str) -> List[ComplianceIssue]:
        history = self._audit_trail.reconstruct_trade_history(signal_id)
        risk_events = [entry["data"] for entry in history.get("risk_checks", [])]
        order_events = [entry["data"] for entry in history.get("orders", [])]
        fill_events = [entry["data"] for entry in history.get("fills", [])]
        llm_decisions = [entry["data"] for entry in history.get("llm_decisions", [])]

        issues: List[ComplianceIssue] = []
        issues.extend(
            self._core_control_issues(signal_id, risk_events, llm_decisions)
        )
        issues.extend(
            issue
            for risk_event in risk_events
            for issue in self._assess_risk_event(
                signal_id, risk_event, order_events, fill_events
            )
        )
        issues.extend(self._assess_llm_decisions(signal_id, llm_decisions))
        issues.extend(
            self._order_notional_issues(signal_id, order_events, fill_events)
        )
        return issues

    def _core_control_issues(
        self,
        signal_id: str,
        risk_events: Sequence[Dict[str, Any]],
        llm_decisions: Sequence[Dict[str, Any]],
    ) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []
        if self._policy.require_risk_check and not risk_events:
            issue = ComplianceIssue(
                issue_code="missing_risk_check",
                description="Signal executed without recorded risk checks",
                severity=ComplianceSeverity.CRITICAL,
                signal_id=signal_id,
            )
            issues.append(issue)
            
            # Record metric
            if PROMETHEUS_AVAILABLE:
                COMPLIANCE_ISSUES_TOTAL.labels(
                    severity='critical',
                    issue_code='missing_risk_check'
                ).inc()
                RISK_CHECK_FAILURES.labels(failure_type='missing').inc()
                
        if self._policy.require_llm_review and not llm_decisions:
            issue = ComplianceIssue(
                issue_code="llm_review_missing",
                description="LLM review required but not recorded",
                severity=ComplianceSeverity.WARNING,
                signal_id=signal_id,
            )
            issues.append(issue)
            
            # Record metric
            if PROMETHEUS_AVAILABLE:
                COMPLIANCE_ISSUES_TOTAL.labels(
                    severity='warning',
                    issue_code='llm_review_missing'
                ).inc()
                
        return issues

    def _order_notional_issues(
        self,
        signal_id: str,
        orders: Sequence[Dict[str, Any]],
        fills: Sequence[Dict[str, Any]],
    ) -> List[ComplianceIssue]:
        if self._policy.max_order_notional is None or not orders:
            return []
        return self._check_order_notional(signal_id, list(orders), list(fills))

    def _assess_risk_event(
        self,
        signal_id: str,
        risk_event: Dict[str, Any],
        orders: List[Dict[str, Any]],
        fills: List[Dict[str, Any]],
    ) -> List[ComplianceIssue]:
        context = self._risk_context(risk_event, orders, fills)
        issues: List[ComplianceIssue] = []

        override_issue = self._risk_override_issue(signal_id, context)
        if override_issue:
            issues.append(override_issue)

        risk_score_issue = self._risk_score_issue(signal_id, context)
        if risk_score_issue:
            issues.append(risk_score_issue)

        failed_checks_issue = self._risk_failed_check_issue(signal_id, context)
        if failed_checks_issue:
            issues.append(failed_checks_issue)

        return issues

    def _risk_context(
        self,
        risk_event: Dict[str, Any],
        orders: Sequence[Dict[str, Any]],
        fills: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "decision": risk_event.get("decision", "approve"),
            "risk_score": float(risk_event.get("risk_score", 0.0)),
            "order_ids": [order.get("order_id", "") for order in orders],
            "has_trade": bool(orders or fills),
            "failed_checks": [
                check
                for check in risk_event.get("checks", [])
                if check.get("status") == "fail"
            ],
        }

    def _risk_override_issue(
        self, signal_id: str, context: Dict[str, Any]
    ) -> Optional[ComplianceIssue]:
        if context["decision"] == "approve" or not context["has_trade"]:
            return None
        return ComplianceIssue(
            issue_code="risk_override",
            description=f"Risk decision '{context['decision']}' but orders executed",
            severity=ComplianceSeverity.CRITICAL,
            signal_id=signal_id,
            order_ids=context["order_ids"],
            metadata={"risk_score": context["risk_score"]},
        )

    def _risk_score_issue(
        self, signal_id: str, context: Dict[str, Any]
    ) -> Optional[ComplianceIssue]:
        if context["risk_score"] <= self._policy.max_risk_score:
            return None
        return ComplianceIssue(
            issue_code="risk_score_exceeded",
            description=f"Risk score {context['risk_score']:.2f} exceeds policy limit",
            severity=ComplianceSeverity.WARNING,
            signal_id=signal_id,
            order_ids=context["order_ids"],
            metadata={
                "risk_score": context["risk_score"],
                "limit": self._policy.max_risk_score,
            },
        )

    def _risk_failed_check_issue(
        self, signal_id: str, context: Dict[str, Any]
    ) -> Optional[ComplianceIssue]:
        if not context["failed_checks"] or not context["has_trade"]:
            return None
        return ComplianceIssue(
            issue_code="risk_check_failed",
            description="Risk checks failed but trade executed",
            severity=ComplianceSeverity.CRITICAL,
            signal_id=signal_id,
            order_ids=context["order_ids"],
            metadata={"failed_checks": context["failed_checks"]},
        )

    def _assess_llm_decisions(
        self,
        signal_id: str,
        decisions: List[Dict[str, Any]],
    ) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []
        for decision in decisions:
            action = decision.get("decision", "")
            if action in self._policy.forbidden_llm_decisions:
                issues.append(
                    ComplianceIssue(
                        issue_code="llm_forbidden_action",
                        description=f"LLM decision '{action}' violates policy",
                        severity=ComplianceSeverity.CRITICAL,
                        signal_id=signal_id,
                        metadata={"llm_model": decision.get("llm_model")},
                    )
                )
        return issues

    def _check_order_notional(
        self,
        signal_id: str,
        orders: List[Dict[str, Any]],
        fills: List[Dict[str, Any]],
    ) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []
        # Map fill order id -> average fill price for better notional estimate
        fill_price_by_order: Dict[str, float] = {}
        for fill in fills:
            order_id = fill.get("order_id")
            if not order_id:
                continue
            price = float(fill.get("price", 0.0))
            fill_price_by_order.setdefault(order_id, []).append(price)

        for order in orders:
            order_id = order.get("order_id", "")
            limit_price = order.get("limit_price")
            reference_price = None
            if limit_price is not None:
                reference_price = float(limit_price)
            elif order_id in fill_price_by_order:
                prices = fill_price_by_order[order_id]
                reference_price = sum(prices) / len(prices)

            quantity = float(order.get("quantity", 0.0))
            if reference_price is None:
                continue
            notional = abs(quantity * reference_price)
            if notional > self._policy.max_order_notional:
                issues.append(
                    ComplianceIssue(
                        issue_code="order_notional_exceeded",
                        description=(
                            f"Order notional ${notional:.2f} exceeds limit"
                        ),
                        severity=ComplianceSeverity.WARNING,
                        signal_id=signal_id,
                        order_ids=[order_id],
                        metadata={
                            "notional": notional,
                            "limit": self._policy.max_order_notional,
                        },
                    )
                )
        return issues

    def _summarise_issues(self, issues: List[ComplianceIssue]) -> Dict[str, int]:
        summary = {severity.value: 0 for severity in ComplianceSeverity}
        summary["total"] = len(issues)
        for issue in issues:
            summary[issue.severity.value] += 1
        return summary

    def _run_anomaly_checks(self, metrics: Dict[str, Any]) -> List[Anomaly]:
        try:
            return self._anomaly_detector.detect_all(metrics)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Anomaly detection failed: %s", exc)
            return []
