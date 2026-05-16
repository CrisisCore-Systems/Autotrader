# Phase 2 Paper-Trade Evidence Intake

This directory is the intake contract for real Phase 2 paper-trading outcomes.

Use these files to keep evidence collection consistent before any Phase 2 proof claim:

- `paper_trades.example.csv`: canonical column order and sample row format.
- `paper_trade_schema.json`: machine-readable schema for validation tooling.
- `PAPER_VALIDATION_STATUS.md`: current truth statement for Phase 2 validation readiness.

Important constraints:

- This intake layer does not replace `reports/validation/VALIDATION_REPORT_V1.md`.
- Backtest validation exists, but Phase 2 paper-trade proof is still pending.
- Live capital remains blocked until paper-trade evidence is complete and reviewed.

## Validate paper-trade intake

Run the intake validator from the repository root:

```powershell
python scripts/validation/validate_paper_trades.py
```

By default, this validates:

```text
reports/validation/paper_trading/paper_trades.example.csv
```

The validator fails when required columns are missing, unexpected columns are present, numeric fields are invalid, `mode` is not `paper`, or timestamps are malformed.

A passing validation does not mean Phase 2 paper-trading validation is complete. It only means the intake file follows the evidence contract.
