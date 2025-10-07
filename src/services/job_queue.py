"""Persistent job queue used to smooth ingestion bursts."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping


@dataclass(frozen=True)
class JobContext:
    job_id: int | None
    kind: str
    key: str
    leased: bool = False


class PersistentJobQueue:
    """SQLite backed queue with retry backoff."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                job_key TEXT NOT NULL,
                payload TEXT,
                priority INTEGER NOT NULL DEFAULT 5,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                not_before REAL,
                last_error TEXT,
                updated_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(kind, job_key)
            );
            """
        )
        self._conn.commit()

    def enqueue(self, kind: str, key: str, payload: Mapping[str, Any] | None = None, *, priority: int = 5) -> JobContext:
        now = _now()
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO ingestion_jobs (kind, job_key, payload, priority, status, attempts, not_before, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?, ?)
                ON CONFLICT(kind, job_key)
                DO UPDATE SET priority=excluded.priority, payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (kind, key, json.dumps(payload or {}, sort_keys=True), priority, now, now),
            )
        job_id = cursor.lastrowid or self._job_id(kind, key)
        return JobContext(job_id=job_id, kind=kind, key=key, leased=False)

    def lease(self, kind: str, key: str, *, lease_seconds: float = 30.0) -> JobContext | None:
        now = time.time()
        with self._conn:
            row = self._conn.execute(
                """
                SELECT id, status, attempts, not_before FROM ingestion_jobs
                WHERE kind = ? AND job_key = ?
                """,
                (kind, key),
            ).fetchone()
            if row is None:
                return None
            if row["status"] == "completed":
                return None
            not_before = row["not_before"]
            if not_before and not_before > now:
                return None
            self._conn.execute(
                """
                UPDATE ingestion_jobs
                SET status='leased', attempts=attempts+1, not_before=? , updated_at=?
                WHERE id = ?
                """,
                (now + lease_seconds, _now(), row["id"]),
            )
        return JobContext(job_id=int(row["id"]), kind=kind, key=key, leased=True)

    @contextmanager
    def process(
        self,
        kind: str,
        key: str,
        *,
        payload: Mapping[str, Any] | None = None,
        lease_seconds: float = 30.0,
        backoff_seconds: float = 60.0,
    ) -> Iterator[JobContext]:
        base_context = self.enqueue(kind, key, payload)
        leased = self.lease(kind, key, lease_seconds=lease_seconds)
        if leased is None:
            yield base_context
            return
        try:
            yield leased
        except Exception as exc:
            self.fail(leased.job_id, str(exc), backoff_seconds=backoff_seconds)
            raise
        else:
            self.complete(leased.job_id)

    def complete(self, job_id: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                UPDATE ingestion_jobs
                SET status='completed', not_before=NULL, updated_at=?
                WHERE id = ?
                """,
                (_now(), job_id),
            )

    def fail(self, job_id: int, error: str, *, backoff_seconds: float = 60.0) -> None:
        next_run = time.time() + max(backoff_seconds, 1.0)
        with self._conn:
            self._conn.execute(
                """
                UPDATE ingestion_jobs
                SET status='pending', not_before=?, last_error=?, updated_at=?
                WHERE id = ?
                """,
                (next_run, error[:512], _now(), job_id),
            )

    def _job_id(self, kind: str, key: str) -> int:
        row = self._conn.execute(
            """SELECT id FROM ingestion_jobs WHERE kind = ? AND job_key = ?""",
            (kind, key),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Job {kind}:{key} not found")
        return int(row["id"])


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


__all__ = ["JobContext", "PersistentJobQueue"]
