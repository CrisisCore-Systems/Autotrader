"""
Real-Time Portfolio Monitoring and Automated Rebalancing.

Implements threshold-based monitoring and rebalancing triggers
for maintaining target portfolio allocations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class RebalanceReason(Enum):
    """Reasons for triggering rebalance."""
    DRIFT_THRESHOLD = "drift_threshold"
    TIME_BASED = "time_based"
    RISK_THRESHOLD = "risk_threshold"
    DRAWDOWN_CONTROL = "drawdown_control"
    CORRELATION_SHIFT = "correlation_shift"
    MANUAL = "manual"


@dataclass
class PortfolioState:
    """Current portfolio state."""
    timestamp: datetime
    positions: Dict[str, float]  # Symbol -> quantity
    weights: Dict[str, float]  # Symbol -> weight
    values: Dict[str, float]  # Symbol -> market value
    total_value: float
    cash: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'positions': self.positions,
            'weights': self.weights,
            'values': self.values,
            'total_value': self.total_value,
            'cash': self.cash,
        }


@dataclass
class RebalanceOrder:
    """Order to rebalance portfolio."""
    symbol: str
    current_quantity: float
    target_quantity: float
    quantity_delta: float
    action: str  # 'BUY' or 'SELL'
    estimated_cost: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'current_quantity': self.current_quantity,
            'target_quantity': self.target_quantity,
            'quantity_delta': self.quantity_delta,
            'action': self.action,
            'estimated_cost': self.estimated_cost,
        }


@dataclass
class RebalanceEvent:
    """Event triggering a rebalance."""
    timestamp: datetime
    reason: RebalanceReason
    current_state: PortfolioState
    target_weights: Dict[str, float]
    orders: List[RebalanceOrder]
    estimated_turnover: float
    estimated_cost: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason.value,
            'current_state': self.current_state.to_dict(),
            'target_weights': self.target_weights,
            'orders': [o.to_dict() for o in self.orders],
            'estimated_turnover': self.estimated_turnover,
            'estimated_cost': self.estimated_cost,
        }


class DriftMonitor:
    """
    Monitor portfolio drift from target allocation.
    
    Triggers rebalance when weights deviate beyond threshold.
    """
    
    def __init__(
        self,
        absolute_threshold: float = 0.05,  # 5% absolute drift
        relative_threshold: float = 0.20,  # 20% relative drift
    ):
        """
        Initialize drift monitor.
        
        Args:
            absolute_threshold: Trigger if weight differs by more than this
            relative_threshold: Trigger if weight differs by more than this fraction of target
        """
        self.absolute_threshold = absolute_threshold
        self.relative_threshold = relative_threshold
    
    def check_drift(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Check if portfolio has drifted beyond threshold.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
        
        Returns:
            Tuple of (needs_rebalance, drift_dict)
        """
        drift = {}
        needs_rebalance = False
        
        # Check all symbols in target
        for symbol, target_weight in target_weights.items():
            current_weight = current_weights.get(symbol, 0.0)
            absolute_drift = abs(current_weight - target_weight)
            
            # Calculate relative drift
            if target_weight > 0:
                relative_drift = absolute_drift / target_weight
            else:
                relative_drift = 0
            
            drift[symbol] = {
                'current': current_weight,
                'target': target_weight,
                'absolute_drift': absolute_drift,
                'relative_drift': relative_drift,
            }
            
            # Check thresholds
            if absolute_drift > self.absolute_threshold or relative_drift > self.relative_threshold:
                needs_rebalance = True
                logger.info(
                    f"{symbol} drift detected: {current_weight:.1%} vs {target_weight:.1%} "
                    f"(absolute={absolute_drift:.1%}, relative={relative_drift:.1%})"
                )
        
        # Check for positions not in target (should be zero)
        for symbol in current_weights:
            if symbol not in target_weights:
                drift[symbol] = {
                    'current': current_weights[symbol],
                    'target': 0.0,
                    'absolute_drift': current_weights[symbol],
                    'relative_drift': float('inf'),
                }
                if current_weights[symbol] > self.absolute_threshold:
                    needs_rebalance = True
                    logger.info(f"{symbol} not in target allocation, should be closed")
        
        return needs_rebalance, drift


class RiskMonitor:
    """
    Monitor portfolio risk metrics.
    
    Triggers rebalance if risk exceeds thresholds.
    """
    
    def __init__(
        self,
        max_portfolio_volatility: float = 0.25,  # 25% annual vol
        max_var_95: float = 0.05,  # 5% daily VaR
        max_beta: float = 1.5,
        max_concentration: float = 0.30,  # Max 30% in single position
    ):
        self.max_portfolio_volatility = max_portfolio_volatility
        self.max_var_95 = max_var_95
        self.max_beta = max_beta
        self.max_concentration = max_concentration
    
    def check_risk(
        self,
        current_weights: Dict[str, float],
        returns_history: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Check if portfolio risk exceeds thresholds.
        
        Args:
            current_weights: Current portfolio weights
            returns_history: Historical returns for each asset
            benchmark_returns: Benchmark returns for beta calculation
        
        Returns:
            Tuple of (needs_rebalance, risk_metrics)
        """
        # Align weights with returns
        symbols = list(current_weights.keys())
        weights = np.array([current_weights[s] for s in symbols])
        returns = returns_history[symbols].values
        
        # Calculate portfolio returns
        portfolio_returns = returns @ weights
        
        # Calculate risk metrics
        portfolio_vol = np.std(portfolio_returns) * np.sqrt(252)  # Annualized
        var_95 = -np.percentile(portfolio_returns, 5)
        max_weight = max(current_weights.values())
        
        # Calculate beta if benchmark provided
        if benchmark_returns is not None:
            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            benchmark_var = np.var(benchmark_returns)
            beta = covariance / benchmark_var if benchmark_var > 0 else 1.0
        else:
            beta = None
        
        risk_metrics = {
            'portfolio_volatility': portfolio_vol,
            'var_95': var_95,
            'beta': beta,
            'max_concentration': max_weight,
        }
        
        # Check thresholds
        needs_rebalance = False
        
        if portfolio_vol > self.max_portfolio_volatility:
            logger.warning(f"Portfolio volatility {portfolio_vol:.1%} exceeds threshold {self.max_portfolio_volatility:.1%}")
            needs_rebalance = True
        
        if var_95 > self.max_var_95:
            logger.warning(f"VaR {var_95:.1%} exceeds threshold {self.max_var_95:.1%}")
            needs_rebalance = True
        
        if beta is not None and abs(beta) > self.max_beta:
            logger.warning(f"Beta {beta:.2f} exceeds threshold {self.max_beta:.2f}")
            needs_rebalance = True
        
        if max_weight > self.max_concentration:
            logger.warning(f"Concentration {max_weight:.1%} exceeds threshold {self.max_concentration:.1%}")
            needs_rebalance = True
        
        return needs_rebalance, risk_metrics


class RebalancingEngine:
    """
    Main rebalancing engine.
    
    Coordinates monitoring and execution of portfolio rebalancing.
    """
    
    def __init__(
        self,
        drift_monitor: Optional[DriftMonitor] = None,
        risk_monitor: Optional[RiskMonitor] = None,
        min_rebalance_interval: timedelta = timedelta(days=7),
        transaction_cost_pct: float = 0.001,  # 10 bps
        min_trade_size: float = 100.0,  # Minimum $100 trade
    ):
        """
        Initialize rebalancing engine.
        
        Args:
            drift_monitor: Drift monitoring component
            risk_monitor: Risk monitoring component
            min_rebalance_interval: Minimum time between rebalances
            transaction_cost_pct: Estimated transaction cost as percentage
            min_trade_size: Minimum trade size in dollars
        """
        self.drift_monitor = drift_monitor or DriftMonitor()
        self.risk_monitor = risk_monitor or RiskMonitor()
        self.min_rebalance_interval = min_rebalance_interval
        self.transaction_cost_pct = transaction_cost_pct
        self.min_trade_size = min_trade_size
        
        self.last_rebalance_time: Optional[datetime] = None
        self.rebalance_history: List[RebalanceEvent] = []
    
    def check_rebalance_needed(
        self,
        current_state: PortfolioState,
        target_weights: Dict[str, float],
        returns_history: Optional[pd.DataFrame] = None,
        force_check: bool = False,
    ) -> Tuple[bool, Optional[RebalanceReason], Dict]:
        """
        Check if rebalancing is needed.
        
        Args:
            current_state: Current portfolio state
            target_weights: Target allocation weights
            returns_history: Historical returns for risk monitoring
            force_check: Force check even if within min interval
        
        Returns:
            Tuple of (needs_rebalance, reason, details)
        """
        # Check minimum interval
        if not force_check and self.last_rebalance_time:
            time_since_last = current_state.timestamp - self.last_rebalance_time
            if time_since_last < self.min_rebalance_interval:
                logger.debug(f"Skipping check: only {time_since_last} since last rebalance")
                return False, None, {}
        
        # Check drift
        needs_rebalance_drift, drift_details = self.drift_monitor.check_drift(
            current_state.weights, target_weights
        )
        
        if needs_rebalance_drift:
            return True, RebalanceReason.DRIFT_THRESHOLD, drift_details
        
        # Check risk if returns history available
        if returns_history is not None:
            needs_rebalance_risk, risk_details = self.risk_monitor.check_risk(
                current_state.weights, returns_history
            )
            
            if needs_rebalance_risk:
                return True, RebalanceReason.RISK_THRESHOLD, risk_details
        
        return False, None, {}
    
    def generate_rebalance_orders(
        self,
        current_state: PortfolioState,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
    ) -> List[RebalanceOrder]:
        """
        Generate orders to rebalance portfolio.
        
        Args:
            current_state: Current portfolio state
            target_weights: Target allocation weights
            prices: Current prices for each symbol
        
        Returns:
            List of rebalance orders
        """
        orders = []
        total_value = current_state.total_value
        
        # Calculate target quantities
        for symbol, target_weight in target_weights.items():
            target_value = total_value * target_weight
            current_quantity = current_state.positions.get(symbol, 0.0)
            
            if symbol not in prices:
                logger.warning(f"No price available for {symbol}, skipping")
                continue
            
            price = prices[symbol]
            target_quantity = target_value / price
            quantity_delta = target_quantity - current_quantity
            
            # Skip if below minimum trade size
            trade_value = abs(quantity_delta * price)
            if trade_value < self.min_trade_size:
                logger.debug(f"Skipping {symbol}: trade size ${trade_value:.2f} below minimum")
                continue
            
            # Determine action
            if quantity_delta > 0:
                action = 'BUY'
            else:
                action = 'SELL'
            
            # Estimate cost (including transaction costs)
            estimated_cost = trade_value * (1 + self.transaction_cost_pct)
            
            orders.append(RebalanceOrder(
                symbol=symbol,
                current_quantity=current_quantity,
                target_quantity=target_quantity,
                quantity_delta=quantity_delta,
                action=action,
                estimated_cost=estimated_cost,
            ))
        
        # Close positions not in target
        for symbol, quantity in current_state.positions.items():
            if symbol not in target_weights and quantity != 0:
                if symbol not in prices:
                    logger.warning(f"No price available for {symbol}, cannot close")
                    continue
                
                price = prices[symbol]
                trade_value = abs(quantity * price)
                
                if trade_value >= self.min_trade_size:
                    estimated_cost = trade_value * (1 + self.transaction_cost_pct)
                    
                    orders.append(RebalanceOrder(
                        symbol=symbol,
                        current_quantity=quantity,
                        target_quantity=0.0,
                        quantity_delta=-quantity,
                        action='SELL',
                        estimated_cost=estimated_cost,
                    ))
        
        return orders
    
    def create_rebalance_event(
        self,
        current_state: PortfolioState,
        target_weights: Dict[str, float],
        reason: RebalanceReason,
        orders: List[RebalanceOrder],
    ) -> RebalanceEvent:
        """Create rebalance event object."""
        # Calculate turnover (fraction of portfolio traded)
        total_trade_value = sum(abs(o.quantity_delta * o.estimated_cost) for o in orders)
        turnover = total_trade_value / current_state.total_value if current_state.total_value > 0 else 0
        
        # Calculate total estimated cost
        total_cost = sum(o.estimated_cost for o in orders)
        
        event = RebalanceEvent(
            timestamp=current_state.timestamp,
            reason=reason,
            current_state=current_state,
            target_weights=target_weights,
            orders=orders,
            estimated_turnover=turnover,
            estimated_cost=total_cost,
        )
        
        return event
    
    def rebalance(
        self,
        current_state: PortfolioState,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        reason: RebalanceReason = RebalanceReason.MANUAL,
    ) -> RebalanceEvent:
        """
        Execute rebalancing.
        
        Args:
            current_state: Current portfolio state
            target_weights: Target allocation weights
            prices: Current prices
            reason: Reason for rebalance
        
        Returns:
            RebalanceEvent with orders to execute
        """
        # Generate orders
        orders = self.generate_rebalance_orders(current_state, target_weights, prices)
        
        if not orders:
            logger.info("No rebalance orders generated")
            return None
        
        # Create event
        event = self.create_rebalance_event(current_state, target_weights, reason, orders)
        
        # Record event
        self.rebalance_history.append(event)
        self.last_rebalance_time = current_state.timestamp
        
        logger.info(
            f"Rebalance triggered ({reason.value}): {len(orders)} orders, "
            f"turnover={event.estimated_turnover:.1%}, cost=${event.estimated_cost:.2f}"
        )
        
        return event
    
    def get_rebalance_summary(self) -> Dict:
        """Get summary of rebalancing history."""
        if not self.rebalance_history:
            return {
                'n_rebalances': 0,
                'total_cost': 0.0,
                'avg_turnover': 0.0,
            }
        
        return {
            'n_rebalances': len(self.rebalance_history),
            'total_cost': sum(e.estimated_cost for e in self.rebalance_history),
            'avg_turnover': np.mean([e.estimated_turnover for e in self.rebalance_history]),
            'reasons': pd.Series([e.reason.value for e in self.rebalance_history]).value_counts().to_dict(),
        }
