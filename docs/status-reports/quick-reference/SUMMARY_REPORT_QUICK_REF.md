# Summary Report - Quick Reference

## 🚀 Quick Start

### CLI - Show Summary After Scan
```bash
python -m src.cli.run_scanner configs/example.yaml --summary
```

### API - Get Token Summary
```bash
curl http://localhost:8001/api/summary/PEPE
```

### UI - Display Summary Component
```tsx
<SummaryReport tokenSymbol="PEPE" />
```

---

## 📊 What It Shows

| Section | Description |
|---------|-------------|
| **Scores** | GemScore, Confidence, Final Score with visual bars |
| **Top Positive Drivers** | Features contributing most to the score |
| **Top Improvement Areas** | Features with lowest values relative to weight |
| **Risk Flags** | Contract issues, liquidity concerns, security warnings |
| **Warnings** | Data quality, volatility, sentiment issues |
| **Recommendations** | Actionable next steps based on analysis |

---

## 🎯 Score Meanings

### GemScore (0-100)
- **80-100**: Excellent - Strong opportunity
- **60-79**: Good - Worth investigating
- **40-59**: Fair - Proceed with caution
- **0-39**: Poor - High risk

### Confidence (0-100)
- **80-100**: High - Data is fresh and complete
- **60-79**: Moderate - Verify with other sources
- **0-59**: Low - Data may be stale/incomplete

### Final Score (0-100)
Composite metric combining APS, NVI, ERR, RRR.

---

## 🚨 Risk Flag Icons

| Icon | Meaning |
|------|---------|
| 🔴 | Critical - immediate attention |
| 🟡 | Moderate - review carefully |
| ⚠️ | Warning - potential concern |
| 💧 | Low liquidity risk |
| 📊 | Tokenomics risk |
| 🔒 | Security/exploit risk |

---

## 💡 Common Commands

```bash
# Basic scan with summary
python -m src.cli.run_scanner configs/example.yaml --summary

# With execution trace
python -m src.cli.run_scanner configs/example.yaml --tree --summary

# Save artifacts + show summary
python -m src.cli.run_scanner configs/example.yaml --output-dir ./reports --summary

# Get all summaries via API
curl http://localhost:8001/api/summary

# Get specific token
curl http://localhost:8001/api/summary/PEPE | jq .
```

---

## 🔧 Configuration

### Disable Colors (for logging)
```python
from src.cli.summary_report import SummaryReportGenerator

generator = SummaryReportGenerator(color_enabled=False)
report = generator.generate_report(...)
```

### Export to JSON
```python
json_data = generator.export_json(report)
```

### Custom Thresholds
Edit `summary_report.py`:
```python
def _print_score_bar(self, ..., threshold=70):  # Change from 50
```

---

## 📈 Integration Examples

### With Feature Store
```python
# Summary automatically uses feature store for historical comparisons
report = generator.generate_report(...)
```

### With Delta Explainability
```bash
# Run summary first
python -m src.cli.run_scanner configs/example.yaml --summary

# Then check delta
curl http://localhost:8001/api/gemscore/delta/PEPE/narrative
```

### In Dashboard
```tsx
import { SummaryReport } from './components/SummaryReport';

function TokenView({ symbol }) {
  return (
    <>
      <TokenDetailPanel symbol={symbol} />
      <SummaryReport tokenSymbol={symbol} />
    </>
  );
}
```

---

## 🧪 Testing

```bash
# Run summary report tests
pytest tests/test_summary_report.py -v

# Test specific function
pytest tests/test_summary_report.py::test_generate_report_basic -v
```

---

## 📚 Key Features

### Driver Analysis
- **Positive**: Shows what's working (high contributions)
- **Negative**: Shows improvement areas (low values vs. weight)
- **Quantified**: Exact contribution/loss values

### Smart Warnings
- Low confidence alerts
- Data completeness issues
- High volatility detection
- Negative sentiment flags

### Actionable Recommendations
- Score-based guidance
- Feature-specific tips
- Always includes verification reminder

---

## 🎨 UI Features

- **Responsive Design** - works on mobile/desktop
- **Color Coding** - red/yellow/green indicators
- **Interactive** - hover effects, smooth transitions
- **Complete** - all data organized logically

---

## 🔍 Troubleshooting

### "No scan results found"
→ Run a scan first, check token symbol is correct

### Colors not showing
→ Terminal doesn't support ANSI, use `color_enabled=False`

### API 404
→ Ensure API server running on port 8001

### Missing data
→ Check original scan logs, verify API keys configured

---

## 📊 Example Output Structure

```json
{
  "token_symbol": "PEPE",
  "timestamp": "2025-10-08T14:23:45",
  "scores": {
    "gem_score": 72.5,
    "confidence": 81.3,
    "final_score": 68.9
  },
  "drivers": {
    "top_positive": [
      {"name": "AccumulationScore", "value": 0.156}
    ],
    "top_negative": [
      {"name": "ContractSafety", "value": 0.089}
    ]
  },
  "risk_flags": ["⚠️  Contract: Owner Can Mint"],
  "warnings": ["⚡ Moderate confidence"],
  "recommendations": ["🔬 Always verify findings"],
  "metadata": {
    "flagged": false,
    "safety_score": 0.64,
    "safety_severity": "medium"
  }
}
```

---

## ✅ Best Practices

1. ✅ **Always review risk flags** - Don't ignore warnings
2. ✅ **Check confidence level** - Low confidence = verify elsewhere
3. ✅ **Act on recommendations** - They're tailored to the token
4. ✅ **Track over time** - Run scans regularly
5. ✅ **Combine with other tools** - Use delta + detailed reports
6. ✅ **Independent verification** - Never rely on one source

---

## 🔗 Related Docs

- **SUMMARY_REPORT_GUIDE.md** - Full documentation
- **GEMSCORE_DELTA_IMPLEMENTATION.md** - Score changes
- **FEATURE_VALIDATION_COMPLETE.md** - Data validation
- **OBSERVABILITY_QUICK_REF.md** - Monitoring

---

## 📞 Support

For issues or questions:
1. Check full guide: `../guides/SUMMARY_REPORT_GUIDE.md`
2. Review test cases: `tests/test_summary_report.py`
3. Examine code: `src/cli/summary_report.py`

---

**Version**: 1.0.0  
**Last Updated**: October 8, 2025  
**Status**: ✅ Production Ready
