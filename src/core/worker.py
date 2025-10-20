"""Ingestion worker orchestrating multi-source data collection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from src.core.clients import GitHubClient, NewsFeedClient, SocialFeedClient, TokenomicsClient
from src.services.github import GitHubActivityAggregator, RepositorySpec
from src.services.job_queue import PersistentJobQueue
from src.services.news import NewsAggregator
from src.services.social import SocialAggregator, SocialStream
from src.services.storage import IngestionStore
from src.services.tokenomics import TokenSpec, TokenomicsAggregator


DEFAULT_DB_PATH = Path("artifacts/autotrader.db")
DEFAULT_CONFIG_PATH = Path("configs/ingestion.yaml")


@dataclass
class WorkerConfig:
    """Runtime configuration for the ingestion worker."""

    poll_interval: float = 900.0
    news_feeds: Sequence[str] = field(default_factory=list)
    social_streams: Sequence[SocialStream] = field(default_factory=list)
    github_repos: Sequence[RepositorySpec] = field(default_factory=list)
    token_endpoints: Sequence[TokenSpec] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "WorkerConfig":
        poll_interval = float(mapping.get("poll_interval", 900.0))

        news_feeds = [
            str(feed)
            for feed in mapping.get("news_feeds", [])
            if isinstance(feed, str) and feed.strip()
        ]

        social_streams: list[SocialStream] = []
        for item in mapping.get("social_feeds", []) or []:
            if not isinstance(item, Mapping):
                continue
            url = str(item.get("url") or "").strip()
            platform = str(item.get("platform") or "").strip() or "social"
            if not url:
                continue
            social_streams.append(SocialStream(url=url, platform=platform, label=str(item.get("label") or "")))

        github_repos: list[RepositorySpec] = []
        for repo in mapping.get("github_repos", []) or []:
            if isinstance(repo, str):
                try:
                    github_repos.append(RepositorySpec.from_string(repo))
                except ValueError:
                    continue

        token_endpoints: list[TokenSpec] = []
        for entry in mapping.get("tokenomics", []) or []:
            if isinstance(entry, Mapping):
                url = str(entry.get("url") or "").strip()
                symbol = str(entry.get("symbol") or "").strip()
                if not url or not symbol:
                    continue
                source = str(entry.get("source") or "") or None
                token_endpoints.append(TokenSpec(symbol=symbol, url=url, source=source))

        return cls(
            poll_interval=poll_interval,
            news_feeds=news_feeds,
            social_streams=social_streams,
            github_repos=github_repos,
            token_endpoints=token_endpoints,
        )


class IngestionWorker:
    """Coordinates data collection and persistence across feeds."""

    def __init__(
        self,
        *,
        store: IngestionStore,
        config: WorkerConfig,
        news_aggregator: NewsAggregator | None = None,
        social_aggregator: SocialAggregator | None = None,
        github_aggregator: GitHubActivityAggregator | None = None,
        tokenomics_aggregator: TokenomicsAggregator | None = None,
        job_queue: PersistentJobQueue | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.news_aggregator = news_aggregator
        self.social_aggregator = social_aggregator
        self.github_aggregator = github_aggregator
        self.tokenomics_aggregator = tokenomics_aggregator
        self.job_queue = job_queue

    def run_once(self) -> None:
        """Collect feeds once and persist into SQLite."""

        if self.news_aggregator and self.config.news_feeds:
            news_items = self.news_aggregator.collect(feeds=self.config.news_feeds)
            self.store.persist_news(news_items)

        if self.social_aggregator and self.config.social_streams:
            social_posts = self.social_aggregator.collect()
            self.store.persist_social(social_posts)

        if self.github_aggregator and self.config.github_repos:
            events = self.github_aggregator.collect()
            self.store.persist_github(events)

        if self.tokenomics_aggregator and self.config.token_endpoints:
            snapshots = self.tokenomics_aggregator.collect()
            self.store.persist_tokenomics(snapshots)

    def run_forever(self) -> None:  # pragma: no cover - long running loop
        while True:
            self.run_once()
            time.sleep(self.config.poll_interval)

    def close(self) -> None:
        if self.job_queue:
            self.job_queue.close()
        self.store.close()


def load_config(path: Path | None = None) -> WorkerConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text()) or {}
        if isinstance(data, Mapping):
            return WorkerConfig.from_mapping(data)
    return WorkerConfig()


def build_worker(config: WorkerConfig, *, db_path: Path = DEFAULT_DB_PATH) -> IngestionWorker:
    store = IngestionStore(db_path)

    job_queue = PersistentJobQueue(db_path.with_suffix(".jobs"))

    news_client = NewsFeedClient()
    social_client = SocialFeedClient()
    github_client = GitHubClient()
    tokenomics_client = TokenomicsClient()

    news_aggregator = NewsAggregator(
        news_client,
        default_feeds=config.news_feeds,
        job_queue=job_queue,
    )
    social_aggregator = SocialAggregator(
        social_client,
        streams=config.social_streams,
        job_queue=job_queue,
    )
    github_aggregator = GitHubActivityAggregator(
        github_client,
        repositories=config.github_repos,
        job_queue=job_queue,
    )
    tokenomics_aggregator = TokenomicsAggregator(
        tokenomics_client,
        tokens=config.token_endpoints,
        job_queue=job_queue,
    )

    return IngestionWorker(
        store=store,
        config=config,
        news_aggregator=news_aggregator,
        social_aggregator=social_aggregator,
        github_aggregator=github_aggregator,
        tokenomics_aggregator=tokenomics_aggregator,
        job_queue=job_queue,
    )


def main() -> None:  # pragma: no cover - CLI helper
    config = load_config()
    worker = build_worker(config)
    try:
        worker.run_forever()
    finally:
        worker.close()


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
