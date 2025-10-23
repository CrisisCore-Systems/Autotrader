"""
Compliance and Audit Trail System.

Implements comprehensive audit logging, trade execution tracking,
and regulatory compliance checks for live trading.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Audit event types."""
    TRADE_EXECUTION = "trade_execution"
    ORDER_PLACED = "order_placed"
    ORDER_MODIFIED = "order_modified"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    REBALANCE_TRIGGERED = "rebalance_triggered"
    RISK_LIMIT_BREACH = "risk_limit_breach"
    STRATEGY_ACTIVATION = "strategy_activation"
    STRATEGY_DEACTIVATION = "strategy_deactivation"
    PARAMETER_CHANGE = "parameter_change"
    MANUAL_INTERVENTION = "manual_intervention"
    SYSTEM_ERROR = "system_error"


class ComplianceStatus(Enum):
    """Compliance check status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class AuditEvent:
    """Single audit trail event."""
    event_id: str
    timestamp: datetime
    event_type: EventType
    user_id: Optional[str]
    session_id: Optional[str]
    details: Dict[str, Any]
    compliance_status: Optional[ComplianceStatus] = None
    checksum: Optional[str] = None
    
    def __post_init__(self):
        """Generate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._generate_checksum()
    
    def _generate_checksum(self) -> str:
        """Generate SHA-256 checksum for integrity verification."""
        data = {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'details': self.details,
            'compliance_status': self.compliance_status.value if self.compliance_status else None,
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify event has not been tampered with."""
        expected_checksum = self._generate_checksum()
        return self.checksum == expected_checksum
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'details': self.details,
            'compliance_status': self.compliance_status.value if self.compliance_status else None,
            'checksum': self.checksum,
        }


@dataclass
class TradeExecution:
    """Detailed trade execution record."""
    execution_id: str
    timestamp: datetime
    order_id: str
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: float
    price: float
    commission: float
    exchange: str
    execution_venue: str
    
    # Pre-trade validation
    pre_trade_checks: Dict[str, ComplianceStatus]
    
    # Post-trade analysis
    slippage: Optional[float] = None
    expected_price: Optional[float] = None
    market_impact: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'execution_id': self.execution_id,
            'timestamp': self.timestamp.isoformat(),
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'commission': self.commission,
            'exchange': self.exchange,
            'execution_venue': self.execution_venue,
            'pre_trade_checks': {k: v.value for k, v in self.pre_trade_checks.items()},
            'slippage': self.slippage,
            'expected_price': self.expected_price,
            'market_impact': self.market_impact,
        }


class ComplianceRule:
    """Base class for compliance rules."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def check(self, context: Dict) -> Tuple[ComplianceStatus, str]:
        """
        Check compliance rule.
        
        Args:
            context: Context information for the check
        
        Returns:
            Tuple of (status, message)
        """
        raise NotImplementedError


class PositionLimitRule(ComplianceRule):
    """Check position size limits."""
    
    def __init__(self, max_position_pct: float = 0.30):
        super().__init__(
            name="position_limit",
            description=f"Maximum position size: {max_position_pct:.0%}"
        )
        self.max_position_pct = max_position_pct
    
    def check(self, context: Dict) -> Tuple[ComplianceStatus, str]:
        """Check if position would exceed limit."""
        position_value = context.get('position_value', 0)
        portfolio_value = context.get('portfolio_value', 1)
        
        position_pct = position_value / portfolio_value if portfolio_value > 0 else 0
        
        if position_pct > self.max_position_pct:
            return ComplianceStatus.FAILED, f"Position {position_pct:.1%} exceeds limit {self.max_position_pct:.1%}"
        elif position_pct > self.max_position_pct * 0.9:
            return ComplianceStatus.WARNING, f"Position {position_pct:.1%} approaching limit"
        else:
            return ComplianceStatus.PASSED, "Position within limit"


class DailyLossLimitRule(ComplianceRule):
    """Check daily loss limits."""
    
    def __init__(self, max_daily_loss_pct: float = 0.02):
        super().__init__(
            name="daily_loss_limit",
            description=f"Maximum daily loss: {max_daily_loss_pct:.0%}"
        )
        self.max_daily_loss_pct = max_daily_loss_pct
    
    def check(self, context: Dict) -> Tuple[ComplianceStatus, str]:
        """Check if daily loss exceeds limit."""
        daily_pnl = context.get('daily_pnl', 0)
        portfolio_value = context.get('portfolio_value', 1)
        
        daily_return = daily_pnl / portfolio_value if portfolio_value > 0 else 0
        
        if daily_return < -self.max_daily_loss_pct:
            return ComplianceStatus.FAILED, f"Daily loss {daily_return:.1%} exceeds limit"
        elif daily_return < -self.max_daily_loss_pct * 0.8:
            return ComplianceStatus.WARNING, f"Daily loss {daily_return:.1%} approaching limit"
        else:
            return ComplianceStatus.PASSED, "Daily loss within limit"


class LiquidityRule(ComplianceRule):
    """Check minimum liquidity requirements."""
    
    def __init__(self, min_avg_daily_volume: float = 1000000):
        super().__init__(
            name="liquidity_requirement",
            description=f"Minimum average daily volume: ${min_avg_daily_volume:,.0f}"
        )
        self.min_avg_daily_volume = min_avg_daily_volume
    
    def check(self, context: Dict) -> Tuple[ComplianceStatus, str]:
        """Check if asset meets liquidity requirements."""
        avg_daily_volume = context.get('avg_daily_volume', 0)
        
        if avg_daily_volume < self.min_avg_daily_volume:
            return ComplianceStatus.FAILED, f"Liquidity ${avg_daily_volume:,.0f} below minimum"
        elif avg_daily_volume < self.min_avg_daily_volume * 1.5:
            return ComplianceStatus.WARNING, f"Liquidity ${avg_daily_volume:,.0f} marginal"
        else:
            return ComplianceStatus.PASSED, "Liquidity adequate"


class TradingHoursRule(ComplianceRule):
    """Check trading hours restrictions."""
    
    def __init__(
        self,
        allowed_start: str = "09:30",
        allowed_end: str = "16:00",
        timezone: str = "US/Eastern",
    ):
        super().__init__(
            name="trading_hours",
            description=f"Trading allowed {allowed_start}-{allowed_end} {timezone}"
        )
        self.allowed_start = allowed_start
        self.allowed_end = allowed_end
        self.timezone = timezone
    
    def check(self, context: Dict) -> Tuple[ComplianceStatus, str]:
        """Check if current time is within trading hours."""
        current_time = context.get('timestamp', datetime.now())
        
        # Parse allowed times (simplified - would need proper timezone handling)
        current_time_str = current_time.strftime("%H:%M")
        
        if self.allowed_start <= current_time_str <= self.allowed_end:
            return ComplianceStatus.PASSED, "Within trading hours"
        else:
            return ComplianceStatus.FAILED, f"Outside trading hours ({current_time_str})"


class ComplianceEngine:
    """
    Main compliance engine.
    
    Manages compliance rules and audit trail.
    """
    
    def __init__(self, audit_log_path: Optional[Path] = None):
        """
        Initialize compliance engine.
        
        Args:
            audit_log_path: Path to audit log file
        """
        self.rules: List[ComplianceRule] = []
        self.audit_trail: List[AuditEvent] = []
        self.audit_log_path = audit_log_path
        
        # Default rules
        self._add_default_rules()
        
        logger.info("Initialized compliance engine")
    
    def _add_default_rules(self):
        """Add default compliance rules."""
        self.add_rule(PositionLimitRule(max_position_pct=0.30))
        self.add_rule(DailyLossLimitRule(max_daily_loss_pct=0.02))
        self.add_rule(LiquidityRule(min_avg_daily_volume=1000000))
        self.add_rule(TradingHoursRule())
    
    def add_rule(self, rule: ComplianceRule):
        """Add a compliance rule."""
        self.rules.append(rule)
        logger.info(f"Added compliance rule: {rule.name}")
    
    def check_compliance(
        self,
        context: Dict,
        rules_to_check: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[ComplianceStatus, str]]:
        """
        Check all compliance rules.
        
        Args:
            context: Context information
            rules_to_check: Specific rules to check (None for all)
        
        Returns:
            Dict mapping rule names to (status, message)
        """
        results = {}
        
        for rule in self.rules:
            if rules_to_check is None or rule.name in rules_to_check:
                try:
                    status, message = rule.check(context)
                    results[rule.name] = (status, message)
                    
                    if status == ComplianceStatus.FAILED:
                        logger.warning(f"Compliance check failed: {rule.name} - {message}")
                    elif status == ComplianceStatus.WARNING:
                        logger.info(f"Compliance warning: {rule.name} - {message}")
                
                except Exception as e:
                    logger.error(f"Error checking rule {rule.name}: {e}")
                    results[rule.name] = (ComplianceStatus.SKIPPED, f"Error: {e}")
        
        return results
    
    def log_event(
        self,
        event_type: EventType,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        compliance_checks: Optional[Dict[str, Tuple[ComplianceStatus, str]]] = None,
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            details: Event details
            user_id: User ID
            session_id: Session ID
            compliance_checks: Results of compliance checks
        
        Returns:
            Created AuditEvent
        """
        # Generate unique event ID
        event_id = hashlib.sha256(
            f"{datetime.now().isoformat()}{event_type.value}{user_id}".encode()
        ).hexdigest()[:16]
        
        # Determine overall compliance status
        if compliance_checks:
            statuses = [status for status, _ in compliance_checks.values()]
            if ComplianceStatus.FAILED in statuses:
                overall_status = ComplianceStatus.FAILED
            elif ComplianceStatus.WARNING in statuses:
                overall_status = ComplianceStatus.WARNING
            else:
                overall_status = ComplianceStatus.PASSED
            
            # Add compliance results to details
            details['compliance_checks'] = {
                rule: {'status': status.value, 'message': msg}
                for rule, (status, msg) in compliance_checks.items()
            }
        else:
            overall_status = None
        
        # Create event
        event = AuditEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            details=details,
            compliance_status=overall_status,
        )
        
        # Add to trail
        self.audit_trail.append(event)
        
        # Write to file if configured
        if self.audit_log_path:
            self._write_to_log(event)
        
        logger.info(f"Logged audit event: {event_type.value} [{event_id}]")
        return event
    
    def _write_to_log(self, event: AuditEvent):
        """Write event to audit log file."""
        try:
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log_trade_execution(
        self,
        execution: TradeExecution,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Log a trade execution with full audit trail."""
        self.log_event(
            event_type=EventType.TRADE_EXECUTION,
            details=execution.to_dict(),
            user_id=user_id,
            session_id=session_id,
            compliance_checks={
                k: (v, "") for k, v in execution.pre_trade_checks.items()
            },
        )
    
    def verify_audit_trail(self) -> Tuple[bool, List[str]]:
        """
        Verify integrity of entire audit trail.
        
        Returns:
            Tuple of (all_valid, list_of_errors)
        """
        errors = []
        
        for i, event in enumerate(self.audit_trail):
            if not event.verify_integrity():
                errors.append(f"Event {i} ({event.event_id}) failed integrity check")
        
        all_valid = len(errors) == 0
        
        if all_valid:
            logger.info(f"Audit trail verified: {len(self.audit_trail)} events")
        else:
            logger.error(f"Audit trail verification failed: {len(errors)} errors")
        
        return all_valid, errors
    
    def get_events(
        self,
        event_types: Optional[List[EventType]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
    ) -> List[AuditEvent]:
        """
        Query audit trail.
        
        Args:
            event_types: Filter by event types
            start_time: Filter by start time
            end_time: Filter by end time
            user_id: Filter by user ID
        
        Returns:
            Filtered list of events
        """
        filtered = self.audit_trail
        
        if event_types:
            filtered = [e for e in filtered if e.event_type in event_types]
        
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]
        
        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        
        return filtered
    
    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict:
        """
        Generate compliance report for a period.
        
        Args:
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Compliance report dictionary
        """
        events = self.get_events(start_time=start_date, end_time=end_date)
        
        # Count events by type
        event_counts = {}
        for event in events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Count compliance statuses
        compliance_counts = {
            ComplianceStatus.PASSED: 0,
            ComplianceStatus.FAILED: 0,
            ComplianceStatus.WARNING: 0,
            ComplianceStatus.SKIPPED: 0,
        }
        
        for event in events:
            if event.compliance_status:
                compliance_counts[event.compliance_status] += 1
        
        # Get failed compliance checks
        failed_checks = [
            event for event in events
            if event.compliance_status == ComplianceStatus.FAILED
        ]
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'total_events': len(events),
            'event_counts': event_counts,
            'compliance_summary': {
                'passed': compliance_counts[ComplianceStatus.PASSED],
                'failed': compliance_counts[ComplianceStatus.FAILED],
                'warnings': compliance_counts[ComplianceStatus.WARNING],
                'skipped': compliance_counts[ComplianceStatus.SKIPPED],
            },
            'failed_checks': [e.to_dict() for e in failed_checks],
        }
    
    def export_audit_trail(self, output_path: Path, format: str = 'json'):
        """
        Export audit trail to file.
        
        Args:
            output_path: Output file path
            format: Export format ('json' or 'csv')
        """
        if format == 'json':
            with open(output_path, 'w') as f:
                json.dump([e.to_dict() for e in self.audit_trail], f, indent=2)
        
        elif format == 'csv':
            df = pd.DataFrame([e.to_dict() for e in self.audit_trail])
            df.to_csv(output_path, index=False)
        
        else:
            raise ValueError(f"Unknown format: {format}")
        
        logger.info(f"Exported {len(self.audit_trail)} events to {output_path}")
