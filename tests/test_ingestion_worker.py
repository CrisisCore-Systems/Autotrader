from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from src.core.worker import IngestionWorker, WorkerConfig
from src.services.github import GitHubEvent, GitHubActivityAggregator, RepositorySpec
from src.services.news import NewsAggregator, NewsItem
from src.services.social import SocialAggregator, SocialPost, SocialStream
from src.services.storage import IngestionStore, EMBEDDING_DIMENSION
from src.services.tokenomics import TokenSpec, TokenomicsAggregator, TokenomicsSnapshot


class StubNewsAggregator(NewsAggregator):
    def __init__(self) -> None:  # noqa: D401 - stub
        pass

    def collect(self, *, feeds=None, keywords=None, limit=50):  # noqa: D401 - stub
        return [
            NewsItem(
                title="VoidBloom unlock schedule update",
                summary="VBM supply unlock reduced by 20%",
                link="https://example.com/news/vbm",
                source="ExampleNews",
                published_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
            )
        ]


class StubSocialAggregator(SocialAggregator):
    def __init__(self) -> None:  # noqa: D401 - stub
        pass

    def collect(self, *, limit=100):  # noqa: D401 - stub
        return [
            SocialPost(
                id="post-1",
                platform="nitter",
                author="oracular",
                content="VBM governance live; TOT community buzzing",
                url="https://example.com/social/1",
                posted_at=datetime(2024, 1, 6, 12, tzinfo=timezone.utc),
                metrics={"likes": 128, "retweets": 32},
            )
        ]


class StubGitHubAggregator(GitHubActivityAggregator):
    def __init__(self) -> None:  # noqa: D401 - stub
        pass

    def collect(self, *, limit=100):  # noqa: D401 - stub
        return [
            GitHubEvent(
                id="evt-1",
                repo="voidbloom/core",
                type="PushEvent",
                title="alice pushed to main",
                url="https://github.com/voidbloom/core",
                event_at=datetime(2024, 1, 4, tzinfo=timezone.utc),
                metadata={"actor": {"login": "alice"}},
            )
        ]


class StubTokenomicsAggregator(TokenomicsAggregator):
    def __init__(self) -> None:  # noqa: D401 - stub
        pass

    def collect(self):  # noqa: D401 - stub
        return [
            TokenomicsSnapshot(
                token="VBM",
                metric="supply_circulating",
                value=123_456.0,
                unit="tokens",
                source="voidbloom",
                recorded_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
                metadata={},
            ),
            TokenomicsSnapshot(
                token="VBM",
                metric="unlock_percent",
                value=4.2,
                unit="percent",
                source="voidbloom",
                recorded_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
                metadata={"cliff": "seed"},
            ),
        ]


def test_worker_persists_ingestion_payloads(tmp_path) -> None:
    db_path = tmp_path / "voidbloom.db"
    store = IngestionStore(db_path)
    config = WorkerConfig(
        poll_interval=60.0,
        news_feeds=["https://example.com/rss"],
        social_streams=[SocialStream(url="https://example.com/social", platform="nitter")],
        github_repos=[RepositorySpec(owner="voidbloom", name="core")],
        token_endpoints=[TokenSpec(symbol="VBM", url="https://example.com/tokenomics")],
    )

    worker = IngestionWorker(
        store=store,
        config=config,
        news_aggregator=StubNewsAggregator(),
        social_aggregator=StubSocialAggregator(),
        github_aggregator=StubGitHubAggregator(),
        tokenomics_aggregator=StubTokenomicsAggregator(),
    )

    worker.run_once()
    worker.run_once()  # ensure idempotency on unique keys

    conn = sqlite3.connect(db_path)
    news_rows = conn.execute("SELECT id, title, source FROM news_items").fetchall()
    assert news_rows == [("https://example.com/news/vbm", "VoidBloom unlock schedule update", "ExampleNews")]

    social_rows = conn.execute("SELECT id, platform, author FROM social_posts").fetchall()
    assert social_rows == [("post-1", "nitter", "oracular")]

    github_rows = conn.execute("SELECT id, repo, type FROM github_events").fetchall()
    assert github_rows == [("evt-1", "voidbloom/core", "PushEvent")]

    token_rows = conn.execute("SELECT token, metric, value FROM tokenomics_metrics ORDER BY metric").fetchall()
    assert token_rows == [
        ("VBM", "supply_circulating", 123_456.0),
        ("VBM", "unlock_percent", 4.2),
    ]

    vectors = conn.execute("SELECT dimension, content_id, kind FROM embeddings ORDER BY kind, content_id").fetchall()
    assert vectors == [
        (EMBEDDING_DIMENSION, "evt-1", "github"),
        (EMBEDDING_DIMENSION, "https://example.com/news/vbm", "news"),
        (EMBEDDING_DIMENSION, "post-1", "social"),
    ]

    payload = conn.execute("SELECT vector FROM embeddings WHERE content_id='post-1'").fetchone()[0]
    vector = json.loads(payload)
    assert len(vector) == EMBEDDING_DIMENSION
    assert any(abs(value) > 0 for value in vector)

    conn.close()
    store.close()
