# Phase 5: Live Connectivity Specification

**Status:** Draft started
**Scope:** Live OMS contract, exchange reconciliation, and guardrails

---

## Objective

Phase 5 connects the validated execution state machine to live market I/O while preserving the deterministic routing and shield behavior established in Phase 4.

The first implementation surface is the OMS boundary because it is the narrowest point where live orders, fills, reconciliation, and kill-switch logic converge.

---

## Package Layout

```text
autotrader/execution/
├── adapters/                 # Exchange/broker integrations
├── oms/                      # Backtest/live order tracking core
├── live/                     # Phase 5 live contract layer
└── resiliency/               # Retry, reconnect, circuit breaker
```

---

## Current Live Contracts

### `LiveOMS`

Location: `autotrader/execution/live/oms.py`

Responsibilities:
- Submit and cancel live orders through the existing broker adapter
- Maintain an event log for submitted, cancelled, filled, and divergence events
- Provide point-in-time portfolio snapshots for audit and reconciliation
- Engage a kill switch when local state diverges from exchange state

### `LiveOrderEvent`

Structured event payload used for CI, shadow mode, and live auditing.

### `PortfolioStateSnapshot`

Portable snapshot of the live portfolio state used to compare engine state against exchange state.

### `StateDivergence`

Record of a reconciliation mismatch between the engine and exchange view of the world.

---

## Build Order

1. `LiveOMS` contract and state log
2. Reconciliation loop that consumes wallet / open-order snapshots
3. Market data adapter for live bar and tick ingestion
4. Guardrail layer that halts on jitter, heartbeat loss, or state drift

---

## Staging Plan

1. Paper sandbox mode
2. Shadow tracking mode
3. Production gate rollout
