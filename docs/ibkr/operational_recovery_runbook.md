# IBKR Execution Engine: Startup Attestation and Recovery Runbook

This runbook describes how startup attestation works in the live IBKR adapter and how operators should recover when startup anomalies are detected.

## Startup Attestation Perimeter

During startup, the adapter executes a zero-trust sequence before order routing is allowed:

1. Rehydrate local expectations from WAL rows.
2. Request live broker snapshots using reqPositions() and reqOpenOrders().
3. Compare expected vs live state with a hard-stop matching fence.
4. Trip global kill if any startup anomaly is detected.

## Anomaly Tripwires

The adapter raises CriticalRecoveryAnomaly and sets _global_kill_active to True when either of these conditions is met:

1. Position drift mismatch.
If any account/symbol quantity reconstructed from WAL differs from the live broker snapshot, drift is treated as a startup failure.

2. Ghost order detection.
If live open orders contain order IDs or perm IDs that do not exist in local tracked state, they are treated as ghost orders.

When tripped, outbound order submission is blocked by the global kill gate.

## Operator Recovery Protocol

Follow this sequence to recover safely.

1. Verify discrepancy.
Inspect startup logs and telemetry for drift rows, ghost order IDs, and ghost perm IDs. Cross-check the same symbols/orders in TWS or Gateway.

2. Harmonize state.
If WAL is stale, reconcile local tracking artifacts with known exchange state before retrying startup.

3. Re-arm interlocks.
After reconciliation is complete, clear circuit state and global kill in the adapter process:

```python
# Default-account clear path
adapter.operator_clear_circuit("operator_manual_recovery")

# Account-scoped clear path (prefix with account namespace)
adapter.operator_clear_circuit("U1234567")
```

Notes:
- A successful clear resets _global_kill_active to False.
- Circuit and lock maps are re-armed.
- Webhook anti-flood epoch trackers are cleared.

## Implementation References

Startup rehydration and attestation path:
- autotrader/execution/adapters/ibkr.py

Validation coverage:
- tests/validation/test_ibkr_resilience_rehydration.py
- tests/validation/test_ibkr_vector2_attestation.py
- tests/validation/test_minimal_ibkr_adapter.py
