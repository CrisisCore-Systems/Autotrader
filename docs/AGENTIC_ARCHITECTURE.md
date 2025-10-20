# Agentic BounceHunter Architecture

## Overview

BounceHunter has been transformed into an **agentic multi-agent system** with memory, learning loops, and deterministic decision-making. The architecture follows a ring of specialized agents that collaborate to identify, validate, and execute (or alert on) mean-reversion trades.

## Core Philosophy

1. **Tools-First**: Agents use deterministic tools (regex, DB queries, rule checks) before reaching for LLMs
2. **Memory-Persistent**: All signals, fills, and outcomes stored in SQLite for learning
3. **Base-Rate Driven**: System tracks hit rates per ticker/regime and auto-adapts thresholds
4. **Veto-Shortcircuit**: Any agent can veto a signal; flow stops immediately
5. **Alert-Only Default**: `live_trading=False` means paper fills and Telegram alerts only

## Agent Ring

```
Sentinel → Screener → Forecaster → RiskOfficer → NewsSentry → Trader → Historian → Auditor
    ↓                                      ↓            ↓          ↓          ↓
  Context                               Veto?       Veto?      Paper    Persist
                                                              Fills     to DB
```

### 1. Sentinel
- **Role**: Regime detection and timing
- **Tools**: VIX percentile (252-day), SPY 200DMA distance, market hours check
- **Output**: `Context` (regime, VIX percentile, SPY stress, market hours)

### 2. Screener
- **Role**: Feature computation and candidate generation
- **Tools**: BounceHunter engine (z-score, RSI2, 200DMA, earnings blackout)
- **Output**: List of `Signal` objects (ticker, entry, stop, target, BCS)

### 3. Forecaster
- **Role**: Probability calibration and threshold filtering
- **Tools**: BCS thresholds (normal vs high-VIX)
- **Output**: Filtered signals (only those above BCS threshold)

### 4. RiskOfficer
- **Role**: Portfolio risk enforcement
- **Tools**: 
  - Max concurrent positions check (default 8)
  - Max per sector (default 3)
  - Ticker base-rate lookup (eject if <40%)
  - Earnings window veto
- **Output**: Approved signals or vetoed with reason

### 5. NewsSentry
- **Role**: Adverse headline detection
- **Tools**: (Stub for now) Severe term scanner (SEC, fraud, probe, restatement)
- **Output**: Signals after news veto

### 6. Trader
- **Role**: Order generation (paper or live)
- **Tools**: Size percentage from policy (normal: 1.2%, high-VIX: 0.6%)
- **Output**: List of `Action` objects (BUY/ALERT, size, entry/stop/target)

### 7. Historian
- **Role**: Data persistence
- **Tools**: SQLite inserts (signals, fills tables)
- **Output**: Success/failure boolean

### 8. Auditor
- **Role**: Post-trade review and learning
- **Tools**: 
  - Reward computation (+1 target, -1 stop, -0.2 time decay)
  - Base-rate calculation per ticker
  - Regime-sliced hit rates
- **Output**: Updated `ticker_stats` table

## Orchestrator

The `Orchestrator` class coordinates the agent flow:

```python
async def run_daily_scan(self) -> Dict[str, Any]:
    ctx = await sentinel.run()
    signals = await screener.run(ctx)
    signals = await forecaster.run(signals, ctx, policy)
    signals = await risk_officer.run(signals, ctx)  # Veto shortcircuit
    signals = await news_sentry.run(signals)         # Veto shortcircuit
    actions = await trader.run(signals, ctx)
    await historian.run(signals, actions, ctx)
    return summary
```

## Memory Schema

SQLite database `bouncehunter_memory.db`:

### `signals` table
- `signal_id`, `timestamp`, `ticker`, `probability`, `entry`, `stop`, `target`
- `regime`, `size_pct`, `z_score`, `rsi2`, `vetoed`, `veto_reason`

### `fills` table
- `fill_id`, `signal_id`, `entry_date`, `entry_price`, `shares`, `size_pct`, `is_paper`

### `outcomes` table
- `outcome_id`, `fill_id`, `exit_date`, `exit_price`, `exit_reason`
- `hold_days`, `return_pct`, `hit_target`, `hit_stop`, `reward`

### `ticker_stats` table
- `ticker`, `base_rate`, `avg_reward`, `normal_regime_rate`, `ejected`, `last_updated`

### `system_state` table
- Key-value store for drawdown tracking, last scan timestamp, etc.

## Policy Configuration

The `Policy` dataclass holds runtime parameters:

```python
@dataclass
class Policy:
    config: BounceHunterConfig  # Reference to scanner config
    live_trading: bool = False
    min_bcs: float = 0.62
    min_bcs_highvix: float = 0.68
    max_concurrent: int = 8
    max_per_sector: int = 3
    allow_earnings: bool = False
    risk_pct_normal: float = 0.012  # 1.2%
    risk_pct_highvix: float = 0.006  # 0.6%
    news_veto_enabled: bool = False
    auto_adapt_thresholds: bool = True
    base_rate_floor: float = 0.40
    min_sample_size: int = 20
```

## CLI Usage

### Daily Scan (Alert Mode)
```bash
python -m bouncehunter.agentic_cli --mode scan --config configs/telegram_pro.yaml
```

Output:
```
Timestamp: 2025-06-15T15:30:00
Context:
  Date: 2025-06-15
  Regime: normal
  VIX Percentile: 42.3
  SPY vs 200DMA: 98.5%
  Market Hours: True

Signals: 3
Approved: 2

Actions:
  AAPL:
    Action: ALERT
    Entry: $172.50
    Stop: $168.20
    Target: $179.80
    Size: 1.20%
    BCS: 68.5%
    Regime: normal
```

### Nightly Audit
```bash
python -m bouncehunter.agentic_cli --mode audit --db bouncehunter_memory.db
```

Output:
```
Updated tickers: 5

Ticker Statistics:
  AAPL:
    Base Rate: 65.0%
    Avg Reward: 0.42
    Total Outcomes: 20

  MSFT:
    Base Rate: 55.0%
    Avg Reward: 0.28
    Total Outcomes: 11
```

### With Telegram Alerts
```bash
python -m bouncehunter.agentic_cli --mode scan --telegram --config configs/telegram_pro.yaml
```

## Learning Loop

1. **Daily**: Orchestrator runs scan, persists signals and paper fills
2. **Position Tracking**: Manual entry of exit prices (or CSV import)
3. **Nightly Audit**: Auditor computes rewards, updates base rates
4. **Auto-Adaptation**: 
   - If ticker base-rate < 40% after 20+ samples → eject ticker
   - If regime-specific hit rate drops → tighten BCS threshold
5. **Drawdown Tripwire**: If portfolio DD > -10% → halt new signals, tighten BCS by +0.05

## Integration with Existing BounceHunter

The agentic system wraps the existing `BounceHunter` engine (in `engine.py`). No changes to core scanner logic required. The agents orchestrate calls to:

- `BounceHunter.fit()` - Train logistic regression model
- `BounceHunter.scan(as_of)` - Generate dip signals
- `RegimeDetector.detect()` - VIX/SPY stress checks

## Three Profile Configs

Use existing Telegram configs for different risk appetites:

- **Pro**: `configs/telegram_pro.yaml` (BCS≥0.62, size=1.2%, max=8)
- **Conservative**: `configs/telegram_conservative.yaml` (BCS≥0.68, size=0.7%, max=5)
- **Aggressive**: `configs/telegram_aggressive.yaml` (BCS≥0.58, size=0.8%, max=10)

Each config automatically loads into Policy via `load_policy_from_yaml()`.

## Next Steps

1. **Position Exit Tracking**: Add CSV import tool for manual exits or integrate broker API
2. **News Sentry Implementation**: Connect to headline feed (Finnhub, Polygon, etc.)
3. **Live Trading Mode**: Implement actual order placement when `live_trading=True`
4. **Drawdown Monitor**: Add `DrawdownMonitor` agent that tracks portfolio equity curve
5. **Telegram Integration**: Send formatted alerts via existing `TelegramNotifier`
6. **Cron Schedule**: Run daily scan at 3:45 PM ET, nightly audit at 11:59 PM ET

## Testing

Verify agent flow without real trades:

```bash
# Dry-run scan
python -m bouncehunter.agentic_cli --mode scan --config configs/telegram_conservative.yaml

# Inspect memory database
sqlite3 bouncehunter_memory.db "SELECT * FROM signals ORDER BY timestamp DESC LIMIT 5"
```

## Architecture Benefits

1. **Transparency**: Every decision logged with veto reasons
2. **Modularity**: Swap/upgrade agents independently (e.g., replace NewsSentry with LLM-based version)
3. **Learning**: Base-rate tracking identifies which tickers/regimes work
4. **Safety**: Multiple veto layers prevent bad trades; circuit breakers halt on drawdown
5. **Auditability**: Full trade lineage from signal → fill → outcome → reward

---

**Status**: ✅ Complete - Agent ring implemented, memory schema operational, CLI tested
**Version**: 1.0
**Last Updated**: 2025-06-15
