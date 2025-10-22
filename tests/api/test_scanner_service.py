"""Tests for the TokenScannerService scanner wiring logic."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import sys
import types
from pathlib import Path
import importlib

import pytest

# Provide a minimal stub for optional dependencies imported at module load
if "dotenv" not in sys.modules:  # pragma: no cover - guard for test environment
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *_, **__: None
    sys.modules["dotenv"] = dotenv_stub

if "fastapi" not in sys.modules:  # pragma: no cover - guard for test environment
    fastapi_stub = types.ModuleType("fastapi")

    class _FastAPI:  # pylint: disable=too-few-public-methods
        def __init__(self, *_, **__):
            pass

    fastapi_stub.FastAPI = _FastAPI
    fastapi_stub.Request = object
    middleware_module = types.ModuleType("fastapi.middleware")
    cors_module = types.ModuleType("fastapi.middleware.cors")
    cors_module.CORSMiddleware = object
    middleware_module.cors = cors_module
    fastapi_stub.middleware = middleware_module
    sys.modules["fastapi"] = fastapi_stub
    sys.modules["fastapi.middleware"] = middleware_module
    sys.modules["fastapi.middleware.cors"] = cors_module

# Avoid importing heavy FastAPI app wiring during test collection
if "src.api" not in sys.modules:  # pragma: no cover - guard for test environment
    api_module = types.ModuleType("src.api")
    api_module.__path__ = [str(Path(__file__).resolve().parents[2] / "src" / "api")]
    api_module.__package__ = "src"
    sys.modules["src.api"] = api_module

# Provide a lightweight fallback implementation of the pipeline if dependencies are missing
try:  # pragma: no cover - only executed in constrained test environments
    importlib.import_module("src.core.pipeline")
except Exception:  # noqa: BLE001 - broad to handle optional dependency errors
    sys.modules.pop("src.core.pipeline", None)

    pipeline_stub = types.ModuleType("src.core.pipeline")

    class TokenConfig:  # pylint: disable=too-few-public-methods
        def __init__(self, symbol: str, coingecko_id: str, defillama_slug: str, contract_address: str, **kwargs):
            self.symbol = symbol
            self.coingecko_id = coingecko_id
            self.defillama_slug = defillama_slug
            self.contract_address = contract_address
            for key, value in kwargs.items():
                setattr(self, key, value)

    class ScanContext:  # pylint: disable=too-few-public-methods
        def __init__(self, config: TokenConfig):
            self.config = config
            self.result = None

    class HiddenGemScanner:  # pylint: disable=too-many-arguments,too-few-public-methods
        def __init__(
            self,
            *,
            coin_client,
            defi_client=None,
            etherscan_client=None,
            dex_client=None,
            blockscout_client=None,
            rpc_client=None,
            **_,
        ) -> None:
            self.coin_client = coin_client
            self.defi_client = defi_client
            self.etherscan_client = etherscan_client
            self.dex_client = dex_client
            self.blockscout_client = blockscout_client
            self.rpc_client = rpc_client

        def _build_execution_tree(self, context):  # pragma: no cover - overridden in tests
            raise NotImplementedError

    pipeline_stub.HiddenGemScanner = HiddenGemScanner
    pipeline_stub.ScanContext = ScanContext
    pipeline_stub.TokenConfig = TokenConfig

    sys.modules["src.core.pipeline"] = pipeline_stub

from src.api.services.scanner import TokenScannerService
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient
from src.core.pipeline import HiddenGemScanner


class _DummyTree:
    """Simple execution tree stub used to short-circuit network calls."""

    def __init__(self, run_callback):
        self._run_callback = run_callback
        self.key = "root"
        self.title = "dummy"
        self.description = "Stub tree"
        self.children = []

    def run(self, context):
        self._run_callback(context)


@pytest.mark.usefixtures("monkeypatch")
def test_scanner_uses_free_clients_when_no_etherscan_key(monkeypatch):
    """When no Etherscan key is configured we should wire up FREE clients."""

    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)

    service = TokenScannerService()
    scanner = service._ensure_scanner()

    assert scanner.etherscan_client is None
    assert isinstance(scanner.blockscout_client, BlockscoutClient)
    assert isinstance(scanner.dex_client, DexscreenerClient)
    assert isinstance(scanner.rpc_client, EthereumRPCClient)

    def fake_build_execution_tree(self, context):
        # Ensure the scanner instance passed to the tree uses the free clients
        assert self.etherscan_client is None
        assert isinstance(self.blockscout_client, BlockscoutClient)
        assert isinstance(self.dex_client, DexscreenerClient)
        assert isinstance(self.rpc_client, EthereumRPCClient)

        def _run(ctx):
            now = datetime.utcnow()
            ctx.result = SimpleNamespace(
                market_snapshot=SimpleNamespace(
                    symbol=ctx.config.symbol,
                    timestamp=now,
                    price=1.23,
                    volume_24h=1_000.0,
                    liquidity_usd=75_000.0,
                    holders=123,
                    onchain_metrics={},
                    narratives=[],
                ),
                narrative=SimpleNamespace(
                    sentiment_score=0.7,
                    momentum=0.6,
                    themes=[],
                    volatility=0.4,
                    meme_momentum=0.2,
                ),
                safety_report=SimpleNamespace(
                    score=0.8,
                    severity="low",
                    findings=[],
                    flags={},
                ),
                gem_score=SimpleNamespace(
                    score=8_500,
                    confidence=9_200,
                    contributions={},
                ),
                final_score=8_800,
                flag=False,
                news_items=[],
                sentiment_metrics={},
                technical_metrics={},
                security_metrics={},
                raw_features={},
                adjusted_features={},
                artifact_markdown="",
                artifact_html="",
            )

        return _DummyTree(_run)

    monkeypatch.setattr(HiddenGemScanner, "_build_execution_tree", fake_build_execution_tree)

    result = service.scan_token(
        "FOO",
        "foo-token",
        "foo-slug",
        "0x0000000000000000000000000000000000000001",
    )

    assert result is not None
    assert result["symbol"] == "FOO"
    assert result["market_snapshot"]["symbol"] == "FOO"
    assert result["flagged"] is False
    # Ensure the serialized tree reflects our dummy node
    assert result["tree"]["title"] == "dummy"
