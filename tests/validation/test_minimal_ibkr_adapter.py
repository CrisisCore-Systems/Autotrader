import pytest
from autotrader.execution.adapters import Position
from autotrader.execution.adapters.ibkr import IBKRAdapter

def test_minimal_log_dir():
    adapter = IBKRAdapter()
    assert hasattr(adapter, "_log_dir"), "Adapter should have a '_log_dir' attribute"
    assert adapter._log_dir == "logs", "Default log directory should be 'logs'"

def test_minimal_monkeypatch(monkeypatch, tmp_path):
    adapter = IBKRAdapter()
    monkeypatch.setattr(adapter, "_log_dir", str(tmp_path))
    assert adapter._log_dir == str(tmp_path), "Monkeypatch did not update '_log_dir' correctly"


def test_trust_startup_broker_snapshot_realigns_baseline(monkeypatch):
    monkeypatch.setenv("IBKR_TRUST_STARTUP_BROKER_SNAPSHOT", "1")
    adapter = IBKRAdapter(default_account_id="DU123456")

    adapter._startup_live_positions = {
        "DU123456": {
            "USD:AAPL": 1.0,
            "USD:AMD": 40.0,
        }
    }
    adapter._broker_position_snapshots = {
        "USD:AAPL": {"quantity": 1.0, "avg_cost": 254.33},
        "USD:AMD": {"quantity": 40.0, "avg_cost": 419.03},
    }
    adapter._expected_wal_positions = {
        "DU123456": {
            "USD:AMD": 30.0,
            "USD:MSFT": 5.0,
        }
    }
    adapter.positions_dict = {
        "AMD": Position(
            symbol="AMD",
            quantity=30.0,
            avg_entry_price=419.03,
            current_price=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        ),
        "MSFT": Position(
            symbol="MSFT",
            quantity=5.0,
            avg_entry_price=100.0,
            current_price=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        ),
    }

    adapter._apply_startup_broker_snapshot_baseline()
    adapter._validate_startup_recovery_state()

    assert adapter._expected_wal_positions == {
        "DU123456": {
            "USD:AAPL": 1.0,
            "USD:AMD": 40.0,
        }
    }
    assert adapter.positions_dict["AAPL"].quantity == 1.0
    assert adapter.positions_dict["AMD"].quantity == 40.0
    assert "MSFT" not in adapter.positions_dict