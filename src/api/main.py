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

# Load environment variables from .env file (if present)
load_dotenv()

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def _check_required_api_keys() -> None:
    """Validate that critical API keys are present, raise on missing keys."""
    required_keys = {
        "GROQ_API_KEY": "Required for LLM-powered narrative analysis",
        "ETHERSCAN_API_KEY": "Required for contract verification and on-chain data",
    }
    
    missing = []
    for key, purpose in required_keys.items():
        if not os.environ.get(key):
            missing.append(f"{key} ({purpose})")
    
    if missing:
        error_msg = (
            "CRITICAL: Missing required API keys:\n" +
            "\n".join(f"  - {m}" for m in missing) +
            "\n\nSet these environment variables before starting the API."
        )
        raise ValueError(error_msg)


def _warn_optional_api_keys() -> None:
    """Log warnings for optional API keys that enhance functionality."""
    optional_keys = ["COINGECKO_API_KEY"]
    for key in optional_keys:
        if not os.environ.get(key):
            LOGGER.warning("%s not set - using free tier with rate limits", key)


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


@app.get("/")
@limiter.limit("60/minute")
def root(request: Request):
    return {"status": "ok", "message": "AutoTrader API is running"}


@app.get("/health")
@limiter.limit("120/minute")
def health_check(request: Request):
    """Health check endpoint - higher rate limit for monitoring."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}
