from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["dashboard"])

# --- Models (abbreviated) ---
class TokenSummary(BaseModel):
    symbol: str
    chain: str
    gemscore: float
    confidence: float
    safety: str
    freshness: str
    badges: dict

class TokensResponse(BaseModel):
    items: List[TokenSummary]
    total: int

@router.get("/tokens", response_model=TokensResponse)
def list_tokens(
    min_score: Optional[float] = None,
    min_confidence: Optional[float] = None,
    safety: Optional[str] = None,
    liquidity_min: Optional[float] = None,
    unlock_within_days: Optional[int] = None,
    time_window: Optional[str] = None,
    paid: bool = False
):
    # TODO: Wire into src.core pipeline; map to FREE vs paid clients
    # TODO: Include provenance/freshness/confidence with each item
    return TokensResponse(items=[], total=0)