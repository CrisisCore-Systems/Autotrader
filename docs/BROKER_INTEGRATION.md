# 🔌 Broker API Integration Guide

## Overview

BounceHunter supports **pluggable broker integrations** for live trading. The system uses an abstract `BrokerAPI` interface that can wrap any broker (Alpaca, IBKR, TD Ameritrade, etc.).

## Architecture

```
Agentic System
      ↓
   Trader Agent ← BrokerAPI (abstract)
      ↓                ↓
   Orders        PaperBroker | AlpacaBroker | IBKRBroker (future)
```

## Supported Brokers

### 1. PaperBroker (Built-in)
- **Simulated trading** with no real money
- Perfect for testing agent logic
- Tracks positions, fills, P&L in memory

### 2. AlpacaBroker (Live Integration)
- Free API for US stocks
- Commission-free trading
- Paper and live modes
- Bracket orders supported

### 3. Future Integrations
- Interactive Brokers (IBKR)
- TD Ameritrade
- Robinhood
- Webull

## Installation

### PaperBroker (No Dependencies)
```bash
# Already included - no extra packages needed
```

### Alpaca
```bash
pip install alpaca-py
```

### Interactive Brokers (Future)
```bash
pip install ib_insync
```

## Usage

### Alert-Only Mode (Default - No Broker)
```bash
# Just scan and log signals - no orders placed
python -m bouncehunter.agentic_cli --mode scan --config configs/telegram_pro.yaml
```

Output:
```
Actions:
  AAPL:
    Action: ALERT
    Entry: $172.50
    Size: 1.20%
```

### Paper Trading Mode
```bash
# Simulated orders with PaperBroker
python -m bouncehunter.agentic_cli \
    --mode scan \
    --broker paper \
    --config configs/telegram_pro.yaml
```

Output:
```
Using PaperBroker (simulated trading)
Actions:
  AAPL:
    Action: BUY
    Entry: $172.50
    Size: 1.20%
    Reason: Approved by all agents | Order ID: PAPER-1
```

### Alpaca Paper Trading
```bash
# Real Alpaca API but paper account
python -m bouncehunter.agentic_cli \
    --mode scan \
    --broker alpaca \
    --broker-key "YOUR_API_KEY" \
    --broker-secret "YOUR_SECRET_KEY" \
    --config configs/telegram_pro.yaml
```

Set `live_trading: false` in YAML to use Alpaca's paper account.

### Alpaca Live Trading ⚠️
```bash
# REAL MONEY - be careful!
python -m bouncehunter.agentic_cli \
    --mode scan \
    --broker alpaca \
    --broker-key "YOUR_LIVE_API_KEY" \
    --broker-secret "YOUR_LIVE_SECRET_KEY" \
    --config configs/telegram_pro.yaml
```

Set `live_trading: true` in YAML to use real Alpaca account.

## Configuration

Add broker credentials to your YAML config:

```yaml
scanner:
  # ... existing config ...
  live_trading: false  # Set to true for live trading

broker:
  type: "alpaca"  # or "paper", "ibkr"
  api_key: "YOUR_API_KEY"  # Optional: set via CLI instead
  secret_key: "YOUR_SECRET_KEY"
  paper: true  # Alpaca paper account
```

**Security Note**: Don't commit API keys to git! Use environment variables or CLI args:

```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET="your_secret"

python -m bouncehunter.agentic_cli \
    --broker alpaca \
    --broker-key "$ALPACA_API_KEY" \
    --broker-secret "$ALPACA_SECRET"
```

## Order Types

### Bracket Order (Recommended)
The Trader agent places **bracket orders** by default:
- **Entry**: Limit order at signal entry price
- **Stop Loss**: Stop order at signal stop price
- **Take Profit**: Limit order at signal target price

Example:
```python
broker.place_bracket_order(
    ticker="AAPL",
    quantity=10,
    entry_price=172.50,
    stop_price=168.20,
    target_price=179.80,
)
```

Benefits:
- ✅ Risk defined upfront
- ✅ No emotional exits
- ✅ Automatic profit-taking
- ✅ One-cancels-other (OCO) logic

### Market Order (Fallback)
```python
broker.place_order(
    ticker="AAPL",
    side=OrderSide.BUY,
    quantity=10,
    order_type=OrderType.MARKET,
)
```

### Limit Order
```python
broker.place_order(
    ticker="AAPL",
    side=OrderSide.BUY,
    quantity=10,
    order_type=OrderType.LIMIT,
    limit_price=172.50,
)
```

## Position Sizing

The Trader agent calculates position size automatically:

```python
# Get account value
account = broker.get_account()
portfolio_value = account.portfolio_value

# Risk percentage from policy
size_pct = 0.012  # 1.2% for normal regime

# Calculate position
position_value = portfolio_value * size_pct
shares = int(position_value / entry_price)
```

Example:
- Portfolio: $100,000
- Size: 1.2%
- Entry: $172.50
- **Shares**: int($1,200 / $172.50) = **6 shares**

## Position Tracking

### Get All Positions
```python
positions = broker.get_positions()
for pos in positions:
    print(f"{pos.ticker}: {pos.shares} shares @ ${pos.avg_price:.2f}")
    print(f"  Current: ${pos.current_price:.2f}")
    print(f"  P&L: ${pos.unrealized_pnl:.2f} ({pos.unrealized_pnl_pct:.1%})")
```

### Get Single Position
```python
position = broker.get_position("AAPL")
if position:
    print(f"Holding {position.shares} shares of AAPL")
```

### Close Position
```python
order = broker.close_position("AAPL")
print(f"Closed AAPL: Order {order.order_id}")
```

## Account Information

```python
account = broker.get_account()
print(f"Cash: ${account.cash:,.2f}")
print(f"Portfolio Value: ${account.portfolio_value:,.2f}")
print(f"Buying Power: ${account.buying_power:,.2f}")
print(f"Equity: ${account.equity:,.2f}")
print(f"Open Positions: {len(account.positions)}")
```

## Order Tracking

### Check Order Status
```python
order = broker.get_order("ORDER-123")
print(f"Status: {order.status}")
print(f"Filled: {order.filled_qty}/{order.quantity}")
if order.filled_price:
    print(f"Fill Price: ${order.filled_price:.2f}")
```

### Cancel Order
```python
success = broker.cancel_order("ORDER-123")
if success:
    print("Order cancelled")
```

## Market Hours Check

```python
if broker.is_market_open():
    print("Market is open - safe to trade")
else:
    print("Market is closed - orders will queue")
```

## Error Handling

The Trader agent wraps broker calls in try-except:

```python
try:
    orders = broker.place_bracket_order(...)
    action.reason += f" | Order ID: {orders['entry'].order_id}"
except Exception as e:
    action.reason += f" | Order failed: {str(e)}"
```

Common errors:
- **Insufficient buying power**: Reduce position size
- **Market closed**: Check `is_market_open()`
- **Invalid ticker**: Verify symbol exists
- **Order rejected**: Check price bounds, liquidity

## Integration Examples

### Example 1: Alert-Only → Paper → Live Progression

**Week 1: Alert-Only**
```bash
python -m bouncehunter.agentic_cli --mode scan
```
- Review signal quality
- Validate agent logic
- No orders placed

**Week 2-4: Paper Trading**
```bash
python -m bouncehunter.agentic_cli --mode scan --broker paper
```
- Test position sizing
- Validate bracket orders
- Track simulated P&L

**Month 2+: Alpaca Paper**
```bash
python -m bouncehunter.agentic_cli --mode scan --broker alpaca --broker-key ... --broker-secret ...
```
- Real API integration
- Verify order fills
- Test error handling

**Month 3+: Live Trading (Small Size)**
```yaml
scanner:
  live_trading: true
  size_pct_base: 0.005  # Start with 0.5% instead of 1.2%
```
```bash
python -m bouncehunter.agentic_cli --mode scan --broker alpaca --broker-key ... --broker-secret ...
```
- Real money, small positions
- Monitor closely for first month
- Scale up after validation

### Example 2: Querying Positions

```python
from bouncehunter.broker import create_broker

# Connect to broker
broker = create_broker("alpaca", api_key="...", secret_key="...", paper=True)

# Check account
account = broker.get_account()
print(f"Portfolio Value: ${account.portfolio_value:,.2f}")

# List positions
for pos in broker.get_positions():
    pnl_symbol = "🟢" if pos.unrealized_pnl > 0 else "🔴"
    print(f"{pnl_symbol} {pos.ticker}: {pos.shares} @ ${pos.avg_price:.2f} | P&L: ${pos.unrealized_pnl:.2f}")
```

### Example 3: Custom Broker Implementation

```python
from bouncehunter.broker import BrokerAPI, Order, Position, Account

class MyBroker(BrokerAPI):
    def __init__(self, credentials):
        self.client = MyBrokerClient(credentials)
    
    def get_account(self) -> Account:
        # Implement account fetch
        pass
    
    def place_order(self, ticker, side, quantity, order_type, **kwargs) -> Order:
        # Implement order placement
        pass
    
    # ... implement other abstract methods
```

## Safety Features

### Portfolio Limits (Enforced by RiskOfficer)
- **Max concurrent positions**: 8 (Pro profile)
- **Max per sector**: 3
- **Base-rate floor**: 40% (eject tickers below this)

### Position Sizing Limits
- **Normal regime**: 1.2% per trade
- **High-VIX regime**: 0.6% per trade (halved)
- **SPY stress**: 0.6% per trade

### Order Validation
- Entry price must be > 0
- Stop price must be < entry
- Target price must be > entry
- Quantity must be > 0

### Broker-Level Safety
- Paper trading by default
- Explicit `live_trading: true` required
- Buying power checks
- Market hours enforcement

## Monitoring & Logging

The Historian agent logs all orders to SQLite:

```sql
-- Check recent fills
SELECT * FROM fills 
ORDER BY entry_date DESC 
LIMIT 10;

-- Check open positions
SELECT f.ticker, f.shares, f.entry_price, f.entry_date
FROM fills f
LEFT JOIN outcomes o ON f.fill_id = o.fill_id
WHERE o.outcome_id IS NULL;

-- Check P&L by ticker
SELECT 
    f.ticker,
    COUNT(*) as trades,
    AVG(o.return_pct) as avg_return,
    SUM(CASE WHEN o.hit_target THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as hit_rate
FROM fills f
JOIN outcomes o ON f.fill_id = o.fill_id
GROUP BY f.ticker
ORDER BY avg_return DESC;
```

## Troubleshooting

### "Order failed: Insufficient buying power"
**Solution**: Reduce `size_pct_base` in config or increase account value.

### "Order failed: Market is closed"
**Solution**: Check `is_market_open()` before scanning or queue orders for market open.

### "Alpaca authentication failed"
**Solution**: Verify API keys are correct and not expired. Check paper vs live keys.

### "Order rejected: Price too far from market"
**Solution**: Entry price limit orders may not fill if market moves. Consider market orders or wider limits.

### "No positions showing up"
**Solution**: Bracket orders may take time to fill. Check order status with `get_order()`.

## Best Practices

1. **Start with Alert-Only**: Validate signal quality for 1-2 weeks
2. **Progress to Paper**: Test broker integration without risk
3. **Small Live Positions**: Start with 0.5% size instead of 1.2%
4. **Monitor Daily**: Check fills, positions, and order status
5. **Audit Weekly**: Run base-rate analysis, eject bad tickers
6. **Circuit Breakers**: Set drawdown limits (-10% → halt trading)
7. **Backup Credentials**: Store API keys securely (env vars, not git)
8. **Test Errors**: Simulate failures (bad ticker, insufficient funds)
9. **Logging**: Keep audit trail of all orders and fills
10. **Diversify**: Use sector caps to avoid concentration risk

## Next Steps

1. **Get Alpaca Account**: Sign up at https://alpaca.markets (free paper account)
2. **Generate API Keys**: Dashboard → API Keys → Create New
3. **Test Paper Trading**: Run scan with `--broker alpaca`
4. **Monitor for 1 Month**: Track hit rate, P&L, errors
5. **Scale to Live**: Reduce size, enable `live_trading: true`, deploy cron job

## Support

- **Alpaca Docs**: https://alpaca.markets/docs/
- **IBKR API**: https://www.interactivebrokers.com/en/index.php?f=5041
- **TD Ameritrade**: https://developer.tdameritrade.com/

---

**Status**: ✅ Broker integration complete, ready for paper trading  
**Next**: Set up Alpaca paper account and run first bracket order test
