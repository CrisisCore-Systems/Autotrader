# Phase 9: LLM-Driven Decision Pipeline Specification

**Date:** October 24, 2025  
**Phase:** 9 - Meta-Orchestration and Guardrail Enforcement  
**Status:** Specification  

---

## Executive Summary

Phase 9 introduces an **LLM-driven meta-orchestration layer** that sits above Phase 8's strategy logic. The LLM acts as an intelligent decision assistant that:

- ✅ Evaluates pre-trade conditions (market regime, liquidity, costs)
- ✅ Selects optimal playbooks based on market features
- ✅ Generates execution plans constrained by hard risk rules
- ✅ Performs post-trade journaling and anomaly detection

**Critical Design Principle:** The LLM **cannot override** hard limits. All actions require programmatic validation. This is a **guardrails-first** architecture.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     LLM Meta-Orchestrator                        │
│  (Reasoning, Planning, Anomaly Detection - NO LIMIT OVERRIDE)   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────┐
        │         Guardrails Layer                │
        │  (Schema Validation, Hard Limits)       │
        └─────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 8: Strategy Logic                       │
│  (Signal Generation → Sizing → Risk → Portfolio → Execution)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                        Market Data
```

### Role Separation

| Component | Role | Can Override Limits? |
|-----------|------|---------------------|
| **LLM Orchestrator** | Meta-reasoning, playbook selection, anomaly detection | ❌ NO |
| **Guardrails** | Schema validation, limit enforcement, action validation | ❌ NO |
| **Phase 8 Strategy** | Signal generation, sizing, risk controls | ✅ YES (within configured limits) |

---

## LLM Tools

### 1. Pre-Trade Checklist

**Purpose:** Evaluate whether conditions are favorable for trading

**Inputs:**
- Current market regime (volatility, trend, correlation)
- Liquidity metrics (bid-ask spread, order book depth)
- Transaction costs vs estimated edge
- Risk limit headroom (daily loss budget remaining, position capacity)
- Recent performance metrics (win rate, Sharpe ratio)

**LLM Task:**
1. Analyze market regime features
2. Compare edge vs costs
3. Check risk capacity
4. Recommend: PROCEED / CAUTION / HALT

**Output Schema:**
```json
{
  "decision": "PROCEED" | "CAUTION" | "HALT",
  "confidence": 0.0-1.0,
  "reasoning": "string",
  "risks_identified": ["string"],
  "market_regime": "trending_high_vol" | "mean_reverting_low_vol" | ...,
  "edge_vs_cost_ratio": float,
  "risk_headroom_pct": float
}
```

**Guardrails:**
- Cannot force trades when risk limits breached
- Cannot ignore market halts
- Must respect Phase 8 circuit breakers

---

### 2. Playbook Selector

**Purpose:** Choose optimal trading horizon and model based on regime

**Inputs:**
- Market regime features (volatility, autocorrelation, microstructure)
- Available models (LSTM, GRU, TCN, Transformer, Online)
- Recent model performance by regime
- Current positions and portfolio state

**LLM Task:**
1. Identify current market regime
2. Match regime to best-performing model/horizon
3. Consider portfolio diversification
4. Recommend playbook configuration

**Output Schema:**
```json
{
  "selected_model": "LSTM" | "GRU" | "TCN" | "Transformer" | "Online",
  "horizon": "1m" | "5m" | "15m" | "1h",
  "confidence": 0.0-1.0,
  "reasoning": "string",
  "regime_match_score": float,
  "historical_performance": {
    "win_rate": float,
    "sharpe": float,
    "sample_size": int
  },
  "fallback_model": "string"
}
```

**Guardrails:**
- Must select from pre-approved models only
- Cannot disable risk controls
- Must maintain minimum diversification

---

### 3. Execution Planner (Reasoning-to-Policy)

**Purpose:** Generate execution plan constrained by hard risk rules

**Inputs:**
- Signal from Phase 8 (direction, confidence, size)
- Current portfolio state
- Risk limits (position size, exposure, correlation)
- Market microstructure (VWAP, arrival price, slippage estimate)
- LLM playbook selection

**LLM Task:**
1. Review Phase 8 signal and constraints
2. Consider execution tactics (timing, splitting, aggression)
3. Evaluate trade-offs (latency vs adverse selection)
4. Generate execution plan respecting ALL hard limits

**Output Schema:**
```json
{
  "action": "EXECUTE" | "DEFER" | "REJECT",
  "execution_plan": {
    "order_type": "MARKET" | "LIMIT" | "TWAP" | "VWAP",
    "urgency": "immediate" | "patient" | "passive",
    "split_strategy": "single" | "iceberg" | "pov",
    "limit_price": float | null,
    "time_horizon_seconds": int
  },
  "reasoning": "string",
  "risk_assessment": {
    "expected_slippage_bps": float,
    "adverse_selection_risk": "low" | "medium" | "high",
    "market_impact_estimate": float
  },
  "constraint_checks": {
    "position_size_ok": bool,
    "risk_limits_ok": bool,
    "portfolio_constraints_ok": bool,
    "correlation_ok": bool
  }
}
```

**Guardrails:**
- **CRITICAL:** Cannot execute if any constraint_check is false
- Cannot modify position sizes beyond Phase 8 limits
- Cannot override circuit breakers or daily loss limits
- All actions logged and auditable

---

### 4. Post-Trade Journal

**Purpose:** Analyze trade outcomes and detect anomalies

**Inputs:**
- Trade execution results (fill price, slippage, P&L)
- Pre-trade prediction vs actual outcome
- Market conditions during execution
- Historical similar trades

**LLM Task:**
1. Compare predicted vs actual performance
2. Identify anomalies (excessive slippage, unexpected P&L)
3. Detect regime changes or model drift
4. Generate insights for future decisions

**Output Schema:**
```json
{
  "anomalies_detected": ["string"],
  "performance_assessment": {
    "predicted_pnl": float,
    "actual_pnl": float,
    "variance_explanation": "string",
    "slippage_vs_expected_bps": float
  },
  "insights": ["string"],
  "recommended_actions": [
    {
      "action": "retrain_model" | "adjust_limits" | "review_strategy",
      "priority": "high" | "medium" | "low",
      "reasoning": "string"
    }
  ],
  "regime_shift_detected": bool,
  "model_drift_score": float
}
```

**Guardrails:**
- Recommendations only (cannot auto-execute)
- Must flag for human review if critical anomalies
- Cannot modify past trade records

---

## Prompt Engineering

### Deterministic Templates

All LLM prompts use deterministic templates with structured outputs:

```python
PRETRADE_TEMPLATE = """
You are a trading risk analyst. Analyze the following pre-trade conditions:

Market Regime:
- Volatility: {volatility:.4f}
- Trend strength: {trend_strength:.4f}
- Correlation regime: {correlation_regime}

Liquidity:
- Bid-ask spread: {spread_bps:.2f} bps
- Order book depth: ${depth:,.0f}

Cost vs Edge:
- Estimated edge: {edge_bps:.2f} bps
- Transaction cost: {cost_bps:.2f} bps
- Edge/Cost ratio: {ratio:.2f}

Risk Headroom:
- Daily loss used: {daily_loss_used:.1%} of limit
- Position slots: {used}/{max} used
- Correlation budget: {corr_used:.1%} used

Recent Performance:
- Win rate (20 trades): {win_rate:.1%}
- Sharpe ratio (30d): {sharpe:.2f}

TASK: Should we proceed with new trades?

Respond ONLY with valid JSON matching this schema:
{
  "decision": "PROCEED" | "CAUTION" | "HALT",
  "confidence": 0.0-1.0,
  "reasoning": "max 200 chars",
  "risks_identified": ["risk1", "risk2"],
  "market_regime": "string",
  "edge_vs_cost_ratio": float,
  "risk_headroom_pct": float
}

CRITICAL: You cannot override risk limits. If limits are breached, you MUST return HALT.
"""
```

### JSON-Only Outputs

All LLM responses must:
- Be valid JSON
- Match predefined schema
- Include confidence scores
- Provide reasoning (limited length)
- Pass schema validation before use

---

## Safety Architecture

### Layer 1: Hard Limits (Unoverridable)

```python
HARD_LIMITS = {
    'max_daily_loss': 10000,  # LLM cannot change
    'max_position_size': 100000,  # LLM cannot change
    'max_leverage': 3.0,  # LLM cannot change
    'circuit_breaker_losses': 5,  # LLM cannot change
    'max_correlation': 0.70,  # LLM cannot change
}
```

### Layer 2: Schema Validation

Every LLM output passes through Pydantic validation:

```python
from pydantic import BaseModel, Field, validator

class PreTradeChecklistOutput(BaseModel):
    decision: Literal["PROCEED", "CAUTION", "HALT"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200)
    risks_identified: List[str]
    market_regime: str
    edge_vs_cost_ratio: float
    risk_headroom_pct: float = Field(ge=0.0, le=1.0)
    
    @validator('decision')
    def validate_decision_logic(cls, v, values):
        # If risk headroom < 10%, must be HALT
        if values.get('risk_headroom_pct', 1.0) < 0.10:
            assert v == 'HALT', "Must HALT when risk headroom < 10%"
        return v
```

### Layer 3: Action Validation

Before any LLM-recommended action:

```python
def validate_llm_action(action: dict, current_state: StrategyState) -> bool:
    """Programmatic validation - LLM cannot bypass."""
    
    # Check hard limits
    if current_state.daily_loss >= HARD_LIMITS['max_daily_loss']:
        return False
    
    # Check circuit breaker
    if risk_manager.circuit_breaker.is_halted():
        return False
    
    # Validate against Phase 8 constraints
    if not strategy.check_trade_allowed(action['symbol'], action['size']):
        return False
    
    return True
```

### Layer 4: Audit Trail

Every LLM interaction logged:

```python
LLM_AUDIT_LOG = {
    'timestamp': datetime,
    'tool': 'pretrade_checklist',
    'input_hash': sha256,
    'output': json,
    'validation_result': bool,
    'action_taken': str,
    'override_attempted': bool,  # Flag if LLM tried to bypass
    'latency_ms': float
}
```

---

## Latency Budget

| Component | Target | Max |
|-----------|--------|-----|
| LLM API call | 200ms | 500ms |
| Schema validation | 1ms | 5ms |
| Guardrail checks | 2ms | 10ms |
| Total overhead | 203ms | 515ms |

**Timeout:** 1000ms hard timeout for all LLM calls  
**Fallback:** If LLM timeout, use pure Phase 8 logic  

---

## Evaluation Framework

### A/B Test Design

**Group A:** Pure Phase 8 (ML policy)
- Signal → Size → Risk → Portfolio → Execute
- No LLM involvement

**Group B:** LLM-Orchestrated Policy
- Pre-trade check → Playbook selection → Phase 8 → Execution plan → Execute
- LLM meta-reasoning at each step

**Traffic Split:** 50/50 with stratified sampling by market regime

### Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **Rule Violation Rate** | % of LLM recommendations violating constraints | < 0.1% |
| **Latency Impact** | Added latency from LLM layer | < 250ms p50, < 500ms p99 |
| **Net Performance Delta** | (Group B Sharpe - Group A Sharpe) | > 0.05 |
| **Override Attempts** | # times LLM tried to bypass limits | 0 |
| **Anomaly Detection Rate** | % of true anomalies caught by post-trade journal | > 80% |
| **Regime Switching Accuracy** | % of correct playbook selections | > 70% |

### Offline Evaluation

Before live deployment:

1. **Backtesting:** Run LLM orchestrator on historical data
   - Measure latency (simulated)
   - Check rule violation rate
   - Compare Sharpe vs pure Phase 8

2. **Shadow Mode:** Run in parallel without affecting trades
   - Log all LLM recommendations
   - Compare to actual Phase 8 decisions
   - Measure disagreement rate and reasons

3. **Limit Testing:** Adversarial prompts attempting to bypass
   - Try to increase position sizes
   - Try to disable circuit breakers
   - Try to ignore risk limits
   - **Expected result:** All blocked by guardrails

---

## Implementation Components

### Module Structure

```
autotrader/llm/
├── __init__.py                 # LLMOrchestrator main class
├── tools/
│   ├── __init__.py            # Tool definitions
│   ├── pretrade.py            # PreTradeChecklist
│   ├── playbook.py            # PlaybookSelector
│   ├── execution.py           # ExecutionPlanner
│   └── journal.py             # PostTradeJournal
├── guardrails/
│   ├── __init__.py            # Guardrail system
│   ├── validators.py          # Schema validators
│   ├── limits.py              # Hard limit enforcement
│   └── audit.py               # Audit logging
├── prompts/
│   ├── __init__.py            # Prompt templates
│   ├── pretrade_template.py
│   ├── playbook_template.py
│   ├── execution_template.py
│   └── journal_template.py
└── evaluation/
    ├── __init__.py            # Evaluation framework
    ├── ab_test.py             # A/B testing
    ├── metrics.py             # Performance metrics
    └── offline_eval.py        # Backtesting with LLM
```

### Key Classes

```python
class LLMOrchestrator:
    """Main LLM meta-orchestration class."""
    
    def __init__(
        self,
        strategy: TradingStrategy,  # Phase 8
        llm_client: LLMClient,
        guardrails: GuardrailSystem,
        config: LLMConfig
    ):
        self.strategy = strategy
        self.llm = llm_client
        self.guardrails = guardrails
        self.tools = [
            PreTradeChecklist(),
            PlaybookSelector(),
            ExecutionPlanner(),
            PostTradeJournal()
        ]
    
    def process_with_llm(
        self,
        symbol: str,
        market_data: dict
    ) -> ExecutionDecision:
        """
        LLM-enhanced decision flow.
        
        Flow:
        1. Pre-trade checklist (LLM)
        2. Playbook selection (LLM)
        3. Phase 8 signal generation
        4. Execution planning (LLM)
        5. Guardrail validation
        6. Execute (if allowed)
        """
        # 1. Pre-trade check
        pretrade = self.run_tool('pretrade_checklist', market_data)
        if pretrade.decision == 'HALT':
            return ExecutionDecision.hold(reason='LLM pre-trade halt')
        
        # 2. Playbook selection
        playbook = self.run_tool('playbook_selector', market_data)
        
        # 3. Phase 8 signal (using selected playbook)
        signal = self.strategy.process_signal(
            symbol=symbol,
            model=playbook.selected_model,
            horizon=playbook.horizon,
            **market_data
        )
        
        # 4. Execution planning
        exec_plan = self.run_tool('execution_planner', {
            'signal': signal,
            'market_data': market_data
        })
        
        # 5. Guardrail validation
        if not self.guardrails.validate(exec_plan):
            return ExecutionDecision.hold(reason='Guardrail violation')
        
        return exec_plan.to_decision()
    
    def run_tool(self, tool_name: str, inputs: dict) -> dict:
        """Run LLM tool with guardrails."""
        tool = self.get_tool(tool_name)
        
        # Generate prompt
        prompt = tool.generate_prompt(inputs)
        
        # Call LLM with timeout
        with timeout(1.0):
            response = self.llm.complete(prompt)
        
        # Validate schema
        validated = tool.validate_output(response)
        
        # Check guardrails
        self.guardrails.check(tool_name, validated, inputs)
        
        # Log audit trail
        self.guardrails.audit_log(tool_name, inputs, validated)
        
        return validated
```

---

## Configuration

### LLM Config

```yaml
llm:
  provider: "openai"  # or "anthropic", "local"
  model: "gpt-4"
  temperature: 0.0  # Deterministic
  max_tokens: 1000
  timeout_ms: 1000
  
  tools_enabled:
    - pretrade_checklist
    - playbook_selector
    - execution_planner
    - post_trade_journal
  
  guardrails:
    schema_validation: true
    hard_limit_enforcement: true
    audit_logging: true
    
  fallback:
    on_timeout: "use_phase8_only"
    on_error: "use_phase8_only"
    on_validation_failure: "reject_decision"

evaluation:
  ab_test_enabled: true
  traffic_split: 0.50
  stratify_by: "market_regime"
  
  metrics:
    - rule_violation_rate
    - latency_p50
    - latency_p99
    - sharpe_delta
    - override_attempts
    
  offline_eval:
    backtest_period: "2024-01-01/2024-12-31"
    shadow_mode_days: 7
    adversarial_test: true
```

---

## Safety Checklist

Before deploying Phase 9:

- [ ] All hard limits unoverridable by LLM
- [ ] Schema validation on all outputs
- [ ] Timeout protection (1s hard limit)
- [ ] Fallback to Phase 8 on LLM failure
- [ ] Audit logging complete
- [ ] Adversarial testing passed (0 successful overrides)
- [ ] Latency within budget (< 500ms p99)
- [ ] A/B test infrastructure ready
- [ ] Shadow mode tested for 7 days
- [ ] Manual review process for anomalies
- [ ] Kill switch tested (disable LLM instantly)

---

## Risk Mitigation

### LLM Failure Modes

| Failure | Mitigation |
|---------|-----------|
| **Timeout** | Fallback to Phase 8 only |
| **Invalid JSON** | Reject, fallback to Phase 8 |
| **Schema violation** | Reject, alert, fallback |
| **Hallucination** | Schema validation catches |
| **Adversarial prompt** | Guardrails block execution |
| **Cost explosion** | Token limits, rate limiting |
| **Latency spike** | Hard timeout, fallback |

### Monitoring

Real-time dashboards:
- LLM call latency (p50, p99, p999)
- Rule violation attempts
- Guardrail blocks
- A/B test performance delta
- Cost per decision
- Override attempt rate

Alerts:
- Rule violation rate > 0.1%
- Latency p99 > 500ms
- Override attempts > 0
- Performance delta < -0.05 (Group B worse)

---

## Phase 9 Deliverables

✅ **LLM Service**
- LLMOrchestrator class integrating all tools
- Schema-validated outputs with Pydantic
- Hard guardrails preventing limit overrides

✅ **Tools**
- PreTradeChecklist
- PlaybookSelector
- ExecutionPlanner
- PostTradeJournal

✅ **Guardrails**
- Schema validators
- Hard limit enforcement
- Action validators
- Audit logging

✅ **Prompts**
- Deterministic templates
- JSON-only outputs
- Reasoning constraints

✅ **Evaluation**
- A/B testing framework
- Offline backtesting
- Latency benchmarks
- Rule violation tracking
- Performance comparison

✅ **Documentation**
- Implementation guide
- Prompt engineering guide
- Safety documentation
- A/B test playbook

---

## Success Criteria

1. **Safety:** 0 successful override attempts in adversarial testing
2. **Performance:** Latency < 500ms p99
3. **Validation:** Rule violation rate < 0.1%
4. **Value:** Sharpe delta > 0.05 in A/B test
5. **Reliability:** Fallback to Phase 8 works 100% on LLM failure
6. **Audit:** Complete logging of all LLM interactions

---

## Next Steps

1. Implement LLM tools with schema validation
2. Build guardrail system with hard limits
3. Create deterministic prompt templates
4. Develop evaluation framework
5. Run offline backtesting
6. Deploy to shadow mode
7. Launch A/B test
8. Monitor and iterate

**Phase 9 transforms Phase 8 from a fixed strategy to an adaptive, reasoning-capable system while maintaining ironclad safety guarantees.**
