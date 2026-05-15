import json
from pathlib import Path

import pytest

from examples.runners.run_pennyhunter_paper import PennyHunterPaperTrader
from src.bouncehunter.pennyhunter_memory import PennyHunterMemory


def write_history(path: Path, total_sessions: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                'first_trade_date': None,
                'last_updated': None,
                'total_sessions': total_sessions,
                'trades': [],
                'metadata': {},
            }
        ),
        encoding='utf-8',
    )


def build_minimal_trader(tmp_path: Path, total_sessions: int, history_name: str = 'history.json') -> PennyHunterPaperTrader:
    history_path = tmp_path / history_name
    write_history(history_path, total_sessions)

    trader = PennyHunterPaperTrader.__new__(PennyHunterPaperTrader)
    trader.results_history_file = history_path
    trader.ticker_cooldown_config = {
        'enabled': True,
        'mode': 'session_based',
        'sessions_by_exit_reason': {
            'profit': 1,
            'stop': 3,
            'manual': 5,
        },
    }
    trader.memory_enabled = True
    trader.memory = PennyHunterMemory(tmp_path / 'pennyhunter_memory.db')
    trader.rejected_signals = []
    trader.cooldown_decisions = []
    trader.scan_diagnostics = []
    trader._record_phase25_outcome = lambda trade: None
    return trader


@pytest.mark.parametrize(
    ('exit_reason', 'won', 'expected_until'),
    [
        ('TARGET', True, 11),
        ('STOP', False, 13),
        ('MANUAL', False, 15),
    ],
)
def test_cooldown_mapping_by_exit_reason(tmp_path: Path, exit_reason: str, won: bool, expected_until: int) -> None:
    trader = build_minimal_trader(tmp_path, total_sessions=9)
    trade = {
        'ticker': 'TLRY',
        'pnl': 5.0 if won else -5.0,
        'exit_reason': exit_reason,
        'exit_time': '2026-05-14T20:00:00',
        'entry_time': '2026-05-14T15:30:00',
        'signal_id': f'TLRY_2026-05-14_{exit_reason.lower()}',
        'signal_date': '2026-05-14',
        'entry_price': 4.5,
        'shares': 100,
    }

    trader.record_trade_outcome(trade)

    cooldown = trader.memory.get_ticker_cooldown('TLRY', current_session=10)
    assert cooldown['trigger_reason'] == exit_reason
    assert cooldown['last_closed_session'] == 10
    assert cooldown['blocked_until'] == expected_until


def test_stop_cooldown_blocks_until_session_boundary_then_unlocks(tmp_path: Path) -> None:
    trader = build_minimal_trader(tmp_path, total_sessions=9, history_name='history_session_10.json')
    trade = {
        'ticker': 'TLRY',
        'pnl': -4.91,
        'exit_reason': 'STOP',
        'exit_time': '2026-05-14T20:00:00',
        'entry_time': '2026-05-14T15:30:00',
        'signal_id': 'TLRY_2026-05-14_runner_vwap',
        'signal_date': '2026-05-14',
        'entry_price': 4.5,
        'shares': 100,
    }

    trader.record_trade_outcome(trade)

    session_11 = build_minimal_trader(tmp_path, total_sessions=10, history_name='history_session_11.json')

    signals = [
        {'ticker': 'TLRY', 'signal_type': 'runner_vwap', 'date': '2026-05-15'},
        {'ticker': 'SPCE', 'signal_type': 'runner_vwap', 'date': '2026-05-15'},
    ]

    filtered_11 = session_11._apply_persistent_ticker_cooldown([dict(signal) for signal in signals])
    assert [signal['ticker'] for signal in filtered_11] == ['SPCE']
    assert session_11.cooldown_decisions[0]['reason'] == 'cooldown_active'
    assert session_11.cooldown_decisions[0]['blocked_until'] == 13
    assert session_11.cooldown_decisions[0]['unlock_at'] == 14
    assert session_11.cooldown_decisions[0]['current_session'] == 11

    session_13 = build_minimal_trader(tmp_path, total_sessions=12, history_name='history_session_13.json')
    filtered_13 = session_13._apply_persistent_ticker_cooldown([{'ticker': 'TLRY', 'signal_type': 'runner_vwap'}])
    assert filtered_13 == []
    assert session_13.cooldown_decisions[0]['current_session'] == 13

    session_14 = build_minimal_trader(tmp_path, total_sessions=13, history_name='history_session_14.json')
    filtered_14 = session_14._apply_persistent_ticker_cooldown([{'ticker': 'TLRY', 'signal_type': 'runner_vwap'}])
    assert [signal['ticker'] for signal in filtered_14] == ['TLRY']
    assert session_14.cooldown_decisions == []