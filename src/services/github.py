"""GitHub activity aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Mapping, MutableMapping, Sequence

from src.core.clients import GitHubClient


@dataclass(frozen=True)
class RepositorySpec:
    """Identifier for a GitHub repository."""

    owner: str
    name: str

    @classmethod
    def from_string(cls, value: str) -> "RepositorySpec":
        owner, _, name = value.partition("/")
        if not owner or not name:
            raise ValueError(f"Invalid repository spec: {value}")
        return cls(owner=owner.strip(), name=name.strip())


@dataclass
class GitHubEvent:
    """Normalized representation of a GitHub activity event."""

    id: str
    repo: str
    type: str
    title: str
    url: str
    event_at: datetime | None
    metadata: MutableMapping[str, object] = field(default_factory=dict)


class GitHubActivityAggregator:
    """Fetch recent GitHub events for configured repositories."""

    def __init__(
        self,
        client: GitHubClient,
        *,
        repositories: Sequence[RepositorySpec] | None = None,
        per_repo: int = 30,
    ) -> None:
        self._client = client
        self._repositories = list(repositories or [])
        self._per_repo = max(1, int(per_repo))

    def collect(self, *, limit: int = 100) -> List[GitHubEvent]:
        events: List[GitHubEvent] = []
        for repo in self._repositories:
            try:
                payload = self._client.fetch_repo_events(repo.owner, repo.name, per_page=self._per_repo)
            except Exception:
                continue
            for item in payload[: self._per_repo]:
                normalized = _normalize_event(item, repo)
                if normalized is None:
                    continue
                events.append(normalized)

        deduped: List[GitHubEvent] = []
        seen: set[str] = set()
        for event in sorted(events, key=_sort_key, reverse=True):
            if event.id in seen:
                continue
            seen.add(event.id)
            deduped.append(event)
            if len(deduped) >= limit:
                break
        return deduped


def _normalize_event(payload: Mapping[str, object], spec: RepositorySpec) -> GitHubEvent | None:
    identifier = payload.get("id")
    if not identifier:
        return None

    event_type = str(payload.get("type") or "event")
    repo_name = spec.name
    repo_obj = payload.get("repo")
    if isinstance(repo_obj, Mapping):
        repo_name = str(repo_obj.get("name") or repo_name)

    created_at = payload.get("created_at")
    event_at = _parse_datetime(created_at)

    title = _extract_title(payload)
    url = _extract_url(payload)

    metadata: MutableMapping[str, object] = {}
    if isinstance(payload, Mapping):
        metadata = {
            key: value
            for key, value in payload.items()
            if key in {"actor", "payload", "public", "created_at"}
        }

    return GitHubEvent(
        id=str(identifier),
        repo=repo_name,
        type=event_type,
        title=title,
        url=url,
        event_at=event_at,
        metadata=metadata,
    )


def _extract_title(payload: Mapping[str, object]) -> str:
    actor = payload.get("actor")
    actor_login = actor.get("login") if isinstance(actor, Mapping) else ""
    event_type = payload.get("type") or "event"
    return f"{actor_login} {event_type}".strip()


def _extract_url(payload: Mapping[str, object]) -> str:
    repo = payload.get("repo")
    if isinstance(repo, Mapping):
        url = repo.get("url") or ""
        if isinstance(url, str):
            return url
    payload_url = payload.get("html_url") or payload.get("url")
    if isinstance(payload_url, str):
        return payload_url
    return ""


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
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


def _sort_key(event: GitHubEvent) -> datetime:
    return event.event_at or datetime.fromtimestamp(0, tz=timezone.utc)


__all__ = ["GitHubActivityAggregator", "GitHubEvent", "RepositorySpec"]
