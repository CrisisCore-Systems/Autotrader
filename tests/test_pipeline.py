"""Integration-style tests for the Hidden-Gem Scanner pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.pipeline import HiddenGemScanner, TokenConfig, UnlockEvent
from src.core.narrative import NarrativeAnalyzer


class StubCoinGeckoClient:
    def fetch_market_chart(self, token_id: str):  # noqa: D401 - stub
        base = datetime.now(timezone.utc) - timedelta(days=7)
        prices = []
        volumes = []
        for i in range(8):
            timestamp = base + timedelta(days=i)
            prices.append([int(timestamp.timestamp() * 1000), 1.0 + 0.05 * i])
            volumes.append([int(timestamp.timestamp() * 1000), 25000 + 1000 * i])
        return {"prices": prices, "total_volumes": volumes}


class StubDefiLlamaClient:
    def fetch_protocol(self, slug: str):  # noqa: D401 - stub
        base = datetime.now(timezone.utc) - timedelta(days=10)
        tvl = []
        for i in range(10):
            timestamp = base + timedelta(days=i)
            tvl.append({"date": int(timestamp.timestamp()), "totalLiquidityUSD": 100000 + 5000 * i})
        return {
            "tvl": tvl,
            "metrics": {"activeUsers": 950 + 10 * i, "holders": 12000},
        }


class StubEtherscanClient:
    def fetch_contract_source(self, address: str):  # noqa: D401 - stub
        return {
            "IsVerified": "true",
            "ABI": "function mint(address to, uint256 amount) public {}",
            "SourceCode": "contract Token { function withdraw() public {} }",
            "SecuritySeverity": "low",
            "HolderCount": "12500",
        }


def test_hidden_gem_scanner_produces_artifact() -> None:
    scanner = HiddenGemScanner(
        coin_client=StubCoinGeckoClient(),
        defi_client=StubDefiLlamaClient(),
        etherscan_client=StubEtherscanClient(),
        narrative_analyzer=NarrativeAnalyzer(),
        liquidity_threshold=50_000,
    )
    token = TokenConfig(
        symbol="TEST",
        coingecko_id="test-token",
        defillama_slug="test-protocol",
        contract_address="0x123",
        narratives=["Bullish growth narrative", "Mainnet launch sparks integration"],
        unlocks=[
            UnlockEvent(date=datetime.now(timezone.utc) + timedelta(days=14), percent_supply=3.5),
        ],
    )

    result = scanner.scan(token)

    assert result.gem_score.score > 0
    assert result.final_score >= 0
    assert "NVI" in result.sentiment_metrics
    assert "APS" in result.technical_metrics
    assert "ERR" in result.security_metrics
    assert "Memorywear Entry" in result.artifact_markdown
    assert isinstance(result.artifact_payload["flags"], list)
    assert "<!DOCTYPE html>" in result.artifact_html
