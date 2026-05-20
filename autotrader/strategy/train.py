from __future__ import annotations

import argparse
import asyncio
import json
import logging
import multiprocessing
from collections import defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Sequence

import pandas as pd

from autotrader.backtesting.engine.historical import (
    DuckDBHistoricalDatasetConnector,
    HistoricalQuoteEvent,
    HistoricalSimulationEngine,
    LatencyDistributionProfile,
    SimulationTraceEvent,
    SimulationRunSummary,
    StrategySignal,
)
from autotrader.strategy.bars import TickToBarAggregator
from autotrader.strategy.pipeline import LiveStrategyPipeline


logger = logging.getLogger("AutoTrader.TrainingLoop")


@dataclass(frozen=True)
class CandidateSpec:
    spread_threshold: float
    imbalance_cutoff: float
    fast_ema_len: int
    slow_ema_len: int
    min_trend_separation_bps: float
    imbalance_velocity_lookback: int
    imbalance_velocity_threshold: float


class _HourFilteredConnector:
    """Filter quote events to a UTC hour range before simulation and scoring."""

    def __init__(self, base_connector: DuckDBHistoricalDatasetConnector, start_hour: int, end_hour: int) -> None:
        self._base_connector = base_connector
        self._start_hour = int(start_hour)
        self._end_hour = int(end_hour)

    def _contains_hour(self, timestamp: pd.Timestamp) -> bool:
        normalized_ts = StrategyTrainer._normalize_timestamp(timestamp)
        hour = int(normalized_ts.hour)
        if self._start_hour <= self._end_hour:
            return self._start_hour <= hour < self._end_hour
        return hour >= self._start_hour or hour < self._end_hour

    def iter_quotes(
        self,
        symbol: str,
        *,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
        limit: Optional[int] = None,
    ):
        yielded = 0
        for event in self._base_connector.iter_quotes(symbol, start_ts=start_ts, end_ts=end_ts, limit=None):
            if not self._contains_hour(event.timestamp):
                continue
            yield event
            yielded += 1
            if limit is not None and yielded >= int(limit):
                break


@dataclass(frozen=True)
class EnvironmentEvaluation:
    net_return: float
    matched_orders: int
    signals_processed: int
    routed_orders: int
    rejected_allocations: int
    diagnostics: "CandidateDiagnostics" = field(default_factory=lambda: CandidateDiagnostics())
    long_side: "SideEnvironmentEvaluation" = field(default_factory=lambda: SideEnvironmentEvaluation())
    short_side: "SideEnvironmentEvaluation" = field(default_factory=lambda: SideEnvironmentEvaluation())


@dataclass(frozen=True)
class CandidateDiagnostics:
    quotes_seen: int = 0
    feature_quotes: int = 0
    spread_rejections: int = 0
    imbalance_rejections: int = 0
    trend_warmup_skips: int = 0
    trend_rejections: int = 0
    trend_separation_rejections: int = 0
    trend_velocity_rejections: int = 0
    passed_signals: int = 0
    matched_orders: int = 0
    pass_rate: float = 0.0
    dominant_kill_gate: str = "none"
    dominant_kill_rate: float = 0.0


@dataclass(frozen=True)
class SideEnvironmentEvaluation:
    net_return: float = 0.0
    matched_orders: int = 0
    diagnostics: "CandidateDiagnostics" = field(default_factory=lambda: CandidateDiagnostics())


class _TrainingAllocationRouter:
    """Lightweight router stub used by the historical simulator training loop."""

    def __init__(self) -> None:
        self._next_order_id = 1

    async def route_order(
        self,
        symbol: str,
        total_qty: int,
        side: str,
        policy: str,
        target_accounts: List[str],
        **kwargs: Any,
    ) -> List[str]:
        _ = (symbol, total_qty, side, policy, kwargs)
        order_ids: List[str] = []
        active_accounts = target_accounts or ["SIM"]
        for account_id in active_accounts:
            order_ids.append(f"SIM-{account_id}-{self._next_order_id}")
            self._next_order_id += 1
        return order_ids


def _evaluate_candidate_worker(payload: Dict[str, Any]) -> Dict[str, Any]:
    trainer = StrategyTrainer(**payload["trainer_kwargs"])
    candidate = CandidateSpec(**payload["candidate"])
    return asyncio.run(trainer._evaluate_candidate(candidate))


class StrategyTrainer:
    DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "configs" / "live_alpha_weights.json"

    def __init__(
        self,
        dataset_glob: str,
        *,
        symbol: str,
        target_accounts: Optional[List[str]] = None,
        policy: str = "DYNAMIC_NLV",
        output_path: Optional[str] = None,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None,
        limit: Optional[int] = None,
        markout_ns: int = 5_000_000_000,
        size_penalty_bps_per_excess_ratio: float = 15.0,
        spread_mode: str = "relative",
        spread_thresholds: Optional[Sequence[float]] = None,
        max_spread_bps: Optional[float] = None,
        bar_frequency: Optional[str] = None,
        imbalance_cutoffs: Optional[Sequence[float]] = None,
        fast_ema_lengths: Optional[Sequence[int]] = None,
        slow_ema_lengths: Optional[Sequence[int]] = None,
        min_trend_separation_bps_values: Optional[Sequence[float]] = None,
        imbalance_velocity_lookbacks: Optional[Sequence[int]] = None,
        imbalance_velocity_thresholds: Optional[Sequence[float]] = None,
        min_trades: int = 3,
        missing_trade_penalty: float = 25.0,
        signal_quantity: int = 10,
        latency_window: int = 5,
        spread_window: int = 32,
        resiliency_penalty_lambda: float = 2.0,
        timestamp_col: str = "timestamp",
        symbol_col: str = "symbol",
        bid_col: str = "bid",
        ask_col: str = "ask",
        bid_size_col: Optional[str] = "bid_size",
        ask_size_col: Optional[str] = "ask_size",
        hour_range: Optional[str] = None,
        exit_time_decay_ticks: Optional[int] = None,
        exit_trailing_vol_multiplier: Optional[float] = None,
        exit_vol_lookback_ticks: int = 32,
        direction: str = "both",
        max_workers: int = 1,
    ) -> None:
        self.dataset_glob = dataset_glob
        self.symbol = str(symbol)
        self.target_accounts = list(target_accounts or ["SIM"])
        self.policy = str(policy)
        self.output_path = Path(output_path) if output_path else self.DEFAULT_OUTPUT_PATH
        self.start_ts = pd.Timestamp(start_ts) if start_ts else None
        self.end_ts = pd.Timestamp(end_ts) if end_ts else None
        self.limit = limit
        self.markout_ns = int(markout_ns)
        self.size_penalty_bps_per_excess_ratio = float(size_penalty_bps_per_excess_ratio)
        self.spread_mode = self._normalize_spread_mode(spread_mode)
        self.spread_thresholds = list(spread_thresholds or [-0.5, 0.0, 0.5, 1.0])
        self.max_spread_bps = float(max_spread_bps) if max_spread_bps is not None else None
        if self.spread_mode == "absolute" and self.max_spread_bps is None:
            raise ValueError("max_spread_bps is required when spread_mode is absolute")
        self.bar_frequency = self._normalize_bar_frequency(bar_frequency)
        self.imbalance_cutoffs = list(imbalance_cutoffs or [0.55, 0.65, 0.75, 0.85])
        self.fast_ema_lengths = [int(value) for value in (fast_ema_lengths or [5, 10, 20])]
        self.slow_ema_lengths = [int(value) for value in (slow_ema_lengths or [20, 50, 100])]
        self.min_trend_separation_bps_values = [
            float(value) for value in (min_trend_separation_bps_values or [0.0, 0.5, 1.0])
        ]
        self.imbalance_velocity_lookbacks = [int(value) for value in (imbalance_velocity_lookbacks or [5, 10, 20])]
        self.imbalance_velocity_thresholds = [
            float(value) for value in (imbalance_velocity_thresholds or [0.01, 0.05, 0.10])
        ]
        self.min_trades = max(0, int(min_trades))
        self.missing_trade_penalty = max(0.0, float(missing_trade_penalty))
        self.signal_quantity = int(signal_quantity)
        self.latency_window = int(latency_window)
        self.spread_window = int(spread_window)
        self.resiliency_penalty_lambda = float(resiliency_penalty_lambda)
        self.connector_kwargs = {
            "timestamp_col": timestamp_col,
            "symbol_col": symbol_col,
            "bid_col": bid_col,
            "ask_col": ask_col,
            "bid_size_col": bid_size_col,
            "ask_size_col": ask_size_col,
        }
        self.hour_range = self._parse_hour_range(hour_range)
        self.exit_time_decay_ticks = int(exit_time_decay_ticks) if exit_time_decay_ticks is not None else None
        self.exit_trailing_vol_multiplier = (
            float(exit_trailing_vol_multiplier) if exit_trailing_vol_multiplier is not None else None
        )
        self.exit_vol_lookback_ticks = max(2, int(exit_vol_lookback_ticks))
        self.direction = self._normalize_direction(direction)
        self.max_workers = max(1, int(max_workers))
        self._quotes_frame: Optional[pd.DataFrame] = None

    def _uses_dynamic_exits(self) -> bool:
        return self.exit_time_decay_ticks is not None or self.exit_trailing_vol_multiplier is not None

    @staticmethod
    def _normalize_timestamp(value: Any) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    @staticmethod
    def _parse_hour_range(raw: Optional[str]) -> Optional[tuple[int, int]]:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        if "-" not in text:
            raise ValueError("hour_range must use start-end format, for example 7-16")
        start_text, end_text = text.split("-", 1)
        start_hour = int(start_text.strip())
        end_hour = int(end_text.strip())
        if not 0 <= start_hour <= 23 or not 0 <= end_hour <= 23:
            raise ValueError("hour_range hours must be between 0 and 23")
        if start_hour == end_hour:
            raise ValueError("hour_range start and end hour must differ")
        return start_hour, end_hour

    @staticmethod
    def _normalize_direction(raw: str) -> str:
        normalized = str(raw).strip().lower()
        if normalized not in {"long", "short", "both"}:
            raise ValueError("direction must be one of: long, short, both")
        return normalized

    @staticmethod
    def _normalize_spread_mode(raw: str) -> str:
        normalized = str(raw).strip().lower()
        if normalized not in {"relative", "absolute"}:
            raise ValueError("spread_mode must be one of: relative, absolute")
        return normalized

    @staticmethod
    def _normalize_bar_frequency(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        normalized = str(raw).strip().lower()
        if not normalized:
            return None
        if normalized not in {"1m", "5m", "15m"}:
            raise ValueError("bar_frequency must be one of: 1m, 5m, 15m")
        return normalized

    def _model_mode(self) -> str:
        if self.bar_frequency is not None:
            return "bar-absolute-v2" if self.spread_mode == "absolute" else "bar-relative"
        if self.spread_mode == "absolute":
            return "tick-absolute-v2"
        return "tick-relative-v1"

    def _bar_gate_allows_event(
        self,
        aggregator: Optional[TickToBarAggregator],
        event: HistoricalQuoteEvent,
    ) -> tuple[bool, List[Dict[str, Any]]]:
        if aggregator is None:
            return True, []
        finalized_bars = aggregator.update(
            symbol=event.symbol,
            timestamp=event.timestamp,
            bid=event.bid,
            ask=event.ask,
            bid_size=event.bid_size,
            ask_size=event.ask_size,
        )
        return bool(finalized_bars), finalized_bars

    @staticmethod
    def _bar_signed_imbalance(bar: Dict[str, Any]) -> float:
        volume_proxy = float(bar.get("volume_proxy", 0.0) or 0.0)
        if volume_proxy <= 1e-12:
            return 0.0
        signed_imbalance = float(bar.get("ofi_bar", 0.0) or 0.0) / volume_proxy
        return float(max(-1.0, min(1.0, signed_imbalance)))

    @staticmethod
    def _bar_imbalance_ratio(bar: Dict[str, Any]) -> float:
        return float((StrategyTrainer._bar_signed_imbalance(bar) + 1.0) / 2.0)

    @staticmethod
    def _bar_latency_mid(mid_history: Deque[float]) -> float:
        mid_values = list(mid_history)
        if not mid_values:
            return 0.0
        if len(mid_values) == 1:
            return float(mid_values[-1])
        return float(sum(mid_values[:-1]) / len(mid_values[:-1]))

    @staticmethod
    def _bar_imbalance_velocity(imbalance_history: Deque[float], lookback: int) -> float:
        history_values = list(imbalance_history)
        if not history_values:
            return 0.0
        window = history_values[-max(1, int(lookback)) :]
        return float(sum(window) / len(window))

    def _apply_finalized_bar_state(
        self,
        *,
        finalized_bars: List[Dict[str, Any]],
        symbol: str,
        ema_state_by_symbol: Dict[str, Dict[str, Optional[float]]],
        bar_mid_history: Dict[str, Deque[float]],
        bar_imbalance_history: Dict[str, Deque[float]],
        latency_window: int,
        imbalance_velocity_lookback: int,
        fast_ema_len: int,
        slow_ema_len: int,
    ) -> Optional[Dict[str, float]]:
        normalized_symbol = str(symbol).upper().strip()
        symbol_ema_state = ema_state_by_symbol[normalized_symbol]
        mid_history = bar_mid_history[normalized_symbol]
        imbalance_history = bar_imbalance_history[normalized_symbol]
        latest_bar: Optional[Dict[str, Any]] = None

        for finalized_bar in finalized_bars:
            latest_bar = finalized_bar
            bar_mid_close = float(finalized_bar["mid_close"])
            symbol_ema_state["fast"] = self._update_ema(symbol_ema_state["fast"], bar_mid_close, length=int(fast_ema_len))
            symbol_ema_state["slow"] = self._update_ema(symbol_ema_state["slow"], bar_mid_close, length=int(slow_ema_len))

            mid_history.append(bar_mid_close)
            while len(mid_history) > max(2, int(latency_window)):
                mid_history.popleft()

            imbalance_history.append(self._bar_signed_imbalance(finalized_bar))
            while len(imbalance_history) > max(1, int(imbalance_velocity_lookback)):
                imbalance_history.popleft()

        if latest_bar is None:
            return None

        return {
            "imbalance_ratio": self._bar_imbalance_ratio(latest_bar),
            "imbalance_velocity": self._bar_imbalance_velocity(imbalance_history, imbalance_velocity_lookback),
            "mid": float(latest_bar["mid_close"]),
            "latency_mid": self._bar_latency_mid(mid_history),
            "fast_ema": float(symbol_ema_state["fast"] if symbol_ema_state["fast"] is not None else latest_bar["mid_close"]),
            "slow_ema": float(symbol_ema_state["slow"] if symbol_ema_state["slow"] is not None else latest_bar["mid_close"]),
        }

    def generate_degradation_profiles(self) -> Dict[str, LatencyDistributionProfile]:
        return {
            "baseline": LatencyDistributionProfile(mode="FIXED", fixed_ns=100_000, min_ns=100_000),
            "stress_surge": LatencyDistributionProfile(
                mode="NORMAL",
                mean_ns=2_500_000_000,
                std_ns=500_000_000,
                min_ns=500_000_000,
            ),
        }

    def _build_data_connector(self) -> Any:
        connector = DuckDBHistoricalDatasetConnector(self.dataset_glob, **self.connector_kwargs)
        if self.hour_range is None:
            return connector
        start_hour, end_hour = self.hour_range
        return _HourFilteredConnector(connector, start_hour, end_hour)

    def _candidate_specs(self) -> List[CandidateSpec]:
        specs: List[CandidateSpec] = []
        spread_thresholds = self.spread_thresholds if self.spread_mode == "relative" else [0.0]
        for spread_threshold in spread_thresholds:
            for imbalance_cutoff in self.imbalance_cutoffs:
                for fast_ema_len in self.fast_ema_lengths:
                    for slow_ema_len in self.slow_ema_lengths:
                        for min_trend_separation_bps in self.min_trend_separation_bps_values:
                            for imbalance_velocity_lookback in self.imbalance_velocity_lookbacks:
                                for imbalance_velocity_threshold in self.imbalance_velocity_thresholds:
                                    if int(fast_ema_len) >= int(slow_ema_len):
                                        continue
                                    specs.append(
                                        CandidateSpec(
                                            spread_threshold=float(spread_threshold),
                                            imbalance_cutoff=float(imbalance_cutoff),
                                            fast_ema_len=int(fast_ema_len),
                                            slow_ema_len=int(slow_ema_len),
                                            min_trend_separation_bps=float(min_trend_separation_bps),
                                            imbalance_velocity_lookback=int(imbalance_velocity_lookback),
                                            imbalance_velocity_threshold=float(imbalance_velocity_threshold),
                                        )
                                    )
        return specs

    def _worker_trainer_kwargs(self) -> Dict[str, Any]:
        hour_range = None
        if self.hour_range is not None:
            hour_range = f"{self.hour_range[0]}-{self.hour_range[1]}"
        return {
            "dataset_glob": self.dataset_glob,
            "symbol": self.symbol,
            "target_accounts": list(self.target_accounts),
            "policy": self.policy,
            "output_path": None,
            "start_ts": self.start_ts.isoformat() if self.start_ts is not None else None,
            "end_ts": self.end_ts.isoformat() if self.end_ts is not None else None,
            "limit": self.limit,
            "markout_ns": self.markout_ns,
            "size_penalty_bps_per_excess_ratio": self.size_penalty_bps_per_excess_ratio,
            "spread_mode": self.spread_mode,
            "spread_thresholds": [0.0],
            "max_spread_bps": self.max_spread_bps,
            "bar_frequency": self.bar_frequency,
            "imbalance_cutoffs": [0.0],
            "fast_ema_lengths": [1],
            "slow_ema_lengths": [2],
            "min_trend_separation_bps_values": [0.0],
            "imbalance_velocity_lookbacks": [1],
            "imbalance_velocity_thresholds": [0.0],
            "min_trades": self.min_trades,
            "missing_trade_penalty": self.missing_trade_penalty,
            "signal_quantity": self.signal_quantity,
            "latency_window": self.latency_window,
            "spread_window": self.spread_window,
            "resiliency_penalty_lambda": self.resiliency_penalty_lambda,
            "timestamp_col": self.connector_kwargs["timestamp_col"],
            "symbol_col": self.connector_kwargs["symbol_col"],
            "bid_col": self.connector_kwargs["bid_col"],
            "ask_col": self.connector_kwargs["ask_col"],
            "bid_size_col": self.connector_kwargs["bid_size_col"],
            "ask_size_col": self.connector_kwargs["ask_size_col"],
            "hour_range": hour_range,
            "exit_time_decay_ticks": self.exit_time_decay_ticks,
            "exit_trailing_vol_multiplier": self.exit_trailing_vol_multiplier,
            "exit_vol_lookback_ticks": self.exit_vol_lookback_ticks,
            "direction": self.direction,
            "max_workers": 1,
        }

    @staticmethod
    def _side_key_from_order_side(side: str) -> Optional[str]:
        normalized_side = str(side).upper().strip()
        if normalized_side == "BUY":
            return "long"
        if normalized_side == "SELL":
            return "short"
        return None

    @staticmethod
    def _empty_raw_diagnostics() -> Dict[str, int]:
        return {
            "quotes_seen": 0,
            "feature_quotes": 0,
            "spread_rejections": 0,
            "imbalance_rejections": 0,
            "trend_warmup_skips": 0,
            "trend_rejections": 0,
            "trend_separation_rejections": 0,
            "trend_velocity_rejections": 0,
            "passed_signals": 0,
        }

    @classmethod
    def _empty_side_raw_diagnostics(cls) -> Dict[str, Dict[str, int]]:
        return {
            "long": cls._empty_raw_diagnostics(),
            "short": cls._empty_raw_diagnostics(),
        }

    def _direction_allows_side(self, side: str) -> bool:
        if self.direction == "both":
            return True
        side_key = self._side_key_from_order_side(side)
        return side_key == self.direction

    @staticmethod
    def _side_evaluation_for_key(evaluation: EnvironmentEvaluation, side_key: str) -> SideEnvironmentEvaluation:
        if side_key == "long":
            return evaluation.long_side
        return evaluation.short_side

    def _compute_side_activity_penalty(self, environment_results: Dict[str, EnvironmentEvaluation], side_key: str) -> float:
        baseline_evaluation = self._side_evaluation_for_key(environment_results["baseline"], side_key)
        missing_trades = max(0, int(self.min_trades) - int(baseline_evaluation.matched_orders))
        return float(float(self.missing_trade_penalty) * float(missing_trades))

    def _compute_side_fitness(self, environment_results: Dict[str, EnvironmentEvaluation], side_key: str) -> float:
        baseline_evaluation = self._side_evaluation_for_key(environment_results["baseline"], side_key)
        stress_evaluation = self._side_evaluation_for_key(environment_results["stress_surge"], side_key)
        resiliency_penalty = self.resiliency_penalty_lambda * abs(min(0.0, float(stress_evaluation.net_return)))
        activity_penalty = self._compute_side_activity_penalty(environment_results, side_key)
        return float(float(baseline_evaluation.net_return) - resiliency_penalty - activity_penalty)

    def _build_side_metrics(self, environment_results: Dict[str, EnvironmentEvaluation]) -> Dict[str, Dict[str, Any]]:
        side_metrics: Dict[str, Dict[str, Any]] = {}
        for side_key in ("long", "short"):
            baseline_evaluation = self._side_evaluation_for_key(environment_results["baseline"], side_key)
            stress_evaluation = self._side_evaluation_for_key(environment_results["stress_surge"], side_key)
            side_metrics[side_key] = {
                "fitness": float(self._compute_side_fitness(environment_results, side_key)),
                "activity_penalty": float(self._compute_side_activity_penalty(environment_results, side_key)),
                "baseline": asdict(baseline_evaluation),
                "stress_surge": asdict(stress_evaluation),
            }
        return side_metrics

    def _build_candidate_payload(
        self,
        candidate: CandidateSpec,
        environment_results: Dict[str, EnvironmentEvaluation],
        fitness: float,
    ) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "spread_mode": self.spread_mode,
            "spread_threshold": float(candidate.spread_threshold),
            "max_spread_bps": self.max_spread_bps,
            "bar_frequency": self.bar_frequency,
            "model_mode": self._model_mode(),
            "imbalance_cutoff": float(candidate.imbalance_cutoff),
            "fast_ema_len": int(candidate.fast_ema_len),
            "slow_ema_len": int(candidate.slow_ema_len),
            "min_trend_separation_bps": float(candidate.min_trend_separation_bps),
            "imbalance_velocity_lookback": int(candidate.imbalance_velocity_lookback),
            "imbalance_velocity_threshold": float(candidate.imbalance_velocity_threshold),
            "min_trades": int(self.min_trades),
            "missing_trade_penalty": float(self.missing_trade_penalty),
            "activity_penalty": float(self._compute_activity_penalty(environment_results)),
            "latency_window": int(self.latency_window),
            "spread_window": int(self.spread_window),
            "signal_quantity": int(self.signal_quantity),
            "resiliency_penalty_lambda": float(self.resiliency_penalty_lambda),
            "exit_time_decay_ticks": self.exit_time_decay_ticks,
            "exit_trailing_vol_multiplier": self.exit_trailing_vol_multiplier,
            "exit_vol_lookback_ticks": int(self.exit_vol_lookback_ticks),
            "fitness": float(fitness),
            "side_metrics": self._build_side_metrics(environment_results),
            "baseline": asdict(environment_results["baseline"]),
            "stress_surge": asdict(environment_results["stress_surge"]),
        }

    async def _evaluate_candidate(self, candidate: CandidateSpec) -> Dict[str, Any]:
        environment_results = await self.evaluate_parameters(
            candidate.spread_threshold,
            candidate.imbalance_cutoff,
            candidate.fast_ema_len,
            candidate.slow_ema_len,
            candidate.min_trend_separation_bps,
            candidate.imbalance_velocity_lookback,
            candidate.imbalance_velocity_threshold,
        )
        fitness = self.compute_fitness(environment_results)
        return self._build_candidate_payload(candidate, environment_results, fitness)

    def _evaluate_candidates_parallel(self, candidates: Sequence[CandidateSpec]) -> List[Dict[str, Any]]:
        requested_workers = max(1, int(self.max_workers))
        max_workers = min(requested_workers, len(candidates), max(1, (multiprocessing.cpu_count() or 1) - 1))
        logger.info("Spawning candidate grid across %d worker process(es)", max_workers)
        trainer_kwargs = self._worker_trainer_kwargs()
        worker_inputs = [{"trainer_kwargs": trainer_kwargs, "candidate": asdict(candidate)} for candidate in candidates]
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(_evaluate_candidate_worker, worker_inputs))

    def _load_quotes_frame(self) -> pd.DataFrame:
        if self._quotes_frame is not None:
            return self._quotes_frame

        connector = self._build_data_connector()
        rows = [
            {
                "timestamp": self._normalize_timestamp(event.timestamp),
                "mid": event.mid,
            }
            for event in connector.iter_quotes(
                self.symbol,
                start_ts=self.start_ts,
                end_ts=self.end_ts,
                limit=self.limit,
            )
        ]
        if not rows:
            raise RuntimeError(f"No historical quotes found for symbol={self.symbol} using dataset={self.dataset_glob}")

        frame = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        self._quotes_frame = frame
        return frame

    def _future_mid_price(self, execution_ts: pd.Timestamp) -> float:
        quotes = self._load_quotes_frame()
        target_ts = self._normalize_timestamp(execution_ts) + pd.to_timedelta(self.markout_ns, unit="ns")
        insertion = quotes["timestamp"].searchsorted(target_ts, side="left")
        index = min(int(insertion), len(quotes) - 1)
        return float(quotes.iloc[index]["mid"])

    @staticmethod
    def _ema_alpha(length: int) -> float:
        return 2.0 / (float(length) + 1.0)

    @staticmethod
    def _update_ema(previous: Optional[float], value: float, *, length: int) -> float:
        if previous is None:
            return float(value)
        alpha = StrategyTrainer._ema_alpha(length)
        return float((alpha * float(value)) + ((1.0 - alpha) * float(previous)))

    @staticmethod
    def _passes_regime_filter(side: str, fast_ema: float, slow_ema: float) -> bool:
        normalized_side = str(side).upper().strip()
        if normalized_side == "BUY":
            return fast_ema >= slow_ema
        if normalized_side == "SELL":
            return fast_ema <= slow_ema
        return False

    @staticmethod
    def _trend_separation_bps(fast_ema: float, slow_ema: float) -> float:
        baseline = abs(float(slow_ema))
        if baseline <= 1e-12:
            return 0.0
        return float(abs(float(fast_ema) - float(slow_ema)) / baseline * 10_000.0)

    @classmethod
    def _passes_trend_separation(cls, fast_ema: float, slow_ema: float, min_trend_separation_bps: float) -> bool:
        return cls._trend_separation_bps(fast_ema, slow_ema) >= float(min_trend_separation_bps)

    def _score_run(self, trace_events: List[Any], summary: SimulationRunSummary) -> EnvironmentEvaluation:
        net_return = 0.0
        side_net_returns = {"long": 0.0, "short": 0.0}
        side_matched_orders = {"long": 0, "short": 0}
        exit_events = [
            trace_event
            for trace_event in trace_events
            if getattr(trace_event, "event_type", "") == "POSITION_EXITED"
        ]
        if exit_events:
            for trace_event in exit_events:
                payload = getattr(trace_event, "payload", {})
                realized_pnl = float(payload.get("realized_pnl", 0.0))
                net_return += realized_pnl
                side_key = self._side_key_from_order_side(str(payload.get("entry_side", "")))
                if side_key is not None:
                    side_net_returns[side_key] += realized_pnl
                    side_matched_orders[side_key] += 1
            return EnvironmentEvaluation(
                net_return=float(net_return),
                matched_orders=int(summary.matched_orders),
                signals_processed=int(summary.signals_processed),
                routed_orders=int(summary.routed_orders),
                rejected_allocations=int(summary.rejected_allocations),
                long_side=SideEnvironmentEvaluation(
                    net_return=float(side_net_returns["long"]),
                    matched_orders=int(side_matched_orders["long"]),
                ),
                short_side=SideEnvironmentEvaluation(
                    net_return=float(side_net_returns["short"]),
                    matched_orders=int(side_matched_orders["short"]),
                ),
            )

        for trace_event in trace_events:
            if getattr(trace_event, "event_type", "") != "ALLOCATION_MATCHED":
                continue
            payload = getattr(trace_event, "payload", {})
            execution_ts = self._normalize_timestamp(payload["execution_ts"])
            execution_price = float(payload["execution_price"])
            quantity = float(payload["quantity"])
            side = str(payload["side"]).upper()
            future_mid = self._future_mid_price(execution_ts)

            if side == "BUY":
                pnl = (future_mid - execution_price) * quantity
            else:
                pnl = (execution_price - future_mid) * quantity
            net_return += pnl
            side_key = self._side_key_from_order_side(side)
            if side_key is not None:
                side_net_returns[side_key] += pnl
                side_matched_orders[side_key] += 1

        return EnvironmentEvaluation(
            net_return=float(net_return),
            matched_orders=int(summary.matched_orders),
            signals_processed=int(summary.signals_processed),
            routed_orders=int(summary.routed_orders),
            rejected_allocations=int(summary.rejected_allocations),
            long_side=SideEnvironmentEvaluation(
                net_return=float(side_net_returns["long"]),
                matched_orders=int(side_matched_orders["long"]),
            ),
            short_side=SideEnvironmentEvaluation(
                net_return=float(side_net_returns["short"]),
                matched_orders=int(side_matched_orders["short"]),
            ),
        )

    @staticmethod
    def _select_signal_side(
        pipeline: LiveStrategyPipeline,
        *,
        imbalance_ratio: float,
        mid: float,
        latency_mid: float,
    ) -> Optional[str]:
        if imbalance_ratio >= float(pipeline.imbalance_cutoff) and mid >= latency_mid:
            return "BUY"
        if imbalance_ratio <= (1.0 - float(pipeline.imbalance_cutoff)) and mid <= latency_mid:
            return "SELL"
        return None

    def _compute_activity_penalty(self, environment_results: Dict[str, EnvironmentEvaluation]) -> float:
        baseline_trades = int(environment_results["baseline"].matched_orders)
        missing_trades = max(0, int(self.min_trades) - baseline_trades)
        return float(float(self.missing_trade_penalty) * float(missing_trades))

    @staticmethod
    def _passes_imbalance_velocity(side: str, imbalance_velocity: float, threshold: float) -> bool:
        return LiveStrategyPipeline._passes_imbalance_velocity(side, imbalance_velocity, threshold)

    @staticmethod
    def _build_candidate_diagnostics(
        raw_counts: Dict[str, int],
        matched_orders: int,
    ) -> CandidateDiagnostics:
        feature_quotes = int(raw_counts["feature_quotes"])
        passed_signals = int(raw_counts["passed_signals"])
        kill_counts = {
            "spread": int(raw_counts["spread_rejections"]),
            "imbalance": int(raw_counts["imbalance_rejections"]),
            "trend": int(raw_counts["trend_rejections"]),
            "trend_gap": int(raw_counts["trend_separation_rejections"]),
            "velocity": int(raw_counts["trend_velocity_rejections"]),
        }
        dominant_kill_gate = "none"
        dominant_kill_count = 0
        if any(kill_counts.values()):
            dominant_kill_gate, dominant_kill_count = max(kill_counts.items(), key=lambda item: item[1])
        denominator = float(feature_quotes) if feature_quotes > 0 else 0.0
        pass_rate = (float(passed_signals) / denominator) if denominator else 0.0
        dominant_kill_rate = (float(dominant_kill_count) / denominator) if denominator else 0.0
        return CandidateDiagnostics(
            quotes_seen=int(raw_counts["quotes_seen"]),
            feature_quotes=feature_quotes,
            spread_rejections=int(raw_counts["spread_rejections"]),
            imbalance_rejections=int(raw_counts["imbalance_rejections"]),
            trend_warmup_skips=int(raw_counts["trend_warmup_skips"]),
            trend_rejections=int(raw_counts["trend_rejections"]),
            trend_separation_rejections=int(raw_counts["trend_separation_rejections"]),
            trend_velocity_rejections=int(raw_counts["trend_velocity_rejections"]),
            passed_signals=passed_signals,
            matched_orders=int(matched_orders),
            pass_rate=float(pass_rate),
            dominant_kill_gate=dominant_kill_gate,
            dominant_kill_rate=float(dominant_kill_rate),
        )

    @staticmethod
    def _format_candidate_diagnostics_matrix(candidates: Sequence[Dict[str, Any]]) -> str:
        headers = [
            "spread",
            "imbal",
            "fast",
            "slow",
            "gapbps",
            "vellbk",
            "velthr",
            "fitness",
            "N",
            "pass%",
            "spread%",
            "imbal%",
            "trend%",
            "gap%",
            "vel%",
            "gate",
            "base_fill",
            "stress_fill",
        ]
        rows: List[List[str]] = [headers]
        for candidate in candidates:
            diagnostics = candidate["baseline"]["diagnostics"]
            feature_quotes = max(int(diagnostics["feature_quotes"]), 1)
            rows.append(
                [
                    f"{float(candidate['spread_threshold']):.2f}",
                    f"{float(candidate['imbalance_cutoff']):.2f}",
                    str(int(candidate["fast_ema_len"])),
                    str(int(candidate["slow_ema_len"])),
                    f"{float(candidate['min_trend_separation_bps']):.1f}",
                    str(int(candidate["imbalance_velocity_lookback"])),
                    f"{float(candidate['imbalance_velocity_threshold']):.2f}",
                    f"{float(candidate['fitness']):.4f}",
                    str(int(diagnostics["passed_signals"])),
                    f"{float(diagnostics['pass_rate']) * 100.0:.1f}",
                    f"{(float(diagnostics['spread_rejections']) / feature_quotes) * 100.0:.1f}",
                    f"{(float(diagnostics['imbalance_rejections']) / feature_quotes) * 100.0:.1f}",
                    f"{(float(diagnostics['trend_rejections']) / feature_quotes) * 100.0:.1f}",
                    f"{(float(diagnostics['trend_separation_rejections']) / feature_quotes) * 100.0:.1f}",
                    f"{(float(diagnostics['trend_velocity_rejections']) / feature_quotes) * 100.0:.1f}",
                    str(diagnostics["dominant_kill_gate"]),
                    str(int(candidate["baseline"]["matched_orders"])),
                    str(int(candidate["stress_surge"]["matched_orders"])),
                ]
            )

        widths = [max(len(row[index]) for row in rows) for index in range(len(headers))]
        formatted_rows = ["  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows]
        return "\n".join(formatted_rows)

    async def evaluate_parameters(
        self,
        spread_threshold: float,
        imbalance_cutoff: float,
        fast_ema_len: int,
        slow_ema_len: int,
        min_trend_separation_bps: float,
        imbalance_velocity_lookback: int,
        imbalance_velocity_threshold: float,
    ) -> Dict[str, EnvironmentEvaluation]:
        results: Dict[str, EnvironmentEvaluation] = {}
        profiles = self.generate_degradation_profiles()

        for env_name, latency_profile in profiles.items():
            ema_state: Dict[str, Optional[float]] = {"fast": None, "slow": None}
            bar_ema_state_by_symbol: Dict[str, Dict[str, Optional[float]]] = defaultdict(
                lambda: {"fast": None, "slow": None}
            )
            bar_mid_history: Dict[str, Deque[float]] = defaultdict(deque)
            bar_imbalance_history: Dict[str, Deque[float]] = defaultdict(deque)
            diagnostics = self._empty_raw_diagnostics()
            side_diagnostics = self._empty_side_raw_diagnostics()
            bar_aggregator = TickToBarAggregator(self.bar_frequency) if self.bar_frequency is not None else None
            pipeline = LiveStrategyPipeline(
                router=_TrainingAllocationRouter(),
                target_accounts=self.target_accounts,
                policy=self.policy,
                spread_mode=self.spread_mode,
                spread_threshold=float(spread_threshold),
                max_spread_bps=self.max_spread_bps,
                imbalance_cutoff=float(imbalance_cutoff),
                imbalance_velocity_lookback=int(imbalance_velocity_lookback),
                imbalance_velocity_threshold=float(imbalance_velocity_threshold),
                signal_quantity=self.signal_quantity,
                latency_window=self.latency_window,
                spread_window=self.spread_window,
            )
            engine: Optional[HistoricalSimulationEngine] = None

            def strategy_callback(
                event: HistoricalQuoteEvent,
                nbbo_cache: Dict[str, Dict[str, float]],
            ) -> Optional[StrategySignal]:
                _ = nbbo_cache
                diagnostics["quotes_seen"] += 1
                bar_signal_state: Optional[Dict[str, float]] = None
                if self.bar_frequency is None:
                    mid_price = float(event.mid)
                    ema_state["fast"] = self._update_ema(ema_state["fast"], mid_price, length=int(fast_ema_len))
                    ema_state["slow"] = self._update_ema(ema_state["slow"], mid_price, length=int(slow_ema_len))

                if self._uses_dynamic_exits() and engine is not None and engine.has_active_trade(event.symbol):
                    return None
                if event.symbol in pipeline.active_signals:
                    return None
                gate_allowed, finalized_bars = self._bar_gate_allows_event(bar_aggregator, event)
                if self.bar_frequency is not None:
                    if not gate_allowed:
                        return None
                    bar_signal_state = self._apply_finalized_bar_state(
                        finalized_bars=finalized_bars,
                        symbol=event.symbol,
                        ema_state_by_symbol=bar_ema_state_by_symbol,
                        bar_mid_history=bar_mid_history,
                        bar_imbalance_history=bar_imbalance_history,
                        latency_window=self.latency_window,
                        imbalance_velocity_lookback=imbalance_velocity_lookback,
                        fast_ema_len=fast_ema_len,
                        slow_ema_len=slow_ema_len,
                    )
                    if bar_signal_state is None:
                        return None

                features = pipeline.evaluate_quote_features(
                    symbol=event.symbol,
                    bid=event.bid,
                    ask=event.ask,
                    bid_size=event.bid_size,
                    ask_size=event.ask_size,
                )
                if features is None:
                    return None

                diagnostics["feature_quotes"] += 1
                imbalance_ratio = float(features["imbalance_ratio"])
                latency_mid = float(features["latency_attenuated_mid"])
                signal_mid = float(features["mid"])
                fast_ema = ema_state["fast"]
                slow_ema = ema_state["slow"]
                imbalance_velocity_value = float(features["imbalance_velocity"])
                if bar_signal_state is not None:
                    imbalance_ratio = float(bar_signal_state["imbalance_ratio"])
                    latency_mid = float(bar_signal_state["latency_mid"])
                    signal_mid = float(bar_signal_state["mid"])
                    fast_ema = float(bar_signal_state["fast_ema"])
                    slow_ema = float(bar_signal_state["slow_ema"])
                    imbalance_velocity_value = float(bar_signal_state["imbalance_velocity"])

                side = self._select_signal_side(
                    pipeline,
                    imbalance_ratio=imbalance_ratio,
                    mid=signal_mid,
                    latency_mid=latency_mid,
                )
                side_key = self._side_key_from_order_side(side) if side is not None else None
                if side_key is not None:
                    side_diagnostics[side_key]["quotes_seen"] += 1
                    side_diagnostics[side_key]["feature_quotes"] += 1

                if not pipeline.passes_spread_gate(features):
                    diagnostics["spread_rejections"] += 1
                    if side_key is not None:
                        side_diagnostics[side_key]["spread_rejections"] += 1
                    return None

                if side is None:
                    diagnostics["imbalance_rejections"] += 1
                    return None
                assert side_key is not None
                if not self._direction_allows_side(side):
                    return None
                if not self._passes_imbalance_velocity(
                    side,
                    imbalance_velocity_value,
                    float(imbalance_velocity_threshold),
                ):
                    diagnostics["trend_velocity_rejections"] += 1
                    side_diagnostics[side_key]["trend_velocity_rejections"] += 1
                    return None

                if fast_ema is None or slow_ema is None:
                    diagnostics["trend_warmup_skips"] += 1
                    side_diagnostics[side_key]["trend_warmup_skips"] += 1
                    return None
                if not self._passes_regime_filter(side, fast_ema, slow_ema):
                    diagnostics["trend_rejections"] += 1
                    side_diagnostics[side_key]["trend_rejections"] += 1
                    return None
                if not self._passes_trend_separation(fast_ema, slow_ema, min_trend_separation_bps):
                    diagnostics["trend_separation_rejections"] += 1
                    side_diagnostics[side_key]["trend_separation_rejections"] += 1
                    return None

                diagnostics["passed_signals"] += 1
                side_diagnostics[side_key]["passed_signals"] += 1

                return StrategySignal(
                    symbol=event.symbol,
                    total_qty=self.signal_quantity,
                    side=side,
                    policy=self.policy,
                    target_accounts=list(self.target_accounts),
                    kwargs={"orderType": "MKT"},
                )

            engine = HistoricalSimulationEngine(
                data_connector=self._build_data_connector(),
                strategy_callback=strategy_callback,
                allocation_router=_TrainingAllocationRouter(),
                latency_profile=latency_profile,
                size_penalty_bps_per_excess_ratio=self.size_penalty_bps_per_excess_ratio,
                exit_time_decay_ticks=self.exit_time_decay_ticks,
                exit_trailing_vol_multiplier=self.exit_trailing_vol_multiplier,
                exit_vol_lookback_ticks=self.exit_vol_lookback_ticks,
            )
            summary = await engine.run(
                self.symbol,
                start_ts=self.start_ts,
                end_ts=self.end_ts,
                limit=self.limit,
            )
            evaluation = self._score_run(engine.trace_events, summary)
            results[env_name] = EnvironmentEvaluation(
                net_return=evaluation.net_return,
                matched_orders=evaluation.matched_orders,
                signals_processed=evaluation.signals_processed,
                routed_orders=evaluation.routed_orders,
                rejected_allocations=evaluation.rejected_allocations,
                diagnostics=self._build_candidate_diagnostics(diagnostics, summary.matched_orders),
                long_side=SideEnvironmentEvaluation(
                    net_return=evaluation.long_side.net_return,
                    matched_orders=evaluation.long_side.matched_orders,
                    diagnostics=self._build_candidate_diagnostics(
                        side_diagnostics["long"],
                        evaluation.long_side.matched_orders,
                    ),
                ),
                short_side=SideEnvironmentEvaluation(
                    net_return=evaluation.short_side.net_return,
                    matched_orders=evaluation.short_side.matched_orders,
                    diagnostics=self._build_candidate_diagnostics(
                        side_diagnostics["short"],
                        evaluation.short_side.matched_orders,
                    ),
                ),
            )

        return results

    def compute_fitness(self, environment_results: Dict[str, EnvironmentEvaluation]) -> float:
        baseline = environment_results["baseline"].net_return
        stress = environment_results["stress_surge"].net_return
        resiliency_penalty = self.resiliency_penalty_lambda * abs(min(0.0, stress))
        activity_penalty = self._compute_activity_penalty(environment_results)
        return float(baseline - resiliency_penalty - activity_penalty)

    async def train(self) -> Dict[str, Any]:
        best_payload: Optional[Dict[str, Any]] = None
        candidate_rows: List[Dict[str, Any]] = []
        candidates = self._candidate_specs()
        if self.max_workers > 1 and len(candidates) > 1:
            candidate_rows = self._evaluate_candidates_parallel(candidates)
        else:
            for candidate in candidates:
                candidate_rows.append(await self._evaluate_candidate(candidate))

        for candidate in candidate_rows:
            logger.info(
                "Evaluated candidate spread_threshold=%.4f imbalance_cutoff=%.4f fast_ema_len=%d slow_ema_len=%d min_trend_separation_bps=%.2f imbalance_velocity_lookback=%d imbalance_velocity_threshold=%.4f fitness=%.4f",
                float(candidate["spread_threshold"]),
                float(candidate["imbalance_cutoff"]),
                int(candidate["fast_ema_len"]),
                int(candidate["slow_ema_len"]),
                float(candidate["min_trend_separation_bps"]),
                int(candidate["imbalance_velocity_lookback"]),
                float(candidate["imbalance_velocity_threshold"]),
                float(candidate["fitness"]),
            )
            if best_payload is None or float(candidate["fitness"]) > float(best_payload["fitness"]):
                best_payload = candidate

        if best_payload is None:
            raise RuntimeError("No candidate strategy parameters were evaluated.")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as handle:
            json.dump(best_payload, handle, indent=2, sort_keys=True)
        logger.info("Candidate diagnostics matrix:\n%s", self._format_candidate_diagnostics_matrix(candidate_rows))
        logger.info("Wrote optimized alpha weights to %s", self.output_path)
        return best_payload


def _parse_float_list(raw: str) -> List[float]:
    return [float(item.strip()) for item in str(raw).split(",") if item.strip()]


def _parse_int_list(raw: str) -> List[int]:
    return [int(item.strip()) for item in str(raw).split(",") if item.strip()]


async def _async_main(args: argparse.Namespace) -> None:
    trainer = StrategyTrainer(
        dataset_glob=str(args.dataset_glob),
        symbol=str(args.symbol),
        target_accounts=[item.strip() for item in str(args.target_accounts).split(",") if item.strip()],
        policy=str(args.policy),
        output_path=str(args.output_path) if args.output_path else None,
        start_ts=args.start_ts,
        end_ts=args.end_ts,
        limit=args.limit,
        markout_ns=args.markout_ns,
        size_penalty_bps_per_excess_ratio=args.size_penalty_bps_per_excess_ratio,
        spread_mode=args.spread_mode,
        spread_thresholds=_parse_float_list(args.spread_thresholds),
        max_spread_bps=args.max_spread_bps,
        bar_frequency=args.bar_frequency,
        imbalance_cutoffs=_parse_float_list(args.imbalance_cutoffs),
        fast_ema_lengths=_parse_int_list(args.fast_ema_lengths),
        slow_ema_lengths=_parse_int_list(args.slow_ema_lengths),
        min_trend_separation_bps_values=_parse_float_list(args.min_trend_separation_bps_values),
        imbalance_velocity_lookbacks=_parse_int_list(args.imbalance_velocity_lookbacks),
        imbalance_velocity_thresholds=_parse_float_list(args.imbalance_velocity_thresholds),
        min_trades=args.min_trades,
        missing_trade_penalty=args.missing_trade_penalty,
        signal_quantity=args.signal_quantity,
        latency_window=args.latency_window,
        spread_window=args.spread_window,
        resiliency_penalty_lambda=args.resiliency_penalty_lambda,
        timestamp_col=args.timestamp_col,
        symbol_col=args.symbol_col,
        bid_col=args.bid_col,
        ask_col=args.ask_col,
        bid_size_col=args.bid_size_col,
        ask_size_col=args.ask_size_col,
        hour_range=args.hour_range,
        exit_time_decay_ticks=args.exit_time_decay_ticks,
        exit_trailing_vol_multiplier=args.exit_trailing_vol_multiplier,
        exit_vol_lookback_ticks=args.exit_vol_lookback_ticks,
        direction=args.direction,
        max_workers=args.max_workers,
    )
    result = await trainer.train()
    print(json.dumps(result, indent=2, sort_keys=True))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train live alpha thresholds against historical quote data.")
    parser.add_argument("--dataset-glob", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--target-accounts", default="SIM")
    parser.add_argument("--policy", default="DYNAMIC_NLV")
    parser.add_argument("--output-path")
    parser.add_argument("--start-ts")
    parser.add_argument("--end-ts")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--markout-ns", type=int, default=5_000_000_000)
    parser.add_argument("--size-penalty-bps-per-excess-ratio", type=float, default=15.0)
    parser.add_argument("--spread-mode", choices=["relative", "absolute"], default="relative")
    parser.add_argument("--spread-thresholds", default="-0.5,0.0,0.5,1.0")
    parser.add_argument("--max-spread-bps", type=float, default=None)
    parser.add_argument("--bar-frequency", choices=["1m", "5m", "15m"], default=None)
    parser.add_argument("--imbalance-cutoffs", default="0.55,0.65,0.75,0.85")
    parser.add_argument("--fast-ema-lengths", default="5,10,20")
    parser.add_argument("--slow-ema-lengths", default="20,50,100")
    parser.add_argument("--min-trend-separation-bps-values", default="0.0,0.5,1.0")
    parser.add_argument("--imbalance-velocity-lookbacks", default="5,10,20")
    parser.add_argument("--imbalance-velocity-thresholds", default="0.01,0.05,0.10")
    parser.add_argument("--min-trades", type=int, default=3)
    parser.add_argument("--missing-trade-penalty", type=float, default=25.0)
    parser.add_argument("--signal-quantity", type=int, default=10)
    parser.add_argument("--latency-window", type=int, default=5)
    parser.add_argument("--spread-window", type=int, default=32)
    parser.add_argument("--resiliency-penalty-lambda", type=float, default=2.0)
    parser.add_argument("--timestamp-col", default="timestamp")
    parser.add_argument("--symbol-col", default="symbol")
    parser.add_argument("--bid-col", default="bid")
    parser.add_argument("--ask-col", default="ask")
    parser.add_argument("--bid-size-col", default="bid_size")
    parser.add_argument("--ask-size-col", default="ask_size")
    parser.add_argument(
        "--hour-range",
        default=None,
        help="UTC hour slice in start-end format with an exclusive end hour, for example 7-16.",
    )
    parser.add_argument(
        "--exit-time-decay-ticks",
        type=int,
        default=None,
        help="Optional hard exit after holding a matched position for this many quote ticks.",
    )
    parser.add_argument(
        "--exit-trailing-vol-multiplier",
        type=float,
        default=None,
        help="Optional trailing-stop distance multiplier applied to rolling quote-level mid volatility.",
    )
    parser.add_argument(
        "--exit-vol-lookback-ticks",
        type=int,
        default=32,
        help="Rolling quote count used for the trailing-stop mid-volatility proxy.",
    )
    parser.add_argument(
        "--direction",
        choices=["long", "short", "both"],
        default="both",
        help="Restrict strategy callback execution to long-only, short-only, or both directional paths.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Optional candidate-level worker count. Values above 1 parallelize the parameter grid across processes.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.spread_mode == "absolute" and args.max_spread_bps is None:
        parser.error("--max-spread-bps is required when --spread-mode absolute")
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()