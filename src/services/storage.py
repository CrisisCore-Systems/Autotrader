"""SQLite persistence utilities for ingestion outputs."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from src.services.github import GitHubEvent
from src.services.news import NewsItem
from src.services.social import SocialPost
from src.services.tokenomics import TokenomicsSnapshot


EMBEDDING_DIMENSION = 64


@dataclass
class IngestionStore:
    """Lightweight SQLite-backed store for feed aggregation results."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS news_items (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                url TEXT,
                source TEXT,
                published_at TEXT,
                fetched_at TEXT
            );

            CREATE TABLE IF NOT EXISTS social_posts (
                id TEXT PRIMARY KEY,
                platform TEXT,
                author TEXT,
                content TEXT,
                url TEXT,
                posted_at TEXT,
                metrics TEXT,
                fetched_at TEXT
            );

            CREATE TABLE IF NOT EXISTS github_events (
                id TEXT PRIMARY KEY,
                repo TEXT,
                type TEXT,
                title TEXT,
                url TEXT,
                event_at TEXT,
                metadata TEXT,
                fetched_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tokenomics_metrics (
                token TEXT,
                metric TEXT,
                value REAL,
                unit TEXT,
                source TEXT,
                recorded_at TEXT,
                metadata TEXT,
                fetched_at TEXT,
                PRIMARY KEY (token, metric, recorded_at)
            );

            CREATE TABLE IF NOT EXISTS embeddings (
                content_id TEXT,
                kind TEXT,
                vector TEXT,
                dimension INTEGER,
                PRIMARY KEY (content_id, kind)
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def persist_news(self, items: Sequence[NewsItem]) -> None:
        now = _now_iso()
        with self._conn:
            for item in items:
                identifier = item.link or f"{item.source}|{item.title}"
                published = item.published_at.isoformat() if item.published_at else None
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO news_items (id, title, summary, url, source, published_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        item.title,
                        item.summary,
                        item.link,
                        item.source,
                        published,
                        now,
                    ),
                )
                self._persist_embedding(identifier, "news", f"{item.title}\n{item.summary}")

    def persist_social(self, posts: Sequence[SocialPost]) -> None:
        now = _now_iso()
        with self._conn:
            for post in posts:
                posted_at = post.posted_at.isoformat() if post.posted_at else None
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO social_posts (id, platform, author, content, url, posted_at, metrics, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post.id,
                        post.platform,
                        post.author,
                        post.content,
                        post.url,
                        posted_at,
                        json.dumps(post.metrics, sort_keys=True),
                        now,
                    ),
                )
                self._persist_embedding(post.id, "social", post.content)

    def persist_github(self, events: Sequence[GitHubEvent]) -> None:
        now = _now_iso()
        with self._conn:
            for event in events:
                event_at = event.event_at.isoformat() if event.event_at else None
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO github_events (id, repo, type, title, url, event_at, metadata, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.repo,
                        event.type,
                        event.title,
                        event.url,
                        event_at,
                        json.dumps(event.metadata, sort_keys=True),
                        now,
                    ),
                )
                summary = f"{event.title} {json.dumps(event.metadata, sort_keys=True)}"
                self._persist_embedding(event.id, "github", summary)

    def persist_tokenomics(self, snapshots: Sequence[TokenomicsSnapshot]) -> None:
        now = _now_iso()
        with self._conn:
            for snapshot in snapshots:
                recorded = snapshot.recorded_at.isoformat() if snapshot.recorded_at else ""
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO tokenomics_metrics (token, metric, value, unit, source, recorded_at, metadata, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.token,
                        snapshot.metric,
                        snapshot.value,
                        snapshot.unit,
                        snapshot.source,
                        recorded,
                        json.dumps(snapshot.metadata, sort_keys=True),
                        now,
                    ),
                )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def _persist_embedding(self, content_id: str, kind: str, text: str) -> None:
        embedding = _bag_of_words_embedding(text)
        if not embedding:
            return
        self._conn.execute(
            """
            INSERT OR REPLACE INTO embeddings (content_id, kind, vector, dimension)
            VALUES (?, ?, ?, ?)
            """,
            (
                content_id,
                kind,
                json.dumps(embedding),
                len(embedding),
            ),
        )


def _bag_of_words_embedding(text: str, *, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    tokens = [token for token in _tokenize(text) if token]
    if not tokens:
        return []
    counts = Counter(tokens)
    total = sum(counts.values())
    vector = [0.0] * dimension
    for token, count in counts.items():
        index = hash(token) % dimension
        vector[index] += count / total
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> Iterable[str]:
    word = []
    for char in text.lower():
        if char.isalnum():
            word.append(char)
        elif word:
            yield "".join(word)
            word.clear()
    if word:
        yield "".join(word)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["IngestionStore", "EMBEDDING_DIMENSION"]
