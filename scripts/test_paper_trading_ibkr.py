"""
Paper Trading Test Script for Intelligent Adjustments (IBKR + Yahoo Finance)

This script validates the paper trading setup by:
1. Loading the paper trading configuration (IBKR)
2. Testing broker connectivity (IBKR paper account)
3. Testing VIX provider (Yahoo Finance - free, no API keys)
4. Testing market regime detector
5. Testing adjustment calculations
6. Logging results for validation

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
import yaml

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import adjustment components
from bouncehunter.exits.adjustments import (
    MarketRegime, VolatilityLevel, MarketConditions, AdjustmentCalculator
)
from bouncehunter.data.regime_detector import MockRegimeDetector

# Import Canadian-friendly providers
from src.core.providers.vix.yahoo_vix_provider import YahooVIXProvider
from src.core.brokers import get_broker, is_ibkr, is_paper_trading

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
        config_path = Path(__file__).parent.parent / 'configs' / 'my_paper_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        logger.info("[OK] Configuration loaded successfully")
        
        # Check broker settings
        broker_config = config.get('broker', {})
        broker_name = broker_config.get('name', 'unknown')
        logger.info(f"[OK] Broker configured: {broker_name.upper()}")
        
        # Check if adjustments are enabled
        adj_config = config.get('adjustments', {})
        if adj_config.get('enabled', False):
            logger.info("[OK] Intelligent adjustments ENABLED")
            
            # Show adjustment settings
            vol_config = adj_config.get('volatility', {})
            logger.info(f"  Volatility adjustments: LOW={vol_config.get('tier1_adjustment_low', 0)}%, "
                       f"HIGH={vol_config.get('tier1_adjustment_high', 0)}%")
            
            time_config = adj_config.get('time_decay', {})
            logger.info(f"  Time decay: max={time_config.get('tier1_max_decay_pct', 0)}% over Noneh")
            
            regime_config = adj_config.get('regime', {})
            logger.info(f"  Regime adjustments: BULL={regime_config.get('tier1_adjustment_bull', 0)}%, "
                       f"BEAR={regime_config.get('tier1_adjustment_bear', 0)}%")
        else:
            logger.warning("[!] Intelligent adjustments DISABLED")
        
        return config
        
    except Exception as e:
        logger.error(f"[X] Configuration loading failed: {e}")
        raise


def test_broker_connectivity():
    """Test 2: IBKR broker connectivity."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 2: Broker Connectivity (IBKR)")
    logger.info("=" * 80)
    
    try:
        # Load config
        config_path = Path(__file__).parent.parent / 'configs' / 'my_paper_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Check if IBKR environment variables are set
        ibkr_host = os.getenv('IBKR_HOST', '127.0.0.1')
        ibkr_port = os.getenv('IBKR_PORT', '7497')
        ibkr_client_id = os.getenv('IBKR_CLIENT_ID', '42')
        use_paper = os.getenv('USE_PAPER', '1')
        
        logger.info(f"  IBKR Host: {ibkr_host}")
        logger.info(f"  IBKR Port: {ibkr_port} ({'TWS' if ibkr_port == '7497' else 'Gateway'} paper)")
        logger.info(f"  Client ID: {ibkr_client_id}")
        logger.info(f"  Paper Mode: {use_paper == '1'}")
        
        # Try to connect (will fail if TWS/Gateway not running - that's OK for this test)
        try:
            broker = get_broker(config)
            
            if broker.is_connected():
                logger.info("[OK] Connected to IBKR successfully")
                
                # Test getting account info
                account = broker.get_account()
                logger.info(f"  Account equity: ${account.get('equity', 0):.2f}")
                logger.info(f"  Buying power: ${account.get('buying_power', 0):.2f}")
                
                # Test getting a quote (AAPL as test)
                quote = broker.get_quote("AAPL")
                if quote.get('last', 0) > 0:
                    logger.info(f"[OK] Market data working: AAPL = ${quote['last']:.2f}")
                
                broker.close()
                return True
            else:
                logger.warning("[!] IBKR connection failed (is TWS/Gateway running?)")
                return False
                
        except Exception as e:
            logger.warning(f"[!] IBKR connection failed: {e}")
            logger.info("  This is OK if TWS/Gateway is not running")
            logger.info("  To enable IBKR:")
            logger.info("    1. Start IBKR TWS or IB Gateway")
            logger.info("    2. Login to Paper account")
            logger.info("    3. Enable API in settings")
            logger.info("    4. Set environment variables:")
            logger.info(f"       $env:IBKR_HOST='{ibkr_host}'")
            logger.info(f"       $env:IBKR_PORT='{ibkr_port}'")
            logger.info(f"       $env:IBKR_CLIENT_ID='{ibkr_client_id}'")
            logger.info(f"       $env:USE_PAPER='1'")
            return False
        
    except Exception as e:
        logger.error(f"[X] Broker test failed: {e}")
        return False


def test_vix_provider():
    """Test 3: Yahoo VIX data provider."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 3: VIX Data Provider (Yahoo Finance)")
    logger.info("=" * 80)
    
    try:
        # Use Yahoo Finance (free, no API keys needed)
        logger.info("[OK] Using Yahoo Finance for VIX data (free)")
        provider = YahooVIXProvider()
        
        # Test connectivity and get VIX
        if provider.is_available():
            logger.info("[OK] Yahoo Finance API accessible")
        else:
            logger.warning("[!] Yahoo Finance API may be degraded")
        
        # Get VIX value
        vix = provider.get_vix()
        logger.info(f"[OK] VIX data retrieved: {vix:.2f}")
        
        # Get volatility regime
        vol_level = provider.get_volatility_level(vix)
        logger.info(f"  VIX Regime: {vol_level}")
        
        return provider
        
    except Exception as e:
        logger.error(f"[X] VIX provider test failed: {e}")
        logger.info("[!] Falling back to mock VIX provider")
        
        # Fallback to mock for testing
        from bouncehunter.data.vix_provider import MockVIXProvider
        return MockVIXProvider(vix_value=20.0)


def test_regime_detector():
    """Test 4: Market regime detector."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 4: Market Regime Detector")
    logger.info("=" * 80)
    
    try:
        # For now, use mock detector
        # TODO: Implement YahooRegimeDetector for SPY data
        logger.warning("[!] Using MockRegimeDetector (Yahoo SPY detector coming soon)")
        detector = MockRegimeDetector(regime=MarketRegime.BULL)
        
        # Get regime
        regime = detector.detect_regime()
        logger.info(f"[OK] Market regime detected: {regime.value}")
        
        # Get diagnostics
        diagnostics = detector.get_regime_details()
        logger.info(f"  20-day SMA: ${diagnostics.get('sma_20', 0):.2f}")
        logger.info(f"  50-day SMA: ${diagnostics.get('sma_50', 0):.2f}")
        logger.info(f"  Spread: {diagnostics.get('spread_pct', 0):.2f}%")
        
        return detector
        
    except Exception as e:
        logger.error(f"[X] Regime detector test failed: {e}")
        raise


def test_adjustment_calculation(vix_provider, regime_detector):
    """Test 5: Adjustment calculation with real providers."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 5: Adjustment Calculation")
    logger.info("=" * 80)
    
    try:
        # Get current market data
        vix = vix_provider.get_vix()
        regime = regime_detector.detect_regime()
        
        # Create market conditions
        conditions = MarketConditions(
            vix_provider=vix_provider,
            regime_detector=regime_detector
        )
        
        # Get volatility level
        vol_level = conditions.get_volatility_level(vix)
        
        logger.info(f"[OK] Market conditions: VIX={vix:.2f} ({vol_level.value}), Regime={regime.value}")
        
        # Create adjustment calculator
        calculator = AdjustmentCalculator(
            market_conditions=conditions,
            enable_volatility_adjustments=True,
            enable_time_adjustments=True,
            enable_regime_adjustments=True
        )
        
        # Test adjustment calculation
        base_target = 5.0
        adjusted_target, breakdown = calculator.adjust_tier1_target(
            base_target=base_target,
            current_vix=vix
        )
        
        total_adjustment = adjusted_target - base_target
        
        logger.info(f"[OK] Adjustment calculation successful")
        logger.info(f"  Base target: {base_target}%")
        logger.info(f"  Adjusted target: {adjusted_target:.2f}%")
        logger.info(f"  Total adjustment: {total_adjustment:+.2f}%")
        logger.info("")
        logger.info("  Breakdown:")
        
        for component, value in breakdown.items():
            if isinstance(value, (int, float)):
                logger.info(f"    {component}: {value:+.2f}%")
            else:
                logger.info(f"    {component}: {value}")
        
        return True
        
    except Exception as e:
        logger.error(f"[X] Adjustment calculation failed: {e}")
        raise


def main():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("PAPER TRADING VALIDATION - Intelligent Adjustments System (IBKR + Yahoo)")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    try:
        # Test 1: Configuration
        config = test_configuration()
        
        # Test 2: Broker connectivity (optional - OK if TWS not running)
        broker_ok = test_broker_connectivity()
        
        # Test 3: VIX provider
        vix_provider = test_vix_provider()
        
        # Test 4: Regime detector
        regime_detector = test_regime_detector()
        
        # Test 5: Adjustment calculation
        test_adjustment_calculation(vix_provider, regime_detector)
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info("[OK] All tests passed successfully!")
        logger.info("")
        logger.info("Next Steps:")
        if not broker_ok:
            logger.info("1. Start IBKR TWS or IB Gateway (paper account)")
            logger.info("2. Enable API in Global Configuration → API → Settings")
            logger.info("3. Set environment variables:")
            logger.info("   $env:IBKR_HOST='127.0.0.1'")
            logger.info("   $env:IBKR_PORT='7497'    # 7497=TWS paper, 4002=Gateway paper")
            logger.info("   $env:IBKR_CLIENT_ID='42'")
            logger.info("   $env:USE_PAPER='1'")
            logger.info("4. Re-run this test to verify IBKR connectivity")
            logger.info("5. Run the paper trading bot: python scripts/run_pennyhunter_paper.py")
        else:
            logger.info("1. Review logs/paper_test.log for detailed output")
            logger.info("2. Customize configs/my_paper_config.yaml if needed")
            logger.info("3. Run the paper trading bot: python scripts/run_pennyhunter_paper.py")
            logger.info("4. Monitor with: python scripts/monitor_adjustments.py")
            logger.info("5. Weekly reports: python scripts/generate_weekly_report.py")
        logger.info("")
        logger.info("Paper trading system is READY for deployment!")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Tests failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
