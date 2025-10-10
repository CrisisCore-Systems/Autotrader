"""Collector interfaces for ingesting pump and dump related signals."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Iterable, Optional


@dataclass
class CollectedEvent:
    """Represents a raw event emitted from any upstream integration."""

    source: str
    payload: Dict[str, object]


class BaseCollector(abc.ABC):
    """Abstract collector interface."""

    source: str

    def __init__(self, source: str) -> None:
        self.source = source

    @abc.abstractmethod
    async def collect(self) -> AsyncIterator[CollectedEvent]:
        """Yield events from the upstream provider."""


class StaticSampleCollector(BaseCollector):
    """Collector used in tests – it replays an in-memory iterable."""

    def __init__(self, source: str, events: Iterable[Dict[str, object]]) -> None:
        super().__init__(source)
        self._events = list(events)

    async def collect(self) -> AsyncIterator[CollectedEvent]:
        for payload in self._events:
            yield CollectedEvent(source=self.source, payload=dict(payload))


class CollectorRegistry:
    """Registry keeping track of available collectors."""

    def __init__(self) -> None:
        self._collectors: Dict[str, BaseCollector] = {}

    def register(self, collector: BaseCollector, *, override: bool = False) -> None:
        if not override and collector.source in self._collectors:
            raise ValueError(f"Collector for source '{collector.source}' already registered")
        self._collectors[collector.source] = collector

    def get(self, source: str) -> Optional[BaseCollector]:
        return self._collectors.get(source)

    def all(self) -> Iterable[BaseCollector]:
        return list(self._collectors.values())
