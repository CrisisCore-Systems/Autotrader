# Intelligent Adjustments User Guide

## Table of Contents
1. [Overview](#overview)
2. [Components](#components)
3. [Configuration](#configuration)
4. [Usage Examples](#usage-examples)
5. [Tuning Recommendations](#tuning-recommendations)
6. [Troubleshooting](#troubleshooting)

---

## Overview

The **Intelligent Adjustment System** automatically adapts exit targets based on real-time market conditions, improving exit timing and profitability.

### Key Features
- **Volatility-Based Adjustments**: Widen targets in high VIX, tighten in low VIX
- **Time-of-Day Decay**: Gradually tighten targets as market close approaches
- **Market Regime Detection**: Adapt to BULL/BEAR/SIDEWAYS markets
- **Symbol-Specific Learning**: Track per-symbol performance and adjust accordingly

### How It Works
```
Base Target (e.g., Tier1 = 5.0%)
  + Volatility Adjustment (VIX-based: -2% to +1%)
  + Time Adjustment (decay: 0% to -1.5%)
  + Regime Adjustment (SPY-based: -1% to +1.5%)
  + Symbol Adjustment (learning: -0.5% to +0.5%)
  = Final Adjusted Target (clamped to safety bounds)
```

**Example:**
- Base Tier1 target: **5.0%**
- HIGH VIX (25): **-1.0%**
- Afternoon (3 PM, 85% through day): **-1.28%**
- BEAR regime: **+1.0%**
- Symbol (TSLA, low win rate): **+0.5%**
- **Final Target: 4.2%** (5.0 - 1.0 - 1.28 + 1.0 + 0.5)

---

## Components

### 1. Volatility Adjustments (VIX-based)

**Purpose**: Adapt to market volatility to improve exit timing.

**VIX Regimes:**
| VIX Level | Regime | Description | Tier1 Adj | Tier2 Adj |
|-----------|--------|-------------|-----------|-----------|
| < 15 | LOW | Calm market | +0.5% | +1.0% |
| 15-20 | NORMAL | Typical conditions | 0.0% | 0.0% |
| 20-30 | HIGH | Elevated volatility | -1.0% | -1.5% |
| > 30 | EXTREME | Crisis conditions | -2.0% | -3.0% |

**Logic:**
- **Low VIX**: Tighten targets (take profits faster in calm markets)
- **High VIX**: Widen targets (let winners run in volatile markets)

**Data Source:**
- Primary: Alpaca VIX quote data (5-minute cache)
- Fallback: Default VIX=20 (NORMAL regime)

**Configuration:**
```yaml
adjustments:
  volatility:
    enabled: true
    vix_low_threshold: 15
    vix_normal_threshold: 20
    vix_high_threshold: 30
    tier1_adjustment_low: 0.5      # Tighten in calm
    tier1_adjustment_high: -1.0    # Widen in volatility
```

---

### 2. Time-of-Day Decay

**Purpose**: Tighten targets as market close approaches to avoid overnight risk.

**Decay Curve:**
```
Progress = (Current Time - Market Open) / (Market Close - Market Open)
Adjustment = Progress × Max Decay

Example (Tier1 max decay = -1.5%):
- 09:30 (open): 0% × -1.5% = 0.0% adjustment
- 12:00 (midday): 38% × -1.5% = -0.57% adjustment
- 15:00 (3 PM): 85% × -1.5% = -1.28% adjustment
- 15:55 (close): 97% × -1.5% = -1.46% adjustment
```

**Logic:**
- **Morning (09:30-12:00)**: Minimal decay, let positions develop
- **Afternoon (12:00-15:00)**: Gradual tightening
- **Pre-Close (15:00-16:00)**: Aggressive tightening, lock in profits

**Configuration:**
```yaml
adjustments:
  time_decay:
    enabled: true
    market_open: "09:30"
    market_close: "16:00"
    tier1_max_decay_pct: -1.5
    tier2_max_decay_pct: -2.0
```

---

### 3. Market Regime Detection (SPY-based)

**Purpose**: Adapt to broader market trends for better exit timing.

**Regime Classification:**
| Regime | Definition | Tier1 Adj | Tier2 Adj | Strategy |
|--------|------------|-----------|-----------|----------|
| BULL | SPY 20 SMA > 50 SMA by +0.5% | -0.5% | -1.0% | Let winners run |
| BEAR | SPY 20 SMA < 50 SMA by -0.5% | +1.0% | +1.5% | Take profits fast |
| SIDEWAYS | SPY SMAs within ±0.5% | 0.0% | 0.0% | Neutral stance |

**Logic:**
- **BULL Market**: Widen targets (trend is your friend)
- **BEAR Market**: Tighten targets (protect gains in downtrend)
- **SIDEWAYS**: No adjustment (choppy conditions)

**Detection Method:**
1. Fetch last 100 bars of SPY (covers 50-period SMA)
2. Calculate 20-period and 50-period SMAs
3. Calculate spread: `(SMA20 - SMA50) / SMA50 × 100`
4. Classify regime based on spread

**Caching:**
- Regime cached for 24 hours (updated daily pre-market)
- Forces fresh calculation if market regime likely changed

**Configuration:**
```yaml
adjustments:
  regime:
    enabled: true
    spy_symbol: "SPY"
    short_window: 20
    long_window: 50
    sideways_threshold_pct: 0.5
    tier1_adjustment_bull: -0.5
    tier1_adjustment_bear: 1.0
    cache_ttl_hours: 24
```

---

### 4. Symbol-Specific Learning

**Purpose**: Track per-symbol performance and adapt targets accordingly.

**Learning Logic:**
```
Win Rate = (Successful Exits) / (Total Exits)
- Successful Exit = Hit target or better
- Failed Exit = Stopped out, time stop, below target

If Win Rate > 60%:
  → Apply NEGATIVE adjustment (-0.5%)
  → Widen targets (symbol tends to run further)

If Win Rate < 60%:
  → Apply POSITIVE adjustment (+0.5%)
  → Tighten targets (symbol tends to reverse)
```

**Example:**
- **AAPL**: 8/10 exits hit target (80% win rate)
  - Adjustment: **-0.5%** (widen targets)
  - Logic: AAPL tends to trend, let it run
  
- **TSLA**: 3/10 exits hit target (30% win rate)
  - Adjustment: **+0.5%** (tighten targets)
  - Logic: TSLA reverses quickly, take profits faster

**Persistence:**
- Learned adjustments saved to `reports/symbol_adjustments.json`
- Auto-saves every 5 minutes
- Survives system restarts

**Configuration:**
```yaml
adjustments:
  symbol_learning:
    enabled: true
    min_exits_for_adjustment: 5      # Need 5 exits before adjusting
    win_rate_threshold: 0.60         # 60% = good performance
    adjustment_magnitude_pct: 0.5    # ±0.5% per symbol
    persistence_file: "reports/symbol_adjustments.json"
```

---

## Configuration

### Quick Start

1. **Choose a Template:**
   - `configs/intelligent_exits.yaml` - Production baseline
   - `configs/paper_trading_adjustments.yaml` - Testing
   - `configs/live_trading_adjustments.yaml` - Conservative live

2. **Enable Adjustments:**
   ```yaml
   adjustments:
     enabled: true  # Master switch
   ```

3. **Configure VIX Provider:**
   ```yaml
   vix_provider:
     provider_type: "fallback"  # Recommended for reliability
     alpaca:
       api_key: ${ALPACA_API_KEY}
       api_secret: ${ALPACA_API_SECRET}
     fallback:
       default_vix: 20.0
   ```

4. **Configure Regime Detector:**
   ```yaml
   regime_detector:
     detector_type: "spy"
     spy:
       price_provider: "alpaca"
       short_window: 20
       long_window: 50
   ```

5. **Set Safety Bounds:**
   ```yaml
   adjustments:
     combination:
       tier1_min_target_pct: 2.0   # Never below 2%
       tier1_max_target_pct: 8.0   # Never above 8%
       tier2_min_target_pct: 5.0
       tier2_max_target_pct: 15.0
   ```

### Environment-Specific Settings

**Paper Trading:**
```yaml
# More aggressive for testing
adjustments:
  volatility:
    tier1_adjustment_high: -0.8   # Less conservative
  time_decay:
    tier1_max_decay_pct: -1.0     # Moderate decay
  symbol_learning:
    min_exits_for_adjustment: 3   # Learn faster

monitoring:
  poll_interval_seconds: 60       # Frequent checks

logging:
  level: DEBUG                    # Verbose logging
```

**Live Trading:**
```yaml
# Conservative for real money
adjustments:
  volatility:
    tier1_adjustment_high: -0.5   # More conservative
  time_decay:
    tier1_max_decay_pct: -0.8     # Gentle decay
  symbol_learning:
    min_exits_for_adjustment: 10  # Need more data

monitoring:
  poll_interval_seconds: 300      # Standard 5 min

logging:
  level: INFO                     # Production logging

safety:
  max_exits_per_cycle: 2          # Very conservative
```

---

## Usage Examples

### Example 1: Basic Integration

```python
from src.bouncehunter.exits.config import ExitConfigManager
from src.bouncehunter.exits.monitor import PositionMonitor

# Load configuration
config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')

# Create monitor with adjustments enabled
monitor = PositionMonitor(
    broker=broker,
    config=config,
    enable_adjustments=True,  # Enable intelligent adjustments
)

# Monitor will automatically apply adjustments
monitor.monitor_positions()
```

### Example 2: Manual Adjustment Calculation

```python
from src.bouncehunter.exits.adjustments import (
    MarketConditions,
    AdjustmentCalculator,
)
from src.bouncehunter.data.vix_provider import AlpacaVIXProvider
from src.bouncehunter.data.regime_detector import SPYRegimeDetector

# Create components
vix_provider = AlpacaVIXProvider(alpaca_client)
regime_detector = SPYRegimeDetector(price_provider)
market_conditions = MarketConditions(
    vix_provider=vix_provider,
    regime_detector=regime_detector,
)
calculator = AdjustmentCalculator(market_conditions)

# Calculate adjusted target
base_target = 5.0  # Tier1 base target
adjusted_target, details = calculator.adjust_tier1_target(
    base_target_pct=base_target,
    symbol="AAPL",
)

print(f"Base: {base_target}%")
print(f"Adjusted: {adjusted_target}%")
print(f"Details: {details}")
```

### Example 3: Position-Specific Overrides

```python
# Disable adjustments for specific position
position = {
    'ticker': 'TSLA',
    'shares': 100,
    'exit_config_override': {
        'adjustments': {
            'enabled': False  # Disable for this position only
        }
    }
}

# Or customize adjustment for specific symbol
position = {
    'ticker': 'AAPL',
    'exit_config_override': {
        'adjustments': {
            'volatility': {
                'tier1_adjustment_high': -1.5  # More aggressive for AAPL
            }
        }
    }
}

# Apply overrides
pos_config = ExitConfigManager.apply_position_overrides(config, position)
```

---

## Tuning Recommendations

### Conservative Settings (Risk-Averse)
```yaml
adjustments:
  volatility:
    tier1_adjustment_high: -0.5    # Gentle widening
  time_decay:
    tier1_max_decay_pct: -0.8      # Moderate decay
  regime:
    tier1_adjustment_bull: -0.3    # Small widening in bull
  combination:
    tier1_min_target_pct: 3.0      # Higher minimum (safer)
```

**Use when:**
- Starting with intelligent adjustments
- Trading less liquid symbols
- Account is close to risk limits

### Aggressive Settings (Risk-Tolerant)
```yaml
adjustments:
  volatility:
    tier1_adjustment_high: -1.5    # Aggressive widening
  time_decay:
    tier1_max_decay_pct: -2.0      # Steep decay
  regime:
    tier1_adjustment_bull: -1.0    # Large widening in bull
  combination:
    tier1_min_target_pct: 1.5      # Lower minimum (more range)
```

**Use when:**
- System is proven in paper trading
- Trading highly liquid symbols
- Confident in trend continuation

### Balanced Settings (Recommended)
```yaml
adjustments:
  volatility:
    tier1_adjustment_low: 0.5
    tier1_adjustment_high: -1.0
  time_decay:
    tier1_max_decay_pct: -1.5
  regime:
    tier1_adjustment_bull: -0.5
    tier1_adjustment_bear: 1.0
  combination:
    tier1_min_target_pct: 2.0
    tier1_max_target_pct: 8.0
```

**Use when:**
- General purpose trading
- Mixed symbol liquidity
- Production baseline

---

## Troubleshooting

### Issue: VIX Data Unavailable

**Symptoms:**
```
WARNING: VIX provider failed, using fallback: default_vix=20.0
```

**Solutions:**
1. Check Alpaca API credentials
2. Verify Alpaca account has market data access
3. Use fallback provider:
   ```yaml
   vix_provider:
     provider_type: "fallback"
     fallback:
       default_vix: 20.0
   ```
4. For testing, use mock provider:
   ```yaml
   vix_provider:
     provider_type: "mock"
     mock:
       fixed_vix: 25.0  # Simulate HIGH VIX
   ```

### Issue: Regime Detector Errors

**Symptoms:**
```
WARNING: Failed to detect regime: Insufficient data
```

**Solutions:**
1. Ensure SPY data is available from provider
2. Check if market is open (need recent bars)
3. Reduce SMA windows temporarily:
   ```yaml
   regime_detector:
     spy:
       short_window: 10
       long_window: 20
   ```
4. Use mock detector for testing:
   ```yaml
   regime_detector:
     detector_type: "mock"
     mock:
       fixed_regime: "BULL"
   ```

### Issue: Adjustments Too Extreme

**Symptoms:**
- Targets consistently hitting min/max bounds
- Exit timing feels off

**Solutions:**
1. Review adjustment ranges:
   ```yaml
   adjustments:
     volatility:
       tier1_adjustment_high: -0.5  # Reduce from -1.0
   ```
2. Tighten safety bounds:
   ```yaml
   combination:
     tier1_min_target_pct: 3.0      # Raise from 2.0
     tier1_max_target_pct: 6.5      # Lower from 8.0
   ```
3. Check logs for specific adjustments:
   ```
   logs/adjustments.log
   ```

### Issue: Symbol Learning Not Working

**Symptoms:**
- No symbol adjustments appearing
- `reports/symbol_adjustments.json` empty or missing

**Solutions:**
1. Ensure enough exits recorded:
   ```yaml
   symbol_learning:
     min_exits_for_adjustment: 3  # Lower threshold
   ```
2. Check persistence file path is writable
3. Verify learning is enabled:
   ```yaml
   symbol_learning:
     enabled: true
   ```
4. Review symbol learner logs for errors

### Issue: Configuration Validation Errors

**Symptoms:**
```
ConfigValidationError: VIX thresholds must be ordered: low < normal < high
```

**Solutions:**
1. Fix threshold ordering:
   ```yaml
   volatility:
     vix_low_threshold: 15      # Must be < normal
     vix_normal_threshold: 20   # Must be < high
     vix_high_threshold: 30
   ```
2. Check adjustment ranges (-10 to +10):
   ```yaml
   tier1_adjustment_high: -1.0  # Must be -10 to +10
   ```
3. Verify all required fields present
4. Use template as reference

---

## Performance Monitoring

### Key Metrics to Track

1. **Adjustment Effectiveness:**
   - Win rate with adjustments vs. baseline
   - Average exit price improvement
   - Target hit rate by regime

2. **Component Health:**
   - VIX data fetch success rate
   - Regime detection cache hit rate
   - Symbol learning coverage (% of symbols tracked)

3. **Configuration Tuning:**
   - Target bound hit rate (should be < 10%)
   - Adjustment magnitude distribution
   - Time-of-day exit clustering

### Reports

**Daily Report:**
```
reports/adjustment_performance/daily_YYYY-MM-DD.json
```
Contains:
- Exits by regime
- VIX regime distribution
- Symbol adjustments applied
- Target vs. actual exit prices

**Weekly Report:**
```
reports/adjustment_performance/weekly_YYYY-WW.json
```
Contains:
- Win rate trends
- Regime performance comparison
- Symbol learning effectiveness
- Configuration recommendations

---

## Best Practices

1. **Start in Paper Trading:**
   - Validate adjustments with paper account first
   - Run for 2-4 weeks minimum
   - Compare to baseline (no adjustments)

2. **Gradual Rollout:**
   - Start with 25% of positions
   - Increase to 50%, then 75%, then 100%
   - Monitor performance at each stage

3. **Regular Review:**
   - Check adjustment logs weekly
   - Tune ranges based on performance
   - Update symbol learning periodically

4. **Safety First:**
   - Always set conservative bounds
   - Use fallback providers
   - Enable all validation
   - Monitor logs for errors

5. **Documentation:**
   - Document any custom settings
   - Track tuning changes
   - Note market conditions during testing

---

## Advanced Topics

### Custom Adjustment Strategies

You can implement custom adjustment strategies by:

1. Creating new adjustment components
2. Extending `AdjustmentCalculator`
3. Adding to configuration schema

**Example: Sector-Based Adjustments**
```python
class SectorAdjuster:
    """Adjust targets based on sector strength."""
    
    def __init__(self, sector_provider):
        self.sector_provider = sector_provider
    
    def get_sector_adjustment(self, symbol: str) -> float:
        sector = self.sector_provider.get_sector(symbol)
        strength = self.sector_provider.get_relative_strength(sector)
        
        if strength > 1.5:  # Sector outperforming
            return -0.5  # Widen targets
        elif strength < 0.5:  # Sector underperforming
            return 0.5  # Tighten targets
        return 0.0
```

### Integration with Existing Systems

The adjustment system integrates with:
- **PositionMonitor**: Automatic adjustment application
- **Tier Executors**: Direct target modification
- **ExitConfig**: Per-position override support
- **Logging**: Detailed audit trail

See `docs/api_reference.md` for integration details.

---

## FAQ

**Q: Do adjustments work in backtesting?**
A: Yes, but you'll need historical VIX data and SPY data. Use mock providers for simplified backtesting.

**Q: Can I disable specific adjustment types?**
A: Yes, each component has an `enabled` flag:
```yaml
adjustments:
  volatility:
    enabled: false  # Disable VIX adjustments only
```

**Q: How often is VIX data refreshed?**
A: Every 5 minutes (configurable via `cache_ttl_seconds`).

**Q: What happens if all providers fail?**
A: System falls back to base targets (no adjustments applied). Logs warning.

**Q: Can I test different settings on different symbols?**
A: Yes, use position-specific overrides (see Example 3).

**Q: How do I reset symbol learning?**
A: Delete or rename `reports/symbol_adjustments.json`.

---

## Support

For issues or questions:
1. Check logs: `logs/adjustments.log`, `logs/tier_exits.log`
2. Review configuration validation errors
3. Consult API documentation: `docs/api_reference.md`
4. Check deployment guide: `docs/deployment_guide.md`

---

**Version:** 1.0.0  
**Last Updated:** October 2025  
**Status:** Production Ready ✅
