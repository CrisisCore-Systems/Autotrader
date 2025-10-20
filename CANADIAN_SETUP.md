# 🇨🇦 Canadian Trading Setup - Quick Start

## 1-Minute Setup

### Option A: Questrade (Best for TFSA)
```bash
# Install
pip install questrade-api

# Get refresh token from questrade.com → API Access

# Run
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker questrade \
  --broker-key "YOUR_REFRESH_TOKEN" \
  --config configs/telegram_conservative.yaml
```

### Option B: Interactive Brokers (Best for Active Trading)
```bash
# Install
pip install ib_insync

# Download IB Gateway from interactivebrokers.com
# Configure: API Settings → Enable Socket, Port 7497

# Run (with Gateway open)
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker ibkr \
  --broker-port 7497 \
  --config configs/telegram_pro.yaml
```

### Option C: Alpaca (Best for Testing)
```bash
# Install
pip install alpaca-py

# Sign up at alpaca.markets, get API keys

# Run
python -m bouncehunter.agentic_cli \
  --mode scan \
  --broker alpaca \
  --broker-key "API_KEY" \
  --broker-secret "SECRET_KEY" \
  --config configs/telegram_pro.yaml
```

---

## Feature Comparison

| Feature | Questrade | IBKR | Alpaca |
|---------|-----------|------|---------|
| TFSA/RRSP | ✅ | ✅ | ❌ |
| Min Balance | $1,000 | $10,000 | $0 |
| Commission | $5-$10 | $1 | $0 |
| Bracket Orders | Manual | Native | Native |
| Paper Trading | ❌ | ✅ | ✅ |

---

## Recommended Configs

### TFSA (Conservative)
```yaml
# configs/canadian_tfsa.yaml
risk_controls:
  max_positions: 5
  size_pct_base: 0.008  # 0.8%
scanner:
  min_bcs: 0.68
```

### Margin (Aggressive)
```yaml
# configs/canadian_margin.yaml
risk_controls:
  max_positions: 8
  size_pct_base: 0.012  # 1.2%
scanner:
  min_bcs: 0.62
```

---

## Common Issues

**Questrade: Token expired**
```bash
# Get new token from web portal
# Tokens expire after 3 months
```

**IBKR: Connection failed**
```bash
# 1. Check IB Gateway is running
# 2. Verify port: 7497 (paper) or 7496 (live)
# 3. Check API settings: Enable Socket Clients
```

---

For full documentation: [CANADIAN_BROKERS.md](CANADIAN_BROKERS.md)
