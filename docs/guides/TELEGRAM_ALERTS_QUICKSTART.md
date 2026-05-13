# 📱 Telegram Alerts Quick Start Guide

**Status**: ✅ Ready to Configure  
**Date**: October 25, 2025

---

## 🎯 What This Does

Sends **real-time compliance alerts** to your Telegram account when violations are detected:

- 🚨 **CRITICAL**: Immediate alerts for severe violations (e.g., risk overrides, forbidden actions)
- ⚠️ **WARNING**: Timely alerts for important issues (e.g., risk check failures)
- ℹ️ **INFO**: Informational alerts for minor issues (e.g., missing reviews)

---

## 🚀 Quick Setup (5 Minutes)

### Step 1: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send the command: `/newbot`
3. Choose a name: `Trading Alerts Bot` (or any name you like)
4. Choose a username: `mycompany_alerts_bot` (must end with `bot`)
5. **Copy the bot token** - looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### Step 2: Get Your Chat ID

**Option A - Using the Bot** (Recommended):
1. Start a chat with your new bot (click the link @BotFather gives you)
2. Send any message: `Hello`
3. Visit this URL in your browser:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Look for `"chat":{"id":123456789}` in the JSON response
5. **Copy that number** - that's your chat ID!

**Option B - Using @userinfobot**:
1. Search for **@userinfobot** in Telegram
2. Send `/start`
3. It will reply with your user ID - that's your chat ID!

### Step 3: Run Setup Script

```powershell
# Navigate to project
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Run interactive setup
python scripts/setup_telegram_alerts.py --configure
```

The script will:
- ✅ Validate your bot token and chat ID
- ✅ Test the connection
- ✅ Send a test message to your Telegram
- ✅ Save configuration to `configs/alerts.yaml`

### Step 4: Verify Setup

You should receive a test message in Telegram:

```
ℹ️ INFO: Compliance Alert

Issue: SETUP_TEST
Description: Telegram alert setup completed successfully! 🎉
Signal: test_signal_001
Instrument: TEST
Timestamp: 2025-10-25 12:00:00 UTC

Details:
  • Setup Time: 2025-10-25 12:00:00
  • Status: Ready to receive alerts
```

---

## 🧪 Test the System

### Test 1: Send Sample Alerts

```powershell
# Test all severity levels
python scripts/setup_telegram_alerts.py --test
```

You'll receive 3 test alerts:
- 🚨 CRITICAL: Risk override
- ⚠️ WARNING: Risk check failed
- ℹ️ INFO: LLM review missing

### Test 2: Run Telegram Alert Demos

```powershell
# Run all demos
python scripts/demo_telegram_alerts.py

# Or run specific demos
python scripts/demo_telegram_alerts.py --demo 1  # Basic alerts
python scripts/demo_telegram_alerts.py --demo 2  # Compliance integration
python scripts/demo_telegram_alerts.py --demo 3  # Live monitoring simulation
```

### Test 3: Generate Real Violations

```powershell
# 1. Generate trading data WITH violations
python scripts/run_compliance_test_trading.py --cycles 10 --violations

# 2. Run compliance analysis (check only, no alerts yet)
python scripts/demo_compliance_monitoring.py

# 3. Run compliance analysis WITH alerts
python scripts/demo_compliance_monitoring.py --send-alerts
```

---

## 📊 Integration with Compliance Monitoring

### Automatic Alerts in Your Code

```python
from autotrader.alerts.router import AlertRouter, TelegramAdapter
from autotrader.alerts.config import load_alert_config
from autotrader.monitoring.compliance.monitor import ComplianceMonitor

# Load config (from environment or alerts.yaml)
config = load_alert_config()

# Create Telegram adapter
telegram = TelegramAdapter(
    bot_token=config.telegram.bot_token,
    chat_id=config.telegram.chat_id
)

# Create alert router
router = AlertRouter(telegram=telegram)

# Run compliance check
monitor = ComplianceMonitor(policy=your_policy)
report = monitor.analyze_period(audit_trail, start_time, end_time)

# Send alerts for any issues found
if report.issues:
    stats = router.route_batch(report.issues)
    print(f"Sent {stats['sent']} alerts, {stats['failed']} failed")
```

### Manual Alert Sending

```python
from autotrader.alerts.router import TelegramAdapter
from autotrader.monitoring.compliance.monitor import (
    ComplianceIssue,
    ComplianceSeverity
)
from datetime import datetime, timezone

# Create adapter
telegram = TelegramAdapter(
    bot_token="your_bot_token",
    chat_id="your_chat_id"
)

# Create issue
issue = ComplianceIssue(
    timestamp=datetime.now(tz=timezone.utc),
    signal_id="sig_001",
    instrument="AAPL",
    issue_code="CUSTOM_VIOLATION",
    description="Something went wrong!",
    severity=ComplianceSeverity.CRITICAL,
    metadata={'details': 'Additional context'}
)

# Send alert
success = telegram.send_alert(issue)
```

---

## 🔧 Configuration

### File: `configs/alerts.yaml`

```yaml
# Telegram Bot Configuration
telegram:
  enabled: true
  bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
  chat_id: "987654321"

# Email Configuration (Optional)
email:
  enabled: false
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  from_addr: "alerts@yourcompany.com"
  to_addrs:
    - "trader@yourcompany.com"
  username: null
  password: null
  use_tls: true
```

### Environment Variables (Alternative)

```bash
# Set environment variables instead of using config file
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="987654321"
export ALERTS_ENABLED="true"
```

**Priority**: Environment variables > Config file

### View Current Config

```powershell
python scripts/setup_telegram_alerts.py --show-config
```

---

## 📝 Alert Format

### Telegram Message Structure

```
[EMOJI] [SEVERITY]: Compliance Alert

Issue: [ISSUE_CODE]
Description: [Human-readable description]
Signal: [signal_id]
Instrument: [trading symbol]
Timestamp: [UTC timestamp]

Details:
  • [Key]: [Value]
  • [Key]: [Value]
```

### Severity Mapping

| Severity | Emoji | When Used | Example |
|----------|-------|-----------|---------|
| CRITICAL | 🚨 | Severe violations requiring immediate action | Risk override without authorization |
| WARNING | ⚠️ | Important issues requiring attention | Risk check failed but not blocked |
| INFO | ℹ️ | Minor issues or informational alerts | Missing LLM review |

---

## 🎛️ Advanced Features

### Multi-Channel Routing

The `AlertRouter` supports multiple channels with severity-based routing:

```python
from autotrader.alerts.router import AlertRouter, TelegramAdapter, EmailAdapter

router = AlertRouter(
    telegram=TelegramAdapter(bot_token, chat_id),
    email=EmailAdapter(smtp_host, smtp_port, from_addr, to_addrs)
)

# Routing logic:
# - CRITICAL → Telegram + Email
# - WARNING → Telegram only
# - INFO → Email only
```

### Batch Processing

```python
# Send multiple alerts efficiently
issues = [issue1, issue2, issue3]  # List of ComplianceIssue

stats = router.route_batch(issues)
print(f"Sent: {stats['sent']}, Failed: {stats['failed']}")
```

### Custom Formatting

Telegram supports **Markdown formatting**:
- `*bold*` for **bold text**
- `_italic_` for _italic text_
- `` `code` `` for `code blocks`
- `[link](url)` for links

### Error Handling

```python
try:
    success = telegram.send_alert(issue)
    if not success:
        logger.error(f"Failed to send alert for {issue.issue_code}")
        # Fallback: save to database, retry queue, etc.
except Exception as e:
    logger.error(f"Alert routing error: {e}")
```

---

## 🐛 Troubleshooting

### Bot Token Invalid

**Error**: `Failed to connect to Telegram bot`

**Solution**:
1. Check you copied the entire token from @BotFather
2. Make sure there are no spaces or line breaks
3. Regenerate token: Send `/revoke` to @BotFather, then `/newbot`

### Chat ID Not Working

**Error**: `Failed to send alert` or `Chat not found`

**Solution**:
1. **Start a chat with your bot first** - send any message
2. Get your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. For groups: Add bot to group, make it admin, then get group ID from getUpdates

### No Message Received

**Possible Causes**:
1. Bot not started - click "Start" button in Telegram
2. Wrong chat ID - verify with @userinfobot
3. Network issues - check firewall/proxy settings
4. Bot blocked by Telegram - check @BotFather for status

### Test Connection

```powershell
python scripts/setup_telegram_alerts.py --test
```

This will:
- ✅ Validate configuration
- ✅ Test bot connection
- ✅ Send 3 sample alerts
- ✅ Report any errors

---

## 📚 Additional Resources

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_telegram_alerts.py` | Interactive setup and testing |
| `scripts/demo_telegram_alerts.py` | Demonstrate all alert features |
| `scripts/demo_compliance_monitoring.py` | Run compliance checks with alerts |
| `scripts/run_compliance_test_trading.py` | Generate test data and violations |

### Code Files

| File | Purpose |
|------|---------|
| `autotrader/alerts/router.py` | Core alert routing logic |
| `autotrader/alerts/config.py` | Configuration management |
| `configs/alerts.yaml` | Alert configuration file |

### Dependencies

```bash
# Required for Telegram support
pip install requests

# Optional for async support (advanced usage)
pip install python-telegram-bot
```

---

## 🎯 Next Steps

1. ✅ **Setup Complete** - You have Telegram alerts configured!

2. **Generate Real Violations**:
   ```powershell
   python scripts/run_compliance_test_trading.py --cycles 20 --violations
   python scripts/demo_compliance_monitoring.py --send-alerts
   ```

3. **Integrate with Production**:
   - Add alert routing to your trading loops
   - Configure production policies
   - Set up monitoring dashboards

4. **Extend the System**:
   - Add email alerts for batch reporting
   - Implement alert throttling/deduplication
   - Create custom alert rules
   - Build Grafana dashboards (next task!)

---

## ✅ Task Complete!

**Alert Routing Status**: Implemented for the documented workflow in this snapshot

- ✅ Telegram bot configured
- ✅ Alert routing implemented
- ✅ Multiple severity levels supported
- ✅ Integration with compliance monitoring
- ✅ Test scripts available
- ✅ Documentation complete

**What's Next?**
- [ ] Create Grafana dashboards for visualization
- [ ] Start agentic validation (Week 1 of 8)
- [ ] Set up production monitoring

---

**Questions?** Check the troubleshooting section or run:
```powershell
python scripts/setup_telegram_alerts.py --help
```
