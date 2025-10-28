# Phase 10: End-to-End Dry Run Guide

**Complete validation procedure for live trading system**

This guide provides step-by-step instructions for validating the execution infrastructure before live trading with real capital.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Phase 1: Paper Trading Test](#phase-1-paper-trading-test)
4. [Phase 2: Broker Testnet Tests](#phase-2-broker-testnet-tests)
5. [Phase 3: Live Dry Run](#phase-3-live-dry-run)
6. [Monitoring Checklist](#monitoring-checklist)
7. [Success Criteria](#success-criteria)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts

- [ ] **Binance Testnet**: Create account at https://testnet.binance.vision
- [ ] **IBKR Paper Account**: Enable paper trading in TWS/Gateway
- [ ] **Coinbase Sandbox**: Create sandbox keys in Coinbase dashboard
- [ ] **OKX Demo**: Enable demo trading in OKX account
- [ ] **Oanda Practice**: Create practice account at Oanda

### Required Software

- [ ] **Python 3.10+**: `python --version`
- [ ] **Dependencies**: `pip install -r requirements.txt`
- [ ] **TWS/Gateway**: For IBKR testing (download from IBKR website)
- [ ] **pytest**: `pip install pytest pytest-asyncio`

### Required Files

- [ ] API keys stored securely (use environment variables)
- [ ] Config files for each broker
- [ ] Logging configured

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create `.env` file:

```bash
# Binance Testnet
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret

# IBKR Paper
IBKR_PAPER_PORT=7497
IBKR_CLIENT_ID=1

# Coinbase Sandbox
COINBASE_SANDBOX_API_KEY=your_sandbox_api_key
COINBASE_SANDBOX_API_SECRET=your_sandbox_api_secret
COINBASE_SANDBOX_PASSPHRASE=your_sandbox_passphrase

# OKX Demo
OKX_DEMO_API_KEY=your_demo_api_key
OKX_DEMO_SECRET_KEY=your_demo_secret_key
OKX_DEMO_PASSPHRASE=your_demo_passphrase

# Oanda Practice
OANDA_PRACTICE_ACCOUNT_ID=your_practice_account_id
OANDA_PRACTICE_ACCESS_TOKEN=your_practice_access_token
```

### 4. Verify Installation

```bash
# Run unit tests
pytest tests/test_execution_integration.py -v

# Expected: All 19 tests pass
```

---

## Phase 1: Paper Trading Test

**Objective**: Validate core execution logic without real broker connection.

### Step 1: Run Paper Trading Script

Create `test_paper_trading.py`:

```python
import asyncio
from autotrader.execution import ExecutionEngine
from autotrader.execution.adapters.paper import PaperTradingAdapter
from autotrader.strategy import TradingStrategy, StrategyConfig

async def main():
    print("=" * 60)
    print("Phase 1: Paper Trading Test")
    print("=" * 60)
    
    # Setup
    config = StrategyConfig()
    strategy = TradingStrategy(config, initial_equity=100000)
    
    adapter = PaperTradingAdapter(
        initial_balance=100000,
        latency_ms=(10, 20),
        slippage_bps=5.0,
        commission_bps=10.0,
        fill_probability=1.0
    )
    
    engine = ExecutionEngine(strategy, adapter)
    
    # Connect
    print("\n1. Connecting to paper trading adapter...")
    connected = await engine.connect()
    assert connected, "❌ Failed to connect"
    print("✅ Connected successfully")
    
    # Set prices
    print("\n2. Setting market prices...")
    adapter.set_price('BTCUSDT', 50000)
    adapter.set_price('ETHUSDT', 3000)
    print("✅ Prices set")
    
    # Execute orders
    print("\n3. Executing test orders...")
    
    from autotrader.strategy import ExecutionDecision
    from datetime import datetime
    
    # BTC order
    btc_decision = ExecutionDecision(
        action='LONG',
        symbol='BTCUSDT',
        size=0.1,
        confidence=0.8,
        timestamp=datetime.now()
    )
    
    btc_order = await engine.execute_decision(btc_decision)
    print(f"✅ BTC order submitted: {btc_order.order_id}")
    
    # ETH order
    eth_decision = ExecutionDecision(
        action='LONG',
        symbol='ETHUSDT',
        size=1.0,
        confidence=0.85,
        timestamp=datetime.now()
    )
    
    eth_order = await engine.execute_decision(eth_decision)
    print(f"✅ ETH order submitted: {eth_order.order_id}")
    
    # Wait for fills
    print("\n4. Waiting for fills...")
    await asyncio.sleep(0.5)
    
    # Check status
    print("\n5. Checking status...")
    status = engine.get_status()
    
    print(f"\nConnection: {status['connected']}")
    print(f"OMS Metrics:")
    print(f"  - Total Orders: {status['oms']['total_orders']}")
    print(f"  - Fill Rate: {status['oms']['fill_rate']:.2%}")
    print(f"  - Avg Fill Latency: {status['oms']['avg_fill_latency']:.3f}s")
    print(f"  - Total Volume: ${status['oms']['total_filled_notional']:,.2f}")
    print(f"  - Total Commission: ${status['oms']['total_commission']:.2f}")
    
    # Verify fills
    fills = engine.oms.get_fills()
    print(f"\n6. Fills received: {len(fills)}")
    assert len(fills) >= 2, "❌ Expected at least 2 fills"
    print("✅ Fills validated")
    
    # Verify positions
    btc_pos = engine.oms.get_position('BTCUSDT')
    eth_pos = engine.oms.get_position('ETHUSDT')
    print(f"\n7. Positions:")
    print(f"  - BTC: {btc_pos}")
    print(f"  - ETH: {eth_pos}")
    assert btc_pos > 0, "❌ BTC position not updated"
    assert eth_pos > 0, "❌ ETH position not updated"
    print("✅ Positions validated")
    
    # Cleanup
    await engine.disconnect()
    
    print("\n" + "=" * 60)
    print("✅ Phase 1: Paper Trading Test PASSED")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
```

### Step 2: Run Test

```bash
python test_paper_trading.py
```

### Step 3: Expected Output

```
============================================================
Phase 1: Paper Trading Test
============================================================

1. Connecting to paper trading adapter...
✅ Connected successfully

2. Setting market prices...
✅ Prices set

3. Executing test orders...
✅ BTC order submitted: PAPER_1
✅ ETH order submitted: PAPER_2

4. Waiting for fills...

5. Checking status...

Connection: True
OMS Metrics:
  - Total Orders: 2
  - Fill Rate: 100.00%
  - Avg Fill Latency: 0.015s
  - Total Volume: $8,000.00
  - Total Commission: $8.00

6. Fills received: 2
✅ Fills validated

7. Positions:
  - BTC: 0.1
  - ETH: 1.0
✅ Positions validated

============================================================
✅ Phase 1: Paper Trading Test PASSED
============================================================
```

### Step 4: Validation Checklist

- [ ] All orders submitted successfully
- [ ] Fill rate = 100%
- [ ] Fill latency < 50ms
- [ ] Positions updated correctly
- [ ] No errors in logs

---

## Phase 2: Broker Testnet Tests

**Objective**: Validate broker adapters with real connections (safe environments).

### 2.1: Binance Testnet

#### Setup

1. Create testnet account: https://testnet.binance.vision
2. Generate API keys
3. Store in `.env`

#### Test Script

Create `test_binance_testnet.py`:

```python
import asyncio
import os
from autotrader.execution.adapters.binance import BinanceAdapter
from autotrader.execution.adapters import Order, OrderSide, OrderType

async def main():
    print("Testing Binance Testnet...")
    
    # Connect
    adapter = BinanceAdapter(
        api_key=os.getenv('BINANCE_TESTNET_API_KEY'),
        api_secret=os.getenv('BINANCE_TESTNET_API_SECRET'),
        testnet=True
    )
    
    connected = await adapter.connect()
    assert connected, "Failed to connect"
    print("✅ Connected")
    
    # Check balance
    balance = await adapter.get_account_balance()
    print(f"✅ Balance: ${balance:,.2f}")
    
    # Submit test order
    order = Order(
        order_id="",
        symbol='BTCUSDT',
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.001,  # Small test amount
        price=30000  # Well below market (won't fill)
    )
    
    submitted = await adapter.submit_order(order)
    print(f"✅ Order submitted: {submitted.order_id}")
    
    # Cancel order
    cancelled = await adapter.cancel_order(submitted.order_id)
    assert cancelled, "Failed to cancel"
    print("✅ Order cancelled")
    
    # Disconnect
    await adapter.disconnect()
    print("✅ Test passed")

if __name__ == '__main__':
    asyncio.run(main())
```

#### Run Test

```bash
python test_binance_testnet.py
```

#### Success Criteria

- [ ] Connection successful
- [ ] Balance retrieved
- [ ] Order submitted
- [ ] Order cancelled
- [ ] WebSocket connected (check logs)

---

### 2.2: IBKR Paper Account

#### Setup

1. Enable paper trading in TWS/Gateway
2. Start TWS/Gateway on port 7497
3. Enable API connections in settings

#### Test Script

Create `test_ibkr_paper.py`:

```python
import asyncio
from autotrader.execution.adapters.ibkr import IBKRAdapter
from autotrader.execution.adapters import Order, OrderSide, OrderType

async def main():
    print("Testing IBKR Paper Account...")
    
    # Connect
    adapter = IBKRAdapter(
        host='127.0.0.1',
        port=7497,  # Paper port
        client_id=1
    )
    
    connected = await adapter.connect()
    assert connected, "Failed to connect"
    print("✅ Connected")
    
    # Wait for connection to stabilize
    await asyncio.sleep(2)
    
    # Submit test order
    order = Order(
        order_id="",
        symbol='AAPL',
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        price=100  # Well below market
    )
    
    submitted = await adapter.submit_order(order)
    print(f"✅ Order submitted: {submitted.order_id}")
    
    # Cancel order
    await asyncio.sleep(1)
    cancelled = await adapter.cancel_order(submitted.order_id)
    print("✅ Order cancelled")
    
    # Disconnect
    await adapter.disconnect()
    print("✅ Test passed")

if __name__ == '__main__':
    asyncio.run(main())
```

#### Run Test

```bash
python test_ibkr_paper.py
```

#### Success Criteria

- [ ] TWS/Gateway running
- [ ] Connection successful
- [ ] Order submitted
- [ ] Order cancelled
- [ ] No callback errors

---

### 2.3: Coinbase Sandbox

#### Test Script

```python
import asyncio
import os
from autotrader.execution.adapters.coinbase import CoinbaseAdapter

async def main():
    print("Testing Coinbase Sandbox...")
    
    adapter = CoinbaseAdapter(
        api_key=os.getenv('COINBASE_SANDBOX_API_KEY'),
        api_secret=os.getenv('COINBASE_SANDBOX_API_SECRET'),
        passphrase=os.getenv('COINBASE_SANDBOX_PASSPHRASE'),
        sandbox=True
    )
    
    connected = await adapter.connect()
    assert connected, "Failed to connect"
    print("✅ Connected")
    
    # Test order submission and cancellation
    # ... (similar to Binance test)
    
    print("✅ Test passed")

asyncio.run(main())
```

---

### 2.4: OKX Demo

Similar structure to above tests.

---

### 2.5: Oanda Practice

Similar structure to above tests.

---

## Phase 3: Live Dry Run

**Objective**: Run complete system with real market data but minimal capital.

### Prerequisites

- [ ] All Phase 2 tests passed
- [ ] Small test capital allocated ($100-$1000)
- [ ] Strategy tested in paper trading
- [ ] Monitoring dashboard ready

### Step 1: Configure Strategy

Create `config/live_dry_run.yaml`:

```yaml
strategy:
  signals:
    buy_threshold: 0.55
    sell_threshold: 0.45
    min_ev: 10.0
  
  sizing:
    method: 'fixed_fractional'
    fraction: 0.01  # 1% per trade (conservative)
  
  risk:
    max_position_size: 100  # Small position limit
    daily_loss_limit_pct: 0.02  # 2% daily loss limit
  
  portfolio:
    max_concurrent_positions: 3

execution:
  enable_resiliency: true
  enable_oms_monitoring: true
  cycle_time_ms: 100
```

### Step 2: Start Live Trading

```bash
python -m autotrader.main --config config/live_dry_run.yaml --broker binance --testnet
```

### Step 3: Monitor for 24 Hours

Use monitoring script:

```python
import asyncio
import time

async def monitor(engine):
    """Monitor execution engine."""
    start_time = time.time()
    
    while True:
        status = engine.get_status()
        elapsed = time.time() - start_time
        
        print(f"\n=== Status (Elapsed: {elapsed/3600:.1f}h) ===")
        print(f"Connected: {status['connected']}")
        print(f"Running: {status['running']}")
        print(f"Orders: {status['oms']['total_orders']}")
        print(f"Fill Rate: {status['oms']['fill_rate']:.2%}")
        print(f"Circuit State: {status['resiliency']['circuit_state']}")
        
        await asyncio.sleep(60)  # Update every minute
```

---

## Monitoring Checklist

### System Health

- [ ] Connection stable (no disconnections)
- [ ] CPU usage < 20%
- [ ] Memory usage < 500MB
- [ ] No errors in logs

### Execution Quality

- [ ] Fill rate > 95%
- [ ] Average fill latency < 100ms
- [ ] Slippage < 10 bps
- [ ] No order rejections

### Risk Controls

- [ ] Position sizes within limits
- [ ] Daily loss limit not breached
- [ ] No excessive drawdown
- [ ] Kill switch functional

### OMS Metrics

- [ ] All fills recorded
- [ ] Positions tracked correctly
- [ ] Commission calculated accurately
- [ ] Performance metrics accurate

---

## Success Criteria

### Phase 1: Paper Trading ✅

- [x] All orders execute
- [x] Fill rate = 100%
- [x] Latency < 50ms
- [x] Positions correct

### Phase 2: Broker Tests ✅

- [ ] All 5 brokers connect successfully
- [ ] Orders submit without errors
- [ ] Orders cancel successfully
- [ ] WebSocket connections stable

### Phase 3: Live Dry Run ✅

- [ ] System runs 24h+ without errors
- [ ] Fill rate > 95%
- [ ] Latency < 100ms
- [ ] No risk limit breaches
- [ ] PnL tracking accurate

---

## Troubleshooting

### Issue: Connection Fails

**Check**:
- API credentials correct
- Network connectivity
- Broker service status
- Firewall/proxy settings

### Issue: Low Fill Rate

**Check**:
- Order prices competitive
- Market volatility
- Broker execution quality
- Order types appropriate

### Issue: High Latency

**Check**:
- Network latency to broker
- CPU usage
- Cycle time configuration
- WebSocket vs REST usage

### Issue: Circuit Breaker Tripped

**Check**:
- Recent errors in logs
- Broker API status
- Network issues
- Configuration thresholds

---

## Final Validation

Before live trading with real capital:

- [ ] ✅ Phase 1 passed (paper trading)
- [ ] ✅ Phase 2 passed (all broker testnets)
- [ ] ✅ Phase 3 passed (24h+ dry run)
- [ ] ✅ All monitoring metrics within limits
- [ ] ✅ No critical errors in logs
- [ ] ✅ Risk controls tested (kill switch)
- [ ] ✅ Documentation reviewed
- [ ] ✅ Team approved for production

---

## Next Steps

Once all validation passes:

1. **Increase Capital Gradually**: Start with small amounts
2. **Monitor Closely**: Watch first week closely
3. **Scale Slowly**: Increase position sizes incrementally
4. **Review Regularly**: Daily performance reviews
5. **Continuous Improvement**: Tune parameters based on results

---

**Status**: Ready for Production Validation  
**Last Updated**: December 2024  
**Version**: Phase 10 Complete

**⚠️ Warning**: Never trade with real capital until all validation phases pass successfully!
