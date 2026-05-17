#!/usr/bin/env python3
"""
TR-007-TELEMETRY: High-Resolution Post-Trade Execution Ledger & Analytics
Compiles raw epoch timestamp metrics and pre-computed latency deltas.
"""

import os
import json
import time
import logging
import sys
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TR-007-Telemetry")


class ExecutionTelemetryArchiver:
    def __init__(self, export_path: str):
        self.export_path = export_path
        os.makedirs(os.path.dirname(self.export_path), exist_ok=True)

    def compile_and_export(
        self,
        lifecycle_history: Dict[str, Any],
        terminal_status: str,
        failure_reason: Optional[str] = None,
    ):
        """
        Gathers raw lifecycle timestamps, computes derived latency deltas,
        and flattens the dataset into a canonical JSONL ledger line.
        """
        # Extract raw timestamps
        ts_ingested = lifecycle_history.get("ts_ingested", 0)
        ts_dispatched = lifecycle_history.get("ts_dispatched", 0)
        ts_first_partial = lifecycle_history.get("ts_first_partial_fill", 0)
        ts_final = lifecycle_history.get("ts_final_settlement", 0)

        # Compute derived latencies (safely handling omitted optional phases)
        latency_ingest_to_dispatch = max(0, ts_dispatched - ts_ingested) if ts_dispatched and ts_ingested else 0

        if ts_first_partial and ts_dispatched:
            latency_dispatch_to_first_partial = max(0, ts_first_partial - ts_dispatched)
            latency_first_partial_to_final = max(0, ts_final - ts_first_partial) if ts_final else 0
        else:
            latency_dispatch_to_first_partial = 0
            latency_first_partial_to_final = 0

        latency_end_to_end = max(0, ts_final - ts_ingested) if ts_final and ts_ingested else 0

        # Calculate exact fills and notional exposure values
        total_qty = float(lifecycle_history.get("total_quantity", 0.0))
        filled_qty = float(lifecycle_history.get("filled_quantity", 0.0))
        avg_price = float(lifecycle_history.get("avg_fill_price", 0.0))
        total_notional = round(filled_qty * avg_price, 4)

        completion_ratio = round(filled_qty / total_qty, 4) if total_qty > 0 else 0.0

        telemetry_record = {
            "identity": {
                "order_id": lifecycle_history.get("order_id"),
                "signal_id": lifecycle_history.get("signal_id"),
                "symbol": lifecycle_history.get("symbol"),
                "side": lifecycle_history.get("side"),
            },
            "pricing_metrics": {
                "total_quantity": total_qty,
                "avg_fill_price": avg_price,
                "total_notional": total_notional,
            },
            "lifecycle_timestamps": {
                "ts_ingested": ts_ingested,
                "ts_dispatched": ts_dispatched,
                "ts_first_partial_fill": ts_first_partial,
                "ts_final_settlement": ts_final,
            },
            "derived_latencies_ms": {
                "latency_ingest_to_dispatch": latency_ingest_to_dispatch,
                "latency_dispatch_to_first_partial": latency_dispatch_to_first_partial,
                "latency_first_partial_to_final": latency_first_partial_to_final,
                "latency_end_to_end": latency_end_to_end,
            },
            "terminal_summary": {
                "terminal_status": terminal_status,
                "completion_ratio": completion_ratio,
                "failure_reason": failure_reason or "N/A",
            },
            "audit_metadata": {
                "exported_at": int(time.time() * 1000),
                "source_module": "TR-007-CORE",
                "schema_version": "1.0.0",
            },
        }

        # Append to offline-first JSONL metrics ledger
        with open(self.export_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(telemetry_record) + "\n")

        logger.info(
            f"📊 [Telemetry Export] Order {lifecycle_history.get('order_id')} archived successfully | "
            f"Status: {terminal_status} | E2E Latency: {latency_end_to_end}ms"
        )


# --- Verification Suite simulating multiple terminal settlement conditions ---
def run_telemetry_simulation():
    ledger_path = "scripts/fixtures/ibkr/execution_performance.jsonl"
    if os.path.exists(ledger_path):
        os.remove(ledger_path)

    archiver = ExecutionTelemetryArchiver(ledger_path)
    now = int(time.time() * 1000)

    logger.info("--- Condition A: Full Execution Pipeline (Filled) ---")
    order_a = {
        "order_id": 2001,
        "signal_id": "SIG-101",
        "symbol": "AAPL",
        "side": "BUY",
        "total_quantity": 100.0,
        "filled_quantity": 100.0,
        "avg_fill_price": 175.50,
        "ts_ingested": now,
        "ts_dispatched": now + 45,
        "ts_first_partial_fill": now + 245,
        "ts_final_settlement": now + 645,
    }
    archiver.compile_and_export(order_a, "Filled")

    logger.info("--- Condition B: Market Drop Cancellation (Cancelled) ---")
    order_b = {
        "order_id": 2002,
        "signal_id": "SIG-102",
        "symbol": "TSLA",
        "side": "SELL",
        "total_quantity": 50.0,
        "filled_quantity": 10.0,
        "avg_fill_price": 220.00,
        "ts_ingested": now,
        "ts_dispatched": now + 35,
        "ts_first_partial_fill": now + 135,
        "ts_final_settlement": now + 335,
    }
    archiver.compile_and_export(order_b, "Cancelled", failure_reason="User cancel instruction received.")

    logger.info("--- Condition C: Exchange Rejection Gate (Rejected) ---")
    order_c = {
        "order_id": 2003,
        "signal_id": "SIG-103",
        "symbol": "NVDA",
        "side": "BUY",
        "total_quantity": 30.0,
        "filled_quantity": 0.0,
        "avg_fill_price": 0.00,
        "ts_ingested": now,
        "ts_dispatched": now + 20,
        "ts_first_partial_fill": None,
        "ts_final_settlement": now + 50,
    }
    archiver.compile_and_export(order_c, "Rejected", failure_reason="Insufficient margin allocation.")

    # Verification and validation check
    logger.info("\n=== Post-Flight Telemetry Verification ===")
    with open(ledger_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]

    assert len(records) == 3, "Telemetry failed to export all three test records."

    # Assert on A
    assert records[0]["derived_latencies_ms"]["latency_end_to_end"] == 645, "Latency delta computation wrong for order A."
    assert records[0]["terminal_summary"]["completion_ratio"] == 1.0, "Completion ratio calculation wrong for order A."

    # Assert on C
    assert records[2]["pricing_metrics"]["total_notional"] == 0.0, "Notional calculation wrong for rejected route."
    assert (
        records[2]["derived_latencies_ms"]["latency_dispatch_to_first_partial"] == 0
    ), "Partial latency should be zeroed if unexecuted."

    print("\nTR-007-TELEMETRY: ALL EXPERIMENTAL ROUTES PASS ✅")


if __name__ == "__main__":
    run_telemetry_simulation()
