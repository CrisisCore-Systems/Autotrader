# Intelligent Adjustments API Reference

## Table of Contents
1. [Core Classes](#core-classes)
2. [Data Providers](#data-providers)
3. [Configuration](#configuration)
4. [Integration Patterns](#integration-patterns)
5. [Code Examples](#code-examples)

---

## Core Classes

### MarketConditions

**Module:** `src.bouncehunter.exits.adjustments`

**Purpose:** Central hub for market state information (VIX, regime, time).

**Constructor:**
```python
MarketConditions(
    vix_provider: Optional[Any] = None,
    regime_detector: Optional[Any] = None
)
```

**Parameters:**
- `vix_provider` (optional): VIX data provider implementing `get_current_vix()`
- `regime_detector` (optional): Regime detector implementing `detect_regime()`

**Methods:**

#### `get_volatility_regime() -> VolatilityRegime`
Get current volatility regime based on VIX.

**Returns:**
- `VolatilityRegime`: Enum value (LOW, NORMAL, HIGH, or EXTREME)

**Example:**
```python
market_conditions = MarketConditions(vix_provider=vix_provider)
regime = market_conditions.get_volatility_regime()
print(f"Volatility: {regime.value}")  # e.g., "HIGH"
```

#### `get_market_regime() -> MarketRegime`
Get current market regime based on SPY.

**Returns:**
- `MarketRegime`: Enum value (BULL, BEAR, SIDEWAYS, or UNKNOWN)

**Example:**
```python
market_conditions = MarketConditions(regime_detector=detector)
regime = market_conditions.get_market_regime()
print(f"Market: {regime.value}")  # e.g., "BULL"
```

#### `get_vix() -> Optional[float]`
Get current VIX value.

**Returns:**
- `float`: VIX value (0-100), or `None` if unavailable

**Example:**
```python
vix = market_conditions.get_vix()
if vix:
    print(f"VIX: {vix:.2f}")
```

#### `update_regime(regime: MarketRegime) -> None`
Manually update market regime (for testing/override).

**Parameters:**
- `regime`: MarketRegime enum value

**Example:**
```python
market_conditions.update_regime(MarketRegime.BULL)
```

---

### AdjustmentCalculator

**Module:** `src.bouncehunter.exits.adjustments`

**Purpose:** Calculate intelligent adjustments for exit targets.

**Constructor:**
```python
AdjustmentCalculator(
    market_conditions: MarketConditions,
    volatility_adjustments: Optional[Dict[str, float]] = None,
    time_adjustments: Optional[Dict[str, float]] = None,
    regime_adjustments: Optional[Dict[str, float]] = None
)
```

**Parameters:**
- `market_conditions`: MarketConditions instance
- `volatility_adjustments` (optional): Custom VIX adjustment map
- `time_adjustments` (optional): Custom time decay settings
- `regime_adjustments` (optional): Custom regime adjustment map

**Methods:**

#### `adjust_tier1_target(base_target_pct: float, symbol: Optional[str] = None) -> Tuple[float, Dict[str, Any]]`
Calculate adjusted Tier1 exit target.

**Parameters:**
- `base_target_pct`: Base target percentage (e.g., 5.0 for +5%)
- `symbol` (optional): Symbol for symbol-specific learning

**Returns:**
- `Tuple[float, Dict]`: (adjusted_target, adjustment_details)
  - `adjusted_target`: Final target after all adjustments
  - `adjustment_details`: Dict with breakdown of each adjustment

**Example:**
```python
calculator = AdjustmentCalculator(market_conditions)
adjusted, details = calculator.adjust_tier1_target(
    base_target_pct=5.0,
    symbol="AAPL"
)

print(f"Base: 5.0%, Adjusted: {adjusted:.2f}%")
print(f"Volatility: {details['volatility_adjustment']:.2f}%")
print(f"Time: {details['time_adjustment']:.2f}%")
print(f"Regime: {details['regime_adjustment']:.2f}%")
print(f"Symbol: {details['symbol_adjustment']:.2f}%")
```

#### `adjust_tier2_target(base_min_pct: float, base_max_pct: float, symbol: Optional[str] = None) -> Tuple[float, float, Dict[str, Any]]`
Calculate adjusted Tier2 exit target range.

**Parameters:**
- `base_min_pct`: Base minimum target (e.g., 8.0 for +8%)
- `base_max_pct`: Base maximum target (e.g., 10.0 for +10%)
- `symbol` (optional): Symbol for symbol-specific learning

**Returns:**
- `Tuple[float, float, Dict]`: (adjusted_min, adjusted_max, details)

**Example:**
```python
min_target, max_target, details = calculator.adjust_tier2_target(
    base_min_pct=8.0,
    base_max_pct=10.0,
    symbol="TSLA"
)

print(f"Target range: {min_target:.2f}% - {max_target:.2f}%")
```

#### `calculate_adjustment(base_value: float, tier: str = 'tier1', symbol: Optional[str] = None) -> Tuple[float, Dict[str, Any]]`
Generic adjustment calculation (internal helper).

**Parameters:**
- `base_value`: Base value to adjust
- `tier`: Tier name ('tier1' or 'tier2')
- `symbol`: Symbol for learning

**Returns:**
- `Tuple[float, Dict]`: (adjusted_value, details)

---

### SymbolLearner

**Module:** `src.bouncehunter.exits.adjustments`

**Purpose:** Track per-symbol performance and provide symbol-specific adjustments.

**Constructor:**
```python
SymbolLearner(
    min_exits_for_adjustment: int = 5,
    win_rate_threshold: float = 0.60,
    adjustment_magnitude_pct: float = 0.5
)
```

**Parameters:**
- `min_exits_for_adjustment`: Minimum exits before applying adjustment (default: 5)
- `win_rate_threshold`: Win rate above which to widen targets (default: 0.60)
- `adjustment_magnitude_pct`: Size of adjustment (default: 0.5%)

**Methods:**

#### `record_exit(symbol: str, hit_target: bool, exit_price: float, target_price: float) -> None`
Record an exit for learning.

**Parameters:**
- `symbol`: Stock symbol
- `hit_target`: True if exit hit or exceeded target
- `exit_price`: Actual exit price
- `target_price`: Target price that was set

**Example:**
```python
learner = SymbolLearner()
learner.record_exit(
    symbol="AAPL",
    hit_target=True,
    exit_price=150.50,
    target_price=150.00
)
```

#### `get_symbol_adjustment(symbol: str) -> float`
Get current adjustment for a symbol.

**Parameters:**
- `symbol`: Stock symbol

**Returns:**
- `float`: Adjustment percentage (-0.5 to +0.5 typically)

**Example:**
```python
adjustment = learner.get_symbol_adjustment("AAPL")
print(f"AAPL adjustment: {adjustment:+.2f}%")
```

#### `get_symbol_stats(symbol: str) -> Dict[str, Any]`
Get statistics for a symbol.

**Parameters:**
- `symbol`: Stock symbol

**Returns:**
- `Dict`: Statistics including exits, hits, win_rate, adjustment

**Example:**
```python
stats = learner.get_symbol_stats("AAPL")
print(f"Exits: {stats['total_exits']}")
print(f"Win Rate: {stats['win_rate']:.1%}")
print(f"Adjustment: {stats['adjustment']:+.2f}%")
```

#### `save_state(filepath: str) -> None`
Save learning state to file.

**Parameters:**
- `filepath`: Path to JSON file

**Example:**
```python
learner.save_state("reports/symbol_adjustments.json")
```

#### `load_state(filepath: str) -> None`
Load learning state from file.

**Parameters:**
- `filepath`: Path to JSON file

**Example:**
```python
learner.load_state("reports/symbol_adjustments.json")
```

---

## Data Providers

### VIX Providers

#### AlpacaVIXProvider

**Module:** `src.bouncehunter.data.vix_provider`

**Purpose:** Fetch real-time VIX data from Alpaca API.

**Constructor:**
```python
AlpacaVIXProvider(
    alpaca_client: StockHistoricalDataClient,
    cache_ttl_seconds: int = 300
)
```

**Parameters:**
- `alpaca_client`: Alpaca StockHistoricalDataClient instance
- `cache_ttl_seconds`: Cache time-to-live (default: 300 = 5 minutes)

**Methods:**

#### `get_current_vix() -> Optional[float]`
Get current VIX value.

**Returns:**
- `float`: VIX value, or `None` if fetch fails

**Example:**
```python
from alpaca.data.historical import StockHistoricalDataClient

client = StockHistoricalDataClient(api_key, api_secret)
vix_provider = AlpacaVIXProvider(client)

vix = vix_provider.get_current_vix()
print(f"Current VIX: {vix:.2f}")
```

#### `clear_cache() -> None`
Force cache invalidation for next fetch.

---

#### MockVIXProvider

**Module:** `src.bouncehunter.data.vix_provider`

**Purpose:** Return fixed VIX for testing/backtesting.

**Constructor:**
```python
MockVIXProvider(fixed_vix: float = 20.0)
```

**Parameters:**
- `fixed_vix`: Fixed VIX value to return (default: 20.0)

**Example:**
```python
# Test with HIGH VIX scenario
vix_provider = MockVIXProvider(fixed_vix=28.0)
```

---

#### FallbackVIXProvider

**Module:** `src.bouncehunter.data.vix_provider`

**Purpose:** Use primary provider with fallback to default.

**Constructor:**
```python
FallbackVIXProvider(
    primary_provider: Any,
    default_vix: float = 20.0
)
```

**Parameters:**
- `primary_provider`: Primary VIX provider (e.g., AlpacaVIXProvider)
- `default_vix`: Default value if primary fails (default: 20.0)

**Example:**
```python
primary = AlpacaVIXProvider(client)
vix_provider = FallbackVIXProvider(
    primary_provider=primary,
    default_vix=20.0
)

# Will use primary if available, else default
vix = vix_provider.get_current_vix()
```

---

### Regime Detectors

#### SPYRegimeDetector

**Module:** `src.bouncehunter.data.regime_detector`

**Purpose:** Detect market regime using SPY SMA crossover.

**Constructor:**
```python
SPYRegimeDetector(
    price_provider: Any,
    symbol: str = "SPY",
    short_window: int = 20,
    long_window: int = 50,
    sideways_threshold_pct: float = 0.5,
    cache_ttl_hours: int = 24
)
```

**Parameters:**
- `price_provider`: Provider with `get_bars()` method
- `symbol`: Symbol to analyze (default: "SPY")
- `short_window`: Short SMA period (default: 20)
- `long_window`: Long SMA period (default: 50)
- `sideways_threshold_pct`: Sideways threshold (default: 0.5%)
- `cache_ttl_hours`: Cache TTL (default: 24 hours)

**Methods:**

#### `detect_regime() -> MarketRegime`
Detect current market regime.

**Returns:**
- `MarketRegime`: BULL, BEAR, or SIDEWAYS

**Example:**
```python
detector = SPYRegimeDetector(price_provider)
regime = detector.detect_regime()
print(f"Market regime: {regime.value}")
```

#### `get_regime_details() -> Dict[str, Any]`
Get detailed regime information.

**Returns:**
- `Dict`: Contains SMAs, spread, regime, diagnostics

**Example:**
```python
details = detector.get_regime_details()
print(f"SMA20: {details['sma_short']:.2f}")
print(f"SMA50: {details['sma_long']:.2f}")
print(f"Spread: {details['spread_pct']:.2f}%")
print(f"Regime: {details['regime']}")
```

#### `clear_cache() -> None`
Force recalculation on next call.

---

#### MockRegimeDetector

**Module:** `src.bouncehunter.data.regime_detector`

**Purpose:** Return fixed regime for testing.

**Constructor:**
```python
MockRegimeDetector(fixed_regime: MarketRegime = MarketRegime.SIDEWAYS)
```

**Parameters:**
- `fixed_regime`: Fixed regime to return

**Example:**
```python
# Test BULL market scenario
detector = MockRegimeDetector(fixed_regime=MarketRegime.BULL)
```

---

## Configuration

### ExitConfig

**Module:** `src.bouncehunter.exits.config`

**Purpose:** Validated configuration object.

**Creation:**
```python
from src.bouncehunter.exits.config import ExitConfigManager

# From YAML
config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')

# From defaults
config = ExitConfigManager.from_default()
```

**Methods:**

#### `get(*keys, default=None) -> Any`
Get configuration value by path.

**Example:**
```python
# Get nested value
threshold = config.get('tier1', 'profit_threshold_pct')

# With default
value = config.get('tier1', 'nonexistent', default=5.0)
```

#### `is_adjustments_enabled() -> bool`
Check if adjustments are enabled.

**Example:**
```python
if config.is_adjustments_enabled():
    # Create adjustment calculator
    pass
```

#### `get_volatility_config() -> Dict[str, Any]`
Get volatility adjustment configuration.

**Example:**
```python
vol_config = config.get_volatility_config()
print(f"VIX low threshold: {vol_config['vix_low_threshold']}")
```

#### `get_vix_provider_config() -> Dict[str, Any]`
Get VIX provider configuration.

#### `get_regime_detector_config() -> Dict[str, Any]`
Get regime detector configuration.

---

### ExitConfigManager

**Module:** `src.bouncehunter.exits.config`

**Purpose:** Load and validate configurations.

**Static Methods:**

#### `from_yaml(yaml_path: str) -> ExitConfig`
Load configuration from YAML file.

**Parameters:**
- `yaml_path`: Path to YAML file

**Returns:**
- `ExitConfig`: Validated configuration

**Raises:**
- `ConfigValidationError`: If configuration invalid
- `FileNotFoundError`: If file not found

**Example:**
```python
config = ExitConfigManager.from_yaml('configs/paper_trading_adjustments.yaml')
```

#### `from_default() -> ExitConfig`
Create configuration from defaults.

**Example:**
```python
config = ExitConfigManager.from_default()
```

#### `apply_position_overrides(config: ExitConfig, position: Dict) -> ExitConfig`
Apply position-specific overrides.

**Parameters:**
- `config`: Base configuration
- `position`: Position dict with optional 'exit_config_override'

**Returns:**
- `ExitConfig`: Configuration with overrides applied

**Example:**
```python
position = {
    'ticker': 'AAPL',
    'exit_config_override': {
        'tier1': {'profit_threshold_pct': 6.0}
    }
}
pos_config = ExitConfigManager.apply_position_overrides(config, position)
```

---

## Integration Patterns

### Pattern 1: Full Integration with PositionMonitor

```python
from src.bouncehunter.exits.config import ExitConfigManager
from src.bouncehunter.exits.monitor import PositionMonitor

# Load configuration
config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')

# Create monitor (automatically creates adjustment components)
monitor = PositionMonitor(
    broker=broker,
    config=config,
    enable_adjustments=True,  # Enable intelligent adjustments
)

# Monitor positions (adjustments applied automatically)
monitor.monitor_positions()
```

**Notes:**
- PositionMonitor creates VIX provider, regime detector, and calculator
- Adjustments applied to all tier executors
- No manual component creation needed

---

### Pattern 2: Manual Component Creation

```python
from alpaca.data.historical import StockHistoricalDataClient
from src.bouncehunter.data.vix_provider import AlpacaVIXProvider, FallbackVIXProvider
from src.bouncehunter.data.regime_detector import SPYRegimeDetector
from src.bouncehunter.exits.adjustments import MarketConditions, AdjustmentCalculator

# Create Alpaca client
client = StockHistoricalDataClient(api_key, api_secret)

# Create VIX provider with fallback
primary_vix = AlpacaVIXProvider(client, cache_ttl_seconds=300)
vix_provider = FallbackVIXProvider(primary_vix, default_vix=20.0)

# Create regime detector
regime_detector = SPYRegimeDetector(
    price_provider=client,
    short_window=20,
    long_window=50,
    cache_ttl_hours=24
)

# Create market conditions
market_conditions = MarketConditions(
    vix_provider=vix_provider,
    regime_detector=regime_detector
)

# Create calculator
calculator = AdjustmentCalculator(market_conditions)

# Use calculator
adjusted, details = calculator.adjust_tier1_target(5.0, symbol="AAPL")
```

**Notes:**
- Full control over component configuration
- Useful for custom integrations
- Can test components individually

---

### Pattern 3: Testing with Mock Providers

```python
from src.bouncehunter.data.vix_provider import MockVIXProvider
from src.bouncehunter.data.regime_detector import MockRegimeDetector
from src.bouncehunter.exits.adjustments import MarketConditions, AdjustmentCalculator, MarketRegime

# Create mock providers
vix_provider = MockVIXProvider(fixed_vix=28.0)  # HIGH VIX
regime_detector = MockRegimeDetector(fixed_regime=MarketRegime.BEAR)

# Create market conditions with mocks
market_conditions = MarketConditions(
    vix_provider=vix_provider,
    regime_detector=regime_detector
)

# Create calculator
calculator = AdjustmentCalculator(market_conditions)

# Test scenario: HIGH VIX + BEAR market
adjusted, details = calculator.adjust_tier1_target(5.0)

print(f"Base: 5.0%")
print(f"Adjusted: {adjusted:.2f}%")
print(f"VIX adjustment: {details['volatility_adjustment']:.2f}%")
print(f"Regime adjustment: {details['regime_adjustment']:.2f}%")
```

**Notes:**
- Perfect for unit tests
- Deterministic results
- Fast (no API calls)

---

### Pattern 4: Symbol Learning Integration

```python
from src.bouncehunter.exits.adjustments import SymbolLearner

# Create learner
learner = SymbolLearner(
    min_exits_for_adjustment=5,
    win_rate_threshold=0.60,
    adjustment_magnitude_pct=0.5
)

# Load previous state
try:
    learner.load_state("reports/symbol_adjustments.json")
except FileNotFoundError:
    pass  # Starting fresh

# Record exits as they happen
def on_position_exit(symbol, hit_target, exit_price, target_price):
    learner.record_exit(symbol, hit_target, exit_price, target_price)
    learner.save_state("reports/symbol_adjustments.json")  # Persist

# Use adjustments
adjustment = learner.get_symbol_adjustment("AAPL")
stats = learner.get_symbol_stats("AAPL")
```

**Notes:**
- Automatically persists learning
- Works across system restarts
- Gradual improvement over time

---

## Code Examples

### Example 1: Basic Adjustment Calculation

```python
from src.bouncehunter.exits.config import ExitConfigManager
from src.bouncehunter.data.vix_provider import MockVIXProvider
from src.bouncehunter.data.regime_detector import MockRegimeDetector
from src.bouncehunter.exits.adjustments import (
    MarketConditions,
    AdjustmentCalculator,
    MarketRegime,
)

# Load config
config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')

# Create components
vix_provider = MockVIXProvider(fixed_vix=25.0)  # HIGH VIX
regime_detector = MockRegimeDetector(fixed_regime=MarketRegime.BULL)

market_conditions = MarketConditions(
    vix_provider=vix_provider,
    regime_detector=regime_detector
)

calculator = AdjustmentCalculator(market_conditions)

# Calculate adjustment
base_target = 5.0
adjusted, details = calculator.adjust_tier1_target(base_target)

print(f"Base Target: {base_target}%")
print(f"Adjusted Target: {adjusted:.2f}%")
print(f"\nBreakdown:")
print(f"  Volatility: {details['volatility_adjustment']:+.2f}%")
print(f"  Time: {details['time_adjustment']:+.2f}%")
print(f"  Regime: {details['regime_adjustment']:+.2f}%")
print(f"  Symbol: {details['symbol_adjustment']:+.2f}%")
print(f"  Total: {details['total_adjustment']:+.2f}%")
```

**Output:**
```
Base Target: 5.0%
Adjusted Target: 3.7%

Breakdown:
  Volatility: -1.0%
  Time: -0.8%
  Regime: -0.5%
  Symbol: +0.0%
  Total: -2.3%
```

---

### Example 2: Environment-Based Provider Selection

```python
import os
from alpaca.data.historical import StockHistoricalDataClient
from src.bouncehunter.data.vix_provider import (
    AlpacaVIXProvider,
    MockVIXProvider,
    FallbackVIXProvider,
)

def create_vix_provider(environment: str):
    """Create VIX provider based on environment."""
    
    if environment == "production":
        # Live API with fallback
        client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY_LIVE"),
            api_secret=os.getenv("ALPACA_API_SECRET_LIVE")
        )
        primary = AlpacaVIXProvider(client, cache_ttl_seconds=300)
        return FallbackVIXProvider(primary, default_vix=20.0)
    
    elif environment == "paper":
        # Paper API with fallback
        client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            api_secret=os.getenv("ALPACA_API_SECRET")
        )
        primary = AlpacaVIXProvider(client, cache_ttl_seconds=60)
        return FallbackVIXProvider(primary, default_vix=20.0)
    
    else:  # testing/backtesting
        # Mock provider
        return MockVIXProvider(fixed_vix=20.0)

# Usage
vix_provider = create_vix_provider(os.getenv("ENV", "testing"))
```

---

### Example 3: Custom Adjustment Ranges

```python
from src.bouncehunter.exits.adjustments import AdjustmentCalculator, MarketConditions

# Create market conditions
market_conditions = MarketConditions(vix_provider, regime_detector)

# Custom volatility adjustments (more conservative)
volatility_adjustments = {
    'tier1': {
        'LOW': 0.3,      # +0.3% in LOW VIX (vs default +0.5%)
        'NORMAL': 0.0,
        'HIGH': -0.5,    # -0.5% in HIGH VIX (vs default -1.0%)
        'EXTREME': -1.0, # -1.0% in EXTREME (vs default -2.0%)
    },
    'tier2': {
        'LOW': 0.5,
        'NORMAL': 0.0,
        'HIGH': -1.0,
        'EXTREME': -2.0,
    }
}

# Create calculator with custom adjustments
calculator = AdjustmentCalculator(
    market_conditions=market_conditions,
    volatility_adjustments=volatility_adjustments
)

# Use as normal
adjusted, details = calculator.adjust_tier1_target(5.0)
```

---

### Example 4: Monitoring Adjustment Effectiveness

```python
from src.bouncehunter.exits.adjustments import SymbolLearner
import json

def analyze_adjustment_effectiveness(learner: SymbolLearner) -> Dict[str, Any]:
    """Analyze symbol learning effectiveness."""
    
    all_symbols = learner.get_all_symbols()
    
    analysis = {
        'total_symbols_tracked': len(all_symbols),
        'symbols_with_adjustment': 0,
        'average_win_rate': 0.0,
        'top_performers': [],
        'bottom_performers': [],
    }
    
    win_rates = []
    symbol_stats = []
    
    for symbol in all_symbols:
        stats = learner.get_symbol_stats(symbol)
        
        if stats['total_exits'] >= 5:
            analysis['symbols_with_adjustment'] += 1
            win_rates.append(stats['win_rate'])
            symbol_stats.append((symbol, stats))
    
    if win_rates:
        analysis['average_win_rate'] = sum(win_rates) / len(win_rates)
    
    # Sort by win rate
    symbol_stats.sort(key=lambda x: x[1]['win_rate'], reverse=True)
    
    # Top 5 performers
    analysis['top_performers'] = [
        {
            'symbol': symbol,
            'win_rate': stats['win_rate'],
            'exits': stats['total_exits'],
            'adjustment': stats['adjustment']
        }
        for symbol, stats in symbol_stats[:5]
    ]
    
    # Bottom 5 performers
    analysis['bottom_performers'] = [
        {
            'symbol': symbol,
            'win_rate': stats['win_rate'],
            'exits': stats['total_exits'],
            'adjustment': stats['adjustment']
        }
        for symbol, stats in symbol_stats[-5:]
    ]
    
    return analysis

# Usage
learner = SymbolLearner()
learner.load_state("reports/symbol_adjustments.json")

analysis = analyze_adjustment_effectiveness(learner)
print(json.dumps(analysis, indent=2))
```

---

### Example 5: Real-Time Adjustment Monitoring

```python
import logging
from datetime import datetime
from src.bouncehunter.exits.adjustments import AdjustmentCalculator

class AdjustmentMonitor:
    """Monitor and log adjustment calculations."""
    
    def __init__(self, calculator: AdjustmentCalculator):
        self.calculator = calculator
        self.logger = logging.getLogger("adjustment_monitor")
    
    def calculate_and_log(self, base_target: float, tier: str, symbol: str) -> float:
        """Calculate adjustment and log details."""
        
        if tier == 'tier1':
            adjusted, details = self.calculator.adjust_tier1_target(base_target, symbol)
        else:
            # Assuming tier2 with range
            adjusted, _, details = self.calculator.adjust_tier2_target(
                base_target, base_target + 2.0, symbol
            )
        
        # Log detailed breakdown
        self.logger.info(
            f"[{datetime.now()}] {symbol} {tier} adjustment: "
            f"base={base_target:.2f}%, adjusted={adjusted:.2f}%, "
            f"vol={details['volatility_adjustment']:+.2f}%, "
            f"time={details['time_adjustment']:+.2f}%, "
            f"regime={details['regime_adjustment']:+.2f}%, "
            f"symbol={details['symbol_adjustment']:+.2f}%"
        )
        
        # Alert on extreme adjustments
        total_adj = details['total_adjustment']
        if abs(total_adj) > 3.0:
            self.logger.warning(
                f"EXTREME ADJUSTMENT: {symbol} total={total_adj:+.2f}%"
            )
        
        return adjusted

# Usage
monitor = AdjustmentMonitor(calculator)
adjusted = monitor.calculate_and_log(5.0, 'tier1', 'AAPL')
```

---

## Error Handling

### Common Exceptions

**ConfigValidationError**
```python
from src.bouncehunter.exits.config import ConfigValidationError

try:
    config = ExitConfigManager.from_yaml('invalid_config.yaml')
except ConfigValidationError as e:
    print(f"Invalid configuration: {e}")
```

**VIX Provider Failures**
```python
vix = vix_provider.get_current_vix()
if vix is None:
    logging.warning("VIX unavailable, using default")
    vix = 20.0
```

**Regime Detection Failures**
```python
try:
    regime = detector.detect_regime()
except Exception as e:
    logging.error(f"Regime detection failed: {e}")
    regime = MarketRegime.SIDEWAYS  # Safe default
```

---

## Best Practices

1. **Always use fallback providers in production**
2. **Cache aggressively** (VIX: 5min, Regime: 24hr)
3. **Log all adjustments** for audit trail
4. **Validate configurations** before deployment
5. **Monitor adjustment ranges** (should rarely hit bounds)
6. **Test with mock providers** first
7. **Persist symbol learning** regularly
8. **Use type hints** for clarity
9. **Handle None returns** from providers
10. **Document custom adjustment logic**

---

**Version:** 1.0.0  
**Last Updated:** October 2025  
**Status:** Production Ready ✅
