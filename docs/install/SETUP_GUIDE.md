# 🚀 VoidBloom AutoTrader - Quick Setup Guide

## ✅ Step 1: Configure API Keys (REQUIRED)

You've already created the `.env` file! Now you need to add your API keys.

### 🔑 Required API Keys

#### 1. **Groq API Key** (FREE - For AI Narrative Analysis)
```bash
# Get your key at: https://console.groq.com
GROQ_API_KEY=gsk_your_actual_key_here
```

**Steps:**
1. Go to https://console.groq.com
2. Sign up for a free account
3. Navigate to API Keys section
4. Create a new API key (starts with `gsk_`)
5. Copy and paste into your `.env` file

#### 2. **Etherscan API Key** (FREE - For On-Chain Data)
```bash
# Get your key at: https://etherscan.io/apis
ETHERSCAN_API_KEY=YOUR_ETHERSCAN_KEY_HERE
```

**Steps:**
1. Go to https://etherscan.io/apis
2. Create a free account
3. Navigate to "API Keys" in your account
4. Generate a new API key
5. Copy and paste into your `.env` file

---

## 📦 Step 2: Install Python Dependencies

```powershell
# Navigate to the project root
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Create virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## 🎨 Step 3: Start the Dashboard

### Backend (FastAPI)
```powershell
# Terminal 1 - Start the backend API
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
uvicorn src.services.dashboard_api:app --reload --port 8000
```

The backend will be available at: http://localhost:8000
API docs available at: http://localhost:8000/api/docs

### Frontend (React + Vite)
```powershell
# Terminal 2 - Start the frontend (dependencies already installed!)
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader\dashboard
npm run dev
```

The dashboard will be available at: http://localhost:5173

---

## 🧪 Step 4: Run Your First Scan

```powershell
# Quick test with demo data
python scripts/demo/main.py

# Or use the CLI with your config
python -m src.cli.run_scanner configs/example.yaml
```

---

## 🔧 Optional: Advanced Configuration

### Telegram Alerts Setup
1. Message @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token to `.env` as `TELEGRAM_BOT_TOKEN`
4. Start a chat with your bot and get your chat ID
5. Add chat ID to `.env` as `TELEGRAM_CHAT_ID`

### Slack Webhooks
1. Go to https://api.slack.com/messaging/webhooks
2. Create an incoming webhook
3. Copy URL to `.env` as `SLACK_WEBHOOK_URL`

### PostgreSQL Database (Production)
```bash
# Install PostgreSQL and create database
createdb voidbloom

# Update .env with connection details
DATABASE_URL=postgresql://user:password@localhost:5432/voidbloom
```

---

## 📊 What You'll See

### Dashboard Features:
- **GemScore Rankings** - Tokens sorted by composite score
- **Token Details** - Deep analytics on each token
- **Score Contributions** - Visual breakdown of metrics
- **Sentiment Analysis** - AI-powered narrative insights
- **Safety Reports** - Contract security findings
- **News Feed** - Latest headlines per token
- **Execution Traces** - Tree-of-Thought workflow
- **Collapse Artifacts** - Exportable lore reports

---

## 🆘 Troubleshooting

### "Module not found" errors
```powershell
pip install -r requirements.txt
```

### "GROQ_API_KEY not found" warning
- Edit `.env` and add your Groq API key
- Restart the backend server

### Dashboard won't connect to API
- Make sure backend is running on port 8000
- Check `vite.config.ts` proxy settings
- Look for CORS errors in browser console

### No tokens showing up
- Edit `configs/example.yaml` with real token data
- Or use demo mode (automatic fallback)

---

## 📝 Next Steps

1. **Customize Token List**: Edit `configs/example.yaml` with tokens you want to track
2. **Set Alert Rules**: Configure `configs/alert_rules.yaml` for notifications
3. **Run Backtests**: Execute `make backtest` to evaluate historical performance
4. **Monitor Dashboard**: Keep it running to track real-time score changes

---

## 🔐 Security Reminders

- ✅ `.env` file is already in `.gitignore`
- ✅ Never share your API keys publicly
- ✅ Rotate keys regularly
- ✅ Monitor API usage/billing
- ✅ Use separate keys for dev/prod

---

## 📚 Additional Resources

- **Architecture Docs**: `ARCHITECTURE.md`
- **Main README**: `README.md`
- **API Documentation**: http://localhost:8000/api/docs (when running)
- **Groq Documentation**: https://console.groq.com/docs
- **Etherscan API Docs**: https://docs.etherscan.io

---

## 🎉 You're Ready!

Your environment is configured. Now just:
1. Add your API keys to `.env`
2. Install Python dependencies
3. Start both servers
4. Open http://localhost:5173

Happy gem hunting! 💎✨
