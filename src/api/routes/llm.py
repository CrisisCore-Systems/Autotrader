"""
LLM Microservice - FastAPI endpoints for local Ollama inference.

Provides 3 endpoints:
1. POST /llm/news_to_signal - Convert news headlines to trading signal
2. POST /llm/trade_plan - Generate trade plan with reasoning
3. POST /llm/calibrate - Calibrate confidence based on outcomes

All endpoints use local CPU-only models (no GPU required).
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from src.agentic.llm_gateway import (
    LLMGateway,
    news_to_signal,
    generate_trade_plan,
    calibrate_confidence,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm", tags=["llm"])

# Initialize LLM gateway (shared across requests)
gateway = LLMGateway()


# Request/Response Models

class NewsToSignalRequest(BaseModel):
    """Request for news-to-signal conversion."""
    headlines: List[str] = Field(..., description="News headlines to analyze")
    
    class Config:
        json_schema_extra = {
            "example": {
                "headlines": [
                    "AAPL announces record iPhone sales",
                    "Apple stock upgraded by Goldman Sachs",
                    "Tech sector rallies on positive earnings"
                ]
            }
        }


class NewsToSignalResponse(BaseModel):
    """Trading signal from news analysis."""
    impact: str = Field(..., description="POSITIVE, NEGATIVE, or NEUTRAL")
    tickers: List[str] = Field(..., description="Affected tickers")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Signal confidence")
    rationale: str = Field(..., description="Brief explanation")
    latency_ms: float = Field(..., description="Processing time")
    cached: bool = Field(..., description="Whether response was cached")


class TradePlanRequest(BaseModel):
    """Request for trade plan generation."""
    ticker: str = Field(..., description="Stock ticker")
    setup: Dict[str, Any] = Field(..., description="Technical setup details")
    market_regime: str = Field(..., description="Current market regime")
    risk_snapshot: Dict[str, Any] = Field(..., description="Risk metrics")
    max_risk_pct: float = Field(default=1.0, description="Max risk per trade (%)")
    min_reward_risk: float = Field(default=2.0, description="Min reward/risk ratio")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "setup": {
                    "rsi": 35,
                    "dist_200dma": -5.2,
                    "volume_spike": 1.3,
                    "gap_down_pct": -3.5
                },
                "market_regime": "CHOPPY",
                "risk_snapshot": {
                    "portfolio_beta": 1.2,
                    "cash_pct": 25,
                    "max_position_exposure": 8
                },
                "max_risk_pct": 1.0,
                "min_reward_risk": 2.0
            }
        }


class TradePlanResponse(BaseModel):
    """Generated trade plan."""
    action: str = Field(..., description="BUY, SELL, HOLD, or WATCH")
    entry_price: Optional[float] = Field(None, description="Suggested entry price")
    stop_loss: Optional[float] = Field(None, description="Stop loss level")
    take_profit: Optional[float] = Field(None, description="Take profit target")
    position_size_pct: Optional[float] = Field(None, description="Position size (% of portfolio)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Plan confidence")
    reasoning: List[str] = Field(..., description="Reasons for the plan")
    risks: List[str] = Field(..., description="Identified risks")
    latency_ms: float = Field(..., description="Processing time")
    cached: bool = Field(..., description="Whether response was cached")


class CalibrationRequest(BaseModel):
    """Request for confidence calibration."""
    predictions: List[Dict[str, Any]] = Field(..., description="Historical predictions")
    outcomes: List[Dict[str, Any]] = Field(..., description="Actual outcomes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "predictions": [
                    {"ticker": "AAPL", "confidence": 0.85, "prediction": "UP"},
                    {"ticker": "MSFT", "confidence": 0.70, "prediction": "DOWN"}
                ],
                "outcomes": [
                    {"ticker": "AAPL", "actual": "UP", "pnl_pct": 2.3},
                    {"ticker": "MSFT", "actual": "UP", "pnl_pct": -1.5}
                ]
            }
        }


class CalibrationResponse(BaseModel):
    """Calibration adjustments."""
    calibration_error: float = Field(..., description="Overall calibration error")
    adjustments: Dict[str, float] = Field(..., description="Confidence multipliers by tier")
    recommendations: List[str] = Field(..., description="Calibration recommendations")
    latency_ms: float = Field(..., description="Processing time")
    cached: bool = Field(..., description="Whether response was cached")


# API Endpoints

@router.post("/news_to_signal", response_model=NewsToSignalResponse)
async def convert_news_to_signal(request: NewsToSignalRequest = Body(...)):
    """
    Convert news headlines to trading signal.
    
    Uses fast Phi-3 Mini model (≤1s latency).
    
    **Agent Usage**: NewsSentry (non-critical path)
    
    **Example**:
    ```json
    {
      "headlines": [
        "AAPL announces record iPhone sales",
        "Apple stock upgraded by Goldman Sachs"
      ]
    }
    ```
    
    **Returns**:
    ```json
    {
      "impact": "POSITIVE",
      "tickers": ["AAPL"],
      "confidence": 0.85,
      "rationale": "Strong fundamentals + analyst upgrade"
    }
    ```
    """
    try:
        result = await news_to_signal(request.headlines, gateway)
        
        # Get response metadata from last call
        last_response = gateway.cache.db.execute("""
        SELECT avg_latency_ms FROM llm_cache 
        ORDER BY created_at DESC LIMIT 1
        """).fetchone()
        
        return NewsToSignalResponse(
            impact=result["impact"],
            tickers=result["tickers"],
            confidence=result["confidence"],
            rationale=result["rationale"],
            latency_ms=last_response[0] if last_response else 0,
            cached=False,  # Updated by gateway internally
        )
        
    except Exception as e:
        logger.error(f"news_to_signal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade_plan", response_model=TradePlanResponse)
async def create_trade_plan(request: TradePlanRequest = Body(...)):
    """
    Generate trade plan with reasoning.
    
    Uses Qwen2.5-7B model (2-5s latency).
    
    **Agent Usage**: Forecaster, Auditor (off critical path)
    
    **Example**:
    ```json
    {
      "ticker": "AAPL",
      "setup": {
        "rsi": 35,
        "dist_200dma": -5.2,
        "volume_spike": 1.3
      },
      "market_regime": "CHOPPY",
      "risk_snapshot": {
        "portfolio_beta": 1.2,
        "cash_pct": 25
      }
    }
    ```
    
    **Returns**:
    ```json
    {
      "action": "BUY",
      "entry_price": 175.50,
      "stop_loss": 170.00,
      "take_profit": 185.00,
      "confidence": 0.78,
      "reasoning": ["Oversold RSI", "Strong support at 200DMA"]
    }
    ```
    """
    try:
        result = await generate_trade_plan(
            ticker=request.ticker,
            setup=request.setup,
            market_regime=request.market_regime,
            risk_snapshot=request.risk_snapshot,
            max_risk_pct=request.max_risk_pct,
            min_reward_risk=request.min_reward_risk,
            gateway=gateway,
        )
        
        return TradePlanResponse(
            action=result["action"],
            entry_price=result.get("entry_price"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit"),
            position_size_pct=result.get("position_size_pct"),
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            risks=result["risks"],
            latency_ms=0,  # Updated by gateway
            cached=False,
        )
        
    except Exception as e:
        logger.error(f"trade_plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calibrate", response_model=CalibrationResponse)
async def calibrate_model(request: CalibrationRequest = Body(...)):
    """
    Calibrate confidence based on historical predictions vs outcomes.
    
    Uses Qwen2.5-7B model (2-5s latency).
    
    **Agent Usage**: Auditor (nightly batch job)
    
    **Example**:
    ```json
    {
      "predictions": [
        {"ticker": "AAPL", "confidence": 0.85, "prediction": "UP"},
        {"ticker": "MSFT", "confidence": 0.70, "prediction": "DOWN"}
      ],
      "outcomes": [
        {"ticker": "AAPL", "actual": "UP", "pnl_pct": 2.3},
        {"ticker": "MSFT", "actual": "UP", "pnl_pct": -1.5}
      ]
    }
    ```
    
    **Returns**:
    ```json
    {
      "calibration_error": 0.15,
      "adjustments": {
        "high_confidence": 0.95,
        "medium_confidence": 1.05,
        "low_confidence": 1.10
      },
      "recommendations": ["Reduce high confidence predictions by 5%"]
    }
    ```
    """
    try:
        result = await calibrate_confidence(
            predictions=request.predictions,
            outcomes=request.outcomes,
            gateway=gateway,
        )
        
        return CalibrationResponse(
            calibration_error=result["calibration_error"],
            adjustments=result["adjustments"],
            recommendations=result["recommendations"],
            latency_ms=0,  # Updated by gateway
            cached=False,
        )
        
    except Exception as e:
        logger.error(f"calibrate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Check if Ollama is running and models are available.
    
    **Returns**:
    ```json
    {
      "status": "healthy",
      "ollama_running": true,
      "available_models": ["phi3:mini", "qwen2.5:7b-instruct"],
      "cache_stats": {
        "total_entries": 42,
        "avg_hits_per_entry": 3.5
      }
    }
    ```
    """
    try:
        ollama_healthy = await gateway.health_check()
        
        if not ollama_healthy:
            return {
                "status": "unhealthy",
                "ollama_running": False,
                "error": "Ollama not responding. Start with: ollama serve"
            }
        
        models = await gateway.list_models()
        cache_stats = gateway.cache.stats()
        
        return {
            "status": "healthy",
            "ollama_running": True,
            "available_models": models,
            "cache_stats": cache_stats,
        }
        
    except Exception as e:
        logger.error(f"health_check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get semantic cache statistics.
    
    **Returns**:
    ```json
    {
      "total_entries": 42,
      "avg_hits_per_entry": 3.5,
      "avg_latency_ms": 2341.5
    }
    ```
    """
    return gateway.cache.stats()


@router.delete("/cache/clear")
async def clear_cache(days: int = 30):
    """
    Clear old cache entries.
    
    **Args**:
    - days: Clear entries older than N days (default: 30)
    
    **Returns**:
    ```json
    {
      "status": "cleared",
      "days": 30
    }
    ```
    """
    try:
        gateway.cache.clear_old(days)
        return {
            "status": "cleared",
            "days": days
        }
    except Exception as e:
        logger.error(f"cache_clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
