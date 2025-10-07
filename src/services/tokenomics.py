"""Tokenomics aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Mapping, MutableMapping, Sequence

from src.core.clients import TokenomicsClient
from src.services.job_queue import PersistentJobQueue


@dataclass(frozen=True)
class TokenSpec:
    """Configuration describing how to fetch tokenomics for a token."""

    symbol: str
    url: str
    source: str | None = None


@dataclass
class TokenomicsSnapshot:
    """Normalized tokenomics datapoint."""

    token: str
    metric: str
    value: float
    unit: str
    source: str
    recorded_at: datetime | None
    metadata: MutableMapping[str, object] = field(default_factory=dict)


class TokenomicsAggregator:
    """Fetch and flatten tokenomics payloads into structured snapshots."""

    def __init__(
        self,
        client: TokenomicsClient,
        *,
        tokens: Sequence[TokenSpec] | None = None,
        job_queue: PersistentJobQueue | None = None,
    ) -> None:
        self._client = client
        self._tokens = list(tokens or [])
        self._queue = job_queue

    def collect(self) -> List[TokenomicsSnapshot]:
        snapshots: List[TokenomicsSnapshot] = []
        for token in self._tokens:
            payload = None
            if self._queue:
                with self._queue.process(
                    "tokenomics",
                    token.url,
                    payload={"symbol": token.symbol},
                    backoff_seconds=300.0,
                ) as job:
                    if not job.leased:
                        continue
                    payload = self._safe_fetch(token.url)
            else:
                payload = self._safe_fetch(token.url)
            if payload is None:
                continue
            for snapshot in _flatten_payload(token, payload):
                snapshots.append(snapshot)
        return snapshots

    def _safe_fetch(self, url: str) -> Mapping[str, object] | None:
        try:
            return self._client.fetch_token_metrics(url)
        except Exception:
            return None


def _flatten_payload(token: TokenSpec, payload: Mapping[str, object]) -> Iterable[TokenomicsSnapshot]:
    source = token.source or str(payload.get("source") or "tokenomics")
    timestamp = payload.get("timestamp") or payload.get("as_of")
    recorded_at = _parse_datetime(timestamp)

    supply = payload.get("supply")
    if isinstance(supply, Mapping):
        for key, value in supply.items():
            if isinstance(value, (int, float)):
                yield TokenomicsSnapshot(
                    token=token.symbol,
                    metric=f"supply_{key}",
                    value=float(value),
                    unit="tokens",
                    source=source,
                    recorded_at=recorded_at,
                )

    metrics = payload.get("metrics")
    if isinstance(metrics, Mapping):
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                yield TokenomicsSnapshot(
                    token=token.symbol,
                    metric=str(key),
                    value=float(value),
                    unit=str(payload.get("unit", "")),
                    source=source,
                    recorded_at=recorded_at,
                )

    unlocks = payload.get("upcoming_unlocks") or payload.get("unlocks")
    if isinstance(unlocks, Sequence):
        for entry in unlocks:
            if not isinstance(entry, Mapping):
                continue
            percent = entry.get("percent") or entry.get("percentage")
            if not isinstance(percent, (int, float)):
                continue
            unlock_time = entry.get("date") or entry.get("timestamp")
            unlock_at = _parse_datetime(unlock_time) or recorded_at
            metadata: MutableMapping[str, object] = {
                key: value
                for key, value in entry.items()
                if key not in {"percent", "percentage", "date", "timestamp"}
            }
            yield TokenomicsSnapshot(
                token=token.symbol,
                metric="unlock_percent",
                value=float(percent),
                unit="percent",
                source=source,
                recorded_at=unlock_at,
                metadata=metadata,
            )


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        if not cleaned:
            return None
        try:
            dt = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


__all__ = ["TokenomicsAggregator", "TokenomicsSnapshot", "TokenSpec"]
