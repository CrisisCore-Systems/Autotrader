"""Scanner service coordinating Hidden Gem scans and caching."""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.pipeline import HiddenGemScanner, ScanContext, TokenConfig
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient

from ..utils.tree import serialize_tree_node
from .cache import TokenCache

LOGGER = logging.getLogger(__name__)

DEFAULT_TOKENS: Tuple[Tuple[str, str, str, str], ...] = (
    ("LINK", "chainlink", "chainlink", "0x514910771AF9Ca656af840dff83E8264EcF986CA"),
    ("UNI", "uniswap", "uniswap", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
    ("AAVE", "aave", "aave", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
    ("PEPE", "pepe", "pepe", "0x6982508145454Ce325dDbE47a25d4ec3d2311933"),
)


class TokenScannerService:
    """Coordinates token scans and caches results."""

    def __init__(
        self,
        cache: Optional[TokenCache] = None,
        tokens: Iterable[Tuple[str, str, str, str]] = DEFAULT_TOKENS,
        ttl_seconds: int = 300,
    ) -> None:
        self._cache = cache or TokenCache(ttl_seconds=ttl_seconds)
        self._tokens = tuple(tokens)
        self._scanner: Optional[HiddenGemScanner] = None

    def _ensure_scanner(self) -> HiddenGemScanner:
        # BUGFIX: Create a NEW scanner instance for each scan to avoid state pollution
        # The old singleton pattern was causing all tokens to share the same scan results
        LOGGER.info("Creating fresh HiddenGemScanner instance to avoid state pollution")
        etherscan_key = os.environ.get("ETHERSCAN_API_KEY")
        sanitized_key = etherscan_key.strip() if etherscan_key and etherscan_key.strip() else None

        dex_client = DexscreenerClient()
        blockscout_client = None
        rpc_client = None
        etherscan_client = None

        if sanitized_key:
            LOGGER.info("Using Etherscan client with configured API key")
            etherscan_client = EtherscanClient(api_key=sanitized_key)
        else:
            LOGGER.info("No Etherscan API key detected; using free Blockscout + RPC clients")
            blockscout_client = BlockscoutClient()
            rpc_client = EthereumRPCClient()

        return HiddenGemScanner(
            coin_client=CoinGeckoClient(),
            defi_client=DefiLlamaClient(),
            etherscan_client=etherscan_client,
            dex_client=dex_client,
            blockscout_client=blockscout_client,
            rpc_client=rpc_client,
        )

    def _build_context(self, symbol: str, coingecko_id: str, defillama_slug: str, address: str) -> ScanContext:
        token_cfg = TokenConfig(
            symbol=symbol,
            coingecko_id=coingecko_id,
            defillama_slug=defillama_slug,
            contract_address=address,
            narratives=[f"{symbol} market activity"],
        )
        return ScanContext(config=token_cfg)

    def scan_token(
        self,
        symbol: str,
        coingecko_id: str,
        defillama_slug: str,
        address: str,
    ) -> Optional[Dict[str, object]]:
        """Run full scan workflow and return the detailed response payload."""
        try:
            LOGGER.info("Scanning token %s", symbol)
            scanner = self._ensure_scanner()
            context = self._build_context(symbol, coingecko_id, defillama_slug, address)

            tree = scanner._build_execution_tree(context)  # pylint: disable=protected-access
            tree.run(context)

            if not context.result:
                LOGGER.error("Scan completed but no result object for %s", symbol)
                return None

            result = context.result
            if not result.market_snapshot:
                LOGGER.error("Scan completed but no market snapshot for %s", symbol)
                return None

            snap = result.market_snapshot
            narrative = result.narrative if result.narrative else None
            safety = result.safety_report if result.safety_report else None
            gem_score = result.gem_score if result.gem_score else None

            LOGGER.info("Successfully scanned %s", symbol)
            scanned_at = datetime.utcnow()

            return {
                "symbol": symbol,
                "price": snap.price,
                "liquidity_usd": snap.liquidity_usd,
                "gem_score": (gem_score.score if gem_score else 0.0) / 100.0,
                "final_score": result.final_score / 100.0,
                "confidence": (gem_score.confidence if gem_score else 100.0) / 100.0,
                "flagged": result.flag,
                "narrative_momentum": narrative.momentum if narrative else 0.5,
                "sentiment_score": narrative.sentiment_score if narrative else 0.5,
                "holders": snap.holders if snap.holders else 0,
                "updated_at": scanned_at.isoformat() + "Z",
                "raw_features": result.raw_features if result.raw_features else {},
                "adjusted_features": result.adjusted_features if result.adjusted_features else {},
                "contributions": gem_score.contributions if gem_score and hasattr(gem_score, "contributions") else {},
                "market_snapshot": {
                    "symbol": snap.symbol,
                    "timestamp": snap.timestamp.isoformat() if hasattr(snap.timestamp, "isoformat") else str(snap.timestamp),
                    "price": snap.price,
                    "volume_24h": snap.volume_24h,
                    "liquidity_usd": snap.liquidity_usd,
                    "holders": snap.holders if snap.holders else 0,
                    "onchain_metrics": snap.onchain_metrics if hasattr(snap, "onchain_metrics") else {},
                    "narratives": snap.narratives if hasattr(snap, "narratives") else [],
                },
                "narrative": {
                    "sentiment_score": narrative.sentiment_score if narrative else 0.5,
                    "momentum": narrative.momentum if narrative else 0.5,
                    "themes": narrative.themes if narrative and hasattr(narrative, "themes") else [],
                    "volatility": narrative.volatility if narrative and hasattr(narrative, "volatility") else 0.5,
                    "meme_momentum": narrative.meme_momentum if narrative and hasattr(narrative, "meme_momentum") else 0.0,
                },
                "safety_report": {
                    "score": safety.score if safety else 0.5,
                    "severity": safety.severity if safety else "unknown",
                    "findings": safety.findings if safety and hasattr(safety, "findings") else [],
                    "flags": safety.flags if safety and hasattr(safety, "flags") else {},
                },
                "news_items": result.news_items if result.news_items else [],
                "sentiment_metrics": result.sentiment_metrics if result.sentiment_metrics else {},
                "technical_metrics": result.technical_metrics if result.technical_metrics else {},
                "security_metrics": result.security_metrics if result.security_metrics else {},
                "unlock_events": [],
                "narratives": narrative.themes if narrative and hasattr(narrative, "themes") else [],
                "keywords": [],
                "artifact": {
                    "markdown": result.artifact_markdown if result.artifact_markdown else "",
                    "html": result.artifact_html if result.artifact_html else "",
                },
                "tree": serialize_tree_node(tree),
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.error("Error scanning %s: %s", symbol, exc)
            LOGGER.debug("Traceback: %s", traceback.format_exc())
            raise

    def get_configured_tokens(self) -> Tuple[Tuple[str, str, str, str], ...]:
        """Return configured token tuples (symbol, coingecko_id, defillama_slug, address)."""
        return self._tokens

    def get_token_summaries(self) -> List[Dict[str, object]]:
        """Return token summaries, scanning as needed."""
        summaries: List[Dict[str, object]] = []
        for symbol, cg_id, df_slug, address in self._tokens:
            entry = self._cache.get(symbol)
            if entry:
                LOGGER.info("Returning cached summary for %s", symbol)
                summaries.append(entry["summary"])
                continue

            detail = self.scan_token(symbol, cg_id, df_slug, address)
            if not detail:
                LOGGER.error("Failed to scan %s; skipping from summary response", symbol)
                continue

            entry = self._cache.put(symbol, detail)
            summaries.append(entry["summary"])
        return summaries

    def get_token_detail(self, symbol: str) -> Dict[str, object]:
        """Return detailed token information, scanning if necessary."""
        symbol = symbol.upper()
        token_map = {sym: (cg_id, df_slug, addr) for sym, cg_id, df_slug, addr in self._tokens}
        if symbol not in token_map:
            raise KeyError(symbol)

        entry = self._cache.get(symbol)
        if entry:
            LOGGER.info("Returning cached full result for %s", symbol)
            return entry["detail"]

        cg_id, df_slug, address = token_map[symbol]
        detail = self.scan_token(symbol, cg_id, df_slug, address)
        if not detail:
            raise RuntimeError(f"Scan failed for {symbol} - no result returned")

        entry = self._cache.put(symbol, detail)
        return entry["detail"]


token_scanner_service = TokenScannerService()
