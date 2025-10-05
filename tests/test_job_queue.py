from __future__ import annotations

from pathlib import Path

import pytest

from src.services.job_queue import PersistentJobQueue


@pytest.fixture()
def job_queue(tmp_path: Path) -> PersistentJobQueue:
    queue = PersistentJobQueue(tmp_path / "jobs.db")
    yield queue
    queue.close()


def test_job_queue_process_completes(job_queue: PersistentJobQueue) -> None:
    with job_queue.process("news", "feed-a", payload={"url": "https://example.com"}) as job:
        assert job.leased

    assert job_queue.lease("news", "feed-a") is None


def test_job_queue_fail_applies_backoff(job_queue: PersistentJobQueue) -> None:
    with pytest.raises(RuntimeError):
        with job_queue.process("social", "stream", backoff_seconds=5.0) as job:
            assert job.leased
            raise RuntimeError("boom")

    # Immediately attempting to lease should yield None because the job is backed off.
    assert job_queue.lease("social", "stream") is None
