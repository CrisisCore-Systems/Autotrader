# BounceHunter Operator's Guide

Professional mean-reversion trading with discipline, regime awareness, and scalable execution.

---

## Philosophy

BounceHunter helps you **say "no" 95% of the time** and reserve capital for rare dips where history suggests favorable odds. The edge comes from:

1. **Filtering** – Probabilistic muzzle ensures only high-conviction setups pass
2. **Small sizing** – Each trade risks minimal capital
3. **Brutal exits** – Fail-first stop prevents catastrophic losses

Mean-reversion edges are fragile. Regime shifts, earnings surprises, and structural downtrends can invalidate signals rapidly.

---

## Three Profiles

### 1. Pro (Recommended Default)

**Use case**: Balanced approach for disciplined operators

- **Entry**: Z-score ≤ -1.5, RSI2 ≤ 10, BCS ≥ 62% (68% high-VIX)
- **Size**: 1.2% normal / 0.6% high-VIX
- **Portfolio**: Max 8 concurrent, ≤3 per sector
- **Earnings**: Skip ±5 trading days

```powershell
python -m src.bouncehunter.telegram_cli --config configs/telegram_pro.yaml
```

### 2. Conservative

**Use case**: Capital preservation, fewer but cleaner signals

- **Entry**: Z-score ≤ -1.75, RSI2 ≤ 8, BCS ≥ 68% (72% high-VIX)
- **Size**: 0.7% normal / 0.4% high-VIX
- **Portfolio**: Max 5 concurrent, ≤2 per sector
- **Earnings**: Skip ±7 trading days

```powershell
python -m src.bouncehunter.telegram_cli --config configs/telegram_conservative.yaml
```

### 3. Aggressive

**Use case**: More shots, smaller edge per trade, faster recycle

- **Entry**: Z-score ≤ -1.25, RSI2 ≤ 12, BCS ≥ 58% (64% high-VIX)
- **Size**: 0.8% normal / 0.5% high-VIX
- **Portfolio**: Max 10 concurrent, ≤4 per sector
- **Time stop**: 4 days (vs 5 for Pro/Conservative)

```powershell
python -m src.bouncehunter.telegram_cli --config configs/telegram_aggressive.yaml
```

---

## Regime Detection

BounceHunter automatically adjusts thresholds based on market conditions:

### High-VIX Regime

**Trigger**: VIX ≥ 80th percentile over past 252 days

**Actions**:
- Raise BCS threshold (fewer signals, higher confidence)
- Halve position sizes
- Same portfolio limits

### SPY Stress Regime

**Trigger**: SPY < 90% of its 200-day moving average

**Actions**:
- Same adjustments as high-VIX
- Combines with VIX check (risk-off if either triggers)

### Normal Regime

**Conditions**: VIX < 80th percentile AND SPY ≥ 90% of 200DMA

**Actions**:
- Base thresholds and sizing apply
- Maximum signal generation rate

---

## Daily Operations

### Post-Close Scan (Primary)

**When**: 6:30 PM ET (after market close, data settled)

**Manual**:
```powershell
python -m src.bouncehunter.telegram_cli --config configs/telegram_pro.yaml
```

**Automated** (Windows Task Scheduler):
1. Open Task Scheduler
2. Create Basic Task → "BounceHunter Nightly"
3. Trigger: Daily, weekdays only, 6:30 PM
4. Action: Start a program
   - Program: `C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\python.exe`
   - Arguments: `-m src.bouncehunter.telegram_cli --config configs/telegram_pro.yaml`
   - Start in: `C:\Users\kay\Documents\Projects\AutoTrader\Autotrader`

### Pre-Close Scout (Optional)

**When**: 3:30–3:45 PM ET

**Purpose**: Verify candidates still qualify into the close

**Note**: Signals improve near close; avoid morning noise

---

## Data Dependencies & Offline Operation

### Primary data feeds

- **Price & volume history** – Pulled from Yahoo Finance via `yfinance` for each ticker when `BounceHunter.fit()` is called. This powers feature engineering (ATR, RSI2, Bollinger, ADV) and the walk-forward trainer.【F:src/bouncehunter/engine.py†L50-L156】
- **Volatility regime (VIX)** – Queried from Yahoo Finance’s `^VIX` series and transformed into a rolling percentile cache that is reused across tickers.【F:src/bouncehunter/engine.py†L159-L182】
- **Earnings calendars** – Retrieved from the Yahoo Finance ticker API to enforce blackout windows around scheduled earnings events.【F:src/bouncehunter/engine.py†L286-L305】

### Offline cache checklist

1. **Pre-fetch datasets on a connected host**:
   ```bash
   python scripts/cache_bouncehunter_data.py --output exports/bouncehunter_cache
   ```
   This captures training events, normalized OHLCV history, engineered feature tables, ticker-level earnings dates, and the VIX percentile series in CSV form that can be synced to an air-gapped workstation.【F:scripts/cache_bouncehunter_data.py†L24-L113】
2. **Version the cache** – Commit the generated `metadata.json` alongside the CSV exports so operators know which universe, start date, and earnings policy were used when the cache was created.【F:scripts/cache_bouncehunter_data.py†L89-L106】
3. **Share ancillary state** – Copy the latest `bouncehunter_memory.db` (optional, for agentic workflows) and any custom configs so the offline operator can reproduce alerts as they existed during capture.

### Reproducible backtests

- The walk-forward harness rebuilds models from the cached `TrainingArtifact` objects. When running in a limited-network environment, load the exported CSVs into a pandas DataFrame and feed them to `BounceHunterBacktester` to avoid live downloads while keeping feature calculations identical.【F:src/bouncehunter/backtest.py†L85-L113】
- Store a canonical copy of `training_events.csv` alongside backtest reports; this file records exactly which bounce events were seen during fitting, making model comparisons reproducible even months later.【F:scripts/cache_bouncehunter_data.py†L95-L106】

---

## Universe Management

### Current Default (Top 40 + Context ETFs)

```
AAPL, MSFT, NVDA, AMZN, GOOGL, META, AVGO, AMD,
COST, PEP, KO, MCD, UNH, XOM, JNJ, PG, V, MA,
NFLX, TSLA, LLY, ABBV, ORCL, CRM, INTC, TXN,
LIN, ADBE, CSCO, NKE, BA, GE, WMT, HD, TMO,
IBM, MU, PANW, SCHW, UBER

Context: SPY, QQQ, IWM (regime detection only, no signals)
```

### Expansion Strategy

Start with top-300 U.S. names by:
- Average dollar volume (ADV) ≥ $5M
- Market cap (liquid, optionable)
- Exclude: biotech microcaps, chronic downtrenders, <$5 stocks

### Ejection Rules

**Weekly review**: Remove tickers if bounce success < 40% over last 3–6 months

**Quarterly audit**: Re-run backtest, eject consistent underperformers

---

## Weekly Maintenance

### Review Base Rates

Check historical success for each ticker:

```powershell
# Run backtest on recent window
python -m src.bouncehunter.cli --backtest \
  --tickers AAPL,MSFT,NVDA \
  --backtest-start 2025-07-01 \
  --backtest-end 2025-10-17 \
  --show-trades
```

**Eject if**:
- Win rate < 40%
- Profit factor < 1.0
- Consistent DD pattern

### Position Journal

Log every trade:
- Entry date/price
- Exit date/price/reason (target/stop/time)
- Hold days
- Notes (regime, news, execution quality)

---

## Monthly/Quarterly Tuning

### Backtest Rolling Window

```powershell
# Last 2–4 years
python -m src.bouncehunter.cli --backtest \
  --tickers AAPL,MSFT,NVDA,AMD,GOOGL,AMZN,META \
  --backtest-start 2022-01-01 \
  --backtest-end 2025-10-17 \
  --training-events 400
```

### Selection Criteria

- **Profit factor** ≥ 1.2
- **Win rate** 42–55%
- **Max DD** < 8–10%
- **Consistency** across years (no one-year wonder)

If two sets tie, pick **higher BCS cut** (fewer but cleaner trades).

### Parameter Adjustments

Monitor for drift:
- If turnover increases → raise BCS threshold
- If DD creeps up → tighten portfolio limits or size down
- If dry spell extends → verify regime isn't permanently shifted

---

## Execution Discipline

### Entry Rules

1. **Wait for close**: Only enter on closing print if signal still valid
2. **Never chase**: No intraday gap-down entries
3. **Limit orders**: Around VWAP ± small band
4. **One position per name**: No averaging down

### Exit Rules

1. **Fail-first stop**: −3% (or configured) triggers immediate exit
2. **Target**: +3% (or configured) hit → exit at market
3. **Time stop**: 5 days (4 for Aggressive) → exit at close if neither hit
4. **News veto**: Guidance cut / SEC probe / fraud → exit immediately

### Position Sizing

- **Base**: 1.2% of equity per trade (Pro)
- **High-VIX**: 0.6% (halved)
- **Max concurrent**: 8 (Pro), respect sector caps
- **Never martingale**: Don't add to losers

---

## Risk Management

### Portfolio Limits

| Profile | Max Concurrent | Max Per Sector | Total Exposure |
|---------|----------------|----------------|----------------|
| Conservative | 5 | 2 | 3.5% (5 × 0.7%) |
| Pro | 8 | 3 | 9.6% (8 × 1.2%) |
| Aggressive | 10 | 4 | 8.0% (10 × 0.8%) |

### Circuit Breakers

**Halt all new signals if**:
- Three consecutive stops hit in same day
- Daily loss > 2% of equity
- VIX spikes > 40 (manual override required)

**Resume when**:
- Market stabilizes (VIX < 30)
- One full trading day passes with no new stops

---

## Upgrades for Production

### 1. ETF Earnings Skip

Already implemented via `skip_earnings_for_etfs: true`

### 2. Late-Entry Bias

Future enhancement: Only trigger signals near close (last 15–30 min)

### 3. News Veto

Basic headline check for:
- "guidance cut"
- "SEC probe"
- "fraud"
- "downgrade to sell"

Auto-skip signal if detected.

### 4. Size by Volatility

Scale size inversely with ATR so each trade risks roughly same **R**.

### 5. Sector Mapping

Auto-classify tickers by sector to enforce `max_per_sector` caps.

---

## Troubleshooting

### No Signals for Days

**Normal**. Mean-reversion edges require patience.

**Check**:
- Is regime high-VIX? (raises thresholds)
- Are tickers in downtrends? (fails 200DMA filter)
- Recent earnings cluster? (blackout windows active)

### Too Many Signals

**Adjust**:
- Raise `bcs_threshold` (+0.02 increments)
- Tighten `z_drop` (more negative)
- Lower `rsi2_max`

### Frequent Stops

**Review**:
- Are you entering pre-close? (wait for close)
- Is regime volatile? (consider Conservative profile)
- Check execution: slippage / bad fills?

### Drawdown Creeping

**Actions**:
- Halve all sizes temporarily
- Raise `bcs_threshold` by +0.05
- Review base rates per ticker, eject weak performers

---

## Quick Reference

### Config Locations

```
configs/telegram_pro.yaml          # Recommended default
configs/telegram_conservative.yaml  # Capital preservation
configs/telegram_aggressive.yaml    # Higher turnover
```

### Commands

```powershell
# Test connection
python -m src.bouncehunter.telegram_cli --config configs/telegram_pro.yaml --test

# Daily scan
python -m src.bouncehunter.telegram_cli --config configs/telegram_pro.yaml

# Backtest validation
python -m src.bouncehunter.cli --backtest --tickers AAPL,MSFT --backtest-start 2024-01-01
```

### Key Metrics

- **Profit Factor**: Gross profit ÷ gross loss (target ≥ 1.2)
- **Win Rate**: Winning trades ÷ total trades (expect 42–55%)
- **Expectancy**: (Avg win × win rate) + (avg loss × loss rate)
- **Max DD**: Peak-to-trough equity decline (keep < 10%)

---

## Reality Check

- This is **mean reversion with a probabilistic muzzle**
- Edge comes from **filtering, sizing, and exit discipline**
- Expect dry days (that's good—signals should be scarce)
- Base rates degrade over time—quarterly reviews mandatory
- Stops matter more than entries—never skip them

**Discipline > Prediction**

---

For questions or enhancements, see `docs/BOUNCEHUNTER_GUIDE.md` and `docs/TELEGRAM_BOT_SETUP.md`.
