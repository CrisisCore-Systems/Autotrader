# Local LLM Setup Guide - CPU-Only Ollama

## 🎯 Overview

This guide sets up **local CPU-only LLM inference** using Ollama for the autonomous trading agent. No GPU required, 100% free, commercial-friendly licenses.

**Performance**: 3.8B Q4 model @ 25-60 tok/s, 7B Q4 @ 10-30 tok/s on modern CPU

---

## 📦 Installation

### Step 1: Install Ollama

**Windows** (native, no WSL needed):
```powershell
# Download and install from: https://ollama.com/download/windows
# Or use winget:
winget install Ollama.Ollama
```

**macOS**:
```bash
brew install ollama
```

**Linux**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull Models

```bash
# Fast parser (1s latency) - MIT License
ollama pull phi3:mini

# Default reasoner (2-5s) - Apache 2.0
ollama pull qwen2.5:7b-instruct

# Backup generalist (2-5s) - Apache 2.0  
ollama pull mistral:7b-instruct
```

**Model sizes**:
- `phi3:mini` (Q4): ~2.3 GB
- `qwen2.5:7b-instruct` (Q4): ~4.7 GB
- `mistral:7b-instruct` (Q4): ~4.1 GB

**Total disk**: ~11 GB

### Step 3: Start Ollama Server

**Windows PowerShell**:
```powershell
# Set CPU optimization
$env:OLLAMA_NUM_THREADS = [Environment]::ProcessorCount
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_KV_CACHE = "4096"

# Start server (runs in background)
ollama serve
```

**Linux/macOS**:
```bash
export OLLAMA_NUM_THREADS=$(nproc)
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_KV_CACHE=4096

ollama serve
```

**Verify**:
```bash
curl http://localhost:11434/api/tags
```

---

## 🚀 Quick Start

### Test LLM Gateway

```powershell
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
$env:PYTHONPATH = "$PWD"
python test_llm_gateway.py
```

**Expected output**:
```
=== TEST 1: Health Check ===
✅ health_check: PASS

=== TEST 2: Fast Intent Parsing (Phi-3 Mini) ===
   Latency: 847ms (target: ≤1000ms)
✅ fast_intent_parsing: PASS

=== TEST 3: News to Signal ===
   Impact: POSITIVE
   Tickers: ['AAPL']
   Confidence: 0.85
   Latency: 1234ms
✅ news_to_signal: PASS

...

Passed: 9/9
✅ All tests passed!
```

### Test API Endpoints

**Start API server**:
```powershell
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
$env:PYTHONPATH = "$PWD"
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

**Test endpoints**:

1. **Health check**:
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/llm/health'
```

2. **News to signal**:
```powershell
$json = @'
{
  "headlines": [
    "AAPL announces record iPhone sales",
    "Apple stock upgraded by Goldman Sachs"
  ]
}
'@
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/llm/news_to_signal' -Method POST -Body $json -ContentType 'application/json'
```

3. **Trade plan**:
```powershell
$json = @'
{
  "ticker": "AAPL",
  "setup": {
    "rsi": 35,
    "dist_200dma": -5.2,
    "volume_spike": 1.3
  },
  "market_regime": "CHOPPY",
  "risk_snapshot": {
    "portfolio_beta": 1.2,
    "cash_pct": 25
  }
}
'@
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/llm/trade_plan' -Method POST -Body $json -ContentType 'application/json'
```

4. **Cache stats**:
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/llm/cache/stats'
```

---

## ⚙️ Performance Tuning

### CPU Optimization (Windows T14-class)

**BIOS settings**:
- Enable all cores
- Set performance mode
- Disable C-states if available

**Windows Power Plan**:
```powershell
# Set high performance
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# Disable USB selective suspend
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
```

**Process priority**:
```powershell
# Run Ollama with high priority
Start-Process -FilePath "ollama" -ArgumentList "serve" -Priority High
```

### Context Window Tuning

For **shorter prompts** (<1000 tokens):
```bash
export OLLAMA_KV_CACHE=2048  # Reduce memory usage
```

For **longer context** (backtests, reports):
```bash
export OLLAMA_KV_CACHE=8192  # More memory
```

### Parallel Requests

**Single request at a time** (recommended for CPU):
```bash
export OLLAMA_NUM_PARALLEL=1
```

**Multiple requests** (if you have 16+ cores):
```bash
export OLLAMA_NUM_PARALLEL=2
export OLLAMA_NUM_THREADS=8  # Split cores between requests
```

---

## 📊 Expected Performance

### Latency Targets

| Task | Model | Target | Typical |
|------|-------|--------|---------|
| Intent parsing | phi3:mini | ≤1s | 500-900ms |
| News summary | phi3:mini | ≤1.5s | 800-1200ms |
| Trade plan | qwen2.5:7b | ≤5s | 2-4s |
| Calibration | qwen2.5:7b | ≤5s | 3-5s |

### Cache Hit Rates

- **First week**: 10-20% (building cache)
- **Steady state**: 30-70% (repeated patterns)
- **Speedup**: ~100x (cached response ≈0ms vs 2-5s)

### Throughput

- **Sequential**: 10-20 req/min (2-5s per request)
- **With cache**: 50-100 req/min (30-70% cache hit rate)
- **Batch jobs**: Run during off-hours for Auditor/Historian

---

## 🔒 Security Best Practices

### Never Send PII to LLM

```python
# ❌ BAD - sends sensitive data
await gateway.ask("default", [
    {"role": "user", "content": f"My portfolio value is ${portfolio_value}"}
])

# ✅ GOOD - sends only features
await gateway.ask("default", [
    {"role": "user", "content": f"Portfolio allocation: {allocation_pct}%"}
])
```

### Log Hashes, Not Secrets

```python
# Prompts are hashed automatically by cache
# Logs show: "Cache HIT: a3b2c1d4" (SHA256 prefix)
# Full prompt never logged
```

### Timeout All Requests

```python
# Always set timeouts
response = await gateway.ask("default", messages, timeout=10.0)

# If timeout exceeded, fall back to rule-based logic
```

---

## 🛠️ Troubleshooting

### Issue: "Ollama not responding"

**Check if running**:
```powershell
netstat -an | findstr 11434
```

**Restart Ollama**:
```powershell
# Kill existing
Get-Process ollama | Stop-Process -Force

# Restart
ollama serve
```

### Issue: "Model not found"

**List available models**:
```bash
ollama list
```

**Pull missing model**:
```bash
ollama pull phi3:mini
```

### Issue: "Too slow on CPU"

**Reduce context window**:
```bash
export OLLAMA_KV_CACHE=2048
```

**Use smaller model**:
```python
# Use phi3:mini for everything
response = await gateway.ask("fast", messages)  # Always fast tier
```

**Increase cache hits**:
```python
# More aggressive caching
gateway.cache.clear_old(days=90)  # Keep cache longer
```

### Issue: "Out of memory"

**Limit parallel requests**:
```bash
export OLLAMA_NUM_PARALLEL=1
```

**Use quantized models**:
```bash
# Q4 quantization (default, most efficient)
ollama pull phi3:mini

# If you need even lighter:
ollama pull phi3:3b  # Smaller base model
```

---

## 📈 Integration with Agents

### Agent Routing (What Uses LLM)

**✅ Use LLM** (non-critical path):
- **NewsSentry**: Headlines → signal JSON
- **Forecaster**: Trade plan generation
- **Auditor**: Confidence calibration
- **TradingCopilot**: Intent parsing, explanations

**❌ Never use LLM** (critical path):
- **Sentinel**: Real-time monitoring (<100ms required)
- **RiskOfficer**: Position risk checks (<200ms required)
- **Trader**: Order execution (<500ms required)
- **Historian**: Data writes (deterministic)

### Example: NewsSentry Integration

```python
# src/bouncehunter/pennyhunter_agentic.py

from src.agentic.llm_gateway import news_to_signal

class NewsSentry:
    async def analyze_headlines(self, headlines: List[str]) -> Signal:
        """Convert headlines to trading signal using LLM."""
        
        # LLM processing (1-2s, non-critical)
        signal = await news_to_signal(headlines)
        
        # Convert to agent signal format
        return Signal(
            ticker="MULTIPLE",
            impact=signal["impact"],
            confidence=signal["confidence"],
            rationale=signal["rationale"],
            source="NewsSentry",
        )
```

---

## 💾 Cache Management

### View cache stats

```python
from src.agentic.llm_gateway import LLMGateway

gateway = LLMGateway()
stats = gateway.cache.stats()
print(f"Cache entries: {stats['total_entries']}")
print(f"Avg hits: {stats['avg_hits_per_entry']:.1f}")
```

### Clear old cache

```python
# Clear entries older than 30 days
gateway.cache.clear_old(days=30)
```

### Benchmark cache effectiveness

```python
# Run for a day, then check hit rate
stats = gateway.cache.stats()
hit_rate = stats['avg_hits_per_entry']
print(f"Cache hit rate: {hit_rate:.1f} hits per entry")
```

---

## 🎓 Next Steps

1. **Test basic functionality**:
   ```powershell
   python test_llm_gateway.py
   ```

2. **Integrate with NewsSentry**:
   - Replace mock news parsing with `news_to_signal()`
   - Test with real headlines

3. **Add to Forecaster**:
   - Use `generate_trade_plan()` for strategy reasoning
   - Compare LLM plans vs rule-based

4. **Enable Auditor calibration**:
   - Run nightly `calibrate_confidence()`
   - Write adjustments to `config/risk_rules.toml`

5. **Monitor performance**:
   - Track latency via `/api/llm/health`
   - Monitor cache hit rate
   - Adjust models/settings if needed

---

## 📚 Additional Resources

- **Ollama Docs**: https://github.com/ollama/ollama/blob/main/docs
- **Model Library**: https://ollama.com/library
- **Phi-3 Info**: https://ollama.com/library/phi3
- **Qwen2.5 Info**: https://ollama.com/library/qwen2.5
- **Performance Tips**: https://github.com/ollama/ollama/blob/main/docs/faq.md

---

## ✅ Production Checklist

- [ ] Ollama installed and running
- [ ] All 3 models pulled (phi3, qwen2.5, mistral)
- [ ] Environment variables set for CPU optimization
- [ ] Test suite passes (9/9 tests)
- [ ] API endpoints responding
- [ ] Cache directory created (`./data/llm_cache.db`)
- [ ] Security review (no PII in prompts)
- [ ] Monitoring enabled (latency, cache hit rate)
- [ ] Fallback tested (Grok API as backup if needed)
- [ ] Documentation updated with team access

---

**Status**: Ready for production use! 🚀

Cost: **$0/month** (100% local, no API fees)
