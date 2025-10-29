# Autonomous Trading Agent - Architecture Requirements & Design Decisions

## 📋 System Requirements Analysis

### 1. **Throughput Targets**

#### Agent-Specific Throughput:

**Real-Time Agents (High Frequency):**
- **Sentinel** (Market Monitor): 10 req/sec
  - Continuous market scanning
  - Price/volume change detection
  - Alert generation
  
- **RiskOfficer** (Position Monitor): 5 req/sec
  - Real-time position risk calculation
  - Stop-loss monitoring
  - Portfolio delta exposure

**Strategic Agents (Medium Frequency):**
- **Screener** (Opportunity Scanner): 1 req/min
  - BounceHunter batch scans
  - HiddenGem crypto analysis
  - Market-wide opportunity search
  
- **Forecaster** (Prediction Engine): 2 req/min
  - Price prediction for watchlist
  - Pattern matching
  - Signal validation

- **NewsSentry** (Sentiment Analysis): 1 req/min
  - News feed parsing
  - Social media sentiment
  - Earnings/event monitoring

**Execution Agents (On-Demand):**
- **Trader** (Order Execution): 10 req/min (burst)
  - Order placement
  - Fill monitoring
  - Position entry/exit

**Analytics Agents (Low Frequency):**
- **Historian** (Data Archival): 1 req/hour
  - Trade history consolidation
  - Performance metrics aggregation
  
- **Auditor** (Performance Review): 1 req/day
  - Nightly performance audit
  - Agent accuracy tracking
  - Model drift detection

**Grok Reasoning (On-Demand):**
- **Intent Parsing**: 5 req/min
- **Trade Plan Generation**: 2 req/min
- **Explanations**: 10 req/min

#### Total System Throughput:
- **Peak**: ~20 req/sec (market open, high volatility)
- **Average**: ~5 req/sec (normal trading hours)
- **Off-hours**: ~0.1 req/sec (monitoring only)

---

### 2. **Latency Tolerance**

#### Per-Agent Latency Budget:

| Agent | Max Latency | Target Latency | Critical? |
|-------|-------------|----------------|-----------|
| **Sentinel** | 100ms | 50ms | ⚠️ Yes - Stop losses |
| **RiskOfficer** | 200ms | 100ms | ⚠️ Yes - Risk mgmt |
| **Trader** | 500ms | 250ms | ⚠️ Yes - Execution |
| **Screener** | 30s | 15s | ❌ No - Background |
| **Forecaster** | 5s | 2s | ⚠️ Medium - Entry timing |
| **NewsSentry** | 10s | 5s | ❌ No - Background |
| **Historian** | 60s | 30s | ❌ No - Batch job |
| **Auditor** | 300s | 120s | ❌ No - Overnight |
| **Grok Reasoning** | 10s | 5s | ⚠️ Medium - UX |

#### Decision Cycle Latency:

**Full Agentic Cycle** (Scan → Analyze → Plan → Execute):
- **Target**: <30 seconds
- **Maximum**: <60 seconds
- **Critical Path**: <5 seconds (emergency stop-loss)

**Breakdown:**
```
1. Market Event Detection:    50ms  (Sentinel)
2. Signal Generation:          2s   (Screener/Forecaster)
3. Risk Assessment:            200ms (RiskOfficer)
4. Grok Reasoning:             5s   (Trade plan + explanation)
5. Human Approval (optional):  Variable (0s auto, 300s manual)
6. Order Execution:            500ms (Trader)
7. Confirmation & Logging:     100ms (Historian)
---------------------------------------------------
Total (Auto):                  ~8s
Total (Manual Approval):       ~308s (5 min)
```

---

### 3. **Hardware Budget**

#### Current Setup (Development):
- **Local Development**: Windows PC with Python 3.13.9
- **API Server**: FastAPI on localhost:8000
- **Database**: SQLite (AgentMemory)
- **Cache**: Disk-based pickle files
- **LLM**: Local Ollama (CPU-only, no GPU required)
- **Cost**: $0/month

#### Production Target (100% Local, No Cloud):

**Local Components** (Single Machine):
- **All Agents**: Local Python processes (Sentinel, Screener, Forecaster, etc.)
- **LLM Inference**: Ollama with CPU-optimized quantized models
  - Phi-3 Mini (3.8B Q4): Fast parsing ≤1s, ~2 GB RAM
  - Qwen2.5-7B (Q4): Default reasoning 2-5s, ~5 GB RAM
  - Mistral-7B (Q4): Backup generalist 2-5s, ~4 GB RAM
- **Database**: Local SQLite or PostgreSQL
- **Hardware**: Mid-range workstation (no GPU needed)
  - CPU: 8 cores (agent parallelization + LLM inference)
  - RAM: 24GB (16GB system + 8GB for models)
  - Storage: 256GB SSD (fast I/O for cache + 11GB models)
  - **Cost**: $0/month (existing hardware)

**LLM Performance on CPU** (AVX2-enabled):
- 3.8B Q4: 25-60 tok/s
- 7B Q4: 10-30 tok/s
- Total LLM load: <10 req/min typical (non-critical path only)

**Data Providers** (Free Tier):
- yfinance, CoinGecko, Dexscreener, Blockscout (free)
- Twitter API (basic tier or free public access)
- Reddit API (free public access)
- **Cost**: $0/month

#### Total Hardware Budget:
- **Development**: $0/month
- **Production**: $0/month (100% local, no cloud costs)
- **Optional Cloud**: $50/month (cloud VM if needed for uptime)
- **Enterprise**: $500-1000/month (dedicated servers, premium data)

#### Critical Path Latency (No LLM):
- **Sentinel**: <100ms (pure code, no LLM)
- **RiskOfficer**: <200ms (pure code, no LLM)
- **Trader**: <500ms (pure code, no LLM)

#### Non-Critical Path (LLM-Enhanced):
- **NewsSentry**: 1-2s (Phi-3 Mini for headline analysis)
- **Forecaster**: 2-5s (Qwen2.5-7B for trade plans)
- **Auditor**: 3-5s (Qwen2.5-7B for calibration)
- **TradingCopilot**: 1-5s (intent parsing + reasoning)

---

### 4. **Confidence & Error Rate Tolerances**

#### Automated Decision Thresholds:

| Decision Type | Min Confidence | Max Error Rate | Human Override |
|---------------|----------------|----------------|----------------|
| **Auto-Execute Trade** | 85% | 5% | ✅ Always available |
| **Auto Stop-Loss** | 99% | 1% | ⚠️ Emergency only |
| **Auto Position Sizing** | 80% | 10% | ✅ Review daily |
| **Auto Alert Creation** | 70% | 20% | ❌ No override |
| **Auto Scan Filtering** | 60% | 30% | ❌ No override |

#### Risk Management Boundaries:

**Portfolio-Level Constraints:**
```python
RISK_LIMITS = {
    "max_position_size_pct": 10,        # No single position > 10% portfolio
    "max_daily_loss_pct": 2,            # Stop all trading if -2% daily
    "max_portfolio_beta": 1.5,          # Limit overall market exposure
    "min_cash_reserve_pct": 20,         # Always keep 20% cash
    "max_sector_concentration": 30,     # No sector > 30% portfolio
}
```

**Trade-Level Constraints:**
```python
TRADE_LIMITS = {
    "min_confidence_auto": 0.85,        # 85% for auto-execution
    "min_confidence_notify": 0.70,      # 70% for notification
    "max_risk_per_trade_pct": 1,        # Risk max 1% per trade
    "min_reward_risk_ratio": 2.0,       # Target 2:1 reward:risk minimum
    "max_holding_period_days": 30,      # Force review after 30 days
}
```

**Agent Accuracy Monitoring:**
```python
AGENT_PERFORMANCE_THRESHOLDS = {
    "forecaster_min_accuracy": 0.65,    # Forecaster must be >65% accurate
    "screener_min_hit_rate": 0.55,      # Screener signals >55% win rate
    "risk_officer_max_breaches": 0.05,  # RiskOfficer <5% risk breaches
    "auditor_review_frequency": "daily", # Daily performance review
}
```

#### Confidence Calibration Strategy:

**Dynamic Confidence Adjustment:**
- Track actual outcome vs predicted confidence
- If overconfident (actual < predicted): Reduce future confidence
- If underconfident (actual > predicted): Increase future confidence
- Update calibration weekly via Auditor

**Example:**
```
Predicted 80% win probability → Actual 60% win rate
→ Apply -15% confidence penalty to similar setups
→ New threshold: 65% confidence (80% × 0.8 + actual variance)
```

---

### 5. **Licensing Requirements**

#### Current Stack Licenses:

**Free/Open Source (Commercial OK):**
- ✅ **Python**: PSF License (commercial friendly)
- ✅ **FastAPI**: MIT License
- ✅ **yfinance**: Apache 2.0
- ✅ **pandas/numpy**: BSD License
- ✅ **scikit-learn**: BSD License
- ✅ **SQLite**: Public Domain

**Paid Services (Commercial Terms):**
- ⚠️ **Grok API (X.AI)**: Review Terms of Service for commercial use
  - Likely requires commercial license
  - Cost: Pay-per-use (tokens)
  - **Action**: Review X.AI commercial terms
  
- ⚠️ **Twitter API**: Review Developer Agreement
  - Basic/Free tier: Rate limits
  - Pro/Enterprise: Commercial use allowed
  - **Action**: Verify commercial data usage allowed

**Data Provider Licenses:**
- ✅ **CoinGecko**: Free tier for commercial use (with attribution)
- ✅ **Reddit Public API**: Commercial use allowed (rate limits)
- ⚠️ **Real-time stock data**: May require paid exchange feeds
  - Delayed data (15-min): Free
  - Real-time: Requires exchange licenses (NASDAQ, NYSE fees)
  - **Action**: Confirm data usage rights with users

#### VoidBloom Integration Licensing:

**If VoidBloom is proprietary/commercial:**
- **Question**: What is VoidBloom's license?
  - If MIT/Apache: ✅ Commercial use OK
  - If GPL: ⚠️ May require open-sourcing trading system
  - If proprietary: ⚠️ Need commercial license agreement

**Recommended Approach:**
1. **Core Trading System**: Keep MIT/Apache licensed
2. **VoidBloom Integration**: Modular plugin architecture
3. **Commercial Deployment**: Review all third-party licenses
4. **Client Distribution**: Provide clear license documentation

#### License Compliance Checklist:

```markdown
- [ ] Review X.AI Grok API terms for commercial trading use
- [ ] Verify Twitter API commercial data usage rights
- [ ] Confirm yfinance data usage for automated trading
- [ ] Check VoidBloom license compatibility
- [ ] Document all third-party license requirements
- [ ] Add LICENSE file to repository
- [ ] Include attribution for open-source components
- [ ] Review broker API (IBKR) terms for automated trading
```

---

### 6. **Fail-Over & Agent Orchestration**

#### Orchestration Architecture:

**Primary Orchestrator**: `TradingCopilot`
- Central coordinator for all agents
- Manages agent lifecycle (start, stop, restart)
- Routes intents to appropriate agents
- Maintains conversation and decision history

**Agent Communication Pattern**:
```
┌─────────────────────────────────────────────────────────┐
│                   TradingCopilot                        │
│              (Central Orchestrator)                      │
└─────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        v                v                v
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Sentinel │     │ Screener │     │  Trader  │
  └──────────┘     └──────────┘     └──────────┘
        │                │                │
        └────────────────┴────────────────┘
                         │
                         v
                 ┌──────────────┐
                 │ AgentMemory  │
                 │  (SQLite)    │
                 └──────────────┘
```

#### Fail-Over Strategy:

**Agent-Level Fail-Over:**

1. **Health Checks** (Every 30 seconds):
```python
async def check_agent_health(agent: BaseAgent) -> bool:
    """Check if agent is responsive."""
    try:
        response = await agent.health_check(timeout=5.0)
        return response.status == "healthy"
    except TimeoutError:
        logger.error(f"{agent.name} timed out")
        return False
    except Exception as e:
        logger.error(f"{agent.name} error: {e}")
        return False
```

2. **Auto-Restart** (On failure):
```python
async def restart_agent(agent: BaseAgent):
    """Restart failed agent."""
    logger.warning(f"Restarting {agent.name}")
    await agent.stop()
    await asyncio.sleep(5)  # Backoff
    await agent.start()
    
    # If restart fails 3 times, move to degraded mode
    if agent.restart_count > 3:
        logger.critical(f"{agent.name} failed permanently")
        await enter_degraded_mode(agent)
```

3. **Degraded Mode** (When agent fails):
```python
DEGRADED_MODE_FALLBACKS = {
    "Sentinel": "Use cached last-known prices, disable real-time monitoring",
    "Screener": "Use cached scan results from last successful run",
    "Forecaster": "Fall back to simple technical indicators (RSI, MA)",
    "RiskOfficer": "Use conservative static risk limits",
    "NewsSentry": "Disable news-based signals, rely on price only",
    "Trader": "CRITICAL - Manual override required, no automated trades",
    "Historian": "Queue writes, batch when restored",
    "Auditor": "Skip current cycle, run on next schedule",
    "Grok": "Fall back to rule-based intent parsing (regex)",
}
```

**System-Level Fail-Over:**

**Scenario 1: Database Failure**
```python
if not db.is_available():
    # Fall back to in-memory state
    logger.critical("Database unavailable, using in-memory fallback")
    memory = InMemoryAgentMemory()
    
    # Persist to disk as JSON backup
    backup_path = "./data/emergency_backup.json"
    asyncio.create_task(persist_to_json(memory, backup_path))
```

**Scenario 2: API Server Crash**
```python
# Run agents in standalone mode
if api_server.crashed:
    logger.critical("API server down, running agents in standalone mode")
    
    # Continue critical agents
    await sentinel.run_standalone()
    await risk_officer.run_standalone()
    await trader.run_standalone()
    
    # Disable non-critical agents
    screener.pause()
    news_sentry.pause()
```

**Scenario 3: Grok API Unavailable**
```python
if grok.is_unavailable():
    # Fall back to rule-based reasoning
    logger.warning("Grok unavailable, using rule-based fallback")
    intent_parser = RuleBasedIntentParser()
    
    # Disable conversational features
    conversational_mode = False
    
    # Continue automated trading with cached logic
    use_cached_trade_plans = True
```

#### Circuit Breaker Pattern:

**Prevent cascading failures:**
```python
class CircuitBreaker:
    """Prevent cascading failures in agent system."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        
        if self.state == "OPEN":
            if time.time() - self.last_failure > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpen("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.critical(f"Circuit breaker OPEN after {self.failure_count} failures")
```

---

### 7. **Logging & Audit Trail (MemoryWear Narrative Style)**

#### Memory Vector Architecture:

Every trade is a **"memory vector"** with rich metadata:

```python
@dataclass
class TradeMemoryVector:
    """
    Trade as a memory vector - captures complete context.
    Inspired by MemoryWear narrative embeddings.
    """
    
    # Identity
    trade_id: str
    timestamp: datetime
    ticker: str
    
    # Action
    action: str  # BUY, SELL, HOLD
    quantity: int
    entry_price: float
    exit_price: Optional[float]
    
    # Decision Context (The "Why")
    agent_signals: List[Dict[str, Any]]  # All 8 agents' votes
    grok_reasoning: str  # Natural language explanation
    confidence: float
    intent: TradingIntent  # Original user request
    market_regime: str  # TRENDING_UP, CHOPPY, VOLATILE, etc.
    
    # Outcome
    pnl: Optional[float]
    pnl_pct: Optional[float]
    holding_period: Optional[timedelta]
    exit_reason: Optional[str]  # TARGET_HIT, STOP_LOSS, MANUAL, etc.
    
    # Embeddings (For Similarity Search)
    technical_embedding: np.ndarray  # RSI, MACD, volume pattern
    sentiment_embedding: np.ndarray  # News, social media sentiment
    narrative_embedding: np.ndarray  # Grok's reasoning embedded
    
    # Metadata
    agent_versions: Dict[str, str]  # Which model versions were used
    model_cache_hash: str  # BounceHunter model version
    risk_score: float
    portfolio_context: Dict[str, Any]  # Portfolio state at time of trade
    
    # Learning Signals (For Future Improvement)
    predicted_outcome: float  # What we expected
    actual_outcome: float  # What actually happened
    prediction_error: float  # actual - predicted
    lessons_learned: List[str]  # Post-trade analysis
    
    # Lineage (Trade Genealogy)
    similar_trades: List[str]  # Trade IDs of similar patterns
    parent_strategy: str  # BOUNCEHUNTER, HIDDENGEM, etc.
    pattern_match_score: float  # How similar to historical winners


# Storage Schema
class TradeMemoryStore:
    """
    Store trade memory vectors with full narrative context.
    Enables semantic search, pattern matching, and causal analysis.
    """
    
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        """Create memory vector storage tables."""
        
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS trade_memories (
            trade_id TEXT PRIMARY KEY,
            timestamp DATETIME,
            ticker TEXT,
            action TEXT,
            quantity INTEGER,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            pnl_pct REAL,
            holding_period_seconds INTEGER,
            
            -- Decision context
            confidence REAL,
            market_regime TEXT,
            risk_score REAL,
            
            -- Embeddings (stored as JSON for SQLite)
            technical_embedding TEXT,
            sentiment_embedding TEXT,
            narrative_embedding TEXT,
            
            -- Metadata
            agent_signals TEXT,  -- JSON
            grok_reasoning TEXT,
            intent_raw TEXT,
            portfolio_context TEXT,  -- JSON
            
            -- Outcome
            exit_reason TEXT,
            predicted_outcome REAL,
            actual_outcome REAL,
            prediction_error REAL,
            
            -- Learning
            lessons_learned TEXT,  -- JSON list
            similar_trades TEXT,   -- JSON list of IDs
            pattern_match_score REAL,
            
            -- Versioning
            agent_versions TEXT,  -- JSON
            model_cache_hash TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Index for fast similarity search
        self.db.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticker_timestamp 
        ON trade_memories(ticker, timestamp)
        """)
        
        self.db.execute("""
        CREATE INDEX IF NOT EXISTS idx_pattern_match 
        ON trade_memories(pattern_match_score DESC)
        """)
    
    def store_memory(self, memory: TradeMemoryVector):
        """Store a trade memory vector."""
        
        self.db.execute("""
        INSERT INTO trade_memories VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            memory.trade_id,
            memory.timestamp,
            memory.ticker,
            memory.action,
            memory.quantity,
            memory.entry_price,
            memory.exit_price,
            memory.pnl,
            memory.pnl_pct,
            memory.holding_period.total_seconds() if memory.holding_period else None,
            memory.confidence,
            memory.market_regime,
            memory.risk_score,
            json.dumps(memory.technical_embedding.tolist()),
            json.dumps(memory.sentiment_embedding.tolist()),
            json.dumps(memory.narrative_embedding.tolist()),
            json.dumps(memory.agent_signals),
            memory.grok_reasoning,
            memory.intent.raw_message,
            json.dumps(memory.portfolio_context),
            memory.exit_reason,
            memory.predicted_outcome,
            memory.actual_outcome,
            memory.prediction_error,
            json.dumps(memory.lessons_learned),
            json.dumps(memory.similar_trades),
            memory.pattern_match_score,
            json.dumps(memory.agent_versions),
            memory.model_cache_hash,
        ))
        self.db.commit()
    
    def find_similar_trades(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> List[TradeMemoryVector]:
        """
        Find similar past trades using cosine similarity.
        This enables analogical reasoning: "Similar to that AAPL trade last month"
        """
        
        # Retrieve all embeddings
        cursor = self.db.execute("""
        SELECT trade_id, narrative_embedding, technical_embedding 
        FROM trade_memories
        """)
        
        similarities = []
        for row in cursor:
            trade_id, narrative_emb, technical_emb = row
            
            # Compute cosine similarity
            narrative_vec = np.array(json.loads(narrative_emb))
            technical_vec = np.array(json.loads(technical_emb))
            
            # Weighted combination
            similarity = (
                0.6 * cosine_similarity(query_embedding, narrative_vec) +
                0.4 * cosine_similarity(query_embedding, technical_vec)
            )
            
            if similarity >= min_similarity:
                similarities.append((trade_id, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Retrieve full memories
        result = []
        for trade_id, score in similarities[:top_k]:
            memory = self.get_memory(trade_id)
            result.append(memory)
        
        return result
    
    def get_memory(self, trade_id: str) -> TradeMemoryVector:
        """Retrieve a trade memory by ID."""
        # Implementation: deserialize from database
        pass
```

#### Audit Trail Requirements:

**Every Decision Logged:**
```python
class DecisionAuditLog:
    """
    Comprehensive audit log for every agent decision.
    Supports forensic analysis and regulatory compliance.
    """
    
    @dataclass
    class DecisionEntry:
        decision_id: str
        timestamp: datetime
        agent_name: str
        decision_type: str  # SCAN, SIGNAL, TRADE, RISK_CHECK, etc.
        
        # Input context
        input_data: Dict[str, Any]
        market_conditions: Dict[str, Any]
        
        # Decision
        output: Any
        confidence: float
        reasoning: str
        
        # Execution
        execution_time_ms: float
        success: bool
        error: Optional[str]
        
        # Traceability
        user_id: Optional[str]
        session_id: str
        parent_decision_id: Optional[str]  # For decision chains
    
    def log_decision(self, entry: DecisionEntry):
        """Log a single decision with full context."""
        
        # Store in database
        self.db.store_decision(entry)
        
        # Stream to audit file
        logger.info(f"[AUDIT] {entry.agent_name}: {entry.decision_type} "
                   f"(confidence={entry.confidence:.2f}, "
                   f"time={entry.execution_time_ms:.1f}ms)")
        
        # If critical decision, also log to separate file
        if entry.decision_type in ["TRADE", "STOP_LOSS", "RISK_BREACH"]:
            self.critical_logger.warning(json.dumps(entry.__dict__, default=str))
```

**Narrative Generation:**
```python
async def generate_trade_narrative(memory: TradeMemoryVector) -> str:
    """
    Generate human-readable narrative of trade.
    Similar to MemoryWear's contextual storytelling.
    """
    
    narrative = f"""
    ### Trade Story: {memory.ticker} on {memory.timestamp.strftime('%Y-%m-%d')}
    
    **The Setup:**
    {memory.grok_reasoning}
    
    **Agent Consensus:**
    {format_agent_signals(memory.agent_signals)}
    
    **Market Conditions:**
    - Regime: {memory.market_regime}
    - Risk Score: {memory.risk_score:.2f}
    - Confidence: {memory.confidence*100:.1f}%
    
    **The Trade:**
    - Action: {memory.action}
    - Entry: ${memory.entry_price:.2f}
    - Quantity: {memory.quantity} shares
    - Total: ${memory.entry_price * memory.quantity:,.2f}
    
    **The Outcome:**
    - Exit: ${memory.exit_price:.2f}
    - P&L: ${memory.pnl:,.2f} ({memory.pnl_pct:+.2f}%)
    - Holding Period: {memory.holding_period}
    - Exit Reason: {memory.exit_reason}
    
    **Lessons Learned:**
    {format_lessons(memory.lessons_learned)}
    
    **Similar Past Trades:**
    {format_similar_trades(memory.similar_trades)}
    """
    
    return narrative
```

---

## 🎯 Summary: Architecture Decisions

| Requirement | Decision | Rationale |
|-------------|----------|-----------|
| **Throughput** | 5-20 req/sec peak | Matches typical day trader activity |
| **Latency** | <8s full cycle, <100ms critical | Fast enough for manual trading, sub-second for stops |
| **Hardware** | $70-100/month hybrid | Local critical path + cloud scalable jobs |
| **Confidence** | 85% for auto-exec | High bar for autonomous decisions |
| **Licensing** | MIT/Apache core + paid APIs | Commercial-friendly open source |
| **Fail-Over** | Circuit breakers + degraded mode | Graceful degradation, never lose money |
| **Audit** | Memory vectors + narrative logs | Full traceability + semantic search |

---

## 📝 Implementation Checklist

- [ ] Implement health checks for all agents
- [ ] Add circuit breaker to critical paths
- [ ] Create TradeMemoryVector schema in AgentMemory
- [ ] Build DecisionAuditLog system
- [ ] Add embedding generation for narrative search
- [ ] Implement fail-over logic for each agent
- [ ] Set up monitoring dashboard (latency, throughput, errors)
- [ ] Create trade narrative generator
- [ ] Add confidence calibration tracking
- [ ] Review all third-party licenses
- [ ] Document risk limits in configuration
- [ ] Build degraded mode fallbacks

---

**Next Steps:**
1. Add health monitoring to agents
2. Implement memory vector storage
3. Build audit trail system
4. Test fail-over scenarios
5. Deploy to production with monitoring
