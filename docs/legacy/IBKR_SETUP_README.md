# IBKR Paper Trading Setup for AutoTrader

This guide will help you set up Interactive Brokers paper trading integration with AutoTrader.

## ✅ Prerequisites

1. **IBKR Paper Trading Account**: You have account `DU0071381` (confirmed active)
2. **TWS Software**: Trader Workstation installed and running
3. **API Access**: TWS configured for API connections
4. **Python Library**: `ib_insync` installed

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install ib_insync
```

### 2. Start TWS
- Launch Trader Workstation
- Log in with your paper trading account (DU0071381)
- Ensure TWS is running on the default port (7497 for paper trading)

### 3. Enable API Connections
In TWS:
1. Go to `Configure` → `API` → `Settings`
2. Check `Enable ActiveX and Socket Clients`
3. Check `Allow connections from localhost only` (recommended for security)
4. Set `Socket port: 7497` (should be default for paper trading)
5. Click `OK`

### 4. Test Connection
```bash
python test_ibkr_connection.py
```

You should see:
```
✅ AutoTrader imports successful
✅ Broker created successfully
✅ Account access successful
Account Value: $XXXXXX.XX
```

## 📁 Configuration Files

### `ibkr_config.json`
Standalone JSON configuration for IBKR settings:
```json
{
  "ibkr": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 1,
    "account_id": "DU0071381",
    "timeout": 60,
    "readonly": false
  }
}
```

### `configs/broker_credentials.yaml`
Updated with your IBKR settings (already configured):
```yaml
ibkr:
  enabled: true
  host: "127.0.0.1"
  port: 7497
  client_id: 1
  account_id: "DU0071381"
  timeout: 60
  readonly: false
```

## 🐍 Usage Examples

### Basic Connection
```python
from bouncehunter.broker import create_broker

# Using config file
broker = create_broker("ibkr")

# Or explicit parameters
broker = create_broker("ibkr",
    host="127.0.0.1",
    port=7497,
    client_id=1
)
```

### Get Account Information
```python
account = broker.get_account()
print(f"Cash: ${account.cash:,.2f}")
print(f"Portfolio Value: ${account.portfolio_value:,.2f}")
print(f"Positions: {len(account.positions)}")
```

### Get Positions
```python
positions = broker.get_positions()
for pos in positions:
    print(f"{pos.ticker}: {pos.shares} shares @ ${pos.avg_price:.2f}")
```

### Place Orders
```python
from bouncehunter.broker import OrderSide, OrderType

# Market order
order = broker.place_order(
    ticker="AAPL",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=10
)

# Bracket order (entry + stop loss + target)
bracket = broker.place_bracket_order(
    ticker="AAPL",
    entry_side=OrderSide.BUY,
    quantity=10,
    entry_price=150.0,
    stop_price=145.0,
    target_price=160.0
)
```

## 🔧 Advanced Configuration

### Environment Variables (Production)
Set these instead of config files:
```bash
# Windows PowerShell
$env:IBKR_HOST="127.0.0.1"
$env:IBKR_PORT="7497"
$env:IBKR_CLIENT_ID="1"
$env:IBKR_ACCOUNT_ID="DU0071381"

# Linux/Mac
export IBKR_HOST="127.0.0.1"
export IBKR_PORT="7497"
export IBKR_CLIENT_ID="1"
export IBKR_ACCOUNT_ID="DU0071381"
```

### Multiple Client IDs
If you need multiple connections, use different client IDs:
```python
broker1 = create_broker("ibkr", client_id=1)
broker2 = create_broker("ibkr", client_id=2)
```

### Live Trading (When Ready)
Switch to live trading by changing the port:
```yaml
ibkr:
  enabled: true
  host: "127.0.0.1"
  port: 7496  # Live trading port
  client_id: 1
  account_id: "YOUR_LIVE_ACCOUNT"  # Your live account number
```

## 🧪 Testing

### Run IBKR Tests
```bash
# Run all broker tests
pytest tests/test_broker.py -v -k "ibkr"

# Run specific IBKR test
pytest tests/test_broker.py::TestIBKRBroker::test_get_account -v
```

### Integration Testing
```bash
# Test with other components
pytest tests/test_e2e_workflows.py -v -k "ibkr"
```

## 🚨 Troubleshooting

### Common Issues

**"ib_insync not installed"**
```bash
pip install ib_insync
```

**"Connection refused"**
- Ensure TWS is running
- Check port 7497 is not blocked by firewall
- Verify API is enabled in TWS settings

**"Client ID already in use"**
- Change client_id in config (try 2, 3, etc.)
- Or restart TWS to clear existing connections

**"Account not found"**
- Verify account number in config matches TWS
- For paper trading, ensure you're logged into paper account

**"No positions found"**
- Normal for new paper accounts
- Place a test order to create positions

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

broker = create_broker("ibkr")
```

### TWS API Settings Checklist
- [ ] Enable ActiveX and Socket Clients
- [ ] Allow connections from localhost
- [ ] Socket port set to 7497 (paper) or 7496 (live)
- [ ] API logging enabled (optional, for debugging)

## 📊 Features Supported

- ✅ Account information retrieval
- ✅ Position tracking
- ✅ Market/Limit orders
- ✅ Bracket orders (entry + stop + target)
- ✅ Order status monitoring
- ✅ Risk management checks
- ✅ Connection management
- ✅ Paper and live trading modes

## 🔒 Security Notes

- Never commit API credentials to version control
- Use environment variables in production
- Enable TWS API logging to monitor connections
- Regularly rotate client IDs if needed
- Consider IP restrictions for live trading accounts

## 📞 Support

If you encounter issues:
1. Check TWS API logs: `C:\TWS API\log`
2. Run the test script: `python test_ibkr_connection.py`
3. Verify TWS settings match configuration
4. Check that ib_insync is properly installed

For IBKR-specific issues, consult the [IBKR API documentation](https://interactivebrokers.github.io/tws-api/) or their support forums.