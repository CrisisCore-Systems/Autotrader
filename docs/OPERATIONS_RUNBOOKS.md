# Operations Runbooks

This document provides troubleshooting guides for common operational issues detected by the Ops & Observability Dashboard.

## Table of Contents

1. [Data Freshness Issues](#data-freshness-issues)
2. [Broker Connectivity Problems](#broker-connectivity-problems)
3. [SLA Violations](#sla-violations)
4. [Circuit Breaker Trips](#circuit-breaker-trips)
5. [Rate Limit Exhaustion](#rate-limit-exhaustion)
6. [Worker Queue Backlog](#worker-queue-backlog)
7. [Security Check Failures](#security-check-failures)

---

## Data Freshness Issues

### Symptoms
- Freshness level shows "stale" or "outdated"
- Data age exceeds update frequency significantly
- High error rates on data source

### Diagnosis Steps

1. **Check SLA Status**: Navigate to SLA Dashboard to see if source is degraded/failed
2. **Review Error Rate**: Check if error rate > 5%
3. **Check Circuit Breaker**: See if circuit breaker is OPEN for the source
4. **Review Logs**: Check application logs for recent errors from the source

### Resolution

**For CoinGecko Issues:**
```bash
# Check rate limit status
curl http://localhost:8000/api/health/rate-limits | jq '.rate_limits.coingecko'

# If rate limited, wait for reset or upgrade to paid tier
# Check API key is set correctly
echo $COINGECKO_API_KEY

# Restart ingestion pipeline
systemctl restart autotrader-ingestion
```

**For Dexscreener Issues:**
```bash
# Test direct API access
curl https://api.dexscreener.com/latest/dex/tokens/0x...

# Check network connectivity
ping api.dexscreener.com

# Restart if needed
systemctl restart autotrader-ingestion
```

**For Blockscout Issues:**
```bash
# Verify RPC endpoint is accessible
curl https://eth.blockscout.com/api

# Check for API changes or maintenance
# Visit https://status.blockscout.com

# Switch to backup RPC if needed
export ETHEREUM_RPC_URL="https://backup-rpc.example.com"
```

**For Ethereum RPC Issues:**
```bash
# Test RPC connection
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  $ETHEREUM_RPC_URL

# Check rate limits on RPC provider
# Consider using Infura/Alchemy with higher limits
```

---

## Broker Connectivity Problems

### Symptoms
- Broker status shows "offline" or "error"
- Cannot place or view orders
- Account data not updating

### Diagnosis Steps

1. **Check Network**: Verify internet connectivity
2. **API Keys**: Ensure API keys/tokens are valid
3. **Broker Status**: Check broker's status page for outages
4. **Logs**: Review connection logs

### Resolution

**For Paper Trading:**
```bash
# Paper broker should always be available
# If showing error, check application logs
journalctl -u autotrader-api -n 100

# Restart API server
systemctl restart autotrader-api
```

**For Alpaca:**
```bash
# Verify API credentials
echo $ALPACA_API_KEY
echo $ALPACA_SECRET_KEY

# Test direct API access
curl -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
     https://paper-api.alpaca.markets/v2/account

# Check Alpaca status: https://status.alpaca.markets
```

**For Questrade:**
```bash
# Refresh token (tokens expire every 30 days)
python scripts/setup/set_questrade_token.py

# Verify token
cat ~/.config/autotrader/questrade_token.json

# Check Questrade status: https://status.questrade.com
```

**For Interactive Brokers (IBKR):**
```bash
# Ensure IB Gateway or TWS is running
ps aux | grep ibgateway

# Check port 4001 is accessible
telnet localhost 4001

# Restart IB Gateway
./ibgateway restart

# Check FA account configuration
cat ibkr_config.json
```

---

## SLA Violations

### Symptoms
- SLA status shows "DEGRADED" or "FAILED"
- Latency P95/P99 exceeds thresholds
- Success rate below 95%

### Diagnosis Steps

1. **Identify Source**: Check which source is degraded
2. **Review Metrics**: Look at latency and success rate trends
3. **Check Dependencies**: Verify all dependencies are healthy
4. **Network Issues**: Test network connectivity to external APIs

### Resolution

**High Latency:**
```bash
# Check network latency to API
ping api.coingecko.com

# Check for DNS issues
nslookup api.coingecko.com

# Consider using CDN/caching if available
# Review timeout settings in configuration
```

**Low Success Rate:**
```bash
# Review recent errors
journalctl -u autotrader-ingestion --since "1 hour ago" | grep ERROR

# Check for API changes or deprecations
# Review API provider's changelog

# Implement exponential backoff if not present
# Consider circuit breaker tuning
```

---

## Circuit Breaker Trips

### Symptoms
- Circuit breaker status shows "OPEN"
- Requests to service are failing immediately
- No attempts to reach service

### Diagnosis Steps

1. **Check Failure Count**: Review how many failures triggered the trip
2. **Review Errors**: Check logs for root cause
3. **Service Health**: Verify if external service is operational

### Resolution

**Manual Reset (Use with caution):**
```python
from src.services.reliability import CIRCUIT_REGISTRY

# Get breaker
breaker = CIRCUIT_REGISTRY.get_monitor("coingecko_api")

# Reset breaker
breaker.reset()
```

**Automatic Recovery:**
```bash
# Circuit breaker will automatically transition to HALF_OPEN
# after timeout period (30-120 seconds depending on config)

# Monitor recovery
watch -n 5 'curl http://localhost:8000/api/health/circuit-breakers | jq'

# If service is healthy, breaker will close automatically
```

---

## Rate Limit Exhaustion

### Symptoms
- Rate limit usage > 80%
- API returns 429 errors
- Increased latency during peak times

### Diagnosis Steps

1. **Check Current Usage**: Review rate limit panel
2. **Identify Peak Times**: Determine when limits are hit
3. **Review Configuration**: Check update frequencies

### Resolution

**Short-term:**
```bash
# Reduce update frequency temporarily
# Edit configuration file
vim configs/ingestion.yaml

# Change update_frequency_seconds from 60 to 300
# Restart ingestion service
systemctl restart autotrader-ingestion
```

**Long-term:**
```bash
# Upgrade to paid tier for higher limits
# Add API key for authenticated access
export COINGECKO_API_KEY="your-pro-key"

# Implement intelligent caching
# Review and optimize query patterns
# Consider request batching where supported
```

---

## Worker Queue Backlog

### Symptoms
- Pending jobs > 50
- Processing time increasing
- Worker queue status shows "degraded"

### Diagnosis Steps

1. **Check Worker Count**: Verify workers are running
2. **Review Processing Times**: Identify slow jobs
3. **Check Resources**: CPU/Memory/Disk usage

### Resolution

**Scale Workers:**
```bash
# Increase worker count
export WORKER_COUNT=4
systemctl restart autotrader-workers

# Or use process manager
pm2 scale autotrader-workers 4
```

**Optimize Jobs:**
```python
# Review slow queries in code
# Add database indexes if needed
# Implement job batching
# Consider async processing for I/O-bound tasks
```

**Clear Stale Jobs:**
```bash
# Connect to job queue (Redis/RabbitMQ)
redis-cli

# List queues
KEYS worker:*

# Clear specific queue if needed (use carefully!)
DEL worker:scanner:queue
```

---

## Security Check Failures

### Symptoms
- Security check status shows "failing"
- Critical/high vulnerabilities detected
- IBKR FA credentials potentially exposed

### Diagnosis Steps

1. **Review Check Details**: Identify which check failed
2. **Check Severity**: Assess critical/high/medium issues
3. **Review Recent Changes**: Check if recent deployments caused issues

### Resolution

**IBKR FA Scrubbing Failure:**
```bash
# Review recent logs for FA account patterns
grep -i "fa=" /var/log/autotrader/*.log

# If found, rotate logs immediately
logrotate -f /etc/logrotate.d/autotrader

# Enable FA scrubbing in config
vim configs/security.yaml
# Set: ibkr_fa_scrubbing: true

# Restart services
systemctl restart autotrader-*
```

**Dependency Vulnerabilities:**
```bash
# Update vulnerable packages
pip install --upgrade package-name

# Or update all packages
pip install -r requirements.txt --upgrade

# Run security audit
pip-audit

# Review and apply security patches
# Test thoroughly before deploying to production
```

**API Key Validation Failure:**
```bash
# Check which keys are missing
curl http://localhost:8000/api/health/security | jq '.checks.api_key_validation'

# Set missing keys
export GROQ_API_KEY="your-key"
export ETHERSCAN_API_KEY="your-key"

# Restart services
systemctl restart autotrader-api
```

---

## Contact & Escalation

For issues not covered by these runbooks:

1. Check application logs: `/var/log/autotrader/`
2. Review documentation: `/docs/`
3. Contact on-call engineer: See PagerDuty
4. Create incident ticket: Use internal ticketing system

## Monitoring Dashboards

- **Operations Dashboard**: http://localhost:3000/ops
- **Grafana Metrics**: http://localhost:9090
- **Log Aggregation**: Check configured log platform (Datadog/Splunk)
