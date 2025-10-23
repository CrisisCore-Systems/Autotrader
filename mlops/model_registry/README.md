# Model Registry Workflow

This directory contains automation helpers for promoting models through MLflow registry stages.

## Promotion Policy

1. **Staging**: Automatically triggered after a successful backtest/paper run meeting Phase 0 KPIs.
2. **Production**: Manual approval required with sign-off from Quant Engineering and Risk.

## Required Environment Variables

- `MLFLOW_TRACKING_URI`
- `MLFLOW_BACKEND_URI`
- `MLFLOW_S3_BUCKET`
- `MODEL_NAME` (default: `autotrader-strategy`)

## Usage

```bash
python -m mlops.model_registry.register_model \
  --run-id 123abc456def \
  --model-name autotrader-strategy \
  --stage Staging
```

Promotion to production requires `--stage Production` and `--comment` describing the change log.
