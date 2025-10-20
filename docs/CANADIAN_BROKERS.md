# Canadian Trading Platform Integration

Complete guide for Canadian traders to integrate live trading with BounceHunter.

## 🇨🇦 Supported Canadian Platforms

### 1. Questrade (Recommended for Canadians)
- **Best For**: Canadian retail traders
- **Pros**: Canadian company, competitive fees, good API
- **Cons**: Manual bracket order management
- **Cost**: $4.95-$9.95/trade, free for ETFs
- **Account Types**: TFSA, RRSP, Margin

### 2. Interactive Brokers Canada (IBKR)
- **Best For**: Active traders, multi-market access
- **Pros**: Lowest fees, best execution, global markets, native bracket orders
- **Cons**: $10k minimum (or $100/month inactivity fee), more complex
- **Cost**: $0.005/share (min $1), $1/trade for IBKR Lite
- **Account Types**: TFSA, RRSP, Margin

### 3. Alpaca (US-based, available to Canadians)
- **Best For**: Paper trading, testing strategies
- **Pros**: Free API, commission-free, excellent for testing
- **Cons**: No registered accounts (TFSA/RRSP), USD only
- **Cost**: Commission-free

---

## Quick Setup

### Questrade Setup

**1. Get API Access**
```bash
# Sign up at questrade.com
# Go to Account Management → API Access
# Create new application, get refresh token
```

**2. Install Dependencies**
```bash
pip install questrade-api
```

**3. Run with Questrade**
```bash
# Paper trading (practice mode)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --config configs/telegram_pro.yaml \
  --broker questrade \
  --broker-key "YOUR_REFRESH_TOKEN"
```

**4. Refresh Token Management**
Questrade tokens expire. Store the new token from API responses:
```python
from questrade_api import Questrade

qt = Questrade(refresh_token="OLD_TOKEN")
# After successful API call, save the new token:
new_token = qt.refresh_token
# Store this securely and use it next time
```

---

### Interactive Brokers Setup

**1. Download TWS or IB Gateway**
```bash
# Download from: interactivebrokers.com
# TWS: Full platform (heavier)
# IB Gateway: Lightweight API-only (recommended)
```

**2. Install Dependencies**
```bash
pip install ib_insync
```

**3. Configure TWS/Gateway**
- Open TWS or IB Gateway
- Go to: File → Global Configuration → API → Settings
- Enable: "Enable ActiveX and Socket Clients"
- Socket Port: 7497 (paper) or 7496 (live)
- Trusted IPs: 127.0.0.1

**4. Run with IBKR**
```bash
# Make sure TWS/Gateway is running first!

# Paper trading (port 7497)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --config configs/telegram_pro.yaml \
  --broker ibkr \
  --broker-port 7497

# Live trading (port 7496) - USE WITH CAUTION
python -m bouncehunter.agentic_cli \
  --mode scan \
  --config configs/telegram_pro.yaml \
  --broker ibkr \
  --broker-port 7496
```

**5. IBKR Advantages**
- Native bracket order support (one API call for entry + stop + target)
- Best execution and lowest fees
- Access to Canadian (TSX) and US markets
- Real-time market data

---

### Alpaca Setup (US-based)

**1. Sign Up**
```bash
# Sign up at alpaca.markets (free, no minimum)
# Verify account with email/phone
```

**2. Get API Keys**
```bash
# Dashboard → API Keys
# Generate paper trading keys
# Copy API Key and Secret Key
```

**3. Install Dependencies**
```bash
pip install alpaca-py
```

**4. Run with Alpaca**
```bash
# Paper trading
python -m bouncehunter.agentic_cli \
  --mode scan \
  --config configs/telegram_pro.yaml \
  --broker alpaca \
  --broker-key "YOUR_API_KEY" \
  --broker-secret "YOUR_SECRET_KEY"
```

---

## Broker Comparison Table

| Feature | Questrade | IBKR Canada | Alpaca |
|---------|-----------|-------------|---------|
| **Canadian Company** | ✅ Yes | ❌ No (US/global) | ❌ No (US) |
| **TFSA/RRSP** | ✅ Yes | ✅ Yes | ❌ No |
| **TSX Stocks** | ✅ Yes | ✅ Yes | ❌ US only |
| **US Stocks** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Minimum Balance** | $1,000 | $10,000 | $0 |
| **Commission** | $4.95-$9.95 | $1-$5 | $0 |
| **Bracket Orders** | ⚠️ Manual | ✅ Native | ✅ Native |
| **API Quality** | ⭐⭐⭐ Good | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Great |
| **Paper Trading** | ❌ No | ✅ Yes | ✅ Yes |
| **Best For** | TFSA traders | Active traders | Testing only |

---

## Usage Examples

### Example 1: Questrade with TFSA Account
```bash
# Use Questrade for tax-advantaged trading
python -m bouncehunter.agentic_cli \
  --mode scan \
  --config configs/telegram_conservative.yaml \
  --broker questrade \
  --broker-key "$(cat ~/.questrade_token)"
```

### Example 2: IBKR with Canadian Dollars
```python
# In broker.py, modify IBKRBroker to use CAD:
contract = self.Stock(ticker, "SMART", "CAD")  # Change from USD to CAD
```

### Example 3: Multi-Broker Testing
```bash
# Test with PaperBroker first
python -m bouncehunter.agentic_cli --broker paper --config configs/test.yaml

# Then IBKR paper account
python -m bouncehunter.agentic_cli --broker ibkr --broker-port 7497 --config configs/test.yaml

# Finally Questrade (if satisfied)
python -m bouncehunter.agentic_cli --broker questrade --broker-key TOKEN --config configs/test.yaml
```

---

## Position Sizing for Canadian Accounts

### TFSA Limits (2025)
```yaml
# configs/canadian_tfsa.yaml
risk_controls:
  max_position_size_pct: 1.0  # 1% per position
  max_positions: 5            # Conservative for TFSA
  size_pct_base: 0.008        # 0.8% base size

scanner:
  min_bcs: 0.68              # Higher threshold for registered accounts
```

**Reasoning**: TFSA contribution room is limited ($95,000 cumulative in 2025). Use conservative sizing to avoid over-leveraging.

### RRSP/Margin Accounts
```yaml
# configs/canadian_margin.yaml
risk_controls:
  max_position_size_pct: 1.5  # 1.5% max
  max_positions: 8
  size_pct_base: 0.012        # 1.2% base size

scanner:
  min_bcs: 0.62              # Pro-level threshold
```

---

## Questrade Specifics

### Bracket Order Workaround
Questrade doesn't support native bracket orders. You need to:

1. Place entry limit order
2. Monitor for fill
3. When filled, place stop loss + target orders

**Automated Approach** (in `broker.py`):
```python
# After entry fills, automatically place exit orders
def _monitor_and_place_exits(self, entry_order_id, ticker, quantity, stop, target):
    # Poll until entry fills
    while True:
        order = self.get_order(entry_order_id)
        if order.status == OrderStatus.FILLED:
            # Place stop loss
            self.place_order(ticker, OrderSide.SELL, quantity, 
                           OrderType.STOP, stop_price=stop)
            # Place target
            self.place_order(ticker, OrderSide.SELL, quantity, 
                           OrderType.LIMIT, limit_price=target)
            break
        time.sleep(30)  # Check every 30 seconds
```

### Currency Conversion
Questrade supports both CAD and USD accounts:
```python
# For CAD stocks (TSX)
symbol_info = self.qt.symbols_search(prefix=f"{ticker}.TO")  # .TO for TSX

# For US stocks (converted to CAD)
symbol_info = self.qt.symbols_search(prefix=ticker)
```

### Commissions
- Min: $4.95/trade
- Max: $9.95/trade
- Active trader ($5k+ trades/quarter): $4.95 flat

**Impact on BounceHunter**:
```python
# Adjust profit targets to account for $10 round-trip commission
min_profit_target = (10.0 / quantity) + 0.03  # $10 commission + 3% gain
```

---

## IBKR Specifics

### Bracket Orders (Native Support)
```python
# IBKR supports true bracket orders (best for BounceHunter)
broker.place_bracket_order(
    ticker="AAPL",
    quantity=100,
    entry_price=150.0,
    stop_price=147.0,    # 2% stop loss
    target_price=154.5,  # 3% profit target
)
# All 3 orders placed atomically!
```

### Market Data Subscriptions
IBKR requires market data subscriptions:
- **US Equity**: $1.50/month (waived if $30+ commissions)
- **Canadian Equity**: $4.50/month

**Free Alternative**: Use delayed data (15-min delay) for backtesting.

### TWS/Gateway Must Be Running
```bash
# Start IB Gateway in background (Linux/Mac)
nohup ~/IBGateway/ibgateway &

# Windows: Run IB Gateway as Windows Service
# Or: Start manually before running scanner
```

### Account Minimum Workaround
If under $10k, expect $100/month inactivity fee unless:
- Generate $30+ commissions/month
- Under 25 years old (waived for youth)

---

## Security Best Practices

### 1. API Key Storage
```bash
# Never commit API keys to git!
echo "QUESTRADE_TOKEN=abc123..." >> .env
echo "IBKR_USERNAME=trader01" >> .env
echo "ALPACA_KEY=..." >> .env
echo "ALPACA_SECRET=..." >> .env

# Add to .gitignore
echo ".env" >> .gitignore
```

### 2. Environment Variables
```bash
# Load from .env
export QUESTRADE_TOKEN=$(grep QUESTRADE_TOKEN .env | cut -d '=' -f2)

# Use in CLI
python -m bouncehunter.agentic_cli \
  --broker questrade \
  --broker-key "$QUESTRADE_TOKEN"
```

### 3. Two-Factor Authentication
- **Questrade**: Enable 2FA in Account Settings
- **IBKR**: Enable 2FA (required for large accounts)
- **Alpaca**: Enable 2FA in Security Settings

### 4. Paper Trading First
```bash
# ALWAYS test with paper trading for at least 1 month
--broker ibkr --broker-port 7497  # IBKR paper
--broker alpaca  # Alpaca defaults to paper

# Questrade: Create practice account (if available)
```

---

## Troubleshooting

### Questrade: "Refresh token expired"
```bash
# Solution: Generate new refresh token from web portal
# Questrade tokens expire after 3 months of inactivity

# Manual refresh:
python
>>> from questrade_api import Questrade
>>> qt = Questrade(refresh_token="OLD_TOKEN")
>>> print(qt.refresh_token)  # Save this new token
```

### IBKR: "Socket connection failed"
```bash
# 1. Check TWS/Gateway is running
ps aux | grep tws  # Linux/Mac
tasklist | findstr java  # Windows

# 2. Check port configuration
# TWS: File → Global Configuration → API → Settings
# Socket Port: 7497 (paper) or 7496 (live)

# 3. Check firewall
# Allow Python through Windows Firewall
```

### IBKR: "No market data"
```bash
# Solution 1: Subscribe to market data in Account Management
# Solution 2: Use delayed data (15-min delay, free)

# In TWS: Edit → Global Configuration → Market Data → Display Delayed
```

### Questrade: "Symbol not found"
```bash
# TSX stocks need .TO suffix
ticker = "TD.TO"  # Toronto-Dominion Bank on TSX

# US stocks: No suffix
ticker = "AAPL"   # Apple on NASDAQ
```

---

## Testing Workflow (Progressive)

### Phase 1: PaperBroker (1 week)
```bash
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker paper \
  --config configs/telegram_pro.yaml
  
# Verify: Orders appear in output, fills tracked correctly
```

### Phase 2: IBKR Paper Account (2 weeks)
```bash
# Start IB Gateway first
~/IBGateway/ibgateway

# Run scanner
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker ibkr \
  --broker-port 7497 \
  --config configs/telegram_pro.yaml
  
# Verify: Orders appear in TWS, fills execute correctly, bracket orders work
```

### Phase 3: Questrade Practice (2 weeks, if available)
```bash
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker questrade \
  --broker-key "$QUESTRADE_PRACTICE_TOKEN" \
  --config configs/telegram_conservative.yaml
  
# Verify: Orders placed successfully, manual bracket management works
```

### Phase 4: Live Trading (Small Size)
```bash
# Reduce size to 0.5% for first 2 weeks
# Edit config:
risk_controls:
  size_pct_base: 0.005  # 0.5% instead of 1.2%
  max_positions: 3      # Conservative

# Run live (IBKR example)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker ibkr \
  --broker-port 7496 \  # LIVE PORT!
  --config configs/live_small.yaml
```

### Phase 5: Scale Up (1 month validation)
```bash
# After 1 month of successful live trading, scale to full size
risk_controls:
  size_pct_base: 0.012  # Back to 1.2%
  max_positions: 8
```

---

## Cost Comparison (Real Example)

**Scenario**: 100 shares of $50 stock, 3% gain, 2% stop

| Broker | Entry | Exit | Total | Net Gain |
|--------|-------|------|-------|----------|
| **Questrade** | $4.95 | $4.95 | $9.90 | $140.10 |
| **IBKR** | $1.00 | $1.00 | $2.00 | $148.00 |
| **Alpaca** | $0 | $0 | $0 | $150.00 |

**Annual Impact** (50 trades/year):
- Questrade: $495 in commissions
- IBKR: $100 in commissions
- Alpaca: $0 in commissions

**Recommendation**: 
- For TFSA with 20-30 trades/year: Questrade is fine
- For active trading (50+ trades/year): IBKR saves significant money
- For testing only: Alpaca (but no registered accounts)

---

## FAQ

**Q: Can I use BounceHunter with a Canadian TFSA?**  
A: Yes! Use Questrade or IBKR Canada with TFSA account type. Set conservative sizing (0.8-1.0%) to preserve contribution room.

**Q: Do I need USD account for US stocks?**  
A: No, but recommended. Questrade/IBKR auto-convert CAD→USD with 1-2% spread. Better to hold USD cash to avoid conversion fees.

**Q: Which broker is cheapest for Canadians?**  
A: IBKR has lowest fees ($1/trade), but requires $10k minimum. Questrade is good for smaller accounts ($1k minimum).

**Q: Can I trade TSX stocks?**  
A: Yes with Questrade/IBKR. Modify `broker.py` to use `.TO` suffix for TSX symbols.

**Q: Does BounceHunter work with Wealthsimple Trade?**  
A: No, Wealthsimple has very limited API. Not recommended for automated trading.

**Q: What about TD Direct Investing or BMO InvestorLine?**  
A: Neither offers good API access. Use Questrade or IBKR instead.

---

## Next Steps

1. **Choose your broker** (Questrade for TFSA, IBKR for active trading)
2. **Open paper account** (IBKR) or practice account
3. **Test PaperBroker** for 1 week
4. **Test real broker** in paper mode for 2 weeks
5. **Go live with small size** (0.5%) for 1 month
6. **Scale gradually** after validation

For support, see main [BROKER_INTEGRATION.md](BROKER_INTEGRATION.md) guide.
