"""Example strategy plugin stub for AutoTrader.

This file demonstrates how to create a custom strategy plugin that integrates
with the AutoTrader CLI plugin system.

Usage:
    1. Copy this file to your project
    2. Implement your custom logic in the analyze() method
    3. Register in pyproject.toml:
    
        [project.entry-points."autotrader.strategies"]
        my_strategy = "my_package.strategies:MyStrategy"
    
    4. Install: pip install -e .
    5. Use: autotrader-scan --strategy my_strategy --config config.yaml
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenData:
    """Token data input structure.
    
    This is the data structure passed to your strategy's analyze() method.
    """
    symbol: str
    name: Optional[str] = None
    contract_address: Optional[str] = None
    
    # Price data
    current_price: Optional[float] = None
    price_change_24h: Optional[float] = None
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    
    # Social metrics
    twitter_followers: Optional[int] = None
    twitter_mentions_24h: Optional[int] = None
    reddit_subscribers: Optional[int] = None
    
    # On-chain data
    holder_count: Optional[int] = None
    transaction_count_24h: Optional[int] = None
    liquidity_usd: Optional[float] = None
    
    # Narratives and events
    narratives: List[str] = None
    upcoming_unlocks: List[Dict[str, Any]] = None
    
    # Metadata
    timestamp: Optional[datetime] = None
    data_sources: List[str] = None


@dataclass
class StrategyResult:
    """Strategy analysis result structure.
    
    This is what your strategy's analyze() method should return.
    """
    # Core metrics
    gem_score: float  # 0-100, higher is better
    risk_score: float  # 0-100, higher is riskier
    confidence: float  # 0-100, how confident in the analysis
    
    # Recommendation
    recommendation: str  # "BUY", "HOLD", "SELL", "SKIP"
    
    # Signals detected
    signals: List[str]  # e.g., ["high_social_momentum", "liquidity_spike"]
    
    # Breakdown by category
    sentiment_score: Optional[float] = None
    technical_score: Optional[float] = None
    fundamental_score: Optional[float] = None
    
    # Supporting data
    reasoning: Optional[str] = None
    warnings: List[str] = None
    
    # Metadata
    strategy_name: str = "example_strategy"
    strategy_version: str = "1.0.0"
    analysis_timestamp: Optional[datetime] = None


class ExampleStrategy:
    """Example strategy implementation.
    
    This is a template showing the required interface for a strategy plugin.
    Replace this with your actual strategy logic.
    
    Required Interface:
    ------------------
    - STRATEGY_API_VERSION: str (class attribute)
        API version this strategy is compatible with (e.g., "1.0")
        REQUIRED as of AutoTrader v2.0 to prevent API drift
    
    - __init__(config: Dict[str, Any]) -> None
        Initialize strategy with configuration
    
    - analyze(token_data: Dict[str, Any]) -> Dict[str, Any]
        Analyze token and return results
    
    Optional Interface:
    ------------------
    - validate_config(config: Dict[str, Any]) -> bool
        Validate configuration (called before __init__)
    
    - get_required_data_sources() -> List[str]
        Return list of required data sources
    
    - warm_up() -> None
        Perform any warm-up/initialization tasks
    """
    
    # REQUIRED: Declare API version for compatibility checking
    # Core will reject strategies with mismatched MAJOR version
    STRATEGY_API_VERSION = "1.0"
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize strategy with configuration.
        
        Args:
            config: Configuration dictionary from YAML file
                    Contains all settings from your config.yaml
        
        Example config.yaml:
            strategy: my_strategy
            my_strategy_settings:
                min_liquidity: 100000
                max_risk_score: 70
                enable_sentiment: true
        """
        self.config = config
        
        # Extract strategy-specific settings
        strategy_settings = config.get("my_strategy_settings", {})
        self.min_liquidity = strategy_settings.get("min_liquidity", 50000)
        self.max_risk_score = strategy_settings.get("max_risk_score", 75)
        self.enable_sentiment = strategy_settings.get("enable_sentiment", True)
        
        # Initialize any models, caches, etc.
        self._cache = {}
        
        logger.info(f"Initialized ExampleStrategy with min_liquidity={self.min_liquidity}")
    
    def analyze(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze token and return results.
        
        This is the main method called by the AutoTrader CLI for each token.
        
        Args:
            token_data: Dictionary containing token information:
                - symbol: Token symbol (str)
                - name: Token name (str)
                - contract_address: Contract address (str)
                - price_data: Price information (dict)
                - social_metrics: Social media metrics (dict)
                - on_chain_data: On-chain data (dict)
                - narratives: List of narratives (list)
                - unlocks: Upcoming unlocks (list)
        
        Returns:
            Dictionary containing analysis results:
                - gem_score: Overall score 0-100 (float)
                - risk_score: Risk assessment 0-100 (float)
                - confidence: Confidence level 0-100 (float)
                - recommendation: "BUY", "HOLD", "SELL", or "SKIP" (str)
                - signals: List of detected signals (list)
                - sentiment_score: Sentiment analysis score (float, optional)
                - technical_score: Technical analysis score (float, optional)
                - fundamental_score: Fundamental analysis score (float, optional)
                - reasoning: Human-readable explanation (str, optional)
                - warnings: List of warnings (list, optional)
                - metadata: Strategy metadata (dict)
        """
        logger.info(f"Analyzing token: {token_data.get('symbol', 'UNKNOWN')}")
        
        # Extract data
        symbol = token_data.get("symbol", "UNKNOWN")
        price_data = token_data.get("price_data", {})
        social_metrics = token_data.get("social_metrics", {})
        on_chain_data = token_data.get("on_chain_data", {})
        narratives = token_data.get("narratives", [])
        
        # Example: Extract specific metrics
        liquidity = on_chain_data.get("liquidity_usd", 0)
        volume_24h = price_data.get("volume_24h", 0)
        twitter_mentions = social_metrics.get("twitter_mentions_24h", 0)
        
        # Initialize scores
        gem_score = 0.0
        risk_score = 50.0  # Start at medium risk
        confidence = 50.0
        signals = []
        warnings = []
        
        # -----------------------------------------------------------------
        # IMPLEMENT YOUR STRATEGY LOGIC HERE
        # -----------------------------------------------------------------
        
        # Example: Check liquidity
        if liquidity < self.min_liquidity:
            warnings.append(f"Low liquidity: ${liquidity:,.0f} < ${self.min_liquidity:,.0f}")
            risk_score += 20
            gem_score -= 10
        else:
            signals.append("sufficient_liquidity")
            gem_score += 10
        
        # Example: Check social momentum
        if self.enable_sentiment and twitter_mentions > 100:
            signals.append("high_social_momentum")
            gem_score += 15
            confidence += 10
        
        # Example: Volume analysis
        volume_to_mcap = volume_24h / price_data.get("market_cap", 1)
        if volume_to_mcap > 0.1:  # 10% volume/mcap ratio
            signals.append("high_volume_ratio")
            gem_score += 10
        
        # Example: Narrative boost
        if narratives and len(narratives) > 0:
            signals.append("strong_narratives")
            gem_score += 5 * len(narratives)
            confidence += 10
        
        # Clamp scores to 0-100
        gem_score = max(0.0, min(100.0, gem_score))
        risk_score = max(0.0, min(100.0, risk_score))
        confidence = max(0.0, min(100.0, confidence))
        
        # Determine recommendation
        if risk_score > self.max_risk_score:
            recommendation = "SKIP"
            warnings.append(f"Risk too high: {risk_score:.1f} > {self.max_risk_score}")
        elif gem_score >= 70:
            recommendation = "BUY"
        elif gem_score >= 50:
            recommendation = "HOLD"
        else:
            recommendation = "SKIP"
        
        # -----------------------------------------------------------------
        # END STRATEGY LOGIC
        # -----------------------------------------------------------------
        
        # Build result
        result = {
            "gem_score": round(gem_score, 2),
            "risk_score": round(risk_score, 2),
            "confidence": round(confidence, 2),
            "recommendation": recommendation,
            "signals": signals,
            "warnings": warnings,
            "reasoning": self._generate_reasoning(
                gem_score, risk_score, signals, warnings
            ),
            "metadata": {
                "strategy": "example_strategy",
                "version": "1.0.0",
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
        
        logger.info(
            f"Analysis complete for {symbol}: "
            f"gem_score={gem_score:.1f}, "
            f"recommendation={recommendation}"
        )
        
        return result
    
    def _generate_reasoning(
        self,
        gem_score: float,
        risk_score: float,
        signals: List[str],
        warnings: List[str]
    ) -> str:
        """Generate human-readable reasoning for the analysis.
        
        Args:
            gem_score: Gem score
            risk_score: Risk score
            signals: Detected signals
            warnings: Warnings
        
        Returns:
            Reasoning text
        """
        parts = []
        
        parts.append(f"Gem Score: {gem_score:.1f}/100")
        parts.append(f"Risk Score: {risk_score:.1f}/100")
        
        if signals:
            parts.append(f"Signals: {', '.join(signals)}")
        
        if warnings:
            parts.append(f"Warnings: {'; '.join(warnings)}")
        
        return " | ".join(parts)
    
    # -----------------------------------------------------------------
    # OPTIONAL METHODS
    # -----------------------------------------------------------------
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """Validate configuration before initialization.
        
        This is called before __init__ to check if the config is valid.
        
        Args:
            config: Configuration dictionary
        
        Returns:
            True if config is valid, False otherwise
        """
        # Example: Check required keys
        required_keys = ["scanner"]
        for key in required_keys:
            if key not in config:
                logger.error(f"Missing required config key: {key}")
                return False
        
        return True
    
    def get_required_data_sources(self) -> List[str]:
        """Return list of required data sources.
        
        Returns:
            List of required data source names
        """
        return [
            "price_data",
            "social_metrics",
            "on_chain_data",
        ]
    
    def warm_up(self) -> None:
        """Perform any warm-up/initialization tasks.
        
        This is called once after initialization, before the first analyze() call.
        Use this to:
        - Pre-load models
        - Initialize caches
        - Warm up API connections
        - etc.
        """
        logger.info("Warming up ExampleStrategy...")
        # Example: Pre-populate cache
        self._cache = {"warm": True}
        logger.info("Warm-up complete")


# -----------------------------------------------------------------
# ADVANCED: MULTI-STRATEGY ENSEMBLE
# -----------------------------------------------------------------

class EnsembleStrategy:
    """Example ensemble strategy combining multiple sub-strategies.
    
    This shows how to combine multiple strategies into one.
    """
    
    # REQUIRED: API version
    STRATEGY_API_VERSION = "1.0"
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize ensemble with sub-strategies."""
        self.config = config
        
        # Initialize sub-strategies
        self.strategies = [
            ExampleStrategy(config),
            # Add more strategies here
        ]
        
        # Weights for each strategy (must sum to 1.0)
        self.weights = [1.0]  # Adjust if multiple strategies
    
    def analyze(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze using ensemble of strategies."""
        results = []
        
        # Run each strategy
        for strategy in self.strategies:
            result = strategy.analyze(token_data)
            results.append(result)
        
        # Combine results (weighted average)
        gem_score = sum(
            r["gem_score"] * w for r, w in zip(results, self.weights)
        )
        risk_score = sum(
            r["risk_score"] * w for r, w in zip(results, self.weights)
        )
        
        # Combine signals
        all_signals = []
        for r in results:
            all_signals.extend(r["signals"])
        
        return {
            "gem_score": round(gem_score, 2),
            "risk_score": round(risk_score, 2),
            "confidence": 75.0,
            "recommendation": "BUY" if gem_score >= 70 else "HOLD",
            "signals": list(set(all_signals)),  # Unique signals
            "metadata": {
                "strategy": "ensemble",
                "version": "1.0.0",
                "sub_strategies": len(self.strategies),
            }
        }


# -----------------------------------------------------------------
# REGISTRATION
# -----------------------------------------------------------------

# If using entry points (recommended):
# Add to pyproject.toml:
#
# [project.entry-points."autotrader.strategies"]
# example = "examples.example_strategy_plugin:ExampleStrategy"
# ensemble = "examples.example_strategy_plugin:EnsembleStrategy"
#
# Then: pip install -e .
# Use: autotrader-scan --strategy example --config config.yaml


# -----------------------------------------------------------------
# TESTING
# -----------------------------------------------------------------

def test_strategy():
    """Test the strategy with sample data."""
    # Sample config
    config = {
        "scanner": {"liquidity_threshold": 75000},
        "my_strategy_settings": {
            "min_liquidity": 50000,
            "max_risk_score": 75,
            "enable_sentiment": True,
        }
    }
    
    # Sample token data
    token_data = {
        "symbol": "TEST",
        "name": "Test Token",
        "contract_address": "0x1234...",
        "price_data": {
            "current_price": 1.23,
            "price_change_24h": 5.6,
            "market_cap": 1000000,
            "volume_24h": 150000,
        },
        "social_metrics": {
            "twitter_followers": 5000,
            "twitter_mentions_24h": 150,
        },
        "on_chain_data": {
            "liquidity_usd": 250000,
            "holder_count": 1234,
            "transaction_count_24h": 456,
        },
        "narratives": ["DeFi 2.0", "Cross-chain"],
        "unlocks": [],
    }
    
    # Initialize and run
    strategy = ExampleStrategy(config)
    result = strategy.analyze(token_data)
    
    # Print results
    print("\n" + "="*60)
    print("STRATEGY TEST RESULTS")
    print("="*60)
    print(f"Token: {token_data['symbol']}")
    print(f"Gem Score: {result['gem_score']:.1f}/100")
    print(f"Risk Score: {result['risk_score']:.1f}/100")
    print(f"Confidence: {result['confidence']:.1f}/100")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Signals: {', '.join(result['signals'])}")
    if result.get('warnings'):
        print(f"Warnings: {'; '.join(result['warnings'])}")
    print(f"Reasoning: {result['reasoning']}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run test when executed directly
    logging.basicConfig(level=logging.INFO)
    test_strategy()
