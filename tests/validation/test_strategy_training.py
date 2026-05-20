import json
from collections import deque
from types import SimpleNamespace

import pytest
import pandas as pd

from autotrader.backtesting.engine.historical import SimulationRunSummary, SimulationTraceEvent
from autotrader.strategy.bars import TickToBarAggregator
from autotrader.strategy.pipeline import LiveStrategyPipeline
from autotrader.strategy.train import CandidateDiagnostics, EnvironmentEvaluation, StrategyTrainer


class _RouterWithoutAdapter:
    pass


def test_pipeline_loads_alpha_config_from_json(tmp_path):
    config_path = tmp_path / "live_alpha_weights.json"
    config_path.write_text(
        json.dumps(
            {
                "spread_mode": "absolute",
                "spread_threshold": -1.25,
                "max_spread_bps": 1.5,
                "imbalance_cutoff": 0.61,
                "imbalance_velocity_lookback": 7,
                "imbalance_velocity_threshold": 0.03,
                "latency_window": 7,
                "spread_window": 40,
                "signal_quantity": 25,
            }
        ),
        encoding="utf-8",
    )

    pipeline = LiveStrategyPipeline(
        router=_RouterWithoutAdapter(),
        target_accounts=["SIM"],
        config_path=str(config_path),
    )

    assert pipeline.spread_mode == "absolute"
    assert pipeline.spread_threshold == -1.25
    assert pipeline.max_spread_bps == 1.5
    assert pipeline.imbalance_cutoff == 0.61
    assert pipeline.imbalance_velocity_lookback == 7
    assert pipeline.imbalance_velocity_threshold == 0.03
    assert pipeline.latency_window == 7
    assert pipeline.spread_window == 40
    assert pipeline.signal_quantity == 25


def test_pipeline_computes_imbalance_velocity_and_applies_gate():
    pipeline = LiveStrategyPipeline(
        router=_RouterWithoutAdapter(),
        target_accounts=["SIM"],
        imbalance_cutoff=0.7,
        imbalance_velocity_lookback=2,
        imbalance_velocity_threshold=0.2,
        spread_threshold=1.0,
    )

    assert pipeline.generate_signal_from_quote("EUR/USD", 1.0, 1.0002, 100.0, 100.0) is None
    assert pipeline.generate_signal_from_quote("EUR/USD", 1.0, 1.0002, 150.0, 100.0) is None

    signal = pipeline.generate_signal_from_quote("EUR/USD", 1.0, 1.0002, 350.0, 100.0)

    assert signal is not None
    assert signal["side"] == "BUY"
    assert signal["features"]["imbalance_velocity"] > 0.2


def test_pipeline_absolute_spread_gate_rejects_and_admits_by_bps():
    pipeline = LiveStrategyPipeline(
        router=_RouterWithoutAdapter(),
        target_accounts=["SIM"],
        spread_mode="absolute",
        max_spread_bps=1.5,
        imbalance_cutoff=0.7,
        imbalance_velocity_lookback=1,
        imbalance_velocity_threshold=0.0,
    )

    assert pipeline.generate_signal_from_quote("EUR/USD", 1.0, 1.0003, 350.0, 100.0) is None

    admit_pipeline = LiveStrategyPipeline(
        router=_RouterWithoutAdapter(),
        target_accounts=["SIM"],
        spread_mode="absolute",
        max_spread_bps=1.5,
        imbalance_cutoff=0.7,
        imbalance_velocity_lookback=1,
        imbalance_velocity_threshold=0.0,
    )

    signal = admit_pipeline.generate_signal_from_quote("EUR/USD", 1.0, 1.0001, 350.0, 100.0)

    assert signal is not None
    assert signal["features"]["spread_bps"] == pytest.approx(0.99995, rel=1e-4)


def test_strategy_trainer_absolute_mode_requires_max_spread_bps():
    with pytest.raises(ValueError, match="max_spread_bps"):
        StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD", spread_mode="absolute")


def test_strategy_trainer_bar_gate_only_allows_first_quote_after_bar_close():
    trainer = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD", bar_frequency="1m")
    aggregator = TickToBarAggregator("1m")

    first_event = SimpleNamespace(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:10Z"),
        bid=1.0850,
        ask=1.0852,
        bid_size=100.0,
        ask_size=80.0,
    )
    second_event = SimpleNamespace(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:00:50Z"),
        bid=1.0851,
        ask=1.0853,
        bid_size=120.0,
        ask_size=90.0,
    )
    third_event = SimpleNamespace(
        symbol="EUR/USD",
        timestamp=pd.Timestamp("2024-10-21T12:01:05Z"),
        bid=1.0852,
        ask=1.0854,
        bid_size=140.0,
        ask_size=110.0,
    )

    assert trainer._bar_gate_allows_event(aggregator, first_event) == (False, [])
    assert trainer._bar_gate_allows_event(aggregator, second_event) == (False, [])

    allowed, finalized_bars = trainer._bar_gate_allows_event(aggregator, third_event)

    assert allowed is True
    assert len(finalized_bars) == 1


def test_strategy_trainer_builds_bar_derived_signal_state_from_finalized_bars():
    trainer = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD", bar_frequency="1m")

    ema_state_by_symbol = {"EUR/USD": {"fast": None, "slow": None}}
    bar_mid_history = {"EUR/USD": deque()}
    bar_imbalance_history = {"EUR/USD": deque()}
    finalized_bars = [
        {
            "symbol": "EUR/USD",
            "mid_close": 1.1000,
            "volume_proxy": 200.0,
            "ofi_bar": 40.0,
        },
        {
            "symbol": "EUR/USD",
            "mid_close": 1.1010,
            "volume_proxy": 200.0,
            "ofi_bar": -20.0,
        },
    ]

    signal_state = trainer._apply_finalized_bar_state(
        finalized_bars=finalized_bars,
        symbol="EUR/USD",
        ema_state_by_symbol=ema_state_by_symbol,
        bar_mid_history=bar_mid_history,
        bar_imbalance_history=bar_imbalance_history,
        latency_window=5,
        imbalance_velocity_lookback=5,
        fast_ema_len=10,
        slow_ema_len=22,
    )

    assert signal_state is not None
    assert signal_state["mid"] == pytest.approx(1.1010)
    assert signal_state["latency_mid"] == pytest.approx(1.1000)
    assert signal_state["imbalance_ratio"] == pytest.approx(0.45)
    assert signal_state["imbalance_velocity"] == pytest.approx(0.05)
    assert signal_state["fast_ema"] > signal_state["slow_ema"]


@pytest.mark.asyncio
async def test_strategy_trainer_writes_best_alpha_weights(tmp_path, monkeypatch):
    output_path = tmp_path / "live_alpha_weights.json"
    trainer = StrategyTrainer(
        dataset_glob="ignored.parquet",
        symbol="AMD",
        output_path=str(output_path),
        spread_thresholds=[-1.0, -0.5],
        imbalance_cutoffs=[0.55, 0.60],
        fast_ema_lengths=[5, 10],
        slow_ema_lengths=[20],
        min_trend_separation_bps_values=[0.0, 1.0],
        imbalance_velocity_lookbacks=[5],
        imbalance_velocity_thresholds=[0.01, 0.05],
        min_trades=3,
        missing_trade_penalty=25.0,
    )

    async def _fake_evaluate_parameters(
        self,
        spread_threshold,
        imbalance_cutoff,
        fast_ema_len,
        slow_ema_len,
        min_trend_separation_bps,
        imbalance_velocity_lookback,
        imbalance_velocity_threshold,
    ):
        baseline = EnvironmentEvaluation(
            net_return=float(
                100.0
                + (spread_threshold * 10.0)
                + (imbalance_cutoff * 20.0)
                + (fast_ema_len * 0.5)
                - (slow_ema_len * 0.1)
                - (min_trend_separation_bps * 5.0)
                - (imbalance_velocity_threshold * 10.0)
            ),
            matched_orders=4,
            signals_processed=4,
            routed_orders=4,
            rejected_allocations=0,
            diagnostics=CandidateDiagnostics(
                quotes_seen=10,
                feature_quotes=8,
                spread_rejections=2,
                imbalance_rejections=3,
                trend_warmup_skips=1,
                trend_rejections=1,
                trend_separation_rejections=1,
                trend_velocity_rejections=1,
                passed_signals=2,
                matched_orders=4,
                pass_rate=0.25,
                dominant_kill_gate="imbalance",
                dominant_kill_rate=0.375,
            ),
        )
        stress = EnvironmentEvaluation(
            net_return=float(-10.0 if imbalance_cutoff >= 0.60 else 5.0),
            matched_orders=4,
            signals_processed=4,
            routed_orders=4,
            rejected_allocations=0,
            diagnostics=CandidateDiagnostics(
                quotes_seen=10,
                feature_quotes=8,
                spread_rejections=2,
                imbalance_rejections=3,
                trend_warmup_skips=1,
                trend_rejections=1,
                trend_separation_rejections=1,
                trend_velocity_rejections=1,
                passed_signals=2,
                matched_orders=4,
                pass_rate=0.25,
                dominant_kill_gate="imbalance",
                dominant_kill_rate=0.375,
            ),
        )
        return {"baseline": baseline, "stress_surge": stress}

    monkeypatch.setattr(StrategyTrainer, "evaluate_parameters", _fake_evaluate_parameters)

    best = await trainer.train()

    assert output_path.exists()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["spread_threshold"] == best["spread_threshold"]
    assert persisted["bar_frequency"] is None
    assert persisted["model_mode"] == "tick-relative-v1"
    assert persisted["imbalance_cutoff"] == best["imbalance_cutoff"]
    assert persisted["fitness"] == best["fitness"]
    assert persisted["fast_ema_len"] == best["fast_ema_len"]
    assert persisted["slow_ema_len"] == best["slow_ema_len"]
    assert persisted["min_trend_separation_bps"] == best["min_trend_separation_bps"]
    assert persisted["imbalance_velocity_lookback"] == best["imbalance_velocity_lookback"]
    assert persisted["imbalance_velocity_threshold"] == best["imbalance_velocity_threshold"]
    assert persisted["min_trades"] == 3
    assert persisted["missing_trade_penalty"] == 25.0
    assert persisted["activity_penalty"] == 0.0
    assert persisted["baseline"]["diagnostics"]["pass_rate"] == 0.25
    assert persisted["baseline"]["diagnostics"]["dominant_kill_gate"] == "imbalance"
    assert persisted["baseline"]["diagnostics"]["trend_separation_rejections"] == 1
    assert persisted["baseline"]["diagnostics"]["trend_velocity_rejections"] == 1
    assert best["imbalance_cutoff"] == 0.55
    assert best["fast_ema_len"] == 10
    assert best["slow_ema_len"] == 20
    assert best["min_trend_separation_bps"] == 0.0
    assert best["imbalance_velocity_lookback"] == 5
    assert best["imbalance_velocity_threshold"] == 0.01


def test_strategy_trainer_regime_filter_requires_side_alignment():
    assert StrategyTrainer._passes_regime_filter("BUY", fast_ema=1.2, slow_ema=1.0)
    assert not StrategyTrainer._passes_regime_filter("BUY", fast_ema=0.9, slow_ema=1.0)
    assert StrategyTrainer._passes_regime_filter("SELL", fast_ema=0.9, slow_ema=1.0)
    assert not StrategyTrainer._passes_regime_filter("SELL", fast_ema=1.2, slow_ema=1.0)


def test_strategy_trainer_requires_minimum_trend_separation():
    assert StrategyTrainer._passes_trend_separation(1.0002, 1.0, min_trend_separation_bps=1.0)
    assert not StrategyTrainer._passes_trend_separation(1.00005, 1.0, min_trend_separation_bps=1.0)


def test_strategy_trainer_requires_side_aware_imbalance_velocity():
    assert StrategyTrainer._passes_imbalance_velocity("BUY", 0.06, 0.05)
    assert not StrategyTrainer._passes_imbalance_velocity("BUY", 0.01, 0.05)
    assert StrategyTrainer._passes_imbalance_velocity("SELL", -0.06, 0.05)
    assert not StrategyTrainer._passes_imbalance_velocity("SELL", -0.01, 0.05)


def test_strategy_trainer_penalizes_underactive_candidates():
    trainer = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD", min_trades=3, missing_trade_penalty=25.0)

    environment_results = {
        "baseline": EnvironmentEvaluation(
            net_return=0.0,
            matched_orders=0,
            signals_processed=0,
            routed_orders=0,
            rejected_allocations=0,
        ),
        "stress_surge": EnvironmentEvaluation(
            net_return=0.0,
            matched_orders=0,
            signals_processed=0,
            routed_orders=0,
            rejected_allocations=0,
        ),
    }

    assert trainer._compute_activity_penalty(environment_results) == 75.0
    assert trainer.compute_fitness(environment_results) == -75.0


def test_strategy_trainer_scores_realized_position_exit_pnl_before_markout():
    trainer = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD")
    summary = SimulationRunSummary(
        symbol="AMD",
        quote_events_processed=3,
        signals_processed=1,
        matched_orders=1,
        routed_orders=1,
        rejected_allocations=0,
    )
    trace_events = [
        SimulationTraceEvent(
            event_type="ALLOCATION_MATCHED",
            timestamp=pd.Timestamp("2026-05-01T09:30:00Z"),
            payload={
                "execution_ts": "2026-05-01T09:30:00Z",
                "execution_price": 100.0,
                "quantity": 10,
                "side": "BUY",
            },
        ),
        SimulationTraceEvent(
            event_type="POSITION_EXITED",
            timestamp=pd.Timestamp("2026-05-01T09:30:01Z"),
            payload={"realized_pnl": 12.5},
        ),
    ]

    evaluation = trainer._score_run(trace_events, summary)

    assert evaluation.net_return == pytest.approx(12.5)


def test_strategy_trainer_splits_long_and_short_side_metrics_from_trace_events():
    trainer = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD")
    summary = SimulationRunSummary(
        symbol="AMD",
        quote_events_processed=4,
        signals_processed=2,
        matched_orders=2,
        routed_orders=2,
        rejected_allocations=0,
    )
    trace_events = [
        SimulationTraceEvent(
            event_type="POSITION_EXITED",
            timestamp=pd.Timestamp("2026-05-01T09:30:01Z"),
            payload={"entry_side": "BUY", "realized_pnl": 12.5},
        ),
        SimulationTraceEvent(
            event_type="POSITION_EXITED",
            timestamp=pd.Timestamp("2026-05-01T09:30:02Z"),
            payload={"entry_side": "SELL", "realized_pnl": -3.0},
        ),
    ]

    evaluation = trainer._score_run(trace_events, summary)

    assert evaluation.net_return == pytest.approx(9.5)
    assert evaluation.long_side.net_return == pytest.approx(12.5)
    assert evaluation.long_side.matched_orders == 1
    assert evaluation.short_side.net_return == pytest.approx(-3.0)
    assert evaluation.short_side.matched_orders == 1


def test_strategy_trainer_direction_gates_side_selection():
    long_only = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD", direction="long")
    short_only = StrategyTrainer(dataset_glob="ignored.parquet", symbol="AMD", direction="short")

    assert long_only._direction_allows_side("BUY")
    assert not long_only._direction_allows_side("SELL")
    assert short_only._direction_allows_side("SELL")
    assert not short_only._direction_allows_side("BUY")


def test_strategy_trainer_hour_range_filters_loaded_quotes(tmp_path):
    ticks = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2024-10-22 06:59:00"),
                pd.Timestamp("2024-10-22 07:00:00"),
                pd.Timestamp("2024-10-22 15:59:00"),
                pd.Timestamp("2024-10-22 16:00:00"),
            ],
            "symbol": ["EUR/USD", "EUR/USD", "EUR/USD", "EUR/USD"],
            "bid": [1.0850, 1.0851, 1.0852, 1.0853],
            "ask": [1.0852, 1.0853, 1.0854, 1.0855],
            "bid_vol": [1_000_000.0] * 4,
            "ask_vol": [2_000_000.0] * 4,
        }
    )
    dataset_path = tmp_path / "eurusd_ticks.parquet"
    ticks.to_parquet(dataset_path)

    trainer = StrategyTrainer(
        dataset_glob=str(dataset_path),
        symbol="EUR/USD",
        bid_size_col="bid_vol",
        ask_size_col="ask_vol",
        hour_range="7-16",
    )

    frame = trainer._load_quotes_frame()

    assert len(frame) == 2
    assert frame["timestamp"].dt.hour.tolist() == [7, 15]