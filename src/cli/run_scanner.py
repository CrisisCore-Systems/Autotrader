"""Command-line interface to execute the Hidden-Gem Scanner pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.pipeline import HiddenGemScanner, TokenConfig, UnlockEvent
from src.core.narrative import NarrativeAnalyzer


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_unlocks(raw_unlocks: Iterable[dict]) -> list[UnlockEvent]:
    unlocks = []
    for item in raw_unlocks or []:
        date = datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc)
        unlocks.append(UnlockEvent(date=date, percent_supply=float(item["percent_supply"])))
    return unlocks


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
    args = parser.parse_args()

    config = load_config(args.config)
    liquidity_threshold = float(config.get("scanner", {}).get("liquidity_threshold", 50_000))

    with CoinGeckoClient() as coin_client, DefiLlamaClient() as defi_client, EtherscanClient(
        api_key=config.get("etherscan_api_key")
    ) as etherscan_client:
        scanner = HiddenGemScanner(
            coin_client=coin_client,
            defi_client=defi_client,
            etherscan_client=etherscan_client,
            narrative_analyzer=NarrativeAnalyzer(),
            liquidity_threshold=liquidity_threshold,
        )

        for token in config.get("tokens", []):
            token_config = TokenConfig(
                symbol=token["symbol"],
                coingecko_id=token["coingecko_id"],
                defillama_slug=token["defillama_slug"],
                contract_address=token["contract_address"],
                narratives=token.get("narratives", []),
                glyph=token.get("glyph", "⧗⟡"),
                unlocks=build_unlocks(token.get("unlocks", [])),
            )
            if args.tree:
                result, tree = scanner.scan_with_tree(token_config)
            else:
                result = scanner.scan(token_config)
            print(f"=== {token_config.symbol} ===")
            print(f"GemScore: {result.gem_score.score:.2f} (confidence {result.gem_score.confidence:.1f})")
            print(f"Flagged: {'yes' if result.flag else 'no'}")
            print(result.artifact_markdown)
            print()
            if args.tree:
                if args.tree_format == "json":
                    print(json.dumps(tree.to_dict(), indent=2))
                else:
                    for line in _render_tree(tree):
                        print(line)
                print()


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
