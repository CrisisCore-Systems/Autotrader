#!/usr/bin/env python3
"""
Phase 2 validation status checker and report generator.

This script:
1. Loads cumulative trade history
2. Identifies trades from Phase 2 optimization deployment (2025-10-20 onwards)
3. Calculates milestone status and validation metrics
4. Writes machine-readable and Markdown validation report artifacts

Usage:
    python scripts/check_validation_status.py
    python scripts/check_validation_status.py --json-out reports/phase2_validation_report.json
"""

import argparse
import json
import math
from pathlib import Path
from datetime import datetime
from statistics import NormalDist
from typing import Dict, List, Optional, Tuple

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
HISTORY_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"
PAPER_TRADES_FILE = PROJECT_ROOT / "reports" / "pennyhunter_paper_trades.json"
DEFAULT_JSON_REPORT = PROJECT_ROOT / "reports" / "phase2_validation_report.json"
DEFAULT_MARKDOWN_REPORT = PROJECT_ROOT / "reports" / "phase2_validation_report.md"

# Phase 2 optimization deployment date
PHASE2_DEPLOYMENT_DATE = "2025-10-20"

# Validation milestones
MILESTONES = {
    5: {"target_wr": 0.60, "min_wins": 3, "name": "Initial Validation"},
    10: {"target_wr": 0.70, "min_wins": 7, "name": "Intermediate Validation"},
    20: {"target_wr": 0.70, "min_wins": 14, "name": "Phase 2.5 Approval"},
}

CLOSED_STATUSES = {"completed", "closed"}


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-ish timestamps used by the paper trading reports."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def safe_float(value, default: float = 0.0) -> float:
    """Convert potentially missing numeric values to float."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def trade_volume_multiple(trade: Dict) -> float:
    """Read volume multiplier from either the old or new trade field."""
    return safe_float(trade.get("vol_mult", trade.get("vol_spike")))


def trade_signal_date(trade: Dict) -> str:
    """Return the signal date for a trade, deriving it from signal_id when needed."""
    explicit = trade.get("signal_date") or trade.get("date")
    if explicit:
        return str(explicit)

    signal_id = str(trade.get("signal_id") or "")
    parts = signal_id.split("_")
    if len(parts) >= 3:
        candidate = parts[1]
        if len(candidate) == 10 and candidate.count("-") == 2:
            return candidate

    entry_time = parse_datetime(trade.get("entry_time"))
    return entry_time.strftime("%Y-%m-%d") if entry_time else "UNKNOWN"


def trade_setup_key(trade: Dict) -> str:
    """Build a stable identity for one historical setup across repeated runs."""
    ticker = str(trade.get("ticker") or "UNKNOWN")
    signal_type = str(trade.get("signal_type") or "UNKNOWN")
    signal_date = trade_signal_date(trade)
    if signal_date != "UNKNOWN":
        return f"{ticker}|{signal_type}|{signal_date}"

    entry_price = round(safe_float(trade.get("entry_price")), 4)
    gap_pct = round(safe_float(trade.get("gap_pct")), 2)
    vol_mult = round(trade_volume_multiple(trade), 2)
    return f"{ticker}|{signal_type}|{entry_price}|{gap_pct}|{vol_mult}"


def dedupe_trade_setups(trades: List[Dict]) -> List[Dict]:
    """Keep the latest record for each historical setup so replayed runs do not inflate counts."""
    deduped: Dict[str, Dict] = {}
    for trade in trades:
        deduped[trade_setup_key(trade)] = trade
    return list(deduped.values())


def load_paper_trade_report() -> Dict:
    """Load the latest one-shot paper trading report when present."""
    if not PAPER_TRADES_FILE.exists():
        return {}

    with open(PAPER_TRADES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_trades() -> List[Dict]:
    """Load cumulative trade history and current paper trades."""
    all_trades = []
    
    # Load historical cumulative trades
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
        all_trades.extend(data.get('trades', []))
    
    # Load current paper trades (may have TODAY's trades not yet in cumulative)
    if PAPER_TRADES_FILE.exists():
        with open(PAPER_TRADES_FILE, 'r') as f:
            paper_data = json.load(f)
        paper_trades = paper_data.get('trades', [])
        
        # Only add if not duplicates (check by ticker + entry_time)
        existing_keys = {(t.get('ticker'), t.get('entry_time')) for t in all_trades if t.get('ticker')}
        for pt in paper_trades:
            key = (pt.get('ticker'), pt.get('entry_time'))
            if key not in existing_keys:
                all_trades.append(pt)
    
    return all_trades


def load_session_markers() -> List[Dict]:
    """Load cumulative session markers for audit-trend reporting."""
    if not HISTORY_FILE.exists():
        return []

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    deployment_dt = datetime.fromisoformat(PHASE2_DEPLOYMENT_DATE)
    markers = []
    for item in data.get('trades', []):
        if item.get('type') != 'session_marker':
            continue
        marker_dt = parse_datetime(item.get('date'))
        if marker_dt and marker_dt >= deployment_dt:
            markers.append(item)

    return markers


def filter_post_optimization_trades(trades: List[Dict]) -> List[Dict]:
    """Filter trades from Phase 2 optimization deployment onwards."""
    deployment_dt = datetime.fromisoformat(PHASE2_DEPLOYMENT_DATE)
    
    post_opt_trades = []
    for trade in trades:
        # Skip session markers
        if trade.get('type') == 'session_marker':
            continue
        
        # Check entry time
        entry_time = trade.get('entry_time')
        if not entry_time:
            continue
        
        try:
            # Parse trade datetime and strip timezone for comparison
            trade_dt_str = entry_time.replace('Z', '+00:00')
            trade_dt = datetime.fromisoformat(trade_dt_str)
            
            # Convert to naive datetime for comparison
            if trade_dt.tzinfo is not None:
                trade_dt = trade_dt.replace(tzinfo=None)
            
            if trade_dt >= deployment_dt:
                post_opt_trades.append(trade)
        except Exception as e:
            # Silently skip unparseable dates (likely old format)
            continue
    
    return dedupe_trade_setups(post_opt_trades)


def wilson_confidence_interval(wins: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Return Wilson score confidence interval for win rate."""
    if total == 0:
        return 0.0, 0.0

    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    phat = wins / total
    denominator = 1 + (z**2 / total)
    center = (phat + z**2 / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((phat * (1 - phat) / total) + (z**2 / (4 * total**2)))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def calculate_max_drawdown(pnls: List[float]) -> float:
    """Calculate max drawdown from cumulative P&L sequence."""
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)

    return max_drawdown


def summarize_bucket(trades: List[Dict], key: str) -> List[Dict]:
    """Summarize closed trades by a categorical key such as ticker or regime."""
    grouped: Dict[str, List[Dict]] = {}
    for trade in trades:
        bucket = str(trade.get(key) or "UNKNOWN")
        grouped.setdefault(bucket, []).append(trade)

    summary = []
    for bucket, bucket_trades in sorted(grouped.items()):
        wins = sum(1 for trade in bucket_trades if safe_float(trade.get("pnl")) > 0)
        total_pnl = sum(safe_float(trade.get("pnl")) for trade in bucket_trades)
        summary.append(
            {
                "name": bucket,
                "trades": len(bucket_trades),
                "wins": wins,
                "losses": len(bucket_trades) - wins,
                "win_rate": wins / len(bucket_trades) if bucket_trades else 0.0,
                "total_pnl": total_pnl,
                "avg_return_pct": sum(safe_float(trade.get("return_pct")) for trade in bucket_trades) / len(bucket_trades)
                if bucket_trades
                else 0.0,
            }
        )

    return summary


def summarize_signal_setups(trades: List[Dict]) -> List[Dict]:
    """Summarize trades by unique ticker + signal date setup."""
    grouped: Dict[str, List[Dict]] = {}
    for trade in trades:
        name = f"{trade.get('ticker', 'UNKNOWN')}@{trade_signal_date(trade)}"
        grouped.setdefault(name, []).append(trade)

    summary = []
    for name, bucket_trades in sorted(grouped.items()):
        wins = sum(1 for trade in bucket_trades if safe_float(trade.get("pnl")) > 0)
        total_pnl = sum(safe_float(trade.get("pnl")) for trade in bucket_trades)
        summary.append(
            {
                "name": name,
                "trades": len(bucket_trades),
                "wins": wins,
                "losses": len(bucket_trades) - wins,
                "win_rate": wins / len(bucket_trades) if bucket_trades else 0.0,
                "total_pnl": total_pnl,
            }
        )

    return summary


def summarize_recent_rejections(rejected_signals: List[Dict]) -> Dict[str, List[Dict]]:
    """Aggregate recent rejected signals by stage and failing check."""
    by_stage: Dict[str, Dict[str, int]] = {}
    by_check: Dict[str, Dict[str, object]] = {}

    for rejected in rejected_signals:
        stage = str(rejected.get("stage") or "UNKNOWN")
        stage_bucket = by_stage.setdefault(stage, {"count": 0})
        stage_bucket["count"] += 1

        for reason in rejected.get("reasons", []):
            check_name = str(reason.get("check") or "UNKNOWN")
            check_bucket = by_check.setdefault(
                check_name,
                {
                    "count": 0,
                    "latest_reason": None,
                },
            )
            check_bucket["count"] += 1
            if reason.get("reason"):
                check_bucket["latest_reason"] = reason.get("reason")

    return {
        "by_stage": [
            {"name": name, "count": data["count"]}
            for name, data in sorted(by_stage.items(), key=lambda item: (-item[1]["count"], item[0]))
        ],
        "by_check": [
            {
                "name": name,
                "count": data["count"],
                "latest_reason": data["latest_reason"],
            }
            for name, data in sorted(by_check.items(), key=lambda item: (-item[1]["count"], item[0]))
        ],
    }


def summarize_scan_near_misses(scan_near_misses: List[Dict]) -> Dict[str, List[Dict]]:
    """Aggregate recent scan near misses by reason."""
    by_reason: Dict[str, Dict[str, object]] = {}

    for diagnostic in scan_near_misses:
        reason = str(diagnostic.get("reason") or "UNKNOWN")
        reason_bucket = by_reason.setdefault(
            reason,
            {
                "count": 0,
                "latest_ticker": None,
                "latest_date": None,
            },
        )
        reason_bucket["count"] += 1
        if diagnostic.get("ticker"):
            reason_bucket["latest_ticker"] = diagnostic.get("ticker")
        if diagnostic.get("date"):
            reason_bucket["latest_date"] = diagnostic.get("date")

    return {
        "by_reason": [
            {
                "name": name,
                "count": data["count"],
                "latest_ticker": data.get("latest_ticker"),
                "latest_date": data.get("latest_date"),
            }
            for name, data in sorted(by_reason.items(), key=lambda item: (-item[1]["count"], item[0]))
        ]
    }


def summarize_session_markers(session_markers: List[Dict]) -> Dict[str, object]:
    """Aggregate cumulative paper-run audit markers across sessions."""
    enriched_markers = [
        marker for marker in session_markers
        if marker.get('source') == 'run_pennyhunter_paper' or marker.get('rejected_signals') or marker.get('trading_stats') or marker.get('scan_near_misses')
    ]
    flattened_rejections = []
    flattened_near_misses = []
    sessions_with_rejections = 0
    sessions_with_trades = 0
    sessions_with_near_misses = 0

    for marker in enriched_markers:
        trading_stats = marker.get('trading_stats', {})
        if trading_stats.get('total_trades', 0):
            sessions_with_trades += 1
        rejected = marker.get('rejected_signals', [])
        if rejected:
            sessions_with_rejections += 1
            flattened_rejections.extend(rejected)
        near_misses = marker.get('scan_near_misses', [])
        if near_misses:
            sessions_with_near_misses += 1
            flattened_near_misses.extend(near_misses)

    rejection_summary = summarize_recent_rejections(flattened_rejections)
    near_miss_summary = summarize_scan_near_misses(flattened_near_misses)
    dominant_stage = rejection_summary['by_stage'][0] if rejection_summary['by_stage'] else None
    dominant_check = rejection_summary['by_check'][0] if rejection_summary['by_check'] else None

    dominant_blocker = None
    if dominant_check:
        dominant_blocker = {
            'type': 'check',
            'name': dominant_check['name'],
            'count': dominant_check['count'],
            'latest_reason': dominant_check.get('latest_reason'),
        }
    elif dominant_stage:
        dominant_blocker = {
            'type': 'stage',
            'name': dominant_stage['name'],
            'count': dominant_stage['count'],
            'latest_reason': None,
        }

    return {
        'tracked_sessions': len(enriched_markers),
        'sessions_with_rejections': sessions_with_rejections,
        'sessions_with_near_misses': sessions_with_near_misses,
        'sessions_with_trades': sessions_with_trades,
        'total_rejected_signals': len(flattened_rejections),
        'total_scan_near_misses': len(flattened_near_misses),
        'rejection_summary': rejection_summary,
        'near_miss_summary': near_miss_summary,
        'dominant_blocker': dominant_blocker,
    }


def build_validation_report(trades: List[Dict], paper_report: Optional[Dict] = None, session_markers: Optional[List[Dict]] = None) -> Dict:
    """Build a richer Phase 2 validation report from the filtered trade set."""
    paper_report = paper_report or {}
    session_markers = session_markers or []
    closed = [t for t in trades if str(t.get("status", "")).lower() in CLOSED_STATUSES]
    active = [t for t in trades if str(t.get("status", "")).lower() == "active"]
    rejected_signals = paper_report.get("rejected_signals", [])
    scan_near_misses = paper_report.get("scan_near_misses", [])
    rejection_summary = summarize_recent_rejections(rejected_signals)
    near_miss_summary = summarize_scan_near_misses(scan_near_misses)
    session_audit = summarize_session_markers(session_markers)
    recent_trading_stats = paper_report.get("trading_stats", {})

    latest_session_status = {
        "had_rejections": bool(rejected_signals),
        "executed_trades": int(recent_trading_stats.get("total_trades", 0) or 0),
        "status": "blocked" if rejected_signals else "cleared",
        "message": "Latest session still encountered quality-gate rejections."
        if rejected_signals
        else "Latest session cleared previously observed blockers.",
    }

    wins = [t for t in closed if safe_float(t.get("pnl")) > 0]
    losses = [t for t in closed if safe_float(t.get("pnl")) <= 0]
    completed = len(closed)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / completed if completed else 0.0

    pnl_values = [safe_float(t.get("pnl")) for t in closed]
    return_values = [safe_float(t.get("return_pct")) for t in closed]
    gross_profit = sum(pnl for pnl in pnl_values if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in pnl_values if pnl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
    avg_return = sum(return_values) / completed if completed else 0.0
    avg_win = gross_profit / win_count if win_count else 0.0
    avg_loss = -gross_loss / loss_count if loss_count else 0.0
    max_drawdown = calculate_max_drawdown(pnl_values)
    confidence_low, confidence_high = wilson_confidence_interval(win_count, completed)

    closed_sorted = sorted(closed, key=lambda trade: parse_datetime(trade.get("exit_time")) or datetime.min)
    losing_trade_analysis = [
        {
            "ticker": trade.get("ticker", "UNKNOWN"),
            "entry_time": trade.get("entry_time"),
            "exit_time": trade.get("exit_time"),
            "pnl": safe_float(trade.get("pnl")),
            "return_pct": safe_float(trade.get("return_pct")),
            "market_regime": trade.get("market_regime", "UNKNOWN"),
            "gap_pct": safe_float(trade.get("gap_pct")),
            "vol_mult": trade_volume_multiple(trade),
        }
        for trade in closed_sorted
        if safe_float(trade.get("pnl")) <= 0
    ]

    milestone = check_milestone(completed, win_count, win_rate)

    return {
        "generated_at": datetime.now().isoformat(),
        "phase2_deployment_date": PHASE2_DEPLOYMENT_DATE,
        "trade_counts": {
            "total_filtered": len(trades),
            "completed": completed,
            "active": len(active),
            "wins": win_count,
            "losses": loss_count,
            "recent_rejected_signals": len(rejected_signals),
            "recent_scan_near_misses": len(scan_near_misses),
            "unique_signal_dates": len({trade_signal_date(trade) for trade in trades}),
            "unique_signal_setups": len({f"{trade.get('ticker', 'UNKNOWN')}@{trade_signal_date(trade)}" for trade in trades}),
        },
        "metrics": {
            "win_rate": win_rate,
            "win_rate_confidence_interval_95": {
                "low": confidence_low,
                "high": confidence_high,
            },
            "profit_factor": profit_factor,
            "average_return_pct": avg_return,
            "average_win_pnl": avg_win,
            "average_loss_pnl": avg_loss,
            "total_pnl": sum(pnl_values),
            "max_drawdown_pnl": max_drawdown,
        },
        "milestone": milestone,
        "by_regime": summarize_bucket(closed, "market_regime"),
        "by_ticker": summarize_bucket(closed, "ticker"),
        "by_signal_setup": summarize_signal_setups(closed),
        "losing_trades": losing_trade_analysis,
        "active_positions": active,
        "recent_session": {
            "generated_at": paper_report.get("generated_at"),
            "trading_stats": paper_report.get("trading_stats", {}),
            "rejected_signals": rejected_signals,
            "rejection_summary": rejection_summary,
            "scan_near_misses": scan_near_misses,
            "near_miss_summary": near_miss_summary,
            "status": latest_session_status,
        },
        "session_audit_trend": session_audit,
    }


def write_markdown_report(report: Dict, output_path: Path) -> None:
    """Write a human-readable Phase 2 Markdown validation report."""
    metrics = report["metrics"]
    counts = report["trade_counts"]
    milestone = report["milestone"]

    def format_bucket_rows(rows: List[Dict]) -> str:
        if not rows:
            return "| None | 0 | 0 | 0 | 0.0% | $0.00 |\n"
        return "".join(
            f"| {row['name']} | {row['trades']} | {row['wins']} | {row['losses']} | {row['win_rate']*100:.1f}% | ${row['total_pnl']:.2f} |\n"
            for row in rows
        )

    confidence = metrics["win_rate_confidence_interval_95"]
    profit_factor = metrics["profit_factor"]
    profit_factor_text = f"{profit_factor:.2f}" if math.isfinite(profit_factor) else "inf"

    lines = [
        "# Phase 2 Validation Report\n",
        f"Generated: {report['generated_at']}\n",
        f"Deployment Date: {report['phase2_deployment_date']}\n\n",
        "## Summary\n",
        f"- Completed trades: {counts['completed']}\n",
        f"- Active trades: {counts['active']}\n",
        f"- Recent rejected signals: {counts['recent_rejected_signals']}\n",
        f"- Recent scan near misses: {counts['recent_scan_near_misses']}\n",
        f"- Unique signal dates: {counts['unique_signal_dates']}\n",
        f"- Unique signal setups: {counts['unique_signal_setups']}\n",
        f"- Tracked audit sessions: {report['session_audit_trend']['tracked_sessions']}\n",
        f"- Latest session status: {report['recent_session']['status']['message']}\n",
        f"- Wins / Losses: {counts['wins']} / {counts['losses']}\n",
        f"- Win rate: {metrics['win_rate']*100:.1f}%\n",
        f"- 95% confidence interval: {confidence['low']*100:.1f}% to {confidence['high']*100:.1f}%\n",
        f"- Profit factor: {profit_factor_text}\n",
        f"- Average return: {metrics['average_return_pct']:.2f}%\n",
        f"- Total P&L: ${metrics['total_pnl']:.2f}\n",
        f"- Max drawdown: ${metrics['max_drawdown_pnl']:.2f}\n",
        f"- Milestone status: {milestone['message'] or 'No milestone reached yet'}\n\n",
        "## Regime Breakdown\n",
        "| Regime | Trades | Wins | Losses | Win Rate | Total P&L |\n",
        "| --- | ---: | ---: | ---: | ---: | ---: |\n",
        format_bucket_rows(report["by_regime"]),
        "\n## Ticker Breakdown\n",
        "| Ticker | Trades | Wins | Losses | Win Rate | Total P&L |\n",
        "| --- | ---: | ---: | ---: | ---: | ---: |\n",
        format_bucket_rows(report["by_ticker"]),
        "\n## Signal Setup Breakdown\n",
        "| Setup | Trades | Wins | Losses | Win Rate | Total P&L |\n",
        "| --- | ---: | ---: | ---: | ---: | ---: |\n",
        format_bucket_rows(report["by_signal_setup"]),
        "\n## Losing Trades\n",
    ]

    if report["losing_trades"]:
        lines.extend(
            [
                "| Ticker | Exit Time | Regime | P&L | Return % | Gap % | Vol Mult |\n",
                "| --- | --- | --- | ---: | ---: | ---: | ---: |\n",
            ]
        )
        for trade in report["losing_trades"]:
            lines.append(
                f"| {trade['ticker']} | {trade['exit_time'] or 'N/A'} | {trade['market_regime']} | ${trade['pnl']:.2f} | {trade['return_pct']:.2f}% | {trade['gap_pct']:.1f}% | {trade['vol_mult']:.1f}x |\n"
            )
    else:
        lines.append("No losing trades recorded in the filtered Phase 2 sample.\n")

    lines.append("\n## Recent Rejected Signals\n")
    recent_rejections = report.get("recent_session", {}).get("rejected_signals", [])
    rejection_summary = report.get("recent_session", {}).get("rejection_summary", {})
    if recent_rejections:
        lines.extend(
            [
                "| Ticker | Date | Stage | Gap % | Vol Mult | Reason |\n",
                "| --- | --- | --- | ---: | ---: | --- |\n",
            ]
        )
        for rejected in recent_rejections:
            reason_text = "; ".join(
                f"{item.get('check')}: {item.get('reason')}" for item in rejected.get("reasons", [])
            ) or "N/A"
            lines.append(
                f"| {rejected.get('ticker', 'UNKNOWN')} | {rejected.get('date') or 'N/A'} | {rejected.get('stage') or 'N/A'} | {safe_float(rejected.get('gap_pct')):.1f}% | {trade_volume_multiple(rejected):.1f}x | {reason_text} |\n"
            )

        lines.append("\n### Rejection Counts By Stage\n")
        lines.extend(
            [
                "| Stage | Count |\n",
                "| --- | ---: |\n",
            ]
        )
        for row in rejection_summary.get("by_stage", []):
            lines.append(f"| {row['name']} | {row['count']} |\n")

        lines.append("\n### Rejection Counts By Check\n")
        lines.extend(
            [
                "| Check | Count | Latest Reason |\n",
                "| --- | ---: | --- |\n",
            ]
        )
        for row in rejection_summary.get("by_check", []):
            lines.append(
                f"| {row['name']} | {row['count']} | {row.get('latest_reason') or 'N/A'} |\n"
            )
    else:
        lines.append("No rejected signals recorded in the latest paper-trading session.\n")

    lines.append("\n## Recent Scan Near Misses\n")
    recent_near_misses = report.get("recent_session", {}).get("scan_near_misses", [])
    near_miss_summary = report.get("recent_session", {}).get("near_miss_summary", {})
    if recent_near_misses:
        lines.extend(
            [
                "| Ticker | Date | Reason | Gap % | Vol Mult | Target |\n",
                "| --- | --- | --- | ---: | ---: | --- |\n",
            ]
        )
        for diagnostic in recent_near_misses:
            target = diagnostic.get("target_gap_range") or diagnostic.get("target_volume_rule") or "N/A"
            lines.append(
                f"| {diagnostic.get('ticker', 'UNKNOWN')} | {diagnostic.get('date') or 'N/A'} | {diagnostic.get('reason') or 'N/A'} | {safe_float(diagnostic.get('gap_pct')):.1f}% | {safe_float(diagnostic.get('vol_spike')):.1f}x | {target} |\n"
            )

        if near_miss_summary.get("by_reason"):
            lines.extend(
                [
                    "\n### Near Miss Counts By Reason\n",
                    "| Reason | Count | Latest Example |\n",
                    "| --- | ---: | --- |\n",
                ]
            )
            for row in near_miss_summary.get("by_reason", []):
                latest_example = "N/A"
                if row.get("latest_ticker") and row.get("latest_date"):
                    latest_example = f"{row['latest_ticker']} ({row['latest_date']})"
                lines.append(f"| {row['name']} | {row['count']} | {latest_example} |\n")
    else:
        lines.append("No scan near misses recorded in the latest paper-trading session.\n")

    session_audit = report.get("session_audit_trend", {})
    lines.append("\n## Session Audit Trend\n")
    lines.append(f"- Tracked audit sessions: {session_audit.get('tracked_sessions', 0)}\n")
    lines.append(f"- Sessions with rejected signals: {session_audit.get('sessions_with_rejections', 0)}\n")
    lines.append(f"- Sessions with scan near misses: {session_audit.get('sessions_with_near_misses', 0)}\n")
    lines.append(f"- Sessions with executed trades: {session_audit.get('sessions_with_trades', 0)}\n")
    lines.append(f"- Total rejected signals across tracked sessions: {session_audit.get('total_rejected_signals', 0)}\n")
    lines.append(f"- Total scan near misses across tracked sessions: {session_audit.get('total_scan_near_misses', 0)}\n")
    dominant_blocker = session_audit.get('dominant_blocker')
    if dominant_blocker:
        blocker_reason = dominant_blocker.get('latest_reason') or 'N/A'
        lines.append(
            f"- Dominant blocker: {dominant_blocker['name']} ({dominant_blocker['count']} occurrences; latest reason: {blocker_reason})\n"
        )
    lines.append(
        f"- Latest session interpretation: {report['recent_session']['status']['message']}\n"
    )

    trend_summary = session_audit.get("rejection_summary", {})
    if trend_summary.get("by_stage"):
        lines.extend(
            [
                "\n### Trend By Stage\n",
                "| Stage | Count |\n",
                "| --- | ---: |\n",
            ]
        )
        for row in trend_summary.get("by_stage", []):
            lines.append(f"| {row['name']} | {row['count']} |\n")

    if trend_summary.get("by_check"):
        lines.extend(
            [
                "\n### Trend By Check\n",
                "| Check | Count | Latest Reason |\n",
                "| --- | ---: | --- |\n",
            ]
        )
        for row in trend_summary.get("by_check", []):
            lines.append(
                f"| {row['name']} | {row['count']} | {row.get('latest_reason') or 'N/A'} |\n"
            )

    output_path.write_text("".join(lines), encoding="utf-8")


def analyze_trades(trades: List[Dict], paper_report: Optional[Dict] = None, session_markers: Optional[List[Dict]] = None) -> Tuple[int, int, int, float]:
    """Retain the original summary tuple for console output and milestone checks."""
    report = build_validation_report(trades, paper_report=paper_report, session_markers=session_markers)
    counts = report["trade_counts"]
    return counts["completed"], counts["wins"], counts["losses"], report["metrics"]["win_rate"]


def check_milestone(completed: int, wins: int, win_rate: float) -> Dict:
    """Check current progress against milestones."""
    # Find the highest milestone we've reached
    reached_milestone = None
    next_milestone = None
    
    for trades_needed in sorted(MILESTONES.keys()):
        if completed >= trades_needed:
            reached_milestone = trades_needed
        elif next_milestone is None:
            next_milestone = trades_needed
            break
    
    # Check if we passed the milestone
    result = {
        'reached': reached_milestone,
        'next': next_milestone,
        'passed': False,
        'message': ''
    }
    
    if reached_milestone:
        milestone = MILESTONES[reached_milestone]
        target_wr = milestone['target_wr']
        min_wins = milestone['min_wins']
        
        if win_rate >= target_wr and wins >= min_wins:
            result['passed'] = True
            result['message'] = f"✅ {milestone['name']} PASSED ({wins}/{reached_milestone} wins = {win_rate*100:.1f}%)"
        else:
            result['passed'] = False
            result['message'] = f"❌ {milestone['name']} FAILED ({wins}/{reached_milestone} wins = {win_rate*100:.1f}% vs {target_wr*100:.0f}% target)"
    
    return result


def print_summary(trades: List[Dict], completed: int, wins: int, losses: int, win_rate: float, paper_report: Optional[Dict] = None, session_markers: Optional[List[Dict]] = None):
    """Print validation summary."""
    paper_report = paper_report or {}
    session_markers = session_markers or []
    report = build_validation_report(trades, paper_report=paper_report, session_markers=session_markers)
    active = [t for t in trades if t.get('status') == 'active']
    rejected_signals = paper_report.get('rejected_signals', [])
    session_audit = summarize_session_markers(session_markers)
    latest_session_status = report['recent_session']['status']['message']
    
    print("=" * 70)
    print("PHASE 2 OUT-OF-SAMPLE VALIDATION STATUS")
    print("=" * 70)
    print(f"Deployment Date: {PHASE2_DEPLOYMENT_DATE}")
    print(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📊 TRADE STATISTICS")
    print(f"   Total Trades: {len(trades)}")
    print(f"   Completed: {completed}")
    print(f"   Active: {len(active)}")
    print(f"   Recent Rejected Signals: {len(rejected_signals)}")
    print(f"   Recent Scan Near Misses: {report['trade_counts']['recent_scan_near_misses']}")
    print(f"   Unique Signal Dates: {report['trade_counts']['unique_signal_dates']}")
    print(f"   Unique Signal Setups: {report['trade_counts']['unique_signal_setups']}")
    print(f"   Tracked Audit Sessions: {session_audit['tracked_sessions']}")
    print(f"   Latest Session Status: {latest_session_status}")
    print(f"   Wins: {wins}")
    print(f"   Losses: {losses}")
    print(f"   Win Rate: {win_rate*100:.1f}%")
    print()
    
    # Show active positions
    if active:
        print("🔄 ACTIVE POSITIONS")
        for trade in active:
            ticker = trade.get('ticker')
            entry = trade.get('entry_price', 0)
            shares = trade.get('shares', 0)
            gap = trade.get('gap_pct', 0)
            vol = trade_volume_multiple(trade)
            print(f"   {ticker}: {shares} shares @ ${entry:.2f} (Gap {gap:.1f}%, Vol {vol:.1f}x)")
        print()

    if rejected_signals:
        print("🚫 RECENT REJECTED SIGNALS")
        for rejected in rejected_signals[:5]:
            reason_text = "; ".join(
                f"{item.get('check')}: {item.get('reason')}" for item in rejected.get('reasons', [])
            ) or 'N/A'
            print(
                f"   {rejected.get('ticker', 'UNKNOWN')} ({rejected.get('date') or 'N/A'}): "
                f"{rejected.get('stage') or 'N/A'} -> {reason_text}"
            )
        summary = summarize_recent_rejections(rejected_signals)
        if summary["by_stage"]:
            stage_text = ", ".join(f"{row['name']}={row['count']}" for row in summary["by_stage"])
            print(f"   By stage: {stage_text}")
        if summary["by_check"]:
            check_text = ", ".join(f"{row['name']}={row['count']}" for row in summary["by_check"])
            print(f"   By check: {check_text}")
        print()

    if session_audit['tracked_sessions']:
        print("🧾 SESSION AUDIT TREND")
        print(f"   Sessions with rejections: {session_audit['sessions_with_rejections']}")
        print(f"   Sessions with near misses: {session_audit['sessions_with_near_misses']}")
        print(f"   Sessions with executed trades: {session_audit['sessions_with_trades']}")
        print(f"   Total rejected signals: {session_audit['total_rejected_signals']}")
        print(f"   Total scan near misses: {session_audit['total_scan_near_misses']}")
        if session_audit.get('dominant_blocker'):
            blocker = session_audit['dominant_blocker']
            blocker_reason = blocker.get('latest_reason') or 'N/A'
            print(
                f"   Dominant blocker: {blocker['name']}={blocker['count']} "
                f"(latest reason: {blocker_reason})"
            )
        trend_stage_text = ", ".join(
            f"{row['name']}={row['count']}" for row in session_audit['rejection_summary'].get('by_stage', [])
        )
        if trend_stage_text:
            print(f"   Trend by stage: {trend_stage_text}")
        trend_check_text = ", ".join(
            f"{row['name']}={row['count']}" for row in session_audit['rejection_summary'].get('by_check', [])
        )
        if trend_check_text:
            print(f"   Trend by check: {trend_check_text}")
        print(f"   Latest session interpretation: {latest_session_status}")
        print()
    
    # Check milestones
    print("🎯 MILESTONE PROGRESS")
    milestone_result = check_milestone(completed, wins, win_rate)
    
    for trades_needed in sorted(MILESTONES.keys()):
        milestone = MILESTONES[trades_needed]
        target_wr = milestone['target_wr']
        min_wins = milestone['min_wins']
        
        if completed >= trades_needed:
            # Reached this milestone
            if win_rate >= target_wr and wins >= min_wins:
                status = "✅ PASSED"
            else:
                status = "❌ FAILED"
            progress = 100
        else:
            status = "⏳ PENDING"
            progress = int((completed / trades_needed) * 100)
        
        bar_length = 30
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        print(f"   {milestone['name']}: [{bar}] {progress}%")
        print(f"      {completed}/{trades_needed} trades, {wins} wins ({win_rate*100:.1f}% vs {target_wr*100:.0f}% target) {status}")
    
    print()
    
    # Decision
    print("=" * 70)
    if completed >= 20:
        if win_rate >= 0.70 and wins >= 14:
            print("🎉 PHASE 2.5 APPROVED!")
            print("   ✅ 20 trades completed")
            print(f"   ✅ {win_rate*100:.1f}% win rate (≥70% target)")
            print(f"   ✅ {wins} wins (≥14 required)")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Implement Phase 2.5 agentic memory system")
            print("   2. Add ticker performance tracking")
            print("   3. Implement auto-ejection logic (<40% WR after 10 trades)")
            print("   4. Add context-aware filtering")
            print("   5. Implement regime-based adjustments")
        else:
            print("⚠️  PHASE 2 VALIDATION INCOMPLETE")
            print(f"   ❌ Win rate {win_rate*100:.1f}% below 70% target")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Analyze losing trades for patterns")
            print("   2. Review if gap/volume filters need adjustment")
            print("   3. Check if market regime shifted")
            print("   4. Consider expanding ticker universe")
    elif completed >= 10:
        milestone = check_milestone(completed, wins, win_rate)
        if milestone['passed']:
            print(f"✅ INTERMEDIATE VALIDATION PASSED ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   System is performing well - continue accumulating trades")
            print()
            print("📋 NEXT STEPS:")
            print(f"   Continue daily trading to reach 20 trades ({20-completed} more needed)")
        else:
            print(f"⚠️  INTERMEDIATE VALIDATION CONCERNS ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   Win rate below target - may need adjustment")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Monitor next few trades closely")
            print("   2. If win rate continues below 60%, re-analyze filters")
    elif completed >= 5:
        milestone = check_milestone(completed, wins, win_rate)
        if milestone['passed']:
            print(f"✅ INITIAL VALIDATION PASSED ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   Filters showing promise - continue accumulating trades")
            print()
            print("📋 NEXT STEPS:")
            print(f"   Continue daily trading to reach 20 trades ({20-completed} more needed)")
        else:
            print(f"⚠️  INITIAL VALIDATION CONCERNS ({wins}/{completed} wins = {win_rate*100:.1f}%)")
            print("   Win rate below 60% - filters may need review")
            print()
            print("📋 NEXT STEPS:")
            print("   1. Review losing trades for common patterns")
            print("   2. Check if gap/volume ranges need adjustment")
    else:
        print(f"🔄 VALIDATION IN PROGRESS ({completed}/5 trades for initial check)")
        print()
        print("📋 NEXT STEPS:")
        print(f"   Continue daily trading to reach 5 trades ({5-completed} more needed)")
    
    print("=" * 70)


def main():
    """Main validation check."""
    global HISTORY_FILE, PAPER_TRADES_FILE

    parser = argparse.ArgumentParser(description="Check Phase 2 validation status")
    parser.add_argument("--history-file", type=Path, default=HISTORY_FILE, help="History file to read trades and session markers from")
    parser.add_argument("--paper-trades-file", type=Path, default=PAPER_TRADES_FILE, help="Paper-trades report file to read latest session data from")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_REPORT, help="Where to write the JSON validation report")
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_REPORT, help="Where to write the Markdown validation report")
    args = parser.parse_args()

    HISTORY_FILE = args.history_file
    PAPER_TRADES_FILE = args.paper_trades_file

    print("\nLoading trade history...\n")
    
    # Load all trades
    all_trades = load_trades()
    paper_report = load_paper_trade_report()
    session_markers = load_session_markers()
    if not all_trades:
        print("❌ No trades found")
        return
    
    # Filter to post-optimization trades only
    post_opt_trades = filter_post_optimization_trades(all_trades)
    
    if not post_opt_trades:
        print(f"❌ No trades found after {PHASE2_DEPLOYMENT_DATE}")
        print("\n📋 NEXT STEPS:")
        print("   Run daily paper trading: python scripts/daily_pennyhunter.py")
        return
    
    # Analyze
    completed, wins, losses, win_rate = analyze_trades(post_opt_trades, paper_report=paper_report, session_markers=session_markers)
    report = build_validation_report(post_opt_trades, paper_report=paper_report, session_markers=session_markers)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(report, args.markdown_out)
    
    # Print summary
    print_summary(post_opt_trades, completed, wins, losses, win_rate, paper_report=paper_report, session_markers=session_markers)
    print(f"\n📄 JSON report: {args.json_out}")
    print(f"📝 Markdown report: {args.markdown_out}")


if __name__ == "__main__":
    main()
