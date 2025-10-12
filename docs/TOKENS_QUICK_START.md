# Token Analysis Quick Start Guide

## 🎯 Overview

This guide provides immediate commands to start analyzing the recommended tokens with the VoidBloom / CrisisCore Hidden-Gem Scanner using the FREE data tier ($0/month).

## 📋 Prerequisites

```bash
# Ensure you're in the project directory
cd c:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Activate virtual environment
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Verify installation
python -m pytest tests/test_smoke.py -v
```

## 🚀 Quick Start Commands

### 1. Single Token Analysis - Ethena (DeFi)

```bash
# Scan Ethena with FREE data sources
python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml --tree

# Expected output:
# - GemScore: 72-78
# - Confidence: 0.82+
# - Safety: PASS
# - Primary signals: S, O, L
```

### 2. Institutional Token - Ondo Finance (RWA)

```bash
# Scan institutional RWA token
python -m src.cli.run_scanner configs/tokens/ondo_finance.yaml --tree

# Expected output:
# - GemScore: 75-82 (highest in test set)
# - Confidence: 0.85+
# - Safety: PASS with high C score
# - Primary signals: S, A, C
```

### 3. Meme Token - Pepe (High Volatility)

```bash
# Scan meme token with strict safety checks
python -m src.cli.run_scanner configs/tokens/pepe_meme.yaml --tree

# Expected output:
# - GemScore: 58-68
# - Confidence: 0.68+
# - Safety: PASS (if contract checks pass)
# - Primary signals: M, L, G
```

### 4. Safety Test Case - WLFI (High Risk)

```bash
# Scan high-risk token for safety gate validation
python -m src.cli.run_scanner configs/tokens/wlfi_safety_test.yaml --tree --verbose

# Expected output:
# - GemScore: 45-62 (may be flagged)
# - Confidence: 0.55+
# - Safety: MAY FLAG on T or C scores
# - Purpose: Validate safety gate detection
```

### 5. Portfolio Comparison - All Risk Tiers

```bash
# Comparative scan across risk spectrum
python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml --tree

# Expected ranking:
# 1. ONDO (75-82) - Institutional
# 2. ENA  (72-78) - DeFi
# 3. PEPE (58-68) - Meme
# 4. WLFI (45-62) - High-risk
```

### 6. DeFi Sector Analysis

```bash
# Focused DeFi infrastructure scan
python -m src.cli.run_scanner configs/tokens/defi_focus.yaml --tree

# Tokens analyzed:
# - ENA (Synthetic Assets)
# - PENDLE (Yield Trading)
# - MORPHO (Lending Optimizer)
# - ETHFI (Liquid Restaking)
```

## 📊 Understanding Output

### GemScore Interpretation

| Range | Interpretation | Action |
|-------|----------------|--------|
| 80-100 | Exceptional signal | High confidence recommendation |
| 70-79 | Strong signal | Watch closely, consider position |
| 60-69 | Moderate signal | Monitor for improvements |
| 50-59 | Weak signal | Requires further analysis |
| <50 | Poor signal / Flagged | Avoid or wait for improvements |

### Confidence Levels

| Confidence | Data Quality | Interpretation |
|------------|--------------|----------------|
| 0.85+ | Excellent | High data completeness & recency |
| 0.75-0.84 | Good | Most data available |
| 0.65-0.74 | Moderate | Some data gaps |
| <0.65 | Low | Significant data limitations |

### Safety Status

- ✅ **PASS** - All safety checks passed
- ⚠️ **WARNING** - Minor concerns, proceed with caution
- 🚫 **FLAGGED** - Critical safety issues detected, avoid

## 🔍 Advanced Analysis

### Generate Lore Capsule (Artifact)

```bash
# Create mythic market intelligence report
python -m src.cli.run_scanner configs/tokens/ondo_finance.yaml \
  --tree \
  --output=artifacts \
  --format=lore_capsule

# Output: artifacts/ondo_finance_lore_capsule.html
```

### Export to Obsidian

```bash
# Generate Obsidian-compatible markdown
python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml \
  --output=obsidian \
  --format=markdown

# Output: reports/obsidian/ena_analysis.md
```

### JSON Output for API Integration

```bash
# Machine-readable output
python -m src.cli.run_scanner configs/tokens/pepe_meme.yaml \
  --output=json \
  --save-to=reports/json/pepe_scan.json
```

### Execution Tree Visualization

```bash
# Pretty-print execution tree
python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml \
  --tree \
  --tree-format=pretty

# JSON tree for programmatic access
python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml \
  --tree \
  --tree-format=json
```

## 📈 Backtesting

### Historical Performance Analysis

```bash
# Backtest token selection over historical period
python -m src.pipeline.backtest \
  --tokens=ENA,ONDO,PEPE,WLFI \
  --start=2024-09-01 \
  --end=2025-10-11 \
  --experiment-description="Token list validation" \
  --experiment-tags="production,recommended_tokens"

# Output: reports/backtests/<date>/summary.json
```

### Compare Weight Configurations

```bash
# Test different scoring weights
python -m src.pipeline.backtest \
  --config=configs/tokens/balanced_portfolio.yaml \
  --weight-experiments \
  --output=reports/backtests/weight_comparison/
```

## 🔔 Setting Up Alerts (Optional)

### Telegram Alerts

```bash
# Edit alert configuration
# configs/alert_rules.yaml

# Add rule for high GemScore
- name: "High GemScore Breakout - ENA"
  condition: "gem_score >= 75 AND confidence >= 0.75"
  tokens: ["ENA"]
  priority: "HIGH"
  telegram:
    enabled: true
    chat_id: "YOUR_CHAT_ID"
```

### Slack Integration

```bash
# Configure Slack webhook in .env
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/..." >> .env

# Run with alerts enabled
python -m src.cli.run_scanner configs/tokens/ondo_finance.yaml \
  --enable-alerts
```

## 🛠️ Troubleshooting

### Issue: "API key required"

**Solution:** You're using FREE tier - ensure configs specify FREE clients:

```yaml
data_sources:
  - "coingecko"      # FREE (no key needed)
  - "dexscreener"    # FREE
  - "blockscout"     # FREE
  - "ethereum_rpc"   # FREE
```

### Issue: "Contract not found"

**Solution:** Verify contract address on Etherscan:
```bash
# Check contract exists
curl "https://api.etherscan.io/api?module=contract&action=getabi&address=0x..."
```

### Issue: "Low confidence score"

**Solution:** This is normal for:
- New tokens (<30 days old)
- Low-volume tokens (<$50K daily)
- Tokens with incomplete data

### Issue: "Safety gate flagged"

**Solution:** Review safety report details:
```bash
python -m src.cli.run_scanner configs/tokens/wlfi_safety_test.yaml \
  --verbose \
  --log-safety-checks
```

## 📚 Additional Resources

### Documentation References

- **Full Token List:** [`docs/RECOMMENDED_TOKENS.md`](../docs/RECOMMENDED_TOKENS.md)
- **FREE Data Sources:** [`docs/FREE_DATA_SOURCES.md`](../docs/FREE_DATA_SOURCES.md)
- **Safety Gate Guide:** [`docs/FEATURE_VALIDATION_GUIDE.md`](../docs/FEATURE_VALIDATION_GUIDE.md)
- **Experiment Tracking:** [`docs/EXPERIMENT_TRACKING.md`](../docs/EXPERIMENT_TRACKING.md)

### Configuration Files

All token configs are in: `configs/tokens/`

```
configs/tokens/
├── ena_ethena.yaml           # DeFi infrastructure
├── ondo_finance.yaml         # Institutional RWA
├── pepe_meme.yaml           # Meme token
├── wlfi_safety_test.yaml    # Safety gate testing
├── balanced_portfolio.yaml  # Multi-token comparison
└── defi_focus.yaml          # DeFi sector analysis
```

## 🔄 Continuous Monitoring

### Daily Scan Routine

```bash
# Morning scan - DeFi focus
python -m src.cli.run_scanner configs/tokens/defi_focus.yaml

# Midday - Portfolio check
python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml

# Evening - Meme momentum check
python -m src.cli.run_scanner configs/tokens/pepe_meme.yaml
```

### Automated Scheduling (Windows)

```powershell
# Create scheduled task for daily scan
$action = New-ScheduledTaskAction -Execute "python" `
  -Argument "-m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml" `
  -WorkingDirectory "c:\Users\kay\Documents\Projects\AutoTrader\Autotrader"

$trigger = New-ScheduledTaskTrigger -Daily -At 9AM

Register-ScheduledTask -TaskName "VoidBloom_Daily_Scan" `
  -Action $action -Trigger $trigger
```

### Automated Scheduling (Linux/Mac)

```bash
# Add to crontab
crontab -e

# Run daily at 9 AM
0 9 * * * cd /path/to/Autotrader && python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml
```

## 🎓 Learning Path

### Beginner

1. Run single token scan (ENA or ONDO)
2. Understand GemScore components
3. Review safety gate results

### Intermediate

1. Run portfolio comparison
2. Experiment with weight configurations
3. Generate lore capsules

### Advanced

1. Historical backtesting
2. Custom weight optimization
3. Alert rule creation
4. Multi-chain token analysis

## 📞 Support

For issues or questions:

1. Check documentation in `docs/`
2. Review test files in `tests/`
3. Open issue on GitHub repository
4. Reference [`README.md`](../README.md) for system overview

---

**Quick Reference Card**

```bash
# Single scan
python -m src.cli.run_scanner configs/tokens/<token>.yaml --tree

# Portfolio scan
python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml

# Backtest
python -m src.pipeline.backtest --tokens=ENA,ONDO,PEPE

# Generate artifact
python -m src.cli.run_scanner <config> --output=artifacts

# Run tests
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

**Cost Reminder:** All commands use FREE data sources ($0/month) unless you explicitly configure paid API keys.

---

**Document Version:** 1.0  
**Last Updated:** October 11, 2025  
**Status:** ✅ Ready for Use
