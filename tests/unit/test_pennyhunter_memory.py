from pathlib import Path

from src.bouncehunter.pennyhunter_memory import PennyHunterMemory


def test_memory_schema_self_migrates_with_cooldown_columns(tmp_path: Path) -> None:
    memory = PennyHunterMemory(tmp_path / 'pennyhunter_memory.db')

    stats = memory.get_ticker_stats('UNKNOWN')
    assert stats is None

    db_info = memory.db_path
    assert db_info.exists()

    import sqlite3

    conn = sqlite3.connect(db_info)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ticker_stats)").fetchall()}
    finally:
        conn.close()

    assert 'last_exit_reason' in columns
    assert 'last_closed_session' in columns
    assert 'cooldown_until_session' in columns


def test_should_trade_ticker_preserves_default_allow_behavior(tmp_path: Path) -> None:
    memory = PennyHunterMemory(tmp_path / 'pennyhunter_memory.db')

    check = memory.should_trade_ticker('FRESH')
    assert check['allowed'] is True
    assert check['stats'] is None


def test_set_and_get_ticker_cooldown_round_trip(tmp_path: Path) -> None:
    memory = PennyHunterMemory(tmp_path / 'pennyhunter_memory.db')
    memory.set_ticker_cooldown(
        ticker='TLRY',
        exit_reason='STOP',
        closed_session=10,
        cooldown_until_session=13,
    )

    blocked = memory.get_ticker_cooldown('TLRY', current_session=11)
    assert blocked['active'] is True
    assert blocked['trigger_reason'] == 'STOP'
    assert blocked['last_closed_session'] == 10
    assert blocked['blocked_until'] == 13
    assert blocked['unlock_at'] == 14

    unlocked = memory.get_ticker_cooldown('TLRY', current_session=14)
    assert unlocked['active'] is False
    assert unlocked['blocked_until'] == 13
