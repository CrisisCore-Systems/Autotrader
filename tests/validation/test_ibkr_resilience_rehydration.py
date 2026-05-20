import pytest

from autotrader.execution.adapters.ibkr import IBKRAdapter

@pytest.fixture
def mock_wal_file(tmp_path):
    wal_content = """
    {"type": "EXEC", "account_id": "U1111111", "symbol": "AAPL", "quantity": 100, "perm_id": 12345}
    {"type": "EXEC", "account_id": "U1111111", "symbol": "AAPL", "quantity": -50, "perm_id": 12346}
    {"type": "SHORTFALL", "account_id": "U1111111", "symbol": "AAPL", "shortfall": -10}
    {"type": "EXEC", "account_id": "U2222222", "symbol": "GOOG", "quantity": 200, "perm_id": 22345}
    {"type": "SHORTFALL", "account_id": "U2222222", "symbol": "GOOG", "shortfall": -20}
    """
    wal_file = tmp_path / "execution_wal.log"
    wal_file.write_text(wal_content)
    return wal_file

def test_rehydrate_and_repair(mock_wal_file, monkeypatch):
    adapter = IBKRAdapter()

    # Mock the log directory to point to the temporary path
    monkeypatch.setattr(adapter, "_log_dir", str(mock_wal_file.parent))

    # Call the rehydrate_and_repair method
    adapter.rehydrate_and_repair()

    # Validate expected positions
    expected_positions = {
        "U1111111": {"AAPL": 40},
        "U2222222": {"GOOG": 180},
    }
    assert adapter._expected_wal_positions == expected_positions

    # Validate active perm IDs
    expected_perm_ids = {12345, 12346, 22345}
    assert adapter._expected_active_perm_ids == expected_perm_ids

def test_adapter_initialization():
    """
    Test that the IBKRAdapter initializes with the correct default log directory.
    """
    adapter = IBKRAdapter()
    print("Adapter initialized.")
    assert hasattr(adapter, "_log_dir"), "Adapter should have a '_log_dir' attribute"
    assert adapter._log_dir == "logs", "Default log directory should be 'logs'"

def test_monkeypatch_log_dir(monkeypatch, tmp_path):
    adapter = IBKRAdapter()

    # Mock the log directory
    monkeypatch.setattr(adapter, "_log_dir", str(tmp_path))

    # Verify the log directory is updated
    assert adapter._log_dir == str(tmp_path), "Monkeypatch did not update _log_dir correctly"