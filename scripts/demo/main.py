"""Executable entry point for running the Hidden Gem scanner demo."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

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
            symbol="ARB",
            coingecko_id="arbitrum",
            defillama_slug="arbitrum",
            contract_address="0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1",
            glyph="⚡🔷",
            narratives=["Arbitrum leads Ethereum L2 scaling race with record TVL", "Major DEX integrations drive Arbitrum ecosystem growth"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=124), percent_supply=2.8)],
        ),
        TokenConfig(
            symbol="OP",
            coingecko_id="optimism",
            defillama_slug="optimism",
            contract_address="0x4200000000000000000000000000000000000042",
            glyph="🔴⚡",
            narratives=["Optimism superchain vision attracts developer mindshare", "OP token utility expansion through governance upgrades"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=159), percent_supply=3.2)],
        ),
        TokenConfig(
            symbol="MATIC",
            coingecko_id="matic-network",
            defillama_slug="polygon",
            contract_address="0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
            glyph="💜🔺",
            narratives=["Polygon 2.0 roadmap introduces zkEVM breakthroughs", "Enterprise adoption accelerates with Disney and Nike partnerships"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=179), percent_supply=1.5)],
        ),
        TokenConfig(
            symbol="LINK",
            coingecko_id="chainlink",
            defillama_slug="chainlink",
            contract_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
            glyph="🔗📡",
            narratives=["Chainlink CCIP expands cross-chain interoperability reach", "Staking v0.2 drives token utility and network security"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=201), percent_supply=2.0)],
        ),
        TokenConfig(
            symbol="UNI",
            coingecko_id="uniswap",
            defillama_slug="uniswap",
            contract_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
            glyph="🦄💱",
            narratives=["Uniswap v4 hooks revolutionize DeFi customization", "Record trading volumes signal strong protocol demand"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=246), percent_supply=1.8)],
        ),
        TokenConfig(
            symbol="AAVE",
            coingecko_id="aave",
            defillama_slug="aave",
            contract_address="0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
            glyph="👻💰",
            narratives=["Aave v3 adoption surges across multiple chains", "GHO stablecoin integration strengthens ecosystem moat"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=285), percent_supply=2.5)],
        ),
        TokenConfig(
            symbol="RNDR",
            coingecko_id="render-token",
            defillama_slug="render-network",
            contract_address="0x6De037ef9aD2725EB40118Bb1702EBb27e4Aeb24",
            glyph="🎨🖥️",
            narratives=["AI boom drives unprecedented demand for decentralized GPU compute", "Hollywood studios pilot Render Network for production workflows"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=324), percent_supply=3.0)],
        ),
        TokenConfig(
            symbol="INJ",
            coingecko_id="injective-protocol",
            defillama_slug="injective",
            contract_address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",
            glyph="💉⚡",
            narratives=["Injective orderbook DEX captures institutional trading flow", "Real-world asset tokenization drives protocol growth"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=349), percent_supply=4.2)],
        ),
        TokenConfig(
            symbol="PENDLE",
            coingecko_id="pendle",
            defillama_slug="pendle",
            contract_address="0x808507121B80c02388fAd14726482e061B8da827",
            glyph="📊💹",
            narratives=["Pendle V2 unlocks yield tokenization for LSTs and LRTs", "EigenLayer integration creates new yield opportunities"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=397), percent_supply=5.0)],
        ),
        TokenConfig(
            symbol="WLD",
            coingecko_id="worldcoin-wld",
            defillama_slug="worldcoin",
            contract_address="0x163f8C2467924be0ae7B5347228CABF260318753",
            glyph="🌍👁️",
            narratives=["Worldcoin orb rollout accelerates global identity verification", "UBI distribution model gains traction in emerging markets"],
            unlocks=[UnlockEvent(date=now + dt.timedelta(days=415), percent_supply=6.0)],
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
        artifact_path.write_text(result.artifact_markdown, encoding='utf-8')
        html_path = ARTIFACTS_DIR / f"{token.symbol.lower()}_demo.html"
        html_path.write_text(result.artifact_html, encoding='utf-8')
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
