# Trading Workspace Quick Reference

Quick guide for using the BounceHunter/PennyHunter Trading Workspace.

---

## Getting Started

### 1. Start the API Server
```bash
cd /home/runner/work/Autotrader/Autotrader
uvicorn src.api.dashboard_api:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Start the Dashboard
```bash
cd dashboard
npm install  # First time only
npm run dev
```

### 3. Access the Dashboard
Open browser to: `http://localhost:5173`

---

## Trading Workspace Layout

```
┌─────────────────────────────────────────────┐
│  RUNBOARD                                   │
│  Session Date | Regime | Phase 2 Progress   │
└─────────────────────────────────────────────┘

┌──────────────────────┐ ┌──────────────────────┐
│  SIGNALS QUEUE       │ │  ORDERS PANEL        │
│  Quality-filtered    │ │  Place paper orders  │
│  gap opportunities   │ │  Two-step confirm    │
└──────────────────────┘ └──────────────────────┘

┌──────────────────────┐ ┌──────────────────────┐
│  BROKER STATUS       │ │  POSITIONS PANEL     │
│  Connection status   │ │  Live P&L tracking   │
│  for all brokers     │ │  Exposure monitoring │
└──────────────────────┘ └──────────────────────┘
```

---

## Daily Workflow

### Morning Routine (Pre-Market)

1. **Check Market Regime** (Runboard)
   - ✅ Risk On: SPY > MA200, VIX < 20 → Trading allowed
   - ⚠️ Neutral: Mixed signals → Trade with caution
   - ❌ Risk Off: SPY < MA200, VIX > 30 → No trading

2. **Review Phase 2 Progress** (Runboard)
   - Current: X/20 trades
   - Win rate: X% (target 65-75%)
   - Remaining: 20-X trades needed

### During Market Hours

3. **Monitor Signals Queue**
   - Signals auto-refresh every 5 minutes
   - Only shows quality ≥5.5 by default
   - Adjust threshold using filter controls
   - Click signal to populate order form

4. **Place Paper Orders**
   - Review signal details in order form
   - Adjust quantity if needed
   - Click "Place Order" → Review preview
   - Click "Confirm Order" → Execute

5. **Track Positions**
   - Auto-updates every 10 seconds
   - Monitor unrealized P&L
   - Watch exposure percentages

6. **Monitor Orders**
   - Track order status (pending/filled)
   - See fill prices and timestamps

### End of Day

7. **Validate Completed Trades**
   - Mark wins/losses for Phase 2
   - Add notes to trade journal
   - Review Phase 2 progress

---

## Signal Quality Gates

### Quality Score Components (0-10 scale)
- Gap magnitude (0-2 pts)
- Volume validation (0-2 pts)
- Market cap validation (0-2 pts)
- Price level (0-2 pts)
- Risk:reward ratio (0-2 pts)

### Minimum Thresholds
- **Conservative**: ≥7.0 (high quality only)
- **Standard**: ≥5.5 (default)
- **Aggressive**: ≥4.0 (more signals, lower quality)

---

## Advanced Filters

Each signal passes through 5 risk modules:

1. **Liquidity Delta**: Checks for liquidity drain (≥-30%)
2. **Slippage**: Estimates execution slippage (≤5%)
3. **Cash Runway**: Validates company has 6+ months cash
4. **Sector Diversification**: Max 3 positions per sector
5. **Volume Fade**: Detects declining volume trend

✅ Green badge = Filter passed  
❌ Red badge = Filter failed

---

## Order Placement

### Two-Step Confirmation

**Step 1: Preview**
- Review ticker, quantity, prices
- See risk amount ($)
- See profit target ($)
- See R:R ratio

**Step 2: Confirm**
- Verify all details
- Click "Confirm Order"
- Bracket order created:
  - Entry order (limit)
  - Stop loss (stop)
  - Target (limit)

### Order Types
- **Entry**: Limit order at entry price
- **Stop**: Stop loss at stop price
- **Target**: Limit order at target price

---

## Position Management

### Key Metrics
- **Market Value**: Current position value
- **Unrealized P&L**: Profit/loss since entry
- **P&L %**: Percentage gain/loss
- **Exposure**: % of total portfolio

### Exit Strategy
Bracket orders automatically manage exits:
- Stop loss triggers on downside
- Target triggers on upside
- Only one will execute (OCO logic)

---

## Phase 2 Validation

### Goal
Accumulate 20 completed trades to validate:
- Win rate ≥65%
- Improvement vs 50% baseline

### Progress Tracking
- Trades completed: X/20
- Win rate: X%
- Total P&L: $X.XX
- Status: In Progress / Success / Needs Review

### Marking Trades
After trade closes:
1. Navigate to validation panel
2. Enter ticker and outcome (win/loss)
3. Enter P&L amount
4. Add notes (optional)
5. Click "Mark for Validation"

---

## Broker Status

### Paper Broker
- ✅ Always online
- $100,000 starting capital
- No real money at risk

### Live Brokers (If Configured)
- **Alpaca**: US broker
- **Questrade**: Canadian broker
- **Interactive Brokers**: Global broker

Status indicators:
- 🟢 Online: Connected and ready
- 🟡 Not Configured: Credentials missing
- 🔴 Error: Connection failed

---

## Troubleshooting

### Signals Not Showing
- Check market regime (may block trading)
- Lower quality threshold
- Verify market is open
- Check scanner logs

### Orders Not Filling
- Paper orders fill immediately at limit price
- Check order status in Orders Panel
- Verify broker connection

### Positions Not Updating
- Wait for next refresh (10s)
- Click refresh button
- Check broker connectivity

### Phase 2 Progress Not Updating
- Ensure trades are marked for validation
- Check cumulative history file
- Verify memory DB is accessible

---

## Keyboard Shortcuts (Planned)

- `R` - Refresh all data
- `S` - Focus signal search
- `O` - Open order form
- `P` - View positions
- `Esc` - Cancel/close modal

---

## API Endpoints (For Debugging)

### Direct API Access
Base URL: `http://localhost:8001`

- `GET /api/trading/regime` - Market regime
- `GET /api/trading/phase2-progress` - Progress
- `GET /api/trading/signals` - Signals queue
- `POST /api/trading/paper-order` - Place order
- `GET /api/trading/positions` - Positions
- `GET /api/trading/orders` - Orders
- `GET /api/trading/broker-status` - Broker status
- `POST /api/trading/validate` - Mark validation

API Docs: `http://localhost:8001/docs`

---

## Best Practices

### Risk Management
- ✅ Only trade when regime allows
- ✅ Respect quality gates (≥5.5)
- ✅ Check advanced filters
- ✅ Limit position sizes
- ✅ Monitor total exposure

### Trade Discipline
- ✅ Use two-step confirmation
- ✅ Let bracket orders work
- ✅ Don't override stop losses
- ✅ Take profits at target
- ✅ Record all trades for Phase 2

### System Health
- ✅ Monitor broker connections
- ✅ Watch for API errors
- ✅ Verify data freshness
- ✅ Keep logs for debugging

---

## Support

### Common Issues
1. **Regime blocking trades**: Wait for better market conditions
2. **No signals found**: Lower quality threshold or check scanner
3. **Broker disconnected**: Check credentials and network
4. **Slow performance**: Reduce refresh rates or restart services

### Files to Check
- API logs: Check console output
- Trade history: `reports/pennyhunter_cumulative_history.json`
- Memory DB: `reports/pennyhunter_memory.db`
- Broker config: `configs/broker_credentials.yaml`

### Getting Help
1. Check API docs: `http://localhost:8001/docs`
2. Review implementation guide: `TRADING_WORKSPACE_IMPLEMENTATION.md`
3. Check test suite: `tests/test_trading_api.py`
4. Review broker integration: `src/bouncehunter/broker.py`

---

## Quick Stats

- **API Endpoints**: 8 trading endpoints
- **UI Components**: 6 React components
- **Refresh Rates**: 10s to 5m (configurable)
- **Test Coverage**: 16 comprehensive tests
- **Supported Brokers**: 4 (Paper/Alpaca/Questrade/IBKR)

---

**Version**: 1.0  
**Last Updated**: October 22, 2025  
**Status**: Historical workspace quick reference snapshot
