import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from examples.runners.run_pennyhunter_paper import (
    PennyHunterPaperTrader,
    load_config_file,
    load_tickers_from_file,
)


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


def run_case(name: str, signals: list[dict], expected_tickers: list[str], expected_decision: str) -> dict:
    temp_root = Path(tempfile.mkdtemp(prefix=f'{name}_'))
    output_path = temp_root / 'cooldown_report.json'
    history_path = temp_root / 'cooldown_history.json'

    trader = build_test_trader(history_path)
    selected = trader.apply_ticker_cooldown(signals)

    assert [signal['ticker'] for signal in selected] == expected_tickers, selected
    assert trader.cooldown_decisions, f'{name}: cooldown_decisions should be populated'
    assert trader.cooldown_decisions[0]['blocked_ticker'] == 'SPCE'
    assert trader.cooldown_decisions[0]['decision'] == expected_decision
    assert trader.cooldown_decisions[0]['selected_tickers'] == expected_tickers

    trader.save_results(str(output_path))

    written = json.loads(output_path.read_text(encoding='utf-8'))
    written_decisions = written.get('cooldown_decisions', [])
    assert written_decisions, f'{name}: cooldown_decisions should be written to output'
    assert written_decisions[0]['blocked_ticker'] == 'SPCE'
    assert written_decisions[0]['decision'] == expected_decision
    assert written_decisions[0]['selected_tickers'] == expected_tickers

    return {
        'selected_tickers': [signal['ticker'] for signal in selected],
        'cooldown_decisions': written_decisions,
        'output_path': str(output_path),
    }


def gather_tickers(cfg: dict) -> list[str]:
    tickers: list[str] = []
    primary = PROJECT_ROOT / 'configs' / 'active_pennies.txt'
    if primary.exists():
        tickers.extend(load_tickers_from_file(primary))

    cfg_ticker_file = cfg.get('universe', {}).get('ticker_file')
    if cfg_ticker_file:
        path = Path(cfg_ticker_file)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        if path.exists():
            tickers.extend(load_tickers_from_file(path))

    deduped: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        if ticker not in seen:
            seen.add(ticker)
            deduped.append(ticker)
    return deduped


def run_head_artifact_case() -> dict:
    config = load_config_file(PROJECT_ROOT / 'configs' / 'pennyhunter_experiment_gap10_vol2_5_cooldown.yaml')
    trader = PennyHunterPaperTrader(
        config,
        account_size=200.0,
        max_risk_per_trade=5.0,
        history_file=PROJECT_ROOT / 'reports' / 'experiments' / 'gap10_vol2_5_cooldown' / 'pennyhunter_cumulative_history.json',
        penny_memory_db=PROJECT_ROOT / 'reports' / 'experiments' / 'gap10_vol2_5_cooldown' / 'pennyhunter_memory.db',
        agent_memory_db=PROJECT_ROOT / 'reports' / 'experiments' / 'gap10_vol2_5_cooldown' / 'bouncehunter_agent.db',
    )
    output_path = PROJECT_ROOT / 'reports' / 'experiments' / 'gap10_vol2_5_cooldown' / 'pennyhunter_paper_trades.json'
    trader.load_existing_results(str(output_path))
    trader.reconcile_active_positions()
    trader.reconcile_cumulative_history()
    pending = trader._pending_cooldown_trade()
    signals_before = trader.scan_for_signals(gather_tickers(config))
    signals_after = trader.apply_ticker_cooldown(signals_before)

    signal_tickers = [signal['ticker'] for signal in signals_before]
    filtered_tickers = [signal['ticker'] for signal in signals_after]

    assert pending is not None, 'HEAD artifact case should detect the just-closed SPCE trade'
    assert pending.get('ticker') == 'SPCE'
    if signal_tickers == ['SPCE']:
        assert filtered_tickers == [], filtered_tickers
        assert trader.cooldown_decisions, 'HEAD artifact case should record cooldown_decisions'
        assert trader.cooldown_decisions[0]['decision'] == 'skip_repeat_without_alternative'
        assert trader.cooldown_decisions[0]['reason'] == 'repeat_ticker_suppressed_no_alternate'

    return {
        'pending_cooldown_trade': pending,
        'signals_before': signal_tickers,
        'signals_after': filtered_tickers,
        'cooldown_decisions': trader.cooldown_decisions,
    }


def main() -> None:
    case_a = run_case(
        'case_a_alternate_available',
        signals=[
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
        ],
        expected_tickers=['TLRY'],
        expected_decision='prefer_alternate',
    )

    case_b = run_case(
        'case_b_no_alternate',
        signals=[
            {
                'ticker': 'SPCE',
                'signal_type': 'runner_vwap',
                'price': 3.07,
                'date': '2026-04-06',
            },
        ],
        expected_tickers=[],
        expected_decision='skip_repeat_without_alternative',
    )

    head_artifact_case = run_head_artifact_case()

    print(json.dumps({'case_a': case_a, 'case_b': case_b, 'head_artifact_case': head_artifact_case}, indent=2, default=str))


if __name__ == '__main__':
    main()