# 🎯 PennyHunter GUI Dashboard - Quick Start

Beautiful, modern GUI for monitoring and controlling your paper trading system.

## Launch

```powershell
# From Autotrader directory
python gui_trading_dashboard.py
```

## Features

### 📊 Real-Time Market Status
- **VIX Display**: Current volatility with regime classification (LOW/NORMAL/HIGH)
- **SPY Tracking**: Price and daily change percentage
- **Market Regime**: Risk assessment (RISK_ON/RISK_OFF) with trading permission

### 📈 Position Monitoring
- Live position table with:
  - Symbol, shares, entry price
  - Current price and P&L ($ and %)
  - Target and stop levels
- Color-coded P&L (green/red)

### 📊 Performance Metrics
- **Total P&L**: Cumulative profit/loss
- **Win Rate**: Percentage of winning trades
- **Total Trades**: Trade count
- **Wins/Losses**: Breakdown by outcome
- **Active Positions**: Current open positions

### 🧠 Memory System
Three tabs showing ticker status:
- **Active**: High-performing tickers (green)
- **Monitored**: Underperforming but not ejected (yellow)
- **Ejected**: Removed from trading universe (red)

### ⚙️ Controls
- **START/STOP Scanner**: Control paper trading bot
- **REFRESH DATA**: Manual data update
- **SETTINGS**: Configure parameters

### 📝 System Logs
- Real-time activity log
- Timestamped events
- Error notifications

## UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 PennyHunter Paper Trading    Account: DUO071381 $200.00 │
├──────────────────────────────┬──────────────────────────────┤
│                              │  ⚙️ Controls                 │
│  📊 Market Status            │  ▶️ START SCANNER            │
│  [VIX] [SPY] [REGIME]        │  🔄 REFRESH DATA             │
│                              │  ⚙️ SETTINGS                 │
│  📈 Active Positions         ├──────────────────────────────┤
│  [Table: positions]          │  🧠 Memory System            │
│                              │  [Active][Monitored][Ejected]│
│  📊 Performance              │                              │
│  [Metrics grid]              ├──────────────────────────────┤
│                              │  📝 System Logs              │
│                              │  [Timestamped events]        │
├──────────────────────────────┴──────────────────────────────┤
│  ● Ready                               2025-10-20 22:15:00  │
└─────────────────────────────────────────────────────────────┘
```

## Color Scheme

**Dark Theme** (VS Code inspired):
- Background: Dark gray (#1e1e1e)
- Panels: Medium gray (#252526)
- Text: Light gray (#cccccc)
- Accents:
  - Blue (#007acc) - Primary actions
  - Green (#4ec9b0) - Profits, active items
  - Red (#f48771) - Losses, warnings
  - Yellow (#dcdcaa) - Cautions, monitored items
  - Purple (#c586c0) - Info, regime

## Data Updates

- **Market Data**: Every 30 seconds (background thread)
- **Manual Refresh**: Click "REFRESH DATA" button
- **Time Display**: Updates every second

## Requirements

```bash
# Core (already installed)
pip install tkinter  # Usually comes with Python
pip install pyyaml

# Optional (for charts - future enhancement)
pip install matplotlib
```

## Integration Points

### Currently Implemented
✅ Market data from Yahoo Finance (VIX, SPY)
✅ Memory system from `pennyhunter_memory.db`
✅ Configuration from `my_paper_config.yaml`

### Ready for Integration
🔄 Live positions from IBKR
🔄 Scanner start/stop control
🔄 Performance stats from database
🔄 Settings dialog for adjustments

## Architecture

```python
# Main components
TradingDashboard
├── UI Layout
│   ├── Title Bar (branding, account info)
│   ├── Left Panel (market + positions + performance)
│   └── Right Panel (controls + memory + logs)
├── Data Management
│   ├── load_config() - YAML configuration
│   ├── update_market_data() - Yahoo Finance
│   └── update_memory_status() - SQLite queries
└── Background Thread
    └── update_loop() - 30s refresh cycle
```

## Customization

### Change Update Frequency
```python
# In update_loop() method (line ~580)
time.sleep(30)  # Change to desired seconds
```

### Modify Colors
```python
# At top of file (lines 25-35)
BG_DARK = "#1e1e1e"      # Main background
ACCENT_BLUE = "#007acc"  # Primary buttons
ACCENT_GREEN = "#4ec9b0" # Profits
# ... etc
```

### Add More Metrics
```python
# In create_performance_panel()
self.create_metric(metrics_frame, "New Metric", "0", ACCENT_BLUE, row, col)
```

## Next Steps

### Phase 1: Basic Monitoring ✅
- [x] Market status display
- [x] Position table
- [x] Performance metrics
- [x] Memory system tabs
- [x] System logs

### Phase 2: Live Integration
- [ ] Connect to IBKR for live positions
- [ ] Real-time P&L updates
- [ ] Scanner process control
- [ ] Order placement from GUI

### Phase 3: Advanced Features
- [ ] Performance charts (matplotlib)
- [ ] Trade history viewer
- [ ] Adjustment calculator dialog
- [ ] Alert notifications
- [ ] Export reports

### Phase 4: Polish
- [ ] Settings persistence
- [ ] Multiple themes
- [ ] Keyboard shortcuts
- [ ] Tooltips and help

## Troubleshooting

### "Module not found: tkinter"
```bash
# Windows - usually pre-installed
# If missing, reinstall Python with tcl/tk enabled
```

### "Database file not found"
```
# Create databases by running paper trading first:
python run_pennyhunter_paper.py

# This creates:
# - bouncehunter_memory.db
# - reports/pennyhunter_memory.db
```

### GUI not updating
```
# Check background thread is running
# Look for errors in System Logs panel
# Try clicking REFRESH DATA button
```

## Development Mode

### Enable Debug Logging
```python
# Add at start of TradingDashboard.__init__()
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Without Dependencies
```python
# Set flags at top of file
HAS_MATPLOTLIB = False  # Disable charts
HAS_YFINANCE = False    # Disable market data
```

## Screenshots Walkthrough

**On Launch**:
- All panels visible
- "Ready" status (yellow)
- Empty positions table
- "No data" in memory tabs

**After REFRESH DATA**:
- VIX shows current value (e.g., 18.2)
- SPY shows price and change (e.g., $671.30 +0.60%)
- Regime shows RISK_ON
- Memory tabs populate from database

**When Scanner Running**:
- Status: "Running" (green)
- Button shows "STOP SCANNER" (red)
- Logs show activity
- Positions update as trades execute

## Support

For issues or questions:
1. Check System Logs panel for errors
2. Review `GUI_QUICKSTART.md` (this file)
3. Consult main documentation in `docs/`

## Quick Reference

| Action | Shortcut | Result |
|--------|----------|--------|
| Launch GUI | `python gui_trading_dashboard.py` | Opens dashboard |
| Start Scanner | Click ▶️ button | Begins paper trading |
| Stop Scanner | Click ⏸️ button | Halts trading |
| Refresh | Click 🔄 button | Updates all data |
| Close | X button or Alt+F4 | Graceful shutdown |

---

**Status**: GUI Foundation Complete ✅  
**Next**: Integrate with live IBKR data feeds 🚀  
**Version**: 1.0.0 (Initial Release)
