# Architectural Specification: Multi-Order Concurrent Harness (TR-004)

Document Status: Working Draft

Target File Path: docs/architecture/TR-004_concurrent_harness_spec_v1.md

## 1. Core Objectives and Problem Space

The single-shot engine (v1) proved the state machine is reliable for an isolated signal lifecycle. Scaling to real-world flow requires simultaneous asynchronous loops while preserving strict safety guarantees.

### The Real-World Complexity

When multiple signals arrive concurrently, three bottlenecks emerge:

1. The single-threaded IBKR connection: TWS API communication uses one TCP socket path. Reusing concurrent connections on one client ID can trigger packet loss or broker-side rejection.
2. State map collisions: parallel writes to one status artifact can create file lock conflicts or corruption.
3. Tracking misalignment: out-of-order exchange updates must still map to the originating signal thread and order identity.

## 2. Structural Blueprint: Shared-Queue Worker Model

To preserve rails under concurrent load, execution shifts from per-signal script instances to a centralized broker-worker model.

```text
[ Incoming Signal Array ] --> Local JSON Payload
            |
            v
+-----------------------+
|   Ingestion Router    | --> Per-signal risk validation
+-----------+-----------+
            |
            v
+-----------------------+
| Async Threaded Queue  | --> FIFO buffer
+-----------+-----------+
            |
            v
+-----------------------+
|   Central TWS Worker  | --> Exclusive owner of client-ID socket
+-----------+-----------+
            |
     +------+------+
     |             |
     v             v
[Order Thread 1] [Order Thread 2] --> Isolated status trackers
```

### Components of the Multi-Order Harness

- Ingestion Router: parses concurrent signal arrays, applies max-notional checks per element, and enqueues only compliant signals.
- Central Worker Thread: owns the persistent paper connection on port 7497, sends all orders, and receives all exchange updates.
- Isolated Tracking Map: uses thread-safe coordination (`threading.Lock` or `asyncio.Queue`) so order state for each order ID remains isolated.

## 3. Toughened Safety Rails (TR-004 Spec)

### Aggregate Risk Ceiling

In addition to per-order max notional (`<= 5`), add an aggregate active-risk ceiling. If total value of active, uncancelled orders exceeds a combined threshold (example: `20`), intake halts and a defensive block is raised.

### Thread-Isolated Serialization

Use unique per-signal artifact keys to avoid write collisions:

`reports/ibkr/concurrent_run_[timestamp]_[signal_id].json`

## 4. Next Implementation Action

To move from design to implementation, create scaffolding for the concurrent harness script.

Recommended immediate actions:

1. Keep current matrix verdict draft untracked until architecture and skeleton are both reviewed.
2. Initialize script skeleton with no strategy automation:
   - queue ingestion stub
   - central worker loop stub
   - thread-safe order-state registry stub
   - isolated artifact writer stub
3. Add a dry-run mode for TR-004 that validates queue flow and state serialization without order submission.

## 5. Safety Constraints for TR-004 Development

- Paper-only, localhost-only, port 7497 only.
- No live routing, no live port usage.
- Limit orders only.
- Per-order notional `<= 5`.
- Aggregate active-risk guard enabled.
- Explicit cancel window retained for rehearsal control.
