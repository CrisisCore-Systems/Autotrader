"""FastAPI endpoints for microstructure detection alerts and monitoring."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import asdict
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

from src.core.logging_config import get_logger
from src.microstructure.detector import DetectionSignal

logger = get_logger(__name__)

# ============================================================================
# Prometheus Metrics
# ============================================================================

# Counters
signal_counter = Counter(
    "microstructure_signals_total",
    "Total number of detection signals",
    ["signal_type", "symbol"],
)

alert_counter = Counter(
    "microstructure_alerts_sent_total",
    "Total number of alerts sent",
    ["channel", "status"],
)

# Gauges
active_signals_gauge = Gauge(
    "microstructure_active_signals",
    "Number of currently active signals",
    ["signal_type"],
)

detection_score_gauge = Gauge(
    "microstructure_detection_score",
    "Latest detection score",
    ["symbol", "signal_type"],
)

# Histograms
signal_processing_time = Histogram(
    "microstructure_signal_processing_seconds",
    "Time to process and emit signal",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

alert_latency = Histogram(
    "microstructure_alert_latency_seconds",
    "Time from signal to alert delivery",
    ["channel"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)


# ============================================================================
# Pydantic Models
# ============================================================================


class SignalRequest(BaseModel):
    """Request model for signal submission."""

    timestamp: float = Field(..., description="Unix timestamp of signal")
    signal_type: str = Field(..., description="Type: buy_imbalance or sell_imbalance")
    score: float = Field(..., ge=0.0, le=1.0, description="Detection score [0-1]")
    symbol: str = Field(default="BTC/USDT", description="Trading symbol")
    features: Dict = Field(default_factory=dict, description="Feature values")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class SignalResponse(BaseModel):
    """Response model for signal operations."""

    signal_id: str
    status: str
    message: str
    timestamp: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    uptime_seconds: float
    signals_received: int
    alerts_sent: int


class MetricsResponse(BaseModel):
    """Metrics summary response."""

    total_signals: int
    active_signals: int
    signals_by_type: Dict[str, int]
    avg_score: float
    alerts_sent: int


# ============================================================================
# Signal Store
# ============================================================================


class SignalStore:
    """In-memory store for recent signals."""

    def __init__(self, max_size: int = 1000):
        """Initialize signal store."""
        self.max_size = max_size
        self.signals: deque = deque(maxlen=max_size)
        self.signals_by_type: Dict[str, int] = defaultdict(int)
        self.total_signals = 0
        self.start_time = time.time()

    def add_signal(self, signal: DetectionSignal) -> None:
        """Add a signal to the store."""
        self.signals.append(signal)
        self.signals_by_type[signal.signal_type] += 1
        self.total_signals += 1

        # Update metrics
        signal_counter.labels(
            signal_type=signal.signal_type,
            symbol=signal.metadata.get("symbol", "unknown"),
        ).inc()

        detection_score_gauge.labels(
            symbol=signal.metadata.get("symbol", "unknown"),
            signal_type=signal.signal_type,
        ).set(signal.score)

    def get_recent_signals(self, limit: int = 10) -> List[DetectionSignal]:
        """Get most recent signals."""
        return list(self.signals)[-limit:]

    def get_stats(self) -> Dict:
        """Get store statistics."""
        return {
            "total_signals": self.total_signals,
            "active_signals": len(self.signals),
            "signals_by_type": dict(self.signals_by_type),
            "avg_score": (
                sum(s.score for s in self.signals) / len(self.signals)
                if self.signals
                else 0.0
            ),
            "uptime_seconds": time.time() - self.start_time,
        }


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Microstructure Detection API",
    description="Real-time orderflow detection alerts and monitoring",
    version="1.0.0",
)

# Global signal store
signal_store = SignalStore(max_size=1000)


@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    return {
        "service": "Microstructure Detection API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    stats = signal_store.get_stats()

    return HealthResponse(
        status="healthy",
        uptime_seconds=stats["uptime_seconds"],
        signals_received=stats["total_signals"],
        alerts_sent=0,  # TODO: Track from alerting module
    )


@app.post("/api/v1/signals", response_model=SignalResponse)
async def submit_signal(
    signal_request: SignalRequest,
    background_tasks: BackgroundTasks,
):
    """
    Submit a detection signal.

    This endpoint receives detection signals from the microstructure detector
    and can trigger alerts to configured channels.
    """
    start_time = time.time()

    try:
        # Generate signal ID
        signal_id = f"api_{int(time.time() * 1000000)}"
        
        # Create detection signal
        signal = DetectionSignal(
            timestamp=signal_request.timestamp,
            signal_type=signal_request.signal_type,
            score=signal_request.score,
            features=signal_request.features,
            cooldown_until=signal_request.timestamp + 60.0,  # 60s cooldown
            metadata={
                **signal_request.metadata,
                "signal_id": signal_id,
                "symbol": signal_request.symbol,
                "source": "api",
            },
        )

        # Store signal
        signal_store.add_signal(signal)

        # Update active signals gauge
        active_buy = sum(
            1 for s in signal_store.signals if s.signal_type == "buy_imbalance"
        )
        active_sell = sum(
            1 for s in signal_store.signals if s.signal_type == "sell_imbalance"
        )

        active_signals_gauge.labels(signal_type="buy_imbalance").set(active_buy)
        active_signals_gauge.labels(signal_type="sell_imbalance").set(active_sell)

        # Record processing time
        processing_time = time.time() - start_time
        signal_processing_time.observe(processing_time)

        # TODO: Trigger alerts in background
        # background_tasks.add_task(send_alerts, signal)

        logger.info(
            "signal_received",
            signal_id=signal_id,
            signal_type=signal.signal_type,
            score=signal.score,
            processing_time_ms=processing_time * 1000,
        )

        return SignalResponse(
            signal_id=signal_id,
            status="accepted",
            message="Signal received and stored",
            timestamp=time.time(),
        )

    except Exception as e:
        logger.error("signal_submission_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process signal: {e}")


@app.get("/api/v1/signals", response_model=List[dict])
async def get_signals(limit: int = 10):
    """
    Get recent detection signals.

    Args:
        limit: Maximum number of signals to return (default 10)
    """
    try:
        signals = signal_store.get_recent_signals(limit=limit)

        return [
            {
                "signal_id": s.metadata.get("signal_id", "unknown"),
                "timestamp": s.timestamp,
                "signal_type": s.signal_type,
                "score": s.score,
                "symbol": s.metadata.get("symbol", "unknown"),
            }
            for s in signals
        ]

    except Exception as e:
        logger.error("get_signals_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch signals: {e}")


@app.get("/api/v1/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get detection metrics summary."""
    try:
        stats = signal_store.get_stats()

        return MetricsResponse(
            total_signals=stats["total_signals"],
            active_signals=stats["active_signals"],
            signals_by_type=stats["signals_by_type"],
            avg_score=stats["avg_score"],
            alerts_sent=0,  # TODO: Track from alerting
        )

    except Exception as e:
        logger.error("get_metrics_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {e}")


@app.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    """
    try:
        metrics_output = generate_latest()
        return Response(
            content=metrics_output,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    except Exception as e:
        logger.error("prometheus_metrics_failed", error=str(e), exc_info=True)
        return Response(
            content=f"# Error generating metrics: {e}",
            media_type="text/plain",
            status_code=500,
        )


# ============================================================================
# Startup/Shutdown Handlers
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info(
        "api_server_started",
        service="microstructure_detection_api",
        version="1.0.0",
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    stats = signal_store.get_stats()

    logger.info(
        "api_server_stopped",
        total_signals_processed=stats["total_signals"],
        uptime_seconds=stats["uptime_seconds"],
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.microstructure.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
