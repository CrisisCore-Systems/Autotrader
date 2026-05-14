import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from examples.runners.run_pennyhunter_paper import PennyHunterPaperTrader


def build_test_trader(history_file: Path) -> PennyHunterPaperTrader:
    trader = PennyHunterPaperTrader.__new__(PennyHunterPaperTrader)
    trader.account_size = 200.0
    trader.results_history_file = history_file
    trader.ticker_cooldown_config = {
        'enabled': True,
        'mode': 'next_session_prefer_alternate',
    }
    trader.trades_log = [
        {
            'ticker': 'SPCE',
            'status': 'closed',
            'entry_time': '2026-05-13T15:30:00',
            'exit_time': '2026-05-13T20:00:00',
            'exit_reason': 'STOP',
            'pnl': -4.91,
            'signal_id': 'SPCE_2026-04-06_runner_vwap',
        }
    ]
    trader.rejected_signals = []
    trader.scan_diagnostics = []
    trader.cooldown_decisions = []
    trader.active_positions = {}
    trader.memory_enabled = False
    trader.record_trade_outcome = lambda trade: None
    trader._append_session_history = lambda report: None
    trader.broker = SimpleNamespace(
        get_account=lambda: SimpleNamespace(
            cash=200.0,
            portfolio_value=200.0,
        )
    )
    return trader


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        output_path = temp_root / 'cooldown_report.json'
        history_path = temp_root / 'cooldown_history.json'

        trader = build_test_trader(history_path)
        signals = [
            {
                'ticker': 'SPCE',
                'signal_type': 'runner_vwap',
                'price': 3.07,
                'date': '2026-04-06',
            },
            {
                'ticker': 'TLRY',
                'signal_type': 'runner_vwap',
                'price': 9.18,
                'date': '2026-01-09',
            },
        ]

        selected = trader.apply_ticker_cooldown(signals)

        assert [signal['ticker'] for signal in selected] == ['TLRY'], selected
        assert trader.cooldown_decisions, 'cooldown_decisions should be populated'
        assert trader.cooldown_decisions[0]['blocked_ticker'] == 'SPCE'
        assert trader.cooldown_decisions[0]['decision'] == 'prefer_alternate'
        assert trader.cooldown_decisions[0]['selected_tickers'] == ['TLRY']

        trader.save_results(str(output_path))

        written = json.loads(output_path.read_text(encoding='utf-8'))
        written_decisions = written.get('cooldown_decisions', [])
        assert written_decisions, 'cooldown_decisions should be written to output'
        assert written_decisions[0]['blocked_ticker'] == 'SPCE'
        assert written_decisions[0]['selected_tickers'] == ['TLRY']

        print(
            json.dumps(
                {
                    'selected_tickers': [signal['ticker'] for signal in selected],
                    'cooldown_decisions': written_decisions,
                    'output_path': str(output_path),
                },
                indent=2,
            )
        )


if __name__ == '__main__':
    main()