# IBKR Paper Trading Harness v1 Varied-Fixture Rehearsal Plan

## Purpose

Define a controlled, docs-only execution plan for a third IBKR paper harness v1 rehearsal cycle that introduces fixture diversity while preserving all safety rails.

This document does not authorize autonomous strategy execution.

## Scope

- Plan-only milestone (no code or configuration changes)
- One controlled rehearsal cycle with five single-shot runs
- Same guardrails as prior rehearsals
- Explicit focus on fixture diversity and cancel-path timing race condition behavior

## Safety Invariants (Must Never Change)

All runs in this plan must keep these constraints locked:

- Paper-only execution
- Port `7497` only
- Localhost only
- One manual trigger per run
- One signal per run
- One capped paper order per run
- Limit order only
- Max notional `<= 5`
- Immediate cancel path attempted
- Status artifact preserved for each run
- No retry loops
- No multi-order loops
- No strategy automation
- No live routing
- No live port usage (`7496`/`4001`)
- No paper-to-live escalation

## Structural Parameters

### 1) Fixture Families

- Baseline variant: same schema class, changed symbols/prices/sizing
- Edge-notional variant: values near max notional boundary while `<= 5`
- Sparse-liquidity variant: wider spread assumptions to test limit viability
- Slow-ack variant: delayed status transitions to stress submit-to-cancel sequencing
- Partial-fill variant: controlled partial fill trace before cancel

### 2) Invariant Enforcement Model

- Run-level preflight gate: hard fail if any rail check is false
- Run-level execution gate: exactly one submit attempt and one cancel path
- Run-level artifact gate: write status artifact before run close

### 3) Acceptance Criteria Model

Each run is evaluated using the same binary checks:

- `fixtures_passed = true`
- `order_submission_attempted = true`
- `connected = true`
- `submitted = true` OR explicit API rejection documented
- `cancel_attempted = true`
- terminal status in allowed set for that variant
- status artifact includes timestamps, variant ID, and terminal status

### 4) Failure Modes to Target

- Schema drift and field ordering assumptions
- Boundary and rounding behavior near notional limits
- Cancel-path timing races under delayed acknowledgments
- Status propagation lag and stale terminal state reads
- Partial-fill handling and remaining quantity state correctness

### 5) Decision and Escalation Rules

- Go only if all five runs stay inside rails and artifact evidence is complete
- No-Go if any rail breach, missing artifact, or unexplained terminal state occurs
- Any No-Go result blocks further submit rehearsals until review sign-off

## Varied-Fixture Execution Matrix

| Run ID | Fixture Variant | Primary Failure Focus | Expected Terminal State |
|---|---|---|---|
| TR-003-A | Baseline Variant (new symbols, standard sizing) | Schema drift, field ordering validation | Clean `Cancelled` state |
| TR-003-B | Edge-Notional Variant (sized at `<= 5` cap) | Boundary truncation, minimum tick size violations | Clean `Cancelled` or API rejection |
| TR-003-C | Sparse-Liquidity Variant (wider simulated bid/ask spreads) | Order hanging, non-immediate fills, pricing logic | Clean `Cancelled` (unfilled limit) |
| TR-003-D | Slow-Ack Variant (injected status transition latency) | Cancel-path race condition in rapid submit-to-cancel | `Cancel Requested` -> `Cancelled` |
| TR-003-E | Partial-Fill Variant (simulated execution before cancel) | Partial-fill handling, remaining quantity math | `Partially Filled` -> `Cancelled` |

## Pre-Flight Checklist (Binary)

The pre-flight routine must pass all checks before each run:

- [ ] Environment lock: host is localhost and port is `7497`
- [ ] Isolation lock: live ports (`7496`/`4001`) structurally inaccessible
- [ ] Single-shot lock: one signal, one trigger, one capped order
- [ ] Fixture isolation: explicit variant fixture loaded, no fallback defaults
- [ ] Artifact check: target local log directory writable

## Run Procedures and Pass/Fail Checklists

Apply this process for each run TR-003-A through TR-003-E.

### Shared Procedure (All Runs)

1. Confirm all pre-flight checklist items are true.
2. Load the exact variant fixture for the run ID.
3. Execute one manual trigger.
4. Allow one order submit attempt only.
5. Attempt immediate cancel path.
6. Record terminal status and write status artifact.
7. Stop run and capture operator notes.

### TR-003-A Pass/Fail Checklist (Baseline Variant)

- [ ] Fixture loaded: Baseline variant
- [ ] Rails preserved end-to-end
- [ ] Submit attempted exactly once
- [ ] Cancel attempted exactly once
- [ ] Terminal state: `Cancelled`
- [ ] Artifact includes variant ID `TR-003-A`

Pass: all boxes checked.

Fail: any unchecked box or unexplained terminal state.

### TR-003-B Pass/Fail Checklist (Edge-Notional Variant)

- [ ] Fixture loaded: Edge-notional variant
- [ ] Max notional remains `<= 5`
- [ ] Submit attempted exactly once
- [ ] Terminal state is either `Cancelled` or explicit API rejection captured
- [ ] If rejected, rejection reason is preserved in artifact
- [ ] Artifact includes variant ID `TR-003-B`

Pass: all boxes checked.

Fail: boundary overrun, missing rejection evidence, or rail violation.

### TR-003-C Pass/Fail Checklist (Sparse-Liquidity Variant)

- [ ] Fixture loaded: Sparse-liquidity variant
- [ ] Limit order constraints preserved
- [ ] Submit attempted exactly once
- [ ] Cancel attempted exactly once
- [ ] Terminal state: `Cancelled` (unfilled limit accepted)
- [ ] Artifact includes variant ID `TR-003-C`

Pass: all boxes checked.

Fail: hanging state without closure evidence, or rail violation.

### TR-003-D Pass/Fail Checklist (Slow-Ack Variant)

- [ ] Fixture loaded: Slow-ack variant
- [ ] Submit attempted exactly once
- [ ] Cancel attempted immediately after submit path
- [ ] Transition observed: `Cancel Requested` -> `Cancelled`
- [ ] No dropped cancel request due to delayed ack state
- [ ] Artifact includes timing markers and variant ID `TR-003-D`

Pass: all boxes checked.

Fail: dropped/ignored cancel request, ambiguous sequence, or rail violation.

### TR-003-E Pass/Fail Checklist (Partial-Fill Variant)

- [ ] Fixture loaded: Partial-fill variant
- [ ] Submit attempted exactly once
- [ ] Partial fill evidence captured before cancel completion
- [ ] Transition observed: `Partially Filled` -> `Cancelled`
- [ ] Remaining quantity/terminal status consistent in artifact
- [ ] Artifact includes variant ID `TR-003-E`

Pass: all boxes checked.

Fail: inconsistent fill math/state, missing trace evidence, or rail violation.

## Artifact Requirements

Each run must write one status artifact containing at minimum:

- run ID and variant name
- fixture identifier
- timestamped connection/submit/cancel events
- terminal order state
- rejection details if applicable
- operator notes for anomalies

## Definitive Go/No-Go Signature Block

Decision basis:

- Go only if all five runs pass with complete artifacts and no rail breaches.
- No-Go if any run fails, any artifact is incomplete, or any prohibited behavior is observed.

Sign-off template:

- Decision: `GO` / `NO-GO`
- Date (UTC): `YYYY-MM-DDTHH:MM:SSZ`
- Reviewer: `________________`
- Safety rail compliance confirmed: `YES` / `NO`
- Artifact completeness confirmed: `YES` / `NO`
- Notes: `____________________________________________________________`

## Forbidden Actions (Reaffirmed)

- Autonomous strategy execution
- Live routing
- Live port `7496`
- Market orders
- Multi-order loops
- Retry loops
- Increased notional beyond cap
- Background execution
- Any paper-to-live escalation

## Next Milestone

If decision is `GO`, proceed to execute the controlled third rehearsal using this plan.

If decision is `NO-GO`, open a remediation review and block further submit rehearsals until signed off.
