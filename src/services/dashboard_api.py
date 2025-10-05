"""FastAPI application powering the VoidBloom dashboard."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from main import build_scanner, demo_tokens
from src.core.pipeline import ScanResult, TokenConfig
from src.services.news import NewsItem

app = FastAPI(
    title="VoidBloom Dashboard API",
    version="0.1.0",
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

router = APIRouter(prefix="/api")


@lru_cache(maxsize=1)
def _scanner():
    return build_scanner()


@lru_cache(maxsize=1)
def _token_map() -> Dict[str, TokenConfig]:
    return {config.symbol.upper(): config for config in demo_tokens()}


@lru_cache(maxsize=32)
def _scan(symbol: str) -> tuple[ScanResult, Dict[str, object]]:
    normalized = symbol.upper()
    token_map = _token_map()
    if normalized not in token_map:
        raise KeyError(symbol)
    result, tree = _scanner().scan_with_tree(token_map[normalized])
    return result, tree.to_dict()


def _serialize_summary(config: TokenConfig, result: ScanResult) -> Dict[str, object]:
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


def _serialize_market_snapshot(result: ScanResult) -> Dict[str, object]:
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


def _serialize_narrative(result: ScanResult) -> Dict[str, object]:
    insight = result.narrative
    return {
        "sentiment_score": insight.sentiment_score,
        "momentum": insight.momentum,
        "themes": list(insight.themes),
        "volatility": insight.volatility,
        "meme_momentum": insight.meme_momentum,
    }


def _serialize_safety(result: ScanResult) -> Dict[str, object]:
    report = result.safety_report
    return {
        "score": report.score,
        "severity": report.severity,
        "findings": list(report.findings),
        "flags": dict(report.flags),
    }


def _serialize_unlocks(config: TokenConfig) -> List[Dict[str, object]]:
    events = []
    for event in config.unlocks:
        events.append(
            {
                "date": event.date.isoformat(),
                "percent_supply": event.percent_supply,
            }
        )
    return events


def _serialize_news(items: Iterable[NewsItem]) -> List[Dict[str, object]]:
    serialized: List[Dict[str, object]] = []
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


def _serialize_detail(config: TokenConfig, result: ScanResult, tree: Dict[str, object]) -> Dict[str, object]:
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
    return {"service": "VoidBloom Dashboard API"}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/tokens")
def list_tokens() -> List[Dict[str, object]]:
    summaries: List[Dict[str, object]] = []
    for symbol, config in _token_map().items():
        result, _ = _scan(symbol)
        summaries.append(_serialize_summary(config, result))
    summaries.sort(key=lambda item: item["final_score"], reverse=True)
    return summaries


@router.get("/tokens/{symbol}")
def get_token(symbol: str) -> Dict[str, object]:
    normalized = symbol.upper()
    token_map = _token_map()
    if normalized not in token_map:
        raise HTTPException(status_code=404, detail="Unknown token")
    try:
        result, tree = _scan(normalized)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown token") from None
    return _serialize_detail(token_map[normalized], result, tree)


@router.post("/refresh", status_code=202)
def refresh() -> Dict[str, str]:
    _scan.cache_clear()
    _scanner.cache_clear()
    return {"status": "refreshed"}


app.include_router(router)
