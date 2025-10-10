"""Asynchronous streaming orchestrator backed by asyncio queues."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import AsyncIterator, Deque, Dict, Iterable, List, Sequence

from .base import BaseCollector, CollectedEvent


@dataclass
class StreamBatch:
    """Batch of harmonised events consumed by downstream feature pipelines."""

    events: Sequence[CollectedEvent]

    def by_source(self) -> Dict[str, List[CollectedEvent]]:
        buckets: Dict[str, List[CollectedEvent]] = {}
        for event in self.events:
            buckets.setdefault(event.source, []).append(event)
        return buckets


class StreamingIngestionOrchestrator:
    """Coordinates collectors and exposes a Pulsar-like async interface."""

    def __init__(self, collectors: Iterable[BaseCollector], *, batch_size: int = 32) -> None:
        self._collectors = list(collectors)
        if not self._collectors:
            raise ValueError("At least one collector must be supplied")
        self._batch_size = batch_size
        self._queue: asyncio.Queue[CollectedEvent] = asyncio.Queue(maxsize=batch_size * 4)
        self._tasks: List[asyncio.Task[None]] = []
        self._closed = asyncio.Event()

    async def _runner(self, collector: BaseCollector) -> None:
        async for event in collector.collect():
            await self._queue.put(event)
        await self._queue.put(CollectedEvent(source=collector.source, payload={"__collector_complete__": True}))

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._tasks = [loop.create_task(self._runner(collector)) for collector in self._collectors]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._closed.set()

    async def batches(self) -> AsyncIterator[StreamBatch]:
        await self.start()
        completed_collectors = set()
        buffer: Deque[CollectedEvent] = deque()
        while True:
            if len(completed_collectors) == len(self._collectors) and self._queue.empty() and not buffer:
                break
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                if buffer:
                    yield StreamBatch(events=tuple(buffer))
                    buffer.clear()
                continue

            if event.payload.get("__collector_complete__"):
                completed_collectors.add(event.source)
                continue

            buffer.append(event)
            if len(buffer) >= self._batch_size:
                yield StreamBatch(events=tuple(buffer))
                buffer.clear()

        if buffer:
            yield StreamBatch(events=tuple(buffer))

        await self.stop()
