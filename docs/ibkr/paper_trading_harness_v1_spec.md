# IBKR Paper Trading Harness v1 Specification

## Purpose

Provide a bounded, observable paper-order harness that accepts one simulated signal and optionally submits at most one constrained IBKR paper order.

This harness exists to validate safety controls and execution plumbing only.

## Hard Boundaries

- Paper mode only.
- Localhost only (`127.0.0.1` or `localhost`).
- TWS paper port only (`7497`).
- Explicit operator acknowledgement phrase required.
- One accepted signal maximum per run.
- One order submission maximum per run.
- Limit orders only (`LMT`).
- Equity security type only (`STK`).
- Notional cap must remain `<= 5.00`.
- No strategy loop or autonomous signal generation.
- No live routing and no live ports.

## Required v1 Flow

1. Load one simulated-signal fixture.
2. Apply paper-only config guard.
3. Run preflight checker and evaluate reject fixtures.
4. If valid and `--submit-paper-order` is set, submit one constrained order.
5. Attempt cancel after a short delay.
6. Write status artifact with preflight, fixture, submit, and cancel events.

## Inputs

- `--paper-only` (required guard flag)
- `--ibkr-host` (default `127.0.0.1`)
- `--ibkr-port` (default `7497`)
- `--ibkr-client-id`
- `--signals-json` (fixture path)
- `--min-confidence`
- `--max-order-notional`
- `--submit-paper-order` (explicit submit switch)
- `--cancel-after-seconds`
- `--i-understand-this-submits-a-paper-order` (must exactly match phrase)
- `--status-output`

## Artifact Contract

Default artifact path: `reports/ibkr/paper_trading_harness_v1_status.json`

Artifact must include:

- Request and constraints.
- Fixture evaluation results.
- Accepted signal id.
- Whether submission was attempted.
- Connection, submit, cancel, and disconnect outcomes.
- Any errors.
- Timestamps.

## Non-Goals

- Live trading behavior.
- Multi-order batching.
- Strategy automation.
- Retry loops.
- Dependency or policy changes.
