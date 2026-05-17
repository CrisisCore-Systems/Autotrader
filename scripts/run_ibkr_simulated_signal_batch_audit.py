#!/usr/bin/env python
"""Batch audit for simulated IBKR signals with reject-first safety controls."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autotrader.execution.adapters import Order, OrderSide, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter

CONFIRM_PHRASE = "YES_PAPER_ORDER_ONLY"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
ALLOWED_SEC_TYPE = "STK"
ALLOWED_ORDER_TYPE = "LMT"
ALLOWED_SOURCE = "simulated_signal"


@dataclass
class Signal:
    signal_id: str
    symbol: str
    sec_type: str
    currency: str
    exchange: str
    side: str
    quantity: float
    order_type: str
    limit_price: Optional[float]
    confidence: float
    source: str


@dataclass
class Decision:
    index: int
    signal_id: str
    accepted: bool
    reasons: List[str]
    selected_for_submit: bool
    submitted: bool
    context: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refuse_unless(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _record_event(status_doc: Dict[str, Any], event_name: str, **fields: Any) -> None:
    payload = {"at": _utc_now(), "event": event_name}
    payload.update(fields)
    status_doc["events"].append(payload)


def _parse_side(value: str) -> OrderSide:
    key = str(value).strip().upper()
    mapping = {"BUY": OrderSide.BUY, "SELL": OrderSide.SELL}
    if key not in mapping:
        raise ValueError(f"Unsupported side: {value}")
    return mapping[key]


def _assert_global_safety(args: argparse.Namespace) -> None:
    host = str(args.ibkr_host).strip().lower()
    _refuse_unless(
        host in ALLOWED_HOSTS,
        f"Refusing batch audit: host must be localhost/127.0.0.1, got {args.ibkr_host}.",
    )
    _refuse_unless(
        int(args.ibkr_port) == 7497,
        f"Refusing batch audit: expected paper TWS port 7497, got {args.ibkr_port}.",
    )
    _refuse_unless(
        str(args.i_understand_this_submits_a_paper_order) == CONFIRM_PHRASE,
        "Refusing batch audit: confirmation phrase mismatch.",
    )
    _refuse_unless(
        0.0 < float(args.max_order_notional) <= 5.0,
        "Refusing batch audit: --max-order-notional must be > 0 and <= 5.",
    )
    _refuse_unless(
        0.0 <= float(args.min_confidence) <= 1.0,
        "Refusing batch audit: --min-confidence must be between 0 and 1.",
    )


def _signal_from_dict(payload: Dict[str, Any]) -> Signal:
    required = {
        "signal_id",
        "symbol",
        "sec_type",
        "currency",
        "exchange",
        "side",
        "quantity",
        "order_type",
        "confidence",
        "source",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Missing required signal fields: {', '.join(missing)}")

    return Signal(
        signal_id=str(payload["signal_id"]),
        symbol=str(payload["symbol"]).upper(),
        sec_type=str(payload["sec_type"]).upper(),
        currency=str(payload["currency"]).upper(),
        exchange=str(payload["exchange"]).upper(),
        side=str(payload["side"]).upper(),
        quantity=float(payload["quantity"]),
        order_type=str(payload["order_type"]).upper(),
        limit_price=(None if payload.get("limit_price") is None else float(payload.get("limit_price"))),
        confidence=float(payload["confidence"]),
        source=str(payload["source"]),
    )


def _validate_signal(
    signal: Signal,
    args: argparse.Namespace,
    host: str,
    port: int,
    phrase: str,
) -> List[str]:
    reasons: List[str] = []

    if host.strip().lower() not in ALLOWED_HOSTS:
        reasons.append(f"live-looking host not allowed: {host}")
    if int(port) != 7497:
        reasons.append(f"paper port 7497 required, got {port}")
    if phrase != CONFIRM_PHRASE:
        reasons.append("missing or invalid confirmation phrase")

    if signal.order_type != ALLOWED_ORDER_TYPE:
        reasons.append(f"order_type must be LMT, got {signal.order_type}")
    if signal.sec_type != ALLOWED_SEC_TYPE:
        reasons.append(f"unsupported sec_type: {signal.sec_type}")
    if signal.limit_price is None:
        reasons.append("limit_price is required")
    elif signal.limit_price <= 0:
        reasons.append("limit_price must be > 0")

    if abs(signal.quantity - round(signal.quantity)) > 1e-9:
        reasons.append(f"STK quantity must be whole number, got {signal.quantity}")

    if signal.confidence < float(args.min_confidence):
        reasons.append(
            f"confidence below threshold: {signal.confidence:.4f} < {float(args.min_confidence):.4f}"
        )

    if signal.source != ALLOWED_SOURCE:
        reasons.append(f"unknown signal source: {signal.source}")

    if signal.limit_price is not None:
        notional = float(signal.quantity) * float(signal.limit_price)
        if notional > float(args.max_order_notional):
            reasons.append(
                f"notional over cap: {notional:.4f} > {float(args.max_order_notional):.4f}"
            )

    return reasons


def _build_order(signal: Signal) -> Order:
    return Order(
        order_id="",
        symbol=signal.symbol,
        side=_parse_side(signal.side),
        order_type=OrderType.LIMIT,
        quantity=float(signal.quantity),
        price=float(signal.limit_price),
        time_in_force="DAY",
        metadata={
            "ibkr_symbol": signal.symbol,
            "ibkr_sec_type": signal.sec_type,
            "ibkr_currency": signal.currency,
            "ibkr_exchange": signal.exchange,
            "ibkr_transmit": True,
            "probe_type": "simulated_signal_batch_audit",
            "signal_id": signal.signal_id,
            "source": signal.source,
        },
    )


def _load_batch(args: argparse.Namespace) -> List[Dict[str, Any]]:
    source_path = (PROJECT_ROOT / args.signals_json).resolve()
    with source_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)

    if not isinstance(loaded, list):
        raise ValueError("signals-json must be a JSON array")
    if not loaded:
        raise ValueError("signals-json array is empty")

    return loaded


def _build_status(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "started_at": _utc_now(),
        "mode": "ibkr_simulated_signal_batch_audit",
        "constraints": {
            "allowed_hosts": sorted(ALLOWED_HOSTS),
            "paper_port": 7497,
            "sec_type": ALLOWED_SEC_TYPE,
            "order_type": ALLOWED_ORDER_TYPE,
            "max_order_notional": float(args.max_order_notional),
            "min_confidence": float(args.min_confidence),
            "confirmation_phrase_required": CONFIRM_PHRASE,
            "one_order_max_per_run": True,
            "default_submit_mode": False,
        },
        "request": {
            "host": args.ibkr_host,
            "port": int(args.ibkr_port),
            "client_id": int(args.ibkr_client_id),
            "signals_json": args.signals_json,
            "submit_one_valid_paper_order": bool(args.submit_one_valid_paper_order),
            "cancel_after_seconds": float(args.cancel_after_seconds),
        },
        "events": [],
        "errors": [],
        "decisions": [],
        "result": {
            "signals_total": 0,
            "signals_rejected": 0,
            "signals_accepted": 0,
            "accepted_signal_ids": [],
            "selected_signal_id": None,
            "order_submission_attempted": False,
            "orders_submitted": 0,
            "connect_ok": False,
            "cancel_attempted": False,
            "cancelled": False,
            "disconnect_recorded": False,
            "order_id": None,
            "order_status": None,
            "refused_additional_valid_signals": 0,
        },
    }


def _evaluate_signals(args: argparse.Namespace, raw_signals: List[Dict[str, Any]]) -> List[Decision]:
    decisions: List[Decision] = []

    for idx, payload in enumerate(raw_signals, start=1):
        if not isinstance(payload, dict):
            decisions.append(
                Decision(
                    index=idx,
                    signal_id=f"invalid-{idx}",
                    accepted=False,
                    reasons=["signal item must be an object"],
                    selected_for_submit=False,
                    submitted=False,
                    context={"host": args.ibkr_host, "port": int(args.ibkr_port), "phrase_ok": True},
                )
            )
            continue

        context = payload.get("context", {})
        if context is None:
            context = {}
        if not isinstance(context, dict):
            context = {}

        host = str(context.get("host", args.ibkr_host))
        port = int(context.get("port", args.ibkr_port))
        phrase = str(context.get("phrase", args.i_understand_this_submits_a_paper_order))

        try:
            signal = _signal_from_dict(payload)
            reasons = _validate_signal(signal, args, host=host, port=port, phrase=phrase)
            accepted = len(reasons) == 0
            signal_id = signal.signal_id
        except Exception as exc:
            accepted = False
            reasons = [f"signal_parse_error: {exc}"]
            signal_id = str(payload.get("signal_id", f"invalid-{idx}"))

        decisions.append(
            Decision(
                index=idx,
                signal_id=signal_id,
                accepted=accepted,
                reasons=reasons,
                selected_for_submit=False,
                submitted=False,
                context={"host": host, "port": port, "phrase_ok": phrase == CONFIRM_PHRASE},
            )
        )

    return decisions


async def _submit_single_candidate(
    args: argparse.Namespace,
    status: Dict[str, Any],
    candidate_payload: Dict[str, Any],
) -> None:
    signal = _signal_from_dict(candidate_payload)
    adapter = IBKRAdapter(
        host=str(args.ibkr_host),
        port=int(args.ibkr_port),
        client_id=int(args.ibkr_client_id),
    )

    connected = await adapter.connect()
    status["result"]["connect_ok"] = bool(connected)
    _record_event(status, "connect", ok=bool(connected))
    if not connected:
        raise RuntimeError("Failed to connect to IBKR paper TWS/Gateway.")

    order = _build_order(signal)
    submitted = await adapter.submit_order(order)
    status["result"]["orders_submitted"] = 1
    status["result"]["order_id"] = submitted.order_id
    status["result"]["order_status"] = submitted.status.value
    _record_event(status, "submit", order_id=submitted.order_id, status=submitted.status.value)

    await asyncio.sleep(float(args.cancel_after_seconds))
    status["result"]["cancel_attempted"] = True
    cancelled = await adapter.cancel_order(submitted.order_id)
    status["result"]["cancelled"] = bool(cancelled)
    _record_event(status, "cancel", order_id=submitted.order_id, ok=bool(cancelled))

    try:
        adapter.disconnect()
        status["result"]["disconnect_recorded"] = True
        _record_event(status, "disconnect", ok=True)
    except Exception as exc:
        status["errors"].append(f"disconnect_error: {exc}")
        _record_event(status, "disconnect", ok=False, message=str(exc))


def _write_status(args: argparse.Namespace, status: Dict[str, Any]) -> None:
    output_path = (PROJECT_ROOT / args.status_output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(status, handle, indent=2, sort_keys=True)
        handle.write("\n")


async def _run(args: argparse.Namespace) -> int:
    _assert_global_safety(args)

    status = _build_status(args)
    raw_signals = _load_batch(args)
    decisions = _evaluate_signals(args, raw_signals)

    accepted = [d for d in decisions if d.accepted]
    rejected = [d for d in decisions if not d.accepted]

    status["result"]["signals_total"] = len(decisions)
    status["result"]["signals_rejected"] = len(rejected)
    status["result"]["signals_accepted"] = len(accepted)
    status["result"]["accepted_signal_ids"] = [d.signal_id for d in accepted]

    for decision in decisions:
        status["decisions"].append(
            {
                "index": decision.index,
                "signal_id": decision.signal_id,
                "accepted": decision.accepted,
                "reasons": decision.reasons,
                "selected_for_submit": decision.selected_for_submit,
                "submitted": decision.submitted,
                "context": decision.context,
            }
        )

    _record_event(
        status,
        "batch_evaluated",
        signals_total=len(decisions),
        signals_accepted=len(accepted),
        signals_rejected=len(rejected),
    )

    if not args.submit_one_valid_paper_order:
        _record_event(status, "audit_only_no_submission")
        status["finished_at"] = _utc_now()
        _write_status(args, status)
        return 0

    if not accepted:
        _record_event(status, "no_accepted_signal_for_submission")
        status["finished_at"] = _utc_now()
        _write_status(args, status)
        return 0

    selected = accepted[0]
    status["result"]["selected_signal_id"] = selected.signal_id
    status["result"]["order_submission_attempted"] = True

    # Enforce one-order maximum by refusing all additional accepted signals.
    if len(accepted) > 1:
        refused_count = len(accepted) - 1
        status["result"]["refused_additional_valid_signals"] = refused_count
        _record_event(status, "one_order_cap_enforced", refused_count=refused_count)

    for row in status["decisions"]:
        if row["signal_id"] == selected.signal_id and row["accepted"]:
            row["selected_for_submit"] = True
            break

    selected_payload = None
    for payload in raw_signals:
        if isinstance(payload, dict) and str(payload.get("signal_id", "")) == selected.signal_id:
            selected_payload = payload
            break

    if selected_payload is None:
        status["errors"].append("selected signal payload not found")
        status["finished_at"] = _utc_now()
        _write_status(args, status)
        return 1

    try:
        await _submit_single_candidate(args, status, selected_payload)
    except Exception as exc:
        status["errors"].append(str(exc))
        _record_event(status, "error", message=str(exc))
        status["result"]["order_status"] = "error"
        code = 1
    else:
        for row in status["decisions"]:
            if row["signal_id"] == selected.signal_id and row["selected_for_submit"]:
                row["submitted"] = True
                break
        code = 0

    status["finished_at"] = _utc_now()
    _write_status(args, status)
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an IBKR simulated-signal batch rejection audit with one-order safety cap."
    )
    parser.add_argument("--signals-json", required=True, help="JSON array of simulated signals")
    parser.add_argument("--ibkr-host", default="127.0.0.1")
    parser.add_argument("--ibkr-port", type=int, default=7497)
    parser.add_argument("--ibkr-client-id", type=int, default=89)
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--max-order-notional", type=float, default=5.0)
    parser.add_argument("--cancel-after-seconds", type=float, default=5.0)
    parser.add_argument(
        "--submit-one-valid-paper-order",
        action="store_true",
        help="Submit at most one accepted signal as a constrained paper order.",
    )
    parser.add_argument(
        "--i-understand-this-submits-a-paper-order",
        required=True,
        help="Must exactly equal YES_PAPER_ORDER_ONLY",
    )
    parser.add_argument(
        "--status-output",
        default="reports/ibkr/simulated_signal_batch_audit_status.json",
        help="Path to write required batch-audit status artifact.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
