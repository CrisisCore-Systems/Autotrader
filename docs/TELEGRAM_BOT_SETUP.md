# BounceHunter Telegram Bot Setup

Send daily BounceHunter mean-reversion signals directly to your Telegram chat.

## Prerequisites

1. **Telegram Bot**: Already created at [@BotFather](https://t.me/BotFather)
   - Bot: `@bounce_hunter_bot`
   - Token: Keep this secure (see configuration below)

2. **Chat ID**: Find your Telegram user ID or channel ID
   - For personal messages: Message [@userinfobot](https://t.me/userinfobot) to get your chat ID
   - For channels: Use the channel's numeric ID (e.g., `-1001234567890`)

3. **Dependencies**: Install the requests library
   ```powershell
   pip install requests pyyaml
   ```

## Configuration

1. **Copy and edit the configuration file**:
   ```powershell
   cp configs/telegram.yaml.example configs/telegram.yaml
   ```

2. **Add your credentials** to `configs/telegram.yaml`:
   ```yaml
   telegram:
     bot_token: "8447164652:AAHTW_RmFRr4UwmBNwMTE_GlZNG0bGs1hi8"
     chat_id: "YOUR_CHAT_ID_HERE"  # Get from @userinfobot
     parse_mode: "Markdown"
     disable_notification: false
   
   scanner:
     # Optional: override default scanner settings
     # threshold: 0.65
     # rebound: 0.03
     # stop: 0.03
   ```

3. **Security**: The config file is already gitignored to prevent accidental commits.

## Usage

### Test Connection

Verify your bot credentials before scheduling:

```powershell
python -m src.bouncehunter.telegram_cli --test
```

Expected output:
```
2025-10-17 09:00:00 - INFO - Connected to bot @bounce_hunter_bot
2025-10-17 09:00:00 - INFO - ✓ Connection test successful
```

### Send Daily Signals

Run a scan and send results to Telegram:

```powershell
python -m src.bouncehunter.telegram_cli
```

The bot will:
1. Run BounceHunter scanner with your configured settings
2. Format the signals with entry/stop/target levels
3. Send a Markdown-formatted message to your Telegram chat

### Custom Configuration

Use a different config file:

```powershell
python -m src.bouncehunter.telegram_cli --config configs/telegram_custom.yaml
```

## Message Format

When signals are found, you'll receive:

```
🎯 BounceHunter Signals
Date: 2025-10-17

Found 2 signals:

*AAPL*
├ Probability: 67.4%
├ Entry: $169.10
├ Stop: $164.00 (-3.0%)
├ Target: $174.30 (+3.0%)
├ R:R: 1.0x
├ Z-score: -2.21 | RSI2: 6.4
└ ⚠️ high VIX regime

*MSFT*
├ Probability: 71.2%
├ Entry: $425.80
├ Stop: $413.03 (-3.0%)
├ Target: $438.57 (+3.0%)
├ R:R: 1.0x
├ Z-score: -1.89 | RSI2: 8.2
└ ✓

───────────────────────────────
Scanned 22 tickers
Historical win rate: 64.3% (201/312 events)
```

When no signals qualify:
```
🎯 BounceHunter Signals
Date: 2025-10-17

✅ No qualifying signals today

Scanned 22 tickers
```

## Scheduling (Cron/Task Scheduler)

### Linux/macOS (cron)

Run daily at 6:30 PM EST (after market close):

```bash
30 18 * * 1-5 cd /path/to/AutoTrader/Autotrader && /path/to/.venv/bin/python -m src.bouncehunter.telegram_cli
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task → "BounceHunter Daily Alert"
3. Trigger: Daily, weekdays only, 6:30 PM
4. Action: Start a program
   - Program: `C:\Users\kay\Documents\Projects\AutoTrader\.venv-1\Scripts\python.exe`
   - Arguments: `-m src.bouncehunter.telegram_cli`
   - Start in: `C:\Users\kay\Documents\Projects\AutoTrader\Autotrader`

## Troubleshooting

### Bot token invalid
- Verify token is copied correctly from @BotFather
- Ensure no extra spaces or quotes in `telegram.yaml`

### Chat ID not working
- Use [@userinfobot](https://t.me/userinfobot) to find your numeric ID
- For channels, make sure the bot is added as an administrator

### No signals received
- Run with `--test` first to verify connection
- Check logs for scanner errors
- Verify market data is downloading (may need yfinance cache refresh)

### Silent failures
- Check Python logs for exceptions
- Verify network connectivity to api.telegram.org
- Ensure firewall allows HTTPS outbound

## Advanced: Multiple Configurations

Create different alert profiles:

```powershell
# Aggressive scanner (lower threshold)
python -m src.bouncehunter.telegram_cli --config configs/telegram_aggressive.yaml

# Conservative scanner (higher threshold)
python -m src.bouncehunter.telegram_cli --config configs/telegram_conservative.yaml
```

Each config can target different chat IDs or use different scanner parameters.
