"""Ingestion worker orchestrating multi-source data collection."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import yaml

try:  # pragma: no cover - optional dependency for metrics export
    from prometheus_client import start_http_server
except ImportError:  # pragma: no cover - runtime optional
    start_http_server = None  # type: ignore[assignment]

from src.core.clients import GitHubClient, NewsFeedClient, SocialFeedClient, TokenomicsClient
from src.core.logging_config import init_logging
from src.core.metrics import (
    INGESTION_CYCLE_DURATION_SECONDS,
    INGESTION_CYCLE_ERRORS_TOTAL,
    INGESTION_ITEMS_TOTAL,
    INGESTION_LAST_SUCCESS_TIMESTAMP,
    is_prometheus_available,
)
from src.services.github import GitHubActivityAggregator, RepositorySpec
from src.services.job_queue import PersistentJobQueue
from src.services.news import NewsAggregator
from src.services.social import SocialAggregator, SocialStream
from src.services.storage import IngestionStore
from src.services.tokenomics import TokenSpec, TokenomicsAggregator


DEFAULT_DB_PATH = Path("artifacts/autotrader.db")
DEFAULT_CONFIG_PATH = Path("configs/ingestion.yaml")


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str) -> Optional[float]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class IngestionStats:
    """Counters describing a single ingestion cycle outcome."""

    news_items: int = 0
    social_posts: int = 0
    github_events: int = 0
    token_snapshots: int = 0

    def as_mapping(self) -> Dict[str, int]:
        return {
            "news": self.news_items,
            "social": self.social_posts,
            "github": self.github_events,
            "tokenomics": self.token_snapshots,
        }

    @property
    def total(self) -> int:
        return sum(self.as_mapping().values())


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

    def run_once(self) -> IngestionStats:
        """Collect feeds once and persist into SQLite."""

        stats = IngestionStats()

        if self.news_aggregator and self.config.news_feeds:
            news_items = self.news_aggregator.collect(feeds=self.config.news_feeds)
            stats.news_items = len(news_items)
            if news_items:
                self.store.persist_news(news_items)

        if self.social_aggregator and self.config.social_streams:
            social_posts = self.social_aggregator.collect()
            stats.social_posts = len(social_posts)
            if social_posts:
                self.store.persist_social(social_posts)

        if self.github_aggregator and self.config.github_repos:
            events = self.github_aggregator.collect()
            stats.github_events = len(events)
            if events:
                self.store.persist_github(events)

        if self.tokenomics_aggregator and self.config.token_endpoints:
            snapshots = self.tokenomics_aggregator.collect()
            stats.token_snapshots = len(snapshots)
            if snapshots:
                self.store.persist_tokenomics(snapshots)

        return stats

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


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AutoTrader ingestion worker service")
    parser.add_argument(
        "--config",
        default=os.getenv("INGESTION_CONFIG", str(DEFAULT_CONFIG_PATH)),
        help="Path to ingestion configuration file",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("INGESTION_DB_PATH", str(DEFAULT_DB_PATH)),
        help="SQLite database path for persisted artifacts",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=_env_float("WORKER_POLL_INTERVAL"),
        help="Override poll interval in seconds",
    )
    default_metrics_port = _env_int("WORKER_METRICS_PORT", 9100)
    if _env_flag("WORKER_DISABLE_METRICS", default=False):
        default_metrics_port = 0
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=default_metrics_port,
        help="Port to expose Prometheus metrics (0 to disable)",
    )
    parser.add_argument(
        "--metrics-address",
        default=os.getenv("WORKER_METRICS_ADDRESS", "0.0.0.0"),
        help="Bind address for Prometheus metrics server",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("WORKER_LOG_LEVEL", "INFO"),
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--worker-name",
        default=os.getenv("WORKER_NAME", "autotrader-worker"),
        help="Worker identifier used for logging and metrics labels",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single ingestion cycle and exit",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI helper
    args = _parse_args(argv)
    if _env_flag("WORKER_RUN_ONCE", default=False):
        args.once = True

    config_path = Path(args.config)
    db_path = Path(args.db_path)

    logger = init_logging(service_name=args.worker_name, level=args.log_level).bind(
        worker=args.worker_name,
        pid=os.getpid(),
    )

    if config_path.exists():
        logger.info("worker_config_loaded", path=str(config_path))
    else:
        logger.warning("worker_config_missing", path=str(config_path), action="using_defaults")

    config = load_config(config_path)
    if args.poll_interval is not None and args.poll_interval > 0:
        config.poll_interval = float(args.poll_interval)

    worker = build_worker(config, db_path=db_path)

    metrics_port = args.metrics_port
    metrics_enabled = metrics_port > 0
    if metrics_enabled:
        if start_http_server is None or not is_prometheus_available():
            logger.warning("worker_metrics_disabled", reason="prometheus_client_missing")
            metrics_enabled = False
        else:
            try:
                start_http_server(metrics_port, addr=args.metrics_address)
                logger.info(
                    "worker_metrics_started",
                    port=metrics_port,
                    address=args.metrics_address,
                )
            except Exception as exc:  # pragma: no cover - best-effort logging
                logger.error(
                    "worker_metrics_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                metrics_enabled = False

    stop_event = threading.Event()

    def _signal_handler(signum, _frame):  # pragma: no cover - signal wiring
        logger.info("worker_signal_received", signal=signum)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _signal_handler)
        except Exception:  # pragma: no cover - Windows compatibility
            continue

    logger.info(
        "worker_started",
        poll_interval_seconds=config.poll_interval,
        db_path=str(db_path),
        metrics_enabled=metrics_enabled,
    )

    exit_code = 0
    try:
        while not stop_event.is_set():
            cycle_start = time.perf_counter()
            try:
                stats = worker.run_once()
            except Exception as exc:
                duration = time.perf_counter() - cycle_start
                INGESTION_CYCLE_DURATION_SECONDS.labels(worker=args.worker_name, outcome="error").observe(duration)
                INGESTION_CYCLE_ERRORS_TOTAL.labels(worker=args.worker_name, stage="cycle").inc()
                logger.error(
                    "ingestion_cycle_failed",
                    duration_seconds=round(duration, 3),
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                if args.once:
                    exit_code = 1
                    break
            else:
                duration = time.perf_counter() - cycle_start
                INGESTION_CYCLE_DURATION_SECONDS.labels(worker=args.worker_name, outcome="success").observe(duration)
                INGESTION_LAST_SUCCESS_TIMESTAMP.labels(worker=args.worker_name).set(time.time())
                counts = stats.as_mapping()
                for source, count in counts.items():
                    if count:
                        INGESTION_ITEMS_TOTAL.labels(worker=args.worker_name, source=source).inc(count)
                logger.info(
                    "ingestion_cycle_success",
                    duration_seconds=round(duration, 3),
                    poll_interval_seconds=config.poll_interval,
                    total_items=stats.total,
                    items_news=counts["news"],
                    items_social=counts["social"],
                    items_github=counts["github"],
                    items_tokenomics=counts["tokenomics"],
                )
                if args.once:
                    break

            if args.once:
                break

            sleep_seconds = max(config.poll_interval, 1.0)
            if stop_event.wait(sleep_seconds):
                break

    except KeyboardInterrupt:  # pragma: no cover - graceful shutdown
        logger.info("worker_shutdown_requested", reason="keyboard_interrupt")
    finally:
        worker.close()
        logger.info("worker_stopped")

    return exit_code


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
