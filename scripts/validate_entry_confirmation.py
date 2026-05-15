import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from examples.runners.run_pennyhunter_paper import PennyHunterPaperTrader


class _DummyOrder:
    def __init__(self, order_id: str):
        self.order_id = order_id


class _DummyBroker:
    def place_bracket_order(self, ticker: str, quantity: int, entry_price: float, stop_price: float, target_price: float):
        return {
            'entry': _DummyOrder(f'entry-{ticker}'),
            'stop': _DummyOrder(f'stop-{ticker}'),
            'target': _DummyOrder(f'target-{ticker}'),
        }

    def get_account(self):
        return SimpleNamespace(cash=200.0, portfolio_value=200.0)


def build_test_trader(entry_confirmation_config: dict, history_file: Path) -> PennyHunterPaperTrader:
    trader = PennyHunterPaperTrader.__new__(PennyHunterPaperTrader)
    trader.account_size = 200.0
    trader.results_history_file = history_file
    trader.memory_enabled = False
    trader.advanced_filters_enabled = False
    trader.entry_confirmation_config = entry_confirmation_config
    trader.rejected_signals = []
    trader.scan_diagnostics = []
    trader.cooldown_decisions = []
    trader.entry_confirmation_decisions = []
    trader.active_positions = {}
    trader.trades_log = []
    trader.base_risk_per_trade = 5.0
    trader.current_risk_per_trade = 5.0
    trader.regime_snapshot = None
    trader.broker = _DummyBroker()
    trader._append_session_history = lambda report: None
    trader._record_phase25_signal = lambda signal, trade: None
    return trader


def make_signal(signal_date: str) -> dict:
    hist_index = pd.to_datetime(['2026-01-09', '2026-01-12', '2026-01-13', '2026-01-14'])
    hist = pd.DataFrame(
        {
            'Open': [8.8, 8.9, 9.0, 9.1],
            'High': [9.2, 9.3, 9.4, 9.5],
            'Low': [8.6, 8.7, 8.8, 8.9],
            'Close': [9.18, 9.0, 9.1, 9.2],
            'Volume': [1000000, 1200000, 1100000, 1300000],
        },
        index=hist_index,
    )
    return {
        'ticker': 'TLRY',
        'signal_type': 'runner_vwap',
        'price': 9.18,
        'gap_pct': 10.08,
        'vol_spike': 2.4,
        'score': 5.0,
        'date': signal_date,
        'hist': hist,
    }


def run_disabled_case() -> dict:
    temp_root = Path(tempfile.mkdtemp(prefix='entry_confirmation_disabled_'))
    trader = build_test_trader({'enabled': False, 'max_signal_age_days': 10}, temp_root / 'history.json')
    signal = make_signal('2026-01-09')

    executed = trader.execute_signal(signal)
    assert executed is True
    assert len(trader.trades_log) == 1
    assert trader.entry_confirmation_decisions == []
    assert trader.rejected_signals == []

    output_path = temp_root / 'report.json'
    trader.save_results(str(output_path))
    report = json.loads(output_path.read_text(encoding='utf-8'))
    assert report.get('entry_confirmation_decisions', []) == []

    return {
        'executed': executed,
        'trade_ticker': trader.trades_log[0]['ticker'],
        'entry_confirmation_decisions': report.get('entry_confirmation_decisions', []),
    }


def run_enabled_rejection_case() -> dict:
    temp_root = Path(tempfile.mkdtemp(prefix='entry_confirmation_enabled_'))
    trader = build_test_trader({'enabled': True, 'max_signal_age_days': 2}, temp_root / 'history.json')
    signal = make_signal('2026-01-09')

    executed = trader.execute_signal(signal)
    assert executed is False
    assert trader.trades_log == []
    assert len(trader.entry_confirmation_decisions) == 1
    assert trader.entry_confirmation_decisions[0]['reason'] == 'signal_too_old'
    assert trader.entry_confirmation_decisions[0]['max_signal_age_days'] == 2
    assert trader.rejected_signals, 'rejected signal should be recorded'
    assert trader.rejected_signals[0]['stage'] == 'entry_confirmation'

    output_path = temp_root / 'report.json'
    trader.save_results(str(output_path))
    report = json.loads(output_path.read_text(encoding='utf-8'))
    persisted_decisions = report.get('entry_confirmation_decisions', [])
    assert len(persisted_decisions) == 1
    assert persisted_decisions[0]['decision'] == 'reject'
    assert persisted_decisions[0]['reason'] == 'signal_too_old'

    return {
        'executed': executed,
        'entry_confirmation_decisions': persisted_decisions,
        'rejected_signals': report.get('rejected_signals', []),
    }


def main() -> None:
    disabled_case = run_disabled_case()
    enabled_rejection_case = run_enabled_rejection_case()
    print(
        json.dumps(
            {
                'disabled_preserves_behavior': disabled_case,
                'enabled_rejects_stale_signal': enabled_rejection_case,
                'validated_at': datetime.now().isoformat(),
            },
            indent=2,
        )
    )


if __name__ == '__main__':
    main()