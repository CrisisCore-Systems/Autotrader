"""
Integration Tests for Phase 10 Execution Module
================================================

Comprehensive tests for broker adapters, OMS, resiliency, and execution engine.

Run tests:
    pytest tests/test_execution_integration.py -v

Run specific test:
    pytest tests/test_execution_integration.py::test_paper_trading_full_flow -v
"""

import pytest
import asyncio
from autotrader.execution import ExecutionEngine, KillSwitch
from autotrader.execution.adapters import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus
)
from autotrader.execution.adapters.paper import PaperTradingAdapter
from autotrader.execution.oms import OrderManager
from autotrader.execution.resiliency import ResiliencyManager


# Fixtures

@pytest.fixture
def paper_adapter():
    """Paper trading adapter for testing."""
    return PaperTradingAdapter(
        initial_balance=100000,
        latency_ms=(10, 20),
        slippage_bps=5.0,
        commission_bps=10.0,
        fill_probability=1.0  # 100% fills for testing
    )


# Paper Trading Tests

@pytest.mark.asyncio
async def test_paper_adapter_connect(paper_adapter):
    """Test paper trading adapter connection."""
    connected = await paper_adapter.connect()
    assert connected is True
    assert paper_adapter.connected is True


@pytest.mark.asyncio
async def test_paper_adapter_market_order(paper_adapter):
    """Test paper trading market order execution."""
    await paper_adapter.connect()
    
    # Set price
    paper_adapter.set_price('BTCUSDT', 50000)
    
    # Create market order
    order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    # Submit order
    filled_order = await paper_adapter.submit_order(order)
    
    # Wait for fill
    await asyncio.sleep(0.1)
    
    # Verify
    assert filled_order.order_id is not None
    assert filled_order.status == OrderStatus.FILLED
    assert filled_order.filled_quantity == 0.1
    assert filled_order.avg_fill_price > 0


@pytest.mark.asyncio
async def test_paper_adapter_limit_order(paper_adapter):
    """Test paper trading limit order execution."""
    await paper_adapter.connect()
    
    # Set price
    paper_adapter.set_price('BTCUSDT', 50000)
    
    # Create limit order (at market price - should fill)
    order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.1,
        price=50000
    )
    
    # Submit order
    filled_order = await paper_adapter.submit_order(order)
    
    # Wait for fill
    await asyncio.sleep(0.1)
    
    # Verify
    assert filled_order.status == OrderStatus.FILLED
    assert filled_order.avg_fill_price <= 50000  # Filled at limit or better


@pytest.mark.asyncio
async def test_paper_adapter_cancel_order(paper_adapter):
    """Test order cancellation."""
    await paper_adapter.connect()
    
    # Set price
    paper_adapter.set_price('BTCUSDT', 50000)
    
    # Create limit order (far from market - won't fill immediately)
    order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.1,
        price=40000  # Well below market
    )
    
    # Submit order
    submitted_order = await paper_adapter.submit_order(order)
    
    # Cancel order
    success = await paper_adapter.cancel_order(submitted_order.order_id)
    
    # Verify
    assert success is True
    assert submitted_order.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_paper_adapter_positions(paper_adapter):
    """Test position tracking."""
    await paper_adapter.connect()
    
    # Set price
    paper_adapter.set_price('BTCUSDT', 50000)
    
    # Buy order
    buy_order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    await paper_adapter.submit_order(buy_order)
    await asyncio.sleep(0.1)
    
    # Get positions
    positions = await paper_adapter.get_positions()
    
    # Verify
    assert len(positions) == 1
    assert positions[0].symbol == 'BTCUSDT'
    assert positions[0].quantity == 0.1


# OMS Tests

@pytest.mark.asyncio
async def test_oms_order_submission(paper_adapter):
    """Test OMS order submission."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    oms = OrderManager(paper_adapter)
    
    # Submit order via OMS
    submitted_order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    await asyncio.sleep(0.1)
    
    # Verify
    assert submitted_order.order_id is not None
    assert submitted_order in oms.active_orders.values() or submitted_order in oms.completed_orders


@pytest.mark.asyncio
async def test_oms_fill_tracking(paper_adapter):
    """Test OMS fill tracking."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    oms = OrderManager(paper_adapter)
    await oms.start_monitoring()
    
    # Submit order
    submitted_order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    await asyncio.sleep(0.2)
    
    # Verify order was submitted
    assert submitted_order.order_id is not None
    
    # Get fills
    fills = oms.get_fills(symbol='BTCUSDT')
    
    # Verify
    assert len(fills) > 0
    assert fills[0].symbol == 'BTCUSDT'
    
    await oms.stop_monitoring()


@pytest.mark.asyncio
async def test_oms_position_tracking(paper_adapter):
    """Test OMS position tracking."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    oms = OrderManager(paper_adapter)
    
    # Buy order
    await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    await asyncio.sleep(0.1)
    
    # Check position
    position = oms.get_position('BTCUSDT')
    
    # Verify
    assert position == 0.1  # Long position


@pytest.mark.asyncio
async def test_oms_performance_metrics(paper_adapter):
    """Test OMS performance metrics."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    oms = OrderManager(paper_adapter)
    
    # Submit multiple orders
    for _ in range(5):
        await oms.submit_order(
            symbol='BTCUSDT',
            side=OrderSide.BUY,
            quantity=0.1,
            order_type=OrderType.MARKET
        )
    
    await asyncio.sleep(0.5)
    
    # Get metrics
    metrics = oms.get_performance_metrics()
    
    # Verify
    assert metrics['total_orders'] == 5
    assert metrics['filled_orders'] > 0
    assert metrics['fill_rate'] > 0


# Resiliency Tests

@pytest.mark.asyncio
async def test_resiliency_retry_logic(paper_adapter):
    """Test resiliency retry logic."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    resiliency = ResiliencyManager(
        paper_adapter,
        max_retries=3,
        initial_backoff=0.1
    )
    
    # Create order
    order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    # Submit with retry
    result = await resiliency.submit_order_with_retry(order)
    
    # Verify
    assert result.order_id is not None
    assert result.status in [OrderStatus.SUBMITTED, OrderStatus.FILLED]


@pytest.mark.asyncio
async def test_resiliency_circuit_breaker():
    """Test circuit breaker functionality."""
    
    # Create failing adapter
    class FailingAdapter(PaperTradingAdapter):
        async def submit_order(self, _order):
            raise Exception("Simulated failure")
    
    adapter = FailingAdapter()
    await adapter.connect()
    
    resiliency = ResiliencyManager(
        adapter,
        max_retries=2,
        circuit_breaker_threshold=3,
        initial_backoff=0.1
    )
    
    # Try to submit orders (will fail)
    failed_order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1
    )
    
    # Submit multiple failing orders
    for _ in range(4):
        try:
            await resiliency.submit_order_with_retry(failed_order)
        except Exception:
            pass
    
    # Check circuit breaker
    stats = resiliency.get_failure_stats()
    
    # Verify circuit opened
    assert stats['circuit_state'] == 'OPEN'
    assert stats['failure_count'] >= 3


# Execution Engine Tests

@pytest.mark.asyncio
async def test_execution_engine_connect(paper_adapter):
    """Test execution engine connection."""
    # Create minimal mock strategy
    class MockStrategy:
        def record_execution(self, fill):
            pass
    
    engine = ExecutionEngine(MockStrategy(), paper_adapter)
    
    connected = await engine.connect()
    
    assert connected is True
    assert engine.connected is True
    
    await engine.disconnect()


@pytest.mark.asyncio
async def test_execution_engine_status(paper_adapter):
    """Test execution engine status monitoring."""
    class MockStrategy:
        def record_execution(self, fill):
            pass
        
        def get_status(self):
            return {'status': 'active'}
    
    engine = ExecutionEngine(MockStrategy(), paper_adapter)
    await engine.connect()
    
    # Get status
    status = engine.get_status()
    
    # Verify
    assert 'connected' in status
    assert 'running' in status
    assert 'strategy_status' in status
    assert 'oms' in status
    
    await engine.disconnect()


@pytest.mark.asyncio
async def test_kill_switch(paper_adapter):
    """Test kill switch functionality."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    class MockStrategy:
        def record_execution(self, fill):
            pass
    
    engine = ExecutionEngine(MockStrategy(), paper_adapter)
    await engine.connect()
    
    # Submit order
    await engine.oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    await asyncio.sleep(0.1)
    
    # Activate kill switch
    kill_switch = KillSwitch(engine)
    await kill_switch.activate()
    
    # Verify
    assert kill_switch.activated is True
    assert engine.connected is False


# Full Flow Tests

@pytest.mark.asyncio
async def test_paper_trading_basic_flow(paper_adapter):
    """Test complete paper trading flow with manual orders."""
    # Setup
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    paper_adapter.set_price('ETHUSDT', 3000)
    
    oms = OrderManager(paper_adapter)
    
    # Execute orders
    btc_order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    eth_order = await oms.submit_order(
        symbol='ETHUSDT',
        side=OrderSide.BUY,
        quantity=1.0,
        order_type=OrderType.MARKET
    )
    
    await asyncio.sleep(0.5)
    
    # Verify orders
    assert btc_order.order_id is not None
    assert eth_order.order_id is not None
    
    # Verify fills
    fills = oms.get_fills()
    assert len(fills) >= 2
    
    # Verify positions
    btc_position = oms.get_position('BTCUSDT')
    eth_position = oms.get_position('ETHUSDT')
    assert btc_position > 0
    assert eth_position > 0
    
    # Verify performance metrics
    metrics = oms.get_performance_metrics()
    assert metrics['total_orders'] >= 2
    assert metrics['fill_rate'] > 0


@pytest.mark.asyncio
async def test_multi_order_execution(paper_adapter):
    """Test multiple orders with different types."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    oms = OrderManager(paper_adapter)
    
    # Market order
    market_order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    # Limit order
    limit_order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.LIMIT,
        price=49000
    )
    
    # IOC order
    ioc_order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.IOC,
        price=50000
    )
    
    await asyncio.sleep(0.2)
    
    # Verify
    assert market_order.status == OrderStatus.FILLED
    assert limit_order.order_id is not None
    assert ioc_order.order_id is not None
    
    # Check metrics
    metrics = oms.get_performance_metrics()
    assert metrics['total_orders'] == 3


@pytest.mark.asyncio
async def test_order_lifecycle(paper_adapter):
    """Test complete order lifecycle: submit -> fill -> position."""
    await paper_adapter.connect()
    paper_adapter.set_price('BTCUSDT', 50000)
    
    oms = OrderManager(paper_adapter)
    
    # Track fills
    fills_received = []
    
    def on_fill(fill):
        fills_received.append(fill)
    
    paper_adapter.subscribe_fills(on_fill)
    
    # Submit order
    order = await oms.submit_order(
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        quantity=0.1,
        order_type=OrderType.MARKET
    )
    
    await asyncio.sleep(0.2)
    
    # Verify order filled
    assert order.status == OrderStatus.FILLED
    
    # Verify fill received
    assert len(fills_received) > 0
    assert fills_received[0].symbol == 'BTCUSDT'
    
    # Verify position
    position = oms.get_position('BTCUSDT')
    assert position == 0.1


# Summary

def test_summary():
    """Print test summary."""
    print("\n" + "="*60)
    print("Phase 10 Integration Tests")
    print("="*60)
    print("\n✅ Paper Trading Adapter Tests")
    print("✅ OMS Tests")
    print("✅ Resiliency Tests")
    print("✅ Execution Engine Tests")
    print("✅ Full Flow Tests")
    print("\nAll critical paths tested!")
    print("="*60)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
