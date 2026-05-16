"""Generate Validation Report v1 artifacts from paper-trading backtest results.

Default input uses reports/agentic_backtest_results.json and writes:
- reports/validation/validation_metrics_v1.json
- reports/validation/VALIDATION_REPORT_V1.md
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ValidationSummary:
    strategy: str
    mode: str
    capital: float
    start_date: str
    end_date: str
    trade_count: int
    wins: int
    losses: int
    win_rate: float
    win_rate_ci_low: float
    win_rate_ci_high: float
    average_win: float
    average_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_return_per_trade: float
    largest_loss: dict[str, Any] | None
    loss_patterns: dict[str, int]
    loss_tickers: dict[str, int]
    loss_regimes: dict[str, int]
    regime_breakdown: dict[str, int]
    memory_review: dict[str, Any]
    live_capital_gate: dict[str, Any]
    source_file: str
    generated_at: str
    framing_note: str


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p) / n) + ((z * z) / (4.0 * n * n)))
    return (max(0.0, center - margin), min(1.0, center + margin))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_sharpe(returns: list[float], years: float) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(var)
    if std == 0.0:
        return 0.0
    trades_per_year = max(n / max(years, 1e-6), 1e-6)
    return (mean_r / std) * math.sqrt(trades_per_year)


def _compute_max_drawdown(position_returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in position_returns:
        equity *= 1.0 + r
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, drawdown)
    return max_dd


def _parse_iso_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_summary(source: dict[str, Any], source_file: Path, default_capital: float) -> ValidationSummary:
    info = source.get("backtest_info", {})
    trades = source.get("trades", [])
    metrics = source.get("metrics", {})
    daily_logs = source.get("daily_logs", [])

    start_date = str(info.get("start_date", "unknown"))
    end_date = str(info.get("end_date", "unknown"))

    trade_returns = [_safe_float(t.get("return_pct")) for t in trades]
    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r < 0]
    n = len(trade_returns)

    wins_n = len(wins)
    losses_n = len(losses)
    win_rate = (wins_n / n) if n else 0.0
    ci_low, ci_high = _wilson_ci(wins_n, n)

    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    years = 1.0
    try:
        years = max((_parse_iso_date(end_date) - _parse_iso_date(start_date)).days / 365.25, 1.0 / 365.25)
    except Exception:
        years = 1.0

    sharpe = _compute_sharpe(trade_returns, years)

    position_returns = []
    for t in trades:
        size_pct = _safe_float(t.get("size_pct"), 1.0)
        position_returns.append(_safe_float(t.get("return_pct")) * size_pct)
    max_dd = _compute_max_drawdown(position_returns)

    avg_return_per_trade = (sum(trade_returns) / n) if n else 0.0

    largest_loss_trade = None
    if losses:
        largest_loss_trade = min(trades, key=lambda x: _safe_float(x.get("return_pct"), 0.0))

    loss_pattern_counter: Counter[str] = Counter()
    loss_ticker_counter: Counter[str] = Counter()
    loss_regime_counter: Counter[str] = Counter()
    for t in trades:
        r = _safe_float(t.get("return_pct"))
        if r < 0:
            loss_pattern_counter[str(t.get("exit_reason", "UNKNOWN"))] += 1
            loss_ticker_counter[str(t.get("ticker", "UNKNOWN"))] += 1
            loss_regime_counter[str(t.get("regime", "unknown"))] += 1

    regime_counter: Counter[str] = Counter()
    for t in trades:
        regime = str(t.get("regime", "unknown")).lower()
        regime_counter[regime] += 1

    if "normal" not in regime_counter:
        regime_counter["normal"] = 0
    if "high_vix" not in regime_counter:
        regime_counter["high_vix"] = 0
    if "spy_stress" not in regime_counter:
        regime_counter["spy_stress"] = 0
    if "unknown" not in regime_counter:
        regime_counter["unknown"] = 0

    memory_ejection_mentions = 0
    ejection_tickers: Counter[str] = Counter()
    for row in daily_logs:
        ticker = str(row.get("ticker", "UNKNOWN"))
        agents = row.get("agent_results", {}).get("agents", {})
        for agent_name, agent_data in agents.items():
            note = str(agent_data.get("note", ""))
            if "eject" in note.lower():
                memory_ejection_mentions += 1
                ejection_tickers[ticker] += 1

    before_wr = _safe_float(metrics.get("phase25_win_rate"), 0.0)
    after_wr = _safe_float(metrics.get("win_rate"), win_rate)
    memory_review = {
        "before_memory_hooks": {
            "win_rate": before_wr,
            "trade_sample": int(_safe_float(metrics.get("phase25_trades"), 0)),
        },
        "after_memory_hooks": {
            "win_rate": after_wr,
            "trade_sample": n,
        },
        "ejection_candidates": dict(ejection_tickers),
        "ejection_event_mentions": memory_ejection_mentions,
        "behavior_assessment": (
            "Sensible based on repeated low-win-rate ejection notes"
            if memory_ejection_mentions > 0
            else "No explicit ejection events found in provided logs"
        ),
    }

    gate_decision = "Fail"
    required_evidence = [
        "Increase completed paper trade sample to >= 30",
        "Sustain positive profit factor and stable drawdown across regimes",
        "Demonstrate memory/ejector impact over a larger sample",
        "Provide slippage/liquidity stress checks",
    ]
    hard_stops = [
        "Disable live capital if max drawdown exceeds 10%",
        "Disable live capital if 95% CI lower bound for win rate falls below 0.50",
        "Disable live capital on repeated unresolved broker/execution errors",
    ]
    if n >= 30 and ci_low >= 0.50 and profit_factor >= 1.5 and max_dd <= 0.10:
        gate_decision = "Pass"
        required_evidence = ["Continue monitoring with rolling weekly validation updates"]
    elif n >= 15 and profit_factor >= 1.2 and max_dd <= 0.15:
        gate_decision = "Conditional"

    return ValidationSummary(
        strategy="BounceHunter Agentic (backtest validation from agentic_backtest_results)",
        mode="Backtest validation artifact",
        capital=default_capital,
        start_date=start_date,
        end_date=end_date,
        trade_count=n,
        wins=wins_n,
        losses=losses_n,
        win_rate=win_rate,
        win_rate_ci_low=ci_low,
        win_rate_ci_high=ci_high,
        average_win=avg_win,
        average_loss=avg_loss,
        profit_factor=profit_factor,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        avg_return_per_trade=avg_return_per_trade,
        largest_loss=largest_loss_trade,
        loss_patterns=dict(loss_pattern_counter),
        loss_tickers=dict(loss_ticker_counter),
        loss_regimes=dict(loss_regime_counter),
        regime_breakdown={
            "normal": regime_counter["normal"],
            "high_vix": regime_counter["high_vix"],
            "spy_stress": regime_counter["spy_stress"],
            "unknown": regime_counter["unknown"],
        },
        memory_review=memory_review,
        live_capital_gate={
            "decision": gate_decision,
            "required_evidence_before_live_use": required_evidence,
            "hard_stop_conditions": hard_stops,
        },
        source_file=str(source_file),
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        framing_note=(
            "Validation Report v1 is a reproducible backtest validation artifact. "
            "It does not replace Phase 2 paper-trading validation. "
            "Live capital remains blocked until paper-trade sample validation is complete."
        ),
    )


def write_outputs(summary: ValidationSummary, markdown_path: Path, metrics_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_payload = {
        "scope": {
            "strategy": summary.strategy,
            "mode": summary.mode,
            "framing_note": summary.framing_note,
            "capital": summary.capital,
            "date_range": {"start": summary.start_date, "end": summary.end_date},
            "trade_sample_size": summary.trade_count,
            "source_file": summary.source_file,
            "generated_at": summary.generated_at,
        },
        "executive_verdict": summary.live_capital_gate["decision"],
        "core_metrics": {
            "total_trades": summary.trade_count,
            "wins": summary.wins,
            "losses": summary.losses,
            "win_rate": summary.win_rate,
            "win_rate_confidence_interval": {
                "low": summary.win_rate_ci_low,
                "high": summary.win_rate_ci_high,
                "method": "wilson_95",
            },
            "average_win": summary.average_win,
            "average_loss": summary.average_loss,
            "profit_factor": summary.profit_factor,
            "sharpe_ratio": summary.sharpe_ratio,
            "max_drawdown": summary.max_drawdown,
            "average_return_per_trade": summary.avg_return_per_trade,
        },
        "loss_analysis": {
            "largest_loss": summary.largest_loss,
            "repeated_failure_patterns": summary.loss_patterns,
            "tickers_responsible_for_losses": summary.loss_tickers,
            "regime_during_losses": summary.loss_regimes,
            "slippage_or_liquidity_notes": "No explicit slippage/liquidity loss note in source trades; investigate separately.",
        },
        "regime_breakdown": summary.regime_breakdown,
        "memory_auto_ejector_review": summary.memory_review,
        "live_capital_gate": summary.live_capital_gate,
    }

    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    largest_loss_line = "N/A"
    if summary.largest_loss:
        largest_loss_line = (
            f"{summary.largest_loss.get('ticker')} on {summary.largest_loss.get('entry_date')} "
            f"({summary.largest_loss.get('return_pct'):.2%})"
        )

    md = f"""# AutoTrader Validation Report v1

## Scope
Strategy: {summary.strategy}
Mode: {summary.mode}
Framing: {summary.framing_note}
Capital: ${summary.capital:,.2f}
Date range: {summary.start_date} to {summary.end_date}
Trade sample size: {summary.trade_count}

## Executive Verdict
{summary.live_capital_gate['decision']} for live-capital eligibility.

## Core Metrics
- Total trades: {summary.trade_count}
- Wins: {summary.wins}
- Losses: {summary.losses}
- Win rate: {summary.win_rate:.2%}
- Win rate confidence interval: [{summary.win_rate_ci_low:.2%}, {summary.win_rate_ci_high:.2%}] (Wilson 95%)
- Average win: {summary.average_win:.2%}
- Average loss: {summary.average_loss:.2%}
- Profit factor: {summary.profit_factor:.3f}
- Sharpe ratio: {summary.sharpe_ratio:.3f}
- Max drawdown: {summary.max_drawdown:.2%}
- Average return per trade: {summary.avg_return_per_trade:.2%}

## Loss Analysis
- Largest loss: {largest_loss_line}
- Repeated failure patterns: {summary.loss_patterns}
- Tickers responsible for losses: {summary.loss_tickers}
- Regime during losses: {summary.loss_regimes}
- Slippage or liquidity notes: No explicit slippage/liquidity loss note in source trades; investigate separately.

## Regime Breakdown
- Normal regime: {summary.regime_breakdown.get('normal', 0)}
- High VIX regime: {summary.regime_breakdown.get('high_vix', 0)}
- SPY stress regime: {summary.regime_breakdown.get('spy_stress', 0)}
- Unknown regime: {summary.regime_breakdown.get('unknown', 0)}

## Memory / Auto-Ejector Review
- Before memory hooks: win rate {summary.memory_review['before_memory_hooks']['win_rate']:.2%} over {summary.memory_review['before_memory_hooks']['trade_sample']} samples
- After memory hooks: win rate {summary.memory_review['after_memory_hooks']['win_rate']:.2%} over {summary.memory_review['after_memory_hooks']['trade_sample']} samples
- Ejection candidates: {summary.memory_review['ejection_candidates']}
- Whether ejection logic behaved sensibly: {summary.memory_review['behavior_assessment']}

## Live Capital Gate
Decision: {summary.live_capital_gate['decision']}
Required evidence before live use:
"""

    for item in summary.live_capital_gate["required_evidence_before_live_use"]:
        md += f"- {item}\n"

    md += "Hard stop conditions:\n"
    for item in summary.live_capital_gate["hard_stop_conditions"]:
        md += f"- {item}\n"

    md += f"""

## Conclusion
Validation artifacts generated from {summary.source_file}. Current sample supports a {summary.live_capital_gate['decision']} verdict; expand sample size and regime coverage before any live-capital claim.

{summary.framing_note}
"""

    markdown_path.write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Validation Report v1 artifacts")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports") / "agentic_backtest_results.json",
        help="Input JSON with trade-level backtest results",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Paper-trading capital used in report scope",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("reports") / "validation" / "VALIDATION_REPORT_V1.md",
        help="Output markdown report path",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("reports") / "validation" / "validation_metrics_v1.json",
        help="Output JSON metrics path",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    source = json.loads(args.input.read_text(encoding="utf-8"))
    summary = build_summary(source, args.input, args.capital)
    write_outputs(summary, args.markdown_output, args.metrics_output)

    print(f"Wrote markdown report: {args.markdown_output}")
    print(f"Wrote metrics json: {args.metrics_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
