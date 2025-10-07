"""Tests for news aggregation utilities."""

from __future__ import annotations

import time
from types import SimpleNamespace

from src.services.news import NewsAggregator, NewsItem


class StubNewsClient:
    def __init__(self, feeds: dict[str, list[dict[str, object]]]) -> None:
        self._feeds = feeds

    def fetch_feed(self, url: str):  # noqa: D401 - stub
        entries = self._feeds.get(url, [])
        return SimpleNamespace(entries=entries, feed={"title": url})


def _entry(title: str, summary: str, link: str, timestamp: int) -> dict[str, object]:
    return {
        "title": title,
        "summary": summary,
        "link": link,
        "published_parsed": time.gmtime(timestamp),
    }


def test_news_aggregator_filters_by_keyword() -> None:
    feeds = {
        "feed-a": [
            _entry("Token ABC surges", "Positive developments", "a", 1_700_000_000),
            _entry("Macro news", "Unrelated", "b", 1_700_000_100),
        ],
    }
    aggregator = NewsAggregator(StubNewsClient(feeds), default_feeds=["feed-a"], max_per_feed=5)

    items = aggregator.collect(keywords=["ABC"], limit=5)

    assert len(items) == 1
    assert isinstance(items[0], NewsItem)
    assert items[0].title == "Token ABC surges"


def test_news_aggregator_deduplicates_links_across_feeds() -> None:
    shared_entry = _entry("Token ABC surges", "Duplicate", "shared", 1_700_000_000)
    feeds = {
        "feed-a": [shared_entry],
        "feed-b": [shared_entry],
    }

    aggregator = NewsAggregator(StubNewsClient(feeds), default_feeds=["feed-a", "feed-b"], max_per_feed=5)

    items = aggregator.collect(limit=10)

    assert len(items) == 1
    assert items[0].link == "shared"
