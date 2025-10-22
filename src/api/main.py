"""Entry point for the lightweight AutoTrader scanner API."""

from __future__ import annotations

import logging
import os
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

# Load environment variables from .env file (if present)
load_dotenv()

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tokens_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(experiments_router, prefix="/api")


@app.get("/")
@limiter.limit("60/minute")
def root(request: Request):
    return {"status": "ok", "message": "AutoTrader API is running"}


@app.get("/health")
@limiter.limit("120/minute")
def health_check(request: Request):
    """Health check endpoint - higher rate limit for monitoring."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}
