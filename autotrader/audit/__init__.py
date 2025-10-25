"""
Audit module - Phase 12
Complete audit trail and compliance tracking
"""

from .trail import (
    AuditTrailStore,
    EventType,
    MarketDataSnapshot,
    SignalEvent,
    RiskCheck,
    RiskCheckEvent,
    RiskCheckStatus,
    OrderEvent,
    FillEvent,
    LLMDecisionEvent,
    PositionUpdateEvent,
    CircuitBreakerEvent,
    get_audit_trail
)

__all__ = [
    'AuditTrailStore',
    'EventType',
    'MarketDataSnapshot',
    'SignalEvent',
    'RiskCheck',
    'RiskCheckEvent',
    'RiskCheckStatus',
    'OrderEvent',
    'FillEvent',
    'LLMDecisionEvent',
    'PositionUpdateEvent',
    'CircuitBreakerEvent',
    'get_audit_trail'
]
