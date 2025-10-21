# Architecture & Model Risk Documentation

**Version:** Phase 2.5
**Last Updated:** October 21, 2025
**Status:** Living document - update after each discovery

---

## Overview

This document catalogs **known failure modes**, **edge cases**, and **systematic risks** discovered during development and live trading. The goal is to maintain institutional memory of "what went wrong" so we don't repeat mistakes or fall into known traps.

---

## Critical Model Failure Modes

### 1. **Scoring Inversion Bug (RESOLVED)**

**Severity:** CRITICAL
**Phase Discovered:** Phase 2 optimization
**Status:** ✅ FIXED

**Description:**
Original scoring logic accidentally inverted signal quality — low-quality setups were scored higher than high-quality ones, leading to systematic underperformance.

**Root Cause:**
```python
# WRONG (Phase 1 bug):
score = base_score - (gap_quality + volume_quality + regime_bonus)

# CORRECT (Phase 2 fix):
score = base_score + (gap_quality + volume_quality + regime_bonus)
```

**Impact:**
- Pre-fix: ~45% win rate (random)
- Post-fix: ~70% win rate (optimized)

**Prevention:**
- Always validate scoring direction with unit tests
- Run smoke test on sample data before deployment
- Document expected score ranges for each quality tier

**Code Location:**
- `src/bouncehunter/scanner.py` - `calculate_signal_score()`

**Lesson:**
Mathematical inversions are silent killers. Always validate with edge cases:
- Best possible setup → should yield highest score
- Worst possible setup → should yield lowest score

---

### 2. **Gap Frequency Bottleneck (ONGOING)**

**Severity:** MEDIUM
**Phase Discovered:** Phase 2 live validation
**Status:** ⏳ MONITORING

**Description:**
Market doesn't provide enough 10-15% gap-up candidates on typical days, creating statistical validation bottleneck. Expected 5-20 candidates/day, often seeing 2-8.

**Root Cause:**
- Narrow gap range (10-15%) reduces universe significantly
- Volume filter (≥4x avg) is aggressive
- Market conditions (low volatility) reduce gap frequency

**Current Impact:**
- Slower Phase 2 validation (target: 20 trades in 2-4 weeks)
- Risk of overfitting to small sample

**Mitigation Options:**
1. **Expand ticker universe** (150+ tickers under $10)
2. **Slightly relax volume threshold** (3.5x instead of 4x) — TEST FIRST
3. **Consider intraday micro-gaps** (2-4%) for throughput — Phase 3 idea
4. **Multi-timeframe scanning** (5min/15min bars) — requires new infrastructure

**Decision Framework:**
- If < 5 candidates/day for 2+ weeks → expand universe
- If < 10 completed trades after 4 weeks → relax filters (controlled experiment)
- DO NOT compromise core edge (gap range, volume confirmation)

**Monitoring Metrics:**
- Daily candidate count (track in `logs/pre_market_scan_*.log`)
- Weekly trade count (check `generate_daily_report.py` output)
- Time-to-validation (days to reach 20 trades)

---

### 3. **Broker Fill Discrepancy Risk (LOW)**

**Severity:** LOW
**Phase Discovered:** Multi-broker integration testing
**Status:** ⚠️ WATCH

**Description:**
Different brokers may show slight price/fill discrepancies for the same ticker at the same time due to:
- Routing differences
- Fractional penny pricing
- Execution venue variations

**Example:**
- Alpaca fill: $5.025
- IBKR fill: $5.03
- Difference: $0.005 (0.1%)

**Impact:**
- Minimal on P&L (usually <0.2% per trade)
- Could affect cross-broker performance comparisons
- May trigger false "slippage alerts" if not normalized

**Current Mitigation:**
- Use broker-specific adapter abstraction
- Log all fills with broker source
- Normalize to 2 decimal places for reporting

**Future Enhancement:**
- Build `broker_fill_analyzer.py` to track systematic biases
- If discrepancy >0.5% on average → investigate routing quality

---

### 4. **Market Regime Transition Risk (MEDIUM)**

**Severity:** MEDIUM
**Phase Discovered:** Regime filter design phase
**Status:** 🛡️ MITIGATED

**Description:**
Gap-up mean-reversion strategy performs poorly when market transitions from "normal" to "risk-off" mid-session. Pre-market regime classification may be stale by entry time (9:35 AM).

**Failure Scenario:**
1. Pre-market (7:30 AM): VIX=15, regime="normal" → signal generated
2. Market open (9:30 AM): News catalyst → VIX spikes to 22
3. Entry (9:35 AM): Now in "highvix" regime, different probabilities

**Current Mitigation:**
- 5-minute delay after open (9:35 AM entry instead of 9:30 AM)
- Dynamic target adjustment based on real-time VIX
- Stop-loss enforcement prevents catastrophic losses

**Known Edge Case:**
- Flash crash scenarios (VIX spike >50% in <10min)
- Black swan events (circuit breakers, trading halts)

**Enhancement Plan (Phase 3):**
- Real-time regime re-check at entry time
- Abort entry if regime changed significantly
- Agent-based dynamic decision: "market changed, skip this"

**Code Location:**
- `src/bouncehunter/pennyhunter_agentic.py` - `_get_regime()`

---

### 5. **Position Sizing Edge Cases (LOW)**

**Severity:** LOW
**Phase Discovered:** Paper trading Phase 2
**Status:** ✅ HANDLED

**Description:**
Fixed dollar allocation ($200/position) can lead to:
- Fractional shares on high-priced tickers
- Micro-positions on low-priced tickers
- Rounding errors in P&L calculation

**Example:**
- $200 ÷ $3.33/share = 60.06 shares → rounds to 60 shares
- Actual allocation: $199.80 (slightly under)

**Impact:**
- Minimal (<1% deviation from target)
- More noticeable on $1-2 tickers (larger % effect)

**Current Handling:**
- Round down to integer shares
- Accept minor under-allocation
- Track actual vs target allocation in fills table

**Not a Risk Because:**
- Systematic (affects all trades equally)
- Small magnitude (<1%)
- Paper trading phase allows validation

---

## Systematic Risks

### Data Quality Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Stale pre-market data | MEDIUM | Validate timestamp freshness | ✅ |
| Missing volume data | MEDIUM | Fallback to 20-day avg | ✅ |
| Delisted ticker signals | LOW | Check `tradable` flag | ✅ |
| Corporate actions (splits) | LOW | Use adjusted data | ✅ |

### Execution Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Slippage >2% on entry | MEDIUM | Pre-trade liquidity check | ✅ |
| Failed order submission | HIGH | Retry logic + alerting | ✅ |
| Partial fills | MEDIUM | Track fill quality | ⏳ |
| TWS disconnection | HIGH | Auto-reconnect + manual alert | ✅ |

### Model Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Overfitting to 2024-2025 data | HIGH | Walk-forward validation | ⏳ |
| Regime misclassification | MEDIUM | Multi-factor regime detection | ✅ |
| Sample size too small (n<20) | HIGH | Extended validation period | ⏳ |
| Black swan event | EXTREME | Stop-loss + position limits | ✅ |

---

## Phase 2.5 Specific Risks

### Memory System Risks

**Risk:** Ticker ejection based on insufficient sample size
- **Mitigation:** Minimum 5 trades before ejection consideration
- **Status:** ✅ Built into `auto_ejector.py`

**Risk:** Regime statistics become stale
- **Mitigation:** Continuous recalculation via `memory_tracker.py`
- **Status:** ✅ Auto-update on every outcome

**Risk:** False positive ejections (good ticker has bad luck)
- **Mitigation:** 40% WR threshold (allows 2/5 losses)
- **Status:** 🛡️ Conservative threshold chosen

---

## Known Edge Cases

### 1. Weekend/Holiday Scanner Runs
**Issue:** Market closed, no data available
**Handling:** Market hours validator auto-skips tasks
**Code:** `scripts/market_hours_validator.py`

### 2. Earnings Announcements
**Issue:** Gap may be fundamental, not technical
**Current:** No earnings filter implemented
**Future:** Add earnings calendar check (Phase 3)

### 3. Low Float Stocks
**Issue:** Extreme volatility, wide spreads
**Handling:** $1M+ avg daily volume filter excludes most
**Future:** Add float-specific filter if needed

### 4. ETF Gaps
**Issue:** ETFs don't mean-revert like equities
**Handling:** Universe is equity-only (no ETFs scanned)
**Prevention:** Validate `asset_type == 'equity'`

---

## Validation Checklist (Before Phase 3)

Before moving to live capital, verify:

- [ ] n ≥ 20 completed trades
- [ ] Win rate ≥ 70% (statistical significance)
- [ ] No systematic broker fill issues
- [ ] Memory system correctly ejecting poor performers
- [ ] No unhandled failure modes discovered
- [ ] Regime classification stable across market conditions
- [ ] Slippage analysis confirms <1.5% avg
- [ ] All edge cases from this doc have mitigation
- [ ] Code review completed on all scoring logic
- [ ] Disaster recovery plan tested (broker disconnect, etc.)

---

## Incident Log

### Incident #1: Scoring Inversion (2025-10-15)
- **Severity:** CRITICAL
- **Impact:** 45% WR vs 70% expected
- **Resolution:** Inverted scoring formula fixed
- **Validation:** Backtests re-run, 70% WR restored
- **Lesson:** Always validate with edge case unit tests

### Incident #2: GUI Settings Dialog Crash (2025-10-21)
- **Severity:** LOW
- **Impact:** Settings dialog AttributeError
- **Resolution:** Fixed attribute access pattern
- **Validation:** GUI tested, dialog works
- **Lesson:** Test Toplevel dialogs with entry storage

### Incident #3: Database Schema Mismatch (2025-10-21)
- **Severity:** MEDIUM
- **Impact:** Daily report script failed
- **Resolution:** Updated queries to match agentic.py schema
- **Validation:** Report generates correctly
- **Lesson:** Keep schema docs synchronized

---

## Future Risk Monitoring

### Phase 3 Risks to Watch
1. **Agent coordination failures** (conflicting signals)
2. **Recursive learning instability** (agent feedback loops)
3. **Real capital psychological impact** (manual override temptation)
4. **Latency sensitivity** (if moving to faster timeframes)

### Metrics to Track
- Daily Sharpe ratio (rolling 20-trade window)
- Max drawdown (portfolio level)
- Regime transition performance (before/after shift)
- Fill quality (actual vs theoretical slippage)
- Memory system ejection rate (should be ~5-10% of universe)

---

## Contact & Escalation

**For new risks discovered:**
1. Document in this file immediately
2. Assess severity (LOW/MEDIUM/HIGH/CRITICAL)
3. Implement mitigation if HIGH or CRITICAL
4. Add to validation checklist if structural
5. Update unit tests to prevent regression

**Critical risk definition:**
Any issue that could cause >10% capital loss or complete system failure.

---

**Document Version:** 1.0 (Phase 2.5 Bootstrap)
**Next Review:** After first 10 completed trades
**Maintained By:** Development team
