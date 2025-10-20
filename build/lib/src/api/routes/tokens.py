"""FastAPI routes for token discovery endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas.token import TokenResponse
from ..services.scanner import token_scanner_service

router = APIRouter(prefix="/tokens", tags=["Tokens"])


@router.get("/", response_model=List[TokenResponse])
def list_tokens() -> List[TokenResponse]:
    """Return summaries for configured tokens."""
    summaries = token_scanner_service.get_token_summaries()
    return [TokenResponse(**summary) for summary in summaries]


@router.get("/{symbol}")
def get_token(symbol: str):
    """Return detailed information for a specific token."""
    try:
        return token_scanner_service.get_token_detail(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Token not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc
