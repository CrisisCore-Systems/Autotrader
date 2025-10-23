"""Entry point for the lightweight AutoTrader scanner API."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .routes.tokens import router as tokens_router
from .routes.health import router as health_router
from .routes.experiments import router as experiments_router
from .routes.monitoring import router as monitoring_router

# Import observability components
from src.core.logging_config import setup_structured_logging, get_logger
from src.core.metrics import (
    record_api_request,
    record_api_duration,
    record_api_error,
    ActiveRequestTracker,
)
from src.core.tracing import setup_tracing, instrument_fastapi, get_trace_id

# Load environment variables from .env file (if present)
load_dotenv()

# Initialize structured logging
structured_logger = setup_structured_logging(
    service_name="autotrader-api",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
LOGGER = get_logger(__name__)

# Initialize tracing
setup_tracing(service_name="autotrader-api")


def _check_required_api_keys() -> None:
    """Warn when critical API keys are missing so the app can degrade gracefully."""
    required_keys = {
        "GROQ_API_KEY": (
            "LLM-powered narrative analysis is disabled until this key is provided."
        ),
        "ETHERSCAN_API_KEY": (
            "Smart contract verification and on-chain data lookups are unavailable "
            "without this key."
        ),
    }

    for key, guidance in required_keys.items():
        if not os.environ.get(key):
            LOGGER.warning("%s is not set. %s", key, guidance)


def _warn_optional_api_keys() -> None:
    """Log warnings for optional API keys that enhance functionality."""
    optional_keys = {
        "COINGECKO_API_KEY": (
            "Falling back to the public CoinGecko endpoints which have stricter rate "
            "limits."
        ),
    }
    for key, guidance in optional_keys.items():
        if not os.environ.get(key):
            LOGGER.warning("%s is not set. %s", key, guidance)


_check_required_api_keys()
_warn_optional_api_keys()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="AutoTrader API", version="1.0.0")

# Add rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)


# Add request logging and metrics middleware
@app.middleware("http")
async def logging_and_metrics_middleware(request: Request, call_next):
    """Middleware for structured logging and metrics collection."""
    start_time = time.time()
    method = request.method
    path = request.url.path
    
    # Get trace ID for correlation
    trace_id = get_trace_id()
    
    # Bind context to logger
    request_logger = LOGGER.bind(
        request_id=trace_id or f"{start_time}",
        method=method,
        path=path,
        client_ip=get_remote_address(request),
    )
    
    request_logger.info(
        "api_request_started",
        query_params=dict(request.query_params),
    )
    
    # Track active requests
    with ActiveRequestTracker(method, path):
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            status_code = response.status_code
            
            # Record metrics
            record_api_request(method, path, status_code)
            record_api_duration(method, path, duration)
            
            request_logger.info(
                "api_request_completed",
                status_code=status_code,
                duration_seconds=duration,
            )
            
            # Add trace ID to response headers
            if trace_id:
                response.headers["X-Trace-Id"] = trace_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            
            # Record error metrics
            record_api_error(method, path, error_type)
            record_api_duration(method, path, duration)
            
            request_logger.error(
                "api_request_failed",
                error_type=error_type,
                error_message=str(e),
                duration_seconds=duration,
                exc_info=e,
            )
            raise

app.include_router(tokens_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(experiments_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")


@app.get("/")
@limiter.limit("60/minute")
def root(request: Request):
    return {"status": "ok", "message": "AutoTrader API is running"}


@app.get("/health")
@limiter.limit("120/minute")
def health_check(request: Request):
    """Health check endpoint - higher rate limit for monitoring."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}
