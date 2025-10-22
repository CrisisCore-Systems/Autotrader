"""
Broker Factory - Multi-Broker Support for Canadian Trading

Supports multiple brokers with unified interface:
- Interactive Brokers (IBKR) - Primary for Canadian markets
- Alpaca (legacy) - US markets only
- Mock broker - Testing

Environment variables:
    BROKER_NAME: "ibkr", "alpaca", or "mock" (default: ibkr)
    
IBKR-specific:
    IBKR_HOST: TWS/Gateway host (default: 127.0.0.1)
    IBKR_PORT: TWS/Gateway port (default: 7497)
    IBKR_CLIENT_ID: Client ID (default: 42)
    USE_PAPER: "1" for paper trading (default: 1)
    
Alpaca-specific (legacy):
    ALPACA_API_KEY: API key
    ALPACA_API_SECRET: API secret
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_broker(config: Optional[Dict[str, Any]] = None):
    """Get broker client based on configuration.
    
    Args:
        config: Configuration dict with broker settings
                If None, uses environment variables
                
    Returns:
        Broker client instance (IBKRClient, AlpacaClient, or MockBroker)
        
    Examples:
        # From config file
        >>> config = yaml.safe_load(open("config.yaml"))
        >>> broker = get_broker(config)
        
        # From environment
        >>> os.environ["BROKER_NAME"] = "ibkr"
        >>> broker = get_broker()
    """
    # Determine broker name
    if config and "broker" in config:
        broker_name = config["broker"].get("name", "ibkr").lower()
        broker_config = config["broker"]
    else:
        broker_name = os.getenv("BROKER_NAME", "ibkr").lower()
        broker_config = {}
    
    logger.info(f"Initializing broker: {broker_name}")
    
    # IBKR (Primary for Canadian markets)
    if broker_name == "ibkr":
        from .ibkr_client import IBKRClient
        
        return IBKRClient(
            host=broker_config.get("host") or os.getenv("IBKR_HOST"),
            port=broker_config.get("port") or os.getenv("IBKR_PORT"),
            client_id=broker_config.get("client_id") or os.getenv("IBKR_CLIENT_ID"),
            paper=broker_config.get("paper", True) or os.getenv("USE_PAPER", "1") == "1"
        )
    
    # Alpaca (Legacy - US markets only)
    elif broker_name == "alpaca":
        logger.warning("Alpaca is legacy for US markets only. Consider IBKR for Canadian trading.")
        
        try:
            from alpaca_trade_api import REST
            
            api_key = broker_config.get("api_key") or os.getenv("ALPACA_API_KEY")
            api_secret = broker_config.get("api_secret") or os.getenv("ALPACA_API_SECRET")
            paper = broker_config.get("paper", True)
            
            if not api_key or not api_secret:
                raise ValueError("Alpaca API credentials not found in config or environment")
            
            base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
            
            return REST(api_key, api_secret, base_url)
        
        except ImportError:
            raise ImportError("Alpaca SDK not installed. Run: pip install alpaca-trade-api")
    
    # Mock (Testing)
    elif broker_name == "mock":
        logger.info("Using mock broker for testing")
        from .mock_broker import MockBroker
        return MockBroker()
    
    else:
        raise ValueError(
            f"Unsupported broker: {broker_name}. "
            f"Supported brokers: ibkr, alpaca (legacy), mock"
        )


def get_broker_type() -> str:
    """Get configured broker type from environment.
    
    Returns:
        Broker name: "ibkr", "alpaca", or "mock"
    """
    return os.getenv("BROKER_NAME", "ibkr").lower()


def is_ibkr() -> bool:
    """Check if using IBKR broker.
    
    Returns:
        True if BROKER_NAME is ibkr or not set (default)
    """
    return get_broker_type() == "ibkr"


def is_alpaca() -> bool:
    """Check if using Alpaca broker (legacy).
    
    Returns:
        True if BROKER_NAME is alpaca
    """
    return get_broker_type() == "alpaca"


def is_paper_trading() -> bool:
    """Check if paper trading mode is enabled.
    
    Returns:
        True if USE_PAPER environment variable is "1"
    """
    return os.getenv("USE_PAPER", "1") == "1"


__all__ = [
    "get_broker",
    "get_broker_type",
    "is_ibkr",
    "is_alpaca",
    "is_paper_trading"
]
