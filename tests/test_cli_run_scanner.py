"""Tests for the CLI scanner helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.cli.run_scanner import _artifact_filename, run
from src.core.narrative import NarrativeAnalyzer
from src.services.news import NewsItem


class StubCoinGeckoClient:
    def fetch_market_chart(self, token_id: str):  # noqa: D401 - stub
        base = datetime.now(timezone.utc) - timedelta(days=3)
        prices = []
        volumes = []
        for i in range(4):
            timestamp = base + timedelta(days=i)
            prices.append([int(timestamp.timestamp() * 1000), 1.0 + 0.05 * i])
            volumes.append([int(timestamp.timestamp() * 1000), 15000 + 500 * i])
        return {"prices": prices, "total_volumes": volumes}


class StubDefiLlamaClient:
    def fetch_protocol(self, slug: str):  # noqa: D401 - stub
        base = datetime.now(timezone.utc) - timedelta(days=5)
        tvl = []
        for idx in range(6):
            timestamp = base + timedelta(days=idx)
            tvl.append({"date": int(timestamp.timestamp()), "totalLiquidityUSD": 80_000 + 2_500 * idx})
        return {
            "tvl": tvl,
            "metrics": {"activeUsers": 420 + 5 * (len(tvl) - 1), "holders": 5_000},
        }


class StubEtherscanClient:
    def fetch_contract_source(self, address: str):  # noqa: D401 - stub
        return {
            "IsVerified": "true",
            "ABI": "function mint(address,uint256) public {}",
            "SourceCode": "contract Token { function withdraw() public {} }",
            "SecuritySeverity": "low",
            "HolderCount": "5000",
        }


class StubNewsAggregator:
    def collect(self, *, feeds=None, keywords=None, limit=50):  # noqa: D401 - stub
        return [
            NewsItem(
                title="Token expands",
                summary="Launch momentum continues.",
                link="https://example.com/token",
                source="Feed",
                published_at=datetime.now(timezone.utc),
            )
        ]


def test_run_saves_artifact(tmp_path: Path) -> None:
    config = {
        "scanner": {"liquidity_threshold": 10_000},
        "tokens": [
            {
                "symbol": "My Token",
                "coingecko_id": "my-token",
                "defillama_slug": "my-token",
                "contract_address": "0x123",
                "narratives": [
                    "My Token announces mainnet launch with strong growth",
                    "Partnership momentum stays bullish",
                ],
                "unlocks": [
                    {"date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(), "percent_supply": 5},
                ],
            }
        ],
    }

    analyzer = NarrativeAnalyzer()
    results = run(
        config,
        output_dir=tmp_path,
        coin_client=StubCoinGeckoClient(),
        defi_client=StubDefiLlamaClient(),
        etherscan_client=StubEtherscanClient(),
        narrative_analyzer=analyzer,
        news_aggregator=StubNewsAggregator(),
    )

    assert len(results) == 1
    result = results[0]
    expected_name = _artifact_filename("My Token", result.market_snapshot.timestamp)
    artifact_path = tmp_path / expected_name
    assert artifact_path.exists()
    content = artifact_path.read_text(encoding="utf-8")
    assert "Memorywear Entry" in content
    assert result.news_items
    assert "## News Highlights" in content
