"""FastAPI application powering the AutoTrader dashboard."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, ForwardRef

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from scripts.demo.main import build_scanner, demo_tokens
from src.cli.run_scanner import build_unlocks, load_config
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient, NewsFeedClient
from src.core.narrative import NarrativeAnalyzer
from src.core.pipeline import HiddenGemScanner, ScanResult, TokenConfig
from src.services.news import NewsAggregator, NewsItem
from src.core.logging_config import init_logging, get_logger
from src.core.metrics import (
    record_api_request,
    record_api_duration,
    record_api_error,
    ActiveRequestTracker,
)
from src.core.tracing import setup_tracing, instrument_fastapi, trace_operation

# ---------------------------------------------------------------------------
# Compatibility patches
# ---------------------------------------------------------------------------
_forward_ref_evaluate = getattr(ForwardRef, "_evaluate", None)
if _forward_ref_evaluate is not None:
    _signature = inspect.signature(_forward_ref_evaluate)
    needs_patch = "recursive_guard" in _signature.parameters and _signature.parameters["recursive_guard"].default is inspect._empty
    if needs_patch:

        def _forward_ref_eval_compat(self, globalns, localns, type_params=None, *, recursive_guard=None):
            if recursive_guard is None:
                recursive_guard = set()
            return _forward_ref_evaluate(self, globalns, localns, type_params, recursive_guard=recursive_guard)

        ForwardRef._evaluate = _forward_ref_eval_compat  # type: ignore[attr-defined]


# Initialize structured logging
logger = get_logger(__name__)

CONFIG_ENV_VAR = "AUTOTRADER_CONFIG"
DEFAULT_CONFIG_PATH = Path("configs/ten_tokens.yaml")


@dataclass
class _DashboardState:
    """Mutable runtime state for the dashboard API."""

    config_path: Path
    config: Dict[str, Any] | None = None
    token_map: Dict[str, TokenConfig] = field(default_factory=dict)
    scanner: HiddenGemScanner | None = None
    results: Dict[str, ScanResult] = field(default_factory=dict)
    trees: Dict[str, Dict[str, Any] | None] = field(default_factory=dict)
    cleanups: List[Callable[[], None]] = field(default_factory=list)
    using_demo: bool = False


def _resolve_config_path() -> Path:
    env_value = os.getenv(CONFIG_ENV_VAR)
    path = Path(env_value) if env_value else DEFAULT_CONFIG_PATH
    
    # If the path is relative, resolve it relative to the project root
    if not path.is_absolute():
        # Assume this file is at src/services/dashboard_api.py
        # So project root is 2 levels up
        project_root = Path(__file__).parent.parent.parent
        path = (project_root / path).resolve()
    
    return path


_state = _DashboardState(config_path=_resolve_config_path())
_scan_lock = asyncio.Lock()


app = FastAPI(
    title="AutoTrader Dashboard API",
    version="0.2.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    description="REST interface exposing Hidden Gem scanner insights for the web dashboard.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for request logging and metrics
@app.middleware("http")
async def observe_requests(request: Request, call_next):
    """Middleware to observe API requests with logging and metrics."""
    start_time = time.time()
    method = request.method
    path = request.url.path
    
    logger.info(
        "api_request_started",
        method=method,
        path=path,
        client=request.client.host if request.client else "unknown",
    )
    
    with ActiveRequestTracker(method, path):
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Record metrics
            record_api_request(method, path, response.status_code)
            record_api_duration(method, path, duration)
            
            # Log completion
            logger.info(
                "api_request_completed",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_seconds=duration,
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            
            # Record error metrics
            record_api_request(method, path, 500)
            record_api_duration(method, path, duration)
            record_api_error(method, path, error_type)
            
            # Log error
            logger.error(
                "api_request_failed",
                method=method,
                path=path,
                error_type=error_type,
                error_message=str(e),
                duration_seconds=duration,
                exc_info=True,
            )
            
            raise


router = APIRouter(prefix="/api")


@app.on_event("startup")
async def _startup() -> None:
    # Initialize observability
    init_logging(service_name="autotrader-api", level=os.getenv("LOG_LEVEL", "INFO"))
    setup_tracing(service_name="autotrader-api")
    instrument_fastapi(app)
    
    logger.info("api_startup", version="0.2.0", config_file="TEN_TOKENS_YAML")
    
    await _initialize_state()
    try:
        await _run_scan(force=True)
    except Exception as exc:  # pragma: no cover - best effort startup scan
        logger.warning("initial_scan_failed", error=str(exc))


@app.on_event("shutdown")
async def _shutdown() -> None:
    logger.info("api_shutdown")
    _close_clients()


async def _initialize_state() -> None:
    _close_clients()
    _clear_results()
    _state.token_map = {}
    _state.scanner = None
    _state.using_demo = False

    logger.info("loading_config", path=str(_state.config_path), absolute_path=str(_state.config_path.absolute()), exists=_state.config_path.exists())
    config = _load_config(_state.config_path)
    _state.config = config

    if not config:
        logger.warning("Config failed to load, falling back to demo mode")
        _activate_demo_mode()
        return

    token_map = _build_token_map(config)
    if not token_map:
        logger.warning("No tokens found in config, falling back to demo mode")
        _activate_demo_mode()
        return

    logger.info("loaded_tokens", count=len(token_map), symbols=[s for s in token_map.keys()])
    _state.token_map = token_map
    scanner, cleanups = _create_scanner(config or {}, token_map)
    _state.scanner = scanner
    _state.cleanups.extend(cleanups)
    _state.using_demo = False


def _load_config(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        logger.info("config_not_found", path=str(path))
        return None
    try:
        return load_config(path)
    except Exception as exc:  # pragma: no cover - config errors surfaced at runtime
        logger.warning("config_load_failed", error=str(exc))
        return None


def _build_token_map(config: Dict[str, Any] | None) -> Dict[str, TokenConfig]:
    if not config:
        return {}

    token_map: Dict[str, TokenConfig] = {}
    for raw in config.get("tokens", []) or []:
        try:
            symbol = str(raw["symbol"]).upper()
            token_config = TokenConfig(
                symbol=str(raw["symbol"]),
                coingecko_id=str(raw["coingecko_id"]),
                defillama_slug=str(raw["defillama_slug"]),
                contract_address=str(raw["contract_address"]),
                narratives=[str(item) for item in raw.get("narratives", []) if item],
                glyph=str(raw.get("glyph", "⧗⟡")),
                unlocks=build_unlocks(raw.get("unlocks", [])),
                news_feeds=[str(url) for url in raw.get("news_feeds", []) if url],
                keywords=[str(keyword) for keyword in (raw.get("keywords") or [raw["symbol"]]) if keyword],
            )
        except KeyError as exc:
            logger.warning("token_config_missing_key", key=str(exc))
            continue
        token_map[symbol] = token_config
    return token_map


def _create_scanner(config: Dict[str, Any], tokens: Mapping[str, TokenConfig]) -> tuple[HiddenGemScanner, List[Callable[[], None]]]:
    coin_client = CoinGeckoClient()
    defi_client = DefiLlamaClient()
    
    # Prefer environment variable over config file for API keys
    # This allows config files to have placeholder values like "YOUR_KEY_HERE"
    etherscan_key = os.getenv("ETHERSCAN_API_KEY") or config.get("etherscan_api_key")
    if etherscan_key == "YOUR_KEY_HERE":
        etherscan_key = None
    etherscan_client = EtherscanClient(api_key=etherscan_key)

    cleanups: List[Callable[[], None]] = [coin_client.close, defi_client.close, etherscan_client.close]

    default_feeds = list(config.get("news_feeds") or config.get("news", {}).get("feeds", []) or [])
    has_token_feeds = any(token_config.news_feeds for token_config in tokens.values())
    news_client: Optional[NewsFeedClient] = None
    news_aggregator: NewsAggregator | None = None
    if default_feeds or has_token_feeds:
        news_client = NewsFeedClient()
        news_aggregator = NewsAggregator(news_client, default_feeds=default_feeds)
        cleanups.append(news_client.close)

    liquidity_threshold = float(config.get("scanner", {}).get("liquidity_threshold", 50_000))
    scanner = HiddenGemScanner(
        coin_client=coin_client,
        defi_client=defi_client,
        etherscan_client=etherscan_client,
        narrative_analyzer=NarrativeAnalyzer(),
        news_aggregator=news_aggregator,
        liquidity_threshold=liquidity_threshold,
    )
    return scanner, cleanups


def _create_demo_scanner() -> tuple[HiddenGemScanner, List[Callable[[], None]]]:
    return build_scanner(), []


def _activate_demo_mode() -> None:
    _close_clients()
    _clear_results()
    _state.token_map = {token_config.symbol.upper(): token_config for token_config in demo_tokens()}
    _state.scanner, cleanups = _create_demo_scanner()
    _state.cleanups.extend(cleanups)
    _state.using_demo = True


def _close_clients() -> None:
    while _state.cleanups:
        cleanup = _state.cleanups.pop()
        try:
            cleanup()
        except Exception:  # pragma: no cover - defensive shutdown
            continue


def _clear_results() -> None:
    _state.results.clear()
    _state.trees.clear()


async def _run_scan(*, force: bool) -> None:
    if _state.scanner is None:
        return
    async with _scan_lock:
        if not force and _state.results:
            return

        loop = asyncio.get_running_loop()

        def _execute(
            current_scanner: HiddenGemScanner,
            current_map: Dict[str, TokenConfig],
        ) -> tuple[Dict[str, ScanResult], Dict[str, Dict[str, Any] | None]]:
            results: Dict[str, ScanResult] = {}
            trees: Dict[str, Dict[str, Any] | None] = {}
            for symbol, config in current_map.items():
                try:
                    # BUGFIX: Call scan_with_tree which should create a fresh context per token
                    # The issue was that the same scanner instance may have shared state
                    result, tree = current_scanner.scan_with_tree(config)
                    logger.info(
                        "token_scanned",
                        symbol=symbol,
                        price=result.market_snapshot.price if result.market_snapshot else 0,
                        liquidity=result.market_snapshot.liquidity_usd if result.market_snapshot else 0,
                    )
                except Exception as exc:  # pragma: no cover - network/runtime failure handling
                    logger.error("scan_failed", symbol=symbol, error=str(exc), exc_info=True)
                    continue
                results[symbol] = result
                trees[symbol] = tree.to_dict() if tree else None
            return results, trees

        async def _run_once() -> tuple[Dict[str, ScanResult], Dict[str, Dict[str, Any] | None]]:
            scanner = _state.scanner
            token_map = dict(_state.token_map)
            if scanner is None or not token_map:
                return {}, {}
            return await loop.run_in_executor(
                None,
                functools.partial(_execute, scanner, token_map),
            )

        results, trees = await _run_once()
        if results:
            _state.results = results
            _state.trees = trees
            return

        # Don't fall back to demo mode - let the errors be visible
        logger.error("Primary scanner produced no results - all token scans failed!")
        # if not _state.using_demo:
        #     logger.warning("Primary scanner produced no results; switching to demo dataset")
        #     _activate_demo_mode()
        #     results, trees = await _run_once()
        #     if results:
        #         _state.results = results
        #         _state.trees = trees


async def _ensure_results() -> None:
    if _state.scanner is None:
        await _initialize_state()
    await _run_scan(force=False)
    if not _state.results:
        raise HTTPException(status_code=503, detail="Scan results not ready")


def _serialize_summary(config: TokenConfig, result: ScanResult) -> Dict[str, Any]:
    snapshot = result.market_snapshot
    narrative = result.narrative
    return {
        "symbol": config.symbol,
        "final_score": result.final_score,
        "gem_score": result.gem_score.score,
        "confidence": result.gem_score.confidence,
        "flagged": result.flag,
        "price": snapshot.price,
        "liquidity_usd": snapshot.liquidity_usd,
        "holders": snapshot.holders,
        "narrative_momentum": narrative.momentum,
        "sentiment_score": narrative.sentiment_score,
        "updated_at": snapshot.timestamp.isoformat(),
    }


def _serialize_market_snapshot(result: ScanResult) -> Dict[str, Any]:
    snapshot = result.market_snapshot
    return {
        "symbol": snapshot.symbol,
        "timestamp": snapshot.timestamp.isoformat(),
        "price": snapshot.price,
        "volume_24h": snapshot.volume_24h,
        "liquidity_usd": snapshot.liquidity_usd,
        "holders": snapshot.holders,
        "onchain_metrics": dict(snapshot.onchain_metrics),
        "narratives": list(snapshot.narratives),
    }


def _serialize_narrative(result: ScanResult) -> Dict[str, Any]:
    insight = result.narrative
    return {
        "sentiment_score": insight.sentiment_score,
        "momentum": insight.momentum,
        "themes": list(insight.themes),
        "volatility": insight.volatility,
        "meme_momentum": insight.meme_momentum,
    }


def _serialize_safety(result: ScanResult) -> Dict[str, Any]:
    report = result.safety_report
    return {
        "score": report.score,
        "severity": report.severity,
        "findings": list(report.findings),
        "flags": dict(report.flags),
    }


def _serialize_unlocks(config: TokenConfig) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for event in config.unlocks:
        events.append(
            {
                "date": event.date.isoformat(),
                "percent_supply": event.percent_supply,
            }
        )
    return events


def _serialize_news(items: Iterable[NewsItem]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for item in items:
        serialized.append(
            {
                "title": item.title,
                "summary": item.summary,
                "link": item.link,
                "source": item.source,
                "published_at": item.published_at.isoformat() if item.published_at else None,
            }
        )
    return serialized


def _serialize_detail(config: TokenConfig, result: ScanResult, tree: Dict[str, Any] | None) -> Dict[str, Any]:
    detail = {
        **_serialize_summary(config, result),
        "raw_features": dict(result.raw_features),
        "adjusted_features": dict(result.adjusted_features),
        "contributions": dict(result.gem_score.contributions),
        "market_snapshot": _serialize_market_snapshot(result),
        "narrative": _serialize_narrative(result),
        "safety_report": _serialize_safety(result),
        "news_items": _serialize_news(result.news_items),
        "sentiment_metrics": dict(result.sentiment_metrics),
        "technical_metrics": dict(result.technical_metrics),
        "security_metrics": dict(result.security_metrics),
        "unlock_events": _serialize_unlocks(config),
        "narratives": list(config.narratives),
        "keywords": list(config.keywords),
        "artifact": {
            "markdown": result.artifact_markdown,
            "html": result.artifact_html,
        },
        "tree": tree,
    }
    return detail


@app.get("/")
def root() -> Dict[str, str]:
    return {"service": "AutoTrader Dashboard API"}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/tokens")
async def list_tokens() -> List[Dict[str, Any]]:
    await _ensure_results()
    summaries: List[Dict[str, Any]] = []
    for symbol, config in _state.token_map.items():
        result = _state.results.get(symbol)
        if result is None:
            continue
        summaries.append(_serialize_summary(config, result))
    summaries.sort(key=lambda item: item["final_score"], reverse=True)
    return summaries


@router.get("/tokens/{symbol}")
async def get_token(symbol: str) -> Dict[str, Any]:
    normalized = symbol.upper()
    if normalized not in _state.token_map:
        raise HTTPException(status_code=404, detail="Unknown token")

    await _ensure_results()

    result = _state.results.get(normalized)
    if result is None:
        raise HTTPException(status_code=404, detail="Token not available")
    tree = _state.trees.get(normalized)
    return _serialize_detail(_state.token_map[normalized], result, tree)


@router.post("/scan")
async def trigger_scan() -> Dict[str, Any]:
    try:
        await _run_scan(force=True)
    except Exception as exc:  # pragma: no cover - surfaced to HTTP response
        logger.exception("Manual scan failed")
        raise HTTPException(status_code=500, detail="Scan execution failed") from exc
    return {"status": "success", "tokens_scanned": len(_state.results)}


@router.post("/refresh", status_code=202)
async def refresh() -> Dict[str, str]:
    _clear_results()
    return {"status": "refreshed"}


@router.get("/debug/state")
async def debug_state() -> Dict[str, Any]:
    """Debug endpoint to check API state."""
    return {
        "using_demo": _state.using_demo,
        "config_path": str(_state.config_path),
        "config_loaded": _state.config is not None,
        "token_count": len(_state.token_map),
        "results_count": len(_state.results),
        "scanner_type": type(_state.scanner).__name__ if _state.scanner else None,
    }


app.include_router(router)
