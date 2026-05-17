#!/usr/bin/env python
"""Guard-first IBKR paper harness for simulated strategy signals."""

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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refuse_unless(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _parse_side(value: str) -> OrderSide:
    mapped = {"BUY": OrderSide.BUY, "SELL": OrderSide.SELL}
    key = str(value).strip().upper()
    if key not in mapped:
        raise ValueError(f"Unsupported side: {value}")
    return mapped[key]


def _assert_harness_safety(args: argparse.Namespace) -> None:
    host = str(args.ibkr_host).strip().lower()
    _refuse_unless(
        host in ALLOWED_HOSTS,
        f"Refusing harness: host must be localhost/127.0.0.1, got {args.ibkr_host}.",
    )
    _refuse_unless(
        int(args.ibkr_port) == 7497,
        f"Refusing harness: expected paper TWS port 7497, got {args.ibkr_port}.",
    )
    _refuse_unless(
        str(args.i_understand_this_submits_a_paper_order) == CONFIRM_PHRASE,
        "Refusing harness: confirmation phrase mismatch.",
    )
    _refuse_unless(
        0.0 < float(args.max_order_notional) <= 5.0,
        "Refusing harness: --max-order-notional must be > 0 and <= 5.",
    )
    _refuse_unless(
        0.0 <= float(args.min_confidence) <= 1.0,
        "Refusing harness: --min-confidence must be between 0 and 1.",
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


def _validate_signal(signal: Signal, args: argparse.Namespace, host: str, port: int, phrase: str) -> List[str]:
    issues: List[str] = []

    if host.strip().lower() not in ALLOWED_HOSTS:
        issues.append(f"live-looking host not allowed: {host}")
    if int(port) != 7497:
        issues.append(f"paper port 7497 required, got {port}")
    if phrase != CONFIRM_PHRASE:
        issues.append("missing or invalid confirmation phrase")

    if signal.sec_type != ALLOWED_SEC_TYPE:
        issues.append(f"unsupported sec_type: {signal.sec_type}")
    if signal.order_type != ALLOWED_ORDER_TYPE:
        issues.append(f"order_type must be LMT, got {signal.order_type}")
    if signal.limit_price is None:
        issues.append("limit_price is required")
    elif signal.limit_price <= 0:
        issues.append("limit_price must be > 0")

    if abs(signal.quantity - round(signal.quantity)) > 1e-9:
        issues.append(f"STK quantity must be whole number, got {signal.quantity}")

    if signal.confidence < float(args.min_confidence):
        issues.append(
            f"confidence below threshold: {signal.confidence:.4f} < {float(args.min_confidence):.4f}"
        )

    if signal.source != ALLOWED_SOURCE:
        issues.append(f"unknown signal source: {signal.source}")

    if signal.limit_price is not None:
        notional = float(signal.quantity) * float(signal.limit_price)
        if notional > float(args.max_order_notional):
            issues.append(
                f"notional over cap: {notional:.4f} > {float(args.max_order_notional):.4f}"
            )

    return issues


def _default_valid_signal() -> Dict[str, Any]:
    return {
        "signal_id": "sim-001",
        "symbol": "SNDL",
        "sec_type": "STK",
        "currency": "USD",
        "exchange": "SMART",
        "side": "BUY",
        "quantity": 1,
        "order_type": "LMT",
        "limit_price": 1.00,
        "confidence": 0.72,
        "source": "simulated_signal",
    }


def _load_valid_signal(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.signals_json:
        return _default_valid_signal()

    source_path = (PROJECT_ROOT / args.signals_json).resolve()
    with source_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)

    if isinstance(loaded, list):
        if not loaded:
            raise ValueError("signals-json list is empty")
        if not isinstance(loaded[0], dict):
            raise ValueError("signals-json first list item must be an object")
        return loaded[0]

    if not isinstance(loaded, dict):
        raise ValueError("signals-json must be an object or array of objects")
    return loaded


def _reject_fixtures(valid_signal: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "name": "wrong_port",
            "expect": "reject",
            "context": {"port": 7496},
            "signal": valid_signal,
        },
        {
            "name": "missing_confirmation_phrase",
            "expect": "reject",
            "context": {"phrase": ""},
            "signal": valid_signal,
        },
        {
            "name": "market_order",
            "expect": "reject",
            "signal": {**valid_signal, "order_type": "MKT"},
        },
        {
            "name": "notional_over_cap",
            "expect": "reject",
            "signal": {**valid_signal, "quantity": 10, "limit_price": 1.00},
        },
        {
            "name": "fractional_stk_quantity",
            "expect": "reject",
            "signal": {**valid_signal, "quantity": 1.5},
        },
        {
            "name": "unsupported_sec_type",
            "expect": "reject",
            "signal": {**valid_signal, "sec_type": "OPT"},
        },
        {
            "name": "missing_limit_price",
            "expect": "reject",
            "signal": {**valid_signal, "limit_price": None},
        },
        {
            "name": "confidence_below_threshold",
            "expect": "reject",
            "signal": {**valid_signal, "confidence": 0.1},
        },
        {
            "name": "unknown_signal_source",
            "expect": "reject",
            "signal": {**valid_signal, "source": "unknown_source"},
        },
        {
            "name": "live_looking_host",
            "expect": "reject",
            "context": {"host": "10.0.0.7"},
            "signal": valid_signal,
        },
    ]


def _build_status(args: argparse.Namespace, valid_signal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "started_at": _utc_now(),
        "mode": "ibkr_simulated_signal_paper_harness",
        "constraints": {
            "allowed_hosts": sorted(ALLOWED_HOSTS),
            "paper_port": 7497,
            "sec_type": ALLOWED_SEC_TYPE,
            "order_type": ALLOWED_ORDER_TYPE,
            "max_order_notional": float(args.max_order_notional),
            "min_confidence": float(args.min_confidence),
            "confirmation_phrase_required": CONFIRM_PHRASE,
            "one_order_max_per_run": True,
        },
        "request": {
            "host": args.ibkr_host,
            "port": int(args.ibkr_port),
            "client_id": int(args.ibkr_client_id),
            "submit_valid_signal": bool(args.submit_valid_signal),
            "cancel_after_seconds": float(args.cancel_after_seconds),
            "signals_json": args.signals_json,
        },
        "valid_signal": valid_signal,
        "fixtures": [],
        "events": [],
        "errors": [],
        "result": {
            "fixtures_passed": False,
            "accepted_signal_id": None,
            "order_submission_attempted": False,
            "connected": False,
            "submitted": False,
            "cancel_attempted": False,
            "cancelled": False,
            "order_id": None,
            "order_status": None,
        },
    }


def _record_event(status_doc: Dict[str, Any], event_name: str, **fields: Any) -> None:
    payload = {"at": _utc_now(), "event": event_name}
    payload.update(fields)
    status_doc["events"].append(payload)


def _evaluate_fixture(fixture: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    context = fixture.get("context", {})
    host = context.get("host", args.ibkr_host)
    port = int(context.get("port", args.ibkr_port))
    phrase = context.get("phrase", args.i_understand_this_submits_a_paper_order)

    signal = _signal_from_dict(dict(fixture["signal"]))
    issues = _validate_signal(signal, args, host=host, port=port, phrase=phrase)
    accepted = len(issues) == 0

    expected = str(fixture.get("expect", "reject"))
    expected_accepted = expected.lower() == "accept"

    return {
        "name": fixture["name"],
        "expected": expected,
        "accepted": accepted,
        "matched_expectation": accepted == expected_accepted,
        "issues": issues,
        "signal": asdict(signal),
        "context": {"host": host, "port": port, "phrase_ok": phrase == CONFIRM_PHRASE},
    }


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
            "probe_type": "simulated_signal_paper_harness",
            "signal_id": signal.signal_id,
            "source": signal.source,
        },
    )


async def _execute_one_order(args: argparse.Namespace, status: Dict[str, Any], signal: Signal) -> None:
    adapter = IBKRAdapter(
        host=str(args.ibkr_host),
        port=int(args.ibkr_port),
        client_id=int(args.ibkr_client_id),
    )
    order = _build_order(signal)

    connected = await adapter.connect()
    status["result"]["connected"] = bool(connected)
    _record_event(status, "connect", ok=bool(connected))
    if not connected:
        raise RuntimeError("Failed to connect to IBKR paper TWS/Gateway.")

    submitted = await adapter.submit_order(order)
    status["result"]["submitted"] = True
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
    _assert_harness_safety(args)
    valid_signal_payload = _load_valid_signal(args)
    status = _build_status(args, valid_signal_payload)

    fixtures = _reject_fixtures(valid_signal_payload)
    fixture_results: List[Dict[str, Any]] = []
    fixture_mismatch = False

    for fixture in fixtures:
        result = _evaluate_fixture(fixture, args)
        fixture_results.append(result)
        if not bool(result["matched_expectation"]):
            fixture_mismatch = True

    status["fixtures"] = fixture_results
    status["result"]["fixtures_passed"] = not fixture_mismatch

    valid_signal = _signal_from_dict(valid_signal_payload)
    valid_issues = _validate_signal(
        valid_signal,
        args,
        host=args.ibkr_host,
        port=int(args.ibkr_port),
        phrase=args.i_understand_this_submits_a_paper_order,
    )
    if valid_issues:
        status["errors"].append("Valid signal rejected by guard stack.")
        status["errors"].extend(valid_issues)
        _record_event(status, "valid_signal_rejected", issues=valid_issues)
        status["finished_at"] = _utc_now()
        _write_status(args, status)
        return 1

    status["result"]["accepted_signal_id"] = valid_signal.signal_id
    _record_event(status, "valid_signal_accepted", signal_id=valid_signal.signal_id)

    if fixture_mismatch:
        status["errors"].append("One or more reject fixtures did not reject as expected.")
        _record_event(status, "fixture_mismatch")
        status["finished_at"] = _utc_now()
        _write_status(args, status)
        return 1

    if not bool(args.submit_valid_signal):
        _record_event(status, "dry_run_only", message="Valid signal accepted but order submission disabled.")
        status["finished_at"] = _utc_now()
        _write_status(args, status)
        return 0

    status["result"]["order_submission_attempted"] = True
    try:
        await _execute_one_order(args, status, valid_signal)
    except Exception as exc:
        status["errors"].append(str(exc))
        _record_event(status, "error", message=str(exc))
        status["result"]["order_status"] = "error"
        return_code = 1
    else:
        return_code = 0

    status["finished_at"] = _utc_now()
    _write_status(args, status)
    return return_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a guard-first IBKR paper harness against simulated strategy signals."
    )
    parser.add_argument("--ibkr-host", default="127.0.0.1")
    parser.add_argument("--ibkr-port", type=int, default=7497)
    parser.add_argument("--ibkr-client-id", type=int, default=78)
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--max-order-notional", type=float, default=5.0)
    parser.add_argument("--cancel-after-seconds", type=float, default=5.0)
    parser.add_argument(
        "--signals-json",
        default="",
        help="Optional JSON file containing one valid simulated signal (object or array).",
    )
    parser.add_argument(
        "--submit-valid-signal",
        "--submit-paper-order",
        dest="submit_valid_signal",
        action="store_true",
        help="Submit exactly one valid constrained paper LMT order after reject fixtures pass.",
    )
    parser.add_argument(
        "--i-understand-this-submits-a-paper-order",
        required=True,
        help="Must exactly equal YES_PAPER_ORDER_ONLY",
    )
    parser.add_argument(
        "--status-output",
        default="reports/ibkr/simulated_signal_paper_harness_status.json",
        help="Path to write required harness status artifact.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())