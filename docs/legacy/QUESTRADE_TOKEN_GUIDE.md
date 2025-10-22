# 🔑 How to Get Your Questrade Refresh Token

## ⚠️ Important: Your Current Token is Invalid

The token you provided appears to have expired or been invalidated. You need to generate a **fresh** token directly from your Questrade account.

---

## 📝 Step-by-Step Instructions

### Step 1: Log Into Questrade
1. Go to https://my.questrade.com
2. Log in with your username and password

### Step 2: Navigate to API Settings
1. Click on **"My Account"** (top right)
2. Select **"Account Management"**
3. Look for **"API Access"** or **"App Hub"**
   - If you don't see this option, API access may not be enabled for your account type
   - Contact Questrade support to enable it

### Step 3: Create New Application Token
1. Click **"Create a new token"** or **"Register Personal App"**
2. Fill in the details:
   - **Application Name**: `BounceHunter Trading Bot`
   - **Description**: `Automated trading system`
   - **OAuth Redirect URL**: `http://localhost` (not used, but required)
3. Click **"Generate Token"** or **"Create"**

### Step 4: Copy Your Token
1. **CRITICAL**: The token will be shown **ONLY ONCE**
2. Copy the **ENTIRE** token (should be ~60-70 characters)
3. It looks like: `WRg3COlL51C3AYfu-DSpfhMjEMFGAm0G0vnguRAhWe7ztClm4hnpohBPCC6Y6IzBV0`

### Step 5: Update Your Configuration
Run this command and paste your new token:
```powershell
python update_questrade_token.py
```

Or manually edit `configs/broker_credentials.yaml`:
```yaml
questrade:
  enabled: true
  refresh_token: "YOUR_NEW_TOKEN_HERE"
```

### Step 6: Test Connection
```powershell
python test_questrade_direct.py
```

---

## 🤔 Troubleshooting

### "I don't see API Access in my account"

**Solutions:**
1. **Check account type**: Some Questrade account types don't support API access
   - TFSA, RRSP, and Margin accounts usually support it
   - Ask Questrade support: "How do I enable API access for automated trading?"

2. **Contact Questrade Support**:
   - Phone: 1-888-783-7837
   - Email: support@questrade.com
   - Say: "I need to enable API access for algorithmic trading"

3. **Use practice account first**:
   - Questrade offers a practice (paper) trading account
   - This is risk-free and good for testing
   - API access is usually easier to enable on practice accounts

### "Token expires immediately"

Questrade tokens have special behavior:
- **Refresh tokens expire after 3 days** if not used
- **BUT**: Each time you authenticate, you get a NEW refresh token
- Our system automatically saves new tokens
- You just need ONE successful authentication to start

### "I'm getting 403 Forbidden"

This usually means:
1. API access not enabled (see above)
2. Using wrong account type (live vs. practice)
3. Account doesn't have trading permissions

### "Do I need a Practice or Live account?"

**Start with Practice (Paper Trading):**
- ✅ Risk-free
- ✅ Real market data
- ✅ Test the system thoroughly
- ✅ Easy to get API access

**Switch to Live when ready:**
- Update `practice_account: false` in `broker_credentials.yaml`
- Generate new token from your LIVE account
- Start with small position sizes

---

## 📋 Quick Checklist

- [ ] Logged into Questrade web platform
- [ ] Found API Access / App Hub section
- [ ] Created new application/token
- [ ] Copied COMPLETE token (60-70 chars)
- [ ] Updated `broker_credentials.yaml` with new token
- [ ] Ran `python test_questrade_direct.py`
- [ ] Got success message with account info

---

## 🆘 Still Having Issues?

### Option 1: Try IBKR Instead
Interactive Brokers is another excellent Canadian broker with robust API:
- See `docs/CANADIAN_BROKERS.md` for IBKR setup
- Often easier API setup process
- Professional-grade platform

### Option 2: Use Paper Broker
Start with our built-in paper broker (no real money, no API needed):
```powershell
python src/bouncehunter/agentic_cli.py --broker paper
```

### Option 3: Debug Mode
Enable verbose logging to see exactly what's happening:
```powershell
$env:QUESTRADE_DEBUG="1"
python test_questrade_direct.py
```

---

## 📞 Getting Help

- **Questrade API Documentation**: https://www.questrade.com/api/documentation
- **Questrade Support**: 1-888-783-7837
- **BounceHunter Issues**: See `QUESTRADE_SETUP.md`

---

**Note**: The token you provided earlier (`WRg3COlL51C3AYfu-DSpfhMjEMFGAm0G0vnguRAhWe7ztClm4hnpohBPCC6Y6IzBV0`) 
returned a 400 Bad Request error, which typically means it's expired or invalid. You'll need to generate a fresh one.
