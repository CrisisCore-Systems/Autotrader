"""
Guardrails Module
==================

Hard limit enforcement and validation for LLM decisions.

This module implements:
- Hard limit validation (unoverridable by LLM)
- Schema validation (Pydantic)
- Action validation (programmatic checks)
- Latency monitoring
- Audit logging

Key Principles:
- LLM cannot override hard limits
- All outputs validated before use
- All actions logged for audit
- Fail-safe: reject on validation failure

Example
-------
>>> from autotrader.llm.guardrails import GuardrailSystem, HardLimits
>>> 
>>> limits = HardLimits(max_daily_loss=1000, max_position_size=5000)
>>> guardrails = GuardrailSystem(limits)
>>> 
>>> # Validate LLM decision
>>> is_valid = guardrails.validate_action(
...     action={'size': 3000, 'symbol': 'BTCUSDT'},
...     current_state=strategy_state
... )
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import hashlib
from pathlib import Path


class GuardrailViolation(Exception):
    """Exception raised when guardrail is violated."""
    pass


class ViolationType(Enum):
    """Types of guardrail violations."""
    HARD_LIMIT = "hard_limit"
    SCHEMA = "schema"
    ACTION = "action"
    LATENCY = "latency"
    OVERRIDE_ATTEMPT = "override_attempt"


@dataclass
class HardLimits:
    """
    Hard limits that LLM cannot override.
    
    These are programmatically enforced and unmodifiable by LLM.
    
    Attributes
    ----------
    max_daily_loss : float
        Maximum daily loss (absolute)
    max_position_size : float
        Maximum position size per symbol
    max_leverage : float
        Maximum leverage allowed
    circuit_breaker_losses : int
        Consecutive losses to trigger halt
    max_correlation : float
        Maximum portfolio correlation
    max_concurrent_positions : int
        Maximum simultaneous positions
    max_gross_exposure : float
        Maximum gross exposure
    max_net_exposure : float
        Maximum net exposure
    """
    max_daily_loss: float = 10000.0
    max_position_size: float = 100000.0
    max_leverage: float = 3.0
    circuit_breaker_losses: int = 5
    max_correlation: float = 0.70
    max_concurrent_positions: int = 20
    max_gross_exposure: float = float('inf')
    max_net_exposure: float = float('inf')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'max_daily_loss': self.max_daily_loss,
            'max_position_size': self.max_position_size,
            'max_leverage': self.max_leverage,
            'circuit_breaker_losses': self.circuit_breaker_losses,
            'max_correlation': self.max_correlation,
            'max_concurrent_positions': self.max_concurrent_positions,
            'max_gross_exposure': self.max_gross_exposure,
            'max_net_exposure': self.max_net_exposure
        }


@dataclass
class AuditLogEntry:
    """
    Audit log entry for LLM interaction.
    
    Attributes
    ----------
    timestamp : datetime
        When interaction occurred
    tool_name : str
        Which tool was used
    input_hash : str
        SHA256 hash of inputs
    output : dict
        LLM output (validated)
    validation_result : bool
        Whether validation passed
    action_taken : str
        What action resulted
    override_attempted : bool
        Whether LLM tried to override limits
    violations : list
        Any violations detected
    latency_ms : float
        Execution latency
    """
    timestamp: datetime
    tool_name: str
    input_hash: str
    output: Dict[str, Any]
    validation_result: bool
    action_taken: str
    override_attempted: bool = False
    violations: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'tool_name': self.tool_name,
            'input_hash': self.input_hash,
            'output': self.output,
            'validation_result': self.validation_result,
            'action_taken': self.action_taken,
            'override_attempted': self.override_attempted,
            'violations': self.violations,
            'latency_ms': self.latency_ms
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class HardLimitValidator:
    """
    Validate actions against hard limits.
    
    These limits are unoverridable by LLM.
    
    Example
    -------
    >>> validator = HardLimitValidator(limits)
    >>> validator.check_position_size('BTCUSDT', 3000)  # OK
    >>> validator.check_position_size('BTCUSDT', 150000)  # Raises GuardrailViolation
    """
    
    def __init__(self, limits: HardLimits):
        self.limits = limits
        self.violation_count = 0
        self.violations_by_type: Dict[str, int] = {}
    
    def check_daily_loss(self, current_loss: float) -> bool:
        """
        Check if daily loss exceeds limit.
        
        Parameters
        ----------
        current_loss : float
            Current daily loss (positive = loss)
        
        Returns
        -------
        is_valid : bool
            True if within limit
        """
        if current_loss >= self.limits.max_daily_loss:
            self._record_violation('daily_loss')
            return False
        return True
    
    def check_position_size(self, symbol: str, size: float) -> bool:
        """
        Check if position size exceeds limit.
        
        Parameters
        ----------
        symbol : str
            Trading symbol
        size : float
            Position size (absolute)
        
        Returns
        -------
        is_valid : bool
            True if within limit
        """
        if abs(size) > self.limits.max_position_size:
            self._record_violation('position_size')
            return False
        return True
    
    def check_leverage(self, leverage: float) -> bool:
        """
        Check if leverage exceeds limit.
        
        Parameters
        ----------
        leverage : float
            Leverage ratio
        
        Returns
        -------
        is_valid : bool
            True if within limit
        """
        if leverage > self.limits.max_leverage:
            self._record_violation('leverage')
            return False
        return True
    
    def check_concurrent_positions(self, num_positions: int) -> bool:
        """Check concurrent position limit."""
        if num_positions >= self.limits.max_concurrent_positions:
            self._record_violation('concurrent_positions')
            return False
        return True
    
    def check_correlation(self, correlation: float) -> bool:
        """Check portfolio correlation limit."""
        if correlation > self.limits.max_correlation:
            self._record_violation('correlation')
            return False
        return True
    
    def check_exposure(
        self,
        gross_exposure: float,
        net_exposure: float
    ) -> bool:
        """Check exposure limits."""
        if gross_exposure > self.limits.max_gross_exposure:
            self._record_violation('gross_exposure')
            return False
        
        if abs(net_exposure) > self.limits.max_net_exposure:
            self._record_violation('net_exposure')
            return False
        
        return True
    
    def _record_violation(self, violation_type: str):
        """Record a violation."""
        self.violation_count += 1
        self.violations_by_type[violation_type] = (
            self.violations_by_type.get(violation_type, 0) + 1
        )
    
    def get_violation_stats(self) -> Dict[str, int]:
        """Get violation statistics."""
        return {
            'total': self.violation_count,
            'by_type': self.violations_by_type.copy()
        }


class ActionValidator:
    """
    Validate LLM-proposed actions.
    
    Programmatic validation that LLM cannot bypass.
    
    Example
    -------
    >>> validator = ActionValidator(strategy, limits)
    >>> action = {'symbol': 'BTCUSDT', 'size': 1000, 'action': 'EXECUTE'}
    >>> is_valid = validator.validate(action, current_state)
    """
    
    def __init__(self, hard_limits: HardLimits):
        self.hard_limits = hard_limits
        self.hard_limit_validator = HardLimitValidator(hard_limits)
    
    def validate_pretrade_decision(
        self,
        decision: str,
        risk_headroom: float,
        edge_cost_ratio: float
    ) -> bool:
        """
        Validate pre-trade decision logic.
        
        Enforces:
        - Must HALT if risk_headroom < 0.10
        - Must HALT if edge < cost
        """
        violations = []
        
        # Check risk headroom
        if risk_headroom < 0.10 and decision != 'HALT':
            violations.append('Must HALT when risk_headroom < 10%')
        
        # Check edge vs cost
        if edge_cost_ratio < 1.0 and decision != 'HALT':
            violations.append('Must HALT when edge < cost')
        
        if violations:
            raise GuardrailViolation(
                f"Pre-trade decision violations: {violations}"
            )
        
        return True
    
    def validate_execution_action(
        self,
        action: str,
        constraint_checks: Dict[str, bool],
        position_size: float,
        current_state: Dict[str, Any]
    ) -> bool:
        """
        Validate execution action.
        
        Enforces:
        - Cannot EXECUTE if any constraint violated
        - Position size within limits
        - Risk limits respected
        """
        violations = []
        
        # Check constraints
        if action == 'EXECUTE':
            violated = [k for k, v in constraint_checks.items() if not v]
            if violated:
                violations.append(f"Constraints violated: {violated}")
        
        # Check position size
        if not self.hard_limit_validator.check_position_size('', position_size):
            violations.append(f"Position size {position_size} exceeds limit")
        
        # Check daily loss
        daily_loss = current_state.get('daily_loss', 0)
        if not self.hard_limit_validator.check_daily_loss(daily_loss):
            violations.append(f"Daily loss {daily_loss} exceeds limit")
        
        # Check concurrent positions
        num_positions = current_state.get('num_positions', 0)
        if action == 'EXECUTE':
            if not self.hard_limit_validator.check_concurrent_positions(num_positions + 1):
                violations.append(f"Would exceed max concurrent positions")
        
        if violations:
            raise GuardrailViolation(
                f"Execution action violations: {violations}"
            )
        
        return True


class LatencyMonitor:
    """
    Monitor LLM call latency.
    
    Tracks p50, p99, p999 latencies and alerts on violations.
    
    Example
    -------
    >>> monitor = LatencyMonitor(timeout_ms=1000)
    >>> with monitor.measure('pretrade_checklist'):
    ...     result = llm.complete(prompt)
    >>> stats = monitor.get_stats()
    """
    
    def __init__(self, timeout_ms: float = 1000.0, alert_threshold_ms: float = 500.0):
        self.timeout_ms = timeout_ms
        self.alert_threshold_ms = alert_threshold_ms
        
        self.latencies: List[float] = []
        self.timeouts = 0
        self.alerts = 0
    
    def record(self, latency_ms: float) -> bool:
        """
        Record latency measurement.
        
        Parameters
        ----------
        latency_ms : float
            Latency in milliseconds
        
        Returns
        -------
        is_timeout : bool
            True if latency exceeded timeout
        """
        self.latencies.append(latency_ms)
        
        # Check timeout
        if latency_ms >= self.timeout_ms:
            self.timeouts += 1
            return True
        
        # Check alert threshold
        if latency_ms >= self.alert_threshold_ms:
            self.alerts += 1
        
        return False
    
    def get_stats(self) -> Dict[str, float]:
        """
        Get latency statistics.
        
        Returns
        -------
        stats : dict
            p50, p99, p999, mean, max, timeouts, alerts
        """
        if not self.latencies:
            return {
                'p50': 0, 'p99': 0, 'p999': 0,
                'mean': 0, 'max': 0,
                'timeouts': 0, 'alerts': 0,
                'count': 0
            }
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            'p50': sorted_latencies[int(n * 0.50)],
            'p99': sorted_latencies[int(n * 0.99)] if n > 100 else sorted_latencies[-1],
            'p999': sorted_latencies[int(n * 0.999)] if n > 1000 else sorted_latencies[-1],
            'mean': sum(self.latencies) / n,
            'max': max(self.latencies),
            'timeouts': self.timeouts,
            'alerts': self.alerts,
            'count': n
        }


class AuditLogger:
    """
    Audit logging for LLM interactions.
    
    Logs all inputs, outputs, validations, and violations.
    
    Example
    -------
    >>> logger = AuditLogger('logs/llm_audit.jsonl')
    >>> logger.log_interaction(
    ...     tool_name='pretrade_checklist',
    ...     inputs={'volatility': 0.02},
    ...     output={'decision': 'PROCEED'},
    ...     validation_passed=True
    ... )
    """
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self.logs: List[AuditLogEntry] = []
        
        # Ensure log directory exists
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    def log_interaction(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        output: Dict[str, Any],
        validation_passed: bool,
        action_taken: str,
        override_attempted: bool = False,
        violations: Optional[List[str]] = None,
        latency_ms: float = 0.0
    ):
        """
        Log LLM interaction.
        
        Parameters
        ----------
        tool_name : str
            Name of tool used
        inputs : dict
            Tool inputs
        output : dict
            LLM output
        validation_passed : bool
            Whether validation succeeded
        action_taken : str
            What action resulted
        override_attempted : bool
            Whether LLM tried to bypass limits
        violations : list, optional
            Any violations detected
        latency_ms : float
            Execution latency
        """
        # Hash inputs for audit trail
        input_str = json.dumps(inputs, sort_keys=True)
        input_hash = hashlib.sha256(input_str.encode()).hexdigest()[:16]
        
        entry = AuditLogEntry(
            timestamp=datetime.now(),
            tool_name=tool_name,
            input_hash=input_hash,
            output=output,
            validation_result=validation_passed,
            action_taken=action_taken,
            override_attempted=override_attempted,
            violations=violations or [],
            latency_ms=latency_ms
        )
        
        self.logs.append(entry)
        
        # Write to file if configured
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(entry.to_json() + '\n')
    
    def get_violation_summary(self) -> Dict[str, int]:
        """Get summary of violations."""
        summary = {
            'total_interactions': len(self.logs),
            'validation_failures': sum(1 for log in self.logs if not log.validation_result),
            'override_attempts': sum(1 for log in self.logs if log.override_attempted),
            'violations_by_tool': {}
        }
        
        for log in self.logs:
            if log.violations:
                tool = log.tool_name
                summary['violations_by_tool'][tool] = (
                    summary['violations_by_tool'].get(tool, 0) + len(log.violations)
                )
        
        return summary


class GuardrailSystem:
    """
    Main guardrail system coordinating all validators.
    
    Integrates:
    - Hard limit validation
    - Action validation
    - Latency monitoring
    - Audit logging
    
    Example
    -------
    >>> limits = HardLimits(max_daily_loss=1000)
    >>> guardrails = GuardrailSystem(limits, log_file='logs/audit.jsonl')
    >>> 
    >>> # Validate LLM action
    >>> is_valid = guardrails.validate_and_log(
    ...     tool_name='execution_planner',
    ...     inputs=inputs,
    ...     output=llm_output,
    ...     current_state=state
    ... )
    """
    
    def __init__(
        self,
        hard_limits: HardLimits,
        log_file: Optional[str] = None,
        timeout_ms: float = 1000.0
    ):
        self.hard_limits = hard_limits
        
        # Initialize components
        self.limit_validator = HardLimitValidator(hard_limits)
        self.action_validator = ActionValidator(hard_limits)
        self.latency_monitor = LatencyMonitor(timeout_ms=timeout_ms)
        self.audit_logger = AuditLogger(log_file=log_file)
    
    def validate_and_log(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        output: Dict[str, Any],
        current_state: Dict[str, Any],
        latency_ms: float
    ) -> bool:
        """
        Validate LLM output and log interaction.
        
        Parameters
        ----------
        tool_name : str
            Tool that was used
        inputs : dict
            Tool inputs
        output : dict
            LLM output (already schema-validated)
        current_state : dict
            Current strategy state
        latency_ms : float
            Execution latency
        
        Returns
        -------
        is_valid : bool
            True if all validations pass
        """
        validation_passed = True
        violations = []
        override_attempted = False
        action_taken = 'REJECTED'
        
        try:
            # Record latency
            is_timeout = self.latency_monitor.record(latency_ms)
            if is_timeout:
                violations.append(f"Timeout: {latency_ms}ms > {self.latency_monitor.timeout_ms}ms")
                validation_passed = False
            
            # Tool-specific validation
            if tool_name == 'pretrade_checklist':
                self.action_validator.validate_pretrade_decision(
                    decision=output['decision'],
                    risk_headroom=output['risk_headroom_pct'],
                    edge_cost_ratio=output['edge_vs_cost_ratio']
                )
                action_taken = output['decision']
            
            elif tool_name == 'execution_planner':
                self.action_validator.validate_execution_action(
                    action=output['action'],
                    constraint_checks=output['constraint_checks'],
                    position_size=output['execution_plan'].get('size', 0),
                    current_state=current_state
                )
                action_taken = output['action']
            
            else:
                action_taken = 'LOGGED'
        
        except GuardrailViolation as e:
            validation_passed = False
            violations.append(str(e))
            override_attempted = True
        
        except Exception as e:
            validation_passed = False
            violations.append(f"Unexpected error: {str(e)}")
        
        # Log interaction
        self.audit_logger.log_interaction(
            tool_name=tool_name,
            inputs=inputs,
            output=output,
            validation_passed=validation_passed,
            action_taken=action_taken,
            override_attempted=override_attempted,
            violations=violations,
            latency_ms=latency_ms
        )
        
        return validation_passed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive guardrail statistics."""
        return {
            'hard_limits': self.hard_limits.to_dict(),
            'limit_violations': self.limit_validator.get_violation_stats(),
            'latency': self.latency_monitor.get_stats(),
            'audit': self.audit_logger.get_violation_summary()
        }


# Export public API
__all__ = [
    'GuardrailSystem',
    'HardLimits',
    'HardLimitValidator',
    'ActionValidator',
    'LatencyMonitor',
    'AuditLogger',
    'AuditLogEntry',
    'GuardrailViolation',
    'ViolationType',
]
