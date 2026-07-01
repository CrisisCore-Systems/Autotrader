# 🤖 Telegram Bot Configuration - Step-by-Step Guide

**Date**: October 25, 2025  
**Task**: Configure Telegram bot for compliance alerts  
**Time Required**: 5 minutes

---

## 📋 Prerequisites Check

### 1. Install Required Library

First, make sure the `requests` library is installed:

```powershell
# Check if installed
pip show requests

# If not installed, install it:
pip install requests
```

---

## 🚀 Configuration Steps

### Step 1: Create Your Telegram Bot (2 minutes)

1. **Open Telegram** (desktop or mobile)

2. **Search for @BotFather** in Telegram search

3. **Start a chat** with @BotFather

4. **Send this command**:
   ```
   /newbot
   ```

5. **@BotFather will ask for a name**:
   ```
   Example: "My Trading Alerts Bot"
   (You can choose any name you like)
   ```

6. **@BotFather will ask for a username**:
   ```
   Must end in "bot"
   Example: "mycompany_trading_alerts_bot"
   ```

7. **@BotFather will reply with your bot token**:
   ```
   Example: ${TELEGRAM_BOT_TOKEN}
   ```
   
   ⚠️ **COPY THIS TOKEN** - You'll need it in Step 3!

### Step 2: Get Your Chat ID (1 minute)

**Method A - Using @userinfobot** (Easiest):

1. Search for **@userinfobot** in Telegram
2. Send `/start` to the bot
3. It will reply with your user information
4. **Copy the "Id" number** (e.g., `987654321`)

**Method B - Using your bot's API**:

1. Start a chat with your new bot (click the link @BotFather gave you)
2. Send any message to your bot (e.g., "Hello")
3. Open this URL in your browser (replace `<YOUR_BOT_TOKEN>` with your actual token):
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for `"chat":{"id":123456789}` in the JSON response
5. **Copy that ID number**

### Step 3: Run the Configuration Script (2 minutes)

1. **Open PowerShell** in the project directory:
   ```powershell
   cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
   ```

2. **Run the setup script**:
   ```powershell
   python scripts/setup_telegram_alerts.py --configure
   ```

3. **When prompted, enter your bot token**:
   ```
   Enter your bot token: [paste your token here]
   ```

4. **When prompted, enter your chat ID**:
   ```
   Enter your chat ID: [paste your chat ID here]
   ```

5. **The script will**:
   - ✅ Test the connection
   - ✅ Send a test message to your Telegram
   - ✅ Save the configuration to `configs/alerts.yaml`

6. **Check your Telegram** - you should receive a test message!

---

## ✅ Verification

After setup completes, you should see:

```
================================================================================
🎉 Setup Complete!
================================================================================

Next steps:
1. Run compliance monitoring with alerts:
   python scripts/demo_compliance_monitoring.py --send-alerts

2. Generate violations to test alerts:
   python scripts/run_compliance_test_trading.py --violations
   python scripts/demo_compliance_monitoring.py --send-alerts
```

And in your Telegram, you'll receive:

```
ℹ️ INFO: Compliance Alert

Issue: SETUP_TEST
Description: Telegram alert setup completed successfully! 🎉
Signal: test_signal_001
Instrument: TEST
Timestamp: 2025-10-25 XX:XX:XX UTC

Details:
  • Setup Time: 2025-10-25 XX:XX:XX
  • Status: Ready to receive alerts
```

---

## 🧪 Testing Your Setup

### Test 1: Send Sample Alerts

```powershell
python scripts/setup_telegram_alerts.py --test
```

This will send 3 test alerts to verify all severity levels work:
- 🚨 CRITICAL: Risk override
- ⚠️ WARNING: Risk check failed
- ℹ️ INFO: LLM review missing

### Test 2: Run Demo Scripts

```powershell
# Run all demos
python scripts/demo_telegram_alerts.py

# Or run specific demos
python scripts/demo_telegram_alerts.py --demo 1  # Basic alerts
python scripts/demo_telegram_alerts.py --demo 2  # Compliance integration
python scripts/demo_telegram_alerts.py --demo 3  # Live monitoring
```

### Test 3: Real Violations

```powershell
# 1. Generate trading data with violations
python scripts/run_compliance_test_trading.py --cycles 10 --violations

# 2. Run compliance monitoring with alerts enabled
python scripts/demo_compliance_monitoring.py --send-alerts
```

---

## 🔧 Configuration File

After setup, your configuration will be saved to:

**File**: `C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\configs\alerts.yaml`

**Contents**:
```yaml
# Alert Configuration
telegram:
  enabled: true
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  chat_id: "987654321"

email:
  enabled: false
  # ... (optional email config)
```

You can edit this file manually if needed.

---

## 🐛 Troubleshooting

### Problem: "requests module not found"

**Solution**:
```powershell
pip install requests
```

### Problem: "Failed to connect to Telegram bot"

**Possible causes**:
1. ❌ Wrong bot token - verify with @BotFather
2. ❌ Network issues - check internet connection
3. ❌ Bot was revoked - create a new bot

**Test your token**:
```powershell
# Replace <YOUR_TOKEN> with your actual token
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### Problem: "No messages received"

**Possible causes**:
1. ❌ Wrong chat ID - verify with @userinfobot
2. ❌ Didn't start chat with bot - send any message to your bot first
3. ❌ Bot blocked - unblock it in Telegram

**Solution**: Start fresh chat with your bot, send "Hello", then retry

### Problem: "Chat not found"

**Solution**: 
1. Make sure you've sent at least one message to your bot
2. Use @userinfobot to get correct chat ID
3. For groups: Add bot to group first, make it admin, then get group ID

---

## 📝 Quick Command Reference

| Command | Purpose |
|---------|---------|
| `python scripts/setup_telegram_alerts.py --configure` | Interactive setup wizard |
| `python scripts/setup_telegram_alerts.py --test` | Send test alerts |
| `python scripts/setup_telegram_alerts.py --show-config` | Display current config |
| `python scripts/demo_telegram_alerts.py` | Run all demos |
| `python scripts/demo_telegram_alerts.py --demo 1` | Run basic alerts demo |

---

## 🎯 Next Steps After Setup

Once configuration is complete:

1. ✅ **Test the system** (2 minutes):
   ```powershell
   python scripts/setup_telegram_alerts.py --test
   ```

2. ✅ **Generate violations** (5 minutes):
   ```powershell
   python scripts/run_compliance_test_trading.py --cycles 10 --violations
   ```

3. ✅ **Run compliance with alerts** (2 minutes):
   ```powershell
   python scripts/demo_compliance_monitoring.py --send-alerts
   ```

4. 🎯 **Move to next task**: Create Grafana dashboards

---

## 💡 Tips

1. **Save your bot token securely** - don't commit it to git
2. **Use a dedicated chat/group** for production alerts
3. **Test with demo scripts** before using in production
4. **Check alerts in Telegram** after each test
5. **Read the logs** if something doesn't work

---

## 📞 Need Help?

If you encounter issues:

1. Check the troubleshooting section above
2. Run `--show-config` to verify your settings
3. Test connection with `--test` flag
4. Check the logs for error messages

---

## ✅ Checklist

Before proceeding, make sure:

- [ ] `requests` library is installed
- [ ] Bot created via @BotFather
- [ ] Bot token copied
- [ ] Chat ID obtained from @userinfobot
- [ ] Setup script completed successfully
- [ ] Test message received in Telegram
- [ ] Test alerts sent successfully

---

**Ready? Let's configure your bot!** 🚀

Run this command to start:
```powershell
python scripts/setup_telegram_alerts.py --configure
```
