# 30-Day Paper Trading Deployment Guide

**Start Date**: October 18, 2025  
**End Date**: November 17, 2025  
**Status**: 🚀 READY TO DEPLOY  
**System Version**: Phase 3 Production with Agent Weighting v1.0

---

## 🎯 **Objectives**

1. **Validate Production Components** in live market conditions
2. **Collect Agent Performance Data** for weighted consensus training
3. **Achieve 60%+ Win Rate** over 30 days (20+ trades)
4. **Prove System Reliability** before live capital deployment

---

## 📋 **Pre-Deployment Checklist**

### ✅ **System Readiness**
- [x] Production GemScorer implemented (multi-factor analysis)
- [x] Real RegimeDetector integrated (VIX/SPY data)
- [x] NewsSentry sentiment analysis operational
- [x] GapScanner autonomous signal discovery
- [x] Agent weighting infrastructure ready
- [x] Database schema validated
- [x] 6-year backtest complete (75% WR, 6.0x PF)

### ✅ **Configuration**
- [x] Confidence threshold: 5.5 (normal), 7.5 (high-vix)
- [x] Binary veto mode: Active (trades 1-19)
- [x] Weighted mode: Auto-activates at trade 20
- [x] Risk per trade: 1% (normal), 0.5% (high-vix)
- [x] Max concurrent positions: 5

### 📝 **To Complete Before Start**
- [ ] Set up paper trading account (broker integration)
- [ ] Configure alert notifications (Slack/Discord/Email)
- [ ] Set up monitoring dashboard
- [ ] Schedule daily scan script (pre-market)
- [ ] Create trade journal spreadsheet

---

## 🏗️ **Infrastructure Setup**

### **1. Paper Trading Account**

Choose one of the following brokers:

| Broker | Paper Trading | API Quality | Recommended |
|--------|---------------|-------------|-------------|
| **Alpaca** | ✅ Free | Excellent | ⭐ BEST |
| **TD Ameritrade** | ✅ Free | Good | ⭐ Good |
| **Interactive Brokers** | ✅ Free | Excellent | ⭐ Advanced |
| **TradeStation** | ✅ Free | Good | ⭐ Alternative |

**Recommended: Alpaca Paper Trading**
- Free, unlimited paper trading
- Real-time market data
- Python SDK available
- Easy API integration

**Setup Steps:**
```bash
# 1. Sign up at https://alpaca.markets
# 2. Navigate to Paper Trading section
# 3. Generate API keys (KEY_ID and SECRET_KEY)
# 4. Store in environment variables
```

**Configuration File** (`configs/paper_trading.yaml`):
```yaml
broker:
  name: alpaca
  paper_trading: true
  api_key_id: ${ALPACA_API_KEY}
  api_secret: ${ALPACA_API_SECRET}
  base_url: https://paper-api.alpaca.markets

trading:
  initial_capital: 25000
  max_position_size: 2500  # 10% max per position
  risk_per_trade: 0.01  # 1%
  max_concurrent: 5
  
alerts:
  slack_webhook: ${SLACK_WEBHOOK_URL}
  email: ${NOTIFICATION_EMAIL}
```

### **2. Daily Scan Script**

Create automated pre-market scanner:

**File**: `scripts/run_daily_scan.py`
```python
#!/usr/bin/env python
"""
Daily pre-market scan for PennyHunter Paper Trading

Schedule to run at 8:30 AM ET (before market open)
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from bouncehunter.pennyhunter_agentic import Orchestrator, AgenticMemory, AgenticPolicy
from bouncehunter.config import BounceHunterConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/daily_scan.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Run daily pre-market scan."""
    logger.info("="*70)
    logger.info(f"PENNYHUNTER DAILY SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    # Initialize system
    config = BounceHunterConfig.from_yaml("configs/phase3.yaml")
    memory = AgenticMemory(
        agentic_db_path="reports/pennyhunter_agentic.db",
        base_db_path="reports/pennyhunter_memory.db"
    )
    policy = AgenticPolicy(
        config=config,
        live_trading=False,  # Paper trading mode
        min_confidence=5.5,
        min_confidence_highvix=7.5,
        auto_adapt_thresholds=True,
    )
    
    # Create orchestrator with paper trading broker
    orchestrator = Orchestrator(
        policy=policy,
        memory=memory,
        broker=None,  # TODO: Initialize Alpaca broker
    )
    
    # Run daily scan
    try:
        results = await orchestrator.run_daily_scan()
        
        logger.info(f"\n📊 SCAN RESULTS:")
        logger.info(f"  Context: {results['context']['regime']} regime")
        logger.info(f"  Signals Found: {results['signals']}")
        logger.info(f"  Approved: {results['approved']}")
        logger.info(f"  Actions: {len(results['actions'])}")
        
        if results['actions']:
            logger.info(f"\n🎯 TRADE ALERTS:")
            for action in results['actions']:
                logger.info(f"  {action['ticker']}: {action['action']} @ ${action['entry']:.2f}")
                logger.info(f"    Stop: ${action['stop']:.2f} | Target: ${action['target']:.2f}")
                logger.info(f"    Confidence: {action['confidence']:.1f}/10 | Size: {action['size_pct']*100:.1f}%")
        
        # Send alerts (Slack, Discord, Email)
        if results['actions']:
            await send_alerts(results)
        
        logger.info(f"\n✅ Daily scan complete!")
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Daily scan failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def send_alerts(results: dict):
    """Send trade alerts to configured channels."""
    # TODO: Implement Slack/Discord/Email alerts
    pass


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

**Windows Task Scheduler** (run daily at 8:30 AM ET):
```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "scripts/run_daily_scan.py" -WorkingDirectory "C:\Users\kay\Documents\Projects\AutoTrader\Autotrader"
$trigger = New-ScheduledTaskTrigger -Daily -At 8:30AM
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "PennyHunter-DailyScan" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

### **3. Trade Journal Spreadsheet**

**File**: `reports/paper_trading_journal.xlsx`

| Date | Ticker | Entry | Stop | Target | Size | Confidence | Regime | Agents | Outcome | Return | Notes |
|------|--------|-------|------|--------|------|------------|--------|--------|---------|--------|-------|
| 2025-10-18 | COMP | $7.50 | $7.13 | $8.25 | 1.0% | 6.5 | NORMAL | All ✅ | TARGET | +10% | Perfect gap |
| 2025-10-19 | EVGO | $4.20 | $3.99 | $4.62 | 1.0% | 7.0 | NORMAL | All ✅ | STOP | -5% | Failed bounce |

**Columns:**
- **Entry Date**: Signal date
- **Ticker**: Symbol
- **Entry/Stop/Target**: Price levels
- **Size**: Position size (% of capital)
- **Confidence**: Gem score (0-10)
- **Regime**: Market regime at entry
- **Agents**: Agent votes (✅/❌ per agent)
- **Outcome**: TARGET/STOP/TIME exit
- **Return**: Percentage gain/loss
- **Notes**: Trade observations

---

## 📊 **Daily Workflow**

### **8:00 AM ET - Pre-Market Preparation**
1. Check market regime (VIX, SPY 200 DMA)
2. Review overnight news for existing positions
3. Run daily scan script: `python scripts/run_daily_scan.py`

### **8:30 AM ET - Signal Review**
1. Review scan results (signals found, agent votes)
2. Verify gap calculations with Finviz/TradingView
3. Check consensus scores for each signal
4. Approve/reject signals manually (paper trading)

### **9:30 AM ET - Market Open**
1. Monitor entry executions (virtual fills)
2. Set stop-loss and target orders
3. Log trade details in journal
4. Update database with fills

### **Throughout Day**
1. Monitor positions for stop/target hits
2. Check regime changes (VIX spikes, SPY breakdown)
3. Review NewsSentry for adverse headlines

### **4:00 PM ET - Market Close**
1. Update position statuses
2. Log any exits (stop/target/time)
3. Calculate P&L for closed trades
4. Update agent performance tracking

### **Evening - Nightly Audit**
1. Run auditor: `python scripts/run_nightly_audit.py`
2. Review agent accuracy metrics
3. Check if weighted mode activated (>20 trades)
4. Update journal and reports

---

## 📈 **Success Metrics**

### **Primary Targets (30 Days)**
| Metric | Target | Minimum | Notes |
|--------|--------|---------|-------|
| **Win Rate** | 60-70% | 55% | Maintain Phase 3 quality |
| **Total Trades** | 20-30 | 20 | Need 20 for weighted mode |
| **Profit Factor** | 2.5x+ | 2.0x | Risk/reward balance |
| **Avg Return** | +5% | +3% | Per winning trade |
| **Max Drawdown** | <15% | <20% | Peak to trough |

### **Secondary Metrics**
- **Agent Accuracy**: Track per-agent correctness
- **Consensus Scores**: Average 70-90% in weighted mode
- **Regime Performance**: Win rate by regime
- **Ticker Performance**: Win rate by ticker

---

## 🚨 **Risk Management**

### **Position Limits**
- **Max Position Size**: 10% of capital ($2,500)
- **Max Concurrent**: 5 positions
- **Max Per Sector**: 2 positions
- **Daily Loss Limit**: 3% of capital ($750)

### **Stop-Loss Rules**
- **Initial Stop**: Based on gap analysis (typically -5%)
- **Never Move Stop Down**: Only trail upward
- **Time Stop**: Exit after 5 days if no resolution

### **Circuit Breakers**
- **3 Losses in Row**: Pause trading, review system
- **Drawdown >10%**: Reduce position size to 0.5%
- **Win Rate <50% After 15 Trades**: Debug agents

---

## 📊 **Monitoring Dashboard**

### **Key Performance Indicators (KPIs)**

**Trade Performance:**
```
Win Rate:           13W / 20T = 65.0% ✅
Profit Factor:      $3,250 / $1,100 = 2.95x ✅
Avg Win:            $250 (+10.0%)
Avg Loss:           -$110 (-4.4%)
Current Drawdown:   -2.5%
```

**Agent Accuracy:**
```
Forecaster:     18/20 correct = 90.0% (weight: 1.5x)
RiskOfficer:    16/20 correct = 80.0% (weight: 1.0x)
NewsSentry:     17/20 correct = 85.0% (weight: 1.0x)
```

**System Health:**
```
Mode:               Weighted (trade 21)
Consensus Avg:      73.5%
Threshold:          70.0%
Alerts Sent:        25
Errors:             0
```

---

## 🔧 **Troubleshooting**

### **Issue: No Signals Found**
**Symptoms**: Daily scan returns 0 signals for 3+ days

**Solutions**:
1. Check ticker universe (ensure valid symbols)
2. Verify market regime (may be in high-vix/stress mode)
3. Lower confidence threshold temporarily (5.5 → 5.0)
4. Check GapScanner for data errors

### **Issue: Low Win Rate (<50%)**
**Symptoms**: Losing more than winning after 15+ trades

**Solutions**:
1. Review losing trades for patterns
2. Increase confidence threshold (5.5 → 6.0)
3. Check agent veto patterns (which agent is wrong?)
4. Consider pausing trading to debug

### **Issue: Agent Disagreements**
**Symptoms**: Forecaster approves, RiskOfficer vetoes (or vice versa)

**Solutions**:
1. Review individual trade details
2. Check which agent was correct
3. Adjust agent weights manually if needed
4. Wait for auto-weighting after 20 trades

---

## 📅 **30-Day Timeline**

### **Week 1 (Days 1-7)**
- **Goal**: Execute 5-7 trades, validate infrastructure
- **Focus**: System reliability, data collection
- **Checkpoint**: 60%+ WR, no errors

### **Week 2 (Days 8-14)**
- **Goal**: Execute 8-10 more trades (15 total)
- **Focus**: Agent accuracy tracking, pattern recognition
- **Checkpoint**: Maintain 60%+ WR

### **Week 3 (Days 15-21)**
- **Goal**: Reach 20 trades, activate weighted mode
- **Focus**: Monitor consensus scores, agent weights
- **Checkpoint**: Smooth transition to weighted voting

### **Week 4 (Days 22-30)**
- **Goal**: Complete 25-30 total trades
- **Focus**: Validate weighted system performance
- **Decision Gate**: Proceed to live trading or iterate?

---

## ✅ **Week-by-Week Checklist**

### **Week 1**
- [ ] Day 1: Run first daily scan, verify all systems operational
- [ ] Day 2-3: Execute first 2-3 trades, log meticulously
- [ ] Day 4-5: Monitor open positions, update journal daily
- [ ] Day 6-7: Review first week performance, adjust if needed
- [ ] Weekend: Analyze trade data, update documentation

### **Week 2**
- [ ] Continue daily scans and trade execution
- [ ] Track agent disagreements (note which agents veto)
- [ ] Monitor regime changes (VIX spikes, SPY moves)
- [ ] Update agent performance tracking
- [ ] Weekend: 2-week performance review

### **Week 3**
- [ ] Target trade 20 by end of week
- [ ] System auto-switches to weighted mode at trade 20
- [ ] Monitor consensus scores (should be 70-90%)
- [ ] Validate weighted voting works correctly
- [ ] Weekend: Analyze weighted system impact

### **Week 4**
- [ ] Complete final 5-10 trades
- [ ] Collect comprehensive performance metrics
- [ ] Review agent weights (expect divergence)
- [ ] Generate 30-day report
- [ ] **Decision**: Proceed to live trading or extend testing?

---

## 📊 **Decision Gate: After 30 Days**

### **Criteria for Live Trading Approval**

✅ **PROCEED TO LIVE** if ALL met:
- Win Rate ≥ 60%
- Profit Factor ≥ 2.5x
- Total Trades ≥ 20
- Max Drawdown < 15%
- No system errors
- Agent weighting operational

⚠️ **EXTEND PAPER TRADING** if:
- Win Rate 50-60% (promising but needs more data)
- Profit Factor 2.0-2.5x
- Total Trades < 20 (insufficient data)

❌ **STOP & DEBUG** if:
- Win Rate < 50%
- Profit Factor < 2.0x
- System errors/crashes
- Agent weighting not working

---

## 🚀 **Quick Start Commands**

```powershell
# Activate virtual environment
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
.\.venv-1\Scripts\Activate.ps1

# Run daily scan (manual test)
python scripts/run_daily_scan.py

# Run nightly audit
python scripts/run_nightly_audit.py

# Check agent performance
python scripts/check_agent_stats.py

# Generate weekly report
python scripts/generate_weekly_report.py

# View trade journal
start reports/paper_trading_journal.xlsx
```

---

## 📞 **Support & Resources**

**Documentation:**
- `PHASE_3_PRODUCTION_COMPLETE.md` - System overview
- `AGENT_WEIGHTING_SYSTEM.md` - Agent learning mechanics
- `AGENTIC_TRAINING_ROADMAP.md` - Future enhancements

**Databases:**
- `reports/pennyhunter_agentic.db` - Trade history and agent votes
- `reports/pennyhunter_memory.db` - Ticker ejection tracking
- `reports/pennyhunter_agentic_backtest.db` - Backtest results

**Logs:**
- `logs/daily_scan.log` - Pre-market scan results
- `logs/trading.log` - Trade execution log
- `logs/errors.log` - System errors

---

## 🎯 **Day 1 Action Plan**

### **Today (October 18, 2025):**

1. ✅ **Review Deployment Guide** (you are here!)

2. **Set Up Paper Trading Account** (30 minutes)
   - [ ] Sign up for Alpaca paper trading
   - [ ] Generate API keys
   - [ ] Store in environment variables

3. **Create Monitoring Infrastructure** (30 minutes)
   - [ ] Create `logs/` directory
   - [ ] Set up trade journal spreadsheet
   - [ ] Configure alert notifications

4. **Test Daily Scan** (15 minutes)
   - [ ] Run `python scripts/run_daily_scan.py` manually
   - [ ] Verify signals generated
   - [ ] Check agent votes logged

5. **Schedule Automation** (15 minutes)
   - [ ] Set up Windows Task Scheduler
   - [ ] Test scheduled run (tomorrow morning)

6. **First Trade** (Today - if signal found!)
   - [ ] Review today's scan results
   - [ ] Execute first paper trade
   - [ ] Log in journal

---

**Ready to begin? Let's start with setting up the paper trading account!** 🚀

Would you like me to:
1. Create the daily scan script?
2. Set up the Alpaca broker integration?
3. Create the trade journal template?
4. All of the above?
