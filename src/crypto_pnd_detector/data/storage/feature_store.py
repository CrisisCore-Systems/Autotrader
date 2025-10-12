"""In-memory representation of a Redis-like feature store."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional


@dataclass
class FeatureRecord:
    token_id: str
    values: Dict[str, float]
    timestamp: float = field(default_factory=time.time)


class InMemoryFeatureStore:
    """Simplified feature store mirroring the Redis Streams contract."""

    def __init__(self) -> None:
        self._store: Dict[str, FeatureRecord] = {}

    def put(self, record: FeatureRecord) -> None:
        self._store[record.token_id] = record

    def get(self, token_id: str) -> Optional[FeatureRecord]:
        return self._store.get(token_id)

    def snapshot(self) -> Iterable[FeatureRecord]:
        return list(self._store.values())
