# Token Analysis Documentation Index

**Quick navigation for the VoidBloom / CrisisCore token research deliverables**

---

## 📚 Main Documents

### 1. [Recommended Tokens](RECOMMENDED_TOKENS.md) 
**Primary reference document (15K words)**

Complete research on 10 curated tokens optimized for scanner analysis:
- Detailed token profiles with contract addresses
- Scanner optimization analysis for each token
- Expected GemScore predictions
- Safety gate calibration guidelines
- Data source mapping
- Testing scenarios and alert rules

**Start here for:** Understanding which tokens to analyze and why

---

### 2. [Quick Start Guide](TOKENS_QUICK_START.md)
**Immediate execution commands**

Ready-to-run commands for:
- Single token scans
- Portfolio comparisons
- Backtesting
- Artifact generation
- Alert setup
- Troubleshooting

**Start here for:** Running your first scan right now

---

### 3. [Token Research Summary](TOKEN_RESEARCH_SUMMARY.md)
**Executive overview**

High-level summary of:
- Deliverables overview
- Selection rationale
- Expected performance matrix
- Cost analysis
- Testing scenarios
- Maintenance plan
- Success metrics

**Start here for:** Understanding what was delivered and why

---

## 🎯 Token Profiles

### Category A: High-Signal Established (DeFi)

| Token | Profile | Config | Expected Score |
|-------|---------|--------|----------------|
| **Ethena (ENA)** | [View](RECOMMENDED_TOKENS.md#1-ethena-ena) | [`ena_ethena.yaml`](../configs/tokens/ena_ethena.yaml) | 72-78 |
| **Ondo (ONDO)** | [View](RECOMMENDED_TOKENS.md#2-ondo-ondo) | [`ondo_finance.yaml`](../configs/tokens/ondo_finance.yaml) | 75-82 |
| **Pendle (PENDLE)** | [View](RECOMMENDED_TOKENS.md#3-pendle-pendle) | N/A | 68-75 |
| **Morpho (MORPHO)** | [View](RECOMMENDED_TOKENS.md#4-morpho-morpho) | N/A | 70-76 |

### Category B: Emerging Infrastructure

| Token | Profile | Config | Expected Score |
|-------|---------|--------|----------------|
| **Virtuals Protocol (VIRTUAL)** | [View](RECOMMENDED_TOKENS.md#5-virtuals-protocol-virtual) | N/A | 65-72 |
| **Ether.fi (ETHFI)** | [View](RECOMMENDED_TOKENS.md#6-etherfi-ethfi) | N/A | 66-73 |

### Category C: Narrative-Driven Memes

| Token | Profile | Config | Expected Score |
|-------|---------|--------|----------------|
| **Pepe (PEPE)** | [View](RECOMMENDED_TOKENS.md#7-pepe-pepe) | [`pepe_meme.yaml`](../configs/tokens/pepe_meme.yaml) | 58-68 |
| **Pudgy Penguins (PENGU)** | [View](RECOMMENDED_TOKENS.md#8-pudgy-penguins-pengu) | N/A | 60-70 |
| **Floki (FLOKI)** | [View](RECOMMENDED_TOKENS.md#10-floki-floki) | N/A | 62-71 |

### Category D: Safety Testing

| Token | Profile | Config | Expected Score |
|-------|---------|--------|----------------|
| **World Liberty Financial (WLFI)** | [View](RECOMMENDED_TOKENS.md#11-world-liberty-financial-wlfi) | [`wlfi_safety_test.yaml`](../configs/tokens/wlfi_safety_test.yaml) | 45-62 ⚠️ |

---

## ⚙️ Configuration Files

### Individual Token Configs

Located in: `configs/tokens/`

| File | Token | Purpose | Risk Level |
|------|-------|---------|------------|
| [`ena_ethena.yaml`](../configs/tokens/ena_ethena.yaml) | Ethena | DeFi synthetic dollar | Medium |
| [`ondo_finance.yaml`](../configs/tokens/ondo_finance.yaml) | Ondo | Institutional RWA | Low-Medium |
| [`pepe_meme.yaml`](../configs/tokens/pepe_meme.yaml) | Pepe | Meme with strict safety | High |
| [`wlfi_safety_test.yaml`](../configs/tokens/wlfi_safety_test.yaml) | WLFI | Safety gate validation | Very High |

### Portfolio Configs

| File | Tokens | Purpose |
|------|--------|---------|
| [`balanced_portfolio.yaml`](../configs/tokens/balanced_portfolio.yaml) | ENA, ONDO, PEPE, WLFI | Cross-spectrum comparison |
| [`defi_focus.yaml`](../configs/tokens/defi_focus.yaml) | ENA, PENDLE, MORPHO, ETHFI | DeFi sector analysis |

---

## 🚀 Quick Commands

### Single Token Scan
```bash
# DeFi token (low-medium risk)
python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml --tree

# Institutional token (low risk)
python -m src.cli.run_scanner configs/tokens/ondo_finance.yaml --tree

# Meme token (high risk, strict safety)
python -m src.cli.run_scanner configs/tokens/pepe_meme.yaml --tree

# Test case (very high risk, may flag)
python -m src.cli.run_scanner configs/tokens/wlfi_safety_test.yaml --tree --verbose
```

### Portfolio Analysis
```bash
# Balanced across risk spectrum
python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml --tree

# DeFi infrastructure focus
python -m src.cli.run_scanner configs/tokens/defi_focus.yaml --tree
```

### Backtesting
```bash
# Historical validation
python -m src.pipeline.backtest \
  --tokens=ENA,ONDO,PEPE,WLFI \
  --start=2024-09-01 \
  --end=2025-10-11
```

---

## 📊 Expected Performance

| Rank | Token | GemScore | Confidence | Safety | Category |
|------|-------|----------|------------|--------|----------|
| 1 | ONDO | 75-82 | 0.85 | ✅ PASS | Institutional |
| 2 | ENA | 72-78 | 0.82 | ✅ PASS | DeFi |
| 3 | MORPHO | 70-76 | 0.78 | ✅ PASS | DeFi |
| 4 | PENDLE | 68-75 | 0.80 | ✅ PASS | DeFi |
| 5 | ETHFI | 66-73 | 0.75 | ✅ PASS | DeFi |
| 6 | VIRTUAL | 65-72 | 0.72 | ⚠️ VERIFY | Emerging |
| 7 | PEPE | 58-68 | 0.68 | ⚠️ STRICT | Meme |
| 8 | FLOKI | 62-71 | 0.72 | ⚠️ VERIFY | Meme |
| 9 | PENGU | 60-70 | 0.70 | ⚠️ VERIFY | Meme |
| 10 | WLFI | 45-62 | 0.55 | 🚫 MAY FLAG | Test Case |

---

## 🎓 Learning Paths

### Beginner: Understanding GemScore

**Documents:**
1. [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Understanding Output"
2. [Recommended Tokens](RECOMMENDED_TOKENS.md) - Section: "GemScore Formula"

**Commands:**
```bash
# Start with institutional token (clearest signals)
python -m src.cli.run_scanner configs/tokens/ondo_finance.yaml --tree
```

**Expected Learning:**
- What each score component means (S, A, O, L, T, C, M, G)
- How GemScore aggregates features
- Confidence scoring interpretation

---

### Intermediate: Risk Spectrum Analysis

**Documents:**
1. [Recommended Tokens](RECOMMENDED_TOKENS.md) - All category sections
2. [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Portfolio Comparison"

**Commands:**
```bash
# Compare across risk tiers
python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml --tree
```

**Expected Learning:**
- How different token types score differently
- Safety gate importance for memes
- Weight configuration impact

---

### Advanced: Strategy Development

**Documents:**
1. [Recommended Tokens](RECOMMENDED_TOKENS.md) - Sections: "Safety Gate", "Alert Rules"
2. [Token Research Summary](TOKEN_RESEARCH_SUMMARY.md) - Section: "Testing Scenarios"

**Commands:**
```bash
# Backtest with custom weights
python -m src.pipeline.backtest \
  --config=configs/tokens/defi_focus.yaml \
  --weight-experiments
```

**Expected Learning:**
- Weight optimization for specific strategies
- Alert rule creation
- Continuous monitoring workflows

---

## 🔍 Finding Information

### "I want to know..."

**...which tokens to scan first**
→ [Recommended Tokens](RECOMMENDED_TOKENS.md) - Categories A & B

**...how to run a scan right now**
→ [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Quick Start Commands"

**...what GemScore to expect**
→ [Token Research Summary](TOKEN_RESEARCH_SUMMARY.md) - Section: "Expected Performance Matrix"

**...how to interpret safety warnings**
→ [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Understanding Output"

**...how to set up alerts**
→ [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Setting Up Alerts"

**...how to customize weights**
→ [Recommended Tokens](RECOMMENDED_TOKENS.md) - Section: "Multi-Token Scan Configurations"

**...which data sources are free**
→ [Token Research Summary](TOKEN_RESEARCH_SUMMARY.md) - Section: "Cost Analysis"

**...how to validate the scanner**
→ [Token Research Summary](TOKEN_RESEARCH_SUMMARY.md) - Section: "Testing Scenarios Enabled"

---

## 📋 Checklists

### First-Time Setup

- [ ] Read [Quick Start Guide](TOKENS_QUICK_START.md) prerequisites
- [ ] Verify virtual environment activated
- [ ] Run smoke tests: `pytest tests/test_smoke.py -v`
- [ ] Choose starter token (ENA or ONDO recommended)
- [ ] Run first scan: `python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml --tree`
- [ ] Review output and understand GemScore

### Daily Operations

- [ ] Run portfolio scan: `python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml`
- [ ] Review top performers (GemScore ≥ 70)
- [ ] Check safety gate flags
- [ ] Update alert rules if needed
- [ ] Log observations for weekly review

### Weekly Review

- [ ] Compare predicted vs. actual GemScores
- [ ] Identify outliers for investigation
- [ ] Run backtest on weekly window
- [ ] Review alert effectiveness
- [ ] Plan next week's focus tokens

### Monthly Maintenance

- [ ] Full backtest on 30-day window
- [ ] Weight configuration experiments
- [ ] Update token list (add/remove)
- [ ] Safety gate calibration review
- [ ] Documentation updates

---

## 🛠️ Troubleshooting Index

### Common Issues

**Issue: "Command not found" or "Module not found"**
→ [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Troubleshooting"

**Issue: "API key required"**
→ [Token Research Summary](TOKEN_RESEARCH_SUMMARY.md) - Section: "FREE Tier"

**Issue: "Contract not found"**
→ [Recommended Tokens](RECOMMENDED_TOKENS.md) - Appendix A: Contract addresses

**Issue: "Low confidence score"**
→ [Quick Start Guide](TOKENS_QUICK_START.md) - Section: "Understanding Output"

**Issue: "Safety gate flagged"**
→ [Recommended Tokens](RECOMMENDED_TOKENS.md) - Section: "Safety Gate Calibration"

---

## 🔗 Related Documentation

### System Documentation

- [`README.md`](../README.md) - System overview
- [`docs/FREE_DATA_SOURCES.md`](FREE_DATA_SOURCES.md) - Data source guide
- [`docs/FEATURE_STATUS.md`](FEATURE_STATUS.md) - Implementation status
- [`docs/EXPERIMENT_TRACKING.md`](EXPERIMENT_TRACKING.md) - Backtest tracking

### Configuration Examples

- [`configs/example.yaml`](../configs/example.yaml) - Base config template
- [`configs/alert_rules.yaml`](../configs/alert_rules.yaml) - Alert configuration
- [`configs/llm.yaml`](../configs/llm.yaml) - LLM settings

### Test Files

- [`tests/test_smoke.py`](../tests/test_smoke.py) - Basic functionality
- [`tests/test_free_clients_integration.py`](../tests/test_free_clients_integration.py) - FREE data sources

---

## 📞 Getting Help

### Self-Service

1. **Search this index** for your topic
2. **Check troubleshooting** in Quick Start Guide
3. **Review test files** for usage examples
4. **Run validation:** `python scripts/testing/validate_system.py`

### Community Support

1. **GitHub Issues:** Report bugs or request features
2. **Documentation Updates:** Submit PRs for improvements
3. **Token Suggestions:** Follow contribution guidelines in Token Research Summary

---

## 📈 Success Metrics

### Immediate (Week 1)

- [ ] All 10 tokens scan successfully
- [ ] GemScores within ±5 points of predictions
- [ ] Safety gate correctly identifies WLFI risks
- [ ] Portfolio ranking matches expectations

### Short-Term (Month 1)

- [ ] Precision@5 measured
- [ ] False positive rate <20%
- [ ] Alert rules triggering appropriately
- [ ] Confidence correlates with data quality

### Long-Term (Quarter 1)

- [ ] Forward return analysis complete
- [ ] Weight optimization improves Sharpe
- [ ] Safety gate prevents ≥90% of rugs
- [ ] Token list expanded with discoveries

---

## 🎯 Quick Navigation Map

```
Token Research Documentation
│
├── 📄 RECOMMENDED_TOKENS.md (START HERE for research)
│   ├── Token Profiles (10 tokens)
│   ├── Contract Addresses
│   ├── Expected GemScores
│   ├── Safety Guidelines
│   └── Testing Scenarios
│
├── 🚀 TOKENS_QUICK_START.md (START HERE for execution)
│   ├── Immediate Commands
│   ├── Output Interpretation
│   ├── Advanced Analysis
│   ├── Troubleshooting
│   └── Learning Path
│
├── 📊 TOKEN_RESEARCH_SUMMARY.md (START HERE for overview)
│   ├── Deliverables Overview
│   ├── Selection Rationale
│   ├── Performance Matrix
│   ├── Cost Analysis
│   └── Maintenance Plan
│
└── 🗂️ INDEX.md (YOU ARE HERE)
    ├── Quick Navigation
    ├── Command Reference
    ├── Troubleshooting Index
    └── Learning Paths
```

---

## 💡 Pro Tips

### For Maximum Efficiency

1. **Bookmark this index** - Fastest way to find information
2. **Start with ONDO or ENA** - Clearest signals for learning
3. **Use balanced_portfolio.yaml** - See all risk tiers at once
4. **Run backtests early** - Validate before relying on scores
5. **Check safety gate on memes** - Always verify PEPE, PENGU, FLOKI
6. **Monitor WLFI** - Best test case for risk detection

### Time-Saving Aliases

Add to your shell profile:

```bash
# Bash/Zsh
alias vb-scan="python -m src.cli.run_scanner"
alias vb-portfolio="python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml --tree"
alias vb-backtest="python -m src.pipeline.backtest"

# PowerShell
Set-Alias vb-scan "python -m src.cli.run_scanner"
```

---

**Document Version:** 1.0  
**Last Updated:** October 11, 2025  
**Purpose:** Central navigation hub for token research deliverables  
**Status:** ✅ Complete

---

**Quick Links:**
- [Main Research](RECOMMENDED_TOKENS.md)
- [Quick Start](TOKENS_QUICK_START.md)
- [Summary](TOKEN_RESEARCH_SUMMARY.md)
- [Configs](../configs/tokens/)
