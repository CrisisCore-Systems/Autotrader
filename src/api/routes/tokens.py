"""FastAPI routes for token discovery endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..schemas.token import TokenResponse
from ..services.scanner import token_scanner_service

# Initialize limiter for this router
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/tokens", tags=["Tokens"])


@router.get("/", response_model=List[TokenResponse])
@limiter.limit("30/minute")
def list_tokens(request: Request) -> List[TokenResponse]:
    """Return summaries for configured tokens.
    
    Rate limit: 30 requests per minute per IP address.
    """
    summaries = token_scanner_service.get_token_summaries()
    return [TokenResponse(**summary) for summary in summaries]


@router.get("/{symbol}")
@limiter.limit("10/minute")
def get_token(request: Request, symbol: str):
    """Return detailed information for a specific token.
    
    Rate limit: 10 requests per minute per IP address (lower due to expensive scan operations).
    """
    try:
        return token_scanner_service.get_token_detail(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Token not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc
