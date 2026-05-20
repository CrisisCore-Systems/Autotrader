import pytest

from autotrader.execution.adapters.ibkr import CriticalRecoveryAnomaly, IBKRAdapter


def test_startup_attestation_passes_when_state_matches() -> None:
    adapter = IBKRAdapter()
    adapter._expected_wal_positions = {"U1111111": {"USD:AAPL": 40.0}}
    adapter._expected_active_perm_ids = {12345}
    adapter._order_state_snapshots = {
        9001: {
            "signal_id": "sim-phase3-9001",
            "status": "Submitted",
            "filled": 0.0,
            "remaining": 1.0,
            "last_seq": 3,
        }
    }
    adapter._startup_live_positions = {"U1111111": {"USD:AAPL": 40.0}}
    adapter._startup_live_open_perm_ids = {12345}
    adapter._startup_live_open_order_ids = {9001}

    adapter._validate_startup_recovery_state()

    assert adapter._global_kill_active is False


def test_startup_attestation_trips_kill_on_position_drift() -> None:
    adapter = IBKRAdapter()
    adapter._expected_wal_positions = {"U1111111": {"USD:AAPL": 40.0}}
    adapter._expected_active_perm_ids = set()
    adapter._order_state_snapshots = {}
    adapter._startup_live_positions = {"U1111111": {"USD:AAPL": 39.0}}
    adapter._startup_live_open_perm_ids = set()
    adapter._startup_live_open_order_ids = set()

    with pytest.raises(CriticalRecoveryAnomaly):
        adapter._validate_startup_recovery_state()

    assert adapter._global_kill_active is True
    assert adapter._reconciliation_circuit_open is True


def test_startup_attestation_trips_kill_on_ghost_order() -> None:
    adapter = IBKRAdapter()
    adapter._expected_wal_positions = {}
    adapter._expected_active_perm_ids = set()
    adapter._order_state_snapshots = {}
    adapter._startup_live_positions = {}
    adapter._startup_live_open_perm_ids = {777777}
    adapter._startup_live_open_order_ids = {9001}

    with pytest.raises(CriticalRecoveryAnomaly):
        adapter._validate_startup_recovery_state()

    assert adapter._global_kill_active is True
