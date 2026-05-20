# IBKR Paper Trading Harness v1 Dual-Run Review

## Purpose

Review the first two controlled IBKR paper harness v1 rehearsals and decide whether a third controlled rehearsal with varied fixture input is allowed.

This review does not authorize autonomous strategy execution.

## Reviewed checkpoints

| Rehearsal | Evidence doc | Artifact | Client ID | Result |
|---|---|---|---:|---|
| 001 | paper_trading_harness_v1_controlled_submit_evidence.md | reports/ibkr/paper_trading_harness_v1_status.submit.json | 90 | success |
| 002 | paper_trading_harness_v1_second_controlled_rehearsal.md | reports/ibkr/paper_trading_harness_v1_status.submit_002.json | 91 | success |

## Shared successful fields

Both rehearsals recorded:

- `fixtures_passed = true`
- `accepted_signal_id = sim-v1-001`
- `order_submission_attempted = true`
- `connected = true`
- `submitted = true`
- `cancel_attempted = true`
- `cancelled = true`
- `order_status = submitted`

## Boundary confirmation

Both rehearsals remained inside the v1 rails:

- Paper port `7497` only
- Localhost only
- One manual trigger
- One simulated signal
- One capped paper order
- Limit order only
- Cancel attempted
- No retry loop
- No strategy automation
- No live routing
- No live port usage

## Stability assessment

The harness has now demonstrated repeatable controlled paper execution across two manual rehearsals.

The repeated success indicates the v1 guardrails, preflight validation, paper connection path, submit path, cancel path, and status artifact path are functioning as intended under the same fixture input.

## Remaining limitation

Both successful rehearsals used the same simulated signal fixture:

`sim-v1-001`

This proves repeatability of the harness path, not diversity of signal handling.

## Go / no-go decision

Go for one third controlled rehearsal with varied fixture input.

## Third rehearsal allowed scope

The third rehearsal may vary the simulated fixture while preserving all rails:

- Paper-only
- Port `7497`
- Localhost
- One manual trigger
- One signal
- One capped paper order
- Limit order only
- Max notional `<= 5`
- Immediate cancel path
- Status artifact preserved

## Still forbidden

- Autonomous strategy execution
- Live routing
- Live port `7496`
- Market orders
- Multi-order loops
- Retry loops
- Increased notional
- Background execution
- Any paper-to-live escalation

## Next milestone

IBKR paper harness v1 varied-fixture rehearsal plan.

That milestone should define a safe alternate simulated signal fixture before any third controlled submit is attempted.

## Phase 3 Verification & Lockdown (2026-05-17)

### Subsystem Integration

* **Resilience Gate:** Integrated `ConnState` tracking directly inside `IBKRAdapter.error()`. Classification matrix filters out informational code `399` to prevent false terminal state transitions.
* **Durability Layer:** Active `StateWALEngine` instance tracking atomic line mutations down to local disk workspace under `reports/ibkr/adapter_state_journal.wal`.
* **Telemetry Core:** Added local post-trade performance analytics engine exporting unified JSONL records under `reports/ibkr/execution_performance.jsonl`.

### Live Operational Benchmarks (Run 294)

* **Commit Hash:** `a013cec6`
* **Trigger Sequence:** Connect -> Submit -> Warning 399 (Interceded) -> PreSubmitted -> Local Cancel (Forced Seal).
* **State Accuracy:** Checked file targets. Zero false rejections occurred. Telemetry records perfectly captured the terminal `Cancelled` transition along with pre-calculated microsecond latency deltas.

## Option A Lock-In: WAL Execution Fingerprint Durability (2026-05-17)

### Transaction Boundary

Execution reports now cross a strict durability boundary before any downstream mutation:

1. Dedup gate checks `order_id:exec_id` against the in-memory fingerprint index.
2. New packets are persisted as an append-only WAL `EXEC` row.
3. WAL append is synchronously committed with `fdatasync`/`fsync`.
4. Only after disk commit does the adapter advance in-memory execution and fill flows.

This protects idempotency across cold restarts and crash scenarios.

### Compatible WAL Grammars

Boot-time rehydration accepts mixed historical row formats:

- Legacy JSON state rows (with checksum)
- `STATE|<sequence_id>|<timestamp>|<order_id>|<status>|<filled>|<remaining>`
- `EXEC|<sequence_id>|<timestamp>|<order_id>|<exec_id>|<price>|<shares>`

`EXEC` rows hydrate `_seen_execution_fingerprints` before reconnect callback processing, preventing duplicate fill ingestion from replayed broker packets.

### Deterministic Verification Protocol

1. Run a controlled paper rehearsal with a fill path expected to produce partials.
2. Confirm `EXEC` rows are appended in `reports/ibkr/adapter_state_journal.wal` during fills.
3. Force terminate the process mid-order to emulate crash conditions.
4. Restart the adapter and verify rehydration completes without parser faults.
5. Confirm replayed historical `execId` packets are suppressed while new executions still pass.

## Vector 1 Phase 1: Telemetry Export Gateway (2026-05-17)

### Non-Blocking Telemetry Bus

The IBKR adapter now emits structured telemetry envelopes through a bounded, non-blocking queue serviced by a daemon worker thread.

- Queue policy is strict `drop_oldest` under saturation to prevent callback path blocking.
- Primary transport is JSON-over-UDP for out-of-band diagnostics streaming.
- Event sequence IDs are monotonic per process for replay correlation.

### Envelope Families Enabled

- `SYSTEM_HEARTBEAT` with drift/lock/fingerprint operational metrics.
- `CIRCUIT_BREACH` for symbol or portfolio-level interlock transitions.
- `CIRCUIT_RESET` for successful operator clear transitions.
- `WAL_RECOVERY_ANOMALY` when startup tail repair is detected.

### Validation Coverage

- Saturation behavior validated with explicit drop-oldest regression checks.
- Adapter callback path validated for `CIRCUIT_BREACH` emission on threshold breach.
- Heartbeat envelope emissions validated for schema and metrics presence.

## Vector 1 Phase 2: Last-Gasp Crash Diagnostics (2026-05-17)

### Crash Envelope Persistence

The adapter now performs synchronous crash-path diagnostics writes to:

- `reports/ibkr/crash_diagnostics.json`

The persisted envelope includes:

- Fatal exception type, message, and traceback string.
- Current reconciliation/circuit state and gross portfolio drift metrics.
- Local and broker position snapshots at failure time.
- Sliding tail of the last 10 reconciliation journal events.

### Triggered Failure Boundaries

Last-gasp persistence is invoked on high-severity boundaries:

- WAL rehydration failure during adapter startup.
- Connection retry exhaustion after max reconnect attempts.
- Fatal order submission exceptions (`submit_order`).

### Validation Coverage

- Verified envelope persistence and exact last-10 event truncation behavior.
- Verified submit-order failure path writes crash envelope with symbol-scoped context tag.

## Vector 1 Phase 3: Webhook Cooldown & Re-Arm (2026-05-17)

### Breach-Epoch Suppression Model

Critical webhook alerts now follow a stateful, epoch-based suppression gate:

- First transition to breach context emits one webhook dispatch envelope.
- Repeated breach updates for the same alert token are suppressed while breached.
- Successful `operator_clear_circuit()` re-arms the webhook gate for the next fresh breach.

### Critical Paths Wired

- `CIRCUIT_BREACH` events trigger webhook dispatch through the telemetry worker.
- `WAL_RECOVERY_ANOMALY` startup path triggers one critical webhook alert.

### Validation Coverage

- Verified first-breach webhook dispatch emission.
- Verified sustained breach suppression across repeated packets.
- Verified operator clear re-arm allows a fresh breach to emit a new webhook event.

## Vector A Phase 1: Account-Keyed Scaffolding (2026-05-17)

### Compatibility-First Namespace Migration

The adapter now supports account-scoped runtime state bootstrap while preserving legacy single-account behavior.

- Added `default_account_id` constructor parameter with env fallback (`IBKR_DEFAULT_ACCOUNT_ID`).
- Added account context resolver `_get_account_ctx(account_id)` with lazy initialization.
- Added compatibility bridge `_sync_default_account_state()` so existing flat primitives remain authoritative during migration.

### Account Routing Baseline

Incoming `position(account, ...)` callbacks now route broker position snapshots into account-keyed containers while retaining existing flat snapshots for regression-safe behavior.

### Validation Coverage

- Verified default account namespace initialization and key presence.
- Verified per-account broker snapshot partitioning for distinct account IDs.
