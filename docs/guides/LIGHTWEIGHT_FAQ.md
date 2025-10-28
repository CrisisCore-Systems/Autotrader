# 🪶 Lightweight Development - FAQ

## Common Questions About Lightweight Development

### General Questions

**Q: Will I lose functionality by using lightweight mode?**
A: No! All core trading features work perfectly:
- ✅ BounceHunter/PennyHunter gap trading
- ✅ Paper trading with all brokers
- ✅ Market scanning and signal generation
- ✅ Risk management and filters
- ✅ Backtesting
- ✅ All tests run successfully

What's disabled are production infrastructure components (Kafka, Grafana, Prometheus) that aren't needed for development.

**Q: Can I switch between lightweight and full Docker modes?**
A: Yes! It's just a configuration change:
```bash
# To lightweight:
cp .env.lightweight .env

# To full Docker:
cp .env.example .env
docker compose up -d
```

**Q: How much time does it take to set up?**
A: 
- Lightweight local: 5 minutes
- GitHub Codespaces: 2 minutes (one-click)
- Gitpod: 3 minutes (one-click)

**Q: Is this production-ready?**
A: Lightweight mode is for **development only**. For production, use the full Docker stack with proper infrastructure.

---

### GitHub Codespaces

**Q: How much does GitHub Codespaces cost?**
A: 
- **Personal accounts**: 60 hours/month FREE
- **GitHub Pro**: 120 hours/month FREE ($4/month for Pro)
- After free tier: ~$0.18/hour for 2-core machine

**Q: How do I manage Codespaces hours?**
A:
1. Codespaces auto-stop after 30 minutes of inactivity
2. Manually stop when done: https://github.com/codespaces
3. Configure timeout: Settings → Codespaces → Default idle timeout
4. Delete unused codespaces to save storage

**Q: Can I use a more powerful machine in Codespaces?**
A: Yes! Configure it when creating:
- 2-core: Development (free tier sufficient)
- 4-core: Heavy testing ($0.36/hour)
- 8-core: Performance work ($0.72/hour)

**Q: What happens when I run out of free hours?**
A: 
1. Switch to lightweight local development
2. Use Gitpod (50 hours/month free)
3. Upgrade to GitHub Pro for 2x hours
4. Continue next month when hours reset

---

### Technical Questions

**Q: Does SQLite perform well enough?**
A: Yes! For development workloads:
- ✅ Handles 1000s of trades easily
- ✅ Fast enough for testing
- ✅ Single file, portable
- ❌ Not suitable for production (use Postgres)

**Q: How do I run integration tests that need the full stack?**
A: Use CI/CD! Push to GitHub and let Actions run tests with full Docker stack. It's free and unlimited for public repos.

**Q: Can I use Jupyter notebooks in lightweight mode?**
A: Absolutely! Just install and run:
```bash
pip install jupyter
jupyter notebook
```

**Q: What about MLflow tracking?**
A: Lightweight mode uses file-based MLflow (no server needed):
```bash
# In .env.lightweight:
MLFLOW_TRACKING_URI=file:./mlruns
```
View experiments: `mlflow ui` (optional)

---

### Troubleshooting

**Q: "ModuleNotFoundError" when running scripts**
A:
```bash
# Install dependencies:
pip install -r requirements.txt

# Verify installation:
python -c "import pandas; print('OK')"
```

**Q: "Database not found" errors**
A:
```bash
# Initialize databases:
python scripts/db/init_dev_databases.py
```

**Q: "Connection refused" when accessing services**
A: In lightweight mode, some services aren't running. Check your `.env`:
```bash
# Should say:
REDIS_ENABLED=false
KAFKA_ENABLED=false
```

**Q: Tests are failing in lightweight mode**
A:
1. Make sure you're using lightweight config: `cp .env.lightweight .env`
2. Initialize databases: `python scripts/db/init_dev_databases.py`
3. Install all dependencies: `pip install -r requirements.txt`
4. Clear caches: `rm -rf __pycache__ .pytest_cache`

**Q: "ccxt.pro not found" error**
A: This is a known issue with Python 3.12+. Solutions:
1. Use Python 3.11 (recommended)
2. Or install ccxt without the pro version: `pip install ccxt==4.5.12`
3. Exchange streaming features may not work, but core trading does

**Q: My laptop is still slow**
A: Try these optimizations:
1. Close unnecessary applications
2. Use VS Code instead of PyCharm/full IDEs
3. Disable file watchers in your IDE settings
4. Use Codespaces instead (zero local resources)

**Q: "Permission denied" errors**
A:
```bash
# Windows:
Run scripts as: python script.py

# Mac/Linux:
chmod +x setup_lightweight.py
./setup_lightweight.py
```

---

### Workflow Questions

**Q: Can I develop offline?**
A:
- Lightweight local: ✅ Yes (after initial setup)
- Codespaces: ❌ No (requires internet)
- Gitpod: ❌ No (requires internet)

**Q: How do I collaborate with others?**
A: All modes work with Git:
```bash
git pull    # Get latest changes
# Make changes
git commit -m "Your changes"
git push    # Share with team
```

**Q: Can I use my preferred IDE?**
A:
- Lightweight local: ✅ Any IDE (VS Code, PyCharm, Vim, etc.)
- Codespaces: VS Code in browser (or connect from desktop)
- Gitpod: Theia (VS Code-like) in browser

**Q: How do I debug code in lightweight mode?**
A: Same as normal development:
```python
# Use Python debugger:
import pdb; pdb.set_trace()

# Or use IDE debugging (VS Code, PyCharm)
# Set breakpoints and debug normally
```

---

### Comparison Questions

**Q: Lightweight local vs Codespaces - which should I choose?**
A:
- **Lightweight local** if you:
  - Have decent laptop (8GB+ RAM)
  - Prefer working offline
  - Want full control
  
- **Codespaces** if you:
  - Have limited laptop resources
  - Want to work from anywhere
  - Want zero setup

**Q: Why not just use full Docker?**
A: Full Docker is great for production-like environments, but:
- ❌ Uses 4-8 GB RAM (vs 200-500 MB lightweight)
- ❌ Slow startup (5+ minutes vs 5 seconds)
- ❌ High disk I/O (heavy logging, metrics)
- ❌ Bogs down resource-constrained laptops

For development, you don't need all that infrastructure!

---

### Migration Questions

**Q: I'm already using Docker. How do I migrate?**
A:
1. Export any important data from Docker volumes
2. Stop Docker: `docker compose down`
3. Run setup: `python setup_lightweight.py`
4. Copy your broker credentials to new `.env`
5. Start developing!

**Q: Can I migrate my data from Postgres to SQLite?**
A: Yes, but for development, start fresh:
```bash
# Initialize new databases:
python scripts/db/init_dev_databases.py

# Your old data is preserved in Docker volumes
# You can restart Docker anytime to access it
```

**Q: What about my MLflow experiments?**
A: They're in `./mlruns/` - already portable! Just continue using them.

---

### Future Questions

**Q: Will lightweight mode always be supported?**
A: Yes! It's a core development mode now. Many developers prefer it over Docker.

**Q: Can I request new features for lightweight mode?**
A: Absolutely! Open a GitHub issue with your request.

**Q: What if I need a feature that requires Docker?**
A: Three options:
1. Use the hybrid approach: `docker-compose.lightweight.yml` (specific services)
2. Use CI/CD to test with full stack
3. Temporarily switch to full Docker for that specific task

---

## Still Have Questions?

- 📖 Read the full guide: [LIGHTWEIGHT_DEVELOPMENT.md](LIGHTWEIGHT_DEVELOPMENT.md)
- 💬 Open a GitHub Discussion
- 🐛 Report issues on GitHub Issues
- 📝 Check the quick reference: [LIGHTWEIGHT_QUICK_REF.txt](LIGHTWEIGHT_QUICK_REF.txt)

**Remember**: The goal is to keep you developing, not to force you to use specific tools. Choose what works best for your situation! 🚀
