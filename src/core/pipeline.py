"""High-level orchestration pipeline for the Hidden-Gem Scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Sequence

import numpy as np
import pandas as pd

from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.features import MarketSnapshot, build_feature_vector, compute_time_series_features
from src.core.narrative import NarrativeAnalyzer, NarrativeInsight
from src.core.safety import SafetyReport, apply_penalties, evaluate_contract, liquidity_guardrail
from src.core.scoring import GemScoreResult, compute_gem_score, should_flag_asset
from src.core.tree import NodeOutcome, TreeNode
from src.services.exporter import render_html_artifact, render_markdown_artifact
from src.services.news import NewsAggregator, NewsItem


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
    artifact_html: str | None = None
    safety_report: SafetyReport | None = None
    liquidity_ok: bool = False
    result: ScanResult | None = None
    news_items: list[NewsItem] = field(default_factory=list)
    sentiment_metrics: Dict[str, float] = field(default_factory=dict)
    technical_metrics: Dict[str, float] = field(default_factory=dict)
    security_metrics: Dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0


class HiddenGemScanner:
    """Coordinates data ingestion, feature building, and scoring."""

    def __init__(
        self,
        *,
        coin_client: CoinGeckoClient,
        defi_client: DefiLlamaClient,
        etherscan_client: EtherscanClient,
        narrative_analyzer: NarrativeAnalyzer | None = None,
        news_aggregator: NewsAggregator | None = None,
        liquidity_threshold: float = 50_000.0,
    ) -> None:
        self.coin_client = coin_client
        self.defi_client = defi_client
        self.etherscan_client = etherscan_client
        self.narrative_analyzer = narrative_analyzer or NarrativeAnalyzer()
        self.news_aggregator = news_aggregator
        self.liquidity_threshold = liquidity_threshold

    def scan(self, config: TokenConfig) -> ScanResult:
        context = ScanContext(config=config)
        tree = self._build_execution_tree(context)
        tree.run(context)
        if context.result is None:
            raise RuntimeError("Scan execution did not produce a result")
        return context.result

    def scan_with_tree(self, config: TokenConfig) -> tuple[ScanResult, TreeNode]:
        context = ScanContext(config=config)
        tree = self._build_execution_tree(context)
        tree.run(context)
        if context.result is None:
            raise RuntimeError("Scan execution did not produce a result")
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
                title="News & Narrative Signals",
                description="Aggregate news feeds for sentiment context",
                action=self._action_fetch_news,
            )
        )
        branch_a.add_child(
            TreeNode(
                key="A5",
                title="Contract Source & Verification",
                description="Fetch Etherscan contract metadata",
                action=self._action_fetch_contract_metadata,
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

        branch_d = root.add_child(
            TreeNode(
                key="D",
                title="Branch D — Safety & Filtering",
                description="Apply liquidity floors and safety penalties before scoring",
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
                key="C3",
                title="GemScore Ensemble",
                description="Compute weighted GemScore with contributions",
                action=self._action_compute_gem_score,
            )
        )
        branch_c.add_child(
            TreeNode(
                key="C4",
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
                key="E3",
                title="Collapse Artifact Export",
                description="Render Collapse Artifact payload and markdown",
                action=self._action_build_artifact,
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
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch price data: {exc}",
                data={"error": str(exc)},
                proceed=False,
            )

    def _action_fetch_onchain_metrics(self, context: ScanContext) -> NodeOutcome:
        try:
            context.protocol_metrics = self.defi_client.fetch_protocol(context.config.defillama_slug)
            points = len((context.protocol_metrics or {}).get("tvl", []) or [])
            return NodeOutcome(
                status="success",
                summary=f"Fetched {points} on-chain points",
                data={"tvl_points": points},
            )
        except Exception as exc:  # pragma: no cover - network failures handled at runtime
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch on-chain metrics: {exc}",
                data={"error": str(exc)},
                proceed=False,
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

    def _action_fetch_contract_metadata(self, context: ScanContext) -> NodeOutcome:
        try:
            context.contract_metadata = self.etherscan_client.fetch_contract_source(context.config.contract_address)
            verified = str((context.contract_metadata or {}).get("IsVerified", "false")).lower() == "true"
            return NodeOutcome(
                status="success",
                summary="Fetched contract metadata",
                data={"verified": verified},
            )
        except Exception as exc:  # pragma: no cover - network failures handled at runtime
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch contract metadata: {exc}",
                data={"error": str(exc)},
                proceed=False,
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
            return NodeOutcome(
                status="failure",
                summary="On-chain metrics missing",
                data={},
                proceed=False,
            )
        context.onchain_metrics = self._derive_onchain_metrics(context.protocol_metrics, context.config.unlocks)
        return NodeOutcome(
            status="success",
            summary="Derived on-chain metrics",
            data=context.onchain_metrics,
        )

    def _action_build_snapshot(self, context: ScanContext) -> NodeOutcome:
        if context.market_chart is None or context.protocol_metrics is None:
            return NodeOutcome(
                status="failure",
                summary="Cannot assemble snapshot without market and on-chain data",
                data={},
                proceed=False,
            )
        context.holders = self._extract_holder_count(context.contract_metadata or {}, context.protocol_metrics)
        combined_narratives = list(context.config.narratives)
        combined_narratives.extend(item.title for item in context.news_items[:3])

        snapshot = MarketSnapshot(
            symbol=context.config.symbol,
            timestamp=context.price_series.index[-1]
            if not context.price_series.empty
            else datetime.now(timezone.utc),
            price=float(context.price_series.iloc[-1]) if not context.price_series.empty else 0.0,
            volume_24h=self._extract_volume(context.market_chart),
            liquidity_usd=context.onchain_metrics.get("current_tvl", 0.0),
            holders=context.holders,
            onchain_metrics=context.onchain_metrics,
            narratives=combined_narratives,
        )
        context.snapshot = snapshot
        return NodeOutcome(
            status="success",
            summary=f"Snapshot at {snapshot.timestamp.isoformat()} with price ${snapshot.price:.4f}",
            data={"liquidity_usd": snapshot.liquidity_usd, "holders": snapshot.holders},
        )

    def _action_narrative_analysis(self, context: ScanContext) -> NodeOutcome:
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

    def _action_contract_metrics(self, context: ScanContext) -> NodeOutcome:
        if context.contract_metadata is None:
            return NodeOutcome(
                status="failure",
                summary="Contract metadata missing",
                data={},
                proceed=False,
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

    def _action_compute_gem_score(self, context: ScanContext) -> NodeOutcome:
        if not context.adjusted_features:
            return NodeOutcome(
                status="failure",
                summary="Adjusted features missing",
                data={},
                proceed=False,
            )
        context.gem_score = compute_gem_score(context.adjusted_features)
        return NodeOutcome(
            status="success",
            summary=f"GemScore {context.gem_score.score:.2f} (confidence {context.gem_score.confidence:.1f})",
            data=context.gem_score.contributions,
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
        if context.gem_score is None or context.snapshot is None or context.narrative is None or context.safety_report is None:
            return NodeOutcome(
                status="failure",
                summary="Missing data to build artifact",
                data={},
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
        )
        return NodeOutcome(
            status="success",
            summary="Artifact rendered",
            data={"hash": payload.get("hash")},
        )

    # ------------------------------------------------------------------
    # Legacy helper methods shared by actions
    # ------------------------------------------------------------------
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
        unlock_pressure = self._compute_unlock_pressure(unlocks)

        return {
            "active_wallets": active_wallets,
            "net_inflows": net_inflows,
            "unlock_pressure": unlock_pressure,
            "tvl_change_pct": tvl_change_pct,
            "current_tvl": current_tvl,
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

    def _compute_unlock_pressure(self, unlocks: Sequence[UnlockEvent]) -> float:
        now = datetime.now(timezone.utc)
        pressure = 0.0
        for unlock in unlocks:
            days = (unlock.date - now).days
            if days < 0:
                continue
            decay = np.exp(-days / 30)
            pressure += unlock.percent_supply * decay
        return float(np.clip(pressure / 100, 0.0, 1.0))

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
            "narratives": narrative.themes,
            "news_items": news_payload,
            "sentiment_metrics": sentiment_metrics,
            "technical_metrics": technical_metrics,
            "security_metrics": security_metrics,
        }
        return payload

    def _artifact_hash(self, config: TokenConfig, snapshot: MarketSnapshot, gem_score: GemScoreResult) -> str:
        data = f"{config.symbol}|{snapshot.timestamp.isoformat()}|{gem_score.score:.2f}|{gem_score.confidence:.2f}"
        return str(abs(hash(data)))

    def _sentiment_label(self, score: float) -> str:
        if score >= 0.65:
            return "positive"
        if score <= 0.35:
            return "negative"
        return "neutral"
