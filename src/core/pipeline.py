"""High-level orchestration pipeline for the Hidden-Gem Scanner."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Iterable, Sequence

import numpy as np
import pandas as pd

from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient
from src.core.features import MarketSnapshot, build_feature_vector, compute_time_series_features
from src.core.narrative import NarrativeAnalyzer, NarrativeInsight
from src.core.safety import SafetyReport, apply_penalties, evaluate_contract, liquidity_guardrail
from src.core.scoring import GemScoreResult, compute_gem_score, should_flag_asset
from src.core.tree import NodeOutcome, TreeNode
from src.services.exporter import render_html_artifact, render_markdown_artifact
from src.core.news_client import NewsClient
from src.core.sentiment import SentimentAnalyzer
from src.services.news import NewsItem
from src.core.logging_config import get_logger
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_scan_error,
    record_gem_score,
    record_confidence_score,
    record_flagged_token,
)
from src.core.tracing import trace_operation, add_span_attributes

# Initialize logger for this module
logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from src.services.alerting import AlertManager, Alert
    from src.services.feedback import PrecisionTracker
    from src.services.github import GitHubActivityAggregator, GitHubEvent
    from src.services.social import SocialAggregator, SocialPost
    from src.services.tokenomics import TokenomicsAggregator, TokenomicsSnapshot
    from src.services.news import NewsAggregator
    # Phase 3: Derivatives & On-Chain Flow
    from src.services.onchain_monitor import OnChainAlert
    from src.services.derivatives import DerivativesAggregator
    from src.services.feature_gate import FeatureGate


@dataclass
class UnlockEvent:
    date: datetime
    percent_supply: float


@dataclass
class TokenConfig:
    symbol: str
    coingecko_id: str
    defillama_slug: str
    contract_address: str
    narratives: Sequence[str] = field(default_factory=list)
    glyph: str = "⧗⟡"
    unlocks: Sequence[UnlockEvent] = field(default_factory=list)
    news_feeds: Sequence[str] = field(default_factory=list)
    keywords: Sequence[str] = field(default_factory=list)


@dataclass
class ScanResult:
    token: str
    market_snapshot: MarketSnapshot
    narrative: NarrativeInsight
    raw_features: Dict[str, float]
    adjusted_features: Dict[str, float]
    gem_score: GemScoreResult
    safety_report: SafetyReport
    flag: bool
    debug: Dict[str, float]
    artifact_payload: Dict[str, object]
    artifact_markdown: str
    artifact_html: str
    news_items: Sequence[NewsItem] = field(default_factory=list)
    sentiment_metrics: Dict[str, float] = field(default_factory=dict)
    technical_metrics: Dict[str, float] = field(default_factory=dict)
    security_metrics: Dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0
    github_events: Sequence["GitHubEvent"] = field(default_factory=list)
    social_posts: Sequence["SocialPost"] = field(default_factory=list)
    tokenomics_metrics: Sequence["TokenomicsSnapshot"] = field(default_factory=list)
    alerts: Sequence["Alert"] = field(default_factory=list)
    # Phase 3: Derivatives & On-Chain Flow
    derivatives_data: Dict[str, Any] = field(default_factory=dict)
    onchain_alerts: Sequence["OnChainAlert"] = field(default_factory=list)
    liquidation_spikes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanContext:
    """Mutable context shared across Tree-of-Thought execution."""

    config: TokenConfig
    market_chart: Dict[str, Iterable[Iterable[float]]] | None = None
    protocol_metrics: Dict[str, object] | None = None
    contract_metadata: Dict[str, object] | None = None
    price_series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    price_features: Dict[str, float] = field(default_factory=dict)
    onchain_metrics: Dict[str, float] = field(default_factory=dict)
    holders: int = 0
    snapshot: MarketSnapshot | None = None
    narrative: NarrativeInsight | None = None
    contract_metrics: Dict[str, object] = field(default_factory=dict)
    feature_vector: Dict[str, float] = field(default_factory=dict)
    adjusted_features: Dict[str, float] = field(default_factory=dict)
    gem_score: GemScoreResult | None = None
    flag: bool = False
    debug: Dict[str, float] = field(default_factory=dict)
    artifact_payload: Dict[str, object] = field(default_factory=dict)
    artifact_markdown: str | None = None
    safety_report: SafetyReport | None = None
    liquidity_ok: bool = False
    result: ScanResult | None = None
    artifact_html: str | None = None
    news_items: list[NewsItem] = field(default_factory=list)
    sentiment_metrics: Dict[str, float] = field(default_factory=dict)
    technical_metrics: Dict[str, float] = field(default_factory=dict)
    security_metrics: Dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0
    github_events: list["GitHubEvent"] = field(default_factory=list)
    social_posts: list["SocialPost"] = field(default_factory=list)
    tokenomics_metrics: list["TokenomicsSnapshot"] = field(default_factory=list)
    alerts: list["Alert"] = field(default_factory=list)
    # Phase 3: Derivatives & On-Chain Flow
    derivatives_data: Dict[str, Any] = field(default_factory=dict)
    onchain_alerts: Sequence["OnChainAlert"] = field(default_factory=list)
    liquidation_spikes: Dict[str, Any] = field(default_factory=dict)


class HiddenGemScanner:
    """Coordinates data ingestion, feature building, and scoring."""

    def __init__(
        self,
        *,
        coin_client: CoinGeckoClient,
        defi_client: DefiLlamaClient | None = None,  # Keep for backward compatibility
        etherscan_client: EtherscanClient | None = None,  # Keep for backward compatibility
        dex_client: DexscreenerClient | None = None,  # NEW - FREE Dexscreener
        blockscout_client: BlockscoutClient | None = None,  # NEW - FREE Blockscout
        rpc_client: EthereumRPCClient | None = None,  # NEW - FREE RPC
        narrative_analyzer: NarrativeAnalyzer | None = None,
        liquidity_threshold: float = 50_000.0,
        alert_manager: "AlertManager" | None = None,
        precision_tracker: "PrecisionTracker" | None = None,
        github_aggregator: "GitHubActivityAggregator" | None = None,
        social_aggregator: "SocialAggregator" | None = None,
        tokenomics_aggregator: "TokenomicsAggregator" | None = None,
        news_aggregator: "NewsAggregator" | None = None,
        feature_store: object | None = None,  # Optional FeatureStore for delta explainability
        # Phase 3: Derivatives & On-Chain Flow
        derivatives_aggregator: "DerivativesAggregator" | None = None,
        onchain_monitor: "OnChainMonitor" | None = None,
        feature_gate: "FeatureGate" | None = None,
    ) -> None:
        self.coin_client = coin_client
        # Use FREE clients if provided, otherwise fall back to paid clients
        self.defi_client = defi_client
        self.dex_client = dex_client
        self.etherscan_client = etherscan_client
        self.blockscout_client = blockscout_client
        self.rpc_client = rpc_client
        self.narrative_analyzer = narrative_analyzer or NarrativeAnalyzer()
        self.liquidity_threshold = liquidity_threshold
        self.news_client = NewsClient()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.alert_manager = alert_manager
        self.precision_tracker = precision_tracker
        self.github_aggregator = github_aggregator
        self.social_aggregator = social_aggregator
        self.tokenomics_aggregator = tokenomics_aggregator
        self.news_aggregator = news_aggregator
        self.feature_store = feature_store
        # Phase 3: Derivatives & On-Chain Flow
        self.derivatives_aggregator = derivatives_aggregator
        self.onchain_monitor = onchain_monitor
        self.feature_gate = feature_gate

    def scan(self, config: TokenConfig) -> ScanResult:
        """Scan a token and produce a comprehensive analysis result.
        
        Args:
            config: Token configuration
            
        Returns:
            Scan result with scores, metrics, and artifacts
        """
        start_time = time.time()
        
        # Log scan initiation
        logger.info(
            "scan_started",
            token_symbol=config.symbol,
            token_id=config.coingecko_id,
            contract_address=config.contract_address,
        )
        
        try:
            with trace_operation(
                "scanner.scan",
                attributes={
                    "token.symbol": config.symbol,
                    "token.contract": config.contract_address,
                }
            ):
                context = ScanContext(config=config)
                tree = self._build_execution_tree(context)
                tree.run(context)
                
                if context.result is None:
                    raise RuntimeError("Scan execution did not produce a result")
                
                self._post_process(context)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Record metrics
                record_scan_request(config.symbol, "success")
                record_scan_duration(config.symbol, duration, "success")
                record_gem_score(config.symbol, context.result.gem_score.score)
                record_confidence_score(config.symbol, context.result.gem_score.confidence)
                
                if context.result.flag:
                    record_flagged_token(config.symbol, "security_concern")
                
                # Log completion
                logger.info(
                    "scan_completed",
                    token_symbol=config.symbol,
                    gem_score=context.result.gem_score.score,
                    confidence=context.result.gem_score.confidence,
                    flagged=context.result.flag,
                    duration_seconds=duration,
                )
                
                # Add trace attributes
                add_span_attributes(
                    gem_score=context.result.gem_score.score,
                    confidence=context.result.gem_score.confidence,
                    flagged=context.result.flag,
                )
                
                return context.result
                
        except Exception as e:
            # Calculate duration even on failure
            duration = time.time() - start_time
            
            # Record error metrics
            error_type = type(e).__name__
            record_scan_request(config.symbol, "failure")
            record_scan_duration(config.symbol, duration, "failure")
            record_scan_error(config.symbol, error_type)
            
            # Log error
            logger.error(
                "scan_failed",
                token_symbol=config.symbol,
                error_type=error_type,
                error_message=str(e),
                duration_seconds=duration,
                exc_info=True,
            )
            
            raise

    def scan_with_tree(self, config: TokenConfig) -> tuple[ScanResult, TreeNode]:
        logger.info(f"Starting scan_with_tree for {config.symbol}")
        context = ScanContext(config=config)
        logger.info(f"Building execution tree for {config.symbol}")
        tree = self._build_execution_tree(context)
        logger.info(f"Running tree execution for {config.symbol}")
        tree.run(context)
        logger.info(f"Tree execution completed for {config.symbol}, checking result...")
        if context.result is None:
            logger.error(f"ERROR: context.result is None for {config.symbol} after tree execution")
            raise RuntimeError("Scan execution did not produce a result")
        logger.info(f"Result found for {config.symbol}, running post-process")
        self._post_process(context)
        logger.info(f"Scan completed successfully for {config.symbol}")
        return context.result, tree

    # ------------------------------------------------------------------
    # Tree-of-Thought construction
    # ------------------------------------------------------------------
    def _build_execution_tree(self, context: ScanContext) -> TreeNode:
        root = TreeNode(
            key="root",
            title="Hidden-Gem Scanner",
            description="Root goal: Build a reliable hidden-gem scanner",
            action=lambda ctx: NodeOutcome(
                status="success",
                summary=f"Initiating scan for {ctx.config.symbol}",
                data={"token": ctx.config.symbol},
            ),
        )

        branch_a = root.add_child(
            TreeNode(
                key="A",
                title="Branch A — Data Ingestion",
                description="Collect market, on-chain, and contract intelligence",
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A_decision",
                title="Decision — Ingestion Weighting",
                description="Prioritise price, on-chain, and contract telemetry for the MVP",
                action=self._action_record_ingestion_decision,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A1",
                title="Price + Orderbook",
                description="Fetch CoinGecko market chart data",
                action=self._action_fetch_price_data,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A2",
                title="On-chain Metrics",
                description="Fetch DefiLlama protocol metrics",
                action=self._action_fetch_onchain_metrics,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A3",
                title="Contract Source & Verification",
                description="Fetch Etherscan contract metadata",
                action=self._action_fetch_contract_metadata,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A4",
                title="Wallet Clustering",
                description="Smart-money heuristics staged for enrichment",
                action=self._action_wallet_clustering_deferred,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A5",
                title="News & Narrative Signals",
                description="Aggregate news feeds for sentiment context",
                action=self._action_fetch_news,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A6",
                title="Social & Narrative Streams",
                description="Memetic signal ingestion queued post-MVP",
                action=self._action_social_signal_deferred,
            )
        )
        if self.github_aggregator is not None:
            branch_a.add_child(
                TreeNode(
                    key="A7",
                    title="GitHub Activity",
                    description="Collect repository development signals",
                    action=self._action_fetch_github_activity,
                )
            )
        if self.social_aggregator is not None:
            branch_a.add_child(
                TreeNode(
                    key="A8",
                    title="Social Sentiment",
                    description="Pull high-signal social posts",
                    action=self._action_fetch_social_sentiment,
                )
            )
        if self.tokenomics_aggregator is not None:
            branch_a.add_child(
                TreeNode(
                    key="A9",
                    title="Tokenomics Intelligence",
                    description="Normalize circulating supply & unlock data",
                    action=self._action_fetch_tokenomics,
                )
            )

        # Phase 3: Derivatives and On-chain Flow Analysis
        if self.derivatives_aggregator is not None:
            branch_a.add_child(
                TreeNode(
                    key="A10",
                    title="Derivatives Data",
                    description="Fetch funding rates, open interest, and liquidation data",
                    action=self._action_fetch_derivatives_data,
                )
            )
        if self.onchain_monitor is not None:
            branch_a.add_child(
                TreeNode(
                    key="A11",
                    title="On-chain Flow Analysis",
                    description="Monitor CEX wallet transfers and whale movements",
                    action=self._action_scan_onchain_transfers,
                )
            )

        branch_b = root.add_child(
            TreeNode(
                key="B",
                title="Branch B — Feature Extraction",
                description="Transform raw inputs into hybrid feature vectors",
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B2",
                title="Time-Series Signals",
                description="Build price series and technical indicators",
                action=self._action_build_price_series,
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B3",
                title="On-chain Behaviour",
                description="Derive wallet activity, TVL changes, and unlock pressure",
                action=self._action_compute_onchain_metrics,
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B4",
                title="Market Snapshot",
                description="Assemble current market snapshot including holders and liquidity",
                action=self._action_build_snapshot,
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B1",
                title="Narrative Analyzer",
                description="Embed and score narrative snippets",
                action=self._action_narrative_analysis,
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B5",
                title="Security Features",
                description="Evaluate contract heuristics and compute safety report",
                action=self._action_contract_metrics,
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B6",
                title="Hybrid Feature Vector",
                description="Assemble feature vector and confidence signals",
                action=self._action_build_feature_vector,
            )
        )
        branch_b.add_child(
            TreeNode(
                key="B_decision",
                title="Decision — Hybrid Feature Blend",
                description="Document fusion of numeric, semantic, and risk features",
                action=self._action_feature_strategy_note,
            )
        )

        branch_d = root.add_child(
            TreeNode(
                key="D",
                title="Branch D — Safety & Filtering",
                description="Apply liquidity floors and safety penalties before scoring",
            )
        )
        branch_d.add_child(
            TreeNode(
                key="D1",
                title="Static Code Analysis",
                description="Record contract verification and severity findings",
                action=self._action_record_static_analysis,
            )
        )
        branch_d.add_child(
            TreeNode(
                key="D2",
                title="Dynamic Analysis Placeholder",
                description="Fuzzing and symbolic execution scheduled for follow-up",
                action=self._action_fuzzing_placeholder,
            )
        )
        branch_d.add_child(
            TreeNode(
                key="D4",
                title="Liquidity Guardrail",
                description="Ensure liquidity exceeds configured threshold",
                action=self._action_liquidity_guardrail,
            )
        )
        branch_d.add_child(
            TreeNode(
                key="D3",
                title="Heuristic Penalties",
                description="Apply heuristic penalties based on contract safety and unlocks",
                action=self._action_apply_penalties,
            )
        )
        branch_d.add_child(
            TreeNode(
                key="D3_summary",
                title="Safety Heuristic Summary",
                description="Summarise contract flags feeding the safety gate",
                action=self._action_record_safety_heuristics,
            )
        )
        branch_d.add_child(
            TreeNode(
                key="D1",
                title="Penalty Application",
                description="Apply safety penalties to the feature vector",
                action=self._action_apply_penalties,
            )
        )

        branch_c = root.add_child(
            TreeNode(
                key="C",
                title="Branch C — Analysis & Scoring",
                description="Compute GemScore and multi-signal confirmation",
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C2",
                title="Narrative Momentum",
                description="Record narrative velocity prior to scoring",
                action=self._action_record_narrative_momentum,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C3",
                title="GemScore Ensemble",
                description="Compute weighted GemScore with contributions",
                action=self._action_compute_gem_score,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C4",
                title="Liquidity Depth Model",
                description="Summarise liquidity coverage relative to volume",
                action=self._action_liquidity_model_summary,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C5",
                title="Tokenomics Adjustment",
                description="Highlight tokenomics penalties ahead of GemScore",
                action=self._action_tokenomics_adjustment_summary,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C3",
                title="GemScore Ensemble",
                description="Compute weighted GemScore with contributions",
                action=self._action_compute_gem_score,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C6",
                title="Composite Metric Deck",
                description="Synthesize narrative, technical, and safety metrics",
                action=self._action_compute_composite_metrics,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C1",
                title="Flagging Heuristics",
                description="Evaluate multi-signal confirmation and contract safety gate",
                action=self._action_flag_asset,
            )
        )

        branch_e = root.add_child(
            TreeNode(
                key="E",
                title="Branch E — Output & Action",
                description="Render Collapse Artifacts and operational guidance",
            )
        )
        branch_e.add_child(
            TreeNode(
                key="E1",
                title="Dashboard Surface",
                description="Surface signals via dashboard once API is wired",
                action=self._action_dashboard_placeholder,
            )
        )
        branch_e.add_child(
            TreeNode(
                key="E2",
                title="Alert Streams",
                description="Telegram/Slack notifications staged for rollout",
                action=self._action_alerts_placeholder,
            )
        )
        branch_e.add_child(
            TreeNode(
                key="E3",
                title="Collapse Artifact Export",
                description="Render Collapse Artifact payload and markdown",
                action=self._action_build_artifact,
            )
        )
        branch_e.add_child(
            TreeNode(
                key="E4",
                title="Watchlist Automation",
                description="TradingView and portfolio hooks remain human-triggered",
                action=self._action_watchlist_placeholder,
            )
        )

        return root

    # ------------------------------------------------------------------
    # Tree node actions
    # ------------------------------------------------------------------
    def _action_fetch_price_data(self, context: ScanContext) -> NodeOutcome:
        try:
            context.market_chart = self.coin_client.fetch_market_chart(context.config.coingecko_id)
            points = len((context.market_chart or {}).get("prices", []))
            return NodeOutcome(
                status="success",
                summary=f"Fetched {points} price points",
                data={"price_points": points},
            )
        except Exception as exc:  # pragma: no cover - network failures handled at runtime
            # Allow scan to continue with missing price data - not critical
            logger.warning(f"Could not fetch price data: {exc}", exc_info=True)
            context.price_history = None
            return NodeOutcome(
                status="partial_success",
                summary=f"Could not fetch price data, continuing scan: {exc}",
                data={"error": str(exc)},
                proceed=True,  # Changed: Allow scan to continue
            )

    def _action_fetch_onchain_metrics(self, context: ScanContext) -> NodeOutcome:
        try:
            # Use FREE Dexscreener if available, otherwise fall back to DeFiLlama
            if self.dex_client:
                pairs_data = self.dex_client.fetch_token_pairs(context.config.contract_address)
                pairs = pairs_data.get("pairs", [])
                total_liquidity = sum(p.get("liquidity", {}).get("usd", 0) for p in pairs)
                total_volume = sum(p.get("volume", {}).get("h24", 0) for p in pairs)
                context.protocol_metrics = {
                    "liquidity": total_liquidity,
                    "volume_24h": total_volume,
                    "pairs": pairs,
                    "tvl": [{"totalLiquidityUSD": total_liquidity}],  # Compatibility format
                }
                return NodeOutcome(
                    status="success",
                    summary=f"Fetched {len(pairs)} DEX pairs via Dexscreener (FREE)",
                    data={"pairs": len(pairs), "liquidity": total_liquidity},
                )
            elif self.defi_client:
                context.protocol_metrics = self.defi_client.fetch_protocol(context.config.defillama_slug)
                points = len((context.protocol_metrics or {}).get("tvl", []) or [])
                return NodeOutcome(
                    status="success",
                    summary=f"Fetched {points} on-chain points via DeFiLlama",
                    data={"tvl_points": points},
                )
            else:
                return NodeOutcome(
                    status="failure",
                    summary="No liquidity data client available (need dex_client or defi_client)",
                    data={"error": "missing_client"},
                    proceed=False,
                )
        except Exception as exc:  # pragma: no cover - network failures handled at runtime
            # Allow scan to continue with missing onchain metrics - not critical
            logger.warning(f"Could not fetch on-chain metrics: {exc}", exc_info=True)
            context.protocol_metrics = None
            return NodeOutcome(
                status="partial_success",
                summary=f"Could not fetch on-chain metrics, continuing scan: {exc}",
                data={"error": str(exc)},
                proceed=True,  # Changed: Allow scan to continue
            )

    def _action_fetch_contract_metadata(self, context: ScanContext) -> NodeOutcome:
        try:
            # Use FREE Blockscout if available, otherwise fall back to Etherscan
            if self.blockscout_client:
                context.contract_metadata = self.blockscout_client.fetch_contract_source(context.config.contract_address)
                verified = str((context.contract_metadata or {}).get("is_verified", "false")).lower() == "true"
                return NodeOutcome(
                    status="success",
                    summary="Fetched contract metadata via Blockscout (FREE)",
                    data={"verified": verified},
                )
            elif self.etherscan_client:
                context.contract_metadata = self.etherscan_client.fetch_contract_source(context.config.contract_address)
                verified = str((context.contract_metadata or {}).get("IsVerified", "false")).lower() == "true"
                return NodeOutcome(
                    status="success",
                    summary="Fetched contract metadata via Etherscan",
                    data={"verified": verified},
                )
            else:
                return NodeOutcome(
                    status="failure",
                    summary="No contract verification client available (need blockscout_client or etherscan_client)",
                    data={"error": "missing_client"},
                    proceed=False,
                )
        except Exception as exc:  # pragma: no cover - network failures handled at runtime
            # Allow scan to continue with missing contract metadata - not critical
            logger.warning(f"Could not fetch contract metadata: {exc}", exc_info=True)
            context.contract_metadata = None
            return NodeOutcome(
                status="partial_success",
                summary=f"Could not fetch contract metadata, continuing scan: {exc}",
                data={"error": str(exc)},
                proceed=True,  # Changed: Allow scan to continue
            )

    def _action_record_ingestion_decision(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="success",
            summary="Executing A1/A2/A3/A5 for MVP; wallet + social streams deferred",
            data={"active_streams": ["A1", "A2", "A3", "A5"], "deferred": ["A4", "A6"]},
        )

    def _action_wallet_clustering_deferred(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="skipped",
            summary="Wallet clustering scheduled for enrichment sprint",
            data={"scheduled_sprint": "Sprint 3"},
        )

    def _action_social_signal_deferred(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="skipped",
            summary="Social feeds deferred until noise controls hardened",
            data={"reason": "High noise, rate limits"},
        )

    def _action_feature_strategy_note(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        feature_keys = sorted(context.feature_vector.keys()) if context.feature_vector else []
        return NodeOutcome(
            status="success",
            summary="Hybrid feature blend recorded",
            data={"features": feature_keys},
        )

    def _action_fetch_news(self, context: ScanContext) -> NodeOutcome:
        if self.news_aggregator is None:
            return NodeOutcome(
                status="skipped",
                summary="News aggregator not configured",
                data={},
            )

        feeds = list(context.config.news_feeds)
        keywords = list(context.config.keywords) or [context.config.symbol]
        try:
            items = self.news_aggregator.collect(
                feeds=feeds if feeds else None,
                keywords=keywords,
                limit=20,
            )
        except Exception as exc:  # pragma: no cover - aggregation should not halt pipeline
            return NodeOutcome(
                status="failure",
                summary=f"Failed to aggregate news: {exc}",
                data={"error": str(exc)},
                proceed=True,
            )

        context.news_items = items
        if not items:
            return NodeOutcome(
                status="success",
                summary="No recent matching news",
                data={"articles": 0},
            )

        return NodeOutcome(
            status="success",
            summary=f"Collected {len(items)} news items",
            data={"articles": len(items)},
        )

    def _action_fetch_github_activity(self, context: ScanContext) -> NodeOutcome:
        if self.github_aggregator is None:
            return NodeOutcome(status="skipped", summary="GitHub aggregator disabled", data={}, proceed=True)
        try:
            events = self.github_aggregator.collect(limit=40)
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch GitHub activity: {exc}",
                data={"error": str(exc)},
                proceed=True,
            )
        context.github_events = list(events)
        return NodeOutcome(
            status="success",
            summary=f"Collected {len(context.github_events)} GitHub events",
            data={"events": len(context.github_events)},
        )

    def _action_fetch_social_sentiment(self, context: ScanContext) -> NodeOutcome:
        if self.social_aggregator is None:
            return NodeOutcome(status="skipped", summary="Social aggregator disabled", data={}, proceed=True)
        try:
            posts = self.social_aggregator.collect(limit=40)
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch social sentiment: {exc}",
                data={"error": str(exc)},
                proceed=True,
            )
        context.social_posts = list(posts)
        return NodeOutcome(
            status="success",
            summary=f"Collected {len(context.social_posts)} social posts",
            data={"posts": len(context.social_posts)},
        )

    def _action_fetch_tokenomics(self, context: ScanContext) -> NodeOutcome:
        if self.tokenomics_aggregator is None:
            return NodeOutcome(status="skipped", summary="Tokenomics aggregator disabled", data={}, proceed=True)
        try:
            snapshots = self.tokenomics_aggregator.collect()
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch tokenomics: {exc}",
                data={"error": str(exc)},
                proceed=True,
            )
        context.tokenomics_metrics = list(snapshots)
        return NodeOutcome(
            status="success",
            summary=f"Collected {len(context.tokenomics_metrics)} tokenomics datapoints",
            data={"snapshots": len(context.tokenomics_metrics)},
        )

    def _action_build_price_series(self, context: ScanContext) -> NodeOutcome:
        if context.market_chart is None:
            return NodeOutcome(
                status="failure",
                summary="Market chart data missing",
                data={},
                proceed=False,
            )
        context.price_series = self._build_price_series(context.market_chart)
        context.price_features = compute_time_series_features(context.price_series)
        span = 0.0
        if not context.price_series.empty:
            span = (context.price_series.index[-1] - context.price_series.index[0]).total_seconds() / 3600
        return NodeOutcome(
            status="success",
            summary=f"Built price series spanning {span:.1f} hours",
            data={"series_length": len(context.price_series)},
        )

    def _action_compute_onchain_metrics(self, context: ScanContext) -> NodeOutcome:
        if context.protocol_metrics is None:
            # Create empty onchain_metrics when protocol_metrics is missing
            logger.warning("protocol_metrics is None, creating empty onchain_metrics")
            context.onchain_metrics = {"current_tvl": 0.0, "tvl_trend": 0.0}
            return NodeOutcome(
                status="partial_success",
                summary="Protocol metrics missing, using empty on-chain metrics",
                data=context.onchain_metrics,
            )
        context.onchain_metrics = self._derive_onchain_metrics(context.protocol_metrics, context.config.unlocks)
        return NodeOutcome(
            status="success",
            summary="Derived on-chain metrics",
            data=context.onchain_metrics,
        )

    def _action_build_snapshot(self, context: ScanContext) -> NodeOutcome:
        # Build snapshot with available data - handle missing data gracefully
        if context.market_chart is None:
            logger.warning("market_chart is None, using empty data for snapshot")
        if context.protocol_metrics is None:
            logger.warning("protocol_metrics is None, using empty data for snapshot")
            
        context.holders = self._extract_holder_count(context.contract_metadata or {}, context.protocol_metrics or {})
        combined_narratives = list(context.config.narratives)
        combined_narratives.extend(item.title for item in context.news_items[:3])

        snapshot = MarketSnapshot(
            symbol=context.config.symbol,
            timestamp=context.price_series.index[-1]
            if not context.price_series.empty
            else datetime.now(timezone.utc),
            price=float(context.price_series.iloc[-1]) if not context.price_series.empty else 0.0,
            volume_24h=self._extract_volume(context.market_chart) if context.market_chart else 0.0,
            liquidity_usd=context.onchain_metrics.get("current_tvl", 0.0) if context.onchain_metrics else 0.0,
            holders=context.holders,
            onchain_metrics=context.onchain_metrics if context.onchain_metrics else {},
            narratives=combined_narratives,
        )
        context.snapshot = snapshot
        return NodeOutcome(
            status="success",
            summary=f"Snapshot at {snapshot.timestamp.isoformat()} with price ${snapshot.price:.4f}",
            data={"liquidity_usd": snapshot.liquidity_usd, "holders": snapshot.holders},
        )

    def _action_narrative_analysis(self, context: ScanContext) -> NodeOutcome:
        try:
            context.narrative = self.narrative_analyzer.analyze(context.config.narratives)
            base_narratives = list(context.config.narratives)
            if context.news_items:
                news_texts = [
                    f"{item.source}: {item.title}. {item.summary}"
                    if item.summary
                    else f"{item.source}: {item.title}"
                    for item in context.news_items
                ]
                base_narratives.extend(news_texts)
            context.narrative = self.narrative_analyzer.analyze(base_narratives)
            sentiment_label = self._sentiment_label(context.narrative.sentiment_score)
            return NodeOutcome(
                status="success",
                summary=f"Narrative sentiment {sentiment_label} ({context.narrative.sentiment_score:.2f})",
                data={
                    "sentiment": sentiment_label,
                    "sentiment_score": context.narrative.sentiment_score,
                    "momentum": context.narrative.momentum,
                },
            )
        except Exception as exc:
            # Create default narrative when LLM fails (e.g., rate limits)
            logger.warning(f"Could not perform narrative analysis: {exc}", exc_info=True)
            from src.core.narrative import NarrativeInsight
            context.narrative = NarrativeInsight(
                sentiment_score=0.5,
                momentum=0.5,
                volatility=0.5,
                meme_momentum=0.0,
                themes=["Unable to analyze - LLM unavailable"],
            )
            return NodeOutcome(
                status="partial_success",
                summary=f"Narrative analysis unavailable, using neutral defaults: {exc}",
                data={"sentiment": "neutral", "sentiment_score": 0.5, "error": str(exc)},
            )

    def _action_contract_metrics(self, context: ScanContext) -> NodeOutcome:
        if context.contract_metadata is None:
            # Create default safety report when contract metadata is missing
            logger.warning("contract_metadata is None, creating default safety report")
            context.contract_metrics = {"score": 0.5, "report": self._default_safety_report()}
            context.safety_report = context.contract_metrics["report"]
            return NodeOutcome(
                status="partial_success",
                summary="Contract metadata missing, using default safety score 0.5",
                data={"score": 0.5, "severity": context.safety_report.severity},
            )
        contract_metrics = self._contract_metrics(context.contract_metadata)
        context.contract_metrics = contract_metrics
        context.safety_report = contract_metrics["report"]
        return NodeOutcome(
            status="success",
            summary=f"Contract safety score {contract_metrics['score']:.2f}",
            data={"score": contract_metrics["score"], "severity": context.safety_report.severity},
        )

    def _action_build_feature_vector(self, context: ScanContext) -> NodeOutcome:
        if context.snapshot is None or context.narrative is None:
            return NodeOutcome(
                status="failure",
                summary="Snapshot or narrative missing",
                data={},
                proceed=False,
            )
        contract_score = float((context.contract_metrics or {}).get("score", 0.0))
        feature_vector = build_feature_vector(
            context.snapshot,
            context.price_features,
            narrative_embedding_score=context.narrative.sentiment_score,
            contract_metrics={"score": contract_score},
            narrative_momentum=context.narrative.momentum,
        )
        feature_vector["Recency"] = self._compute_recency(context.snapshot.timestamp)
        feature_vector["DataCompleteness"] = self._compute_data_completeness(feature_vector)
        context.feature_vector = feature_vector
        return NodeOutcome(
            status="success",
            summary="Feature vector assembled",
            data={"features": list(feature_vector.keys())},
        )

    def _action_liquidity_guardrail(self, context: ScanContext) -> NodeOutcome:
        if context.snapshot is None:
            return NodeOutcome(
                status="failure",
                summary="Snapshot required for liquidity check",
                data={},
                proceed=False,
            )
        context.liquidity_ok = liquidity_guardrail(context.snapshot.liquidity_usd, threshold=self.liquidity_threshold)
        status = "success" if context.liquidity_ok else "failure"
        return NodeOutcome(
            status=status,
            summary="Liquidity check passed" if context.liquidity_ok else "Liquidity below threshold",
            data={"liquidity_ok": context.liquidity_ok, "liquidity_usd": context.snapshot.liquidity_usd},
            proceed=True,
        )

    def _action_apply_penalties(self, context: ScanContext) -> NodeOutcome:
        if not context.feature_vector or context.safety_report is None:
            return NodeOutcome(
                status="failure",
                summary="Feature vector or safety report missing",
                data={},
                proceed=False,
            )
        context.adjusted_features = apply_penalties(
            context.feature_vector,
            context.safety_report,
            liquidity_ok=context.liquidity_ok,
        )
        return NodeOutcome(
            status="success",
            summary="Applied safety penalties",
            data={"penalized_keys": [k for k in context.feature_vector if context.adjusted_features.get(k) != context.feature_vector.get(k)]},
        )

    def _action_record_static_analysis(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        if context.safety_report is None:
            return NodeOutcome(
                status="failure",
                summary="Safety report unavailable",
                data={},
                proceed=False,
            )
        return NodeOutcome(
            status="success",
            summary=f"Contract severity {context.safety_report.severity}",
            data={"findings": context.safety_report.findings, "score": context.safety_report.score},
        )

    def _action_fuzzing_placeholder(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="skipped",
            summary="Dynamic analysis queued post-MVP",
            data={"tooling": ["MythX", "echidna"]},
        )

    def _action_record_safety_heuristics(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        if context.safety_report is None:
            return NodeOutcome(
                status="failure",
                summary="No safety heuristics captured",
                data={},
                proceed=False,
            )
        return NodeOutcome(
            status="success",
            summary="Safety heuristics recorded",
            data={"flags": context.safety_report.flags},
        )

    def _action_compute_gem_score(self, context: ScanContext) -> NodeOutcome:
        if not context.adjusted_features:
            return NodeOutcome(
                status="failure",
                summary="Adjusted features missing",
                data={},
                proceed=False,
            )
        context.gem_score = compute_gem_score(context.adjusted_features)
        
        # Store snapshot and compute delta if feature store is available
        if self.feature_store is not None:
            from src.core.score_explainer import create_snapshot_from_result
            
            # Create and store snapshot
            snapshot = create_snapshot_from_result(
                token_symbol=context.config.symbol,
                gem_score_result=context.gem_score,
                features=context.adjusted_features,
                timestamp=context.snapshot.timestamp if context.snapshot else None,
            )
            self.feature_store.write_snapshot(snapshot)
            
            # Compute delta explanation if we have previous history
            delta = self.feature_store.compute_score_delta(
                token_symbol=context.config.symbol,
                current_snapshot=snapshot,
            )
            
            # Log delta if available
            if delta:
                logger.info(
                    "gem_score_delta",
                    token_symbol=context.config.symbol,
                    delta_score=delta.delta_score,
                    percent_change=delta.percent_change,
                    time_delta_hours=delta.time_delta_hours,
                    top_positive=[fd.feature_name for fd in delta.top_positive_contributors[:3]],
                    top_negative=[fd.feature_name for fd in delta.top_negative_contributors[:3]],
                )
        
        return NodeOutcome(
            status="success",
            summary=f"GemScore {context.gem_score.score:.2f} (confidence {context.gem_score.confidence:.1f})",
            data=context.gem_score.contributions,
        )

    def _action_flag_asset(self, context: ScanContext) -> NodeOutcome:
        if context.gem_score is None:
            return NodeOutcome(
                status="failure",
                summary="GemScore missing",
                data={},
                proceed=False,
            )
        context.flag, context.debug = should_flag_asset(context.gem_score, context.adjusted_features)
        return NodeOutcome(
            status="success",
            summary="Flagged for review" if context.flag else "Below flag threshold",
            data=context.debug,
        )

    def _action_record_narrative_momentum(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        if context.narrative is None:
            return NodeOutcome(
                status="failure",
                summary="Narrative insight missing",
                data={},
                proceed=False,
            )
        return NodeOutcome(
            status="success",
            summary=f"Narrative momentum {context.narrative.momentum:.2f}",
            data={"themes": context.narrative.themes},
        )

    def _action_liquidity_model_summary(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        if context.snapshot is None:
            return NodeOutcome(
                status="failure",
                summary="Snapshot required for liquidity model",
                data={},
                proceed=False,
            )
        coverage = 0.0
        if context.snapshot.volume_24h:
            coverage = float(np.clip(context.snapshot.liquidity_usd / max(context.snapshot.volume_24h, 1.0), 0.0, 10.0))
        return NodeOutcome(
            status="success",
            summary="Liquidity coverage captured",
            data={"coverage_ratio": coverage},
        )

    def _action_tokenomics_adjustment_summary(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        if not context.feature_vector or not context.adjusted_features:
            return NodeOutcome(
                status="failure",
                summary="Feature vectors unavailable",
                data={},
                proceed=False,
            )
        penalties = {
            key: round(context.feature_vector.get(key, 0.0) - context.adjusted_features.get(key, 0.0), 4)
            for key in context.feature_vector
            if abs(context.feature_vector.get(key, 0.0) - context.adjusted_features.get(key, 0.0)) > 1e-6
        }
        return NodeOutcome(
            status="success",
            summary="Tokenomics adjustments catalogued",
            data={"penalties": penalties},
        )

    def _action_compute_composite_metrics(self, context: ScanContext) -> NodeOutcome:
        if context.snapshot is None or context.narrative is None or context.safety_report is None:
            return NodeOutcome(
                status="failure",
                summary="Snapshot, narrative, or safety report missing",
                data={},
                proceed=False,
            )

        sentiment_metrics = self._compute_sentiment_metrics(context.narrative)
        technical_metrics = self._compute_technical_metrics(context.price_series)
        security_metrics = self._compute_security_metrics(
            context.safety_report,
            context.snapshot,
            context.contract_metadata or {},
        )
        final_score = self._compute_final_score(sentiment_metrics, technical_metrics, security_metrics)

        context.sentiment_metrics = sentiment_metrics
        context.technical_metrics = technical_metrics
        context.security_metrics = security_metrics
        context.final_score = final_score

        return NodeOutcome(
            status="success",
            summary=f"Composite score {final_score:.2f}",
            data={
                "final_score": final_score,
                "nvi": sentiment_metrics.get("NVI"),
                "aps": technical_metrics.get("APS"),
            },
        )

    def _action_flag_asset(self, context: ScanContext) -> NodeOutcome:
        if context.gem_score is None:
            return NodeOutcome(
                status="failure",
                summary="GemScore missing",
                data={},
                proceed=False,
            )
        context.flag, context.debug = should_flag_asset(context.gem_score, context.adjusted_features)
        return NodeOutcome(
            status="success",
            summary="Flagged for review" if context.flag else "Below flag threshold",
            data=context.debug,
        )

    def _action_build_artifact(self, context: ScanContext) -> NodeOutcome:
        missing_fields = []
        if context.gem_score is None:
            missing_fields.append("gem_score")
        if context.snapshot is None:
            missing_fields.append("snapshot")
        if context.narrative is None:
            missing_fields.append("narrative")
        if context.safety_report is None:
            missing_fields.append("safety_report")
            
        if missing_fields:
            logger.error(
                "artifact_build_failed_missing_data",
                token=context.config.symbol,
                missing_fields=missing_fields,
            )
            return NodeOutcome(
                status="failure",
                summary=f"Missing data to build artifact: {', '.join(missing_fields)}",
                data={"missing_fields": missing_fields},
                proceed=False,
            )
        payload = self._build_artifact_payload(
            context.config,
            context.snapshot,
            context.narrative,
            context.gem_score,
            context.adjusted_features,
            context.safety_report,
            context.liquidity_ok,
            context.debug,
            context.news_items,
            context.sentiment_metrics,
            context.technical_metrics,
            context.security_metrics,
            context.final_score,
        )
        markdown = render_markdown_artifact(payload)
        context.artifact_payload = payload
        context.artifact_markdown = markdown
        if context.github_events:
            payload["github_activity"] = [
                {
                    "id": event.id,
                    "repo": event.repo,
                    "type": event.type,
                    "title": event.title,
                    "url": event.url,
                    "event_at": event.event_at.isoformat() if event.event_at else None,
                }
                for event in context.github_events[:10]
            ]
        if context.social_posts:
            payload["social_posts"] = [
                {
                    "id": post.id,
                    "platform": post.platform,
                    "author": post.author,
                    "content": post.content,
                    "url": post.url,
                    "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                    "metrics": dict(post.metrics),
                }
                for post in context.social_posts[:10]
            ]
        if context.tokenomics_metrics:
            payload["tokenomics_metrics"] = [
                {
                    "token": snapshot.token,
                    "metric": snapshot.metric,
                    "value": snapshot.value,
                    "unit": snapshot.unit,
                    "source": snapshot.source,
                    "recorded_at": snapshot.recorded_at.isoformat() if snapshot.recorded_at else None,
                    "metadata": dict(snapshot.metadata),
                }
                for snapshot in context.tokenomics_metrics[:20]
            ]
        markdown = render_markdown_artifact(payload)
        html = render_html_artifact(payload)
        context.artifact_payload = payload
        context.artifact_markdown = markdown
        context.artifact_html = html
        context.result = ScanResult(
            token=context.config.symbol,
            market_snapshot=context.snapshot,
            narrative=context.narrative,
            raw_features=context.feature_vector,
            adjusted_features=context.adjusted_features,
            gem_score=context.gem_score,
            safety_report=context.safety_report,
            flag=context.flag,
            debug=context.debug,
            artifact_payload=payload,
            artifact_markdown=markdown,
            artifact_html=html,
            news_items=context.news_items,
            sentiment_metrics=context.sentiment_metrics,
            technical_metrics=context.technical_metrics,
            security_metrics=context.security_metrics,
            final_score=context.final_score,
            github_events=context.github_events,
            social_posts=context.social_posts,
            tokenomics_metrics=context.tokenomics_metrics,
            # Phase 3: Derivatives & On-Chain Flow
            derivatives_data=getattr(context, 'derivatives_data', {}),
            onchain_alerts=getattr(context, 'onchain_alerts', []),
            liquidation_spikes=getattr(context, 'liquidation_spikes', {}),
        )
        return NodeOutcome(
            status="success",
            summary="Artifact rendered",
            data={"hash": payload.get("hash")},
        )

    def _action_dashboard_placeholder(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="skipped",
            summary="Dashboard delivery slated once FastAPI endpoints are live",
            data={"frontend": "Next.js"},
        )

    def _action_alerts_placeholder(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="skipped",
            summary="Alert webhooks pending secrets provisioning",
            data={"channels": ["Telegram", "Slack"]},
        )

    def _action_watchlist_placeholder(self, context: ScanContext) -> NodeOutcome:  # noqa: D401 - documentation node
        return NodeOutcome(
            status="skipped",
            summary="Automated watchlist intentionally human-in-the-loop",
            data={"scope": "Monitoring only"},
        )

    # ------------------------------------------------------------------
    # Phase 3: Derivatives and On-chain Flow Actions
    # ------------------------------------------------------------------
    def _action_fetch_derivatives_data(self, context: ScanContext) -> NodeOutcome:
        if self.derivatives_aggregator is None:
            return NodeOutcome(
                status="skipped",
                summary="Derivatives aggregator not configured",
                data={},
                proceed=True,
            )
        try:
            snapshot = self.derivatives_aggregator.generate_snapshot(context.config.symbol)
            context.derivatives_data = snapshot
            context.liquidation_spikes = snapshot.get('liquidation_spikes', {})
            
            total_exchanges = len(snapshot.get('funding_rates', {}))
            total_oi = sum(snapshot.get('open_interest', {}).values())
            
            return NodeOutcome(
                status="success",
                summary=f"Fetched derivatives data from {total_exchanges} exchanges",
                data={
                    "exchanges": total_exchanges,
                    "total_open_interest": total_oi,
                    "liquidation_spikes": len(context.liquidation_spikes),
                },
            )
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch derivatives data: {exc}",
                data={"error": str(exc)},
                proceed=True,  # Non-critical for MVP
            )

    def _action_scan_onchain_transfers(self, context: ScanContext) -> NodeOutcome:
        if self.onchain_monitor is None:
            return NodeOutcome(
                status="skipped",
                summary="On-chain monitor not configured",
                data={},
                proceed=True,
            )
        try:
            alerts = self.onchain_monitor.scan_transfers(context.config.contract_address)
            context.onchain_alerts = alerts
            
            return NodeOutcome(
                status="success",
                summary=f"Scanned on-chain transfers, found {len(alerts)} alerts",
                data={"alerts": len(alerts)},
            )
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to scan on-chain transfers: {exc}",
                data={"error": str(exc)},
                proceed=True,  # Non-critical for MVP
            )

    # ------------------------------------------------------------------
    # Legacy helper methods shared by actions
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Legacy helper methods shared by actions
    # ------------------------------------------------------------------
    def _post_process(self, context: ScanContext) -> None:
        if context.result is None:
            return

        result = context.result
        if self.alert_manager is not None:
            alerts = self.alert_manager.ingest_scan(result)
            if alerts:
                result.alerts = list(alerts)
                if context.artifact_payload is not None:
                    context.artifact_payload["alerts"] = [
                        {
                            "rule": alert.rule,
                            "severity": alert.severity,
                            "message": alert.message,
                            "triggered_at": alert.triggered_at.isoformat(),
                        }
                        for alert in alerts
                    ]
                    result.artifact_payload = context.artifact_payload

        if self.precision_tracker is not None:
            timestamp = context.snapshot.timestamp if context.snapshot else datetime.now(timezone.utc)
            run_id = f"scan:{result.token}:{int(timestamp.timestamp())}"
            self.precision_tracker.log_scan(
                run_id,
                result,
                executed=result.flag,
                timestamp=timestamp,
            )

    def _build_price_series(self, market_chart: Dict[str, Iterable[Iterable[float]]]) -> pd.Series:
        prices = market_chart.get("prices", [])
        if not prices:
            return pd.Series(dtype=float)
        data = {datetime.fromtimestamp(point[0] / 1000, tz=timezone.utc): point[1] for point in prices if len(point) >= 2}
        series = pd.Series(data)
        series.sort_index(inplace=True)
        return series

    def _derive_onchain_metrics(self, protocol_metrics: Dict[str, object], unlocks: Sequence[UnlockEvent]) -> Dict[str, float]:
        tvl_points = protocol_metrics.get("tvl", []) or []
        tvl_values = [float(point.get("totalLiquidityUSD", 0.0)) for point in tvl_points if "totalLiquidityUSD" in point]
        current_tvl = tvl_values[-1] if tvl_values else 0.0
        previous_tvl = tvl_values[-2] if len(tvl_values) >= 2 else current_tvl
        reference_tvl = tvl_values[-8] if len(tvl_values) >= 8 else (tvl_values[0] if tvl_values else 0.0)

        net_inflows = current_tvl - previous_tvl
        tvl_change_pct = (current_tvl - reference_tvl) / reference_tvl if reference_tvl else 0.0

        metrics = protocol_metrics.get("metrics", {}) or {}
        active_wallets = float(metrics.get("activeUsers") or metrics.get("uniqueWallets") or 0.0)
        unlock_pressure, unlock_meta = self._compute_unlock_pressure(unlocks)

        return {
            "active_wallets": active_wallets,
            "net_inflows": net_inflows,
            "unlock_pressure": unlock_pressure,
            "tvl_change_pct": tvl_change_pct,
            "current_tvl": current_tvl,
            **unlock_meta,
        }

    def _extract_holder_count(self, contract_metadata: Dict[str, object], protocol_metrics: Dict[str, object]) -> int:
        holders_raw = contract_metadata.get("HolderCount") or contract_metadata.get("holders")
        if holders_raw is None:
            holders_raw = (protocol_metrics.get("metrics", {}) or {}).get("holders")
        try:
            return int(float(holders_raw))
        except (TypeError, ValueError):
            return 0

    def _extract_volume(self, market_chart: Dict[str, Iterable[Iterable[float]]]) -> float:
        volumes = market_chart.get("total_volumes", [])
        if not volumes:
            return 0.0
        latest = volumes[-1]
        return float(latest[1]) if len(latest) >= 2 else 0.0

    def _default_safety_report(self) -> SafetyReport:
        """Create a default safety report when contract metadata is unavailable."""
        return SafetyReport(
            score=0.5,
            findings=["Contract verification status unknown"],
            severity="unknown",
            flags={"unverified": True},
        )

    def _contract_metrics(self, contract_metadata: Dict[str, object]) -> Dict[str, object]:
        is_verified = str(contract_metadata.get("IsVerified", "false")).lower() == "true"
        abi = str(contract_metadata.get("ABI", "")).lower()
        source = str(contract_metadata.get("SourceCode", "")).lower()
        tags = str(contract_metadata.get("SecurityTag", "")).lower()
        severity = str(contract_metadata.get("SecuritySeverity", contract_metadata.get("severity", "none"))).lower()

        findings = {
            "unverified": not is_verified,
            "owner_can_mint": "function mint" in source or "mint(" in abi,
            "owner_can_withdraw": "withdraw" in source or "withdraw" in abi,
            "honeypot": "honeypot" in tags,
        }
        report = evaluate_contract(findings, severity=severity)
        return {"score": report.score, "report": report}

    def _compute_recency(self, timestamp: datetime) -> float:
        now = datetime.now(timezone.utc)
        delta = now - timestamp
        if delta <= timedelta(hours=24):
            return 1.0
        if delta <= timedelta(days=7):
            return 0.7
        if delta <= timedelta(days=30):
            return 0.4
        return 0.1

    def _compute_data_completeness(self, features: Dict[str, float]) -> float:
        required_keys = ["SentimentScore", "AccumulationScore", "OnchainActivity", "LiquidityDepth", "TokenomicsRisk"]
        available = sum(1 for key in required_keys if key in features)
        return available / len(required_keys)

    def _compute_sentiment_metrics(self, narrative: NarrativeInsight) -> Dict[str, float]:
        return {
            "Sentiment": narrative.sentiment_score,
            "Momentum": narrative.momentum,
            "NVI": narrative.volatility,
            "MMS": narrative.meme_momentum,
        }

    def _compute_technical_metrics(self, price_series: pd.Series | None) -> Dict[str, float]:
        if price_series is None or price_series.empty:
            return {"APS": 0.5, "RSS": 0.5, "RRR": 0.5}

        returns = price_series.pct_change().dropna()
        if returns.empty:
            positive_ratio = 0.5
            cumulative_return = 0.0
            volatility = 0.0
            expected_return = 0.0
        else:
            positive_ratio = float((returns > 0).sum() / len(returns))
            cumulative_return = float((1 + returns).prod() - 1)
            volatility = float(returns.std())
            expected_return = float(returns.mean())

        aps = float(np.clip(positive_ratio, 0.0, 1.0))
        rss = float(np.clip(0.5 + 0.5 * np.tanh(cumulative_return), 0.0, 1.0))
        ratio = expected_return / (volatility + 1e-6)
        rrr = float(np.clip(0.5 + 0.5 * np.tanh(ratio), 0.0, 1.0))

        return {"APS": aps, "RSS": rss, "RRR": rrr}

    def _compute_security_metrics(
        self,
        safety_report: SafetyReport,
        snapshot: MarketSnapshot,
        contract_metadata: Dict[str, object],
    ) -> Dict[str, float]:
        err = float(np.clip(1.0 - safety_report.score, 0.0, 1.0))
        ocw = 1.0 if snapshot.holders >= 1_000 or snapshot.liquidity_usd >= 100_000 else 0.0

        audit_hint = str(
            contract_metadata.get("SecurityAudit")
            or contract_metadata.get("AuditInfo")
            or contract_metadata.get("audit")
            or ""
        ).lower()
        verified = not safety_report.flags.get("unverified", False)
        if audit_hint:
            aci = 0.9 if verified else 0.75
        elif verified:
            aci = 0.6
        else:
            aci = 0.25

        severity = safety_report.severity
        if severity == "high":
            aci = min(aci, 0.2)
        elif severity == "medium":
            aci = min(aci, 0.5)

        return {"ERR": err, "OCW": ocw, "ACI": float(np.clip(aci, 0.0, 1.0))}

    def _compute_final_score(
        self,
        sentiment_metrics: Dict[str, float],
        technical_metrics: Dict[str, float],
        security_metrics: Dict[str, float],
    ) -> float:
        aps = float(np.clip(technical_metrics.get("APS", 0.0), 0.0, 1.0))
        nvi = float(np.clip(sentiment_metrics.get("NVI", 0.0), 0.0, 1.0))
        err = float(np.clip(security_metrics.get("ERR", 1.0), 0.0, 1.0))
        rrr = float(np.clip(technical_metrics.get("RRR", 0.0), 0.0, 1.0))
        return (0.4 * aps + 0.3 * nvi + 0.2 * (1.0 - err) + 0.1 * rrr) * 100

    def _compute_unlock_pressure(self, unlocks: Sequence[UnlockEvent]) -> tuple[float, Dict[str, float]]:
        now = datetime.now(timezone.utc)
        pressure = 0.0
        soonest: UnlockEvent | None = None
        for unlock in unlocks:
            days = (unlock.date - now).days
            if days < 0:
                continue
            if soonest is None or unlock.date < soonest.date:
                soonest = unlock
            decay = np.exp(-days / 30)
            pressure += unlock.percent_supply * decay
        normalized_pressure = float(np.clip(pressure / 100, 0.0, 1.0))
        upcoming_unlock_risk = 0.0
        next_unlock_days = None
        next_unlock_percent = None
        if soonest is not None:
            next_unlock_days = max((soonest.date - now).days, 0)
            next_unlock_percent = float(soonest.percent_supply)
            if next_unlock_percent >= 10.0 and next_unlock_days <= 30:
                upcoming_unlock_risk = 1.0
        return normalized_pressure, {
            "upcoming_unlock_risk": upcoming_unlock_risk,
            "next_unlock_days": next_unlock_days if next_unlock_days is not None else -1,
            "next_unlock_percent": next_unlock_percent if next_unlock_percent is not None else 0.0,
        }

    def _build_artifact_payload(
        self,
        config: TokenConfig,
        snapshot: MarketSnapshot,
        narrative: NarrativeInsight,
        gem_score: GemScoreResult,
        features: Dict[str, float],
        safety_report: SafetyReport,
        liquidity_ok: bool,
        debug: Dict[str, float],
        news_items: Sequence[NewsItem],
        sentiment_metrics: Dict[str, float],
        technical_metrics: Dict[str, float],
        security_metrics: Dict[str, float],
        final_score: float,
    ) -> Dict[str, object]:
        flags = []
        if config.glyph:
            glyph = config.glyph
        else:
            glyph = "⧗⟡"
        if liquidity_ok:
            flags.append("LiquidityFloorPass")
        else:
            flags.append("LowLiquidity")
        if safety_report.findings:
            flags.extend(sorted(safety_report.findings))
        news_payload = [
            {
                "title": item.title,
                "summary": item.summary,
                "link": item.link,
                "source": item.source,
                "published_at": item.published_at.isoformat() if item.published_at else None,
            }
            for item in news_items[:5]
        ]

        payload = {
            "glyph": glyph,
            "title": f"{config.symbol} — Memorywear Entry",
            "timestamp": snapshot.timestamp.isoformat(),
            "gem_score": gem_score.score,
            "confidence": gem_score.confidence,
            "flags": flags,
            "narrative_sentiment": self._sentiment_label(narrative.sentiment_score),
            "narrative_momentum": narrative.momentum,
            "final_score": final_score,
            "flags": flags,
            "narrative_sentiment": self._sentiment_label(narrative.sentiment_score),
            "narrative_momentum": narrative.momentum,
            "nvi": sentiment_metrics.get("NVI", 0.0),
            "meme_momentum": sentiment_metrics.get("MMS", 0.0),
            "price": snapshot.price,
            "volume_24h": snapshot.volume_24h,
            "liquidity": snapshot.liquidity_usd,
            "holders": snapshot.holders,
            "features": features,
            "debug": debug,
            "hash": self._artifact_hash(config, snapshot, gem_score),
            "schema_version": "1.0",
            "source_commit": self._get_source_commit(),
            "feature_set_hash": self._compute_feature_set_hash(features),
            "classification": self._classify_score(gem_score.score),
            "narratives": narrative.themes,
            "upcoming_unlock_risk": features.get("UpcomingUnlockRisk"),
            "next_unlock_days": snapshot.onchain_metrics.get("next_unlock_days"),
            "next_unlock_percent": snapshot.onchain_metrics.get("next_unlock_percent"),
            "news_items": news_payload,
            "sentiment_metrics": sentiment_metrics,
            "technical_metrics": technical_metrics,
            "security_metrics": security_metrics,
        }
        return payload

    def _artifact_hash(self, config: TokenConfig, snapshot: MarketSnapshot, gem_score: GemScoreResult) -> str:
        """Generate artifact hash using cryptographic signature."""
        from src.security.artifact_integrity import get_signer
        
        data = f"{config.symbol}|{snapshot.timestamp.isoformat()}|{gem_score.score:.2f}|{gem_score.confidence:.2f}"
        signer = get_signer()
        return signer.compute_hash(data, algorithm="sha256")[:16]  # First 16 chars for readability
    
    def _get_source_commit(self) -> str:
        """Get current git commit hash for reproducibility."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except Exception:
            pass
        return "unknown"
    
    def _compute_feature_set_hash(self, features: Dict[str, Any]) -> str:
        """Compute hash of feature names and values for provenance."""
        import hashlib
        feature_str = "|".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" 
                               for k, v in sorted(features.items()))
        return hashlib.sha256(feature_str.encode()).hexdigest()[:16]
    
    def _classify_score(self, score: float) -> str:
        """Classify GemScore into categories."""
        if score >= 80:
            return "exceptional"
        elif score >= 70:
            return "strong"
        elif score >= 60:
            return "moderate"
        elif score >= 50:
            return "weak"
        else:
            return "poor"

    def _sentiment_label(self, score: float) -> str:
        if score >= 0.65:
            return "positive"
        if score <= 0.35:
            return "negative"
        return "neutral"
