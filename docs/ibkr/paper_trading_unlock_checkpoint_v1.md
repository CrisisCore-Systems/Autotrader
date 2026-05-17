# IBKR Paper Trading Unlock Checkpoint v1

## Purpose

Declare that constrained IBKR paper-trading work may resume after CI visibility, dependency lane reporting, package metadata propagation, and warning-only license summaries were restored.

## Completed safety chain

- IBKR paper probe completed
- Simulated signal paper harness completed
- Batch rejection audit completed
- One-order cap validated
- Cancel path validated
- Dependency lane reports operational
- Package metadata propagation fixed
- Lane license policy drafted
- Warning-only lane license summaries implemented
- Remaining license findings are visible and non-blocking

## Unlock decision

Constrained paper-trading development may resume.

This does not authorize live trading, autonomous strategy execution, increased order sizing, or production deployment.

## Allowed next scope

- Simulated strategy signal only
- IBKR paper/TWS port 7497 only
- One accepted signal
- One capped paper order
- Preflight validation
- Cancel path
- Status artifact
- No loop

## Still forbidden

- Live trading ports
- Live account routing
- Market orders
- Multi-order loops
- Increased notional
- Real autonomous strategy feed
- Automatic retry loops
- Background execution
- Any escalation from paper to live

## Required next implementation

The next implementation milestone should be:

IBKR paper trading harness v1

The harness must remain bounded, observable, and reversible.

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No dependency movement.
No license enforcement changes.
No live trading behavior.
No autonomous trading behavior.
