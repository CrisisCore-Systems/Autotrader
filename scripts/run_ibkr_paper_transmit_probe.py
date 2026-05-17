#!/usr/bin/env python
"""Single-order IBKR paper transmit probe with strict fail-closed guardrails."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autotrader.execution.adapters import Order, OrderSide, OrderType
from autotrader.execution.adapters.ibkr import IBKRAdapter


CONFIRM_PHRASE = "YES_PAPER_ORDER_ONLY"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_side(value: str) -> OrderSide:
    raw = str(value).strip().upper()
    if raw == "BUY":
        return OrderSide.BUY
    if raw == "SELL":
        return OrderSide.SELL
    raise argparse.ArgumentTypeError(f"Unsupported side: {value}")


def _assert_safety(args: argparse.Namespace) -> None:
    host = str(args.ibkr_host).strip().lower()
    if host not in ALLOWED_HOSTS:
        raise SystemExit(f"Refusing probe: host must be localhost/127.0.0.1, got {args.ibkr_host}.")

    if int(args.ibkr_port) != 7497:
        raise SystemExit(f"Refusing probe: expected paper TWS port 7497, got {args.ibkr_port}.")

    if str(args.i_understand_this_submits_a_paper_order) != CONFIRM_PHRASE:
        raise SystemExit("Refusing probe: confirmation phrase mismatch.")

    sec_type = str(args.sec_type).strip().upper()
    if sec_type != "STK":
        raise SystemExit(f"Refusing probe: sec-type must be STK, got {args.sec_type}.")

    order_type = str(args.order_type).strip().upper()
    if order_type != "LMT":
        raise SystemExit(f"Refusing probe: order-type must be LMT, got {args.order_type}.")

    quantity = float(args.quantity)
    if abs(quantity - round(quantity)) > 1e-9:
        raise SystemExit(f"Refusing probe: STK quantity must be whole number, got {args.quantity}.")

    limit_price = float(args.limit_price)
    if limit_price <= 0.0:
        raise SystemExit("Refusing probe: --limit-price must be > 0.")

    max_notional = float(args.max_order_notional)
    if max_notional <= 0.0 or max_notional > 5.0:
        raise SystemExit(
            f"Refusing probe: --max-order-notional must be > 0 and <= 5.0, got {args.max_order_notional}."
        )

    notional = quantity * limit_price
    if notional > max_notional:
        raise SystemExit(
            f"Refusing probe: order notional {notional:.4f} exceeds max-order-notional {max_notional:.4f}."
        )


async def _run(args: argparse.Namespace) -> int:
    _assert_safety(args)

    status: Dict[str, Any] = {
        "started_at": _utc_now(),
        "mode": "ibkr_paper_transmit_probe",
        "constraints": {
            "paper_port": 7497,
            "sec_type": str(args.sec_type).upper(),
            "order_type": str(args.order_type).upper(),
            "max_order_notional": float(args.max_order_notional),
            "confirmation_phrase_required": CONFIRM_PHRASE,
        },
        "request": {
            "host": args.ibkr_host,
            "port": int(args.ibkr_port),
            "client_id": int(args.ibkr_client_id),
            "symbol": args.symbol,
            "sec_type": str(args.sec_type).upper(),
            "currency": str(args.currency).upper(),
            "exchange": str(args.exchange).upper(),
            "side": args.side.value,
            "quantity": float(args.quantity),
            "order_type": str(args.order_type).upper(),
            "limit_price": float(args.limit_price),
            "cancel_after_seconds": float(args.cancel_after_seconds),
            "transmit": True,
        },
        "events": [],
        "errors": [],
        "result": {
            "connected": False,
            "submitted": False,
            "cancel_attempted": False,
            "cancelled": False,
            "order_id": None,
            "order_status": None,
        },
    }

    output_path = (PROJECT_ROOT / args.status_output).resolve()
    adapter = IBKRAdapter(
        host=str(args.ibkr_host),
        port=int(args.ibkr_port),
        client_id=int(args.ibkr_client_id),
    )

    order = Order(
        order_id="",
        symbol=str(args.symbol).upper(),
        side=args.side,
        order_type=OrderType.LIMIT,
        quantity=float(args.quantity),
        price=float(args.limit_price),
        time_in_force="DAY",
        metadata={
            "ibkr_symbol": str(args.symbol).upper(),
            "ibkr_sec_type": str(args.sec_type).upper(),
            "ibkr_currency": str(args.currency).upper(),
            "ibkr_exchange": str(args.exchange).upper(),
            "ibkr_transmit": True,
            "probe_type": "paper_transmit_single_order",
        },
    )

    try:
        connected = await adapter.connect()
        status["result"]["connected"] = bool(connected)
        status["events"].append({"at": _utc_now(), "event": "connect", "ok": bool(connected)})
        if not connected:
            raise RuntimeError("Failed to connect to IBKR paper TWS/Gateway.")

        submitted = await adapter.submit_order(order)
        status["result"]["submitted"] = True
        status["result"]["order_id"] = submitted.order_id
        status["result"]["order_status"] = submitted.status.value
        status["events"].append(
            {
                "at": _utc_now(),
                "event": "submit",
                "order_id": submitted.order_id,
                "status": submitted.status.value,
            }
        )

        await asyncio.sleep(float(args.cancel_after_seconds))
        status["result"]["cancel_attempted"] = True
        cancelled = await adapter.cancel_order(submitted.order_id)
        status["result"]["cancelled"] = bool(cancelled)
        status["events"].append(
            {
                "at": _utc_now(),
                "event": "cancel",
                "order_id": submitted.order_id,
                "ok": bool(cancelled),
            }
        )

    except Exception as exc:
        status["errors"].append(str(exc))
        status["events"].append({"at": _utc_now(), "event": "error", "message": str(exc)})
        status["result"]["order_status"] = "error"
        return_code = 1
    else:
        return_code = 0
    finally:
        try:
            adapter.disconnect()
            status["events"].append({"at": _utc_now(), "event": "disconnect", "ok": True})
        except Exception as exc:
            status["errors"].append(f"disconnect_error: {exc}")
            status["events"].append({"at": _utc_now(), "event": "disconnect", "ok": False, "message": str(exc)})

        status["finished_at"] = _utc_now()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(status, handle, indent=2, sort_keys=True)
            handle.write("\n")

    return return_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one explicit IBKR paper transmit probe order.")
    parser.add_argument("--ibkr-host", default="127.0.0.1")
    parser.add_argument("--ibkr-port", type=int, default=7497)
    parser.add_argument("--ibkr-client-id", type=int, default=77)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--sec-type", default="STK")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--exchange", default="SMART")
    parser.add_argument("--side", type=_parse_side, default=OrderSide.BUY)
    parser.add_argument("--quantity", type=float, required=True)
    parser.add_argument("--order-type", default="LMT")
    parser.add_argument("--limit-price", type=float, required=True)
    parser.add_argument("--max-order-notional", type=float, default=5.0)
    parser.add_argument("--cancel-after-seconds", type=float, default=5.0)
    parser.add_argument(
        "--i-understand-this-submits-a-paper-order",
        required=True,
        help="Must exactly equal YES_PAPER_ORDER_ONLY",
    )
    parser.add_argument(
        "--status-output",
        default="reports/ibkr/paper_transmit_probe_status.json",
        help="Path to write probe status artifact",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
