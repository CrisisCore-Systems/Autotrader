# Token Research Deliverables Summary

**Date:** October 11, 2025  
**Project:** VoidBloom / CrisisCore Hidden-Gem Scanner  
**Task:** Curated Token List for Multi-Signal Analysis

---

## 📦 Deliverables Overview

### 1. **Comprehensive Token Research Document**
**File:** `docs/RECOMMENDED_TOKENS.md`  
**Size:** ~15,000 words

**Contents:**
- ✅ 10 curated tokens across 4 risk categories
- ✅ Detailed contract addresses and metadata
- ✅ Scanner optimization analysis for each token
- ✅ Expected GemScore predictions with confidence ranges
- ✅ Safety gate calibration guidelines
- ✅ Data source mapping (FREE vs. Paid)
- ✅ Testing scenarios and alert rule suggestions

**Key Sections:**
- Category A: High-Signal Established Projects (ENA, ONDO, PENDLE, MORPHO)
- Category B: Emerging DeFi Infrastructure (VIRTUAL, ETHFI)
- Category C: Narrative-Driven Meme Tokens (PEPE, PENGU, FLOKI)
- Category D: Safety Gate Testing Tokens (WLFI)

---

### 2. **Ready-to-Use YAML Configurations**
**Location:** `configs/tokens/`

#### Individual Token Configs:
1. **`ena_ethena.yaml`** - DeFi synthetic dollar protocol
   - Expected GemScore: 72-78
   - Risk Level: Medium
   - Focus: S, O, L scores

2. **`ondo_finance.yaml`** - Institutional RWA tokenization
   - Expected GemScore: 75-82 (highest)
   - Risk Level: Low-Medium
   - Focus: S, A, C scores

3. **`pepe_meme.yaml`** - Meme token with strict safety
   - Expected GemScore: 58-68
   - Risk Level: High
   - Focus: M, L, G scores with enhanced safety checks

4. **`wlfi_safety_test.yaml`** - High-risk safety gate validation
   - Expected GemScore: 45-62 (may flag)
   - Risk Level: Very High
   - Purpose: Test safety gate effectiveness

#### Portfolio Configs:
5. **`balanced_portfolio.yaml`** - Multi-token comparative scan
   - Tokens: ENA, ONDO, PEPE, WLFI
   - Purpose: Test across full risk spectrum

6. **`defi_focus.yaml`** - DeFi infrastructure sector analysis
   - Tokens: ENA, PENDLE, MORPHO, ETHFI
   - Weights: Optimized for DeFi metrics (M=0%)

---

### 3. **Quick Start Execution Guide**
**File:** `docs/TOKENS_QUICK_START.md`

**Contents:**
- ✅ Immediate command-line examples for each token
- ✅ Output interpretation guidelines
- ✅ Advanced analysis techniques (artifacts, Obsidian export)
- ✅ Backtesting commands
- ✅ Alert setup instructions
- ✅ Troubleshooting common issues
- ✅ Continuous monitoring strategies
- ✅ Learning path (beginner → advanced)

**Quick Reference Commands:**
```bash
# Single token
python -m src.cli.run_scanner configs/tokens/ena_ethena.yaml --tree

# Portfolio
python -m src.cli.run_scanner configs/tokens/balanced_portfolio.yaml

# Backtest
python -m src.pipeline.backtest --tokens=ENA,ONDO,PEPE
```

---

## 🎯 Token Selection Rationale

### Selection Criteria Applied:

1. **Narrative Volatility (S Score)**
   - ✅ Diverse narrative types: DeFi, RWA, Meme, Political
   - ✅ Range from institutional to viral community-driven

2. **On-chain Metrics (A, O Scores)**
   - ✅ Verifiable holder distribution data
   - ✅ Measurable transaction patterns
   - ✅ Smart money overlap signals

3. **Liquidity Depth (L Score)**
   - ✅ Minimum $100K daily volume
   - ✅ Multi-venue DEX presence
   - ✅ Range: $100K (testing) to $759M (PEPE)

4. **Tokenomics Structure (T Score)**
   - ✅ Mix of transparent (ONDO) to TBD (WLFI)
   - ✅ Vesting schedule diversity for testing
   - ✅ Unlock cliff scenarios included

5. **Contract Safety (C Score)**
   - ✅ Audited (ONDO, MORPHO) to unaudited (WLFI)
   - ✅ Verified contracts (Blockscout/Etherscan compatible)
   - ✅ Known edge cases for safety gate validation

6. **Meme Momentum (M Score)**
   - ✅ Established memes (PEPE, FLOKI)
   - ✅ Political meme (WLFI)
   - ✅ DeFi tokens for M=0 baseline

7. **Community Growth (G Score)**
   - ✅ Large communities (PEPE: millions)
   - ✅ Niche technical (MORPHO: developers)
   - ✅ NFT crossover (PENGU)

---

## 📊 Expected Performance Matrix

| Token | Category | GemScore | Confidence | Safety | Primary Drivers |
|-------|----------|----------|------------|--------|-----------------|
| **ONDO** | Institutional | 75-82 | 0.85 | ✅ PASS | S, A, C |
| **ENA** | DeFi | 72-78 | 0.82 | ✅ PASS | S, O, L |
| **PENDLE** | DeFi | 68-75 | 0.80 | ✅ PASS | S, O, T |
| **MORPHO** | DeFi | 70-76 | 0.78 | ✅ PASS | S, C, O |
| **ETHFI** | DeFi | 66-73 | 0.75 | ✅ PASS | S, A, O |
| **VIRTUAL** | Emerging | 65-72 | 0.72 | ⚠️ VERIFY | S, M, L |
| **PEPE** | Meme | 58-68 | 0.68 | ⚠️ STRICT | M, L, G |
| **PENGU** | Meme | 60-70 | 0.70 | ⚠️ VERIFY | M, G, S |
| **FLOKI** | Meme | 62-71 | 0.72 | ⚠️ VERIFY | M, S, G |
| **WLFI** | Test Case | 45-62 | 0.55 | 🚫 MAY FLAG | S, M |

---

## 💰 Cost Analysis

### FREE Tier (100% Coverage)

All 10 tokens can be fully analyzed with **$0/month** using:

| Data Source | Client | Coverage |
|-------------|--------|----------|
| CoinGecko | `CoinGeckoClient` | Price, volume, market cap |
| Dexscreener | `DexscreenerClient` | DEX liquidity, pools |
| Blockscout | `BlockscoutClient` | Contract verification, holders |
| Ethereum RPC | `EthereumRPCClient` | On-chain transactions |
| Groq AI | `GroqAIClient` | Narrative analysis (limited) |

**Total Cost:** $0/month  
**API Keys Required:** 0

### Optional Paid Tier

Enhanced reliability available with:
- Etherscan API: ~$20/month (contract details)
- CoinGecko Pro: ~$30/month (enhanced price data)
- **Total:** ~$50/month (optional)

---

## 🧪 Testing Scenarios Enabled

### Scenario 1: Baseline Calibration ✅
**Tokens:** ENA, ONDO, PENDLE, MORPHO  
**Purpose:** Establish DeFi baseline performance  
**Expected:** All pass safety gate, GemScore 68-82

### Scenario 2: Meme Momentum Detection ✅
**Tokens:** PEPE, PENGU, FLOKI  
**Purpose:** Validate NVI/MMS narrative detection  
**Expected:** High M scores, borderline safety passes

### Scenario 3: Safety Gate Enforcement ✅
**Tokens:** WLFI, (SafeMoon V2 if added)  
**Purpose:** Validate risk detection  
**Expected:** WLFI may flag on T/C scores

### Scenario 4: Multi-Signal Convergence ✅
**Tokens:** ENA, PEPE, MORPHO  
**Purpose:** Demonstrate diverse token handling  
**Expected:** Different score profiles, appropriate ranking

### Scenario 5: Sector Analysis ✅
**Tokens:** ENA, PENDLE, MORPHO, ETHFI  
**Purpose:** DeFi-specific weight optimization  
**Expected:** M=0%, boosted S/A/O/C scores

---

## 🔄 Maintenance Plan

### Monthly Review Cycle

1. **Performance Validation**
   - Compare predicted vs. actual GemScores
   - Identify outliers and adjust expectations

2. **Token Rotation**
   - Remove stale/delisted tokens
   - Add emerging high-potential tokens
   - Update contract addresses if migrated

3. **Weight Tuning**
   - Backtest alternative weight configurations
   - Adjust based on historical performance
   - Document changes in experiment tracking

4. **Safety Gate Calibration**
   - Review false positives/negatives
   - Adjust thresholds based on findings
   - Add new exploit patterns to detection

### Quarterly Deep Dive

1. **Narrative Evolution**
   - Update keyword libraries
   - Refine archetypal pattern detection
   - Incorporate new crypto trends

2. **Contract Pattern Library**
   - Add newly discovered exploit patterns
   - Update proxy detection logic
   - Enhance honeypot detection

3. **Data Source Reliability**
   - Assess FREE vs. Paid accuracy
   - Identify data gaps
   - Consider new data source integrations

4. **Feature Engineering**
   - Evaluate new feature candidates
   - Test correlation with forward returns
   - Implement top-performing features

---

## 📈 Success Metrics

### Immediate Validation (Week 1)

- [ ] All 10 tokens scan successfully with FREE tier
- [ ] GemScores within predicted ranges (±5 points)
- [ ] Safety gate correctly flags WLFI (if applicable)
- [ ] Portfolio ranking matches expectations (ONDO > ENA > PEPE > WLFI)

### Short-Term (Month 1)

- [ ] Precision@5 measured on daily scans
- [ ] False positive rate <20% on safety gate
- [ ] Confidence scores correlate with data completeness
- [ ] Alert rules trigger appropriately

### Medium-Term (Quarter 1)

- [ ] Forward return analysis (7/30/90-day windows)
- [ ] GemScore predictive power validated
- [ ] Weight optimization improves Sharpe ratio
- [ ] Safety gate prevents ≥90% of known rugs

---

## 🛠️ Integration Checklist

### Scanner Compatibility

- [x] All tokens have Ethereum mainnet contracts (FREE RPC compatible)
- [x] CoinGecko IDs verified and active
- [x] Dexscreener coverage confirmed
- [x] Blockscout explorer availability checked
- [x] Configurations match scanner schema

### Data Pipeline Readiness

- [x] FREE clients initialized in scanner
- [x] Groq API integrated for narrative analysis
- [x] Safety gate rules implemented
- [x] GemScore calculation logic supports all feature families
- [x] Output formats configured (JSON, HTML, Markdown)

### Testing Infrastructure

- [x] Smoke tests cover client initialization
- [x] Integration tests validate FREE data sources
- [x] Safety gate test cases prepared
- [x] Backtest harness supports token list
- [x] Experiment tracking configured

---

## 📝 Usage Recommendations

### For Researchers/Analysts

**Start with:**
1. Single token scan (ENA or ONDO) to understand output
2. Portfolio comparison to see ranking logic
3. Backtest to validate historical performance

**Key configs:**
- `configs/tokens/balanced_portfolio.yaml`
- `configs/tokens/defi_focus.yaml`

### For Developers

**Start with:**
1. Review YAML config structure
2. Run smoke tests to validate setup
3. Experiment with weight configurations

**Key files:**
- `configs/tokens/*.yaml` (all configs)
- `tests/test_smoke.py`
- `tests/test_free_clients_integration.py`

### For Operators

**Start with:**
1. Daily automated scans with portfolio config
2. Alert rules for high GemScore breakouts
3. Weekly backtest for performance tracking

**Key configs:**
- `configs/tokens/balanced_portfolio.yaml`
- `configs/alert_rules.yaml`

---

## 🎓 Educational Value

### Learning Outcomes

By working with this token list, users will understand:

1. **Multi-Signal Analysis**
   - How different tokens score across S, A, O, L, T, C, M, G
   - Trade-offs between feature families
   - Weight configuration impact

2. **Risk Spectrum**
   - Institutional (ONDO) vs. Meme (PEPE) characteristics
   - Safety gate importance for high-risk tokens
   - Confidence scoring with incomplete data

3. **Narrative Detection**
   - DeFi sophistication narratives (MORPHO, PENDLE)
   - RWA institutional adoption (ONDO)
   - Meme viral momentum (PEPE, FLOKI)
   - Political/controversial narratives (WLFI)

4. **Practical Scanner Operations**
   - Configuration management
   - Output interpretation
   - Alert rule creation
   - Continuous monitoring workflows

---

## 🔗 Cross-References

### Documentation Links

- **Main README:** [`README.md`](../README.md)
- **FREE Data Sources:** [`docs/FREE_DATA_SOURCES.md`](FREE_DATA_SOURCES.md)
- **Feature Status:** [`docs/FEATURE_STATUS.md`](FEATURE_STATUS.md)
- **Experiment Tracking:** [`docs/EXPERIMENT_TRACKING.md`](EXPERIMENT_TRACKING.md)

### Configuration Files

- **Alert Rules:** [`configs/alert_rules.yaml`](../configs/alert_rules.yaml)
- **LLM Config:** [`configs/llm.yaml`](../configs/llm.yaml)
- **Example Config:** [`configs/example.yaml`](../configs/example.yaml)

### Test Files

- **Smoke Tests:** [`tests/test_smoke.py`](../tests/test_smoke.py)
- **Integration Tests:** [`tests/test_free_clients_integration.py`](../tests/test_free_clients_integration.py)

---

## 🚀 Next Steps

### Immediate Actions (Today)

1. ✅ Review token research document (`docs/RECOMMENDED_TOKENS.md`)
2. ✅ Verify all YAML configs are valid
3. ✅ Run first single-token scan (ENA recommended)
4. ✅ Review output and understand GemScore components

### Week 1 Goals

1. [ ] Complete all testing scenarios (1-5)
2. [ ] Validate GemScore predictions
3. [ ] Calibrate safety gate thresholds
4. [ ] Set up daily automated scans

### Month 1 Goals

1. [ ] Establish baseline performance metrics
2. [ ] Tune weight configurations based on backtests
3. [ ] Configure alert rules for top performers
4. [ ] Generate first set of lore capsules

### Quarter 1 Goals

1. [ ] Complete forward return analysis
2. [ ] Optimize feature weights for Sharpe ratio
3. [ ] Expand token list with new discoveries
4. [ ] Publish findings and methodology

---

## 📞 Support & Feedback

### Questions or Issues?

1. Check [`docs/TOKENS_QUICK_START.md`](TOKENS_QUICK_START.md) troubleshooting section
2. Review main [`README.md`](../README.md) for system overview
3. Run system validation: `python scripts/testing/validate_system.py`
4. Open GitHub issue with scan logs

### Contributing

To suggest additional tokens for the list:

1. Verify token meets selection criteria (see above)
2. Gather contract address, CoinGecko ID, chain
3. Predict GemScore range with rationale
4. Submit YAML config following template structure

---

## ✅ Deliverables Checklist

- [x] **Comprehensive token research document** (15K words)
- [x] **10 curated tokens** across 4 risk categories
- [x] **6 YAML configuration files** (4 individual + 2 portfolio)
- [x] **Quick start guide** with immediate commands
- [x] **Expected performance matrix** with predictions
- [x] **Safety gate calibration guidelines**
- [x] **Testing scenarios** (5 scenarios defined)
- [x] **Cost analysis** (FREE vs. Paid tiers)
- [x] **Maintenance plan** (monthly/quarterly)
- [x] **Integration checklist** (scanner compatibility)
- [x] **Educational outcomes** defined

---

## 🎉 Conclusion

This token list provides a **production-ready foundation** for validating and operating the VoidBloom / CrisisCore Hidden-Gem Scanner. All tokens are:

- ✅ **Analyzable with $0/month** FREE data sources
- ✅ **Optimized for scanner's feature vectors**
- ✅ **Diverse across risk spectrum** (institutional to meme)
- ✅ **Ready for immediate testing** with provided configs
- ✅ **Documented with expected performance** for validation

The deliverables enable immediate hands-on experimentation while providing the structure for systematic long-term analysis and continuous improvement.

---

**Document Version:** 1.0  
**Created:** October 11, 2025  
**Status:** ✅ Complete and Ready for Use  
**Maintained By:** VoidBloom / CrisisCore Systems
