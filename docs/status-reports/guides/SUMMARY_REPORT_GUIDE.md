# Summary Report Feature - Documentation

## Overview

The Summary Report feature provides a **trust-building, easy-to-understand** view of scan results, focusing on:
- **Overall Scores** (GemScore, Confidence, Final Score)
- **Top Positive Drivers** - what's working well
- **Top Improvement Areas** - what needs attention
- **Risk Flags** - critical warnings to address
- **Actionable Recommendations** - what to do next

This feature is designed to increase internal trust by making complex scan results accessible and actionable.

---

## 🎯 Key Features

### 1. Visual Score Display
- Color-coded score bars (green/yellow/red)
- Progress indicators showing % of maximum
- Threshold-based status indicators (✓ good, ! warning, ✗ danger)

### 2. Driver Analysis
- **Positive Drivers**: Features contributing most to the score
- **Negative Drivers**: Features with the most improvement potential
- Impact quantification for each driver

### 3. Risk Flags
- Contract safety warnings
- Liquidity concerns
- Tokenomics risks
- Severity indicators (🔴 critical, 🟡 moderate, 🟢 low)

### 4. Smart Warnings
- Low confidence alerts
- Data completeness issues
- High volatility warnings
- Negative sentiment indicators

### 5. Actionable Recommendations
- Score-based suggestions
- Feature-specific guidance
- Due diligence reminders

---

## 📟 CLI Usage

### Basic Summary Report

```bash
python -m src.cli.run_scanner configs/example.yaml --summary
```

This will scan all configured tokens and display a summary report for each.

### With Tree-of-Thought Trace

```bash
python -m src.cli.run_scanner configs/example.yaml --tree --summary
```

Shows both the execution trace and summary reports.

### Save Artifacts + Summary

```bash
python -m src.cli.run_scanner configs/example.yaml --output-dir ./reports --summary
```

Saves markdown/HTML artifacts and displays summary reports.

### Example Output

```
================================================================================
                     📊 GemScore Summary Report: PEPE
================================================================================

▶ SCORES
  ✓ GemScore          72.5 [████████████████████████████████░░░░░░░░] 72.5%
  ✓ Confidence        81.3 [████████████████████████████████████░░░░] 81.3%
  ! Final Score       68.9 [███████████████████████████░░░░░░░░░░░░░] 68.9%

▶ TOP POSITIVE DRIVERS
  ↑ Accumulation Score           +0.156
  ↑ Narrative Momentum            +0.089
  ↑ Sentiment Score               +0.078
  ↑ Community Growth              +0.067
  ↑ Onchain Activity              +0.054

▶ TOP IMPROVEMENT AREAS
  ↓ Contract Safety               -0.089
  ↓ Liquidity Depth               -0.067
  ↓ Tokenomics Risk               -0.045

▶ RISK FLAGS
  ⚠️  Contract: Owner Can Mint
  🟡 Moderate safety score: 0.64
  💧 Low liquidity - high slippage risk

▶ WARNINGS
  ⚡ Moderate confidence (81.3%) - verify with additional sources
  📈 High volatility detected - expect significant price swings

▶ RECOMMENDATIONS
  ⚠️  Moderate score - review risk flags before proceeding
  🔍 Contract safety concerns - verify with independent audit
  💧 Consider deeper liquidity pools to reduce slippage risk
  🔐 Review contract code and obtain security audit
  🔬 Always verify findings with independent research

--------------------------------------------------------------------------------
                  Generated: 2025-10-08T14:23:45.123456
              VoidBloom / CrisisCore Hidden-Gem Scanner
--------------------------------------------------------------------------------
```

---

## 🌐 API Endpoints

### Get Single Token Summary

```http
GET /api/summary/{token_symbol}
```

**Example:**
```bash
curl http://localhost:8001/api/summary/PEPE
```

**Response:**
```json
{
  "token_symbol": "PEPE",
  "timestamp": "2025-10-08T14:23:45.123456",
  "scores": {
    "gem_score": 72.5,
    "confidence": 81.3,
    "final_score": 68.9
  },
  "drivers": {
    "top_positive": [
      {"name": "AccumulationScore", "value": 0.156},
      {"name": "NarrativeMomentum", "value": 0.089}
    ],
    "top_negative": [
      {"name": "ContractSafety", "value": 0.089},
      {"name": "LiquidityDepth", "value": 0.067}
    ]
  },
  "risk_flags": [
    "⚠️  Contract: Owner Can Mint",
    "🟡 Moderate safety score: 0.64"
  ],
  "warnings": [
    "⚡ Moderate confidence (81.3%) - verify with additional sources"
  ],
  "recommendations": [
    "⚠️  Moderate score - review risk flags before proceeding",
    "🔬 Always verify findings with independent research"
  ],
  "metadata": {
    "flagged": false,
    "safety_score": 0.64,
    "safety_severity": "medium"
  }
}
```

### Get All Summaries

```http
GET /api/summary
```

Returns an array of summary reports for all scanned tokens, sorted by final_score descending.

---

## 🎨 UI Component

### Integration

Add to your dashboard component:

```tsx
import { SummaryReport } from './components/SummaryReport';

function TokenDetail({ tokenSymbol }) {
  return (
    <div>
      {/* Other components */}
      <SummaryReport tokenSymbol={tokenSymbol} />
    </div>
  );
}
```

### Features

- **Responsive Design**: Works on desktop and mobile
- **Color-Coded Scores**: Visual indicators for quick assessment
- **Interactive Elements**: Hover effects and transitions
- **Comprehensive Layout**: All information organized logically
- **Professional Styling**: Clean, modern appearance

### Screenshot Description

The UI displays:
1. **Header** with token symbol and timestamp
2. **Score Cards** with progress bars
3. **Two-Column Driver Layout** (positive left, negative right)
4. **Risk Flags Section** with colored indicators
5. **Warnings Section** (if applicable)
6. **Recommendations Section** with actionable items
7. **Metadata Footer** with additional details

---

## 🔧 Programmatic Usage

### Generate Report in Code

```python
from src.cli.summary_report import SummaryReportGenerator
from src.core.scoring import GemScoreResult

generator = SummaryReportGenerator()

report = generator.generate_report(
    token_symbol="PEPE",
    gem_score=gem_score_result,
    features=features_dict,
    safety_report=safety_report,
    final_score=final_score,
    sentiment_metrics=sentiment_metrics,
    technical_metrics=technical_metrics,
    security_metrics=security_metrics,
    flagged=False,
    debug_info=debug_dict,
)

# Print to console
generator.print_report(report)

# Export to JSON
json_data = generator.export_json(report)
```

### Disable Colors

```python
generator = SummaryReportGenerator(color_enabled=False)
```

Useful for logging to files or CI/CD environments.

---

## 📊 Understanding the Scores

### GemScore (0-100)
Weighted composite of 8 key features:
- **20%** AccumulationScore - whale activity and accumulation patterns
- **15%** SentimentScore - narrative and community sentiment
- **15%** OnchainActivity - network usage and activity
- **12%** TokenomicsRisk - unlock schedules and supply dynamics
- **12%** ContractSafety - security audit and code quality
- **10%** LiquidityDepth - available liquidity and slippage risk
- **8%** NarrativeMomentum - trending topics and momentum
- **8%** CommunityGrowth - holder growth and engagement

### Confidence (0-100)
Data quality score based on:
- **50%** Recency - how recent the data is
- **50%** DataCompleteness - how complete the feature set is

### Final Score (0-100)
Composite metric combining:
- **40%** APS (Accumulation & Price Score)
- **30%** NVI (Narrative Value Index)
- **20%** (1 - ERR) (inverse Exploit Risk Rating)
- **10%** RRR (Risk-Reward Ratio)

---

## 🚨 Risk Flags Explained

### Contract Flags
- **Owner Can Mint**: Contract allows minting new tokens
- **Owner Can Withdraw**: Contract has withdrawal functions
- **Unverified**: Source code not verified on blockchain explorer
- **Honeypot**: Potential honeypot characteristics detected

### Score-Based Flags
- **Low Safety Score** (<0.5): High risk contract
- **Moderate Safety Score** (<0.7): Moderate risk
- **Low Liquidity** (<0.3): High slippage risk
- **High Tokenomics Risk** (<0.4): Unlock pressure concerns

### Severity Levels
- **🚨 CRITICAL**: Immediate attention required
- **🔴 HIGH**: Serious concern, proceed with caution
- **🟡 MEDIUM**: Moderate risk, review carefully
- **🟢 LOW**: Minor concern, monitor

---

## 💡 Best Practices

### 1. Always Review Risk Flags
Don't ignore warnings - investigate each flag thoroughly.

### 2. Verify With Multiple Sources
Use the summary as a starting point, not the final word.

### 3. Monitor Confidence Levels
Low confidence (<70%) means data may be stale or incomplete.

### 4. Act on Recommendations
The recommendations are tailored to the specific token's weaknesses.

### 5. Track Changes Over Time
Run scans regularly to monitor score trends and driver changes.

### 6. Combine With Other Tools
Use alongside the delta explainability and detailed reports.

---

## 🔄 Integration With Other Features

### With Delta Explainability
```bash
# Get summary + score change explanation
python -m src.cli.run_scanner configs/example.yaml --summary
# Then check delta API: GET /api/gemscore/delta/{symbol}/narrative
```

### With Feature Store
```bash
# Summary uses feature store for historical comparisons
# Feature values are validated before summary generation
```

### With Dashboard
```tsx
// Summary component fetches data from API automatically
<SummaryReport tokenSymbol="PEPE" />
```

---

## 🐛 Troubleshooting

### "No scan results found"
- Ensure you've run a scan first
- Check that the token symbol is correct (case-insensitive)

### Colors Not Showing in CLI
- Colors only work in terminals that support ANSI codes
- Use `color_enabled=False` for file output

### API 404 Error
- Make sure the API server is running
- Verify the token has been scanned
- Check API URL (default: http://localhost:8001)

### Missing Data in Summary
- Some fields may be None if data is unavailable
- Check the original scan logs for warnings
- Verify API keys are configured

---

## 📈 Example Workflow

### 1. Initial Scan with Summary
```bash
python -m src.cli.run_scanner configs/example.yaml --summary
```

### 2. Review Risk Flags
Look for red flags in contract safety and liquidity.

### 3. Check Top Drivers
Understand what's working (positive) and what needs work (negative).

### 4. Act on Recommendations
Follow the specific guidance for this token.

### 5. Monitor Changes
Re-run scans periodically to track improvements.

### 6. Compare in Dashboard
Use the UI to visualize trends and correlations.

---

## 🎓 Advanced Usage

### Custom Thresholds
Modify thresholds in `summary_report.py`:
```python
def _print_score_bar(self, label, value, max_value, threshold=50):
    # Change threshold to 80 for stricter evaluation
    threshold = 80
    ...
```

### Filter by Risk Level
```python
reports = [r for r in summaries if r.metadata['safety_severity'] != 'critical']
```

### Export to CSV
```python
import csv

with open('summary.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Token', 'GemScore', 'Confidence', 'Flagged'])
    for report in reports:
        writer.writerow([
            report.token_symbol,
            report.gem_score,
            report.confidence,
            report.metadata['flagged']
        ])
```

---

## 📚 Related Documentation

- **GEMSCORE_DELTA_IMPLEMENTATION.md** - Score change explanations
- **FEATURE_VALIDATION_COMPLETE.md** - Feature validation details
- **OBSERVABILITY_QUICK_REF.md** - Monitoring and metrics
- **TESTING_QUICK_REF.md** - Testing the summary feature

---

## ✅ Checklist

When using summary reports, verify:
- [ ] Risk flags have been reviewed
- [ ] Confidence level is acceptable (>70%)
- [ ] Top drivers make sense for the token
- [ ] Recommendations are actionable
- [ ] Safety severity is acceptable for your risk tolerance
- [ ] Multiple scans show consistent results
- [ ] Independent verification has been performed

---

## 🤝 Contributing

To improve the summary report feature:

1. **Add new metrics** in `SummaryReportGenerator`
2. **Enhance recommendations** based on feature patterns
3. **Improve risk detection** in `_extract_risk_flags()`
4. **Add visualizations** to the UI component
5. **Write tests** in `tests/test_summary_report.py`

---

**Last Updated**: October 8, 2025  
**Version**: 1.0.0  
**Author**: VoidBloom / CrisisCore Team
