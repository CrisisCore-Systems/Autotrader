from __future__ import annotations

import json
from pathlib import Path

import pytest


pytest.importorskip("ibapi")

from autotrader.execution.adapters.ibkr import _AdapterStateWALEngine


def _legacy_json_state_row(
    engine: _AdapterStateWALEngine,
    *,
    seq: int,
    order_id: int,
    signal_id: str,
    prev_status: str,
    new_status: str,
    filled: float,
    remaining: float,
    ts_ms: int,
) -> str:
    payload = {
        "seq": seq,
        "order_id": order_id,
        "signal_id": signal_id,
        "prev_status": prev_status,
        "new_status": new_status,
        "filled": filled,
        "remaining": remaining,
        "ts_ms": ts_ms,
    }
    payload["checksum"] = engine._calculate_checksum(payload)
    return json.dumps(payload)


def test_rehydrate_supports_mixed_legacy_state_and_exec_rows(tmp_path: Path) -> None:
    wal_path = tmp_path / "adapter_state_journal.wal"
    engine = _AdapterStateWALEngine(wal_path)

    lines = [
        _legacy_json_state_row(
            engine,
            seq=1,
            order_id=1001,
            signal_id="sig-1001",
            prev_status="Pending",
            new_status="Submitted",
            filled=0.0,
            remaining=2.0,
            ts_ms=1715800001000,
        ),
        "STATE|2|1715800002000|1001|PartialFill|1.0|1.0",
        "EXEC|3|1715800003000|1001|EX-ABC-001|101.25|1.0",
    ]
    wal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    trackers, fingerprints, repaired = engine.rehydrate_and_repair()

    assert repaired is False
    assert engine.current_sequence == 3
    assert trackers[1001]["status"] == "PartialFill"
    assert trackers[1001]["filled"] == pytest.approx(1.0)
    assert trackers[1001]["remaining"] == pytest.approx(1.0)
    assert "1001:EX-ABC-001" in fingerprints


def test_append_execution_fingerprint_roundtrip_rehydrates_dedupe_set(tmp_path: Path) -> None:
    wal_path = tmp_path / "adapter_state_journal.wal"
    engine = _AdapterStateWALEngine(wal_path)

    seq = engine.append_execution_fingerprint(
        order_id=77,
        exec_id="EX-DEDUP-777",
        price=250.5,
        shares=3.0,
    )

    assert seq == 1

    trackers, fingerprints, repaired = engine.rehydrate_and_repair()

    assert repaired is False
    assert trackers == {}
    assert "77:EX-DEDUP-777" in fingerprints
