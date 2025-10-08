"""Enhanced API endpoints for dashboard with advanced features."""

from __future__ import annotations

import os
import time
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.services.reliability import get_system_health, SLA_REGISTRY, CIRCUIT_REGISTRY
from src.core.feature_store import FeatureStore
from src.core.pipeline import HiddenGemScanner, TokenConfig, ScanContext
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API keys should be set via environment variables before running
# Example: export GROQ_API_KEY="your-key-here"
# Example: export ETHERSCAN_API_KEY="your-key-here"
# Example: export COINGECKO_API_KEY="your-key-here"
if not os.environ.get('GROQ_API_KEY'):
    logger.warning("GROQ_API_KEY not set in environment variables")
if not os.environ.get('ETHERSCAN_API_KEY'):
    logger.warning("ETHERSCAN_API_KEY not set in environment variables")
if not os.environ.get('COINGECKO_API_KEY'):
    logger.warning("COINGECKO_API_KEY not set in environment variables")


# ============================================================================
# Data Models
# ============================================================================

class TokenResponse(BaseModel):
    """Scanner token summary response."""
    symbol: str
    price: float
    liquidity_usd: float
    gem_score: float
    final_score: float
    confidence: float
    flagged: bool
    narrative_momentum: float
    sentiment_score: float
    holders: int
    updated_at: str


class AnomalyAlert(BaseModel):
    """Anomaly detection alert."""
    alert_id: str
    token_symbol: str
    alert_type: str  # "price_spike", "volume_surge", "liquidity_drain", "sentiment_shift"
    severity: str  # "low", "medium", "high", "critical"
    message: str
    timestamp: float
    metrics: Dict[str, Any]


class ConfidenceInterval(BaseModel):
    """Confidence interval for a metric."""
    value: float
    lower_bound: float
    upper_bound: float
    confidence_level: float  # e.g., 0.95 for 95%


class SLAStatus(BaseModel):
    """SLA status for a data source."""
    source_name: str
    status: str  # "HEALTHY", "DEGRADED", "FAILED"
    latency_p50: Optional[float]
    latency_p95: Optional[float]
    latency_p99: Optional[float]
    success_rate: Optional[float]
    uptime_percentage: Optional[float]


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status."""
    breaker_name: str
    state: str  # "CLOSED", "OPEN", "HALF_OPEN"
    failure_count: int


class TokenCorrelation(BaseModel):
    """Cross-token correlation data."""
    token_a: str
    token_b: str
    correlation: float
    metric: str  # "price", "volume", "sentiment"


class OrderFlowSnapshot(BaseModel):
    """Order flow depth chart data."""
    token_symbol: str
    timestamp: float
    bids: List[tuple[float, float]]  # [(price, volume), ...]
    asks: List[tuple[float, float]]
    bid_depth_usd: float
    ask_depth_usd: float
    imbalance: float


class SentimentTrend(BaseModel):
    """Twitter sentiment trend data."""
    token_symbol: str
    timestamps: List[float]
    sentiment_scores: List[float]
    tweet_volumes: List[int]
    engagement_scores: List[float]


# ============================================================================
# API Initialization
# ============================================================================

app = FastAPI(
    title="VoidBloom Dashboard API",
    description="Enhanced API with anomaly detection, SLA monitoring, and advanced visualizations",
    version="2.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global feature store (in production, this would be shared)
feature_store = FeatureStore()

# Global scanner instance and cache configuration
scanner = None
cached_results: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300


# ============================================================================
# Scanner Helper Functions
# ============================================================================

def _parse_iso_timestamp(value: str) -> datetime:
    """Parse ISO timestamp string."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def _build_summary(detail: Dict[str, Any]) -> Dict[str, Any]:
    """Build token summary from detailed scan result."""
    return {
        "symbol": detail["symbol"],
        "price": detail["price"],
        "liquidity_usd": detail["liquidity_usd"],
        "gem_score": detail["gem_score"],
        "final_score": detail["final_score"],
        "confidence": detail["confidence"],
        "flagged": detail["flagged"],
        "narrative_momentum": detail["narrative_momentum"],
        "sentiment_score": detail["sentiment_score"],
        "holders": detail["holders"],
        "updated_at": detail["updated_at"],
    }


def _cache_token(symbol: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """Cache token scan results."""
    updated_at_iso = detail.get("updated_at")
    timestamp = datetime.utcnow()
    if updated_at_iso:
        timestamp = _parse_iso_timestamp(updated_at_iso)

    summary = _build_summary(detail)
    entry = {
        "detail": detail,
        "summary": summary,
        "timestamp": timestamp,
    }
    cached_results[symbol] = entry
    return entry


def _get_cached(symbol: str) -> Dict[str, Any] | None:
    """Get cached token results if still valid."""
    entry = cached_results.get(symbol)
    if not entry:
        return None

    timestamp = entry.get("timestamp")
    if not timestamp:
        return None

    # Make both datetimes timezone-naive for comparison
    now = datetime.utcnow()
    if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
        # If timestamp is timezone-aware, convert to naive UTC
        timestamp = timestamp.replace(tzinfo=None)
    
    if (now - timestamp).total_seconds() > CACHE_TTL_SECONDS:
        return None

    return entry


def init_scanner():
    """Initialize the hidden gem scanner."""
    global scanner
    if scanner is None:
        scanner = HiddenGemScanner(
            coin_client=CoinGeckoClient(),
            defi_client=DefiLlamaClient(),
            etherscan_client=EtherscanClient(api_key=os.environ['ETHERSCAN_API_KEY']),
        )
    return scanner


def serialize_tree_node(node) -> Dict[str, Any]:
    """Serialize a TreeNode to a dictionary."""
    serialized = {
        "key": node.key,
        "title": node.title,
        "description": node.description,
        "outcome": None,
        "children": []
    }

    if hasattr(node, 'outcome') and node.outcome:
        serialized["outcome"] = {
            "status": node.outcome.status,
            "summary": node.outcome.summary,
            "data": node.outcome.data if hasattr(node.outcome, 'data') else {}
        }

    if hasattr(node, 'children'):
        serialized["children"] = [serialize_tree_node(child) for child in node.children]

    return serialized


def scan_token_full(symbol: str, coingecko_id: str, defillama_slug: str, address: str) -> Dict[str, Any]:
    """Scan a single token and return full detailed results."""
    try:
        logger.info(f"Scanning token {symbol}...")
        s = init_scanner()

        token_cfg = TokenConfig(
            symbol=symbol,
            coingecko_id=coingecko_id,
            defillama_slug=defillama_slug,
            contract_address=address,
            narratives=[f"{symbol} market activity"],
        )

        context = ScanContext(config=token_cfg)
        tree = s._build_execution_tree(context)
        tree.run(context)

        if not context.result or not context.result.market_snapshot:
            logger.error(f"Scan completed but no result for {symbol}")
            return None

        result = context.result
        snap = result.market_snapshot
        narrative = result.narrative if result.narrative else None
        safety = result.safety_report if result.safety_report else None
        gem_score = result.gem_score if result.gem_score else None

        logger.info(f"Successfully scanned {symbol}")

        scanned_at = datetime.utcnow()

        # Build comprehensive response
        return {
            # Summary fields
            "symbol": symbol,
            "price": snap.price,
            "liquidity_usd": snap.liquidity_usd,
            "gem_score": gem_score.score if gem_score else 0.0,
            "final_score": result.final_score,
            "confidence": gem_score.confidence if gem_score else 100.0,
            "flagged": result.flag,
            "narrative_momentum": narrative.momentum if narrative else 0.5,
            "sentiment_score": narrative.sentiment_score if narrative else 0.5,
            "holders": snap.holders if snap.holders else 0,
            "updated_at": scanned_at.isoformat() + "Z",

            # Detailed fields
            "raw_features": result.raw_features if result.raw_features else {},
            "adjusted_features": result.adjusted_features if result.adjusted_features else {},
            "contributions": gem_score.contributions if gem_score and hasattr(gem_score, 'contributions') else {},

            "market_snapshot": {
                "symbol": snap.symbol,
                "timestamp": snap.timestamp.isoformat() if hasattr(snap.timestamp, 'isoformat') else str(snap.timestamp),
                "price": snap.price,
                "volume_24h": snap.volume_24h,
                "liquidity_usd": snap.liquidity_usd,
                "holders": snap.holders if snap.holders else 0,
                "onchain_metrics": snap.onchain_metrics if hasattr(snap, 'onchain_metrics') else {},
                "narratives": snap.narratives if hasattr(snap, 'narratives') else []
            },

            "narrative": {
                "sentiment_score": narrative.sentiment_score if narrative else 0.5,
                "momentum": narrative.momentum if narrative else 0.5,
                "themes": narrative.themes if narrative and hasattr(narrative, 'themes') else [],
                "volatility": narrative.volatility if narrative and hasattr(narrative, 'volatility') else 0.5,
                "meme_momentum": narrative.meme_momentum if narrative and hasattr(narrative, 'meme_momentum') else 0.0
            },

            "safety_report": {
                "score": safety.score if safety else 0.5,
                "severity": safety.severity if safety else "unknown",
                "findings": safety.findings if safety and hasattr(safety, 'findings') else [],
                "flags": safety.flags if safety and hasattr(safety, 'flags') else {}
            },

            "news_items": result.news_items if result.news_items else [],
            "sentiment_metrics": result.sentiment_metrics if result.sentiment_metrics else {},
            "technical_metrics": result.technical_metrics if result.technical_metrics else {},
            "security_metrics": result.security_metrics if result.security_metrics else {},
            "unlock_events": [],
            "narratives": narrative.themes if narrative and hasattr(narrative, 'themes') else [],
            "keywords": [],

            "artifact": {
                "markdown": result.artifact_markdown if result.artifact_markdown else "",
                "html": result.artifact_html if result.artifact_html else ""
            },

            "tree": serialize_tree_node(tree)
        }

    except Exception as e:
        logger.error(f"Error scanning {symbol}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

    return None


# ============================================================================
# Scanner Endpoints (Token Discovery)
# ============================================================================

@app.get("/", tags=["Root"])
def root():
    """Root endpoint."""
    return {"status": "ok", "message": "VoidBloom Unified API is running"}


@app.get("/api/tokens", response_model=List[TokenResponse], tags=["Scanner"])
def get_tokens():
    """Get all scanned tokens with summary information.

    Returns:
        List of token summaries
    """
    tokens = [
        ("LINK", "chainlink", "chainlink", "0x514910771AF9Ca656af840dff83E8264EcF986CA"),
        ("UNI", "uniswap", "uniswap", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
        ("AAVE", "aave", "aave", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
        ("PEPE", "pepe", "pepe", "0x6982508145454Ce325dDbE47a25d4ec3d2311933"),
    ]

    summaries: List[Dict[str, Any]] = []
    for symbol, cg_id, df_slug, addr in tokens:
        entry = _get_cached(symbol)
        if entry:
            logger.info(f"Returning cached summary for {symbol}")
            summaries.append(entry["summary"])
            continue

        detail = scan_token_full(symbol, cg_id, df_slug, addr)
        if not detail:
            logger.error(f"Failed to scan {symbol}; skipping from summary response")
            continue

        entry = _cache_token(symbol, detail)
        summaries.append(entry["summary"])

    return summaries


@app.get("/api/tokens/{symbol}", tags=["Scanner"])
def get_token(symbol: str):
    """Get detailed information for a specific token.

    Args:
        symbol: Token symbol (e.g., LINK, UNI, AAVE, PEPE)

    Returns:
        Detailed token scan results
    """
    symbol = symbol.upper()

    token_map = {
        "LINK": ("chainlink", "chainlink", "0x514910771AF9Ca656af840dff83E8264EcF986CA"),
        "UNI": ("uniswap", "uniswap", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
        "AAVE": ("aave", "aave", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
        "PEPE": ("pepe", "pepe", "0x6982508145454Ce325dDbE47a25d4ec3d2311933"),
    }

    if symbol not in token_map:
        raise HTTPException(status_code=404, detail="Token not found")

    entry = _get_cached(symbol)
    if entry:
        logger.info(f"Returning cached full result for {symbol}")
        return entry["detail"]

    try:
        cg_id, df_slug, addr = token_map[symbol]
        result = scan_token_full(symbol, cg_id, df_slug, addr)

        if not result:
            raise HTTPException(status_code=500, detail=f"Scan failed for {symbol} - no result returned")

        entry = _cache_token(symbol, result)
        return entry["detail"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_token for {symbol}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================

@app.get("/api/anomalies", response_model=List[AnomalyAlert], tags=["Monitoring"])
async def get_anomalies(
    token_symbol: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> List[AnomalyAlert]:
    """Get recent anomaly alerts.

    Args:
        token_symbol: Filter by token (optional)
        severity: Filter by severity (optional)
        limit: Maximum number of alerts

    Returns:
        List of anomaly alerts
    """
    # In production, these would come from an anomaly detection service
    # For now, detect anomalies based on feature thresholds

    alerts = []
    current_time = time.time()

    # Example: Check for price spikes
    tokens = [token_symbol] if token_symbol else ["BTC", "ETH", "LINK"]

    for token in tokens:
        # Check price momentum
        momentum = feature_store.read_feature("price_momentum_1h", token)
        if momentum and abs(momentum.value) > 0.05:  # 5% move
            alerts.append(AnomalyAlert(
                alert_id=f"price_spike_{token}_{int(current_time)}",
                token_symbol=token,
                alert_type="price_spike",
                severity="high" if abs(momentum.value) > 0.10 else "medium",
                message=f"{token} price moved {momentum.value:.2%} in 1 hour",
                timestamp=current_time,
                metrics={"momentum": momentum.value},
            ))

    # Filter by severity if provided
    if severity:
        alerts = [a for a in alerts if a.severity == severity]

    return alerts[:limit]


@app.post("/api/anomalies/{alert_id}/acknowledge", tags=["Monitoring"])
async def acknowledge_anomaly(alert_id: str) -> Dict[str, str]:
    """Acknowledge an anomaly alert.

    Args:
        alert_id: Alert ID to acknowledge

    Returns:
        Success message
    """
    # In production, this would update alert status in database
    return {"status": "acknowledged", "alert_id": alert_id}


# ============================================================================
# Confidence Interval Endpoints
# ============================================================================

@app.get("/api/confidence/gem-score/{token_symbol}", response_model=ConfidenceInterval, tags=["Analytics"])
async def get_gem_score_confidence(token_symbol: str) -> ConfidenceInterval:
    """Get gem score with confidence interval.

    Args:
        token_symbol: Token symbol

    Returns:
        Gem score with confidence bounds
    """
    gem_score = feature_store.read_feature("gem_score", token_symbol)

    if not gem_score:
        raise HTTPException(status_code=404, detail="Gem score not found")

    # Calculate confidence interval based on data quality
    confidence = gem_score.confidence
    value = gem_score.value

    # Wider interval for lower confidence
    margin = (1 - confidence) * value * 0.5

    return ConfidenceInterval(
        value=value,
        lower_bound=max(0, value - margin),
        upper_bound=min(100, value + margin),
        confidence_level=confidence,
    )


@app.get("/api/confidence/liquidity/{token_symbol}", response_model=ConfidenceInterval, tags=["Analytics"])
async def get_liquidity_confidence(token_symbol: str) -> ConfidenceInterval:
    """Get liquidity score with confidence interval.

    Args:
        token_symbol: Token symbol

    Returns:
        Liquidity score with confidence bounds
    """
    liquidity = feature_store.read_feature("liquidity_score", token_symbol)

    if not liquidity:
        raise HTTPException(status_code=404, detail="Liquidity score not found")

    confidence = liquidity.confidence
    value = liquidity.value
    margin = (1 - confidence) * value * 0.3

    return ConfidenceInterval(
        value=value,
        lower_bound=max(0, value - margin),
        upper_bound=min(100, value + margin),
        confidence_level=confidence,
    )


# ============================================================================
# SLA Monitoring Endpoints
# ============================================================================

@app.get("/api/sla/status", response_model=List[SLAStatus], tags=["Monitoring"])
async def get_sla_status() -> List[SLAStatus]:
    """Get SLA status for all data sources.

    Returns:
        List of SLA statuses
    """
    statuses = []

    for source_name, monitor in SLA_REGISTRY.get_all().items():
        metrics = monitor.get_current_metrics()
        status = monitor.get_status()

        statuses.append(SLAStatus(
            source_name=source_name,
            status=status.value,
            latency_p50=metrics.latency_p50_seconds if metrics else None,
            latency_p95=metrics.latency_p95_seconds if metrics else None,
            latency_p99=metrics.latency_p99_seconds if metrics else None,
            success_rate=metrics.success_rate if metrics else None,
            uptime_percentage=metrics.uptime_percentage if metrics else None,
        ))

    return statuses


@app.get("/api/sla/circuit-breakers", response_model=List[CircuitBreakerStatus], tags=["Monitoring"])
async def get_circuit_breaker_status() -> List[CircuitBreakerStatus]:
    """Get circuit breaker status for all services.

    Returns:
        List of circuit breaker statuses
    """
    statuses = []

    for breaker_name, breaker in CIRCUIT_REGISTRY.get_all().items():
        statuses.append(CircuitBreakerStatus(
            breaker_name=breaker_name,
            state=breaker.get_state().value,
            failure_count=breaker._failure_count,
        ))

    return statuses


@app.get("/api/sla/health", tags=["Monitoring"])
async def get_overall_health() -> Dict[str, Any]:
    """Get overall system health.

    Returns:
        System health status
    """
    return get_system_health()


# ============================================================================
# Cross-Token Correlation Endpoints
# ============================================================================

@app.get("/api/correlation/matrix", response_model=List[TokenCorrelation], tags=["Analytics"])
async def get_correlation_matrix(
    metric: str = "price",
    tokens: Optional[List[str]] = None,
) -> List[TokenCorrelation]:
    """Get cross-token correlation matrix.

    Args:
        metric: Metric to correlate ("price", "volume", "sentiment")
        tokens: List of tokens (uses all if not provided)

    Returns:
        List of pairwise correlations
    """
    if tokens is None:
        tokens = ["BTC", "ETH", "LINK", "UNI", "AAVE"]

    feature_name = {
        "price": "price_usd",
        "volume": "volume_24h_usd",
        "sentiment": "sentiment_score",
    }.get(metric, "price_usd")

    correlations = []

    # Get historical data for each token
    token_data = {}
    for token in tokens:
        history = feature_store.read_feature_history(
            feature_name=feature_name,
            token_symbol=token,
            limit=100,
        )
        if history:
            token_data[token] = [fv.value for fv in reversed(history)]

    # Calculate pairwise correlations
    import numpy as np

    for i, token_a in enumerate(tokens):
        for token_b in tokens[i + 1:]:
            if token_a in token_data and token_b in token_data:
                data_a = token_data[token_a]
                data_b = token_data[token_b]

                # Align lengths
                min_len = min(len(data_a), len(data_b))
                if min_len > 1:
                    corr = np.corrcoef(data_a[:min_len], data_b[:min_len])[0, 1]

                    correlations.append(TokenCorrelation(
                        token_a=token_a,
                        token_b=token_b,
                        correlation=float(corr),
                        metric=metric,
                    ))

    return correlations


# ============================================================================
# Order Flow Visualization Endpoints
# ============================================================================

@app.get("/api/orderflow/{token_symbol}", response_model=OrderFlowSnapshot, tags=["Analytics"])
async def get_orderflow_depth(token_symbol: str) -> OrderFlowSnapshot:
    """Get order flow depth chart data.

    Args:
        token_symbol: Token symbol

    Returns:
        Order flow snapshot with bid/ask depth
    """
    # Read order book features
    best_bid = feature_store.read_feature("best_bid_price", token_symbol)
    best_ask = feature_store.read_feature("best_ask_price", token_symbol)
    bid_volume = feature_store.read_feature("total_bid_volume", token_symbol)
    ask_volume = feature_store.read_feature("total_ask_volume", token_symbol)
    imbalance = feature_store.read_feature("orderbook_imbalance", token_symbol)

    if not all([best_bid, best_ask, bid_volume, ask_volume]):
        raise HTTPException(status_code=404, detail="Order book data not found")

    # Generate synthetic depth data (in production, use real order book)
    bids = [(best_bid.value - i * 0.01, bid_volume.value / 10) for i in range(10)]
    asks = [(best_ask.value + i * 0.01, ask_volume.value / 10) for i in range(10)]

    return OrderFlowSnapshot(
        token_symbol=token_symbol,
        timestamp=time.time(),
        bids=bids,
        asks=asks,
        bid_depth_usd=bid_volume.value,
        ask_depth_usd=ask_volume.value,
        imbalance=imbalance.value if imbalance else 0.0,
    )


# ============================================================================
# Twitter Sentiment Endpoints
# ============================================================================

@app.get("/api/sentiment/trend/{token_symbol}", response_model=SentimentTrend, tags=["Analytics"])
async def get_sentiment_trend(token_symbol: str, hours: int = 24) -> SentimentTrend:
    """Get Twitter sentiment trend over time.

    Args:
        token_symbol: Token symbol
        hours: Number of hours to look back

    Returns:
        Sentiment trend data
    """
    end_time = time.time()
    start_time = end_time - (hours * 3600)

    # Get historical sentiment
    history = feature_store.read_feature_history(
        feature_name="sentiment_score",
        token_symbol=token_symbol,
        start_time=start_time,
        end_time=end_time,
        limit=100,
    )

    if not history:
        raise HTTPException(status_code=404, detail="Sentiment data not found")

    # Reverse to chronological order
    history = list(reversed(history))

    # Get tweet volumes (if available)
    tweet_history = feature_store.read_feature_history(
        feature_name="tweet_volume",
        token_symbol=token_symbol,
        start_time=start_time,
        end_time=end_time,
        limit=100,
    )

    tweet_volumes = [int(fv.value) for fv in reversed(tweet_history)] if tweet_history else [0] * len(history)

    # Engagement scores (if available)
    engagement_history = feature_store.read_feature_history(
        feature_name="engagement_to_followers_ratio",
        token_symbol=token_symbol,
        start_time=start_time,
        end_time=end_time,
        limit=100,
    )

    engagement_scores = [fv.value for fv in reversed(engagement_history)] if engagement_history else [0.0] * len(history)

    return SentimentTrend(
        token_symbol=token_symbol,
        timestamps=[fv.timestamp for fv in history],
        sentiment_scores=[fv.value for fv in history],
        tweet_volumes=tweet_volumes[:len(history)],
        engagement_scores=engagement_scores[:len(history)],
    )


# ============================================================================
# Feature Store Endpoints
# ============================================================================

@app.get("/api/features/{token_symbol}", tags=["Feature Store"])
async def get_token_features(token_symbol: str) -> Dict[str, Any]:
    """Get all available features for a token.

    Args:
        token_symbol: Token symbol

    Returns:
        Dictionary of feature values
    """
    features = {}

    # Get all features for this token
    for feature_name in feature_store._schema.keys():
        feature_value = feature_store.read_feature(feature_name, token_symbol)
        if feature_value:
            features[feature_name] = {
                "value": feature_value.value,
                "confidence": feature_value.confidence,
                "timestamp": feature_value.timestamp,
                "source": feature_store._schema[feature_name].source,
            }

    if not features:
        raise HTTPException(status_code=404, detail="No features found for token")

    return features


@app.get("/api/features/schema", tags=["Feature Store"])
async def get_feature_schema() -> List[Dict[str, Any]]:
    """Get feature store schema.

    Returns:
        List of feature metadata
    """
    return [metadata.to_dict() for metadata in feature_store._schema.values()]


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
