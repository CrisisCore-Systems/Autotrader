#!/usr/bin/env python3
"""
TR-006-PERSIST: Write-Ahead Log (WAL) State Persistence & Rehydration
Implements crash-resilient local logging with atomic line writes and tail-repair.
"""

import os
import json
import hmac
import hashlib
import logging
import sys
from typing import Dict, Any, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TR-006-WAL")


class StateWALEngine:
    def __init__(self, filepath: str, secret_key: str = "crisis_core_secure_salt"):
        self.filepath = filepath
        self.secret_key = secret_key.encode("utf-8")
        self.current_sequence = 0

    def _calculate_checksum(self, record_payload: dict) -> str:
        """Computes a deterministic signature over the record values to capture bit-rot or truncation."""
        serialized = json.dumps(record_payload, sort_keys=True)
        return hmac.new(self.secret_key, serialized.encode("utf-8"), hashlib.sha256).hexdigest()

    def append_state_transition(
        self,
        order_id: int,
        signal_id: str,
        prev_status: str,
        new_status: str,
        filled: float,
        remaining: float,
    ):
        """
        Appends an atomic state update line to the WAL.
        Forces physical execution boundary synchronization using os.fsync.
        """
        self.current_sequence += 1

        record = {
            "seq": self.current_sequence,
            "order_id": order_id,
            "signal_id": signal_id,
            "prev_status": prev_status,
            "new_status": new_status,
            "filled": filled,
            "remaining": remaining,
        }

        # Inject validation checksum
        record["checksum"] = self._calculate_checksum(record)

        # Serialize to strict single-line entry
        line = json.dumps(record) + "\n"

        # Atomic Write-and-Flush Pattern
        fd = os.open(self.filepath, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            if hasattr(os, "fdatasync"):
                os.fdatasync(fd)
            else:
                os.fsync(fd)  # Windows fallback
        finally:
            os.close(fd)

    def rehydrate_and_repair(self) -> Tuple[Dict[int, Dict[str, Any]], bool]:
        """
        Scans the WAL line-by-line to reconstruct the latest in-memory tracker maps.
        Automatically isolates, drops, and repairs corrupted trailing sectors.
        """
        trackers = {}
        corrupted_tail_detected = False
        valid_lines = []

        if not os.path.exists(self.filepath):
            logger.info("No existing WAL trace found. Bootstrapping clean memory map.")
            return trackers, False

        logger.info(f"Scanning WAL archive for state rehydration: {self.filepath}")

        with open(self.filepath, "rb") as f:
            lines = f.readlines()

        highest_seq = 0

        for i, line_bytes in enumerate(lines):
            line_str = line_bytes.decode("utf-8", errors="ignore").strip()
            if not line_str:
                continue

            try:
                record = json.loads(line_str)
                provided_checksum = record.pop("checksum", None)

                # Check for structural integrity against hash
                expected_checksum = self._calculate_checksum(record)
                if provided_checksum != expected_checksum:
                    raise ValueError("Checksum verification mismatch. Data payload is fractured.")

                # Update high-water sequence mark
                highest_seq = max(highest_seq, record["seq"])

                # Rehydrate track coordinates
                order_id = record["order_id"]
                trackers[order_id] = {
                    "signal_id": record["signal_id"],
                    "status": record["new_status"],
                    "filled": record["filled"],
                    "remaining": record["remaining"],
                    "last_seq": record["seq"],
                }

                valid_lines.append(line_bytes)

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                # If a failure occurs, check if it's the final sector or an inline break
                if i == len(lines) - 1:
                    logger.warning(f"⚠️ Fractured trailing entry caught at file end: {e}")
                    corrupted_tail_detected = True
                else:
                    logger.critical(f"💥 FATAL CORRUPTION DETECTED IN MID-WAL SECTOR (Line {i+1}): {e}")
                    raise SystemError("WAL security domain breached. Inline integrity check failed.")

        self.current_sequence = highest_seq

        # Execute Tail Repair if truncation is active
        if corrupted_tail_detected:
            logger.warning("Executing file recovery rewrite to repair tail truncation...")
            with open(self.filepath, "wb") as f:
                for v_line in valid_lines:
                    f.write(v_line)
            logger.info("🛡️ Tail repair completed cleanly. Integrity restored.")

        return trackers, corrupted_tail_detected


# --- Simulation Runner for Crash Validation ---
def execute_crash_simulation_harness():
    wal_path = "scripts/fixtures/ibkr/state_journal.wal"
    os.makedirs(os.path.dirname(wal_path), exist_ok=True)

    # Clean old run traces if they exist
    if os.path.exists(wal_path):
        os.remove(wal_path)

    engine = StateWALEngine(wal_path)

    logger.info("--- Step 1: Simulating Healthy Order Pipeline Transitions ---")
    engine.append_state_transition(1001, "SIG-901", "Pending", "Submitted", 0.0, 100.0)
    engine.append_state_transition(1001, "SIG-901", "Submitted", "PartiallyFilled", 50.0, 50.0)
    engine.append_state_transition(1002, "SIG-902", "Pending", "Submitted", 0.0, 200.0)

    # Verify healthy rehydration
    trackers, was_repaired = engine.rehydrate_and_repair()
    logger.info(f"Rehydrated Active Maps: {json.dumps(trackers, indent=2)}")

    logger.info("\n--- Step 2: Injecting Synthetic Partial-Write Corruption Sector ---")
    # Manually append a broken line mimicking a hard crash mid-write
    with open(wal_path, "a") as f:
        f.write(
            '{"seq": 4, "order_id": 1002, "signal_id": "SIG-902", "prev_status": "Submitted", "new_status": "Fil'
        )  # Missing termination bracket and signature

    logger.info("WAL file corrupted on disk. Triggering initialization boot scan...")

    # Execute rehydration loop over the fractured data log
    rehydrated_trackers, was_repaired = engine.rehydrate_and_repair()

    logger.info(f"Post-Repair Rehydrated Maps: {json.dumps(rehydrated_trackers, indent=2)}")
    assert was_repaired is True, "Verification failed: The engine did not identify and flag the broken tail."
    assert (
        1002 in rehydrated_trackers and rehydrated_trackers[1002]["status"] == "Submitted"
    ), "Verification failed: Valid historical records were incorrectly wiped."

    print("\nTR-006-PERSIST: WAL RECOVERY ALL PASS ✅")


if __name__ == "__main__":
    execute_crash_simulation_harness()
