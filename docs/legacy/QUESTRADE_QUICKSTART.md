# 🚀 Questrade Setup - Quick Start

## You're on the right screen! Here's what to do:

### Step 1: Copy Your Token (DO THIS NOW!)

1. Click **"COPY TOKEN"** in that popup
2. The token should be ~60-70 characters long
3. Keep that window open until you test it works

### Step 2: Set Environment Variable

Open PowerShell and run:

```powershell
# Set the token (paste your actual token)
$env:QTRADE_REFRESH_TOKEN = "YOUR_TOKEN_HERE"

# Verify it's set
$env:QTRADE_REFRESH_TOKEN
```

### Step 3: Test Connection

```powershell
cd Autotrader
python src/bouncehunter/questrade_client.py
```

Expected output:
```
✅ Questrade token refreshed (expires in 1800s)
   API Server: https://api01.iq.questrade.com/
✅ Found 1 account(s):
   - Account #29601141
     Type: TFSA
     Status: Active
✅ Balances:
   - CAD: Cash=$5,000.00, Equity=$5,000.00
```

### Step 4: Make It Permanent (Optional)

Create `.env` file in project root:

```bash
# .env
QTRADE_REFRESH_TOKEN=your_token_here
```

Then load it before running:

```powershell
# Load from .env
$env:QTRADE_REFRESH_TOKEN = (Get-Content .env | Select-String 'QTRADE_REFRESH_TOKEN').ToString().Split('=')[1]

# Now run your scripts
python src/bouncehunter/questrade_client.py
```

---

## ⚠️ Important Notes

### Token Expiry
- **Refresh token**: Expires on the date shown in popup (usually ~7 days)
- **Access token**: Auto-refreshes every 30 minutes (handled automatically)
- When refresh token expires, generate a new one from the same screen

### Security
- **NEVER** commit tokens to git
- `.env` is already in `.gitignore`
- Use environment variables in production
- Rotate tokens regularly

### Common Errors

**❌ "QTRADE_REFRESH_TOKEN not set"**
```powershell
# Set it first
$env:QTRADE_REFRESH_TOKEN = "your_token"
```

**❌ "Questrade refresh failed 400: Bad Request"**
- Token expired → Generate new one from portal
- Token already used → Some tokens are single-use
- Wrong format → Make sure you copied entire token

**❌ "Questrade API error 401"**
- Access token expired (should auto-refresh)
- Refresh token invalid
- API access not enabled in account

---

## 🎯 Next Steps

Once the test passes:

### A. Quick Test Trade (Paper)
```powershell
# Update config
$env:QTRADE_REFRESH_TOKEN = "your_token"

# Run scanner in dry-run mode
python src/bouncehunter/agentic_cli.py `
    --config configs/canadian_tfsa.yaml `
    --broker questrade `
    --max-positions 3 `
    --dry-run
```

### B. Update Broker Integration

The `QuestradeBroker` class in `broker.py` will use this new client automatically.

### C. Generate Order Executor

Let me know when you're ready and I'll create the order execution module with:
- Buy/sell with $5-$10 test orders
- Stop-loss logic
- Time-based stops
- Fill logging
- Error handling

---

## 📋 Checklist

- [ ] Copied token from Questrade popup (COPY TOKEN button)
- [ ] Set `$env:QTRADE_REFRESH_TOKEN` in PowerShell
- [ ] Ran `python src/bouncehunter/questrade_client.py`
- [ ] Saw account info and balances
- [ ] (Optional) Saved to `.env` file

---

## 🆘 Still Having Issues?

Run the diagnostic:
```powershell
python test_questrade_direct.py
```

Or use paper broker while troubleshooting:
```powershell
python src/bouncehunter/agentic_cli.py --broker paper --dry-run
```

---

**Ready?** Copy that token from the popup and let's test it! 🚀
