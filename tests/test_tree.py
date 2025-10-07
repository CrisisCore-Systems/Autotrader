"""Tests for Tree-of-Thought execution traces."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.pipeline import HiddenGemScanner, TokenConfig, UnlockEvent
from src.core.tree import TreeNode


class StubCoinGeckoClient:
    def fetch_market_chart(self, token_id: str):  # noqa: D401 - stub
        base = datetime.now(timezone.utc) - timedelta(days=3)
        prices = []
        volumes = []
        for i in range(4):
            timestamp = base + timedelta(days=i)
            prices.append([int(timestamp.timestamp() * 1000), 1.0 + 0.1 * i])
            volumes.append([int(timestamp.timestamp() * 1000), 15000 + 500 * i])
        return {"prices": prices, "total_volumes": volumes}


class StubDefiLlamaClient:
    def fetch_protocol(self, slug: str):  # noqa: D401 - stub
        base = datetime.now(timezone.utc) - timedelta(days=6)
        tvl = []
        for i in range(6):
            timestamp = base + timedelta(days=i)
            tvl.append({"date": int(timestamp.timestamp()), "totalLiquidityUSD": 80000 + 2500 * i})
        return {
            "tvl": tvl,
            "metrics": {"activeUsers": 750 + 5 * i, "holders": 9000},
        }


class StubEtherscanClient:
    def fetch_contract_source(self, address: str):  # noqa: D401 - stub
        return {
            "IsVerified": "true",
            "ABI": "function mint(address to, uint256 amount) public {}",
            "SourceCode": "contract Token { function withdraw() public {} }",
            "SecuritySeverity": "low",
            "HolderCount": "9500",
        }


def test_scan_with_tree_emits_trace() -> None:
    scanner = HiddenGemScanner(
        coin_client=StubCoinGeckoClient(),
        defi_client=StubDefiLlamaClient(),
        etherscan_client=StubEtherscanClient(),
        liquidity_threshold=50_000,
    )
    token = TokenConfig(
        symbol="TOT",
        coingecko_id="tot-token",
        defillama_slug="tot-protocol",
        contract_address="0xabc",
        narratives=["Launch partners secured", "DeFi integrations pending"],
        unlocks=[
            UnlockEvent(date=datetime.now(timezone.utc) + timedelta(days=30), percent_supply=5.0),
        ],
    )

    result, tree = scanner.scan_with_tree(token)

    assert isinstance(tree, TreeNode)
    statuses = {node.key: (node.outcome.status if node.outcome else None) for node in tree.iter_nodes()}

    assert statuses["A1"] == "success"
    assert statuses["A3"] == "skipped"
    assert statuses["A4"] == "skipped"
    assert statuses["B6"] == "success"
    assert statuses["C2"] == "success"
    assert statuses["C3"] == "success"
    assert statuses["D2"] == "skipped"
    assert statuses["E1"] == "skipped"
    assert statuses["E3"] == "success"
    assert statuses["E4"] == "skipped"
    assert statuses["B6"] == "success"
    assert statuses["C3"] == "success"
    assert statuses["E3"] == "success"
    assert result.gem_score.score > 0
    assert "Memorywear Entry" in result.artifact_markdown
