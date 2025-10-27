"""
Trading Strategy Orchestrator
==============================

Main integration layer for the complete trading strategy.

This module integrates:
- Signal generation (Phase 8.1)
- Position sizing (Phase 8.2)
- Risk controls (Phase 8.3)
- Portfolio management (Phase 8.4)

Flow: Model Predictions → Signals → Position Sizes → Risk Checks → Portfolio Checks → Execution

Key Classes
-----------
StrategyConfig : Complete strategy configuration
TradingStrategy : Main orchestrator class
StrategyState : Current strategy state
ExecutionDecision : Final trade decision

Example
-------
>>> from autotrader.strategy import TradingStrategy, StrategyConfig
>>> 
>>> config = StrategyConfig.from_yaml('strategy_config.yaml')
>>> strategy = TradingStrategy(config)
>>> 
>>> # Process model predictions
>>> decision = strategy.process_signal(
...     symbol='BTCUSDT',
...     probability=0.62,
...     expected_value=50,
...     market_data=market_data,
...     equity=100000
... )
>>> 
>>> if decision.action != 'HOLD':
...     # Execute trade
...     execute_order(decision)
...     strategy.record_execution(decision)
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import pandas as pd
import yaml
import json
from pathlib import Path

# Import all strategy components
from autotrader.strategy.signals import (
    SignalGenerator, SignalConfig, Signal, SignalDirection, Position
)
from autotrader.strategy.sizing import (
    PositionSizer, SizingConfig, PositionSize
)
from autotrader.strategy.risk import (
    RiskManager, RiskConfig, TradeRecord
)
from autotrader.strategy.portfolio import (
    PortfolioManager, PortfolioConfig, PortfolioStatus
)


class StrategyStatus(Enum):
    """Overall strategy status."""
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    RISK_HALT = "risk_halt"
    CIRCUIT_BREAKER = "circuit_breaker"
    DRAWDOWN_HALT = "drawdown_halt"


@dataclass
class ExecutionDecision:
    """
    Final execution decision.
    
    Attributes
    ----------
    action : str
        'LONG', 'SHORT', 'HOLD', 'CLOSE'
    symbol : str
        Trading symbol
    size : float
        Position size (0 if HOLD)
    confidence : float
        Signal confidence
    timestamp : datetime
        Decision timestamp
    metadata : dict
        Additional information (signal, sizing, risk checks)
    """
    action: str
    symbol: str
    size: float
    confidence: float
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class StrategyState:
    """
    Current strategy state.
    
    Tracks all open positions, performance metrics, and status.
    """
    status: StrategyStatus = StrategyStatus.ACTIVE
    equity: float = 0.0
    peak_equity: float = 0.0
    current_drawdown: float = 0.0
    
    open_positions: Dict[str, Position] = field(default_factory=dict)
    closed_positions: List[TradeRecord] = field(default_factory=list)
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    total_fees: float = 0.0
    
    last_update: Optional[datetime] = None


@dataclass
class StrategyConfig:
    """
    Complete strategy configuration.
    
    Combines all component configurations.
    """
    # Component configs
    signals: SignalConfig = field(default_factory=SignalConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    
    # Global settings
    strategy_name: str = "AutoTrader"
    description: str = ""
    
    # Logging
    log_level: str = "INFO"
    log_decisions: bool = True
    log_file: Optional[str] = None
    
    @classmethod
    def from_yaml(cls, path: str) -> 'StrategyConfig':
        """
        Load configuration from YAML file.
        
        Parameters
        ----------
        path : str
            Path to YAML config file
        
        Returns
        -------
        config : StrategyConfig
            Loaded configuration
        """
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Parse component configs
        signals = SignalConfig(**data.get('signals', {}))
        sizing = SizingConfig(**data.get('sizing', {}))
        risk = RiskConfig(**data.get('risk', {}))
        portfolio = PortfolioConfig(**data.get('portfolio', {}))
        
        return cls(
            signals=signals,
            sizing=sizing,
            risk=risk,
            portfolio=portfolio,
            strategy_name=data.get('strategy_name', 'AutoTrader'),
            description=data.get('description', ''),
            log_level=data.get('log_level', 'INFO'),
            log_decisions=data.get('log_decisions', True),
            log_file=data.get('log_file')
        )
    
    def to_yaml(self, path: str):
        """Save configuration to YAML file."""
        data = {
            'strategy_name': self.strategy_name,
            'description': self.description,
            'signals': asdict(self.signals),
            'sizing': asdict(self.sizing),
            'risk': asdict(self.risk),
            'portfolio': asdict(self.portfolio),
            'log_level': self.log_level,
            'log_decisions': self.log_decisions,
            'log_file': self.log_file
        }
        
        with open(path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)


class TradingStrategy:
    """
    Main trading strategy orchestrator.
    
    Integrates all components into complete trading system.
    
    Parameters
    ----------
    config : StrategyConfig
        Strategy configuration
    initial_equity : float
        Starting equity
    
    Example
    -------
    >>> config = StrategyConfig(
    ...     signals=SignalConfig(buy_threshold=0.55),
    ...     sizing=SizingConfig(method='volatility_scaled'),
    ...     risk=RiskConfig(max_daily_loss=1000),
    ...     portfolio=PortfolioConfig(max_concurrent_positions=10)
    ... )
    >>> 
    >>> strategy = TradingStrategy(config, initial_equity=100000)
    >>> 
    >>> # Process new prediction
    >>> decision = strategy.process_signal(
    ...     symbol='BTCUSDT',
    ...     probability=0.62,
    ...     returns=returns_series
    ... )
    >>> 
    >>> # Execute if allowed
    >>> if decision.action != 'HOLD':
    ...     execute_order(decision)
    ...     strategy.record_execution(decision, pnl=50.0)
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        initial_equity: float = 100000.0
    ):
        self.config = config
        
        # Initialize components
        self.signal_generator = SignalGenerator(config.signals)
        self.position_sizer = PositionSizer(config.sizing)
        self.risk_manager = RiskManager(config.risk)
        self.portfolio_manager = PortfolioManager(config.portfolio)
        
        # Initialize state
        self.state = StrategyState(
            equity=initial_equity,
            peak_equity=initial_equity,
            status=StrategyStatus.ACTIVE
        )
        
        # Decision log
        self.decision_log: List[ExecutionDecision] = []
    
    def process_signal(
        self,
        symbol: str,
        probability: float,
        expected_value: Optional[float] = None,
        returns: Optional[pd.Series] = None,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None,
        sector: Optional[str] = None,
        venue: Optional[str] = None,
        returns_data: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> ExecutionDecision:
        """
        Process model prediction and generate execution decision.
        
        Flow:
        1. Generate signal from probability
        2. Check portfolio constraints
        3. Calculate position size
        4. Check risk limits
        5. Return final decision
        
        Parameters
        ----------
        symbol : str
            Trading symbol
        probability : float
            Model prediction probability
        expected_value : float, optional
            Expected value of trade
        returns : pd.Series, optional
            Historical returns (for volatility sizing)
        high, low : pd.Series, optional
            High/low prices (for Parkinson volatility)
        sector : str, optional
            Symbol sector (for portfolio checks)
        venue : str, optional
            Trading venue (for portfolio checks)
        returns_data : pd.DataFrame, optional
            Multi-asset returns (for correlation)
        **kwargs
            Additional parameters
        
        Returns
        -------
        decision : ExecutionDecision
            Final execution decision
        """
        timestamp = datetime.now()
        
        # Check existing position
        existing_position = self.state.open_positions.get(symbol)
        
        # 1. Generate signal
        if existing_position is None:
            # Entry signal
            signal = self.signal_generator.generate_entry(
                probability=probability,
                expected_value=expected_value,
                metadata={'symbol': symbol}
            )
        else:
            # Exit signal (check stops)
            signal = self.signal_generator.check_exit(
                position=existing_position,
                current_price=kwargs.get('current_price', 0)
            )
        
        # If signal is HOLD or insufficient, return immediately
        if signal.direction == SignalDirection.HOLD:
            return self._create_hold_decision(symbol, timestamp, signal)
        
        # 2. Check portfolio constraints (for entries only)
        if signal.is_entry():
            can_open = self.portfolio_manager.can_open_position(
                symbol=symbol,
                sector=sector,
                venue=venue,
                returns_data=returns_data
            )
            
            if not can_open:
                return self._create_hold_decision(
                    symbol,
                    timestamp,
                    signal,
                    reason="Portfolio constraints"
                )
        
        # 3. Calculate position size
        if signal.is_entry():
            # Get correlation scale factor
            corr_scale = self.portfolio_manager.get_correlation_scale_factor(symbol)
            
            # Calculate base size
            position_size = self.position_sizer.calculate_size(
                capital=self.state.equity,
                volatility=kwargs.get('volatility'),
                returns=returns,
                high=high,
                low=low,
                **kwargs
            )
            
            # Apply correlation scaling
            final_size = position_size.size * corr_scale
        else:
            # Exit: use existing position size
            final_size = existing_position.size if existing_position else 0
        
        # 4. Check risk limits
        current_positions = {
            sym: pos.size for sym, pos in self.state.open_positions.items()
        }
        
        risk_allowed = self.risk_manager.check_trade_allowed(
            symbol=symbol,
            size=final_size,
            equity=self.state.equity,
            current_positions=current_positions
        )
        
        if not risk_allowed:
            return self._create_hold_decision(
                symbol,
                timestamp,
                signal,
                reason="Risk limits"
            )
        
        # 5. Create execution decision
        decision = ExecutionDecision(
            action=signal.direction.value,
            symbol=symbol,
            size=final_size,
            confidence=signal.confidence,
            timestamp=timestamp,
            metadata={
                'signal': {
                    'direction': signal.direction.value,
                    'confidence': signal.confidence,
                    'expected_value': signal.expected_value
                },
                'sizing': {
                    'base_size': position_size.size if signal.is_entry() else final_size,
                    'correlation_scale': corr_scale if signal.is_entry() else 1.0,
                    'final_size': final_size
                },
                'portfolio_status': self.portfolio_manager.get_status_info(),
                'equity': self.state.equity
            }
        )
        
        # Log decision
        if self.config.log_decisions:
            self.decision_log.append(decision)
        
        return decision
    
    def record_execution(
        self,
        decision: ExecutionDecision,
        pnl: float,
        fees: float = 0.0,
        fill_price: Optional[float] = None
    ):
        """
        Record executed trade.
        
        Parameters
        ----------
        decision : ExecutionDecision
            Executed decision
        pnl : float
            Realized P&L
        fees : float
            Transaction fees
        fill_price : float, optional
            Actual fill price
        """
        symbol = decision.symbol
        
        # Create trade record
        trade = TradeRecord(
            timestamp=decision.timestamp,
            symbol=symbol,
            size=decision.size,
            pnl=pnl,
            is_win=pnl > 0,
            metadata={
                'action': decision.action,
                'fees': fees,
                'fill_price': fill_price
            }
        )
        
        # Update risk manager
        self.risk_manager.record_trade(trade)
        
        # Update portfolio manager
        self.portfolio_manager.record_trade_result(pnl)
        
        # Update state
        self.state.total_trades += 1
        if pnl > 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1
        
        self.state.total_pnl += pnl
        self.state.total_fees += fees
        self.state.equity += pnl - fees
        
        # Update peak and drawdown
        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity
        
        self.state.current_drawdown = (
            (self.state.peak_equity - self.state.equity) / self.state.peak_equity
        )
        
        # Update positions
        if decision.action in ['LONG', 'SHORT']:
            # Open position
            self.state.open_positions[symbol] = Position(
                symbol=symbol,
                direction=decision.action,
                size=decision.size,
                entry_price=fill_price or 0,
                current_price=fill_price or 0,
                entry_time=decision.timestamp
            )
            
            self.portfolio_manager.add_position(
                symbol=symbol,
                size=decision.size,
                sector=decision.metadata.get('sector'),
                venue=decision.metadata.get('venue')
            )
        
        elif decision.action == 'CLOSE':
            # Close position
            if symbol in self.state.open_positions:
                del self.state.open_positions[symbol]
            
            self.portfolio_manager.remove_position(symbol)
            self.state.closed_positions.append(trade)
        
        # Update status
        self._update_status()
        self.state.last_update = datetime.now()
    
    def _create_hold_decision(
        self,
        symbol: str,
        timestamp: datetime,
        signal: Signal,
        reason: str = "Filtered"
    ) -> ExecutionDecision:
        """Create HOLD decision."""
        return ExecutionDecision(
            action='HOLD',
            symbol=symbol,
            size=0,
            confidence=signal.confidence,
            timestamp=timestamp,
            metadata={
                'reason': reason,
                'signal': {
                    'direction': signal.direction.value,
                    'confidence': signal.confidence
                }
            }
        )
    
    def _update_status(self):
        """Update overall strategy status."""
        # Check circuit breaker
        if self.risk_manager.circuit_breaker.is_halted():
            self.state.status = StrategyStatus.CIRCUIT_BREAKER
        
        # Check cooldown
        elif self.portfolio_manager.cooldown.is_in_cooldown():
            self.state.status = StrategyStatus.COOLDOWN
        
        # Check drawdown
        elif self.risk_manager.drawdown_control.get_scale_factor(self.state.equity) == 0:
            self.state.status = StrategyStatus.DRAWDOWN_HALT
        
        # Check daily loss
        elif self.risk_manager.daily_loss.current_loss >= self.config.risk.max_daily_loss:
            self.state.status = StrategyStatus.RISK_HALT
        
        else:
            self.state.status = StrategyStatus.ACTIVE
    
    def get_state_summary(self) -> Dict:
        """
        Get complete state summary.
        
        Returns
        -------
        summary : dict
            Strategy state and performance
        """
        win_rate = (
            self.state.winning_trades / self.state.total_trades
            if self.state.total_trades > 0 else 0
        )
        
        avg_win = 0
        avg_loss = 0
        if self.state.closed_positions:
            wins = [t.pnl for t in self.state.closed_positions if t.is_win]
            losses = [abs(t.pnl) for t in self.state.closed_positions if not t.is_win]
            
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
        
        return {
            'status': self.state.status.value,
            'equity': self.state.equity,
            'peak_equity': self.state.peak_equity,
            'current_drawdown': self.state.current_drawdown,
            'open_positions': len(self.state.open_positions),
            'total_trades': self.state.total_trades,
            'winning_trades': self.state.winning_trades,
            'losing_trades': self.state.losing_trades,
            'win_rate': win_rate,
            'total_pnl': self.state.total_pnl,
            'total_fees': self.state.total_fees,
            'net_pnl': self.state.total_pnl - self.state.total_fees,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': avg_win / avg_loss if avg_loss > 0 else 0,
            'last_update': self.state.last_update.isoformat() if self.state.last_update else None
        }
    
    def save_state(self, path: str):
        """Save strategy state to file."""
        state_data = self.get_state_summary()
        
        with open(path, 'w') as f:
            json.dump(state_data, f, indent=2)
    
    def reset(self):
        """Reset strategy to initial state."""
        initial_equity = self.state.equity
        
        self.state = StrategyState(
            equity=initial_equity,
            peak_equity=initial_equity,
            status=StrategyStatus.ACTIVE
        )
        
        self.decision_log = []


# Export public API
__all__ = [
    'StrategyConfig',
    'TradingStrategy',
    'StrategyState',
    'StrategyStatus',
    'ExecutionDecision',
]
