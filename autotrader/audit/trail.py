"""
Audit Trail System - Phase 12
Complete event capture for compliance and forensic analysis
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import logging
from pathlib import Path

import pandas as pd


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of audit events"""
    MARKET_DATA = "market_data"
    SIGNAL = "signal"
    RISK_CHECK = "risk_check"
    ORDER = "order"
    FILL = "fill"
    LLM_DECISION = "llm_decision"
    POSITION_UPDATE = "position_update"
    CIRCUIT_BREAKER = "circuit_breaker"
    SYSTEM_EVENT = "system_event"


class RiskCheckStatus(Enum):
    """Risk check result status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class MarketDataSnapshot:
    """Market data snapshot for audit trail"""
    timestamp: datetime
    instrument: str
    bid: float
    ask: float
    mid: float
    spread_bps: float
    volume: float
    orderbook_depth: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class SignalEvent:
    """Trading signal event for audit trail"""
    timestamp: datetime
    signal_id: str
    instrument: str
    signal_type: str
    signal_strength: float
    prediction: float
    confidence: float
    model_version: str
    features: Dict[str, float]
    expected_return: Optional[float] = None
    expected_sharpe: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class RiskCheck:
    """Individual risk check result"""
    name: str
    status: RiskCheckStatus
    value: float
    limit: float
    message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'status': self.status.value,
            'value': self.value,
            'limit': self.limit,
            'message': self.message
        }


@dataclass
class RiskCheckEvent:
    """Risk check event for audit trail"""
    timestamp: datetime
    signal_id: str
    instrument: str
    checks: List[RiskCheck]
    decision: str  # approve, reject, modify
    risk_score: float
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'signal_id': self.signal_id,
            'instrument': self.instrument,
            'checks': [check.to_dict() for check in self.checks],
            'decision': self.decision,
            'risk_score': self.risk_score,
            'reason': self.reason
        }


@dataclass
class OrderEvent:
    """Order event for audit trail"""
    timestamp: datetime
    order_id: str
    signal_id: str
    instrument: str
    side: str  # buy, sell
    quantity: float
    order_type: str  # market, limit, stop
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str = "submitted"  # submitted, filled, cancelled, rejected
    exchange_order_id: Optional[str] = None
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class FillEvent:
    """Fill event for audit trail"""
    timestamp: datetime
    fill_id: str
    order_id: str
    instrument: str
    side: str
    quantity: float
    price: float
    fee: float
    fee_currency: str
    liquidity: str  # maker, taker
    slippage_bps: float
    market_price_at_fill: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class LLMDecisionEvent:
    """LLM decision event for audit trail"""
    timestamp: datetime
    signal_id: str
    instrument: str
    llm_model: str
    prompt: str
    response: str
    reasoning: str
    confidence: float
    decision: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class PositionUpdateEvent:
    """Position update event for audit trail"""
    timestamp: datetime
    instrument: str
    previous_quantity: float
    new_quantity: float
    average_price: float
    unrealized_pnl: float
    realized_pnl: float
    reason: str  # fill, adjustment, liquidation
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class CircuitBreakerEvent:
    """Circuit breaker event for audit trail"""
    timestamp: datetime
    trigger_type: str  # daily_loss, drawdown, error_rate
    trigger_value: float
    threshold: float
    action: str  # halt, reduce, monitor
    affected_instruments: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AuditTrailStore:
    """
    Audit trail storage and retrieval system
    Stores all trading events for compliance and forensic analysis
    """
    
    def __init__(self, storage_path: str = "data/audit"):
        """
        Initialize audit trail store
        
        Args:
            storage_path: Path to store audit trail files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory buffer for recent events (last 1000)
        self.event_buffer: List[Dict] = []
        self.buffer_size = 1000
        
        logger.info(f"Audit trail store initialized at {self.storage_path}")
    
    def record_market_data(self, snapshot: MarketDataSnapshot) -> None:
        """Record market data snapshot"""
        event = {
            'event_type': EventType.MARKET_DATA.value,
            'data': snapshot.to_dict()
        }
        self._store_event(event)
    
    def record_signal(self, signal: SignalEvent) -> None:
        """Record trading signal"""
        event = {
            'event_type': EventType.SIGNAL.value,
            'data': signal.to_dict()
        }
        self._store_event(event)
    
    def record_risk_check(self, risk_check: RiskCheckEvent) -> None:
        """Record risk check"""
        event = {
            'event_type': EventType.RISK_CHECK.value,
            'data': risk_check.to_dict()
        }
        self._store_event(event)
    
    def record_order(self, order: OrderEvent) -> None:
        """Record order event"""
        event = {
            'event_type': EventType.ORDER.value,
            'data': order.to_dict()
        }
        self._store_event(event)
    
    def record_fill(self, fill: FillEvent) -> None:
        """Record fill event"""
        event = {
            'event_type': EventType.FILL.value,
            'data': fill.to_dict()
        }
        self._store_event(event)
    
    def record_llm_decision(self, decision: LLMDecisionEvent) -> None:
        """Record LLM decision"""
        event = {
            'event_type': EventType.LLM_DECISION.value,
            'data': decision.to_dict()
        }
        self._store_event(event)
    
    def record_position_update(self, update: PositionUpdateEvent) -> None:
        """Record position update"""
        event = {
            'event_type': EventType.POSITION_UPDATE.value,
            'data': update.to_dict()
        }
        self._store_event(event)
    
    def record_circuit_breaker(self, cb_event: CircuitBreakerEvent) -> None:
        """Record circuit breaker event"""
        event = {
            'event_type': EventType.CIRCUIT_BREAKER.value,
            'data': cb_event.to_dict()
        }
        self._store_event(event)
    
    def _store_event(self, event: Dict) -> None:
        """
        Store event to buffer and persistent storage
        
        Args:
            event: Event dictionary to store
        """
        # Add to in-memory buffer
        self.event_buffer.append(event)
        if len(self.event_buffer) > self.buffer_size:
            self.event_buffer.pop(0)
        
        # Write to persistent storage (append to daily file)
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = self.storage_path / f"audit_{date_str}.jsonl"
        
        try:
            with open(file_path, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")
    
    def query_events(
        self,
        event_type: Optional[EventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        instrument: Optional[str] = None,
        signal_id: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Query audit trail events
        
        Args:
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            instrument: Filter by instrument
            signal_id: Filter by signal ID
            order_id: Filter by order ID
        
        Returns:
            List of matching events
        """
        events = []
        
        # Determine which files to scan
        if start_time and end_time:
            date_range = pd.date_range(start=start_time, end=end_time, freq='D')
            files_to_scan = [
                self.storage_path / f"audit_{date.strftime('%Y-%m-%d')}.jsonl"
                for date in date_range
            ]
        else:
            files_to_scan = list(self.storage_path.glob("audit_*.jsonl"))
        
        # Read and filter events
        for file_path in files_to_scan:
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        event = json.loads(line)
                        
                        # Apply filters
                        if event_type and event['event_type'] != event_type.value:
                            continue
                        
                        event_data = event['data']
                        event_time = datetime.fromisoformat(event_data['timestamp'])
                        
                        if start_time and event_time < start_time:
                            continue
                        if end_time and event_time > end_time:
                            continue
                        
                        if instrument and event_data.get('instrument') != instrument:
                            continue
                        if signal_id and event_data.get('signal_id') != signal_id:
                            continue
                        if order_id and event_data.get('order_id') != order_id:
                            continue
                        
                        events.append(event)
            
            except Exception as e:
                logger.error(f"Failed to read audit file {file_path}: {e}")
        
        return events
    
    def reconstruct_trade_history(self, signal_id: str) -> Dict[str, List[Dict]]:
        """
        Reconstruct complete history for a trade
        
        Args:
            signal_id: Signal ID to trace
        
        Returns:
            Dictionary with all related events by type
        """
        events = self.query_events(signal_id=signal_id)
        
        history = {
            'signal': [],
            'risk_checks': [],
            'orders': [],
            'fills': [],
            'llm_decisions': [],
            'position_updates': []
        }
        
        for event in events:
            event_type = event['event_type']
            if event_type == EventType.SIGNAL.value:
                history['signal'].append(event)
            elif event_type == EventType.RISK_CHECK.value:
                history['risk_checks'].append(event)
            elif event_type == EventType.ORDER.value:
                history['orders'].append(event)
            elif event_type == EventType.FILL.value:
                history['fills'].append(event)
            elif event_type == EventType.LLM_DECISION.value:
                history['llm_decisions'].append(event)
            elif event_type == EventType.POSITION_UPDATE.value:
                history['position_updates'].append(event)
        
        return history
    
    def get_recent_events(self, count: int = 100) -> List[Dict]:
        """
        Get most recent events from buffer
        
        Args:
            count: Number of events to retrieve
        
        Returns:
            List of recent events
        """
        return self.event_buffer[-count:]
    
    def export_to_dataframe(
        self,
        event_type: EventType,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Export events to pandas DataFrame
        
        Args:
            event_type: Type of events to export
            start_time: Start time filter
            end_time: End time filter
        
        Returns:
            DataFrame of events
        """
        events = self.query_events(
            event_type=event_type,
            start_time=start_time,
            end_time=end_time
        )
        
        if not events:
            return pd.DataFrame()
        
        # Extract data from events
        data = [event['data'] for event in events]
        df = pd.DataFrame(data)
        
        # Convert timestamp to datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate compliance report for date range
        
        Args:
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Compliance report dictionary
        """
        # Query all events in range
        all_events = self.query_events(start_time=start_date, end_time=end_date)
        
        # Count events by type
        event_counts = {}
        for event in all_events:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Get risk check failures
        risk_events = [e for e in all_events if e['event_type'] == EventType.RISK_CHECK.value]
        risk_failures = [
            e for e in risk_events
            if e['data']['decision'] == 'reject'
        ]
        
        # Get circuit breaker events
        cb_events = [e for e in all_events if e['event_type'] == EventType.CIRCUIT_BREAKER.value]
        
        report = {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'total_events': len(all_events),
            'events_by_type': event_counts,
            'risk_checks': {
                'total': len(risk_events),
                'failures': len(risk_failures),
                'failure_rate': len(risk_failures) / len(risk_events) if risk_events else 0
            },
            'circuit_breakers': {
                'triggered': len(cb_events),
                'events': [e['data'] for e in cb_events]
            },
            'generated_at': datetime.now().isoformat()
        }
        
        return report


# Global audit trail instance
_audit_trail: Optional[AuditTrailStore] = None


def get_audit_trail() -> AuditTrailStore:
    """Get global audit trail instance"""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = AuditTrailStore()
    return _audit_trail
