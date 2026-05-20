"""Historical event-driven simulation scaffolding for high-fidelity backtests.

Phase 2 scope:
- Stream top-of-book quote events from Parquet via DuckDB.
- Maintain an NBBO cache in an event loop.
- Route strategy signals through allocation router with delayed arrival modeling.
- Match arrivals to historical bid/ask and emit signed shortfall traces.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import heapq
import math
import random
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional, Tuple

import pandas as pd


class HistoricalDataError(Exception):
    """Raised when historical feed loading fails."""


@dataclass(frozen=True)
class HistoricalQuoteEvent:
    """Synthetic quote event used by the historical simulation loop."""

    timestamp: pd.Timestamp
    symbol: str
    bid: float
    ask: float
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class StrategySignal:
    """Allocation-layer signal consumed by the simulation engine."""

    symbol: str
    total_qty: int
    side: str
    policy: str
    target_accounts: List[str]
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationTraceEvent:
    """Trace event emitted during simulation execution."""

    event_type: str
    timestamp: pd.Timestamp
    payload: Dict[str, Any]


@dataclass(frozen=True)
class SimulationRunSummary:
    """Summary of one historical simulation run."""

    symbol: str
    quote_events_processed: int
    signals_processed: int
    matched_orders: int
    routed_orders: int
    rejected_allocations: int


@dataclass(frozen=True)
class MatchedExecution:
    """Result of matching one pending order at the current historical quote."""

    symbol: str
    side: str
    quantity: int
    arrival_timestamp: pd.Timestamp
    execution_timestamp: pd.Timestamp
    execution_price: float
    nbbo_mid: float
    shortfall_bps: float
    slippage_penalty_bps: float


@dataclass(frozen=True)
class PendingOrder:
    """Deferred order waiting for simulated wire arrival time."""

    sequence: int
    arrival_ts: pd.Timestamp
    signal_ts: pd.Timestamp
    signal: StrategySignal


@dataclass
class OpenPosition:
    """One simulated open position tracked for dynamic exit evaluation."""

    symbol: str
    entry_side: str
    quantity: int
    entry_timestamp: pd.Timestamp
    entry_execution_timestamp: pd.Timestamp
    entry_price: float
    entry_quote_index: int
    best_price: float
    trailing_offset: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    entry_volatility: float = 0.0


LatencyNsProvider = Callable[[StrategySignal, HistoricalQuoteEvent, Dict[str, Dict[str, float]]], int]


@dataclass
class LatencyDistributionProfile:
    """Deterministic latency distribution sampler for simulation delays."""

    mode: str = "fixed"
    fixed_ns: int = 0
    mean_ns: int = 0
    std_ns: int = 0
    min_ns: int = 0
    max_ns: Optional[int] = None
    seed: Optional[int] = None
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def sample_ns(self) -> int:
        """Sample one non-negative latency delay in nanoseconds."""
        mode = self.mode.upper()

        if mode == "FIXED":
            sampled = int(self.fixed_ns)
        elif mode == "NORMAL":
            sampled = int(round(self._rng.gauss(float(self.mean_ns), float(self.std_ns))))
        else:
            raise HistoricalDataError(f"Unsupported latency profile mode: {self.mode}")

        sampled = max(sampled, int(self.min_ns))
        if self.max_ns is not None:
            sampled = min(sampled, int(self.max_ns))
        return max(sampled, 0)


class DuckDBHistoricalDatasetConnector:
    """Streams quote events from Parquet partitions using DuckDB."""

    SIZE_COLUMN_ALIASES: Dict[str, Tuple[str, ...]] = {
        "bid_size": ("bid_vol",),
        "ask_size": ("ask_vol",),
    }

    def __init__(
        self,
        dataset_glob: str,
        *,
        timestamp_col: str = "timestamp",
        symbol_col: str = "symbol",
        bid_col: str = "bid",
        ask_col: str = "ask",
        bid_size_col: Optional[str] = None,
        ask_size_col: Optional[str] = None,
        connection_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.dataset_glob = dataset_glob
        self.timestamp_col = timestamp_col
        self.symbol_col = symbol_col
        self.bid_col = bid_col
        self.ask_col = ask_col
        self.bid_size_col = bid_size_col
        self.ask_size_col = ask_size_col
        self._connection_factory = connection_factory

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()

        try:
            import duckdb  # type: ignore
        except Exception as exc:
            raise HistoricalDataError(
                "DuckDB is required for historical parquet streaming. "
                "Install it with: pip install duckdb"
            ) from exc
        return duckdb.connect(database=":memory:")

    def _read_parquet_schema(self, conn: Any, dataset: str) -> List[str]:
        rows = conn.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{dataset}', union_by_name = true)"
        ).fetchall()
        return [str(row[0]) for row in rows]

    def _resolve_optional_column(
        self,
        conn: Any,
        dataset: str,
        configured_column: Optional[str],
        default_column: str,
    ) -> Optional[str]:
        available_columns = set(self._read_parquet_schema(conn, dataset))
        base_candidate = configured_column if configured_column is not None else default_column
        candidates = (base_candidate, *self.SIZE_COLUMN_ALIASES.get(default_column, ()))
        for candidate in candidates:
            if candidate in available_columns:
                return candidate
        return None

    def iter_quotes(
        self,
        symbol: str,
        *,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
        limit: Optional[int] = None,
    ) -> Iterator[HistoricalQuoteEvent]:
        """Yield quote events ordered by timestamp for one symbol."""
        dataset = self.dataset_glob.replace("'", "''")
        where_clauses: List[str] = [
            f"{self.symbol_col} = ?",
            f"{self.bid_col} IS NOT NULL",
            f"{self.ask_col} IS NOT NULL",
        ]
        params: List[Any] = [symbol]

        if start_ts is not None:
            where_clauses.append(f"{self.timestamp_col} >= ?")
            params.append(pd.Timestamp(start_ts).to_pydatetime())
        if end_ts is not None:
            where_clauses.append(f"{self.timestamp_col} <= ?")
            params.append(pd.Timestamp(end_ts).to_pydatetime())

        limit_clause = ""
        if limit is not None:
            limit_clause = f" LIMIT {int(limit)}"

        conn = self._connect()
        try:
            resolved_bid_size_col = self._resolve_optional_column(conn, dataset, self.bid_size_col, "bid_size")
            resolved_ask_size_col = self._resolve_optional_column(conn, dataset, self.ask_size_col, "ask_size")

            select_cols = [
                f"{self.timestamp_col} AS ts",
                f"{self.symbol_col} AS sym",
                f"{self.bid_col} AS bid_px",
                f"{self.ask_col} AS ask_px",
            ]
            if resolved_bid_size_col:
                select_cols.append(f"{resolved_bid_size_col} AS bid_sz")
            else:
                select_cols.append("NULL AS bid_sz")
            if resolved_ask_size_col:
                select_cols.append(f"{resolved_ask_size_col} AS ask_sz")
            else:
                select_cols.append("NULL AS ask_sz")

            sql = (
                f"SELECT {', '.join(select_cols)} "
                f"FROM read_parquet('{dataset}', union_by_name = true) "
                f"WHERE {' AND '.join(where_clauses)} "
                f"ORDER BY {self.timestamp_col} ASC{limit_clause}"
            )

            rows = conn.execute(sql, params).fetchall()
            for row in rows:
                if len(row) == 4:
                    ts, sym, bid_px, ask_px = row
                    bid_sz = None
                    ask_sz = None
                else:
                    ts, sym, bid_px, ask_px, bid_sz, ask_sz = row
                yield HistoricalQuoteEvent(
                    timestamp=pd.Timestamp(ts),
                    symbol=str(sym),
                    bid=float(bid_px),
                    ask=float(ask_px),
                    bid_size=float(bid_sz) if bid_sz is not None else None,
                    ask_size=float(ask_sz) if ask_sz is not None else None,
                )
        finally:
            try:
                conn.close()
            except Exception:
                pass


class HistoricalSimulationEngine:
    """Event-driven simulation loop wired for allocation-router integration."""

    def __init__(
        self,
        data_connector: DuckDBHistoricalDatasetConnector,
        strategy_callback: Callable[[HistoricalQuoteEvent, Dict[str, Dict[str, float]]], Optional[StrategySignal]],
        allocation_router: Any,
        latency_ns_provider: Optional[LatencyNsProvider] = None,
        latency_profile: Optional[LatencyDistributionProfile] = None,
        size_penalty_bps_per_excess_ratio: float = 5.0,
        exit_time_decay_ticks: Optional[int] = None,
        exit_trailing_vol_multiplier: Optional[float] = None,
        exit_vol_lookback_ticks: int = 32,
        synthetic_wal_path: Optional[str] = None,
    ) -> None:
        self.data_connector = data_connector
        self.strategy_callback = strategy_callback
        self.allocation_router = allocation_router
        self._latency_profile = latency_profile
        self.latency_ns_provider = latency_ns_provider or self._build_latency_provider_from_profile(latency_profile)
        self.size_penalty_bps_per_excess_ratio = float(size_penalty_bps_per_excess_ratio)
        self.exit_time_decay_ticks = int(exit_time_decay_ticks) if exit_time_decay_ticks is not None else None
        if self.exit_time_decay_ticks is not None and self.exit_time_decay_ticks < 1:
            raise ValueError("exit_time_decay_ticks must be >= 1 when provided")
        self.exit_trailing_vol_multiplier = (
            float(exit_trailing_vol_multiplier) if exit_trailing_vol_multiplier is not None else None
        )
        if self.exit_trailing_vol_multiplier is not None and self.exit_trailing_vol_multiplier <= 0.0:
            raise ValueError("exit_trailing_vol_multiplier must be > 0 when provided")
        self.exit_vol_lookback_ticks = max(2, int(exit_vol_lookback_ticks))
        self.nbbo_cache: Dict[str, Dict[str, float]] = {}
        self.trace_events: List[SimulationTraceEvent] = []
        self._event_queue: Deque[HistoricalQuoteEvent] = deque()
        self._pending_heap: List[Tuple[int, int, PendingOrder]] = []
        self._pending_seq = 0
        self._quote_index = -1
        self._open_positions: Dict[str, OpenPosition] = {}
        self._recent_mid_prices: Deque[float] = deque(maxlen=self.exit_vol_lookback_ticks)
        self._synthetic_wal_path = synthetic_wal_path
        self._synthetic_wal_fd = None
        if synthetic_wal_path is not None:
            self._synthetic_wal_fd = open(synthetic_wal_path, "a", encoding="utf-8")

    def _dynamic_exits_enabled(self) -> bool:
        return self.exit_time_decay_ticks is not None or self.exit_trailing_vol_multiplier is not None

    def has_active_trade(self, symbol: str) -> bool:
        if symbol in self._open_positions:
            return True
        return any(pending.signal.symbol == symbol for _, _, pending in self._pending_heap)

    def _append_synthetic_wal_record(self, matched: MatchedExecution, account_id: str = "SIM", order_id: str = "SIMORDER"):
        """Emit a production-format WAL row for a matched execution."""
        if self._synthetic_wal_fd is None:
            return
        # Format: SHORTFALL|{account_id}|{timestamp_ms}|{symbol}|{order_id}|{side}|{exec_price}|{exec_qty}|{benchmark_mid}|{slippage_bps}
        ts_ms = int(matched.execution_timestamp.value // 10**6)
        row = (
            f"SHORTFALL|{account_id}|{ts_ms}|{matched.symbol}|{order_id}|{matched.side}|"
            f"{matched.execution_price}|{matched.quantity}|{matched.nbbo_mid}|{matched.shortfall_bps}\n"
        )
        self._synthetic_wal_fd.write(row)
        self._synthetic_wal_fd.flush()

    async def run(
        self,
        symbol: str,
        *,
        start_ts: Optional[pd.Timestamp] = None,
        end_ts: Optional[pd.Timestamp] = None,
        limit: Optional[int] = None,
    ) -> SimulationRunSummary:
        """Run simulation by streaming historical quote events sequentially."""
        quote_events_processed = 0
        signals_processed = 0
        matched_orders = 0

        for quote_event in self.data_connector.iter_quotes(
            symbol,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
        ):
            self._event_queue.append(quote_event)

            while self._event_queue:
                event = self._event_queue.popleft()
                quote_events_processed += 1
                self._quote_index += 1

                self.nbbo_cache[event.symbol] = {
                    "bid": event.bid,
                    "ask": event.ask,
                    "mid": event.mid,
                    "bid_size": event.bid_size,
                    "ask_size": event.ask_size,
                }
                self._recent_mid_prices.append(float(event.mid))

                self._process_open_positions(event, quote_index=self._quote_index)

                matured_matches = await self._process_matching_engine(event, quote_index=self._quote_index)
                matched_orders += len(matured_matches)

                signal = self.strategy_callback(event, self.nbbo_cache)
                if signal is None:
                    continue

                signals_processed += 1
                delay_ns = max(
                    int(self.latency_ns_provider(signal, event, self.nbbo_cache)),
                    0,
                    )
                arrival_ts = event.timestamp + pd.to_timedelta(delay_ns, unit="ns")
                pending = PendingOrder(
                    sequence=self._pending_seq,
                    arrival_ts=arrival_ts,
                    signal_ts=event.timestamp,
                    signal=signal,
                )
                self._pending_seq += 1
                heapq.heappush(self._pending_heap, (arrival_ts.value, pending.sequence, pending))
                self.trace_events.append(
                    SimulationTraceEvent(
                        event_type="ALLOCATION_PENDING_ENQUEUED",
                        timestamp=event.timestamp,
                        payload={
                            "symbol": signal.symbol,
                            "side": signal.side,
                            "total_qty": signal.total_qty,
                            "policy": signal.policy,
                            "delay_ns": delay_ns,
                            "arrival_ts": arrival_ts.isoformat(),
                        },
                    )
                )

        # End-of-stream flush using the last symbol quote so delayed entries are finalized.
        if symbol in self.nbbo_cache:
            snapshot = self.nbbo_cache[symbol]
            tail_ts = end_ts if end_ts is not None else pd.Timestamp.utcnow()
            tail_event = HistoricalQuoteEvent(
                timestamp=tail_ts,
                symbol=symbol,
                bid=float(snapshot["bid"]),
                ask=float(snapshot["ask"]),
                bid_size=snapshot.get("bid_size"),
                ask_size=snapshot.get("ask_size"),
            )
            self._quote_index += 1
            self._recent_mid_prices.append(float(tail_event.mid))
            matured_matches = await self._process_matching_engine(tail_event, quote_index=self._quote_index, flush_all=True)
            matched_orders += len(matured_matches)
            self._process_open_positions(tail_event, quote_index=self._quote_index, force_exit=True)

        routed_orders = sum(
            len(evt.payload.get("order_ids", []))
            for evt in self.trace_events
            if evt.event_type == "ALLOCATION_ROUTE_ACCEPT"
        )
        rejected_allocations = sum(
            1
            for evt in self.trace_events
            if evt.event_type == "ALLOCATION_REJECT"
        )

        return SimulationRunSummary(
            symbol=symbol,
            quote_events_processed=quote_events_processed,
            signals_processed=signals_processed,
            matched_orders=matched_orders,
            routed_orders=routed_orders,
            rejected_allocations=rejected_allocations,
        )

    @staticmethod
    def _zero_latency_provider(
        signal: StrategySignal,
        event: HistoricalQuoteEvent,
        nbbo_cache: Dict[str, Dict[str, float]],
    ) -> int:
        _ = (signal, event, nbbo_cache)
        return 0

    @classmethod
    def _build_latency_provider_from_profile(
        cls,
        latency_profile: Optional[LatencyDistributionProfile],
    ) -> LatencyNsProvider:
        if latency_profile is None:
            return cls._zero_latency_provider

        def _provider(
            signal: StrategySignal,
            event: HistoricalQuoteEvent,
            nbbo_cache: Dict[str, Dict[str, float]],
        ) -> int:
            _ = (signal, event, nbbo_cache)
            return latency_profile.sample_ns()

        return _provider

    async def _process_matching_engine(
        self,
        current_quote: HistoricalQuoteEvent,
        *,
        quote_index: int,
        flush_all: bool = False,
    ) -> List[MatchedExecution]:
        """Match pending orders whose arrival time has passed."""
        matched: List[MatchedExecution] = []

        while self._pending_heap:
            arrival_ns, _, pending = self._pending_heap[0]
            if not flush_all and arrival_ns > current_quote.timestamp.value:
                break

            heapq.heappop(self._pending_heap)
            signal = pending.signal
            side = signal.side.upper()
            if side not in {"BUY", "SELL"}:
                self.trace_events.append(
                    SimulationTraceEvent(
                        event_type="ALLOCATION_REJECT",
                        timestamp=current_quote.timestamp,
                        payload={
                            "symbol": signal.symbol,
                            "policy": signal.policy,
                            "target_accounts": list(signal.target_accounts),
                            "reason": f"Unsupported side: {signal.side}",
                        },
                    )
                )
                continue

            try:
                order_ids = await self.allocation_router.route_order(
                    symbol=signal.symbol,
                    total_qty=signal.total_qty,
                    side=signal.side,
                    policy=signal.policy,
                    target_accounts=signal.target_accounts,
                    **signal.kwargs,
                )
                self.trace_events.append(
                    SimulationTraceEvent(
                        event_type="ALLOCATION_ROUTE_ACCEPT",
                        timestamp=current_quote.timestamp,
                        payload={
                            "symbol": signal.symbol,
                            "policy": signal.policy,
                            "target_accounts": list(signal.target_accounts),
                            "order_ids": list(order_ids),
                        },
                    )
                )
            except Exception as exc:
                self.trace_events.append(
                    SimulationTraceEvent(
                        event_type="ALLOCATION_REJECT",
                        timestamp=current_quote.timestamp,
                        payload={
                            "symbol": signal.symbol,
                            "policy": signal.policy,
                            "target_accounts": list(signal.target_accounts),
                            "reason": str(exc),
                        },
                    )
                )
                continue

            matched_execution = self._match_order_to_quote(pending, current_quote)
            matched.append(matched_execution)
            self.trace_events.append(
                SimulationTraceEvent(
                    event_type="ALLOCATION_MATCHED",
                    timestamp=current_quote.timestamp,
                    payload={
                        "symbol": matched_execution.symbol,
                        "side": matched_execution.side,
                        "quantity": matched_execution.quantity,
                        "arrival_ts": matched_execution.arrival_timestamp.isoformat(),
                        "execution_ts": matched_execution.execution_timestamp.isoformat(),
                        "execution_price": matched_execution.execution_price,
                        "nbbo_mid": matched_execution.nbbo_mid,
                        "shortfall_bps": matched_execution.shortfall_bps,
                        "slippage_penalty_bps": matched_execution.slippage_penalty_bps,
                    },
                )
            )
            # Emit WAL row if enabled
            self._append_synthetic_wal_record(matched_execution)
            if self._dynamic_exits_enabled():
                position = self._open_position_from_match(matched_execution, current_quote, quote_index=quote_index)
                self._open_positions[position.symbol] = position
                self.trace_events.append(
                    SimulationTraceEvent(
                        event_type="POSITION_OPENED",
                        timestamp=current_quote.timestamp,
                        payload={
                            "symbol": position.symbol,
                            "entry_side": position.entry_side,
                            "quantity": position.quantity,
                            "entry_ts": position.entry_timestamp.isoformat(),
                            "entry_execution_ts": position.entry_execution_timestamp.isoformat(),
                            "entry_price": position.entry_price,
                            "entry_quote_index": position.entry_quote_index,
                            "entry_volatility": position.entry_volatility,
                            "trailing_offset": position.trailing_offset,
                            "trailing_stop_price": position.trailing_stop_price,
                        },
                    )
                )

        return matched
    def __del__(self):
        if self._synthetic_wal_fd is not None:
            try:
                self._synthetic_wal_fd.close()
            except Exception:
                pass

    def _match_order_to_quote(
        self,
        pending: PendingOrder,
        quote: HistoricalQuoteEvent,
    ) -> MatchedExecution:
        """Compute execution against bid/ask with optional size-based penalty."""
        signal = pending.signal
        side = signal.side.upper()
        qty = int(signal.total_qty)
        execution_price, nbbo_mid, shortfall_bps, penalty_bps = self._compute_execution_metrics(side, qty, quote)

        return MatchedExecution(
            symbol=signal.symbol,
            side=side,
            quantity=qty,
            arrival_timestamp=pending.arrival_ts,
            execution_timestamp=quote.timestamp,
            execution_price=execution_price,
            nbbo_mid=nbbo_mid,
            shortfall_bps=shortfall_bps,
            slippage_penalty_bps=penalty_bps,
        )

    def _compute_execution_metrics(
        self,
        side: str,
        quantity: int,
        quote: HistoricalQuoteEvent,
    ) -> Tuple[float, float, float, float]:
        nbbo_mid = quote.mid

        if side == "BUY":
            base_price = float(quote.ask)
            available_size = quote.ask_size
            direction_flag = 1.0
        else:
            base_price = float(quote.bid)
            available_size = quote.bid_size
            direction_flag = -1.0

        penalty_bps = 0.0
        if available_size is not None and available_size > 0 and quantity > available_size:
            excess_ratio = (quantity - available_size) / available_size
            penalty_bps = max(0.0, excess_ratio) * self.size_penalty_bps_per_excess_ratio

        if side == "BUY":
            execution_price = base_price * (1.0 + penalty_bps / 10000.0)
        else:
            execution_price = base_price * (1.0 - penalty_bps / 10000.0)

        if nbbo_mid <= 0:
            shortfall_bps = 0.0
        else:
            shortfall_bps = ((execution_price - nbbo_mid) / nbbo_mid) * 10000.0 * direction_flag

        return execution_price, nbbo_mid, shortfall_bps, penalty_bps

    def _compute_mid_volatility(self) -> float:
        if len(self._recent_mid_prices) < 2:
            return 0.0
        mid_values = list(self._recent_mid_prices)
        mean_mid = sum(mid_values) / float(len(mid_values))
        variance = sum((value - mean_mid) ** 2 for value in mid_values) / float(len(mid_values))
        return math.sqrt(max(variance, 0.0))

    def _open_position_from_match(
        self,
        matched_execution: MatchedExecution,
        quote: HistoricalQuoteEvent,
        *,
        quote_index: int,
    ) -> OpenPosition:
        entry_side = matched_execution.side.upper()
        if entry_side == "BUY":
            best_price = float(quote.bid)
        else:
            best_price = float(quote.ask)

        trailing_offset = None
        trailing_stop_price = None
        entry_volatility = self._compute_mid_volatility()
        if self.exit_trailing_vol_multiplier is not None:
            spread_width = max(float(quote.ask) - float(quote.bid), 0.0)
            volatility_basis = max(entry_volatility, spread_width, 1e-9)
            trailing_offset = float(self.exit_trailing_vol_multiplier) * volatility_basis
            if entry_side == "BUY":
                trailing_stop_price = best_price - trailing_offset
            else:
                trailing_stop_price = best_price + trailing_offset

        return OpenPosition(
            symbol=matched_execution.symbol,
            entry_side=entry_side,
            quantity=matched_execution.quantity,
            entry_timestamp=matched_execution.arrival_timestamp,
            entry_execution_timestamp=matched_execution.execution_timestamp,
            entry_price=matched_execution.execution_price,
            entry_quote_index=quote_index,
            best_price=best_price,
            trailing_offset=trailing_offset,
            trailing_stop_price=trailing_stop_price,
            entry_volatility=entry_volatility,
        )

    def _process_open_positions(
        self,
        current_quote: HistoricalQuoteEvent,
        *,
        quote_index: int,
        force_exit: bool = False,
    ) -> None:
        if not self._open_positions:
            return

        position = self._open_positions.get(current_quote.symbol)
        if position is None:
            return

        exit_reason: Optional[str] = None
        if force_exit:
            exit_reason = "end_of_stream"
        elif self.exit_time_decay_ticks is not None and (quote_index - position.entry_quote_index) >= self.exit_time_decay_ticks:
            exit_reason = "time_decay"
        else:
            self._refresh_trailing_stop(position, current_quote)
            if self._trailing_stop_breached(position, current_quote):
                exit_reason = "trailing_stop"

        if exit_reason is None:
            return

        exit_side = "SELL" if position.entry_side == "BUY" else "BUY"
        execution_price, nbbo_mid, shortfall_bps, penalty_bps = self._compute_execution_metrics(
            exit_side,
            position.quantity,
            current_quote,
        )
        if position.entry_side == "BUY":
            realized_pnl = (execution_price - position.entry_price) * float(position.quantity)
        else:
            realized_pnl = (position.entry_price - execution_price) * float(position.quantity)

        self.trace_events.append(
            SimulationTraceEvent(
                event_type="POSITION_EXITED",
                timestamp=current_quote.timestamp,
                payload={
                    "symbol": position.symbol,
                    "entry_side": position.entry_side,
                    "exit_side": exit_side,
                    "quantity": position.quantity,
                    "entry_ts": position.entry_timestamp.isoformat(),
                    "entry_execution_ts": position.entry_execution_timestamp.isoformat(),
                    "exit_ts": current_quote.timestamp.isoformat(),
                    "entry_price": position.entry_price,
                    "exit_price": execution_price,
                    "exit_reason": exit_reason,
                    "entry_quote_index": position.entry_quote_index,
                    "exit_quote_index": quote_index,
                    "held_ticks": max(0, quote_index - position.entry_quote_index),
                    "entry_volatility": position.entry_volatility,
                    "trailing_offset": position.trailing_offset,
                    "trailing_stop_price": position.trailing_stop_price,
                    "nbbo_mid": nbbo_mid,
                    "shortfall_bps": shortfall_bps,
                    "slippage_penalty_bps": penalty_bps,
                    "realized_pnl": realized_pnl,
                },
            )
        )
        del self._open_positions[position.symbol]

    def _refresh_trailing_stop(self, position: OpenPosition, current_quote: HistoricalQuoteEvent) -> None:
        if position.trailing_offset is None:
            return

        if position.entry_side == "BUY":
            current_reference_price = float(current_quote.bid)
            if current_reference_price > position.best_price:
                position.best_price = current_reference_price
                position.trailing_stop_price = current_reference_price - position.trailing_offset
            return

        current_reference_price = float(current_quote.ask)
        if current_reference_price < position.best_price:
            position.best_price = current_reference_price
            position.trailing_stop_price = current_reference_price + position.trailing_offset

    def _trailing_stop_breached(self, position: OpenPosition, current_quote: HistoricalQuoteEvent) -> bool:
        if position.trailing_stop_price is None:
            return False
        if position.entry_side == "BUY":
            return float(current_quote.bid) <= float(position.trailing_stop_price)
        return float(current_quote.ask) >= float(position.trailing_stop_price)
