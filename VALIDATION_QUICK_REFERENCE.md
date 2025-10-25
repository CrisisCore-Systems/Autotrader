# Validation Pipeline - Quick Reference

## Daily Operations

### Check Pipeline Status
```bash
cd Autotrader
dvc status
```

### Run Full Validation
```bash
# Reproduce all stages
dvc repro

# Push results to cache
dvc push
```

### Run Reconciliation Only
```bash
python scripts/validation/reconcile_data.py \
  --historical data/historical/dukascopy \
  --live data/raw/market \
  --output reports/reconciliation_report.json \
  --validation-log reports/validation.log

# View report
cat reports/validation.log
```

### Snapshot Current Config
```bash
python scripts/validation/snapshot_config.py \
  --agents-config configs/agents.yaml \
  --training-config configs/training/strategy.yaml \
  --feature-catalog FEATURE_CATALOG.md \
  --output artifacts/config_snapshot_$(date +%Y%m%d).json \
  --dvc-metrics artifacts/config_metrics.json
```

### Run Smoke Test
```bash
# Local
python scripts/validation/smoke_test.py \
  data/processed/features/EURUSD_bars_features.parquet

# Docker
docker-compose --profile validation up backtest
```

## Troubleshooting

### "Data not found"
```bash
# Pull from DVC cache
dvc pull

# Or regenerate
dvc repro fetch_market_data
```

### "Stage failed"
```bash
# Check specific stage
dvc repro <stage_name> --verbose

# Force rerun
dvc repro <stage_name> --force
```

### "Reconciliation failed"
```bash
# Check data exists
ls -la data/historical/dukascopy/
ls -la data/raw/market/

# Copy sample data if needed
cp data/raw/market/EURUSD_bars.parquet data/historical/dukascopy/
```

## CI/CD Integration

### Pre-commit Hook
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
dvc status || exit 1
python scripts/validation/smoke_test.py data/processed/features/EURUSD_bars_features.parquet
```

### GitHub Actions Workflow
```yaml
name: Validation Pipeline
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: iterative/setup-dvc@v1
      - run: dvc pull
      - run: dvc repro
      - run: python scripts/validation/smoke_test.py data/processed/features/EURUSD_bars_features.parquet
```

## Metrics to Monitor

### Data Quality
- Reconciliation match rate: >95%
- Feature completeness: 100%
- Data freshness: <24h lag

### Config Drift
- Training config hash changes
- Feature catalog hash changes
- Agent definition changes

### Backtest Baseline
- Precision@10: >0.30
- Information Coefficient: >0.03
- ROC AUC: >0.55

## Contact

- Data Issues: data-eng@autotrader.com
- Pipeline Issues: mlops@autotrader.com
- Backtest Issues: quant-dev@autotrader.com
