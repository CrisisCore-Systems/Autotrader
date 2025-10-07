# Backtesting Runbook

This runbook explains how to operate the walk-forward GemScore backtest harness and how nightly jobs should be configured.

## Daily Workflow

1. Sync the latest historical data snapshot to `data/historic/` (or ensure the S3/GCS mount is available).
2. Execute `make backtest` to run the harness with the default parameters.
3. Review the generated report under `reports/backtests/<yyyymmdd>/`.
4. Publish the `summary.json` precision metrics to the dashboard badge.

## Custom Execution

The CLI wrapper accepts several parameters for ad-hoc investigations:

```bash
python -m pipeline.backtest \
  --start 2023-01-01 \
  --end 2025-09-30 \
  --walk 30d \
  --k 10 \
  --output reports/backtests \
  --seed 42
```

## Outputs

* `summary.json` – aggregated precision@K and forward return metrics.
* `weights_suggestion.json` – recommended feature weights for the next production cycle.
* `windows.csv` – per-window statistics for deeper debugging.

Upload these artifacts to the long-term storage bucket after each run to keep the lineage reproducible.

## CI Nightly Job

The `.github/workflows/tests-and-coverage.yml` job can be duplicated with a `schedule:` trigger to execute the backtest overnight. Mount required secrets for data access and push the artifacts using `actions/upload-artifact` or a custom sync step.

## Troubleshooting

* **No windows generated** – ensure the `--walk` interval is shorter than the overall backtest range.
* **Precision regression** – compare the `windows.csv` output with the previous day's run to identify outlier periods and re-run with a smaller walk size for more granularity.
* **Inconsistent metrics** – confirm the random seed and the historical data snapshot hash to rule out upstream changes.
