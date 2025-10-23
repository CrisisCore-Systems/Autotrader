# Phase 0 — HFT Scope & Success Criteria

## 1. Mission Overview
- Establish a tradable universe and evaluation framework for the initial high-frequency trading (HFT) rollout.
- Determine the optimal trading horizon for each instrument across equities, crypto, and forex within Phase 0 constraints.
- Deliver go/no-go criteria for advancing to architectural build-out in Phase 1.

## 2. Asset Universe & Market Coverage
| Asset Class | Coverage Definition | Venue / Feed Priorities | Rebalance Cadence |
| --- | --- | --- | --- |
| U.S. Equities | Top 100 names by 60-day average daily dollar volume across NYSE/NASDAQ (ex-ETFs). | Direct feeds (SIP + depth) via colocation in NY4; historical via Polygon/Intrinio. | Monthly with ad-hoc review for liquidity shifts. |
| Crypto | BTC, ETH, plus the 10 highest ADV altcoins listed on Coinbase, Binance, or Kraken with USD/USDT books. | Consolidated order book via Gemini/Coinbase prime FIX + CCXT historical depth. | Bi-weekly; immediate review on delistings or ADV drop >30%. |
| FX Majors | G10 pairs: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD, EURGBP, EURJPY, GBPJPY. | Primary ECNs (Currenex/Hotspot) with NY4 cross-connect; historical via TrueFX. | Quarterly with rolling liquidity audit. |

Universe governance: maintain rolling audit of spreads, depth, and realized volatility to flag candidates for removal or inclusion. Any instrument falling below 70% of baseline ADV for 10 consecutive sessions is reviewed.

## 3. Trading Horizons & Evaluation Grid
All instruments are profiled across six horizons to isolate signal decay and execution slippage impacts. Horizons are measured from signal timestamp to order completion.

| Horizon | Signal Refresh | Execution Style | Primary Use Case |
| --- | --- | --- | --- |
| 5 seconds | Tick-driven | Passive/Hybrid | Queue prioritization and microstructure alpha. |
| 15 seconds | 1–5 tick roll | Passive/Hybrid | Short-term reversal and liquidity fade. |
| 30 seconds | Event-driven | Passive/Aggressive mix | Momentum ignition, cross-venue arbitrage. |
| 1 minute | Sliding window | Aggressive | Volatility breakout filters. |
| 3 minutes | Bar close | Aggressive/Stat-arb | Mean reversion and hedging overlays. |
| 5 minutes | Bar close | Aggressive | Regime detection and risk-adjusted scaling. |

Success requires selecting a preferred horizon per instrument with documented rationale (edge persistence, fill probability, risk-adjusted returns).

## 4. Constraints & Guardrails

### 4.1 Latency Budgets (Round-Trip)
- **Equities:** ≤ 12 ms total (market data decode ≤ 4 ms, signal compute ≤ 3 ms, order route ≤ 5 ms).
- **Crypto:** ≤ 18 ms total (due to exchange API dispersion); per leg: data ≤ 6 ms, compute ≤ 4 ms, route ≤ 8 ms.
- **FX:** ≤ 10 ms total (primary ECN) with compute budget capped at 2.5 ms to preserve hit ratios.

Latency measurements captured via hardware timestamp counters; exceeding budget for three consecutive trading sessions triggers an engineering corrective action ticket.

### 4.2 Cost Targets per Trade (All-in, Post-Rebates)
- **Equities:** ≤ 0.45 bps explicit + slippage ≤ 0.55 bps → total ≤ 1.0 bps.
- **Crypto:** Taker ≤ 4 bps, Maker ≤ 1 bps; blended target ≤ 2.5 bps after rebates.
- **FX:** ECN commission ≤ 0.25 bps; slippage ≤ 0.35 bps → total ≤ 0.60 bps.

Cost monitoring uses executed order logs with 5-minute refresh dashboards. Breaches beyond 10% of target produce a daily risk control alert.

### 4.3 Risk Limits (Daily)
- Gross notional per asset class capped at 8% of deployable capital; instrument-level cap at 1.5%.
- Realized daily P&L stop-loss at −1.75% of capital; soft alert at −1.25% to trigger de-escalation review.
- Inventory: equities net position ≤ 30% of daily ADV per name; crypto exposure normalized to USD value ≤ $3.5M per asset; FX open positions ≤ $25M per pair.
- Counterparty risk: minimum of two venues alive per asset class; failover must occur within 60 seconds.

Risk dashboards aggregate in near real-time; any breach pauses new order submission until manual override.

## 5. Success Metrics & Go/No-Go Criteria
Phase 0 is deemed successful when the following are achieved on paper trading (or high-fidelity simulation) over a 90-trading-day equivalent backtest and a 10-trading-day forward paper trial:

- **Net Sharpe Ratio:** > 1.5 after transaction costs for the aggregated portfolio and > 1.2 per selected instrument/horizon combination.
- **Profit Factor:** > 1.2 aggregated, with no single instrument < 1.05.
- **Max Drawdown:** < 5% on capital over the evaluation window; individual instrument drawdown < 6.5%.
- **Hit Rate:** ≥ 52% for horizons ≤ 30s, ≥ 48% for horizons ≥ 1m.
- **Capacity:** Demonstrated scalable sizing to at least **$2.0M/day** notional turnover at **5 bps** cost assumption without degrading Sharpe below 1.3.
- **Operational Resilience:** Latency budget adherence ≥ 97% of sessions; zero critical incidents (SEV-1 outages).

Failure to meet any KPI requires iterative tuning; two consecutive failed cycles escalate to steering committee for scope reassessment.

## 6. Data, Tooling & Validation Requirements
- **Market Data:** Coalesced tick data (Level II for equities/crypto, top of book for FX) with microsecond timestamps; historical depth ≥ 12 months.
- **Reference Data:** Corporate actions, FX holiday calendars, crypto delisting feeds, funding rates for derivatives hedging.
- **Backtesting Stack:** Deterministic simulator supporting latency modeling, order queue dynamics, and venue-specific fee schedules.
- **Paper Trading Environment:** Synchronized to production connectivity, 15-minute heartbeat compliance check, full logging of order lifecycle.
- **Analytics:** Rolling performance dashboards (Sharpe, PF, DD, cost breakdown), horizon comparison matrix, and anomaly detection on fills.

## 7. Deliverables & Timeline
1. **Universe & Data Pack (Week 1):** Finalized instrument list, data validation report, and latency benchmark baseline.
2. **Horizon Evaluation Framework (Week 2):** Backtest configuration, scenario catalog, and cost model validation.
3. **Paper Trial Report (Week 4):** KPI scorecard, risk observations, capacity stress tests, and go/no-go recommendation.

Artifacts are versioned in the `docs/specs/phase0` directory with reproducible notebooks and scripts logged in MLflow.

---
**Decision Gate:** Approval to proceed to Phase 1 requires all success metrics to be met, risk/compliance sign-off, and documentation of any outstanding technical debt with mitigation plans.
