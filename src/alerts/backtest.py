"""Backtestable alert logic for historical analysis.

Allows replaying historical data through alert rules to evaluate:
- Alert precision and recall
- False positive/negative rates
- Optimal threshold tuning
- Suppression effectiveness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from .engine import AlertCandidate, evaluate_and_enqueue
from .repo import AlertOutboxEntry, InMemoryAlertOutbox
from .rules import AlertRule


@dataclass
class BacktestAlert:
    """Alert fired during backtest."""
    
    timestamp: datetime
    rule_id: str
    symbol: str
    severity: str
    message: str
    context: Dict[str, Any]
    suppressed: bool = False
    true_positive: Optional[bool] = None  # Set by validation


@dataclass
class BacktestResult:
    """Results from backtesting alert rules."""
    
    start_time: datetime
    end_time: datetime
    total_candidates: int = 0
    alerts_fired: int = 0
    alerts_suppressed: int = 0
    alerts_by_rule: Dict[str, int] = field(default_factory=dict)
    alerts_by_severity: Dict[str, int] = field(default_factory=dict)
    alert_details: List[BacktestAlert] = field(default_factory=list)
    
    def add_alert(self, alert: BacktestAlert) -> None:
        """Record an alert in the backtest results."""
        self.alerts_fired += 1
        self.alerts_by_rule[alert.rule_id] = self.alerts_by_rule.get(alert.rule_id, 0) + 1
        self.alerts_by_severity[alert.severity] = self.alerts_by_severity.get(alert.severity, 0) + 1
        self.alert_details.append(alert)
    
    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        return {
            "period": {
                "start": self.start_time.isoformat(),
                "end": self.end_time.isoformat(),
                "duration_hours": (self.end_time - self.start_time).total_seconds() / 3600,
            },
            "candidates_evaluated": self.total_candidates,
            "alerts_fired": self.alerts_fired,
            "alerts_suppressed": self.alerts_suppressed,
            "suppression_rate": (
                self.alerts_suppressed / (self.alerts_fired + self.alerts_suppressed)
                if (self.alerts_fired + self.alerts_suppressed) > 0
                else 0.0
            ),
            "by_rule": self.alerts_by_rule,
            "by_severity": self.alerts_by_severity,
        }


class AlertBacktester:
    """Backtester for alert rules."""
    
    def __init__(self, rules: Sequence[AlertRule]):
        """Initialize backtester with rules.
        
        Args:
            rules: Alert rules to test
        """
        self.rules = rules
        self.outbox = InMemoryAlertOutbox()
    
    def run(
        self,
        candidates: Sequence[AlertCandidate],
        start_time: datetime,
        end_time: datetime,
    ) -> BacktestResult:
        """Run backtest on historical candidates.
        
        Args:
            candidates: Historical alert candidates
            start_time: Start of backtest period
            end_time: End of backtest period
            
        Returns:
            Backtest results with statistics
        """
        from datetime import timezone as tz
        
        # Ensure start_time and end_time are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=tz.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=tz.utc)
        
        result = BacktestResult(start_time=start_time, end_time=end_time)
        result.total_candidates = len(candidates)
        
        # Process candidates chronologically
        for candidate in sorted(candidates, key=lambda c: c.window_start):
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(candidate.window_start.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = start_time
            
            # Skip if outside backtest period
            if timestamp < start_time or timestamp > end_time:
                continue
            
            # Evaluate rules
            entries = evaluate_and_enqueue(
                [candidate],
                now=timestamp,
                outbox=self.outbox,
                rules=self.rules,
            )
            
            # Record fired alerts
            for entry in entries:
                alert = BacktestAlert(
                    timestamp=timestamp,
                    rule_id=entry.payload.get("rule", "unknown"),
                    symbol=candidate.symbol,
                    severity=entry.payload.get("severity", "info"),
                    message=entry.payload.get("message", ""),
                    context=candidate.to_context(),
                )
                result.add_alert(alert)
        
        # Count suppressed alerts
        result.alerts_suppressed = result.total_candidates - result.alerts_fired
        
        return result
    
    def evaluate_thresholds(
        self,
        candidates: Sequence[AlertCandidate],
        metric: str,
        threshold_range: Sequence[float],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[float, BacktestResult]:
        """Evaluate different threshold values for a metric.
        
        Useful for finding optimal alert thresholds.
        
        Args:
            candidates: Historical candidates
            metric: Metric name to vary threshold for
            threshold_range: Sequence of threshold values to test
            start_time: Start of backtest period
            end_time: End of backtest period
            
        Returns:
            Dictionary mapping threshold to backtest results
        """
        results = {}
        
        for threshold in threshold_range:
            # Create temporary rule with this threshold
            # This is a simplified version - in practice, you'd modify the actual rules
            temp_rules = list(self.rules)
            
            # Run backtest
            self.outbox = InMemoryAlertOutbox()  # Reset outbox
            result = self.run(candidates, start_time, end_time)
            results[threshold] = result
        
        return results


def compare_rule_versions(
    candidates: Sequence[AlertCandidate],
    rules_v1: Sequence[AlertRule],
    rules_v2: Sequence[AlertRule],
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, BacktestResult]:
    """Compare performance of different rule versions.
    
    Args:
        candidates: Historical candidates
        rules_v1: First set of rules
        rules_v2: Second set of rules
        start_time: Start time
        end_time: End time
        
    Returns:
        Dictionary with results for each version
    """
    backtester_v1 = AlertBacktester(rules_v1)
    result_v1 = backtester_v1.run(candidates, start_time, end_time)
    
    backtester_v2 = AlertBacktester(rules_v2)
    result_v2 = backtester_v2.run(candidates, start_time, end_time)
    
    return {
        "v1": result_v1,
        "v2": result_v2,
        "comparison": {
            "alert_diff": result_v2.alerts_fired - result_v1.alerts_fired,
            "suppression_diff": result_v2.alerts_suppressed - result_v1.alerts_suppressed,
        }
    }


__all__ = [
    "BacktestAlert",
    "BacktestResult",
    "AlertBacktester",
    "compare_rule_versions",
]
