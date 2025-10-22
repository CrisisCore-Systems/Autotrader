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
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal

from src.services.reliability import get_system_health, SLA_REGISTRY, CIRCUIT_REGISTRY
from src.core.feature_store import FeatureStore
from src.core.pipeline import HiddenGemScanner, TokenConfig, ScanContext
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.freshness import get_freshness_tracker
from src.core.provenance import get_provenance_tracker

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

class DataSourceInfo(BaseModel):
    """Information about a data source with freshness."""
    source_name: str = Field(..., description="Name of data source")
    last_updated: str = Field(..., description="ISO timestamp of last update")
    data_age_seconds: float = Field(..., description="Age of data in seconds")
    freshness_level: str = Field(..., description="Freshness classification")
    is_free: bool = Field(default=True, description="Whether this is a FREE data source")
    
    
class ProvenanceInfo(BaseModel):
    """Provenance information for token data."""
    artifact_id: Optional[str] = Field(None, description="Unique artifact identifier")
    data_sources: List[str] = Field(default_factory=list, description="List of data sources used")
    pipeline_version: Optional[str] = Field(None, description="Pipeline version")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class TokenResponse(BaseModel):
    """Scanner token summary response."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Token symbol")
    price: float = Field(..., gt=0, description="Token price in USD")
    liquidity_usd: float = Field(..., ge=0, description="Liquidity in USD")
    gem_score: float = Field(..., ge=0, le=1, description="Gem score between 0 and 1")
    final_score: float = Field(..., ge=0, le=1, description="Final score between 0 and 1")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level")
    flagged: bool = Field(..., description="Whether token is flagged")
    narrative_momentum: float = Field(..., ge=0, le=1, description="Narrative momentum score")
    sentiment_score: float = Field(..., ge=-1, le=1, description="Sentiment score")
    holders: int = Field(..., ge=0, description="Number of token holders")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    provenance: Optional[ProvenanceInfo] = Field(None, description="Data provenance information")
    freshness: Optional[Dict[str, DataSourceInfo]] = Field(None, description="Data freshness by source")
    
    @field_validator('symbol')
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper()
    
    @field_validator('updated_at')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate ISO timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('Invalid ISO timestamp format')
        return v


class AnomalyAlert(BaseModel):
    """Anomaly detection alert."""
    alert_id: str = Field(..., min_length=1, description="Unique alert identifier")
    token_symbol: str = Field(..., min_length=1, max_length=20, description="Token symbol")
    alert_type: Literal["price_spike", "volume_surge", "liquidity_drain", "sentiment_shift"] = Field(
        ..., description="Type of anomaly detected"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Alert severity")
    message: str = Field(..., min_length=1, description="Human-readable alert message")
    timestamp: float = Field(..., gt=0, description="Unix timestamp of alert")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Additional metrics")
    
    @field_validator('token_symbol')
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper()


class ConfidenceInterval(BaseModel):
    """Confidence interval for a metric."""
    value: float = Field(..., description="Measured value")
    lower_bound: float = Field(..., description="Lower confidence bound")
    upper_bound: float = Field(..., description="Upper confidence bound")
    confidence_level: float = Field(..., gt=0, le=1, description="Confidence level (e.g., 0.95)")
    
    @model_validator(mode='after')
    def validate_bounds(self):
        """Ensure bounds are ordered correctly."""
        if self.lower_bound > self.upper_bound:
            raise ValueError('lower_bound must be <= upper_bound')
        if not (self.lower_bound <= self.value <= self.upper_bound):
            raise ValueError('value must be between lower_bound and upper_bound')
        return self


class SLAStatus(BaseModel):
    """SLA status for a data source."""
    source_name: str = Field(..., min_length=1, description="Data source name")
    status: Literal["HEALTHY", "DEGRADED", "FAILED"] = Field(..., description="Current status")
    latency_p50: Optional[float] = Field(None, ge=0, description="50th percentile latency (ms)")
    latency_p95: Optional[float] = Field(None, ge=0, description="95th percentile latency (ms)")
    latency_p99: Optional[float] = Field(None, ge=0, description="99th percentile latency (ms)")
    success_rate: Optional[float] = Field(None, ge=0, le=1, description="Success rate (0-1)")
    uptime_percentage: Optional[float] = Field(None, ge=0, le=100, description="Uptime percentage")


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status."""
    breaker_name: str = Field(..., min_length=1, description="Circuit breaker name")
    state: Literal["CLOSED", "OPEN", "HALF_OPEN"] = Field(..., description="Current state")
    failure_count: int = Field(..., ge=0, description="Number of failures")


class TokenCorrelation(BaseModel):
    """Cross-token correlation data."""
    token_a: str = Field(..., min_length=1, max_length=20, description="First token symbol")
    token_b: str = Field(..., min_length=1, max_length=20, description="Second token symbol")
    correlation: float = Field(..., ge=-1, le=1, description="Correlation coefficient")
    metric: Literal["price", "volume", "sentiment"] = Field(..., description="Metric type")
    
    @field_validator('token_a', 'token_b')
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Ensure symbols are uppercase."""
        return v.upper()


class OrderFlowSnapshot(BaseModel):
    """Order flow depth chart data."""
    token_symbol: str = Field(..., min_length=1, max_length=20, description="Token symbol")
    timestamp: float = Field(..., gt=0, description="Unix timestamp")
    bids: List[tuple[float, float]] = Field(..., description="Bid levels [(price, volume), ...]")
    asks: List[tuple[float, float]] = Field(..., description="Ask levels [(price, volume), ...]")
    bid_depth_usd: float = Field(..., ge=0, description="Total bid depth in USD")
    ask_depth_usd: float = Field(..., ge=0, description="Total ask depth in USD")
    imbalance: float = Field(..., ge=-1, le=1, description="Order book imbalance")
    
    @field_validator('token_symbol')
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper()


class SentimentTrend(BaseModel):
    """Twitter sentiment trend data."""
    token_symbol: str = Field(..., min_length=1, max_length=20, description="Token symbol")
    timestamps: List[float] = Field(..., min_length=1, description="Unix timestamps")
    sentiment_scores: List[float] = Field(..., min_length=1, description="Sentiment scores")
    tweet_volumes: List[int] = Field(..., min_length=1, description="Tweet volumes")
    engagement_scores: List[float] = Field(..., min_length=1, description="Engagement scores")
    
    @field_validator('token_symbol')
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper()
    
    @model_validator(mode='after')
    def validate_list_lengths(self):
        """Ensure all lists have the same length."""
        lengths = [
            len(self.timestamps),
            len(self.sentiment_scores),
            len(self.tweet_volumes),
            len(self.engagement_scores)
        ]
        if len(set(lengths)) > 1:
            raise ValueError('All trend data lists must have the same length')
        return self


# ============================================================================
# API Initialization
# ============================================================================

app = FastAPI(
    title="AutoTrader Dashboard API",
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


# Scanner cache class to hold scan results
class ScannerCache:
    """Cache for scanner results."""
    def __init__(self):
        self.results: List[Any] = []
        self.last_updated: float = 0.0
    
    def update(self, results: List[Any]) -> None:
        """Update cache with new results."""
        self.results = results
        self.last_updated = time.time()
    
    def clear(self) -> None:
        """Clear the cache."""
        self.results = []
        self.last_updated = 0.0


# Global scanner cache instance
_scanner_cache = ScannerCache()


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
            etherscan_client=EtherscanClient(api_key=os.environ.get('ETHERSCAN_API_KEY', '')),
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
            "gem_score": (gem_score.score if gem_score else 0.0) / 100.0,
            "final_score": result.final_score / 100.0,
            "confidence": (gem_score.confidence if gem_score else 100.0) / 100.0,
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
    return {"status": "ok", "message": "AutoTrader Unified API is running"}


@app.get("/api/tokens", response_model=List[TokenResponse], tags=["Scanner"])
def get_tokens(
    min_score: Optional[float] = None,
    min_confidence: Optional[float] = None,
    min_liquidity: Optional[float] = None,
    max_liquidity: Optional[float] = None,
    safety_filter: Optional[str] = None,
    time_window_hours: Optional[int] = None,
    include_provenance: bool = True,
    include_freshness: bool = True,
):
    """Get all scanned tokens with summary information and filters.
    
    Args:
        min_score: Minimum final score (0-1)
        min_confidence: Minimum confidence level (0-1)
        min_liquidity: Minimum liquidity in USD
        max_liquidity: Maximum liquidity in USD
        safety_filter: Safety filter ("safe", "flagged", "all")
        time_window_hours: Only include tokens updated within this many hours
        include_provenance: Include provenance information
        include_freshness: Include freshness badges

    Returns:
        List of token summaries with optional provenance and freshness data
    """
    tokens = [
        ("LINK", "chainlink", "chainlink", "0x514910771AF9Ca656af840dff83E8264EcF986CA"),
        ("UNI", "uniswap", "uniswap", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
        ("AAVE", "aave", "aave", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
        ("PEPE", "pepe", "pepe", "0x6982508145454Ce325dDbE47a25d4ec3d2311933"),
    ]

    summaries: List[Dict[str, Any]] = []
    freshness_tracker = get_freshness_tracker()
    
    for symbol, cg_id, df_slug, addr in tokens:
        entry = _get_cached(symbol)
        if entry:
            logger.info(f"Returning cached summary for {symbol}")
            summary = entry["summary"].copy()
        else:
            detail = scan_token_full(symbol, cg_id, df_slug, addr)
            if not detail:
                logger.error(f"Failed to scan {symbol}; skipping from summary response")
                continue
            entry = _cache_token(symbol, detail)
            summary = entry["summary"].copy()
        
        # Apply filters
        if min_score is not None and summary["final_score"] < min_score:
            continue
        if min_confidence is not None and summary["confidence"] < min_confidence:
            continue
        if min_liquidity is not None and summary["liquidity_usd"] < min_liquidity:
            continue
        if max_liquidity is not None and summary["liquidity_usd"] > max_liquidity:
            continue
        if safety_filter == "safe" and summary["flagged"]:
            continue
        if safety_filter == "flagged" and not summary["flagged"]:
            continue
        if time_window_hours is not None:
            updated_at = datetime.fromisoformat(summary["updated_at"].replace('Z', '+00:00'))
            age_hours = (datetime.utcnow() - updated_at.replace(tzinfo=None)).total_seconds() / 3600
            if age_hours > time_window_hours:
                continue
        
        # Add provenance if requested
        if include_provenance:
            summary["provenance"] = {
                "artifact_id": f"token_{symbol}_{int(time.time())}",
                "data_sources": ["coingecko", "dexscreener", "blockscout"],
                "pipeline_version": "2.0.0",
                "created_at": summary["updated_at"],
            }
        
        # Add freshness if requested
        if include_freshness:
            # Record updates for tracked sources
            freshness_tracker.record_update("coingecko")
            freshness_tracker.record_update("dexscreener")
            freshness_tracker.record_update("blockscout")
            
            freshness_data = {}
            for source in ["coingecko", "dexscreener", "blockscout"]:
                freshness = freshness_tracker.get_freshness(
                    source,
                    is_free=True,
                    update_frequency_seconds=300  # 5 minutes
                )
                freshness_data[source] = freshness.to_dict()
            summary["freshness"] = freshness_data
        
        summaries.append(summary)

    return summaries


@app.get("/api/tokens/{symbol}", tags=["Scanner"])
def get_token(
    symbol: str,
    include_provenance: bool = True,
    include_freshness: bool = True,
):
    """Get detailed information for a specific token.

    Args:
        symbol: Token symbol (e.g., LINK, UNI, AAVE, PEPE)
        include_provenance: Include provenance information
        include_freshness: Include freshness badges

    Returns:
        Detailed token scan results with evidence panels
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
        detail = entry["detail"]
    else:
        try:
            cg_id, df_slug, addr = token_map[symbol]
            result = scan_token_full(symbol, cg_id, df_slug, addr)

            if not result:
                raise HTTPException(status_code=500, detail=f"Scan failed for {symbol} - no result returned")

            entry = _cache_token(symbol, result)
            detail = entry["detail"]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in get_token for {symbol}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
    # Enhance with provenance and freshness
    if include_provenance:
        freshness_tracker = get_freshness_tracker()
        provenance_tracker = get_provenance_tracker()
        
        # Add provenance information
        detail["provenance"] = {
            "artifact_id": f"token_{symbol}_{int(time.time())}",
            "data_sources": ["coingecko", "dexscreener", "blockscout"],
            "pipeline_version": "2.0.0",
            "created_at": detail["updated_at"],
            "clickable_links": {
                "coingecko": f"https://www.coingecko.com/en/coins/{token_map[symbol][0]}",
                "dexscreener": f"https://dexscreener.com/ethereum/{token_map[symbol][2]}",
                "blockscout": f"https://eth.blockscout.com/token/{token_map[symbol][2]}",
            }
        }
        
        # Add freshness badges
        if include_freshness:
            freshness_tracker.record_update("coingecko")
            freshness_tracker.record_update("dexscreener")
            freshness_tracker.record_update("blockscout")
            
            freshness_data = {}
            for source in ["coingecko", "dexscreener", "blockscout"]:
                freshness = freshness_tracker.get_freshness(
                    source,
                    is_free=True,
                    update_frequency_seconds=300
                )
                freshness_data[source] = freshness.to_dict()
            detail["freshness"] = freshness_data
        
        # Add evidence panels with confidence levels
        detail["evidence_panels"] = {
            "price_volume": {
                "title": "Price & Volume Analysis",
                "confidence": detail["confidence"],
                "freshness": freshness_data.get("coingecko", {}).get("freshness_level", "recent") if include_freshness else "recent",
                "source": "coingecko",
                "is_free": True,
                "data": {
                    "price": detail["price"],
                    "volume_24h": detail["market_snapshot"]["volume_24h"],
                }
            },
            "liquidity": {
                "title": "Liquidity Analysis",
                "confidence": detail["confidence"],
                "freshness": freshness_data.get("dexscreener", {}).get("freshness_level", "recent") if include_freshness else "recent",
                "source": "dexscreener",
                "is_free": True,
                "data": {
                    "liquidity_usd": detail["liquidity_usd"],
                }
            },
            "narrative": {
                "title": "Narrative Analysis (NVI)",
                "confidence": detail["confidence"] * 0.9,  # Slightly lower for narrative
                "freshness": "fresh",
                "source": "groq_ai",
                "is_free": True,
                "data": detail["narrative"]
            },
            "tokenomics": {
                "title": "Tokenomics & Unlocks",
                "confidence": detail["confidence"],
                "freshness": freshness_data.get("blockscout", {}).get("freshness_level", "recent") if include_freshness else "recent",
                "source": "blockscout",
                "is_free": True,
                "data": {
                    "holders": detail["holders"],
                    "unlock_events": detail["unlock_events"],
                }
            },
            "safety": {
                "title": "Contract Safety Checks",
                "confidence": detail["confidence"],
                "freshness": freshness_data.get("blockscout", {}).get("freshness_level", "recent") if include_freshness else "recent",
                "source": "blockscout",
                "is_free": True,
                "data": detail["safety_report"]
            }
        }
    
    return detail


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
        metrics = monitor.get_metrics()
        status = monitor.get_metrics().status

        statuses.append(SLAStatus(
            source_name=source_name,
            status=status.value.upper(),
            latency_p50=metrics.latency_p50 if metrics else None,
            latency_p95=metrics.latency_p95 if metrics else None,
            latency_p99=metrics.latency_p99 if metrics else None,
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
            state=breaker.state.value.upper(),
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

@app.get("/api/features/schema", tags=["Feature Store"])
async def get_feature_schema() -> List[Dict[str, Any]]:
    """Get feature store schema.

    Returns:
        List of feature metadata
    """
    return [metadata.to_dict() for metadata in feature_store._schema.values()]


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


# ============================================================================
# GemScore Delta Explainability Endpoints
# ============================================================================

@app.get("/api/gemscore/delta/{token_symbol}", tags=["Analytics"])
async def get_gemscore_delta(token_symbol: str) -> Dict[str, Any]:
    """Get GemScore delta explanation for a token.
    
    Returns the most recent score change with detailed feature contributions.

    Args:
        token_symbol: Token symbol

    Returns:
        Delta explanation with top contributors
    """
    # Get current snapshot
    current_snapshot = feature_store.read_snapshot(token_symbol)
    
    if not current_snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No GemScore snapshots found for {token_symbol}"
        )
    
    # Compute delta
    delta = feature_store.compute_score_delta(token_symbol, current_snapshot)
    
    if not delta:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient history to compute delta for {token_symbol}"
        )
    
    return delta.get_summary(top_n=5)


@app.get("/api/gemscore/delta/{token_symbol}/narrative", tags=["Analytics"])
async def get_gemscore_delta_narrative(token_symbol: str) -> Dict[str, str]:
    """Get human-readable narrative explaining GemScore change.

    Args:
        token_symbol: Token symbol

    Returns:
        Narrative explanation
    """
    current_snapshot = feature_store.read_snapshot(token_symbol)
    
    if not current_snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No GemScore snapshots found for {token_symbol}"
        )
    
    delta = feature_store.compute_score_delta(token_symbol, current_snapshot)
    
    if not delta:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient history to compute delta for {token_symbol}"
        )
    
    return {
        "token": token_symbol,
        "narrative": delta.get_narrative(),
        "timestamp": current_snapshot.timestamp,
    }


@app.get("/api/gemscore/delta/{token_symbol}/detailed", tags=["Analytics"])
async def get_gemscore_delta_detailed(
    token_symbol: str,
    threshold: float = 0.01,
) -> Dict[str, Any]:
    """Get detailed GemScore delta explanation with all significant changes.

    Args:
        token_symbol: Token symbol
        threshold: Minimum contribution change in points (default: 0.01)

    Returns:
        Detailed delta explanation
    """
    from src.core.score_explainer import ScoreExplainer
    
    current_snapshot = feature_store.read_snapshot(token_symbol)
    
    if not current_snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No GemScore snapshots found for {token_symbol}"
        )
    
    delta = feature_store.compute_score_delta(token_symbol, current_snapshot)
    
    if not delta:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient history to compute delta for {token_symbol}"
        )
    
    explainer = ScoreExplainer()
    return explainer.explain_score_change(delta, threshold=threshold)


@app.get("/api/gemscore/history/{token_symbol}", tags=["Analytics"])
async def get_gemscore_history(
    token_symbol: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Get GemScore history for a token.

    Args:
        token_symbol: Token symbol
        limit: Maximum number of snapshots to return (default: 10)

    Returns:
        List of historical snapshots
    """
    snapshots = feature_store.read_snapshot_history(
        token_symbol=token_symbol,
        limit=limit,
    )
    
    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No history found for {token_symbol}"
        )
    
    return [
        {
            "timestamp": snapshot.timestamp,
            "score": snapshot.score,
            "confidence": snapshot.confidence,
            "features": snapshot.features,
            "contributions": snapshot.contributions,
        }
        for snapshot in snapshots
    ]


@app.get("/api/gemscore/deltas/{token_symbol}/series", tags=["Analytics"])
async def get_gemscore_delta_series(
    token_symbol: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Get series of GemScore deltas showing trend over time.

    Args:
        token_symbol: Token symbol
        limit: Number of deltas to compute (default: 5)

    Returns:
        List of delta summaries
    """
    from src.core.score_explainer import ScoreExplainer
    
    snapshots = feature_store.read_snapshot_history(
        token_symbol=token_symbol,
        limit=limit + 1,  # Need one extra for comparisons
    )
    
    if len(snapshots) < 2:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient history for delta series (need at least 2 snapshots)"
        )
    
    explainer = ScoreExplainer()
    deltas = []
    
    # Compute deltas between consecutive snapshots
    for i in range(len(snapshots) - 1):
        current = snapshots[i]
        previous = snapshots[i + 1]  # List is sorted descending
        
        delta = explainer.compute_delta(previous, current)
        deltas.append(delta.get_summary(top_n=3))
    
    return deltas


# ============================================================================
# Summary Reports
# ============================================================================

@app.get("/api/summary/{token_symbol}", tags=["Summary"])
async def get_token_summary_report(token_symbol: str) -> Dict[str, Any]:
    """Get comprehensive summary report for a token.
    
    Returns score, top drivers, risk flags, and recommendations.

    Args:
        token_symbol: Token symbol

    Returns:
        Summary report data
    """
    from src.cli.summary_report import SummaryReportGenerator
    
    # Find scan result
    if not hasattr(_scanner_cache, 'results') or not _scanner_cache.results:
        raise HTTPException(
            status_code=404,
            detail=f"No scan results found for {token_symbol}"
        )
    
    result = None
    for r in _scanner_cache.results:
        if r.token.upper() == token_symbol.upper():
            result = r
            break
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Token {token_symbol} not found"
        )
    
    # Generate summary report
    generator = SummaryReportGenerator(color_enabled=False)
    report = generator.generate_report(
        token_symbol=result.token,
        gem_score=result.gem_score,
        features=result.adjusted_features,
        safety_report=result.safety_report,
        final_score=result.final_score,
        sentiment_metrics=result.sentiment_metrics,
        technical_metrics=result.technical_metrics,
        security_metrics=result.security_metrics,
        flagged=result.flag,
        debug_info=result.debug,
    )
    
    # Convert to JSON
    return generator.export_json(report)


@app.get("/api/summary", tags=["Summary"])
async def get_all_summaries() -> List[Dict[str, Any]]:
    """Get summary reports for all scanned tokens.

    Returns:
        List of summary reports
    """
    from src.cli.summary_report import SummaryReportGenerator
    
    if not hasattr(_scanner_cache, 'results') or not _scanner_cache.results:
        return []
    
    generator = SummaryReportGenerator(color_enabled=False)
    summaries = []
    
    for result in _scanner_cache.results:
        report = generator.generate_report(
            token_symbol=result.token,
            gem_score=result.gem_score,
            features=result.adjusted_features,
            safety_report=result.safety_report,
            final_score=result.final_score,
            sentiment_metrics=result.sentiment_metrics,
            technical_metrics=result.technical_metrics,
            security_metrics=result.security_metrics,
            flagged=result.flag,
            debug_info=result.debug,
        )
        summaries.append(generator.export_json(report))
    
    # Sort by final score descending
    summaries.sort(key=lambda x: x['scores']['final_score'], reverse=True)
    
    return summaries


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
