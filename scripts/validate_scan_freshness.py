import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import examples.runners.run_pennyhunter_paper as runner
from examples.runners.run_pennyhunter_paper import PennyHunterPaperTrader


class _DummyUniverse:
    def screen(self, tickers, lookback_days=10):
        return tickers


class _DummyScorer:
    def score_runner_vwap(self, **kwargs):
        return SimpleNamespace(total_score=6.0, components={'dummy': 1.0})


class _DummyTicker:
    def __init__(self, hist):
        self._hist = hist

    def history(self, period='90d'):
        return self._hist.copy()


def _build_trader(scan_filter_config: dict):
    trader = PennyHunterPaperTrader.__new__(PennyHunterPaperTrader)
    trader.scan_diagnostics = []
    trader.cooldown_decisions = []
    trader.entry_confirmation_decisions = []
    trader.rejected_signals = []
    trader.trades_log = []
    trader.regime_snapshot = None
    trader.refresh_regime = lambda force_refresh=False: None
    trader.ticker_blocklist = []
    trader.universe = _DummyUniverse()
    trader.scorer = _DummyScorer()
    trader.scan_filter_config = scan_filter_config
    trader.ticker_cooldown_config = {'enabled': False, 'mode': 'next_session_prefer_alternate'}
    trader.entry_confirmation_config = {'enabled': True, 'max_signal_age_days': 2}
    return trader


def _build_hist_with_stale_qualifying_bar():
    index = pd.to_datetime(
        [
            '2026-05-10',
            '2026-05-11',
            '2026-05-12',
            '2026-05-13',
            '2026-05-14',
        ]
    )

    # The newest qualifying bar is 2026-05-11 (gap ~10.9%, vol spike 3x),
    # making it stale relative to 2026-05-14 when max_signal_age_days=2.
    return pd.DataFrame(
        {
            'Open': [10.0, 11.2, 9.6, 9.7, 9.8],
            'High': [10.2, 11.4, 9.8, 9.9, 10.0],
            'Low': [9.7, 10.9, 9.4, 9.5, 9.6],
            'Close': [10.1, 11.1, 9.5, 9.8, 9.9],
            'Volume': [1000, 3000, 900, 800, 850],
        },
        index=index,
    )


def run_default_behavior_case(hist):
    trader = _build_trader(
        {
            'gap_min_pct': 10.0,
            'gap_max_pct': 15.0,
            'volume_min_mult': 2.4,
            'volume_max_mult': None,
            'allow_extreme_volume_above_mult': 15.0,
            'max_signal_age_days': None,
            'only_recent_signals': False,
        }
    )

    original_ticker = runner.yf.Ticker
    runner.yf.Ticker = lambda ticker: _DummyTicker(hist)
    try:
        signals = trader.scan_for_signals(['SPCE'])
    finally:
        runner.yf.Ticker = original_ticker

    assert len(signals) == 1, signals
    assert signals[0]['ticker'] == 'SPCE'
    assert signals[0]['date'] == '2026-05-11'
    assert not any(item.get('reason') == 'signal_too_old_scan_window' for item in trader.scan_diagnostics)
    assert trader.entry_confirmation_decisions == []

    return {
        'signals_found': [s.get('ticker') for s in signals],
        'signal_dates': [s.get('date') for s in signals],
        'scan_diagnostics': trader.scan_diagnostics,
        'entry_confirmation_decisions': trader.entry_confirmation_decisions,
    }


def run_enabled_scan_freshness_case(hist):
    trader = _build_trader(
        {
            'gap_min_pct': 10.0,
            'gap_max_pct': 15.0,
            'volume_min_mult': 2.4,
            'volume_max_mult': None,
            'allow_extreme_volume_above_mult': 15.0,
            'max_signal_age_days': 2,
            'only_recent_signals': True,
        }
    )

    original_ticker = runner.yf.Ticker
    runner.yf.Ticker = lambda ticker: _DummyTicker(hist)
    try:
        signals = trader.scan_for_signals(['TLRY'])
    finally:
        runner.yf.Ticker = original_ticker

    assert signals == [], signals
    assert trader.scan_diagnostics, 'scan diagnostics should capture stale-signal rejection'
    diag = trader.scan_diagnostics[0]
    assert diag['ticker'] == 'TLRY'
    assert diag['reason'] == 'signal_too_old_scan_window'
    assert diag['signal_age_days'] == 3
    assert diag['max_signal_age_days'] == 2
    assert trader.entry_confirmation_decisions == []

    return {
        'signals_found': [s.get('ticker') for s in signals],
        'scan_diagnostics': trader.scan_diagnostics,
        'entry_confirmation_decisions': trader.entry_confirmation_decisions,
    }


def main() -> None:
    hist = _build_hist_with_stale_qualifying_bar()
    default_case = run_default_behavior_case(hist)
    enabled_case = run_enabled_scan_freshness_case(hist)

    print(
        json.dumps(
            {
                'default_behavior_preserved': default_case,
                'scan_freshness_enabled_rejects_stale': enabled_case,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == '__main__':
    main()
