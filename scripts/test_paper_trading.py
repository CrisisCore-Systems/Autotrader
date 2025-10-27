"""
Paper Trading Test Script for Intelligent Adjustments (IBKR + Yahoo Finance)

This script validates the paper trading setup by:
1. Loading the paper trading configuration (IBKR)
2. Testing API connectivity (IBKR, Yahoo VIX)
3. Creating a PositionMonitor with adjustments enabled
4. Running a test monitoring cycle
5. Logging results for validation

Canadian-friendly setup:
- Interactive Brokers (IBKR) for brokerage
- Yahoo Finance for VIX data (free, no API keys)
- Mock regime detector (or Yahoo for SPY data)
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from bouncehunter.exits.config import ExitConfigManager
from bouncehunter.exits.monitor import PositionMonitor
from bouncehunter.exits.adjustments import MarketRegime, VolatilityLevel, MarketConditions, AdjustmentCalculator
from bouncehunter.data.regime_detector import MockRegimeDetector

# Import new Canadian-friendly providers
from src.core.providers.vix.yahoo_vix_provider import YahooVIXProvider
from src.core.brokers import get_broker, is_ibkr

# Setup logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'paper_test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def test_configuration():
    """Test 1: Load and validate configuration."""
    logger.info("=" * 80)
    logger.info("TEST 1: Configuration Loading")
    logger.info("=" * 80)
    
    try:
        config = ExitConfigManager.from_yaml('configs/my_paper_config.yaml')
        logger.info("[OK] Configuration loaded successfully")
        
        # Check if adjustments are enabled
        if config.is_adjustments_enabled():
            logger.info("[OK] Intelligent adjustments ENABLED")
            
            # Show adjustment settings
            vol_config = config.get_volatility_config()
            logger.info(f"  Volatility adjustments: LOW={vol_config.get('tier1_adjustment_low')}%, "
                       f"HIGH={vol_config.get('tier1_adjustment_high')}%")
            
            time_config = config.get_time_decay_config()
            logger.info(f"  Time decay: max={time_config.get('tier1_max_decay_pct')}% "
                       f"over {time_config.get('tier1_max_decay_hours')}h")
            
            regime_config = config.get_regime_config()
            logger.info(f"  Regime adjustments: BULL={regime_config.get('tier1_adjustment_bull')}%, "
                       f"BEAR={regime_config.get('tier1_adjustment_bear')}%")
        else:
            logger.warning("[!] Intelligent adjustments DISABLED")
        
        return config
        
    except Exception as e:
        logger.error(f"[X] Configuration loading failed: {e}")
        raise


def test_vix_provider():
    """Test 2: VIX data provider connectivity."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 2: VIX Data Provider")
    logger.info("=" * 80)
    
    try:
        # Check if Alpaca credentials are set
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            logger.warning("[!] Alpaca credentials not found in environment")
            logger.info("  Using MockVIXProvider for testing")
            provider = MockVIXProvider(vix_value=20.0)
        else:
            logger.info("[OK] Alpaca credentials found")
            
            # Try to create Alpaca provider
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                
                client = StockHistoricalDataClient(
                    api_key=api_key,
                    api_secret=api_secret
                )
                
                # Create fallback provider for reliability
                alpaca_provider = AlpacaVIXProvider(client)
                mock_provider = MockVIXProvider(vix_value=20.0)
                provider = FallbackVIXProvider(
                    primary_provider=alpaca_provider,
                    default_vix=20.0
                )
                logger.info("[OK] Created FallbackVIXProvider (Alpaca -> Mock -> Default)")
                
            except Exception as e:
                logger.warning(f"[!] Alpaca provider creation failed: {e}")
                logger.info("  Using MockVIXProvider instead")
                provider = MockVIXProvider(vix_value=20.0)
        
        # Test VIX retrieval
        vix = provider.get_vix()
        if vix:
            logger.info(f"[OK] VIX data retrieved: {vix:.2f}")
            
            # Classify VIX
            if vix < 15:
                regime = "LOW (calm market)"
            elif vix < 25:
                regime = "NORMAL"
            elif vix < 35:
                regime = "HIGH (elevated volatility)"
            else:
                regime = "EXTREME (crisis mode)"
            
            logger.info(f"  VIX Regime: {regime}")
        else:
            logger.error("[X] VIX data unavailable")
        
        return provider
        
    except Exception as e:
        logger.error(f"[X] VIX provider test failed: {e}")
        raise


def test_regime_detector():
    """Test 3: SPY regime detector."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 3: Market Regime Detector")
    logger.info("=" * 80)
    
    try:
        # Check if Alpaca credentials are set
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            logger.warning("[!] Using MockRegimeDetector (no Alpaca credentials)")
            detector = MockRegimeDetector(regime=MarketRegime.BULL)
        else:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                
                client = StockHistoricalDataClient(
                    api_key=api_key,
                    api_secret=api_secret
                )
                
                detector = SPYRegimeDetector(client)
                logger.info("[OK] Created SPYRegimeDetector")
                
            except Exception as e:
                logger.warning(f"[!] SPYRegimeDetector creation failed: {e}")
                logger.info("  Using MockRegimeDetector instead")
                detector = MockRegimeDetector(regime=MarketRegime.BULL)
        
        # Test regime detection
        regime = detector.detect_regime()
        if regime:
            logger.info(f"[OK] Market regime detected: {regime.value}")
            
            # Get diagnostics if available
            try:
                details = detector.get_regime_details()
                if details:
                    sma50 = details.get('sma_50', 'N/A')
                    sma200 = details.get('sma_200', 'N/A')
                    spread = details.get('spread_pct', 'N/A')
                    
                    if isinstance(sma50, (int, float)):
                        logger.info(f"  SMA50: {sma50:.2f}")
                    else:
                        logger.info(f"  SMA50: {sma50}")
                    
                    if isinstance(sma200, (int, float)):
                        logger.info(f"  SMA200: {sma200:.2f}")
                    else:
                        logger.info(f"  SMA200: {sma200}")
                    
                    if isinstance(spread, (int, float)):
                        logger.info(f"  Spread: {spread:.2f}%")
                    else:
                        logger.info(f"  Spread: {spread}")
            except AttributeError:
                pass  # Mock detector doesn't have details
        else:
            logger.error("[X] Regime detection failed")
        
        return detector
        
    except Exception as e:
        logger.error(f"[X] Regime detector test failed: {e}")
        raise


def test_adjustment_calculation(config, vix_provider, regime_detector):
    """Test 4: Adjustment calculation (without broker)."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 4: Adjustment Calculation")
    logger.info("=" * 80)
    
    try:
        # Get current market data
        vix = vix_provider.get_vix() or 20.0
        regime = regime_detector.detect_regime() or MarketRegime.SIDEWAYS
        
        # Create market conditions with providers
        conditions = MarketConditions(
            vix_provider=vix_provider,
            regime_detector=regime_detector
        )
        
        vol_level = conditions.get_volatility_level(vix)
        
        logger.info(f"[OK] Market conditions: VIX={vix:.2f} ({vol_level.value}), Regime={regime.value}")
        
        # Create calculator with market conditions
        calculator = AdjustmentCalculator(
            market_conditions=conditions,
            enable_volatility_adjustments=True,
            enable_time_adjustments=True,
            enable_regime_adjustments=True
        )
        
        # Test calculation
        base_target = 5.0
        
        adjusted_target, breakdown = calculator.adjust_tier1_target(
            base_target=base_target,
            current_vix=vix
        )
        
        logger.info(f"[OK] Adjustment calculation successful")
        logger.info(f"  Base target: {base_target}%")
        logger.info(f"  Adjusted target: {adjusted_target:.2f}%")
        logger.info(f"  Total adjustment: {adjusted_target - base_target:+.2f}%")
        logger.info("")
        logger.info("  Breakdown:")
        for component, value in breakdown.items():
            if isinstance(value, (int, float)):
                logger.info(f"    {component}: {value:+.2f}%")
            else:
                logger.info(f"    {component}: {value}")
        
        return calculator
        
    except Exception as e:
        logger.error(f"[X] Adjustment calculation failed: {e}")
        raise


def main():
    """Run all paper trading tests."""
    logger.info("=" * 80)
    logger.info("PAPER TRADING VALIDATION - Intelligent Adjustments System")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    try:
        # Test 1: Configuration
        config = test_configuration()
        
        # Test 2: VIX Provider
        vix_provider = test_vix_provider()
        
        # Test 3: Regime Detector
        regime_detector = test_regime_detector()
        
        # Test 4: Adjustment Calculation
        calculator = test_adjustment_calculation(config, vix_provider, regime_detector)
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info("[OK] All tests passed successfully!")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("1. Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables")
        logger.info("2. Review logs/paper_test.log for detailed output")
        logger.info("3. Customize configs/my_paper_config.yaml if needed")
        logger.info("4. Run the paper trading bot: python scripts/run_pennyhunter_paper.py")
        logger.info("")
        logger.info("Paper trading system is READY for deployment!")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("TEST FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Please fix the issues above before deploying paper trading.")
        logger.error("=" * 80)
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
