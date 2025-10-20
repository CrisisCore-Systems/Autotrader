# Questrade Quick Start Guide

## ✅ Credentials Stored Successfully!

Your Questrade refresh token has been securely stored in:
```
configs/broker_credentials.yaml
```

**Token Expiry**: October 24, 2025 at 7:37 PM  
**Auto-refresh**: ✅ This token will automatically refresh on each API call

---

## 🚀 Test Your Connection

### 1. Test Questrade Authentication
```bash
python -c "
from src.bouncehunter.broker import create_broker
import yaml

# Load credentials
with open('configs/broker_credentials.yaml') as f:
    creds = yaml.safe_load(f)

# Create broker
broker = create_broker('questrade', refresh_token=creds['questrade']['refresh_token'])

# Test connection
print('Testing Questrade connection...')
balance = broker.get_account_balance()
print(f'✅ Connected! Account balance: {balance}')
"
```

### 2. Run a Test Scan with Questrade
```bash
python src/bouncehunter/agentic_cli.py \
    --config configs/canadian_tfsa.yaml \
    --broker questrade \
    --max-positions 3 \
    --dry-run
```

### 3. Run Live Trading (When Ready)
```bash
# TFSA account (conservative)
python src/bouncehunter/agentic_cli.py \
    --config configs/canadian_tfsa.yaml \
    --broker questrade \
    --max-positions 5 \
    --position-size 0.008  # 0.8% per position

# Margin account (aggressive)  
python src/bouncehunter/agentic_cli.py \
    --config configs/canadian_margin.yaml \
    --broker questrade \
    --max-positions 8 \
    --position-size 0.012  # 1.2% per position
```

---

## 🔐 Security Checklist

- [x] Token stored in `broker_credentials.yaml`
- [x] File added to `.gitignore` (won't be committed)
- [ ] Test authentication (run step 1 above)
- [ ] Review commission settings in `broker_credentials.yaml`
- [ ] Set `default_account_type` to your preferred account (TFSA/RRSP/Margin)

---

## 📋 Important Notes

### Token Management
- **Auto-refresh**: Your token refreshes on every API call
- **Storage**: After each refresh, the new token is saved to `broker_credentials.yaml`
- **Backup**: Keep a copy of your refresh token somewhere safe
- **Expiry**: If token expires, get a new one from Questrade Account Management

### Rate Limits
- **Quotes**: 1 request per second
- **Orders**: 2 requests per second
- The broker module handles rate limiting automatically

### Account Types
Edit `configs/broker_credentials.yaml` to set your preferred account:
```yaml
questrade:
  default_account_type: "TFSA"  # Options: TFSA, RRSP, Margin, Cash
```

---

## 🛠️ Troubleshooting

### "Invalid refresh token"
1. Check token hasn't expired (Oct 24, 2025)
2. Ensure no extra spaces when copying token
3. Get new token from Questrade if needed

### "Account not found"
1. Confirm you have the correct account type enabled
2. Check Questrade API access is enabled in your account settings
3. Try using practice account first: `practice_account: true`

### "Rate limit exceeded"
- Wait 1-2 seconds between manual API calls
- The broker module handles this automatically during trading

---

## 📚 Full Documentation

- **Questrade Setup**: `docs/CANADIAN_BROKERS.md`
- **Broker API Reference**: `src/bouncehunter/broker.py`
- **TFSA Configuration**: `configs/canadian_tfsa.yaml`
- **Margin Configuration**: `configs/canadian_margin.yaml`

---

## 🎯 Next Steps

1. **Test connection** (see step 1 above)
2. **Paper trade first**: Set `practice_account: true` in `broker_credentials.yaml`
3. **Review TFSA/RRSP limits**: See `docs/CANADIAN_BROKERS.md` for contribution limits
4. **Start small**: Begin with 1-2 positions, then scale up
5. **Monitor performance**: Check trade logs in `artifacts/` directory

---

## 🔄 Token Refresh Process

The system automatically:
1. Uses your refresh token to get an access token
2. Makes API calls with the access token
3. Saves the new refresh token after each auth
4. Updates `broker_credentials.yaml` with new token

**You don't need to do anything!** Just make sure the file stays secure.

---

## 🆘 Need Help?

- **Questrade API Docs**: https://www.questrade.com/api/documentation
- **BounceHunter Docs**: `docs/CANADIAN_BROKERS.md`
- **Configuration Help**: `CANADIAN_SETUP.md`

Happy trading! 🚀
