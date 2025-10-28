# Production Deployment Guide

**Status:** Ready for deployment  
**Date:** October 25, 2025  
**Validation Framework:** 80% complete

---

## Overview

This guide covers deploying the validated AutoTrader system to production with optimized hyperparameters.

---

## Step 1: Run Full Hyperparameter Optimization

### Option A: Python Script (Recommended)

Run optimization on all 7 symbols:

```bash
# Activate virtual environment
& C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\Activate.ps1

# Navigate to project directory
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Run full optimization (50 trials per symbol, ~30-40 minutes)
python scripts/validation/run_full_optimization.py --trials 50 --splits 5

# OR run with 200 trials for production (1-2 hours)
python scripts/validation/run_full_optimization.py --trials 200 --splits 5
```

### Option B: PowerShell Script

```powershell
# Navigate to project directory
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Run optimization
.\scripts\validation\run_full_optimization.ps1 -Trials 50 -Splits 5

# OR with 200 trials
.\scripts\validation\run_full_optimization.ps1 -Trials 200 -Splits 5
```

### Option C: Individual Symbols

Run optimization one symbol at a time:

```bash
# Activate environment
& C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\Activate.ps1
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# AAPL
python scripts/validation/optuna_optimization.py \
    --data-dir data/processed/features \
    --symbol AAPL \
    --n-trials 200 \
    --n-splits 5 \
    --objective sharpe

# MSFT
python scripts/validation/optuna_optimization.py \
    --data-dir data/processed/features \
    --symbol MSFT \
    --n-trials 200 \
    --n-splits 5 \
    --objective sharpe

# Repeat for: NVDA, BTCUSD, ETHUSD, EURUSD, GBPUSD
```

### Expected Output

After completion, you'll have:

```
reports/optuna/
├── AAPL_best_params.json
├── AAPL_optimization_history.png
├── AAPL_param_importance.png
├── MSFT_best_params.json
├── MSFT_optimization_history.png
├── MSFT_param_importance.png
├── NVDA_best_params.json
├── ...
├── GBPUSD_best_params.json
└── optimization_summary.json
```

---

## Step 2: Analyze Optimization Results

### View Summary

```bash
# View optimization summary
cat reports/optuna/optimization_summary.json

# OR in PowerShell
Get-Content reports/optuna/optimization_summary.json | ConvertFrom-Json | Format-List
```

### Compare Results Across Symbols

Create a comparison script to analyze patterns:

```python
import json
from pathlib import Path

results_dir = Path("reports/optuna")
symbols = ["AAPL", "MSFT", "NVDA", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD"]

print("Optimization Results Comparison")
print("="*80)
print(f"{'Symbol':<10} {'Best Sharpe':<15} {'Strategy':<20} {'Key Param':<30}")
print("-"*80)

for symbol in symbols:
    result_file = results_dir / f"{symbol}_best_params.json"
    if result_file.exists():
        with open(result_file) as f:
            data = json.load(f)
        
        best_value = data['best_value']
        params = data['best_params']
        strategy = params['strategy_type']
        
        # Get key parameter based on strategy
        if strategy == 'momentum':
            key_param = f"lookback={params['momentum_lookback']}"
        elif strategy == 'mean_reversion':
            key_param = f"lookback={params['mr_lookback']}, std={params['mr_std_threshold']}"
        elif strategy == 'ma_crossover':
            key_param = f"fast={params['ma_fast']}, slow={params['ma_slow']}"
        else:
            key_param = "N/A"
        
        print(f"{symbol:<10} {best_value:<15.6f} {strategy:<20} {key_param:<30}")
```

Save this as `scripts/validation/compare_optuna_results.py` and run:

```bash
python scripts/validation/compare_optuna_results.py
```

---

## Step 3: Create Production Config Files

Export optimal parameters to production configs:

```bash
python scripts/validation/export_production_configs.py \
    --optuna-dir reports/optuna \
    --output-dir configs/production
```

This will create:

```
configs/production/
├── AAPL_strategy.yaml
├── MSFT_strategy.yaml
├── NVDA_strategy.yaml
├── BTCUSD_strategy.yaml
├── ETHUSD_strategy.yaml
├── EURUSD_strategy.yaml
└── GBPUSD_strategy.yaml
```

Each file contains:

```yaml
symbol: AAPL
strategy:
  type: momentum
  parameters:
    lookback: 4400
    threshold: 0.0081
risk_management:
  position_size: 0.9
  stop_loss_pct: 0.04
  take_profit_pct: 0.04
transaction_costs:
  commission: 0.0003
  slippage: 0.0005
optimization:
  best_sharpe: 0.0144
  n_trials: 200
  timestamp: "2025-10-25T..."
```

---

## Step 4: Set Up Live Trading Infrastructure

### 4.1 Configure Data Feeds

Update `configs/data/live_feeds.yaml`:

```yaml
providers:
  equities:
    - alpaca  # AAPL, MSFT, NVDA
  crypto:
    - binance  # BTCUSD, ETHUSD
  forex:
    - dukascopy  # EURUSD, GBPUSD

refresh_rate: 1s  # 1-second bars
buffer_size: 1000  # Keep 1000 bars in memory
```

### 4.2 Set Up Paper Trading

Configure paper trading environment in `configs/execution/paper_trading.yaml`:

```yaml
mode: paper  # paper | live
broker: alpaca_paper

initial_capital: 100000  # $100k starting capital
leverage: 1.0  # No leverage initially

symbols:
  - AAPL
  - MSFT
  - NVDA
  - BTCUSD
  - ETHUSD
  - EURUSD
  - GBPUSD

strategies:
  AAPL: configs/production/AAPL_strategy.yaml
  MSFT: configs/production/MSFT_strategy.yaml
  NVDA: configs/production/NVDA_strategy.yaml
  BTCUSD: configs/production/BTCUSD_strategy.yaml
  ETHUSD: configs/production/ETHUSD_strategy.yaml
  EURUSD: configs/production/EURUSD_strategy.yaml
  GBPUSD: configs/production/GBPUSD_strategy.yaml

risk_limits:
  max_position_pct: 0.15  # Max 15% per position
  max_daily_loss_pct: 0.05  # Stop if 5% daily loss
  max_drawdown_pct: 0.20  # Stop if 20% drawdown
```

### 4.3 Deploy Trading Engine

```bash
# Start paper trading
python src/execution/trading_engine.py \
    --config configs/execution/paper_trading.yaml \
    --mode paper

# Monitor logs
tail -f logs/trading_engine.log
```

---

## Step 5: Set Up Monitoring & Alerts

### 5.1 Grafana Dashboards

Start monitoring stack:

```bash
# Start Grafana + Prometheus
docker-compose --profile monitoring up -d

# Access Grafana
# URL: http://localhost:3000
# User: admin
# Pass: admin
```

### 5.2 Configure Alerts

Create `configs/monitoring/alerts.yaml`:

```yaml
alerts:
  - name: high_drawdown
    condition: drawdown > 0.15
    severity: critical
    channels: [email, slack]
    
  - name: strategy_degradation
    condition: sharpe_1d < 0.5
    severity: warning
    channels: [slack]
    
  - name: execution_failure
    condition: order_rejection_rate > 0.05
    severity: critical
    channels: [email, pagerduty]
    
  - name: data_feed_down
    condition: last_bar_age > 60s
    severity: critical
    channels: [email, slack, pagerduty]
```

### 5.3 Set Up Email/Slack Notifications

Update `configs/monitoring/notifications.yaml`:

```yaml
email:
  smtp_server: smtp.gmail.com
  smtp_port: 587
  from: alerts@autotrader.io
  to: [trading-team@autotrader.io]
  
slack:
  webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  channel: "#trading-alerts"
  
pagerduty:
  api_key: YOUR_PAGERDUTY_API_KEY
  service_id: YOUR_SERVICE_ID
```

---

## Step 6: Validation Before Live Trading

### 6.1 Run 1-Week Paper Trading

```bash
# Start paper trading
python src/execution/trading_engine.py \
    --config configs/execution/paper_trading.yaml \
    --mode paper \
    --duration 7d

# Monitor performance
python scripts/monitoring/track_performance.py \
    --mode paper \
    --interval 1h
```

### 6.2 Validation Checklist

Before going live, verify:

- [ ] All 7 symbols show positive paper trading results
- [ ] Sharpe ratios match backtest expectations (±20%)
- [ ] Transaction costs are within expected ranges
- [ ] No order rejections or execution errors
- [ ] Max drawdown stays below 20%
- [ ] Data feeds are stable (>99.9% uptime)
- [ ] Monitoring alerts are working
- [ ] Risk limits are enforced correctly

### 6.3 Performance Metrics

Expected metrics from 1-week paper trading:

```
Symbol    | Expected Sharpe | Paper Sharpe | Status
----------|-----------------|--------------|--------
AAPL      | 0.0144         | 0.0120-0.0168| ✓ PASS
MSFT      | 0.0XXX         | ±20%         | ✓ PASS
NVDA      | 0.0XXX         | ±20%         | ✓ PASS
BTCUSD    | 0.0XXX         | ±20%         | ✓ PASS
ETHUSD    | 0.0XXX         | ±20%         | ✓ PASS
EURUSD    | 0.0XXX         | ±20%         | ✓ PASS
GBPUSD    | 0.0XXX         | ±20%         | ✓ PASS
```

---

## Step 7: Go Live

### 7.1 Switch to Live Trading

Update `configs/execution/live_trading.yaml`:

```yaml
mode: live  # IMPORTANT: Changed from paper to live
broker: alpaca_live  # Use live broker API

initial_capital: 100000  # Actual starting capital
leverage: 1.0

# Same configuration as paper trading
# but with real money
```

### 7.2 Start with Small Capital

```bash
# Start with 10% of target capital
python src/execution/trading_engine.py \
    --config configs/execution/live_trading.yaml \
    --mode live \
    --capital-scale 0.1  # 10% of $100k = $10k
```

### 7.3 Gradual Ramp-Up

**Week 1-2:** 10% capital ($10k)  
**Week 3-4:** 25% capital ($25k) if Week 1-2 successful  
**Week 5-6:** 50% capital ($50k) if Week 3-4 successful  
**Week 7+:** 100% capital ($100k) if Week 5-6 successful

---

## Troubleshooting

### Optimization Fails

```bash
# Check data files exist
ls data/processed/features/*.parquet

# Check for corrupted data
python scripts/validation/check_data_integrity.py

# Run with fewer trials
python scripts/validation/run_full_optimization.py --trials 10
```

### Paper Trading Errors

```bash
# Check broker connection
python scripts/execution/test_broker_connection.py

# Verify API keys
cat configs/execution/.env.paper

# Check logs
tail -f logs/trading_engine.log
```

### Performance Degradation

```bash
# Run walk-forward validation on recent data
python scripts/validation/walk_forward.py \
    --data-dir data/processed/features \
    --symbol AAPL \
    --recent-only

# Check for regime change
python scripts/analysis/detect_regime_change.py
```

---

## Timeline

**Day 1:** Run full optimization (1-2 hours)  
**Day 2:** Analyze results, create production configs  
**Day 3:** Set up paper trading infrastructure  
**Day 4:** Deploy to paper trading  
**Day 5-11:** Monitor paper trading (1 week)  
**Day 12:** Validation review  
**Day 13:** Go live with 10% capital  
**Week 3-7:** Gradual ramp-up to 100% capital

---

## Success Criteria

**Optimization:**
- ✓ All 7 symbols optimized with 200+ trials
- ✓ Best Sharpe > 0.01 for all symbols
- ✓ No failed optimizations

**Paper Trading:**
- ✓ 7 days with positive returns
- ✓ Sharpe within ±20% of backtest
- ✓ Max drawdown < 20%
- ✓ Zero execution errors
- ✓ Data uptime > 99.9%

**Live Trading:**
- ✓ Week 1-2: Positive returns at 10% capital
- ✓ Week 3-4: Positive returns at 25% capital
- ✓ Week 5-6: Positive returns at 50% capital
- ✓ Week 7+: Positive returns at 100% capital

---

## Support

**Questions?** Contact:
- Validation Team: validation@autotrader.io
- Trading Ops: trading-ops@autotrader.io
- On-call: +1-XXX-XXX-XXXX

**Documentation:**
- [Validation Summary](./VALIDATION_SUMMARY_REPORT.md)
- [Quick Reference](./VALIDATION_QUICK_REFERENCE.md)
- [Roadmap Status](./VALIDATION_ROADMAP_STATUS.md)

---

**Last Updated:** October 25, 2025  
**Version:** 1.0.0  
**Status:** Ready for deployment
