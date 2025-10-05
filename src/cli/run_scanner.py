"""Command-line interface to execute the Hidden-Gem Scanner pipeline."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

import yaml

from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient, NewsFeedClient
from src.core.pipeline import HiddenGemScanner, ScanResult, TokenConfig, UnlockEvent
from src.core.narrative import NarrativeAnalyzer
from src.services.exporter import save_artifact
from src.services.news import NewsAggregator


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_unlocks(raw_unlocks: Iterable[dict]) -> list[UnlockEvent]:
    unlocks = []
    for item in raw_unlocks or []:
        date = datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc)
        unlocks.append(UnlockEvent(date=date, percent_supply=float(item["percent_supply"])))
    return unlocks


def _artifact_filename(symbol: str, timestamp: datetime) -> str:
    """Return a filesystem-safe filename for an artifact."""

    safe_symbol = re.sub(r"[^a-z0-9]+", "-", symbol.lower()).strip("-") or "token"
    safe_timestamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{safe_symbol}-{safe_timestamp}.md"


def _ensure_clients(
    *,
    coin_client: CoinGeckoClient | None,
    defi_client: DefiLlamaClient | None,
    etherscan_client: EtherscanClient | None,
    etherscan_api_key: str | None,
) -> Tuple[CoinGeckoClient, DefiLlamaClient, EtherscanClient, List[Callable[[], None]]]:
    """Return concrete clients and cleanup callbacks."""

    cleanups: List[Callable[[], None]] = []

    if coin_client is None:
        coin_client = CoinGeckoClient()
        cleanups.append(coin_client.close)
    if defi_client is None:
        defi_client = DefiLlamaClient()
        cleanups.append(defi_client.close)
    if etherscan_client is None:
        etherscan_client = EtherscanClient(api_key=etherscan_api_key)
        cleanups.append(etherscan_client.close)

    return coin_client, defi_client, etherscan_client, cleanups


def _ensure_news_aggregator(
    *,
    news_aggregator: NewsAggregator | None,
    config: dict,
    cleanups: List[Callable[[], None]],
) -> NewsAggregator | None:
    if news_aggregator is not None:
        return news_aggregator

    default_feeds = config.get("news_feeds") or config.get("news", {}).get("feeds") or []
    token_has_feeds = any(token.get("news_feeds") for token in config.get("tokens", []))
    if not default_feeds and not token_has_feeds:
        return None

    news_client = NewsFeedClient()
    cleanups.append(news_client.close)
    return NewsAggregator(news_client, default_feeds=list(default_feeds))


def run(
    config: dict,
    *,
    tree: bool = False,
    tree_format: str = "pretty",
    output_dir: Path | None = None,
    coin_client: CoinGeckoClient | None = None,
    defi_client: DefiLlamaClient | None = None,
    etherscan_client: EtherscanClient | None = None,
    narrative_analyzer: NarrativeAnalyzer | None = None,
    news_aggregator: NewsAggregator | None = None,
) -> list[ScanResult]:
    """Execute the scanner for ``config`` and optionally persist artifacts."""

    liquidity_threshold = float(config.get("scanner", {}).get("liquidity_threshold", 50_000))
    coin_client, defi_client, etherscan_client, cleanups = _ensure_clients(
        coin_client=coin_client,
        defi_client=defi_client,
        etherscan_client=etherscan_client,
        etherscan_api_key=config.get("etherscan_api_key"),
    )
    news_aggregator = _ensure_news_aggregator(
        news_aggregator=news_aggregator,
        config=config,
        cleanups=cleanups,
    )

    analyzer = narrative_analyzer or NarrativeAnalyzer()
    scanner = HiddenGemScanner(
        coin_client=coin_client,
        defi_client=defi_client,
        etherscan_client=etherscan_client,
        narrative_analyzer=analyzer,
        news_aggregator=news_aggregator,
        liquidity_threshold=liquidity_threshold,
    )

    results: list[ScanResult] = []

    try:
        for token in config.get("tokens", []):
            token_config = TokenConfig(
                symbol=token["symbol"],
                coingecko_id=token["coingecko_id"],
                defillama_slug=token["defillama_slug"],
                contract_address=token["contract_address"],
                narratives=token.get("narratives", []),
                glyph=token.get("glyph", "⧗⟡"),
                unlocks=build_unlocks(token.get("unlocks", [])),
                news_feeds=token.get("news_feeds", []),
                keywords=token.get("keywords") or [token["symbol"]],
            )
            if tree:
                result, tree_obj = scanner.scan_with_tree(token_config)
            else:
                result = scanner.scan(token_config)
                tree_obj = None

            print(f"=== {token_config.symbol} ===")
            print(
                f"GemScore: {result.gem_score.score:.2f} (confidence {result.gem_score.confidence:.1f})"
            )
            print(f"Flagged: {'yes' if result.flag else 'no'}")
            print(result.artifact_markdown)
            print()

            if output_dir is not None:
                filename = _artifact_filename(token_config.symbol, result.market_snapshot.timestamp)
                path = save_artifact(result.artifact_markdown, output_dir, filename)
                html_name = filename[:-3] + ".html" if filename.endswith(".md") else f"{filename}.html"
                html_path = save_artifact(result.artifact_html, output_dir, html_name)
                print(f"Saved artifact to {path}")
                print(f"Saved HTML artifact to {html_path}")
                print()

            if tree and tree_obj is not None:
                if tree_format == "json":
                    print(json.dumps(tree_obj.to_dict(), indent=2))
                else:
                    for line in _render_tree(tree_obj):
                        print(line)
                print()

            results.append(result)
    finally:
        for cleanup in cleanups:
            cleanup()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the VoidBloom Hidden-Gem Scanner")
    parser.add_argument("config", type=Path, help="Path to YAML configuration file")
    parser.add_argument(
        "--tree",
        action="store_true",
        help="Emit the Tree-of-Thought execution trace for each token",
    )
    parser.add_argument(
        "--tree-format",
        choices=["pretty", "json"],
        default="pretty",
        help="Rendering format for the Tree-of-Thought trace",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to persist rendered artifacts",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    run(
        config,
        tree=args.tree,
        tree_format=args.tree_format,
        output_dir=args.output_dir,
    )


def _render_tree(node, indent: int = 0) -> list[str]:
    from src.core.tree import TreeNode  # Local import to avoid CLI import cycle

    assert isinstance(node, TreeNode)
    prefix = "  " * indent
    status = node.outcome.status if node.outcome else "pending"
    summary = node.outcome.summary if node.outcome else ""
    lines = [f"{prefix}- [{status}] {node.title}: {summary}"]
    for child in node.children:
        lines.extend(_render_tree(child, indent + 1))
    return lines


if __name__ == "__main__":
    main()
