from datetime import date

from examples.runners.run_pennyhunter_paper import PennyHunterPaperTrader


def build_minimal_trader(max_signal_age_days):
    trader = PennyHunterPaperTrader.__new__(PennyHunterPaperTrader)
    trader.entry_confirmation_config = {
        'enabled': True,
        'max_signal_age_days': max_signal_age_days,
    }
    trader.entry_confirmation_decisions = []
    trader.rejected_signals = []
    trader._record_rejected_signal = lambda *args, **kwargs: None
    trader._reference_market_date = lambda signal: date(2026, 5, 14)
    return trader


def test_entry_confirmation_logs_pass_when_age_rule_disabled() -> None:
    trader = build_minimal_trader(max_signal_age_days=None)

    allowed = trader._evaluate_entry_confirmation({'ticker': 'SPCE', 'date': '2026-05-13'})

    assert allowed is True
    assert len(trader.entry_confirmation_decisions) == 1
    decision = trader.entry_confirmation_decisions[0]
    assert decision['decision'] == 'pass'
    assert decision['reason'] == 'no_age_limit'


def test_entry_confirmation_logs_pass_when_signal_is_fresh() -> None:
    trader = build_minimal_trader(max_signal_age_days=1)

    allowed = trader._evaluate_entry_confirmation({'ticker': 'SPCE', 'date': '2026-05-13'})

    assert allowed is True
    assert len(trader.entry_confirmation_decisions) == 1
    decision = trader.entry_confirmation_decisions[0]
    assert decision['decision'] == 'pass'
    assert decision['reason'] == 'signal_fresh'
    assert decision['age_days'] == 1
    assert decision['max_signal_age_days'] == 1


def test_entry_confirmation_logs_reject_when_signal_is_stale() -> None:
    trader = build_minimal_trader(max_signal_age_days=0)

    allowed = trader._evaluate_entry_confirmation({'ticker': 'SPCE', 'date': '2026-05-13'})

    assert allowed is False
    assert len(trader.entry_confirmation_decisions) == 1
    decision = trader.entry_confirmation_decisions[0]
    assert decision['decision'] == 'reject'
    assert decision['reason'] == 'signal_too_old'
    assert decision['age_days'] == 1
    assert decision['max_signal_age_days'] == 0
