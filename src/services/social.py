"""Social feed aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from typing import Iterable, List, Mapping, MutableMapping, Sequence

from src.core.clients import SocialFeedClient


@dataclass(frozen=True)
class SocialStream:
    """Configuration for a social feed endpoint."""

    url: str
    platform: str
    label: str | None = None


@dataclass
class SocialPost:
    """Normalized representation of a social post."""

    id: str
    platform: str
    author: str
    content: str
    url: str
    posted_at: datetime | None
    metrics: MutableMapping[str, float | int] = field(default_factory=dict)


class SocialAggregator:
    """Fetch and normalize social posts across configured streams."""

    def __init__(
        self,
        client: SocialFeedClient,
        *,
        streams: Sequence[SocialStream] | None = None,
        max_per_stream: int = 50,
    ) -> None:
        self._client = client
        self._streams = list(streams or [])
        self._max_per_stream = max(1, int(max_per_stream))

    def collect(self, *, limit: int = 100) -> List[SocialPost]:
        posts: List[SocialPost] = []
        for stream in self._streams:
            try:
                payload = self._client.fetch_posts(stream.url, limit=self._max_per_stream)
            except Exception:
                continue
            for item in payload[: self._max_per_stream]:
                normalized = _normalize_post(item, stream)
                if normalized is None:
                    continue
                posts.append(normalized)

        deduped: List[SocialPost] = []
        seen: set[str] = set()
        for post in sorted(posts, key=_sort_key, reverse=True):
            if post.id in seen:
                continue
            seen.add(post.id)
            deduped.append(post)
            if len(deduped) >= limit:
                break
        return deduped


def _normalize_post(payload: Mapping[str, object], stream: SocialStream) -> SocialPost | None:
    content = _string(payload, "content") or _string(payload, "text") or ""
    content = content.strip()
    if not content:
        return None

    author = _string(payload, "author") or _string(payload, "username") or ""
    url = _string(payload, "url") or _string(payload, "link") or ""
    timestamp = payload.get("timestamp") or payload.get("created_at") or payload.get("published_at")
    posted_at = _parse_datetime(timestamp)

    identifier = (
        _string(payload, "id")
        or _string(payload, "post_id")
        or _string(payload, "guid")
        or url
        or _hash_identifier(stream.platform, author, content, posted_at)
    )

    metrics = {}
    for key in ("likes", "upvotes", "retweets", "replies", "comments", "shares"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            metrics[key] = value

    return SocialPost(
        id=str(identifier),
        platform=stream.platform,
        author=author.strip(),
        content=content,
        url=url,
        posted_at=posted_at,
        metrics=metrics,
    )


def _string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value
    return ""


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(cleaned)
        except ValueError:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", cleaned)
            if match:
                try:
                    return datetime.fromisoformat(match.group(1)).replace(tzinfo=timezone.utc)
                except ValueError:
                    return None
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _hash_identifier(platform: str, author: str, content: str, posted_at: datetime | None) -> str:
    digest = hashlib.sha256()
    digest.update(platform.encode("utf-8"))
    digest.update(b"|")
    digest.update(author.encode("utf-8"))
    digest.update(b"|")
    digest.update(content.encode("utf-8"))
    digest.update(b"|")
    digest.update((posted_at.isoformat() if posted_at else "").encode("utf-8"))
    return digest.hexdigest()


def _sort_key(post: SocialPost) -> datetime:
    return post.posted_at or datetime.fromtimestamp(0, tz=timezone.utc)


__all__ = ["SocialAggregator", "SocialPost", "SocialStream"]
