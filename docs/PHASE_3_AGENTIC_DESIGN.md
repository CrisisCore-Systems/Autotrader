# Phase 3: Agentic Intelligence System - Design Document

**Status**: 🚧 In Progress  
**Target Win Rate**: 75-85%  
**Baseline**: 60% (Phase 2.5 with memory)  
**Expected Improvement**: +15-25%

---

## 🎯 **Executive Summary**

Phase 3 implements a **full 8-agent agentic system** modeled after BounceHunter's proven architecture, adapted for penny stock gap trading. The system coordinates multiple specialized agents to make intelligent, consensus-based trading decisions with regime awareness and continuous learning.

**Key Innovation**: Multi-agent consensus replaces single-layer filtering, dramatically improving trade quality through distributed intelligence and adaptive thresholds.

---

## 📊 **Performance Evolution**

| Phase | System | Win Rate | Sample (6yr) | Key Feature |
|-------|--------|----------|--------------|-------------|
| **1.0** | Base filters | 56.4% | 94 trades | Quality gates + regime detection |
| **2.5** | Memory | 60.0% | 85 trades | Ticker-level learning + ejection |
| **3.0** | Agentic | **75-85%** | 20-30 trades | 8-agent consensus + adaptation |

**Target Improvement**: +15-25% absolute win rate improvement  
**Trade-off**: ~60-70% reduction in signal count (quality over quantity)

---

## 🏗️ **Architecture Overview**

```
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                            │
│            (Coordinates all agents, makes final decision)    │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │ CONTEXT (shared market intelligence)   │
        │  - regime: normal/high_vix/spy_stress │
        │  - vix_percentile: 0.0 - 1.0          │
        │  - is_market_hours: bool              │
        │  - is_preclose: bool                  │
        └───────────────────────────────────────┘
                            │
    ┌───────────────────────┴───────────────────────┐
    │                                               │
    v                                               v
┌────────────────┐                          ┌────────────────┐
│  1. SENTINEL   │ → Context                │  2. SCREENER   │ → Signals
│  Market Watch  │                          │  Gap Discovery │
└────────────────┘                          └────────────────┘
         │                                           │
         v                                           v
┌────────────────┐                          ┌────────────────┐
│ 3. FORECASTER  │ → Scored Signals         │ 4. RISKOFFICER │ → Approved
│ Confidence     │                          │ Memory + Risk  │
└────────────────┘                          └────────────────┘
         │                                           │
         v                                           v
┌────────────────┐                          ┌────────────────┐
│ 5. NEWSSENTRY  │ → Vetted Signals         │  6. TRADER     │ → Actions
│ Sentiment      │                          │  Execution     │
└────────────────┘                          └────────────────┘
         │                                           │
         v                                           v
┌────────────────┐                          ┌────────────────┐
│  7. HISTORIAN  │ → Recorded               │  8. AUDITOR    │ → Updated
│  Persistence   │                          │  Learning      │
└────────────────┘                          └────────────────┘
```

---

## 🤖 **Agent Responsibilities**

### **1. Sentinel Agent** (Market Watch)
**Purpose**: Monitor market conditions and timing  
**Inputs**: Market data, VIX, SPY  
**Outputs**: Context object (regime, timing, conditions)

**Responsibilities**:
- Detect market regime (normal/high_vix/spy_stress)
- Calculate VIX percentile (60-day lookback)
- Check market hours (9:30 AM - 4:00 PM ET)
- Identify pre-close period (3:00 PM+)
- Determine if conditions are suitable for gap scanning

**Integration**: Reuses existing `RegimeDetector` from bouncehunter/regime.py

**Code Pattern**:
```python
async def run(self) -> Context:
    detector = RegimeDetector(...)
    regime_state = detector.detect(as_of, ...)
    return Context(
        dt=date_str,
        regime="normal" | "high_vix" | "spy_stress",
        vix_percentile=0.0-1.0,
        spy_dist_200dma=float,
        is_market_hours=bool,
        is_preclose=bool
    )
```

---

### **2. Screener Agent** (Gap Discovery)
**Purpose**: Find and qualify gap candidates  
**Inputs**: Context, market data  
**Outputs**: List[Signal] (gap candidates)

**Responsibilities**:
- Scan for stocks with 5%+ overnight gaps
- Apply initial quality gates (liquidity, price range)
- Calculate gap metrics (size, direction, volume)
- Filter by average dollar volume (>$1M ADV)
- Generate Signal objects with metadata

**Integration**: Uses `GapScanner` from pennyhunter_scanner.py

**Code Pattern**:
```python
async def run(self, ctx: Context) -> list[Signal]:
    scanner = GapScanner(self.policy.config)
    gaps = scanner.scan(as_of=ctx.dt, min_gap_pct=0.05)
    
    signals = []
    for gap in gaps:
        if self._passes_quality_gates(gap):
            signals.append(Signal(
                ticker=gap.ticker,
                date=gap.date,
                gap_pct=gap.gap_pct,
                entry=gap.entry,
                stop=gap.stop,
                target=gap.target,
                ...
            ))
    return signals
```

---

### **3. Forecaster Agent** (Confidence Scoring)
**Purpose**: Score signal quality and confidence  
**Inputs**: List[Signal], Context  
**Outputs**: List[Signal] (filtered by confidence threshold)

**Responsibilities**:
- Calculate gem_score for each signal (technical confluence)
- Apply regime-aware thresholds (higher bar in high VIX)
- Filter signals below minimum confidence (7.0 default)
- Assign probability estimates
- Rank signals by quality

**Integration**: Uses `GemScorer` from pennyhunter_scoring.py

**Thresholds**:
- **Normal regime**: gem_score ≥ 7.0
- **High VIX regime**: gem_score ≥ 7.5
- **SPY stress regime**: gem_score ≥ 8.0

**Code Pattern**:
```python
async def run(self, signals: list[Signal], ctx: Context) -> list[Signal]:
    threshold = self._get_threshold(ctx.regime)
    scorer = GemScorer(self.policy.config)
    
    scored = []
    for sig in signals:
        gem_score = scorer.score(sig.ticker, sig.date)
        if gem_score >= threshold:
            sig.confidence = gem_score
            sig.probability = self._gem_to_probability(gem_score)
            scored.append(sig)
    
    return sorted(scored, key=lambda s: s.confidence, reverse=True)
```

---

### **4. RiskOfficer Agent** (Risk Management)
**Purpose**: Enforce position limits and memory checks  
**Inputs**: List[Signal], Context, AgenticMemory  
**Outputs**: List[Signal] (risk-approved)

**Responsibilities**:
- Check ticker memory status (ejected/monitored/active)
- Enforce max concurrent positions (5 default)
- Apply sector concentration limits (2 per sector)
- Calculate position sizing (1% normal, 0.5% high VIX)
- Validate gap quality (not too extreme)
- Apply adaptive base rate floors (40% default)

**Integration**: Uses `PennyHunterMemory` for ticker checks, `QualityGates` for filters

**Veto Conditions**:
- Ticker ejected by memory (<35% win rate)
- Ticker monitored and in high VIX regime
- Portfolio at max concurrent positions
- Sector concentration exceeded
- Gap too large (>25%) or too small (<5%)
- Base rate below floor after ≥10 trades

**Code Pattern**:
```python
async def run(self, signals: list[Signal], ctx: Context) -> list[Signal]:
    approved = []
    
    for sig in signals:
        # Memory check
        can_trade, reason, stats = self.memory.should_trade_ticker(sig.ticker)
        if not can_trade:
            sig.vetoed = True
            sig.veto_reason = f"Memory: {reason}"
            continue
        
        # Adaptive threshold check
        if stats and stats['total_trades'] >= 10:
            if stats['win_rate'] < self.policy.base_rate_floor:
                sig.vetoed = True
                sig.veto_reason = f"Base rate {stats['win_rate']:.1%} < floor"
                continue
        
        # Portfolio limits check
        if self._count_open_positions() >= self.policy.max_concurrent:
            sig.vetoed = True
            sig.veto_reason = "Max concurrent positions reached"
            break
        
        approved.append(sig)
    
    return approved
```

---

### **5. NewsSentry Agent** (Sentiment Analysis)
**Purpose**: Veto signals with adverse news catalysts  
**Inputs**: List[Signal]  
**Outputs**: List[Signal] (news-vetted)

**Responsibilities**:
- Check for negative news headlines (optional)
- Identify SEC investigations, fraud, bankruptcy
- Detect guidance cuts, restatements
- Flag unusual insider selling
- Screen for negative sentiment spikes

**Integration**: Optional - can integrate with news APIs or run as stub

**Severe Terms** (veto triggers):
- "SEC investigation", "fraud", "restatement"
- "chapter 11", "bankruptcy", "delisting"
- "guidance cut", "miss", "probe"

**Code Pattern**:
```python
async def run(self, signals: list[Signal]) -> list[Signal]:
    if not self.policy.news_veto_enabled:
        return signals  # Pass-through if disabled
    
    vetted = []
    for sig in signals:
        news = self._check_news(sig.ticker, lookback_days=3)
        if self._has_severe_news(news):
            sig.vetoed = True
            sig.veto_reason = f"Adverse news: {news.headline[:50]}"
        else:
            vetted.append(sig)
    
    return vetted
```

---

### **6. Trader Agent** (Execution)
**Purpose**: Generate trade actions and execute orders  
**Inputs**: List[Signal], Context  
**Outputs**: List[Action] (trade plans)

**Responsibilities**:
- Calculate position sizes (% of portfolio)
- Generate bracket orders (entry + stop + target)
- Place paper trades or send to broker
- Create Action objects with execution metadata
- Log all trade decisions

**Integration**: Uses `BrokerAPI` for live trading (optional)

**Position Sizing**:
- **Normal regime**: 1.0% per position
- **High VIX regime**: 0.5% per position
- **SPY stress regime**: 0.25% per position

**Code Pattern**:
```python
async def run(self, signals: list[Signal], ctx: Context) -> list[Action]:
    size_pct = self._get_size_pct(ctx.regime)
    actions = []
    
    for sig in signals:
        action = Action(
            signal_id=f"{sig.ticker}_{sig.date}",
            ticker=sig.ticker,
            action="BUY" if self.policy.live_trading else "ALERT",
            size_pct=size_pct,
            entry=sig.entry,
            stop=sig.stop,
            target=sig.target,
            confidence=sig.confidence,
            regime=ctx.regime,
            reason="Approved by all 8 agents"
        )
        
        # If live trading, place order
        if self.policy.live_trading and self.broker:
            shares = self._calculate_shares(size_pct, sig.entry)
            order_id = self.broker.place_bracket_order(
                ticker=sig.ticker,
                quantity=shares,
                entry_price=sig.entry,
                stop_price=sig.stop,
                target_price=sig.target
            )
            action.order_id = order_id
        
        actions.append(action)
    
    return actions
```

---

### **7. Historian Agent** (Persistence)
**Purpose**: Record all signals, actions, and outcomes  
**Inputs**: Signals, Actions, Context  
**Outputs**: bool (success)

**Responsibilities**:
- Store signals to `agentic_signals` table
- Record fills to `agentic_fills` table
- Log agent votes (which agents approved/vetoed)
- Store context metadata (regime, VIX, timing)
- Integrate with base PennyHunterMemory

**Database Schema**:
```sql
CREATE TABLE agentic_signals (
    signal_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    gap_pct REAL NOT NULL,
    confidence REAL NOT NULL,
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL NOT NULL,
    regime TEXT NOT NULL,
    sentinel_vote INTEGER,
    screener_vote INTEGER,
    forecaster_vote INTEGER,
    riskofficer_vote INTEGER,
    newssentry_vote INTEGER,
    trader_vote INTEGER,
    vetoed INTEGER DEFAULT 0,
    veto_reason TEXT
);

CREATE TABLE agentic_fills (
    fill_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    shares REAL NOT NULL,
    size_pct REAL NOT NULL,
    regime TEXT NOT NULL,
    is_paper INTEGER DEFAULT 1,
    FOREIGN KEY (signal_id) REFERENCES agentic_signals(signal_id)
);

CREATE TABLE agentic_outcomes (
    outcome_id TEXT PRIMARY KEY,
    fill_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    exit_date TEXT NOT NULL,
    exit_price REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    hold_days INTEGER NOT NULL,
    return_pct REAL NOT NULL,
    hit_target INTEGER DEFAULT 0,
    hit_stop INTEGER DEFAULT 0,
    hit_time INTEGER DEFAULT 0,
    reward REAL NOT NULL,
    FOREIGN KEY (fill_id) REFERENCES agentic_fills(fill_id)
);
```

**Code Pattern**:
```python
async def run(self, signals: list[Signal], actions: list[Action], ctx: Context) -> bool:
    for sig, act in zip(signals, actions):
        # Record signal with agent votes
        signal_id = self.memory.record_signal_agentic(
            signal=sig,
            action=act,
            agent_votes={
                "sentinel": True,
                "screener": True,
                "forecaster": True,
                "riskofficer": not sig.vetoed,
                "newssentry": not sig.vetoed,
                "trader": True,
            }
        )
        
        # Record paper fill
        if not sig.vetoed:
            self.memory.record_fill_agentic(
                signal_id=signal_id,
                ticker=sig.ticker,
                entry_date=sig.date,
                entry_price=sig.entry,
                size_pct=act.size_pct,
                regime=ctx.regime,
                is_paper=True
            )
    
    return True
```

---

### **8. Auditor Agent** (Learning)
**Purpose**: Post-trade analysis and threshold adaptation  
**Inputs**: AgenticMemory  
**Outputs**: Dict[str, Any] (performance stats)

**Responsibilities**:
- Update ticker base rates in memory
- Calculate regime-specific win rates
- Adapt confidence thresholds based on results
- Identify underperforming agents (future)
- Trigger ticker ejections
- Generate performance reports

**Adaptive Logic**:
- If win rate < 70% after 20 trades → **raise confidence threshold by 0.5**
- If win rate > 85% after 20 trades → **lower threshold by 0.5**
- If ticker < 35% after 4 trades → **eject immediately**
- If ticker < 40% after 10 trades → **eject (adaptive)**

**Code Pattern**:
```python
async def run(self) -> Dict[str, Any]:
    # Update all ticker stats
    tickers = self.memory.get_all_tickers_with_outcomes()
    
    updates = []
    for ticker in tickers:
        self.memory.update_ticker_stats(ticker)
        stats = self.memory.get_ticker_stats(ticker)
        
        # Check for ejection
        if stats['total_trades'] >= 4 and stats['win_rate'] < 0.35:
            self.memory.eject_ticker(ticker, "Below 35% after 4 trades")
        elif stats['total_trades'] >= 10 and stats['win_rate'] < 0.40:
            self.memory.eject_ticker(ticker, "Below 40% after 10 trades")
        
        updates.append(stats)
    
    # Adapt global thresholds
    overall_stats = self.memory.get_overall_performance()
    if overall_stats['total_trades'] >= 20:
        if overall_stats['win_rate'] < 0.70:
            self.policy.min_confidence += 0.5
        elif overall_stats['win_rate'] > 0.85:
            self.policy.min_confidence -= 0.5
    
    return {
        "updated_tickers": len(updates),
        "overall_win_rate": overall_stats['win_rate'],
        "min_confidence": self.policy.min_confidence,
        "stats": updates
    }
```

---

## 🔄 **Orchestrator Flow**

The **Orchestrator** coordinates all 8 agents in a defined pipeline:

```python
async def run_daily_scan(self) -> Dict[str, Any]:
    """Execute full agent flow."""
    
    # 1. Sentinel: Detect market regime
    ctx = await self.sentinel.run()
    
    # 2. Screener: Find gap candidates
    signals = await self.screener.run(ctx)
    if not signals:
        return {"signals": 0, "reason": "No gaps found"}
    
    # 3. Forecaster: Score confidence
    signals = await self.forecaster.run(signals, ctx, self.policy)
    if not signals:
        return {"signals": 0, "reason": "Below confidence threshold"}
    
    # 4. RiskOfficer: Apply risk controls
    signals = await self.risk_officer.run(signals, ctx)
    if not signals:
        return {"signals": 0, "reason": "Vetoed by RiskOfficer"}
    
    # 5. NewsSentry: Check for adverse news
    signals = await self.news_sentry.run(signals)
    
    # 6. Trader: Generate actions
    actions = await self.trader.run(signals, ctx)
    
    # 7. Historian: Persist to database
    await self.historian.run(signals, actions, ctx)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "context": ctx,
        "signals": len(signals),
        "approved": len([s for s in signals if not s.vetoed]),
        "actions": actions
    }
```

---

## 📦 **Data Structures**

### **AgenticPolicy** (Configuration)
```python
@dataclass
class AgenticPolicy:
    config: Any  # PennyHunterConfig reference
    live_trading: bool = False
    min_confidence: float = 7.0  # Gem score threshold
    min_confidence_highvix: float = 7.5
    max_concurrent: int = 5
    max_per_sector: int = 2
    allow_earnings: bool = False
    risk_pct_normal: float = 0.01  # 1% per position
    risk_pct_highvix: float = 0.005  # 0.5% in high VIX
    preclose_only: bool = False
    news_veto_enabled: bool = False
    auto_adapt_thresholds: bool = True
    base_rate_floor: float = 0.40
    min_sample_size: int = 10
```

### **Context** (Market State)
```python
@dataclass
class Context:
    dt: str  # Date (YYYY-MM-DD)
    regime: str  # "normal" | "high_vix" | "spy_stress"
    vix_percentile: float  # 0.0 - 1.0
    spy_dist_200dma: float  # Distance to SPY 200 DMA
    is_market_hours: bool
    is_preclose: bool  # After 3 PM ET
```

### **Signal** (Gap Candidate)
```python
@dataclass
class Signal:
    ticker: str
    date: str
    gap_pct: float
    close: float
    entry: float
    stop: float
    target: float
    confidence: float  # Gem score
    probability: float  # Win probability estimate
    adv_usd: float  # Average dollar volume
    sector: str = "UNKNOWN"
    notes: str = ""
    vetoed: bool = False
    veto_reason: str = ""
```

### **Action** (Trade Proposal)
```python
@dataclass
class Action:
    signal_id: str
    ticker: str
    action: str  # "ALERT" | "BUY" | "VETO"
    size_pct: float
    entry: float
    stop: float
    target: float
    confidence: float
    regime: str
    reason: str = ""
    order_id: str = ""
```

---

## 🔧 **Configuration**

Add to `configs/pennyhunter.yaml`:

```yaml
agentic:
  enabled: true
  
  # Confidence thresholds (gem_score)
  min_confidence: 7.0
  min_confidence_highvix: 7.5
  min_confidence_stress: 8.0
  
  # Portfolio limits
  max_concurrent: 5
  max_per_sector: 2
  
  # Position sizing (% of portfolio)
  risk_pct_normal: 0.01    # 1% per position
  risk_pct_highvix: 0.005  # 0.5% in high VIX
  risk_pct_stress: 0.0025  # 0.25% in SPY stress
  
  # Risk controls
  allow_earnings: false
  preclose_only: false
  news_veto_enabled: false
  
  # Adaptive learning
  auto_adapt_thresholds: true
  base_rate_floor: 0.40
  min_sample_size: 10
  adapt_after_n_trades: 20
  
  # Memory integration
  use_existing_memory: true
  memory_db_path: "reports/pennyhunter_memory.db"
  agentic_db_path: "reports/pennyhunter_agentic.db"
```

---

## 📈 **Expected Performance**

### **Win Rate Projection**:

| Agent | Contribution | Mechanism |
|-------|-------------|-----------|
| Sentinel | +0-1% | Avoid high VIX gaps |
| Screener | +2-3% | Better gap quality |
| Forecaster | +3-5% | Gem score ≥7.0 filter |
| RiskOfficer | +2-3% | Memory + liquidity |
| NewsSentry | +1-2% | Avoid negative catalysts |
| Trader | +0% | Execution only |
| Historian | +0% | Recording only |
| Auditor | +2-3% | Adaptive thresholds |
| **TOTAL** | **+10-17%** | Cumulative improvement |

**Conservative Target**: 60% + 10% = **70% win rate**  
**Optimistic Target**: 60% + 17% = **77% win rate**  
**Phase 3 Goal**: **75-85% win rate**

### **Trade-off Analysis**:

| Metric | Phase 2.5 | Phase 3 (Projected) | Change |
|--------|-----------|---------------------|--------|
| Win Rate | 60.0% | **75-80%** | +15-20% |
| Sample Size (6yr) | 85 trades | **25-35 trades** | -60% |
| Profit Factor | 2.12 | **>3.5** | +65% |
| Avg Win | $9.75 | **$12+** | +23% |
| Max Drawdown | -12% | **<10%** | -17% |

**Key Insight**: Quality over quantity - fewer signals but much higher win rate.

---

## 🧪 **Validation Plan**

### **Phase 3.1: Implementation** (Day 1)
1. ✅ Study BounceHunter agentic architecture
2. ✅ Design PennyHunter adaptation
3. ⏭️ Create `pennyhunter_agentic.py` (~650 lines)
4. ⏭️ Implement all 8 agents + Orchestrator
5. ⏭️ Add agentic configuration to YAML

### **Phase 3.2: Backtesting** (Day 2)
6. ⏭️ Create `backtest_pennyhunter_agentic.py`
7. ⏭️ Replay 2019-2025 data through agents
8. ⏭️ Validate win rate 70-80%
9. ⏭️ Analyze per-agent contributions
10. ⏭️ Compare vs Phase 2.5 baseline (60%)

### **Phase 3.3: Optimization** (Day 2-3)
11. ⏭️ Tune confidence thresholds (6.5-8.0 range)
12. ⏭️ Optimize position sizing
13. ⏭️ Adjust sector caps
14. ⏭️ Refine adaptive learning rates

### **Phase 3.4: Documentation** (Day 3)
15. ⏭️ Generate Phase 3 results report
16. ⏭️ Document optimal configuration
17. ⏭️ Create architecture diagrams
18. ⏭️ Write deployment guide

### **Success Criteria**:
- ✅ Win rate: 75-85%
- ✅ Sample size: ≥20 trades (6-year)
- ✅ Profit factor: >3.0
- ✅ Statistical significance: p < 0.05
- ✅ All 8 agents operational
- ✅ Adaptive thresholds working

---

## 🚀 **Implementation Roadmap**

### **Files to Create**:
1. `src/bouncehunter/pennyhunter_agentic.py` (~650 lines)
2. `scripts/backtest_pennyhunter_agentic.py` (~450 lines)
3. `scripts/test_agentic_integration.py` (~150 lines)
4. `docs/PHASE_3_AGENTIC_RESULTS.md` (post-backtest)

### **Files to Modify**:
1. `configs/pennyhunter.yaml` (add agentic section)
2. `run_pennyhunter_paper.py` (add --agentic flag)

### **Timeline**:
- **Day 1**: Core implementation (agentic.py + config)
- **Day 2**: Backtesting + validation
- **Day 3**: Optimization + documentation

---

## 🎓 **Key Design Decisions**

### **1. Extend vs Replace Memory**
**Decision**: Extend PennyHunterMemory (composition pattern)  
**Rationale**: Preserve existing functionality, add agentic features  
**Implementation**: AgenticMemory wraps base memory, adds new tables

### **2. Parallel vs Sequential Agent Execution**
**Decision**: Sequential with async/await  
**Rationale**: Clear data flow, easier debugging, proven pattern  
**Trade-off**: Slightly slower but more reliable

### **3. Consensus vs Weighted Voting**
**Decision**: All agents must pass (any veto blocks)  
**Rationale**: Higher quality, conservative approach  
**Future**: Could add weighted voting for flexibility

### **4. Confidence Threshold Strategy**
**Decision**: Start high (7.0), adapt based on results  
**Rationale**: Quality over quantity, let system learn optimal level  
**Monitoring**: Track win rate, adjust if <70% or >85%

### **5. News Integration**
**Decision**: Optional stub, can enable later  
**Rationale**: Focus on core agents first, add news as enhancement  
**Future**: Integrate with FinViz, Yahoo Finance, or Alpha Vantage

---

## 📊 **Risk Analysis**

### **Potential Issues**:

1. **Sample Size Too Small**
   - Risk: <20 trades, statistically insignificant
   - Mitigation: Lower confidence threshold if needed
   - Monitoring: Track signal count per month

2. **Over-fitting to Historical Data**
   - Risk: 6-year backtest doesn't predict future
   - Mitigation: Out-of-sample testing, walk-forward validation
   - Monitoring: Track live paper trading performance

3. **Adaptive Thresholds Too Aggressive**
   - Risk: System adapts too quickly, unstable
   - Mitigation: Require min_sample_size before adapting
   - Monitoring: Track threshold changes over time

4. **Agent Conflicts**
   - Risk: One agent vetoes all signals
   - Mitigation: Log veto reasons, analyze per-agent contribution
   - Monitoring: Track veto rates by agent

### **Mitigation Strategy**:
- Start conservative (high thresholds)
- Validate with live paper trading
- Monitor signal count and win rate
- Adjust gradually based on data

---

## ✅ **Next Steps**

**Immediate** (Next 2 hours):
1. Create `src/bouncehunter/pennyhunter_agentic.py`
2. Implement all data classes and AgenticMemory
3. Build all 8 agents (40-60 lines each)
4. Create Orchestrator (~80 lines)

**Today** (6-8 hours):
5. Add agentic configuration to YAML
6. Create agentic backtest script
7. Run initial validation test
8. Debug and refine

**Tomorrow** (8 hours):
9. Run full 6-year backtest
10. Analyze results vs Phase 2.5
11. Tune parameters
12. Generate results report

---

**Status**: 🚧 Design Complete, Implementation Starting  
**Target**: 75-85% win rate with 8-agent consensus  
**ETA**: 2-3 days for full Phase 3 completion
