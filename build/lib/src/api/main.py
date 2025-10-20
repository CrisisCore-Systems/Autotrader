"""Entry point for the lightweight VoidBloom scanner API."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.tokens import router as tokens_router

# Load environment variables from .env file (if present)
load_dotenv()

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def _warn_missing_api_keys() -> None:
    """Log warnings for missing upstream API keys."""
    for key in ("GROQ_API_KEY", "ETHERSCAN_API_KEY", "COINGECKO_API_KEY"):
        if not os.environ.get(key):
            LOGGER.warning("%s not set in environment variables", key)


_warn_missing_api_keys()

app = FastAPI(title="VoidBloom API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tokens_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "message": "VoidBloom API is running"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}
