# BounceHunter Mean-Reversion Scanner

BounceHunter is a research scaffold for detecting "habitual droppers" that historically rebound after panic-selling events. The goal is to filter for oversold conditions with a statistically favourable bounce rate over the next few sessions and to deliver ready-to-act trade candidates together with suggested levels.

---

## Design Pillars

1. **Universe quality** – Stick to liquid large/mid-cap names, eject chronic decliners, and avoid instruments living far below their long-term trend.
2. **Probabilistic edge** – Model the historical probability of hitting a rebound target before violating a volatility-aware stop.
3. **Risk-first execution** – Throttle exposure in high-volatility regimes, size small, enforce strict time/price stops, and never add to losers.

---

## Feature Engineering

A signal is evaluated only after a sharp dip is detected. Each event is described by:

| Feature | Description |
| ------- | ----------- |
| `z5` | Five-day return normalised by 60-day volatility (Z-score) |
| `rsi2` | Two-period RSI capturing ultra-short-term exhaustion |
| `bb_dev` | Distance from the lower Bollinger band (20,2) |
| `dist_200` | Percentage distance from the 200-day moving average |
| `trend_63` | Three-month price slope (63-day pct-change) |
| `gap_dn` | Overnight gap size relative to the prior close |
| `vix_regime` | Percentile rank of the VIX over the past year |

Labels are set to `1` when price closes **at least +3%** (default) within **5 trading days** without hitting a **-3% stop** first. Otherwise the event is labelled `0`.

---

## Running the Scanner

Install the optional dependency set:

```powershell
pip install .[bouncehunter]
```

Then execute the CLI:

```powershell
python -m src.bouncehunter --output markdown
```

By default BounceHunter suppresses signals that occur within ±5 calendar days of a scheduled earnings announcement. The window can be customised or disabled via CLI switches.

Example output:

```
 ticker date close z_score rsi2 dist_200dma probability entry stop target adv_usd notes
  AAPL 2025-10-16 169.1   -2.2   6.4        -5.3%      0.674 169.1 164.0 174.3  $9.5M high VIX regime
```

### Key Arguments

- `--tickers` – Override the default universe (`AAPL,MSFT,...,QQQ`).
- `--threshold` – Minimum bounce credibility score (probability) required to surface a signal.
- `--rebound` / `--stop` – Target and fail-first stop expressed as decimals.
- `--horizon` – Number of trading days to look ahead when labelling events.
- `--output` – `table`, `markdown`, `json`, or `csv`.
- `--earnings-window` – Size (in days) of the blackout zone around earnings; set to `0` for same-day only.
- `--allow-earnings` – Opt in to evaluating signals even when the day is inside the blackout window.
- `--export` – Persist results as CSV/JSON for pipelines or dashboards.

The CLI prints both the signal table and the historical success rate for transparency.

---

## Walk-Forward Backtesting

BounceHunter ships with a light-weight simulator that retrains the classifier through time and records each hypothetical trade. Use backtest mode when you want to sanity-check the regime-level performance before promoting a configuration to live scanning.

Run the backtester with the same dependency set:

```powershell
python -m src.bouncehunter --backtest --tickers AAPL,MSFT,QQQ --backtest-start 2022-01-01 --backtest-end 2024-12-31
```

By default the entire history available in the local cache is evaluated. You can narrow the evaluation window or reduce data requirements:

- `--backtest-start` / `--backtest-end` – Bound the walk-forward window to a specific date range.
- `--training-events` – Cap how many labelled events the classifier can see before each decision (helpful for modelling limited sample setups). A value of `0` keeps the full history.
- `--allow-earnings` and `--earnings-window` – Mirror the scanning behaviour with identical earnings-blackout controls.
- `--show-trades` – Print every simulated trade with entry/exit metadata in addition to the summary metrics.

The summary table includes the total trade count, win rate, expectancy, cumulative return, maximum drawdown, profit factor, and average holding period. Export the individual trades to a CSV/JSON file with `--export` for deeper analysis in notebooks or dashboards.

Tip: validate configuration changes in backtest mode first, then switch back to the live scan once the behaviour matches expectations.

---

## Live Trading Integration

BounceHunter supports automated trading through broker integrations. Available modes:

1. **Alert-Only** (default) - Receive signals via Telegram/Slack, place orders manually
2. **Paper Trading** - Simulated orders for testing and validation
3. **Live Trading** - Automated order placement with real brokers

### Supported Brokers

| Broker | Best For | Min Balance | Commission | TFSA/RRSP |
|--------|----------|-------------|------------|-----------|
| **Questrade** 🇨🇦 | Canadian TFSA/RRSP | $1,000 | $5-$10 | ✅ Yes |
| **IBKR** 🌎 | Active traders, low fees | $10,000 | $1 | ✅ Yes (Canada) |
| **Alpaca** 🇺🇸 | Testing, US markets | $0 | $0 | ❌ No |
| **PaperBroker** | Risk-free simulation | $0 | $0 | N/A |

### Quick Start Examples

```bash
# Alert-only mode (no broker)
python -m bouncehunter.agentic_cli --mode scan --config configs/telegram_pro.yaml

# Paper trading (simulation)
python -m bouncehunter.agentic_cli --mode scan --broker paper --config configs/test.yaml

# Questrade (Canadian TFSA)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker questrade \
  --broker-key "YOUR_REFRESH_TOKEN" \
  --config configs/canadian_tfsa.yaml

# Interactive Brokers (paper account)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker ibkr \
  --broker-port 7497 \
  --config configs/telegram_pro.yaml

# Alpaca (US markets)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker alpaca \
  --broker-key "API_KEY" \
  --broker-secret "SECRET_KEY" \
  --config configs/telegram_pro.yaml
```

### Canadian Trader Resources

For Canadian traders using TFSA/RRSP accounts:
- **Setup Guide**: [CANADIAN_BROKERS.md](CANADIAN_BROKERS.md)
- **Quick Reference**: [CANADIAN_SETUP.md](../CANADIAN_SETUP.md)
- **TFSA Config**: `configs/canadian_tfsa.yaml` (0.8% sizing, max 5 positions)
- **Margin Config**: `configs/canadian_margin.yaml` (1.2% sizing, max 8 positions)

**Progressive Testing Workflow**:
1. PaperBroker (1 week) - Validate order logic
2. Broker paper account (2 weeks) - Test real API
3. Live small size (2 weeks) - 0.5% positions
4. Full scale (after validation) - 1.2% positions

For full broker integration documentation, see:
- [BROKER_INTEGRATION.md](BROKER_INTEGRATION.md) - Complete integration guide
- [CANADIAN_BROKERS.md](CANADIAN_BROKERS.md) - Canadian-specific setup

---

## Extending the Blueprint

* **Earnings guard** – (Now included) Pulls a lightweight calendar from Yahoo Finance and suppresses events within ±5 days of earnings by default.
* **Intraday flavour** – Recompute features on 15-minute bars, but trigger entries only near the session close to stay aligned with daily statistics.
* **Adaptive universe** – Start with a broad ETF/sector list, then remove names whose bounce credibility falls below 55% with sufficient sample size.
* **Portfolio layer** – Respect sector concentration, cap concurrent signals, and scale risk down during stressed volatility regimes.
* **Alerting** – Wire the CLI into a cron job and publish Slack/Telegram messages for qualifying events.
* **Backtest harness** – Wrap the signal logic with a walk-forward simulator to monitor drawdowns, turnover, and parameter drift.

---

## Caveats

Mean-reversion edges are fragile:

* Regime shifts, earnings surprises, and structural downtrends can invalidate the signal rapidly.
* Base rates should be reviewed quarterly; decommission symbols if their bounce success rate deteriorates.
* Stops and sizing discipline matter more than the entry itself—never martingale and never double down on failing signals.

BounceHunter helps you **say "no" 95% of the time** and reserve capital for the rare dips where history suggests the odds are stacked in your favour.
