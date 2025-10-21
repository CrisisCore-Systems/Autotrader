# Intelligent Adjustments Deployment Guide

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Paper Trading Setup](#paper-trading-setup)
3. [Live Trading Migration](#live-trading-migration)
4. [Monitoring & Alerts](#monitoring--alerts)
5. [Performance Validation](#performance-validation)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

### 1. Test Coverage Validation
- [ ] **200 unit tests passing** (all phases)
- [ ] **55 configuration tests** passing
- [ ] **16 regime detector tests** passing
- [ ] **18 VIX provider tests** passing
- [ ] **No failing tests** in `tests/unit/`

```bash
# Run full test suite
pytest tests/unit/ --ignore=tests/unit/exits/test_monitor_integration.py -v

# Expected: 200 passed
```

### 2. Configuration Validation
- [ ] All 3 config templates validate successfully
- [ ] Environment variables set correctly
- [ ] API credentials configured
- [ ] Safety bounds appropriate for account size

```bash
# Validate production config
python -c "
from src.bouncehunter.exits.config import ExitConfigManager
config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')
print('✓ Production config valid')
"

# Validate paper config
python -c "
from src.bouncehunter.exits.config import ExitConfigManager
config = ExitConfigManager.from_yaml('configs/paper_trading_adjustments.yaml')
print('✓ Paper trading config valid')
"

# Validate live config
python -c "
from src.bouncehunter.exits.config import ExitConfigManager
config = ExitConfigManager.from_yaml('configs/live_trading_adjustments.yaml')
print('✓ Live trading config valid')
"
```

### 3. API Connectivity
- [ ] Alpaca API keys valid (paper + live)
- [ ] VIX data accessible
- [ ] SPY data accessible
- [ ] Broker connection working

```bash
# Test Alpaca connectivity
python scripts/test_alpaca_connection.py

# Test VIX data fetch
python -c "
from alpaca.data.historical import StockHistoricalDataClient
from src.bouncehunter.data.vix_provider import AlpacaVIXProvider
import os

client = StockHistoricalDataClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    api_secret=os.getenv('ALPACA_API_SECRET')
)

vix_provider = AlpacaVIXProvider(client)
vix = vix_provider.get_current_vix()

if vix:
    print(f'✓ VIX data available: {vix:.2f}')
else:
    print('✗ VIX data unavailable')
"
```

### 4. Directory Structure
- [ ] `configs/` directory exists
- [ ] `logs/` directory exists
- [ ] `reports/` directory exists
- [ ] Appropriate permissions set

```bash
# Create required directories
mkdir -p configs logs reports reports/adjustment_performance backups

# Set permissions
chmod 755 logs reports backups
```

### 5. Dependencies
- [ ] All Python packages installed
- [ ] Correct Python version (3.8+)
- [ ] No dependency conflicts

```bash
# Install dependencies
pip install -r requirements.txt

# Verify key packages
python -c "
import yaml
import alpaca
from src.bouncehunter.exits.adjustments import AdjustmentCalculator
print('✓ All dependencies available')
"
```

---

## Paper Trading Setup

### Phase 1: Configuration

**1. Copy Paper Trading Template:**
```bash
cp configs/paper_trading_adjustments.yaml configs/my_paper_config.yaml
```

**2. Set Environment Variables:**
```bash
# Add to .env or shell profile
export ALPACA_API_KEY="your_paper_api_key"
export ALPACA_API_SECRET="your_paper_api_secret"
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"
```

**3. Customize Settings (Optional):**
```yaml
# configs/my_paper_config.yaml

# Enable all adjustments for testing
adjustments:
  enabled: true
  
  # Test with moderate adjustments
  volatility:
    tier1_adjustment_low: 0.3
    tier1_adjustment_high: -0.8
  
  # Faster learning for testing
  symbol_learning:
    min_exits_for_adjustment: 3
    
# Frequent monitoring
monitoring:
  poll_interval_seconds: 60  # 1 minute
  
# Verbose logging
logging:
  level: DEBUG
```

### Phase 2: Initial Test Run

**1. Create Test Script:**
```python
# scripts/test_paper_trading.py
import logging
from src.bouncehunter.exits.config import ExitConfigManager
from src.bouncehunter.exits.monitor import PositionMonitor
from src.bouncehunter.broker import YourBrokerClient

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/paper_test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    # Load config
    config = ExitConfigManager.from_yaml('configs/my_paper_config.yaml')
    logger.info("Config loaded successfully")
    
    # Create broker client
    broker = YourBrokerClient(paper=True)
    logger.info("Broker client created")
    
    # Create monitor with adjustments
    monitor = PositionMonitor(
        broker=broker,
        config=config,
        enable_adjustments=True,
    )
    logger.info("Position monitor created with adjustments ENABLED")
    
    # Run one monitoring cycle
    logger.info("Starting monitoring cycle...")
    monitor.monitor_positions()
    logger.info("Monitoring cycle complete")

if __name__ == "__main__":
    main()
```

**2. Run Test:**
```bash
python scripts/test_paper_trading.py

# Check logs
tail -f logs/paper_test.log
tail -f logs/paper_adjustments.log
```

**3. Verify Outputs:**
- [ ] No errors in logs
- [ ] VIX data fetched successfully
- [ ] Regime detected correctly
- [ ] Adjustments calculated (check logs)
- [ ] No crashes or exceptions

### Phase 3: Extended Paper Trading (2-4 Weeks)

**1. Deploy Paper Trading Bot:**
```bash
# Run in background with nohup
nohup python scripts/run_paper_trading.py > logs/paper_output.log 2>&1 &

# Or use systemd (recommended for production)
sudo systemctl start paper-trading-bot
```

**2. Monitor Daily:**
```bash
# Check logs daily
tail -100 logs/paper_tier_exits.log
tail -100 logs/paper_adjustments.log

# Review adjustment decisions
grep "ADJUSTMENT" logs/paper_adjustments.log | tail -20

# Check for errors
grep "ERROR\|CRITICAL" logs/paper_*.log
```

**3. Weekly Review:**
```bash
# Generate weekly report
python scripts/generate_weekly_report.py --config configs/my_paper_config.yaml

# Review reports
cat reports/paper_adjustment_performance/weekly_*.json
```

### Phase 4: Performance Validation

**Metrics to Track:**

1. **Win Rate Comparison:**
```python
# Calculate baseline vs. adjusted win rates
baseline_win_rate = exits_hit_target_baseline / total_exits_baseline
adjusted_win_rate = exits_hit_target_adjusted / total_exits_adjusted

improvement = (adjusted_win_rate - baseline_win_rate) / baseline_win_rate
print(f"Win rate improvement: {improvement:.1%}")
```

2. **Average Exit Quality:**
```python
# Compare actual exit vs. base target
avg_improvement = mean(exit_price - base_target_price) / base_target_price
print(f"Average exit improvement: {avg_improvement:.2%}")
```

3. **Regime Performance:**
```python
# Break down by regime
bull_win_rate = wins_in_bull / exits_in_bull
bear_win_rate = wins_in_bear / exits_in_bear
sideways_win_rate = wins_in_sideways / exits_in_sideways
```

**Acceptance Criteria:**
- [ ] **Win rate improvement >= 5%** (adjusted vs. baseline)
- [ ] **No increase in losses > 10%** (risk control maintained)
- [ ] **Symbol learning shows positive trend** (improving over time)
- [ ] **No system errors** for 7+ consecutive days
- [ ] **VIX data availability > 95%**
- [ ] **Regime detection success > 99%**

**If criteria met:** Proceed to live trading  
**If criteria not met:** Review configuration, extend paper trading

---

## Live Trading Migration

### Phase 1: Pre-Migration Prep

**1. Review Paper Trading Results:**
```bash
# Generate comprehensive report
python scripts/generate_migration_report.py \
    --paper-db reports/pennyhunter_agentic.db \
    --start-date 2025-09-01 \
    --end-date 2025-10-01

# Review report
cat reports/migration_readiness_report.txt
```

**2. Backup Current State:**
```bash
# Backup paper trading data
cp -r reports reports_backup_$(date +%Y%m%d)

# Backup configuration
cp configs/my_paper_config.yaml backups/

# Backup symbol learning
cp reports/paper_symbol_adjustments.json backups/
```

**3. Switch to Live Configuration:**
```bash
# Copy live template
cp configs/live_trading_adjustments.yaml configs/my_live_config.yaml

# Set live environment variables
export ALPACA_API_KEY_LIVE="your_live_api_key"
export ALPACA_API_SECRET_LIVE="your_live_api_secret"
export ALPACA_BASE_URL="https://api.alpaca.markets"  # LIVE URL
```

**4. Conservative Live Settings:**
```yaml
# configs/my_live_config.yaml

adjustments:
  enabled: true
  
  # More conservative for live
  volatility:
    tier1_adjustment_low: 0.2      # Gentler adjustments
    tier1_adjustment_high: -0.5
    tier1_adjustment_extreme: -1.0
  
  time_decay:
    tier1_max_decay_pct: -0.8      # Moderate decay
  
  regime:
    tier1_adjustment_bull: -0.2    # Subtle adjustments
    tier1_adjustment_bear: 0.5
  
  symbol_learning:
    min_exits_for_adjustment: 10   # More data required
  
  combination:
    tier1_min_target_pct: 3.0      # Tighter bounds
    tier1_max_target_pct: 6.5

safety:
  max_exits_per_cycle: 2           # Very conservative
  require_volume_confirmation: true
  validate_adjustments: true
  alert_on_extreme_adjustments: true

monitoring:
  poll_interval_seconds: 300       # Standard 5 min
```

### Phase 2: Gradual Rollout

**Week 1: 25% Rollout**
```yaml
# Enable adjustments for 25% of positions
adjustments:
  enabled: true

# In code: randomly select 25% of positions
import random
positions_with_adjustments = random.sample(all_positions, len(all_positions) // 4)
```

**Week 2: 50% Rollout**
```python
# Increase to 50% if Week 1 successful
positions_with_adjustments = random.sample(all_positions, len(all_positions) // 2)
```

**Week 3: 75% Rollout**
```python
# Increase to 75% if Week 2 successful
positions_with_adjustments = random.sample(all_positions, 3 * len(all_positions) // 4)
```

**Week 4: 100% Rollout**
```yaml
# Full rollout if all previous weeks successful
adjustments:
  enabled: true  # All positions use adjustments
```

### Phase 3: Live Deployment

**1. Pre-Flight Checks:**
```bash
# Run pre-flight checklist
python scripts/pre_flight_check.py --config configs/my_live_config.yaml

# Expected output:
# ✓ Configuration valid
# ✓ API connectivity OK
# ✓ VIX data available
# ✓ SPY data available
# ✓ Directories writable
# ✓ All systems GO
```

**2. Deploy Live Bot:**
```bash
# Use systemd for reliability
sudo systemctl start live-trading-bot

# Verify running
sudo systemctl status live-trading-bot

# Check initial logs
tail -f /var/log/live_trading.log
```

**3. Monitor First Hour Intensively:**
```bash
# Watch logs in real-time
tail -f logs/live_tier_exits.log &
tail -f logs/live_adjustments.log &
tail -f logs/live_errors.log &

# Check for any issues
watch -n 10 'grep "ERROR\|WARNING" logs/live_*.log | tail -20'
```

### Phase 4: Ongoing Monitoring

**Daily Tasks:**
- [ ] Review exit logs
- [ ] Check adjustment calculations
- [ ] Verify no errors
- [ ] Monitor win rates
- [ ] Review extreme adjustments

**Weekly Tasks:**
- [ ] Generate weekly report
- [ ] Compare to baseline
- [ ] Review symbol learning
- [ ] Tune if needed
- [ ] Update stakeholders

**Monthly Tasks:**
- [ ] Comprehensive performance review
- [ ] Configuration optimization
- [ ] Cost/benefit analysis
- [ ] Document learnings

---

## Monitoring & Alerts

### Key Metrics Dashboard

**1. Create Monitoring Script:**
```python
# scripts/monitor_adjustments.py
import json
from datetime import datetime, timedelta
from src.bouncehunter.exits.adjustments import SymbolLearner

def generate_metrics():
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'adjustments': {},
        'performance': {},
        'health': {}
    }
    
    # Load symbol learning
    learner = SymbolLearner()
    try:
        learner.load_state("reports/live_symbol_adjustments.json")
        
        all_symbols = learner.get_all_symbols()
        metrics['adjustments']['total_symbols'] = len(all_symbols)
        
        # Calculate aggregate win rate
        total_exits = sum(learner.get_symbol_stats(s)['total_exits'] for s in all_symbols)
        total_hits = sum(learner.get_symbol_stats(s)['successful_exits'] for s in all_symbols)
        metrics['performance']['win_rate'] = total_hits / total_exits if total_exits > 0 else 0
        
    except FileNotFoundError:
        metrics['adjustments']['error'] = "No learning data found"
    
    # Check recent logs for health
    with open('logs/live_adjustments.log', 'r') as f:
        recent_logs = f.readlines()[-100:]
        errors = [line for line in recent_logs if 'ERROR' in line]
        metrics['health']['recent_errors'] = len(errors)
        metrics['health']['status'] = 'healthy' if len(errors) == 0 else 'degraded'
    
    return metrics

if __name__ == "__main__":
    metrics = generate_metrics()
    print(json.dumps(metrics, indent=2))
```

**2. Set Up Cron Job:**
```bash
# Add to crontab
crontab -e

# Run every hour
0 * * * * /path/to/python /path/to/scripts/monitor_adjustments.py >> /path/to/logs/metrics.log 2>&1
```

### Alert Configuration

**1. Telegram Alerts:**
```python
# scripts/send_telegram_alert.py
import requests
import os

def send_alert(message: str, priority: str = "INFO"):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🚨"}[priority]
    
    payload = {
        "chat_id": chat_id,
        "text": f"{emoji} *{priority}*\n{message}",
        "parse_mode": "Markdown"
    }
    
    requests.post(url, json=payload)

# Usage
send_alert("VIX reached EXTREME level: 35.2", priority="WARNING")
send_alert("System error detected in adjustment calculation", priority="ERROR")
```

**2. Alert Triggers:**
```python
# In monitoring code
from scripts.send_telegram_alert import send_alert

# VIX alerts
if vix > 30:
    send_alert(f"VIX EXTREME: {vix:.2f}", priority="WARNING")

# Regime change alerts
if regime != previous_regime:
    send_alert(f"Regime changed: {previous_regime.value} → {regime.value}", priority="INFO")

# Extreme adjustment alerts
if abs(total_adjustment) > 3.0:
    send_alert(f"Extreme adjustment: {symbol} {total_adjustment:+.2f}%", priority="WARNING")

# Error alerts
if error_count > 5:
    send_alert(f"Multiple errors detected: {error_count} in last hour", priority="ERROR")
```

### Log Rotation

**1. Configure logrotate:**
```bash
# /etc/logrotate.d/trading-bot
/path/to/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 trading trading
    postrotate
        systemctl reload live-trading-bot
    endscript
}
```

**2. Manual rotation:**
```bash
# Rotate logs manually
python scripts/rotate_logs.py --days 30
```

---

## Performance Validation

### Baseline Comparison

**1. Record Baseline Metrics (Before Adjustments):**
```python
# scripts/record_baseline.py
baseline_metrics = {
    'period': '2025-09-01 to 2025-10-01',
    'total_exits': 150,
    'successful_exits': 90,
    'win_rate': 0.60,
    'avg_exit_pct': 5.2,
    'avg_hold_time_hours': 12.5,
}

with open('reports/baseline_metrics.json', 'w') as f:
    json.dump(baseline_metrics, f, indent=2)
```

**2. Compare with Adjustment Metrics:**
```python
# scripts/compare_performance.py
import json

# Load baseline
with open('reports/baseline_metrics.json') as f:
    baseline = json.load(f)

# Load adjusted
with open('reports/adjusted_metrics.json') as f:
    adjusted = json.load(f)

# Compare
improvements = {
    'win_rate_improvement': (adjusted['win_rate'] - baseline['win_rate']) / baseline['win_rate'],
    'exit_improvement': (adjusted['avg_exit_pct'] - baseline['avg_exit_pct']) / baseline['avg_exit_pct'],
    'hold_time_change': (adjusted['avg_hold_time_hours'] - baseline['avg_hold_time_hours']) / baseline['avg_hold_time_hours'],
}

print("Performance Improvements:")
for metric, value in improvements.items():
    print(f"  {metric}: {value:+.1%}")
```

### A/B Testing (Advanced)

**Run parallel systems:**
- System A: No adjustments (baseline)
- System B: With adjustments

**Compare results after 30 days:**
```python
# Statistical significance test
from scipy import stats

baseline_exits = [...]  # Exit percentages without adjustments
adjusted_exits = [...]  # Exit percentages with adjustments

t_stat, p_value = stats.ttest_ind(baseline_exits, adjusted_exits)

if p_value < 0.05:
    print("✓ Improvement is statistically significant")
else:
    print("✗ Improvement not statistically significant")
```

---

## Rollback Procedures

### Scenario 1: Minor Issues (Tuning Needed)

**Symptoms:**
- Adjustments seem too aggressive/conservative
- Win rate slightly lower than expected
- No system errors

**Solution: Tune Configuration**
```yaml
# Reduce adjustment magnitudes
adjustments:
  volatility:
    tier1_adjustment_high: -0.3  # Reduce from -0.5
  
  regime:
    tier1_adjustment_bull: -0.1  # Reduce from -0.2
```

**Steps:**
1. Update config file
2. Restart bot: `sudo systemctl restart live-trading-bot`
3. Monitor for 24-48 hours
4. Re-evaluate

### Scenario 2: Moderate Issues (Temporary Disable)

**Symptoms:**
- Unexpected behavior in exits
- VIX data unreliable
- Win rate declining

**Solution: Disable Specific Adjustments**
```yaml
# Disable problematic component
adjustments:
  enabled: true
  volatility:
    enabled: false  # Disable VIX adjustments temporarily
  time_decay:
    enabled: true   # Keep working components
  regime:
    enabled: true
```

**Steps:**
1. Identify problematic component
2. Disable in config
3. Restart bot
4. Investigate root cause
5. Re-enable when fixed

### Scenario 3: Major Issues (Full Rollback)

**Symptoms:**
- System errors
- Crashes
- Significant loss increase
- Data provider failures

**Solution: Emergency Disable**

**Option A: Quick Disable (Hot Fix)**
```yaml
# Disable all adjustments immediately
adjustments:
  enabled: false  # Master switch OFF
```

```bash
# Restart bot
sudo systemctl restart live-trading-bot

# Verify adjustments disabled
grep "Intelligent adjustments DISABLED" logs/live_trading.log
```

**Option B: Full Rollback to Baseline**
```bash
# Stop live bot
sudo systemctl stop live-trading-bot

# Restore baseline config
cp backups/baseline_config.yaml configs/current_config.yaml

# Restart with baseline
sudo systemctl start live-trading-bot

# Verify no adjustments
tail -f logs/live_trading.log | grep "adjustment"
```

**Post-Rollback:**
1. Notify stakeholders
2. Document issue
3. Investigate root cause
4. Fix in paper trading
5. Re-validate before re-deployment

### Emergency Contact Protocol

**If critical issue:**
1. **Immediate:** Disable adjustments (master switch)
2. **Within 1 hour:** Investigate and document
3. **Within 4 hours:** Implement fix or rollback
4. **Within 24 hours:** Post-mortem report
5. **Within 1 week:** Corrective action plan

---

## Troubleshooting

### Issue: VIX Data Unavailable

**Check:**
```bash
# Test VIX provider
python -c "
from src.bouncehunter.data.vix_provider import AlpacaVIXProvider
from alpaca.data.historical import StockHistoricalDataClient
import os

client = StockHistoricalDataClient(
    api_key=os.getenv('ALPACA_API_KEY_LIVE'),
    api_secret=os.getenv('ALPACA_API_SECRET_LIVE')
)

provider = AlpacaVIXProvider(client)
vix = provider.get_current_vix()
print(f'VIX: {vix}')
"
```

**Solutions:**
1. Check API credentials
2. Verify market hours
3. Check Alpaca status
4. Switch to fallback provider

### Issue: Regime Detection Failing

**Check:**
```bash
# Test regime detector
python -c "
from src.bouncehunter.data.regime_detector import SPYRegimeDetector
# ... test code
"
```

**Solutions:**
1. Reduce SMA windows temporarily
2. Check SPY data availability
3. Use mock detector temporarily

### Issue: Symbol Learning Not Persisting

**Check:**
```bash
# Verify file permissions
ls -la reports/live_symbol_adjustments.json

# Verify writes
python -c "
from src.bouncehunter.exits.adjustments import SymbolLearner
learner = SymbolLearner()
learner.record_exit('TEST', True, 100.0, 95.0)
learner.save_state('reports/test.json')
print('✓ Write successful')
"
```

**Solutions:**
1. Fix file permissions
2. Check disk space
3. Verify directory exists

---

## Production Checklist

**Before Going Live:**
- [ ] 200 unit tests passing
- [ ] Paper trading validated (2-4 weeks)
- [ ] Win rate improvement >= 5%
- [ ] Configuration validated
- [ ] API credentials set
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] Rollback plan documented
- [ ] Stakeholders notified
- [ ] Backup created

**Go-Live Day:**
- [ ] Pre-flight checks passed
- [ ] Start with 25% rollout
- [ ] Monitor first hour intensively
- [ ] No errors in first 24 hours
- [ ] Performance within expectations

**Post-Deployment:**
- [ ] Daily monitoring (Week 1)
- [ ] Weekly reports
- [ ] Gradual rollout to 100%
- [ ] Document lessons learned
- [ ] Update runbooks

---

**Version:** 1.0.0  
**Last Updated:** October 2025  
**Status:** Production Ready ✅
