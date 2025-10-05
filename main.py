"""Executable entry point for running the Hidden Gem scanner demo."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from src.core.pipeline import HiddenGemScanner, TokenConfig, UnlockEvent
from src.core.tree import TreeNode

ARTIFACTS_DIR = Path("artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)


class DemoCoinGeckoClient:
    """Offline stub that returns deterministic market data."""

    def fetch_market_chart(self, token_id: str) -> Dict[str, Iterable[Iterable[float]]]:
        base = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
        prices: List[List[float]] = []
        volumes: List[List[float]] = []
        for i in range(8):
            timestamp = base + dt.timedelta(days=i)
            prices.append([int(timestamp.timestamp() * 1000), 1.0 + 0.05 * i])
            volumes.append([int(timestamp.timestamp() * 1000), 25_000 + 1_000 * i])
        return {"prices": prices, "total_volumes": volumes}


class DemoDefiLlamaClient:
    """Offline stub that produces synthetic protocol metrics."""

    def fetch_protocol(self, slug: str) -> Dict[str, Any]:
        base = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)
        tvl: List[Dict[str, float]] = []
        for i in range(10):
            timestamp = base + dt.timedelta(days=i)
            tvl.append({"date": int(timestamp.timestamp()), "totalLiquidityUSD": 100_000 + 5_000 * i})
        return {
            "tvl": tvl,
            "metrics": {"activeUsers": 950 + 10 * i, "holders": 12_000},
        }


class DemoEtherscanClient:
    """Offline stub that mimics contract metadata."""

    def fetch_contract_source(self, address: str) -> Dict[str, Any]:
        return {
            "IsVerified": "true",
            "ABI": "function mint(address to, uint256 amount) public {}",
            "SourceCode": "contract Token { function withdraw() public {} }",
            "SecuritySeverity": "low",
            "HolderCount": "12500",
        }


def demo_tokens() -> Sequence[TokenConfig]:
    now = dt.datetime.now(dt.timezone.utc)
    return (
        TokenConfig(
            symbol="VBM",
            coingecko_id="voidbloom",
            defillama_slug="voidbloom",
            contract_address="0xVoidBloom",
            narratives=["VoidBloom gears up for cross-chain deployments", "Community launch partners secured"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=21), percent_supply=4.0)],
        ),
        TokenConfig(
            symbol="TOT",
            coingecko_id="tree-of-thought",
            defillama_slug="tree-of-thought",
            contract_address="0xToT",
            narratives=["Iterative reasoning rollout", "Validator set expansion"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=35), percent_supply=6.5)],
        ),
    )


def build_scanner() -> HiddenGemScanner:
    return HiddenGemScanner(
        coin_client=DemoCoinGeckoClient(),
        defi_client=DemoDefiLlamaClient(),
        etherscan_client=DemoEtherscanClient(),
    )


def render_tree(tree: TreeNode) -> str:
    lines: List[str] = []

    def _walk(node: TreeNode, depth: int = 0) -> None:
        outcome = node.outcome.status if node.outcome else "pending"
        lines.append(f"{'  ' * depth}- [{node.key}] {node.title} → {outcome}")
        for child in node.children:
            _walk(child, depth + 1)

    _walk(tree)
    return "\n".join(lines)


def run_demo() -> List[Tuple[TokenConfig, str, TreeNode]]:
    scanner = build_scanner()
    outputs: List[Tuple[TokenConfig, str, TreeNode]] = []
    for token in demo_tokens():
        result, tree = scanner.scan_with_tree(token)
        artifact_path = ARTIFACTS_DIR / f"{token.symbol.lower()}_demo.md"
        artifact_path.write_text(result.artifact_markdown)
        outputs.append((token, result.artifact_markdown, tree))
    return outputs


def main() -> None:
    for token, artifact_markdown, tree in run_demo():
        separator = "=" * 80
        print(separator)
        print(f"Memorywear Artifact for {token.symbol}")
        print(separator)
        print(artifact_markdown)
        print()
        print("Tree-of-Thought execution trace:")
        print(render_tree(tree))
        print()


if __name__ == "__main__":
    main()
