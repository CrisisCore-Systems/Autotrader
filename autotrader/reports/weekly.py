"""Weekly research report generation utilities for Phase 12.

This module produces institutional-style weekly reports by combining audit
trail data, post-trade analytics, and anomaly statistics. The goal is to give
quantitative researchers and risk officers a one-stop artefact summarising
strategy performance, execution quality, and market context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import logging

import numpy as np
import pandas as pd

from autotrader.analytics.pnl_attribution import PnLAttributor, Trade
from autotrader.analytics.slippage import SlippageAnalyzer
from autotrader.audit.trail import (
    AuditTrailStore,
    EventType,
    FillEvent,
    OrderEvent,
    PositionUpdateEvent,
    get_audit_trail,
)


logger = logging.getLogger(__name__)


@dataclass
class WeeklyReportConfig:
    """Configuration parameters for weekly research reports."""

    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    timezone: timezone = timezone.utc
    starting_equity: float = 1_000_000.0
    top_n_instruments: int = 10
    include_trade_examples: int = 5

    def resolve_window(self) -> Tuple[datetime, datetime]:
        """Return (start, end) datetimes with sane defaults."""
        end = self.period_end or datetime.now(tz=self.timezone)
        start = self.period_start or (end - timedelta(days=7))
        if start >= end:
            raise ValueError("period_start must be before period_end")
        return start, end


@dataclass
class WeeklyReport:
    """Materialised weekly report ready for export."""

    generated_at: datetime
    period_start: datetime
    period_end: datetime
    summary_metrics: Dict[str, Any]
    highlights: List[str]
    tables: Dict[str, pd.DataFrame]
    trade_examples: List[Trade] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the weekly report as Markdown text."""
        lines: List[str] = []
        self._append_header(lines)
        self._append_summary_section(lines)
        self._append_highlights_section(lines)
        self._append_tables_section(lines)
        self._append_examples_section(lines)
        return "\n".join(lines)

    def _append_header(self, lines: List[str]) -> None:
        lines.append("# Weekly Research Report")
        lines.append(
            f"**Coverage:** {self.period_start.isoformat()} → {self.period_end.isoformat()}"
        )
        lines.append(f"**Generated:** {self.generated_at.isoformat()}")
        lines.append("")

    def _append_summary_section(self, lines: List[str]) -> None:
        lines.append("## Executive Summary")
        for key, value in self.summary_metrics.items():
            formatted = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            lines.append(f"- **{key.replace('_', ' ').title()}:** {formatted}")
        lines.append("")

    def _append_highlights_section(self, lines: List[str]) -> None:
        if not self.highlights:
            return
        lines.append("## Highlights")
        for highlight in self.highlights:
            lines.append(f"- {highlight}")
        lines.append("")

    def _append_tables_section(self, lines: List[str]) -> None:
        for title, df in self.tables.items():
            lines.append(f"## {title}")
            if df.empty:
                lines.append("_No data available for this period._")
            else:
                lines.append(_render_table(df))
            lines.append("")

    def _append_examples_section(self, lines: List[str]) -> None:
        if not self.trade_examples:
            return
        lines.append("## Notable Trades")
        for trade in self.trade_examples:
            lines.extend(_format_trade_example(trade))
            lines.append("")


class WeeklyReportGenerator:
    """Generate weekly research reports from audit trail events."""

    def __init__(
        self,
        audit_trail: Optional[AuditTrailStore] = None,
        pnl_attributor: Optional[PnLAttributor] = None,
        slippage_analyzer: Optional[SlippageAnalyzer] = None,
    ) -> None:
        self._audit_trail = audit_trail or get_audit_trail()
        self._pnl_attributor = pnl_attributor or PnLAttributor()
        self._slippage_analyzer = slippage_analyzer or SlippageAnalyzer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self, config: WeeklyReportConfig) -> WeeklyReport:
        """Generate the full weekly report."""
        start, end = config.resolve_window()
        logger.info("Generating weekly report for %s → %s", start, end)

        trades, fills = self._extract_trades(start, end, tz=config.timezone)
        summary = self._compute_summary_metrics(trades, config)
        tables = self._build_tables(trades, fills, config)
        highlights = self._build_highlights(summary, tables)
        examples = trades[: config.include_trade_examples]

        report = WeeklyReport(
            generated_at=datetime.now(tz=config.timezone),
            period_start=start,
            period_end=end,
            summary_metrics=summary,
            highlights=highlights,
            tables=tables,
            trade_examples=examples,
        )
        logger.info("Weekly report generated with %d trades", len(trades))
        return report

    # ------------------------------------------------------------------
    # Trade reconstruction
    # ------------------------------------------------------------------
    def _extract_trades(
        self,
        start: datetime,
        end: datetime,
        tz: timezone,
    ) -> Tuple[List[Trade], List[FillEvent]]:
        signal_events = self._audit_trail.query_events(
            event_type=EventType.SIGNAL,
            start_time=start,
            end_time=end,
        )
        trades: List[Trade] = []
        fills: List[FillEvent] = []
        for event in signal_events:
            signal_data = event["data"]
            signal_id = signal_data["signal_id"]
            history = self._audit_trail.reconstruct_trade_history(signal_id)
            trade, trade_fills = self._build_trade(signal_data, history, tz)
            if trade is None:
                continue
            trades.append(trade)
            fills.extend(trade_fills)
        trades.sort(key=lambda t: t.exit_time)
        return trades, fills

    def _build_trade(
        self,
        signal_data: Dict[str, Any],
        history: Dict[str, List[Dict[str, Any]]],
        tz: timezone,
    ) -> Tuple[Optional[Trade], List[FillEvent]]:
        fills, position_updates, orders = self._parse_history_lists(history, tz)
        if not fills or not position_updates:
            return None, []

        total_realized = sum(p.realized_pnl for p in position_updates)
        if not self._trade_is_closed(total_realized):
            return None, []

        trade_kwargs = self._trade_core_stats(
            signal_data=signal_data,
            fills=fills,
            position_updates=position_updates,
            orders=orders,
            total_realized=total_realized,
        )
        trade = Trade(**trade_kwargs)
        return trade, fills

    def _parse_history_lists(
        self,
        history: Dict[str, List[Dict[str, Any]]],
        tz: timezone,
    ) -> Tuple[List[FillEvent], List[PositionUpdateEvent], List[OrderEvent]]:
        fills = [_parse_fill(e["data"], tz) for e in history.get("fills", [])]
        position_updates = [
            _parse_position_update(e["data"], tz) for e in history.get("position_updates", [])
        ]
        orders = [_parse_order(e["data"], tz) for e in history.get("orders", [])]
        fills.sort(key=lambda f: f.timestamp)
        position_updates.sort(key=lambda p: p.timestamp)
        return fills, position_updates, orders

    @staticmethod
    def _trade_is_closed(total_realized: float) -> bool:
        return abs(total_realized) >= 1e-9

    def _trade_core_stats(
        self,
        signal_data: Dict[str, Any],
        fills: List[FillEvent],
        position_updates: List[PositionUpdateEvent],
        orders: List[OrderEvent],
        total_realized: float,
    ) -> Dict[str, Any]:
        entry_time = fills[0].timestamp
        exit_time = position_updates[-1].timestamp
        quantity = sum(f.quantity for f in fills)
        avg_entry_price = _weighted_average_price(fills)
        exit_price = position_updates[-1].average_price
        pnl_pct = total_realized / (abs(avg_entry_price * quantity) + 1e-9)
        slippage_bps = float(np.mean([f.slippage_bps for f in fills])) if fills else 0.0
        side = orders[0].side if orders else fills[0].side
        fees = sum(f.fee for f in fills)
        features = signal_data.get("features", {})
        regime = features.get("regime") or features.get("regime_label")
        return {
            "trade_id": signal_data.get("trade_id", signal_data["signal_id"]),
            "signal_id": signal_data["signal_id"],
            "instrument": fills[0].instrument,
            "side": side,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": avg_entry_price,
            "exit_price": exit_price,
            "quantity": abs(quantity),
            "pnl": total_realized,
            "pnl_pct": pnl_pct * 100,
            "fees": fees,
            "slippage_bps": slippage_bps,
            "holding_period_seconds": (exit_time - entry_time).total_seconds(),
            "features": features,
            "regime": regime,
        }

    # ------------------------------------------------------------------
    # Metrics & tables
    # ------------------------------------------------------------------
    def _compute_summary_metrics(
        self,
        trades: List[Trade],
        config: WeeklyReportConfig,
    ) -> Dict[str, Any]:
        if not trades:
            return self._empty_summary()

        total_pnl = sum(trade.pnl for trade in trades)
        wins, losses = self._win_loss_buckets(trades)
        gross_profit = sum(trade.pnl for trade in wins)
        gross_loss = abs(sum(trade.pnl for trade in losses))
        win_rate = len(wins) / len(trades)
        avg_slippage = float(np.mean([trade.slippage_bps for trade in trades]))
        sharpe, drawdown = self._equity_curve_stats(trades, config.starting_equity)

        return {
            "total_trades": len(trades),
            "total_pnl": total_pnl,
            "win_rate": win_rate * 100,
            "avg_trade_pnl": total_pnl / len(trades),
            "profit_factor": self._profit_factor(gross_profit, gross_loss),
            "sharpe_ratio": sharpe,
            "max_drawdown": drawdown,
            "avg_slippage_bps": avg_slippage,
        }

    def _build_tables(
        self,
        trades: List[Trade],
        fills: List[FillEvent],
        config: WeeklyReportConfig,
    ) -> Dict[str, pd.DataFrame]:
        tables: Dict[str, pd.DataFrame] = {}
        if not trades:
            titles = [
                "PnL By Instrument",
                "PnL By Factor",
                "PnL By Holding Horizon",
                "PnL By Time Of Day",
                "PnL By Regime",
                "Slippage Summary",
            ]
            for title in titles:
                tables[title] = pd.DataFrame()
            return tables

        tables["PnL By Instrument"] = self._pnl_attributor.attribute_by_instrument(trades).head(
            config.top_n_instruments
        )
        tables["PnL By Factor"] = self._pnl_attributor.attribute_by_factor(trades)
        tables["PnL By Holding Horizon"] = self._pnl_attributor.attribute_by_horizon(trades)
        tables["PnL By Time Of Day"] = self._pnl_attributor.attribute_by_time(trades)
        tables["PnL By Regime"] = self._pnl_attributor.attribute_by_regime(trades)
        tables["Slippage Summary"] = self._build_slippage_table(fills)
        return tables

    def _build_slippage_table(self, fills: List[FillEvent]) -> pd.DataFrame:
        if not fills:
            return pd.DataFrame()
        df = self._slippage_dataframe(fills)
        return self._summarise_slippage(df)

    @staticmethod
    def _slippage_dataframe(fills: List[FillEvent]) -> pd.DataFrame:
        data = {
            "instrument": [fill.instrument for fill in fills],
            "timestamp": [fill.timestamp for fill in fills],
            "side": [fill.side for fill in fills],
            "quantity": [fill.quantity for fill in fills],
            "price": [fill.price for fill in fills],
            "slippage_bps": [fill.slippage_bps for fill in fills],
            "fee": [fill.fee for fill in fills],
        }
        return pd.DataFrame(data)

    @staticmethod
    def _summarise_slippage(df: pd.DataFrame) -> pd.DataFrame:
        grouped = df.groupby("instrument").agg(
            trades=("instrument", "count"),
            avg_slippage_bps=("slippage_bps", "mean"),
            total_fee=("fee", "sum"),
            avg_quantity=("quantity", "mean"),
        )
        grouped = grouped.sort_values("avg_slippage_bps", ascending=False)
        return grouped.reset_index()

    def _build_highlights(
        self,
        summary: Dict[str, Any],
        tables: Dict[str, pd.DataFrame],
    ) -> List[str]:
        highlights: List[str] = []
        if summary.get("total_trades") == 0:
            highlights.append("No trades executed during the period.")
            return highlights

        top_instruments = tables.get("PnL By Instrument", pd.DataFrame())
        if not top_instruments.empty:
            best_row = top_instruments.iloc[0]
            highlights.append(
                f"Top instrument: {best_row['instrument']} with PnL ${best_row['pnl']:.2f}"
            )
            if len(top_instruments) > 1:
                worst_row = top_instruments.iloc[-1]
                highlights.append(
                    f"Lagging instrument: {worst_row['instrument']} with PnL ${worst_row['pnl']:.2f}"
                )

        factor_table = tables.get("PnL By Factor", pd.DataFrame())
        if not factor_table.empty:
            positive = factor_table[factor_table["pnl"] > 0].sort_values("pnl", ascending=False)
            negative = factor_table[factor_table["pnl"] < 0].sort_values("pnl")
            if not positive.empty:
                best_factor = positive.iloc[0]
                highlights.append(
                    f"Best factor: {best_factor['factor']} contributed ${best_factor['pnl']:.2f}."
                )
            if not negative.empty:
                worst_factor = negative.iloc[0]
                highlights.append(
                    f"Worst factor: {worst_factor['factor']} dragged ${worst_factor['pnl']:.2f}."
                )

        if summary.get("avg_slippage_bps") is not None:
            highlights.append(
                f"Average slippage: {summary['avg_slippage_bps']:.2f} bps across all fills."
            )
        return highlights

    # ------------------------------------------------------------------
    # Helper computations
    # ------------------------------------------------------------------
    @staticmethod
    def _empty_summary() -> Dict[str, Any]:
        return {
            "total_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_trade_pnl": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "avg_slippage_bps": 0.0,
        }

    @staticmethod
    def _win_loss_buckets(trades: List[Trade]) -> Tuple[List[Trade], List[Trade]]:
        wins = [trade for trade in trades if trade.pnl > 0]
        losses = [trade for trade in trades if trade.pnl < 0]
        return wins, losses

    @staticmethod
    def _profit_factor(gross_profit: float, gross_loss: float) -> float:
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def _equity_curve_stats(
        self,
        trades: List[Trade],
        starting_equity: float,
    ) -> Tuple[float, float]:
        equity_curve = self._build_equity_curve(trades, starting_equity)
        sharpe = self._compute_sharpe(equity_curve)
        drawdown = self._compute_max_drawdown(equity_curve)
        return sharpe, drawdown

    @staticmethod
    def _build_equity_curve(trades: List[Trade], starting_equity: float) -> List[Tuple[datetime, float]]:
        equity = starting_equity
        curve: List[Tuple[datetime, float]] = []
        for trade in sorted(trades, key=lambda t: t.exit_time):
            equity += trade.pnl
            curve.append((trade.exit_time, equity))
        return curve

    @staticmethod
    def _compute_sharpe(curve: List[Tuple[datetime, float]]) -> float:
        if len(curve) < 2:
            return 0.0
        equities = np.array([value for _, value in curve])
        returns = np.diff(equities) / equities[:-1]
        if returns.std() == 0:
            return 0.0
        annualisation_factor = np.sqrt(52)  # Weekly sampling approximated
        return float(returns.mean() / returns.std() * annualisation_factor)

    @staticmethod
    def _compute_max_drawdown(curve: List[Tuple[datetime, float]]) -> float:
        if not curve:
            return 0.0
        peak = curve[0][1]
        max_drawdown = 0.0
        for _, equity in curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown


# ----------------------------------------------------------------------
# Utility parsing helpers
# ----------------------------------------------------------------------

def _parse_timestamp(value: str, tz: timezone) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def _parse_fill(data: Dict[str, Any], tz: timezone) -> FillEvent:
    return FillEvent(
        timestamp=_parse_timestamp(data["timestamp"], tz),
        fill_id=data["fill_id"],
        order_id=data["order_id"],
        instrument=data["instrument"],
        side=data["side"],
        quantity=float(data["quantity"]),
        price=float(data["price"]),
        fee=float(data.get("fee", 0.0)),
        fee_currency=data.get("fee_currency", "USD"),
        liquidity=data.get("liquidity", "unknown"),
        slippage_bps=float(data.get("slippage_bps", 0.0)),
        market_price_at_fill=float(data.get("market_price_at_fill")) if data.get("market_price_at_fill") is not None else None,
    )


def _parse_position_update(data: Dict[str, Any], tz: timezone) -> PositionUpdateEvent:
    return PositionUpdateEvent(
        timestamp=_parse_timestamp(data["timestamp"], tz),
        instrument=data["instrument"],
        previous_quantity=float(data.get("previous_quantity", 0.0)),
        new_quantity=float(data.get("new_quantity", 0.0)),
        average_price=float(data.get("average_price", 0.0)),
        unrealized_pnl=float(data.get("unrealized_pnl", 0.0)),
        realized_pnl=float(data.get("realized_pnl", 0.0)),
        reason=data.get("reason", "fill"),
    )


def _parse_order(data: Dict[str, Any], tz: timezone) -> OrderEvent:
    return OrderEvent(
        timestamp=_parse_timestamp(data["timestamp"], tz),
        order_id=data["order_id"],
        signal_id=data.get("signal_id", ""),
        instrument=data["instrument"],
        side=data.get("side", "buy"),
        quantity=float(data.get("quantity", 0.0)),
        order_type=data.get("order_type", "market"),
        limit_price=float(data.get("limit_price")) if data.get("limit_price") is not None else None,
        stop_price=float(data.get("stop_price")) if data.get("stop_price") is not None else None,
        status=data.get("status", "submitted"),
        exchange_order_id=data.get("exchange_order_id"),
        reason=data.get("reason"),
    )


def _weighted_average_price(fills: List[FillEvent]) -> float:
    total_quantity = sum(abs(f.quantity) for f in fills)
    if total_quantity == 0:
        return 0.0
    return sum(f.price * abs(f.quantity) for f in fills) / total_quantity


def _format_trade_example(trade: Trade) -> List[str]:
    return [
        f"- **{trade.instrument}** {trade.side.upper()} trade",  # headline
        f"  - Entry: {trade.entry_time.isoformat()} @ {trade.entry_price:.2f}",
        f"  - Exit: {trade.exit_time.isoformat()} @ {trade.exit_price:.2f}",
        f"  - PnL: ${trade.pnl:.2f} ({trade.pnl_pct:.2f}%)",  # pnl
        f"  - Holding: {trade.holding_period_seconds/60:.1f} minutes",  # holding
        f"  - Slippage: {trade.slippage_bps:.2f} bps | Fees: ${trade.fees:.2f}",
    ]


def _render_table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except Exception:  # pragma: no cover - fallback when optional deps missing
        return df.to_string(index=False)
