# Tree of Thought Integration for Long/Short Trading

## Overview

Integrated a sophisticated Tree of Thought (ToT) reasoning engine that analyzes market conditions across multiple dimensions before the RL agent decides between long and short positions.

## Architecture

### Multi-Path Reasoning Engine

The ToT system evaluates **4 independent reasoning paths**:

1. **Momentum Path (Weight: 35%)**
   - RSI overbought/oversold levels
   - MACD crossovers and divergence
   - Price vs VWAP (institutional reference)
   - Volume confirmation
   - Price momentum strength

2. **Microstructure Path (Weight: 30%)**
   - Bid-ask spread (liquidity quality)
   - Order book imbalance
   - Buy/sell pressure analysis
   - Order flow direction
   - Institutional flow detection

3. **Volatility Path (Weight: 20%)**
   - Price position in session range
   - ATR regime (high/low volatility)
   - Bollinger band width (trending/consolidation)
   - Mean reversion vs breakout signals

4. **Regime Path (Weight: 15%)**
   - Trend strength and direction
   - Time of day effects (open/midday/close)
   - Market phase analysis
   - Volatility regime classification

### Decision Synthesis

Each path generates:
- **Direction Bias**: STRONG_LONG (+3), WEAK_LONG (+2), NEUTRAL (+1), WEAK_SHORT (-1), STRONG_SHORT (-2)
- **Confidence Score**: 0.0 to 1.0
- **Evidence List**: Human-readable reasoning
- **Path Score**: -1.0 to +1.0

Final decision combines:
- **Weighted Consensus**: Paths weighted by importance and confidence
- **Agreement Score**: How aligned are the paths?
- **Action Recommendation**: Maps to 8-action space (0-7)

## Action Mapping

```
0 = CLOSE      (any position)
1 = HOLD       (no action)
2 = LONG_SMALL (100 shares)
3 = LONG_MED   (200 shares)
4 = LONG_LARGE (300 shares)
5 = SHORT_SMALL (-100 shares)
6 = SHORT_MED   (-200 shares)
7 = SHORT_LARGE (-300 shares)
```

## Long vs Short Decision Logic

### Favors LONG when:
- **Momentum**: RSI < 40, MACD bullish, price above VWAP, strong upward momentum
- **Microstructure**: Bid depth dominance, high buy pressure, positive order flow
- **Volatility**: Price near lows (oversold), low vol breakout above resistance
- **Regime**: Strong uptrend, market open momentum, low volatility regime

### Favors SHORT when:
- **Momentum**: RSI > 60, MACD bearish, price below VWAP, strong downward momentum
- **Microstructure**: Ask depth dominance, high sell pressure, negative order flow
- **Volatility**: Price near highs (overbought), low vol breakdown below support
- **Regime**: Strong downtrend, risk-off conditions, defensive positioning

### Position Management:
- **Reversal Detection**: Closes position if direction changes with >70% confidence
- **Hold Logic**: Maintains position if paths remain aligned
- **Size Selection**: Confidence-based sizing (higher confidence = larger size)

## Integration Points

### Trading Environment
```python
# Enable ToT reasoning (default: True)
env = IntradayTradingEnv(
    pipeline=pipeline,
    microstructure=microstructure,
    momentum=momentum,
    enable_tot_reasoning=True,  # NEW parameter
)
```

### Info Dict Additions
```python
info = {
    # ... existing fields ...
    "tot_direction": "STRONG_LONG",    # Direction bias
    "tot_confidence": 0.85,            # Overall confidence
    "tot_action": 4,                   # Recommended action
    "tot_consensus": 0.72,             # Consensus score (-1 to +1)
}
```

### Training Callbacks
Updated `WinRateCallback` to track:
- Long vs Short action distribution
- Per-side performance metrics
- Action balance monitoring

## Benefits

1. **Explainability**: Each decision comes with detailed reasoning across 4 dimensions
2. **Robustness**: Multiple paths reduce false signals from single-indicator noise
3. **Adaptability**: Weighted paths can be tuned for different market conditions
4. **Learning Signal**: ToT decisions serve as soft targets for the RL agent
5. **Risk Management**: High-confidence threshold prevents weak trades

## Example Decision

```
======================================================================
Tree of Thought Decision: STRONG_LONG
Confidence: 82.3%
Consensus Score: +0.72
Recommended Action: 4 (LONG_LARGE)
======================================================================

[Momentum] STRONG_LONG (conf=0.88, score=+0.85)
  • RSI oversold (32.4)
  • MACD strong bullish crossover
  • Price above VWAP (+0.15%)
  • High volume (2.1x)
  • Strong upward momentum

[Microstructure] WEAK_LONG (conf=0.65, score=+0.35)
  • Tight spread (good liquidity)
  • Moderate bid depth (0.22)
  • Moderate buy pressure (0.58)
  • Positive order flow (institutional buying)

[Volatility] NEUTRAL (conf=0.42, score=+0.10)
  • Price near session low (potential bounce)
  • Low volatility (ATR=0.008)
  • Bollinger bands tight (consolidation)

[Regime] STRONG_LONG (conf=0.91, score=+0.95)
  • Strong uptrend (strength=0.68)
  • Market open (high volatility)
  • Low volatility regime

======================================================================
```

## Performance Expectations

With ToT reasoning:
- **Improved Win Rate**: Better entry timing through multi-factor confirmation
- **Reduced Whipsaws**: Consensus requirement filters noise
- **Balanced Exposure**: Equal opportunity for long and short profits
- **Higher Sharpe**: Risk-adjusted returns from selective entry/exit

## Monitoring

Track in training logs:
- `tot_direction`: Direction distribution (long/short/neutral)
- `tot_confidence`: Average confidence levels
- `tot_action`: Action recommendation vs agent action (agreement rate)
- Long/Short action percentages

## Next Steps

1. ✅ Integrate ToT into trading environment
2. ✅ Add short position support (8-action space)
3. ✅ Update training callbacks for long/short tracking
4. ⏭️ Run training with ToT enabled
5. ⏭️ Analyze long vs short performance metrics
6. ⏭️ Fine-tune path weights based on results
7. ⏭️ A/B test: ToT-assisted vs pure RL

## Configuration

Adjust path weights in environment initialization:
```python
tot_reasoner = TreeOfThoughtReasoner(
    momentum_weight=0.35,      # Trend following
    microstructure_weight=0.30, # Order flow
    volatility_weight=0.20,     # Risk regime
    regime_weight=0.15,         # Market phase
)
```

Higher weights = more influence on final decision.
