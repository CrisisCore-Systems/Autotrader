"""
Execution Engine
================

Main orchestrator integrating Phase 8 strategy with execution adapters.

This module combines:
- Phase 8 TradingStrategy (decision generation)
- Broker adapters (order execution)
- OMS (order tracking)
- Resiliency layer (retry, circuit breaker)

Flow:
    Strategy Decision → OMS → Broker Adapter → Exchange → Fill → Update Strategy

Example
-------
>>> from autotrader.execution import ExecutionEngine
>>> from autotrader.strategy import TradingStrategy, StrategyConfig
>>> from autotrader.execution.adapters.paper import PaperTradingAdapter
>>> 
>>> # Initialize components
>>> strategy_config = StrategyConfig.from_yaml('config/strategy.yaml')
>>> strategy = TradingStrategy(strategy_config, initial_equity=100000)
>>> 
>>> adapter = PaperTradingAdapter(initial_balance=100000)
>>> 
>>> # Create execution engine
>>> engine = ExecutionEngine(
...     strategy=strategy,
...     adapter=adapter,
...     enable_resiliency=True
... )
>>> 
>>> # Connect and run
>>> await engine.connect()
>>> await engine.run_live_trading()
"""

from typing import Optional, Dict, Callable
from datetime import datetime
import asyncio
from dataclasses import dataclass
from autotrader.strategy import TradingStrategy, ExecutionDecision, StrategyStatus
from autotrader.execution.adapters import (
    BaseBrokerAdapter,
    Order,
    Fill,
    OrderType,
    OrderSide
)
from autotrader.execution.oms import OrderManager
from autotrader.execution.resiliency import ResiliencyManager


@dataclass
class ExecutionConfig:
    """
    Execution engine configuration.
    
    Attributes
    ----------
    enable_resiliency : bool
        Enable retry and circuit breaker
    enable_oms_monitoring : bool
        Enable OMS order timeout monitoring
    cycle_time_ms : int
        Main loop cycle time (milliseconds)
    enable_paper_trading : bool
        Use paper trading mode
    """
    enable_resiliency: bool = True
    enable_oms_monitoring: bool = True
    cycle_time_ms: int = 100
    enable_paper_trading: bool = False


class ExecutionEngine:
    """
    Main execution orchestrator.
    
    Integrates Phase 8 strategy with execution adapters.
    
    Parameters
    ----------
    strategy : TradingStrategy
        Trading strategy (Phase 8)
    adapter : BaseBrokerAdapter
        Broker adapter
    config : ExecutionConfig, optional
        Configuration
    
    Example
    -------
    >>> engine = ExecutionEngine(
    ...     strategy=strategy,
    ...     adapter=adapter
    ... )
    >>> 
    >>> await engine.connect()
    >>> await engine.run_live_trading()
    """
    
    def __init__(
        self,
        strategy: TradingStrategy,
        adapter: BaseBrokerAdapter,
        config: Optional[ExecutionConfig] = None
    ):
        self.strategy = strategy
        self.adapter = adapter
        self.config = config or ExecutionConfig()
        
        # Initialize components
        self.oms = OrderManager(adapter)
        
        if self.config.enable_resiliency:
            self.resiliency = ResiliencyManager(adapter)
        else:
            self.resiliency = None
        
        # State
        self.running = False
        self.connected = False
        
        # Subscribe to fills
        self.adapter.subscribe_fills(self._handle_fill)
        
        # Callbacks
        self.decision_callbacks: list = []
        self.fill_callbacks: list = []
    
    async def connect(self) -> bool:
        """
        Connect to broker.
        
        Returns
        -------
        success : bool
            True if connection successful
        """
        try:
            self.connected = await self.adapter.connect()
            
            if self.connected:
                # Start OMS monitoring
                if self.config.enable_oms_monitoring:
                    await self.oms.start_monitoring()
                
                # Start resiliency health monitoring
                if self.resiliency:
                    await self.resiliency.start_health_monitoring()
            
            return self.connected
        
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from broker."""
        # Stop monitoring
        if self.config.enable_oms_monitoring:
            await self.oms.stop_monitoring()
        
        if self.resiliency:
            await self.resiliency.stop_health_monitoring()
        
        # Cancel all open orders
        await self.oms.cancel_all_orders()
        
        # Disconnect
        await self.adapter.disconnect()
        self.connected = False
    
    async def execute_decision(
        self,
        decision: ExecutionDecision,
        limit_price: Optional[float] = None
    ) -> Optional[Order]:
        """
        Execute trading decision from Phase 8.
        
        Parameters
        ----------
        decision : ExecutionDecision
            Decision from strategy
        limit_price : float, optional
            Limit price (if not in decision metadata)
        
        Returns
        -------
        order : Order, optional
            Executed order (None if HOLD)
        """
        if decision.action == 'HOLD':
            return None
        
        # Convert decision to order parameters
        side = OrderSide.BUY if decision.action == 'LONG' else OrderSide.SELL
        
        # Get limit price
        price = limit_price or decision.metadata.get('limit_price')
        
        # Determine order type
        if price:
            order_type = OrderType.LIMIT
        else:
            order_type = OrderType.MARKET
        
        # Create order
        order = Order(
            order_id="",
            symbol=decision.symbol,
            side=side,
            order_type=order_type,
            quantity=decision.size,
            price=price
        )
        
        # Submit with or without resiliency
        try:
            if self.resiliency:
                order = await self.resiliency.submit_order_with_retry(order)
            else:
                order = await self.adapter.submit_order(order)
            
            # Notify callbacks
            for callback in self.decision_callbacks:
                try:
                    callback(decision, order)
                except Exception as e:
                    print(f"Error in decision callback: {e}")
            
            return order
        
        except Exception as e:
            print(f"Order execution error: {e}")
            return None
    
    def _handle_fill(self, fill: Fill):
        """
        Handle fill notification.
        
        Updates Phase 8 strategy with execution results.
        
        Parameters
        ----------
        fill : Fill
            Fill report
        """
        # Find corresponding decision (if available)
        # In production, would match fill to original decision
        
        # Calculate P&L (simplified - would need entry price tracking)
        pnl = 0.0  # Would calculate based on position
        
        # Record execution in strategy
        # (This is a placeholder - actual implementation would track the decision)
        
        # Notify callbacks
        for callback in self.fill_callbacks:
            try:
                callback(fill)
            except Exception as e:
                print(f"Error in fill callback: {e}")
    
    async def run_live_trading(
        self,
        market_data_callback: Optional[Callable] = None,
        should_continue: Optional[Callable[[], bool]] = None
    ):
        """
        Main live trading loop.
        
        Continuously processes market data and executes strategy decisions.
        
        Parameters
        ----------
        market_data_callback : callable, optional
            Function to get market data: () -> Dict[str, Any]
        should_continue : callable, optional
            Function to check if should continue: () -> bool
        
        Example
        -------
        >>> async def get_market_data():
        ...     # Fetch current market data
        ...     return {'BTCUSDT': {'price': 50000, 'volume': 1000}}
        >>> 
        >>> await engine.run_live_trading(
        ...     market_data_callback=get_market_data,
        ...     should_continue=lambda: True
        ... )
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
        
        self.running = True
        cycle_time = self.config.cycle_time_ms / 1000.0
        
        print(f"🚀 Starting live trading - cycle time: {self.config.cycle_time_ms}ms")
        
        try:
            while self.running and (should_continue is None or should_continue()):
                # Check strategy status
                if self.strategy.state.status not in [StrategyStatus.ACTIVE, StrategyStatus.COOLDOWN]:
                    print(f"⚠️ Strategy status: {self.strategy.state.status.value}")
                    await asyncio.sleep(cycle_time)
                    continue
                
                # Get market data
                if market_data_callback:
                    market_data = await market_data_callback()
                else:
                    # No market data - skip cycle
                    await asyncio.sleep(cycle_time)
                    continue
                
                # Process each symbol
                for symbol, data in market_data.items():
                    # Generate decision from strategy
                    decision = self.strategy.process_signal(
                        symbol=symbol,
                        probability=data.get('probability', 0.5),
                        expected_value=data.get('expected_value'),
                        current_price=data.get('price'),
                        returns=data.get('returns'),
                        sector=data.get('sector'),
                        venue=data.get('venue')
                    )
                    
                    # Execute if not HOLD
                    if decision.action != 'HOLD':
                        order = await self.execute_decision(
                            decision,
                            limit_price=data.get('price')
                        )
                        
                        if order:
                            print(f"✅ Executed: {order.symbol} {order.side.value} {order.quantity} @ {order.price}")
                
                # Sleep until next cycle
                await asyncio.sleep(cycle_time)
        
        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt - stopping...")
        
        except Exception as e:
            print(f"❌ Error in live trading loop: {e}")
        
        finally:
            self.running = False
            await self.disconnect()
            print("🛑 Live trading stopped")
    
    def stop(self):
        """Stop live trading loop."""
        self.running = False
    
    def subscribe_decisions(self, callback: Callable):
        """
        Subscribe to execution decisions.
        
        Parameters
        ----------
        callback : callable
            Function(decision, order) called on each execution
        """
        self.decision_callbacks.append(callback)
    
    def subscribe_fills(self, callback: Callable):
        """
        Subscribe to fill notifications.
        
        Parameters
        ----------
        callback : callable
            Function(fill) called on each fill
        """
        self.fill_callbacks.append(callback)
    
    def get_status(self) -> Dict:
        """
        Get execution engine status.
        
        Returns
        -------
        status : dict
            Current status
        """
        status = {
            'connected': self.connected,
            'running': self.running,
            'strategy_status': self.strategy.state.status.value,
            'strategy_equity': self.strategy.state.equity,
            'oms': self.oms.get_performance_metrics()
        }
        
        if self.resiliency:
            status['resiliency'] = self.resiliency.get_failure_stats()
        
        return status


# Kill switch for emergency stop
class KillSwitch:
    """
    Emergency stop all trading.
    
    Parameters
    ----------
    engine : ExecutionEngine
        Execution engine to control
    
    Example
    -------
    >>> kill_switch = KillSwitch(engine)
    >>> await kill_switch.activate()
    """
    
    def __init__(self, engine: ExecutionEngine):
        self.engine = engine
        self.activated = False
    
    async def activate(self, close_positions: bool = False):
        """
        Activate kill switch.
        
        Steps:
        1. Stop live trading loop
        2. Cancel all open orders
        3. Optionally close all positions
        4. Disconnect from broker
        
        Parameters
        ----------
        close_positions : bool
            Whether to close all positions
        """
        if self.activated:
            return
        
        print("🚨 KILL SWITCH ACTIVATED")
        
        # Stop trading loop
        self.engine.stop()
        
        # Cancel all orders
        print("Cancelling all orders...")
        await self.engine.oms.cancel_all_orders()
        
        # Close positions if requested
        if close_positions:
            print("Closing all positions...")
            positions = self.engine.oms.get_all_positions()
            
            for symbol, quantity in positions.items():
                if quantity != 0:
                    side = OrderSide.SELL if quantity > 0 else OrderSide.BUY
                    
                    try:
                        await self.engine.oms.submit_order(
                            symbol=symbol,
                            side=side,
                            quantity=abs(quantity),
                            order_type=OrderType.MARKET
                        )
                    except Exception as e:
                        print(f"Error closing {symbol}: {e}")
        
        # Disconnect
        await self.engine.disconnect()
        
        self.activated = True
        print("✅ Kill switch complete - all trading stopped")


# Export
__all__ = [
    'ExecutionConfig',
    'ExecutionEngine',
    'KillSwitch',
]
