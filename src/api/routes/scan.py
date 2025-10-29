"""FastAPI routes to trigger on-demand token scans (lightweight mode)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient
from src.core.clients import CoinGeckoClient
from src.core.tracing import trace_operation
from src.core.logging_config import get_logger

# Import social clients (optional)
try:
    from src.core.twitter_client import TwitterClientV2
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False

try:
    from src.core.reddit_client import RedditClient
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False

try:
    from src.services.social import SocialAggregator, SocialStream
    SOCIAL_AGGREGATOR_AVAILABLE = True
except ImportError:
    SOCIAL_AGGREGATOR_AVAILABLE = False


router = APIRouter(prefix="/scan", tags=["Scan"])
# Note: We rely on the app-level Limiter configured in main. Avoid creating a separate
# limiter instance here to prevent mismatch causing runtime errors.
logger = get_logger(__name__)


class UnlockEventModel(BaseModel):
    date: datetime
    percent_supply: float


class ScanRequest(BaseModel):
    symbol: str = Field(..., description="Token symbol, e.g. 'PEPE'")
    coingecko_id: str = Field(..., description="CoinGecko token id")
    contract_address: str = Field(..., description="Mainnet contract address")
    defillama_slug: Optional[str] = Field(None, description="DefiLlama protocol slug if applicable")
    narratives: List[str] = Field(default_factory=list, description="Optional narrative snippets")
    unlocks: List[UnlockEventModel] = Field(default_factory=list, description="Optional unlock schedule")


class ScanResponse(BaseModel):
    token: str
    gem_score: float
    confidence: float
    flagged: bool
    liquidity_ok: bool
    created_at: str
    artifact_markdown_path: Optional[str] = None
    artifact_html_path: Optional[str] = None
    debug: Dict[str, Any] = {}


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


@router.post("/run", response_model=ScanResponse)
def run_scan(request: Request, payload: ScanRequest = Body(...)) -> ScanResponse:
    """Run a one-off scan using free/public data sources.

    Uses: CoinGecko (public), Dexscreener (public), Blockscout (public), public Ethereum RPC.
    Saves rendered artifacts under artifacts/scans/.
    """
    # Basic sanity checks
    if not payload.contract_address.startswith("0x"):
        raise HTTPException(status_code=400, detail="contract_address must be a 0x-prefixed hex address")

    # Initialize FREE/public clients
    gecko = CoinGeckoClient()
    dexs = DexscreenerClient()
    blockscout = BlockscoutClient()
    rpc = EthereumRPCClient()

    # Build token config
    config = TokenConfig(
        symbol=payload.symbol,
        coingecko_id=payload.coingecko_id,
        defillama_slug=payload.defillama_slug or payload.symbol.lower(),
        contract_address=payload.contract_address,
        narratives=list(payload.narratives or []),
        unlocks=[
            # Convert pydantic model to dataclass expected by pipeline
            # We'll import here to avoid circulars at import time
        ],
    )

    # Convert unlocks to dataclass instances
    if payload.unlocks:
        from src.core.pipeline import UnlockEvent

        config.unlocks = [
            UnlockEvent(date=u.date, percent_supply=u.percent_supply) for u in payload.unlocks
        ]

    scanner = HiddenGemScanner(
        coin_client=gecko,
        dex_client=dexs,
        blockscout_client=blockscout,
        rpc_client=rpc,
    )
    
    # Optionally add social feeds if configured
    social_aggregator = None
    if SOCIAL_AGGREGATOR_AVAILABLE:
        streams = []
        
        # Add Twitter feed if credentials available
        if TWITTER_AVAILABLE:
            import os
            twitter_token = os.getenv("TWITTER_BEARER_TOKEN")
            if twitter_token:
                try:
                    twitter_client = TwitterClientV2(bearer_token=twitter_token)
                    # Note: Twitter API v2 doesn't have a direct feed URL, 
                    # we'll need to fetch programmatically in a wrapper
                    logger.info("twitter_enabled", token_symbol=payload.symbol)
                except Exception as exc:
                    logger.warning("twitter_init_failed", error=str(exc))
        
        # Add Reddit feed if credentials available  
        if REDDIT_AVAILABLE:
            import os
            reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
            reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            if reddit_client_id and reddit_client_secret:
                try:
                    reddit_client = RedditClient(
                        client_id=reddit_client_id,
                        client_secret=reddit_client_secret,
                    )
                    # Fetch Reddit posts and normalize to social feed format
                    reddit_posts = reddit_client.fetch_crypto_sentiment(
                        token_symbol=payload.symbol,
                        hours_back=24,
                        min_score=10,
                        limit=20,
                    )
                    logger.info("reddit_fetched", token_symbol=payload.symbol, posts=len(reddit_posts))
                    # Store for later processing
                except Exception as exc:
                    logger.warning("reddit_fetch_failed", error=str(exc))

    with trace_operation("api.run_scan", attributes={"token": payload.symbol}):
        try:
            result = scanner.scan(config)
        except Exception as exc:
            logger.error("scan_failed", token=payload.symbol, error=str(exc), exc_info=True)
            raise HTTPException(status_code=502, detail=f"Scan failed: {exc}")

    # Persist artifacts to disk
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_dir = Path("artifacts") / "scans" / payload.symbol.upper()
    _ensure_dir(base_dir)
    md_path = base_dir / f"{payload.symbol.upper()}_{ts}.md"
    html_path = base_dir / f"{payload.symbol.upper()}_{ts}.html"

    try:
        if result.artifact_markdown:
            md_path.write_text(result.artifact_markdown, encoding="utf-8")
        if result.artifact_html:
            html_path.write_text(result.artifact_html, encoding="utf-8")
    except Exception as write_exc:  # Do not fail the request on write errors
        logger.warning("artifact_write_failed", error=str(write_exc))

    return ScanResponse(
        token=result.token,
        gem_score=result.gem_score.score,
        confidence=result.gem_score.confidence,
        flagged=result.flag,
        liquidity_ok=bool(getattr(result, "safety_report", None)) and bool(getattr(result, "artifact_payload", {}).get("flags", [])),
        created_at=ts,
        artifact_markdown_path=str(md_path) if md_path.exists() else None,
        artifact_html_path=str(html_path) if html_path.exists() else None,
        debug=result.debug or {},
    )


class RecentScanItem(BaseModel):
    symbol: str
    gem_score: float
    confidence: float
    flagged: bool
    created_at: str
    artifact_markdown_path: str
    artifact_html_path: str


@router.get("/recent", response_model=List[RecentScanItem])
def list_recent_scans(
    request: Request,
    limit: int = 20,
) -> List[RecentScanItem]:
    """List recent scan artifacts sorted by timestamp (newest first).
    
    Args:
        limit: Maximum number of scans to return (default 20, max 100)
        
    Returns:
        List of recent scans with scores and artifact paths
    """
    limit = min(limit, 100)
    artifacts_base = Path("artifacts") / "scans"
    
    if not artifacts_base.exists():
        return []
    
    # Collect all JSON metadata files (we'll use the response JSON structure from run_scan)
    # For now, we'll scan the filesystem for .md files and parse the timestamp from filenames
    scans = []
    
    for symbol_dir in artifacts_base.iterdir():
        if not symbol_dir.is_dir():
            continue
        
        symbol = symbol_dir.name
        
        for md_file in symbol_dir.glob("*.md"):
            # Parse timestamp from filename: SYMBOL_YYYYMMDDTHHMMSSZ.md
            stem = md_file.stem
            parts = stem.split("_")
            if len(parts) < 2:
                continue
            
            ts_str = parts[-1]  # YYYYMMDDTHHMMSSZ
            html_file = md_file.with_suffix(".html")
            
            # We don't have gem_score in the filename, so we'll show a placeholder
            # In production, you'd save a .json metadata file alongside the artifacts
            scans.append(RecentScanItem(
                symbol=symbol,
                gem_score=0.0,  # Placeholder - would read from metadata JSON
                confidence=0.0,  # Placeholder
                flagged=False,   # Placeholder
                created_at=ts_str,
                artifact_markdown_path=str(md_file),
                artifact_html_path=str(html_file) if html_file.exists() else "",
            ))
    
    # Sort by created_at descending (newest first)
    scans.sort(key=lambda x: x.created_at, reverse=True)
    
    return scans[:limit]


@router.get("/view/{symbol}/{filename}", response_class=HTMLResponse)
def view_artifact(
    request: Request,
    symbol: str,
    filename: str,
) -> HTMLResponse:
    """Serve an HTML artifact for viewing in the browser.
    
    Args:
        symbol: Token symbol (e.g., 'UNI')
        filename: Artifact filename (e.g., 'UNI_20251028T225054Z.html')
        
    Returns:
        HTML content for browser rendering
    """
    # Security: validate symbol and filename to prevent path traversal
    if ".." in symbol or "/" in symbol or "\\" in symbol:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="Only HTML artifacts can be viewed")
    
    artifact_path = Path("artifacts") / "scans" / symbol / filename
    
    if not artifact_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {symbol}/{filename}"
        )
    
    try:
        html_content = artifact_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)
    except Exception as exc:
        logger.error("artifact_read_failed", symbol=symbol, filename=filename, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {exc}")


class SocialFeedRequest(BaseModel):
    token_symbol: str = Field(..., description="Token symbol for social sentiment fetch")
    hours_back: int = Field(24, description="Hours to look back for posts", ge=1, le=168)
    limit: int = Field(50, description="Maximum posts to return", ge=1, le=200)


class SocialFeedResponse(BaseModel):
    token_symbol: str
    twitter_posts: List[Dict[str, Any]] = []
    reddit_posts: List[Dict[str, Any]] = []
    total_posts: int
    sentiment_summary: Dict[str, Any] = {}


@router.post("/social-feeds", response_model=SocialFeedResponse)
def fetch_social_feeds(
    request: Request,
    payload: SocialFeedRequest = Body(...),
) -> SocialFeedResponse:
    """Fetch Twitter and Reddit social sentiment feeds for a token.
    
    Args:
        payload: Request with token symbol and fetch parameters
        
    Returns:
        Combined social feed data from Twitter and Reddit
        
    Note:
        Requires TWITTER_BEARER_TOKEN and/or REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET
        environment variables to be set. Returns empty lists if credentials not configured.
    """
    import os
    
    twitter_posts = []
    reddit_posts = []
    
    # Fetch Twitter posts if configured
    if TWITTER_AVAILABLE:
        twitter_token = os.getenv("TWITTER_BEARER_TOKEN")
        if twitter_token:
            try:
                twitter_client = TwitterClientV2(bearer_token=twitter_token)
                response = twitter_client.fetch_sentiment_signals(
                    token_symbol=payload.token_symbol,
                    hours_back=payload.hours_back,
                    max_results=min(payload.limit, 100),
                    min_engagement=5,
                )
                
                # Normalize Twitter response
                tweets = response.get("data", [])
                for tweet in tweets:
                    metrics = tweet.get("public_metrics", {})
                    twitter_posts.append({
                        "id": tweet.get("id"),
                        "platform": "twitter",
                        "author_id": tweet.get("author_id"),
                        "content": tweet.get("text", ""),
                        "created_at": tweet.get("created_at"),
                        "metrics": {
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "replies": metrics.get("reply_count", 0),
                            "quotes": metrics.get("quote_count", 0),
                        },
                        "url": f"https://twitter.com/i/web/status/{tweet.get('id')}",
                    })
                
                logger.info("twitter_fetched", token_symbol=payload.token_symbol, count=len(twitter_posts))
                
            except Exception as exc:
                logger.warning("twitter_fetch_failed", token_symbol=payload.token_symbol, error=str(exc))
    
    # Fetch Reddit posts if configured
    if REDDIT_AVAILABLE:
        reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        
        if reddit_client_id and reddit_client_secret:
            try:
                reddit_client = RedditClient(
                    client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                )
                
                posts = reddit_client.fetch_crypto_sentiment(
                    token_symbol=payload.token_symbol,
                    hours_back=payload.hours_back,
                    min_score=10,
                    limit=payload.limit,
                )
                
                # Normalize Reddit posts
                for post in posts:
                    reddit_posts.append(reddit_client.normalize_to_social_post(post))
                
                logger.info("reddit_fetched", token_symbol=payload.token_symbol, count=len(reddit_posts))
                
            except Exception as exc:
                logger.warning("reddit_fetch_failed", token_symbol=payload.token_symbol, error=str(exc))
    
    # Calculate simple sentiment summary
    total_engagement = 0
    if twitter_posts:
        total_engagement += sum(
            p["metrics"].get("likes", 0) + p["metrics"].get("retweets", 0) 
            for p in twitter_posts
        )
    if reddit_posts:
        total_engagement += sum(
            p["metrics"].get("score", 0) 
            for p in reddit_posts
        )
    
    sentiment_summary = {
        "twitter_count": len(twitter_posts),
        "reddit_count": len(reddit_posts),
        "total_engagement": total_engagement,
        "avg_engagement_per_post": (
            total_engagement / (len(twitter_posts) + len(reddit_posts))
            if (twitter_posts or reddit_posts) else 0
        ),
    }
    
    return SocialFeedResponse(
        token_symbol=payload.token_symbol,
        twitter_posts=twitter_posts,
        reddit_posts=reddit_posts,
        total_posts=len(twitter_posts) + len(reddit_posts),
        sentiment_summary=sentiment_summary,
    )
