"""Simple FastAPI server to serve token scan results"""
import os
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API keys must be set via environment variables before running
# Example: export GROQ_API_KEY="your-key-here"
if not os.environ.get('GROQ_API_KEY'):
    logger.warning("GROQ_API_KEY not set in environment variables")
if not os.environ.get('ETHERSCAN_API_KEY'):
    logger.warning("ETHERSCAN_API_KEY not set in environment variables")
if not os.environ.get('COINGECKO_API_KEY'):
    logger.warning("COINGECKO_API_KEY not set in environment variables")

from src.core.pipeline import HiddenGemScanner, TokenConfig, ScanContext
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient


app = FastAPI(title="VoidBloom API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TokenResponse(BaseModel):
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


# Global scanner instance and cache configuration
scanner = None
cached_results: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300


def _parse_iso_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def _build_summary(detail: Dict[str, Any]) -> Dict[str, Any]:
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
    entry = cached_results.get(symbol)
    if not entry:
        return None

    timestamp = entry.get("timestamp")
    if not timestamp:
        return None

    if (datetime.utcnow() - timestamp).total_seconds() > CACHE_TTL_SECONDS:
        return None

    return entry


def init_scanner():
    """Initialize the scanner"""
    global scanner
    if scanner is None:
        scanner = HiddenGemScanner(
            coin_client=CoinGeckoClient(),
            defi_client=DefiLlamaClient(),
            etherscan_client=EtherscanClient(api_key=os.environ.get('ETHERSCAN_API_KEY', '')),
        )
    return scanner


def serialize_tree_node(node) -> Dict[str, Any]:
    """Serialize a TreeNode to a dictionary"""
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
    """Scan a single token and return full detailed results"""
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


@app.get("/")
def root():
    return {"status": "ok", "message": "VoidBloom API is running"}


@app.get("/api/tokens", response_model=List[TokenResponse])
def get_tokens():
    """Get all scanned tokens"""
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


@app.get("/api/tokens/{symbol}")
def get_token(symbol: str):
    """Get detailed information for a specific token"""
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


# Run with: uvicorn simple_api:app --host 127.0.0.1 --port 8000
