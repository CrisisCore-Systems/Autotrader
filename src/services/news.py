"""Utilities for aggregating news feeds into narrative signals."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Sequence

from src.core.clients import NewsFeedClient
from src.services.job_queue import PersistentJobQueue


@dataclass
class NewsItem:
    """Normalized representation of a news article."""

    title: str
    summary: str
    link: str
    source: str
    published_at: datetime | None


class NewsAggregator:
    """Fetch and filter news items from configured feeds."""

    def __init__(
        self,
        client: NewsFeedClient,
        *,
        default_feeds: Sequence[str] | None = None,
        max_per_feed: int = 25,
        job_queue: PersistentJobQueue | None = None,
    ) -> None:
        self._client = client
        self._default_feeds = list(default_feeds or [])
        self._max_per_feed = max(1, int(max_per_feed))
        self._queue = job_queue

    def collect(
        self,
        *,
        feeds: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        limit: int = 50,
    ) -> List[NewsItem]:
        """Return normalised items filtered by ``keywords``.

        Parameters
        ----------
        feeds:
            Explicit feed URLs to query. Falls back to the aggregator's
            ``default_feeds`` when omitted.
        keywords:
            Optional case-insensitive keywords that must appear in either the
            title or summary. When omitted the aggregator returns all
            articles.
        limit:
            Hard cap on the number of items returned across all feeds.
        """

        feed_urls = list(feeds or self._default_feeds)
        if not feed_urls:
            return []

        normalized_keywords = [kw.lower() for kw in (keywords or []) if kw and kw.strip()]
        results: List[NewsItem] = []

        for url in feed_urls:
            if self._queue:
                with self._queue.process(
                    "news-feed",
                    url,
                    payload={"url": url},
                    backoff_seconds=300.0,
                ) as job:
                    if not job.leased:
                        continue
                    parsed = self._safe_fetch(url)
            else:
                parsed = self._safe_fetch(url)
            if parsed is None:
                continue

            entries = list(getattr(parsed, "entries", []) or [])
            feed_meta = getattr(parsed, "feed", {}) or {}
            source_title = str(feed_meta.get("title") or feed_meta.get("link") or url)

            for entry in entries[: self._max_per_feed]:
                item = _entry_to_item(entry, source_title)
                if item is None:
                    continue
                if normalized_keywords and not _matches(item, normalized_keywords):
                    continue
                results.append(item)

        # Deduplicate by link + title to avoid duplicate syndication hits.
        deduped: List[NewsItem] = []
        seen: set[str] = set()
        for item in sorted(results, key=_sort_key, reverse=True):
            key = item.link or f"{item.source}|{item.title}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break

        return deduped

    def _safe_fetch(self, url: str) -> object | None:
        try:
            return self._client.fetch_feed(url)
        except Exception:
            return None


def _matches(item: NewsItem, keywords: Iterable[str]) -> bool:
    haystack = f"{item.title} {item.summary}".lower()
    return any(keyword in haystack for keyword in keywords)


def _entry_to_item(entry: object, source: str) -> NewsItem | None:
    title = _get(entry, "title") or ""
    summary = _get(entry, "summary") or _get(entry, "description") or ""
    link = _get(entry, "link") or ""
    published = _parse_datetime(entry)

    if not title and not summary:
        return None

    clean_title = title.strip() or summary.strip()[:80]
    clean_summary = summary.strip()

    return NewsItem(
        title=clean_title,
        summary=clean_summary,
        link=link.strip(),
        source=source,
        published_at=published,
    )


def _parse_datetime(entry: object) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, attr, None) or _get(entry, attr)
        if struct:
            try:
                return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
            except (OverflowError, TypeError, ValueError):
                continue

    for attr in ("published", "updated"):
        raw = _get(entry, attr)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _sort_key(item: NewsItem) -> datetime:
    return item.published_at or datetime.fromtimestamp(0, tz=timezone.utc)


def _get(entry: object, key: str):
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key, None)
