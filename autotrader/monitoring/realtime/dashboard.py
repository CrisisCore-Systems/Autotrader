"""Realtime monitoring dashboard aggregation utilities.

This module provides the realtime metrics aggregation engine required by
Phase 12. It ingests audit trail events (orders, fills, positions, risk
checks, etc.) and produces snapshot objects that power live dashboards for
PnL, risk and execution quality monitoring.

Designed to operate in low-latency trading environments (<100ms refresh) with
thread-safe updates and lightweight computations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from threading import RLock
from typing import Any, Deque, Dict, Iterable, Optional, Tuple
from collections import defaultdict, deque
import math

from autotrader.audit.trail import (
    CircuitBreakerEvent,
    FillEvent,
    MarketDataSnapshot,
    OrderEvent,
    PositionUpdateEvent,
    RiskCheckEvent,
    SignalEvent,
)


@dataclass
class RiskLimitConfig:
    """Configuration for risk limit tracking used in the dashboard."""

    max_gross_exposure: Optional[float] = None
    max_net_exposure: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_leverage: Optional[float] = None
    instrument_gross_limits: Dict[str, float] = field(default_factory=dict)


@dataclass
class RealtimeDashboardConfig:
    """Runtime configuration for the realtime dashboard aggregator."""

    starting_equity: float = 1_000_000.0
    timezone: timezone = timezone.utc
    sharpe_window: int = 360  # Number of return samples for Sharpe calc
    latency_window: int = 500  # Number of latency samples to retain
    equity_window: int = 2_880  # Store 8 hours at 10s intervals by default
    max_latency_ms_threshold: float = 2_000.0
    risk_limits: Optional[RiskLimitConfig] = None


@dataclass
class InstrumentMetrics:
    """State container for instrument-level metrics."""

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trade_count: int = 0
    winning_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    slippage_sum_bps: float = 0.0
    slippage_samples: int = 0
    position: float = 0.0
    average_price: float = 0.0
    fills: int = 0
    orders: int = 0
    last_update: Optional[datetime] = None

    def average_slippage(self) -> Optional[float]:
        """Average slippage in basis points for this instrument."""
        if self.slippage_samples == 0:
            return None
        return self.slippage_sum_bps / self.slippage_samples

    def hit_rate(self) -> Optional[float]:
        """Win rate for completed trades."""
        if self.trade_count == 0:
            return None
        return self.winning_trades / self.trade_count

    def profit_factor(self) -> Optional[float]:
        """Profit factor (gross profit divided by gross loss)."""
        if self.gross_loss == 0:
            if self.gross_profit == 0:
                return None
            return float("inf")
        return self.gross_profit / self.gross_loss

    def fill_rate(self) -> Optional[float]:
        """Fill rate computed as fills / orders."""
        if self.orders == 0:
            return None
        return min(1.0, self.fills / self.orders)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serialisable dictionary."""
        return {
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "trade_count": self.trade_count,
            "hit_rate": self.hit_rate(),
            "profit_factor": self.profit_factor(),
            "avg_slippage_bps": self.average_slippage(),
            "position": self.position,
            "average_price": self.average_price,
            "fill_rate": self.fill_rate(),
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }


@dataclass
class LatencySummary:
    """Snapshot of latency statistics in milliseconds."""

    p50: Optional[float]
    p95: Optional[float]
    p99: Optional[float]
    max_latency: Optional[float]
    samples: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialise latency summary."""
        return asdict(self)


@dataclass
class RiskConsumptionSnapshot:
    """View of risk limit consumption."""

    gross_exposure: Optional[float]
    gross_exposure_limit: Optional[float]
    net_exposure: Optional[float]
    net_exposure_limit: Optional[float]
    leverage: Optional[float]
    leverage_limit: Optional[float]
    daily_loss: Optional[float]
    daily_loss_limit: Optional[float]
    per_instrument: Dict[str, Dict[str, Optional[float]]]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise risk consumption snapshot."""
        return asdict(self)


@dataclass
class RealtimeDashboardSnapshot:
    """Complete snapshot of realtime dashboard metrics."""

    timestamp: datetime
    total_realized_pnl: float
    total_unrealized_pnl: float
    daily_realized_pnl: float
    equity: float
    drawdown: float
    drawdown_pct: float
    sharpe_ratio: Optional[float]
    hit_rate: Optional[float]
    profit_factor: Optional[float]
    avg_slippage_bps: Optional[float]
    fill_rate: Optional[float]
    latency_ms: LatencySummary
    error_counts: Dict[str, int]
    risk_consumption: RiskConsumptionSnapshot
    inventory: Dict[str, float]
    per_instrument: Dict[str, Dict[str, Any]]
    circuit_breaker_active: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary suitable for JSON serialisation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["latency_ms"] = self.latency_ms.to_dict()
        data["risk_consumption"] = self.risk_consumption.to_dict()
        return data


def _percentile(values: Iterable[float], percentile: float) -> Optional[float]:
    """Compute percentile without external dependencies."""
    sorted_values = sorted(values)
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * percentile / 100
    lower_index = math.floor(k)
    upper_index = math.ceil(k)
    if lower_index == upper_index:
        return sorted_values[int(k)]
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * (k - lower_index)


class RealtimeDashboardAggregator:
    """Aggregates audit events into realtime dashboard metrics.

    The aggregator is thread-safe and intended to be shared between the
    execution engine and monitoring web service. All mutating APIs acquire an
    internal re-entrant lock to avoid inconsistent reads.
    """

    def __init__(self, config: Optional[RealtimeDashboardConfig] = None) -> None:
        self._config = config or RealtimeDashboardConfig()
        self._lock = RLock()
        self._instrument_metrics: Dict[str, InstrumentMetrics] = defaultdict(InstrumentMetrics)
        self._latencies: Deque[float] = deque(maxlen=self._config.latency_window)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._realized_total: float = 0.0
        self._unrealized_total: float = 0.0
        self._daily_realized: Dict[date, float] = defaultdict(float)
        self._equity_curve: Deque[Tuple[datetime, float]] = deque(maxlen=self._config.equity_window)
        self._returns_window: Deque[float] = deque(maxlen=self._config.sharpe_window)
        self._orders_total: int = 0
        self._fills_total: int = 0
        self._circuit_breaker_active: bool = False
        self._equity_peak: float = self._config.starting_equity
        self._last_equity: float = self._config.starting_equity

    # ------------------------------------------------------------------
    # Event ingestion methods
    # ------------------------------------------------------------------
    def record_market_data(self, snapshot: MarketDataSnapshot) -> None:
        """Handle market data events (currently placeholder for future use)."""
        # Market data updates could be used in future for inventory valuation.
        _ = snapshot  # Explicitly acknowledge parameter for linters.

    def record_signal(self, signal_event: SignalEvent) -> None:
        """Record signal events for potential confidence analytics."""
        _ = signal_event

    def record_risk_checks(self, risk_event: RiskCheckEvent) -> None:
        """Record risk check outcomes for audit and alerting."""
        failing_checks = [check for check in risk_event.checks if check.status.value != "pass"]
        if not failing_checks:
            return
        with self._lock:
            for check in failing_checks:
                key = f"risk_{check.name}_{check.status.value}"
                self._error_counts[key] += 1

    def record_order(self, order_event: OrderEvent, latency_ms: Optional[float] = None) -> None:
        """Record order submissions and optional latency measurement."""
        with self._lock:
            metrics = self._instrument_metrics[order_event.instrument]
            metrics.orders += 1
            metrics.last_update = order_event.timestamp
            self._orders_total += 1
            if latency_ms is not None:
                self._latencies.append(float(latency_ms))

    def record_fill(self, fill_event: FillEvent) -> None:
        """Record order fill events and slippage metrics."""
        with self._lock:
            metrics = self._instrument_metrics[fill_event.instrument]
            metrics.fills += 1
            metrics.slippage_samples += 1
            metrics.slippage_sum_bps += fill_event.slippage_bps
            metrics.last_update = fill_event.timestamp
            self._fills_total += 1

    def record_position_update(self, position_event: PositionUpdateEvent) -> None:
        """Update positions, realised/unrealised PnL and equity curve."""
        with self._lock:
            metrics = self._instrument_metrics[position_event.instrument]
            metrics.realized_pnl += position_event.realized_pnl
            metrics.unrealized_pnl = position_event.unrealized_pnl
            metrics.position = position_event.new_quantity
            metrics.average_price = position_event.average_price
            metrics.last_update = position_event.timestamp

            if abs(position_event.realized_pnl) > 0:
                metrics.trade_count += 1
                if position_event.realized_pnl > 0:
                    metrics.winning_trades += 1
                    metrics.gross_profit += position_event.realized_pnl
                else:
                    metrics.gross_loss += abs(position_event.realized_pnl)

            self._realized_total += position_event.realized_pnl
            self._rebuild_unrealized_total()

            event_date = position_event.timestamp.astimezone(self._config.timezone).date()
            self._daily_realized[event_date] += position_event.realized_pnl

            equity = self._config.starting_equity + self._realized_total + self._unrealized_total
            self._update_equity_curve(position_event.timestamp, equity)

    def record_latency(self, latency_ms: float) -> None:
        """Record arbitrary latency observation (e.g. order roundtrip)."""
        with self._lock:
            self._latencies.append(float(latency_ms))
            if latency_ms > self._config.max_latency_ms_threshold:
                self._error_counts["latency_sla_breach"] += 1

    def record_error(self, error_type: str, *, severity: str = "error") -> None:
        """Increment error counter for monitoring dashboards."""
        key = f"{severity}_{error_type}"
        with self._lock:
            self._error_counts[key] += 1

    def record_circuit_breaker(self, event: CircuitBreakerEvent) -> None:
        """Record circuit breaker state changes."""
        with self._lock:
            self._circuit_breaker_active = event.action in {"halt", "reduce"}
            key = f"circuit_{event.trigger_type}_{event.action}"
            self._error_counts[key] += 1

    # ------------------------------------------------------------------
    # Snapshot retrieval
    # ------------------------------------------------------------------
    def snapshot(self) -> RealtimeDashboardSnapshot:
        """Return the latest dashboard snapshot."""
        with self._lock:
            now = datetime.now(tz=self._config.timezone)
            daily_key = now.date()
            daily_realized = self._daily_realized.get(daily_key, 0.0)
            sharpe_ratio = self._compute_sharpe()
            hit_rate = self._compute_global_hit_rate()
            profit_factor = self._compute_global_profit_factor()
            avg_slippage = self._compute_global_slippage()
            fill_rate = self._compute_global_fill_rate()
            latency = self._compute_latency_summary()
            risk_snapshot = self._compute_risk_consumption()
            inventory = {ins: metrics.position for ins, metrics in self._instrument_metrics.items()}
            per_instrument = {ins: metrics.to_dict() for ins, metrics in self._instrument_metrics.items()}

            return RealtimeDashboardSnapshot(
                timestamp=now,
                total_realized_pnl=self._realized_total,
                total_unrealized_pnl=self._unrealized_total,
                daily_realized_pnl=daily_realized,
                equity=self._last_equity,
                drawdown=self._compute_drawdown(),
                drawdown_pct=self._compute_drawdown_pct(),
                sharpe_ratio=sharpe_ratio,
                hit_rate=hit_rate,
                profit_factor=profit_factor,
                avg_slippage_bps=avg_slippage,
                fill_rate=fill_rate,
                latency_ms=latency,
                error_counts=dict(self._error_counts),
                risk_consumption=risk_snapshot,
                inventory=inventory,
                per_instrument=per_instrument,
                circuit_breaker_active=self._circuit_breaker_active,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _rebuild_unrealized_total(self) -> None:
        self._unrealized_total = sum(metrics.unrealized_pnl for metrics in self._instrument_metrics.values())

    def _update_equity_curve(self, timestamp: datetime, equity: float) -> None:
        if not timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=self._config.timezone)
        self._equity_curve.append((timestamp, equity))
        if self._returns_window:
            previous_equity = self._last_equity
        else:
            previous_equity = self._config.starting_equity
        if previous_equity != 0:
            ret = (equity - previous_equity) / previous_equity
            self._returns_window.append(ret)
        self._last_equity = equity
        if equity > self._equity_peak:
            self._equity_peak = equity

    def _compute_sharpe(self) -> Optional[float]:
        if len(self._returns_window) < 2:
            return None
        mean_return = sum(self._returns_window) / len(self._returns_window)
        variance = sum((r - mean_return) ** 2 for r in self._returns_window) / (len(self._returns_window) - 1)
        if variance == 0:
            return None
        std_dev = math.sqrt(variance)
        # Assuming returns are sampled roughly every minute -> scale to annual.
        annualisation_factor = math.sqrt(252 * 24 * 60)
        return (mean_return / std_dev) * annualisation_factor

    def _compute_global_hit_rate(self) -> Optional[float]:
        total_trades = sum(metrics.trade_count for metrics in self._instrument_metrics.values())
        if total_trades == 0:
            return None
        wins = sum(metrics.winning_trades for metrics in self._instrument_metrics.values())
        return wins / total_trades

    def _compute_global_profit_factor(self) -> Optional[float]:
        gross_profit = sum(metrics.gross_profit for metrics in self._instrument_metrics.values())
        gross_loss = sum(metrics.gross_loss for metrics in self._instrument_metrics.values())
        if gross_loss == 0:
            if gross_profit == 0:
                return None
            return float("inf")
        return gross_profit / gross_loss

    def _compute_global_slippage(self) -> Optional[float]:
        total_slippage = sum(metrics.slippage_sum_bps for metrics in self._instrument_metrics.values())
        samples = sum(metrics.slippage_samples for metrics in self._instrument_metrics.values())
        if samples == 0:
            return None
        return total_slippage / samples

    def _compute_global_fill_rate(self) -> Optional[float]:
        if self._orders_total == 0:
            return None
        return min(1.0, self._fills_total / self._orders_total)

    def _compute_latency_summary(self) -> LatencySummary:
        if not self._latencies:
            return LatencySummary(None, None, None, None, 0)
        return LatencySummary(
            p50=_percentile(self._latencies, 50),
            p95=_percentile(self._latencies, 95),
            p99=_percentile(self._latencies, 99),
            max_latency=max(self._latencies),
            samples=len(self._latencies),
        )

    def _compute_drawdown(self) -> float:
        return self._equity_peak - self._last_equity

    def _compute_drawdown_pct(self) -> float:
        if self._equity_peak == 0:
            return 0.0
        return (self._equity_peak - self._last_equity) / self._equity_peak

    def _compute_risk_consumption(self) -> RiskConsumptionSnapshot:
        limits = self._config.risk_limits
        gross_exposure, net_exposure, per_instrument = self._aggregate_exposure(limits)
        leverage = self._compute_leverage_value(gross_exposure)
        daily_loss = self._current_daily_loss(limits)

        return RiskConsumptionSnapshot(
            gross_exposure=gross_exposure,
            gross_exposure_limit=limits.max_gross_exposure if limits else None,
            net_exposure=net_exposure,
            net_exposure_limit=limits.max_net_exposure if limits else None,
            leverage=leverage,
            leverage_limit=limits.max_leverage if limits else None,
            daily_loss=daily_loss,
            daily_loss_limit=limits.max_daily_loss if limits else None,
            per_instrument=per_instrument,
        )

    def _aggregate_exposure(
        self,
        limits: Optional[RiskLimitConfig],
    ) -> Tuple[float, float, Dict[str, Dict[str, Optional[float]]]]:
        gross_exposure = 0.0
        net_exposure = 0.0
        per_instrument: Dict[str, Dict[str, Optional[float]]] = {}
        for instrument, metrics in self._instrument_metrics.items():
            exposure = abs(metrics.position * metrics.average_price)
            gross_exposure += exposure
            net_exposure += metrics.position * metrics.average_price
            per_instrument[instrument] = self._build_instrument_risk_entry(
                instrument, metrics, limits, exposure
            )
        return gross_exposure, net_exposure, per_instrument

    def _build_instrument_risk_entry(
        self,
        instrument: str,
        metrics: InstrumentMetrics,
        limits: Optional[RiskLimitConfig],
        exposure: float,
    ) -> Dict[str, Optional[float]]:
        limit = limits.instrument_gross_limits.get(instrument) if limits else None
        consumption = (exposure / limit) if limit else None
        return {
            "position": metrics.position,
            "average_price": metrics.average_price,
            "gross_exposure": exposure,
            "gross_limit": limit,
            "consumption_pct": consumption,
        }

    def _compute_leverage_value(self, gross_exposure: float) -> Optional[float]:
        if self._last_equity == 0:
            return None
        return gross_exposure / self._last_equity

    def _current_daily_loss(self, limits: Optional[RiskLimitConfig]) -> Optional[float]:
        if not limits or limits.max_daily_loss is None:
            return None
        today = datetime.now(tz=self._config.timezone).date()
        return -self._daily_realized.get(today, 0.0)

    # ------------------------------------------------------------------
    # Utilities for Prometheus / Grafana exporters
    # ------------------------------------------------------------------
    def metrics_as_grafana_series(self) -> Dict[str, float]:
        """Flattened metrics for pushing into a time-series store."""
        snapshot = self.snapshot()
        data = self._base_grafana_fields(snapshot)
        data.update(self._instrument_grafana_fields(snapshot.per_instrument))
        return data

    def _base_grafana_fields(self, snapshot: RealtimeDashboardSnapshot) -> Dict[str, float]:
        fields: Dict[str, float] = {
            "realized_pnl": snapshot.total_realized_pnl,
            "unrealized_pnl": snapshot.total_unrealized_pnl,
            "equity": snapshot.equity,
            "drawdown": snapshot.drawdown,
            "drawdown_pct": snapshot.drawdown_pct,
        }
        optional_fields = {
            "sharpe_ratio": snapshot.sharpe_ratio,
            "hit_rate": snapshot.hit_rate,
            "profit_factor": snapshot.profit_factor,
            "avg_slippage_bps": snapshot.avg_slippage_bps,
            "fill_rate": snapshot.fill_rate,
            "latency_p95": snapshot.latency_ms.p95,
            "latency_p99": snapshot.latency_ms.p99,
            "latency_max": snapshot.latency_ms.max_latency,
            "leverage": snapshot.risk_consumption.leverage,
            "daily_loss": snapshot.risk_consumption.daily_loss,
        }
        for key, value in optional_fields.items():
            if value is None:
                continue
            if key == "profit_factor" and not math.isfinite(value):
                continue
            fields[key] = value
        return fields

    def _instrument_grafana_fields(self, metrics: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        series: Dict[str, float] = {}
        for instrument, values in metrics.items():
            prefix = f"instrument::{instrument}::"
            series[prefix + "realized_pnl"] = values["realized_pnl"]
            series[prefix + "unrealized_pnl"] = values["unrealized_pnl"]
            for field_name in ("hit_rate", "profit_factor", "avg_slippage_bps", "fill_rate"):
                value = values.get(field_name)
                if value is None:
                    continue
                if field_name == "profit_factor" and not math.isfinite(value):
                    continue
                series[prefix + field_name] = value
        return series


__all__ = [
    "RiskLimitConfig",
    "RealtimeDashboardConfig",
    "RealtimeDashboardAggregator",
    "RealtimeDashboardSnapshot",
    "LatencySummary",
    "RiskConsumptionSnapshot",
]
