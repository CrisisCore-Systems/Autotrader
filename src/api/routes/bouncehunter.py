"""FastAPI routes for BounceHunter mean-reversion scanner."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel, Field

from src.bouncehunter import BounceHunter, BounceHunterConfig
from src.core.tracing import trace_operation
from src.core.logging_config import get_logger


router = APIRouter(prefix="/bouncehunter", tags=["BounceHunter"])
logger = get_logger(__name__)


class ScanRequest(BaseModel):
    """Request to scan for mean-reversion signals."""
    
    tickers: List[str] = Field(
        ...,
        description="List of ticker symbols to scan (e.g., ['AAPL', 'MSFT', 'TSLA'])",
    )
    use_cache: bool = Field(
        True,
        description="Use cached model if available (faster)",
    )
    force_refresh: bool = Field(
        False,
        description="Force model retraining even if cache exists",
    )
    max_cache_age_hours: int = Field(
        24,
        description="Maximum cache age in hours before refresh",
        ge=1,
        le=168,
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                "use_cache": True,
                "force_refresh": False,
                "max_cache_age_hours": 24,
            }
        }


class SignalResponse(BaseModel):
    """Individual mean-reversion signal."""
    
    ticker: str
    signal_date: str
    probability: float
    z_score: float
    rsi2: float
    bb_deviation: float
    distance_200ma: float
    trend_63d: float
    gap_down: bool
    vix_regime: str
    entry_price: float
    target_price: Optional[float] = None
    stop_price: Optional[float] = None


class ScanResponse(BaseModel):
    """Response with all detected signals."""
    
    scan_timestamp: str
    total_tickers_scanned: int
    signals_found: int
    signals: List[SignalResponse]
    statistics: Dict[str, Any]
    cache_info: Optional[Dict[str, Any]] = None


@router.post("/scan", response_model=ScanResponse)
def scan_for_bounces(
    request: Request,
    payload: ScanRequest = Body(...),
) -> ScanResponse:
    """Scan stocks for mean-reversion opportunities using BounceHunter.
    
    The BounceHunter scanner identifies oversold conditions using:
    - Z-score momentum (5-day)
    - RSI-2 (2-day RSI)
    - Bollinger Band deviations
    - Distance from 200-day MA
    - 63-day trend strength
    - Gap-down detection
    - VIX regime classification
    
    Returns probability-ranked signals with entry/exit levels.
    
    Args:
        payload: Scan configuration with tickers and filters
        
    Returns:
        List of mean-reversion signals sorted by probability
    """
    logger.info(
        "bouncehunter_scan_started",
        tickers_count=len(payload.tickers),
        use_cache=payload.use_cache,
        force_refresh=payload.force_refresh,
    )
    
    # Configure BounceHunter with caching
    config = BounceHunterConfig(
        tickers=payload.tickers,
    )
    
    scanner = BounceHunter(
        config=config,
        use_cache=payload.use_cache,
        max_cache_age_hours=payload.max_cache_age_hours,
    )
    
    with trace_operation("bouncehunter.scan", attributes={"ticker_count": len(payload.tickers)}):
        try:
            # Train model on historical data (may use cache)
            logger.info("bouncehunter_training", tickers=payload.tickers[:5], use_cache=payload.use_cache)
            train_df = scanner.fit(force_refresh=payload.force_refresh)
            
            # Get cache info
            cache_info = scanner.get_cache_info()
            
            # Generate current signals
            logger.info("bouncehunter_scanning")
            signal_reports = scanner.scan()
            
        except Exception as exc:
            logger.error("bouncehunter_scan_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")
    
    # Convert signals to response format
    signals = []
    for report in signal_reports:
        signals.append(SignalResponse(
            ticker=report.ticker,
            signal_date=report.date,
            probability=report.probability,
            z_score=report.z_score,
            rsi2=report.rsi2,
            bb_deviation=0.0,  # Not in SignalReport, placeholder
            distance_200ma=report.dist_200dma,
            trend_63d=0.0,  # Not in SignalReport, placeholder
            gap_down=False,  # Not in SignalReport, placeholder
            vix_regime="unknown",  # Not in SignalReport, placeholder
            entry_price=report.entry,
            target_price=report.target,
            stop_price=report.stop,
        ))
    
    # Sort by probability descending
    signals.sort(key=lambda s: s.probability, reverse=True)
    
    # Calculate statistics
    if signals:
        probabilities = [s.probability for s in signals]
        z_scores = [s.z_score for s in signals]
        statistics = {
            "avg_probability": sum(probabilities) / len(probabilities),
            "max_probability": max(probabilities),
            "min_probability": min(probabilities),
            "avg_z_score": sum(z_scores) / len(z_scores),
            "gap_down_count": sum(1 for s in signals if s.gap_down),
            "training_samples": len(train_df),
        }
    else:
        statistics = {
            "avg_probability": 0.0,
            "max_probability": 0.0,
            "min_probability": 0.0,
            "avg_z_score": 0.0,
            "gap_down_count": 0,
            "training_samples": len(train_df),
        }
    
    logger.info(
        "bouncehunter_scan_complete",
        signals_found=len(signals),
        avg_probability=statistics["avg_probability"],
    )
    
    return ScanResponse(
        scan_timestamp=datetime.utcnow().isoformat(),
        total_tickers_scanned=len(payload.tickers),
        signals_found=len(signals),
        signals=signals,
        statistics=statistics,
        cache_info=cache_info,
    )


class BacktestRequest(BaseModel):
    """Request to backtest BounceHunter strategy."""
    
    tickers: List[str] = Field(..., description="Tickers to backtest")
    start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")
    initial_capital: float = Field(100000.0, description="Starting capital", ge=1000)
    position_size: float = Field(0.1, description="Position size as fraction of capital", ge=0.01, le=1.0)


class BacktestResponse(BaseModel):
    """Backtest results."""
    
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    metrics: Dict[str, Any]


@router.post("/backtest", response_model=BacktestResponse)
def backtest_strategy(
    request: Request,
    payload: BacktestRequest = Body(...),
) -> BacktestResponse:
    """Run historical backtest of BounceHunter strategy.
    
    Simulates trading signals over historical period to evaluate performance.
    
    Args:
        payload: Backtest configuration with tickers and date range
        
    Returns:
        Performance metrics including returns, win rate, Sharpe ratio, drawdown
    """
    from src.bouncehunter import BounceHunterBacktester
    from datetime import datetime as dt
    
    logger.info(
        "bouncehunter_backtest_started",
        tickers_count=len(payload.tickers),
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    
    try:
        start = dt.fromisoformat(payload.start_date)
        end = dt.fromisoformat(payload.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {exc}")
    
    # Configure and run backtest
    config = BounceHunterConfig(tickers=payload.tickers)
    backtester = BounceHunterBacktester(config=config)
    
    with trace_operation("bouncehunter.backtest", attributes={"ticker_count": len(payload.tickers)}):
        try:
            result = backtester.run(
                start_date=start,
                end_date=end,
                initial_capital=payload.initial_capital,
                position_size=payload.position_size,
            )
        except Exception as exc:
            logger.error("bouncehunter_backtest_failed", error=str(exc), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")
    
    metrics = result.metrics
    
    logger.info(
        "bouncehunter_backtest_complete",
        total_trades=result.total_trades,
        win_rate=result.win_rate,
        total_return=result.total_return,
    )
    
    return BacktestResponse(
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        win_rate=result.win_rate,
        total_return=result.total_return,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        avg_win=metrics.avg_win,
        avg_loss=metrics.avg_loss,
        profit_factor=metrics.profit_factor,
        metrics=metrics.__dict__,
    )


@router.get("/cache/info")
def get_cache_info(request: Request) -> Dict[str, Any]:
    """Get information about model cache."""
    scanner = BounceHunter(use_cache=True)
    cache_info = scanner.get_cache_info()
    
    if cache_info is None:
        return {"cached": False, "reason": "Cache disabled"}
    
    return cache_info


@router.get("/cache/list")
def list_cached_models(request: Request) -> Dict[str, Any]:
    """List all cached models."""
    scanner = BounceHunter(use_cache=True)
    models = scanner.list_cached_models()
    
    return {
        "total_models": len(models),
        "models": models,
    }


@router.delete("/cache/clear")
def clear_cache(
    request: Request,
    older_than_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Clear cached models.
    
    Args:
        older_than_days: Only clear models older than this many days.
                         If not provided, clears all models.
    """
    scanner = BounceHunter(use_cache=True)
    cleared = scanner.clear_cache(older_than_days)
    
    return {
        "cleared": cleared,
        "message": f"Cleared {cleared} cached model(s)",
    }


class IncrementalTrainRequest(BaseModel):
    """Request for incremental training."""
    
    new_tickers: Optional[List[str]] = Field(
        None,
        description="New tickers to add. If None, refreshes existing tickers.",
    )


@router.post("/train/incremental")
def train_incremental(
    request: Request,
    payload: IncrementalTrainRequest = Body(...),
) -> Dict[str, Any]:
    """Incrementally update model with new data.
    
    This adds new tickers or refreshes existing ones without full retraining.
    """
    logger.info("bouncehunter_incremental_train_started", new_tickers=payload.new_tickers)
    
    try:
        scanner = BounceHunter(use_cache=True)
        train_df = scanner.fit_incremental(new_tickers=payload.new_tickers)
        cache_info = scanner.get_cache_info()
        
        logger.info(
            "bouncehunter_incremental_train_complete",
            training_samples=len(train_df),
        )
        
        return {
            "success": True,
            "training_samples": len(train_df),
            "cache_info": cache_info,
        }
        
    except Exception as exc:
        logger.error("bouncehunter_incremental_train_failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Incremental training failed: {exc}")

