# Production Worker Deployment Guide

**Status**: Production Ready  
**Date**: October 25, 2025  
**Version**: 1.0.0

---

## Overview

This guide covers deploying AutoTrader's production worker services using Docker Compose. The worker architecture provides:

- **Ingestion Workers**: Continuous data collection from news, social media, GitHub, and tokenomics APIs
- **Backtest Workers**: On-demand strategy backtesting across multiple symbols
- **Optimization Workers**: Hyperparameter optimization using Optuna

All workers emit Prometheus metrics, support graceful shutdown, and include health checks for production reliability.

---

## Quick Start

### 1. Start Ingestion Worker (Production)

```bash
# Start all infrastructure + ingestion worker
docker-compose --profile production up -d

# View logs
docker-compose logs -f worker-ingestion

# Check metrics
curl http://localhost:9100/metrics
```

### 2. Run Backtest Worker (Validation)

```bash
# Set symbols to backtest
export BACKTEST_SYMBOLS="AAPL,MSFT,NVDA"

# Run backtest worker
docker-compose --profile validation up worker-backtest

# Results saved to: ./backtest_results/
```

### 3. Run Optimization Worker

```bash
# Configure optimization
export OPTIM_SYMBOLS="AAPL,MSFT,NVDA,BTCUSD,ETHUSD,EURUSD,GBPUSD"
export OPTIM_TRIALS=50
export OPTIM_SPLITS=5

# Run optimization worker
docker-compose --profile optimization up worker-optimization

# Results saved to: ./reports/optuna/
```

---

## Architecture

### Worker Types

#### Ingestion Worker (`worker-ingestion`)
- **Purpose**: Continuous data collection from external APIs
- **Port**: 9100 (Prometheus metrics)
- **Config**: `configs/ingestion.yaml`
- **Database**: `artifacts/autotrader.db` (SQLite)
- **Profile**: `production`, `workers`

**Characteristics**:
- Long-running service (daemon mode)
- Poll interval: 15 minutes (configurable)
- Graceful shutdown on SIGTERM/SIGINT
- Auto-restart on failure
- Circuit breaker for failing data sources

#### Backtest Worker (`worker-backtest`)
- **Purpose**: Execute strategy backtests on historical data
- **Port**: 9101 (Prometheus metrics)
- **Data Input**: `data/processed/features/`
- **Results Output**: `backtest_results/`
- **Profile**: `validation`, `workers`

**Characteristics**:
- Job-based execution (runs to completion)
- Parallel symbol processing (configurable)
- Memory limit: 4GB (configurable)
- Timeout: 10 minutes per symbol

#### Optimization Worker (`worker-optimization`)
- **Purpose**: Hyperparameter search using Optuna
- **Port**: 9102 (Prometheus metrics)
- **Data Input**: `data/processed/features/`
- **Results Output**: `reports/optuna/`
- **Profile**: `optimization`, `workers`

**Characteristics**:
- Job-based execution (long-running)
- Sequential trial processing
- Memory limit: 8GB (configurable)
- Median pruning for early stopping

---

## Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# Worker Configuration
WORKER_NAME=autotrader-worker
WORKER_METRICS_PORT=9100
WORKER_POLL_INTERVAL=900
LOG_LEVEL=INFO

# Ingestion
INGESTION_CONFIG=configs/ingestion.yaml
INGESTION_DB_PATH=artifacts/autotrader.db

# Backtest
BACKTEST_SYMBOLS=AAPL,MSFT,NVDA
BACKTEST_CONFIG=configs/backtest.yaml

# Optimization
OPTIM_SYMBOLS=AAPL,MSFT,NVDA,BTCUSD,ETHUSD,EURUSD,GBPUSD
OPTIM_TRIALS=50
OPTIM_SPLITS=5

# Database
POSTGRES_USER=autotrader
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=autotrader

# MLflow
MLFLOW_S3_BUCKET=mlflow-artifacts
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your_grafana_password
```

### Worker Configuration File

Edit `configs/workers.yaml` to customize:

```yaml
ingestion:
  poll_interval: 900
  max_concurrent_requests: 10
  rate_limits:
    news_feeds: 60
    social_streams: 30

backtest:
  max_symbols_parallel: 3
  memory_limit_mb: 4096
  timeout_per_symbol: 600

optimization:
  max_trials_per_symbol: 200
  parallel_trials: 1
  memory_limit_mb: 8192
```

---

## CLI Usage

### Local Execution (Without Docker)

#### Ingestion Worker

```bash
# Run once and exit
python -m src.cli.worker ingestion --once

# Run continuously
python -m src.cli.worker ingestion

# Custom config
python -m src.cli.worker ingestion \
    --config configs/ingestion.yaml \
    --db-path artifacts/autotrader.db \
    --poll-interval 600 \
    --metrics-port 9100
```

#### Backtest Worker

```bash
python -m src.cli.worker backtest \
    --data-dir data/processed/features \
    --symbols "AAPL,MSFT,NVDA" \
    --metrics-port 9101
```

#### Optimization Worker

```bash
python -m src.cli.worker optimize \
    --data-dir data/processed/features \
    --symbols "AAPL,MSFT,NVDA" \
    --trials 50 \
    --splits 5 \
    --metrics-port 9102 \
    --output-dir reports/optuna
```

---

## Monitoring

### Prometheus Metrics

All workers expose these metrics on `/metrics`:

#### Worker-Specific Metrics

```prometheus
# Job completion counters
worker_jobs_total{worker_type="ingestion",job_type="ingestion_cycle",status="success"} 42

# Job duration histogram
worker_job_duration_seconds_bucket{worker_type="backtest",job_type="backtest",le="10.0"} 15

# Active jobs gauge
worker_active_jobs{worker_type="optimization"} 1

# Health status
worker_health_status{worker_type="ingestion"} 1
```

#### Ingestion Worker Metrics (from `src.core.worker`)

```prometheus
ingestion_cycle_duration_seconds{worker="ingestion-worker-1",outcome="success"} 12.456
ingestion_items_total{worker="ingestion-worker-1",source="news"} 1234
ingestion_cycle_errors_total{worker="ingestion-worker-1",stage="cycle"} 0
ingestion_last_success_timestamp{worker="ingestion-worker-1"} 1729800000
```

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/your_grafana_password):

1. **Workers Overview**: Real-time job status, completion rates, error rates
2. **Ingestion Dashboard**: Data collection metrics, API health, rate limiting
3. **Backtest Dashboard**: Strategy performance, execution time, resource usage
4. **Optimization Dashboard**: Trial progress, best parameters, convergence plots

### Health Checks

```bash
# Check worker health via Docker
docker-compose ps

# Check database exists (ingestion worker health)
docker-compose exec worker-ingestion python -c "from pathlib import Path; print(Path('/app/artifacts/autotrader.db').exists())"

# Check metrics endpoint
curl http://localhost:9100/metrics
curl http://localhost:9101/metrics
curl http://localhost:9102/metrics
```

---

## Production Deployment

### Deployment Profiles

```bash
# Minimal stack (just infrastructure)
docker-compose up -d

# Production stack (with ingestion worker)
docker-compose --profile production up -d

# All workers (development/testing)
docker-compose --profile workers up -d

# Specific worker combinations
docker-compose --profile production --profile optimization up -d
```

### Scaling Workers

```bash
# Scale ingestion workers (horizontal scaling)
docker-compose --profile production up -d --scale worker-ingestion=3

# Each worker gets unique name: ingestion-worker-1, ingestion-worker-2, ingestion-worker-3
# Configure WORKER_NAME env var per instance for proper metrics labeling
```

### Resource Limits

Edit `docker-compose.yml` to add resource constraints:

```yaml
worker-optimization:
  deploy:
    resources:
      limits:
        cpus: '4.0'
        memory: 8G
      reservations:
        cpus: '2.0'
        memory: 4G
```

### Graceful Shutdown

```bash
# Stop workers gracefully (waits for job completion)
docker-compose stop worker-ingestion worker-backtest worker-optimization

# Force stop after 30 seconds
docker-compose down -t 30
```

---

## Troubleshooting

### Common Issues

#### 1. Worker Not Starting

```bash
# Check logs
docker-compose logs worker-ingestion

# Common causes:
# - Missing .env file → Create .env with required vars
# - Database path not writable → Check volume permissions
# - Config file not found → Verify configs/ directory mounted
```

#### 2. Metrics Not Appearing

```bash
# Verify metrics port accessible
curl http://localhost:9100/metrics

# Check Prometheus config
cat infrastructure/prometheus/prometheus.yml

# Restart Prometheus to reload config
docker-compose restart prometheus
```

#### 3. Out of Memory (OOM)

```bash
# Check container memory usage
docker stats worker-optimization

# Solutions:
# - Reduce parallel_trials in configs/workers.yaml
# - Increase Docker memory limit
# - Add resource limits in docker-compose.yml
```

#### 4. Database Locked

```bash
# SQLite database locked (multiple writers)
# Solution: Ensure only one ingestion worker writes to database
docker-compose ps | grep worker-ingestion
# Scale down to 1: docker-compose --profile production up -d --scale worker-ingestion=1
```

### Debug Mode

```bash
# Run with debug logging
docker-compose run --rm \
    -e LOG_LEVEL=DEBUG \
    worker-ingestion python -m src.cli.worker ingestion --once

# Interactive debugging
docker-compose run --rm --entrypoint /bin/bash worker-ingestion
```

### Logs

```bash
# Stream logs
docker-compose logs -f worker-ingestion

# Last 100 lines
docker-compose logs --tail=100 worker-optimization

# Export logs
docker-compose logs worker-backtest > backtest_logs.txt
```

---

## Maintenance

### Regular Tasks

#### Daily
- Check worker health status in Grafana
- Monitor error rates and job completion times
- Review disk usage for databases and logs

#### Weekly
- Rotate logs (automatic with `configs/workers.yaml` settings)
- Backup `artifacts/autotrader.db` database
- Review optimization results and update production configs

#### Monthly
- Update Docker images: `docker-compose pull && docker-compose up -d`
- Review and prune old artifacts: `docker system prune -a`
- Audit resource usage and adjust limits

### Backup Strategy

```bash
# Backup ingestion database
docker-compose exec worker-ingestion cp /app/artifacts/autotrader.db /app/artifacts/autotrader.db.backup

# Copy to host
docker cp $(docker-compose ps -q worker-ingestion):/app/artifacts/autotrader.db.backup ./backups/

# Backup optimization results
tar -czf optuna_results_$(date +%Y%m%d).tar.gz reports/optuna/
```

---

## Next Steps

1. **Set up alerting**: Configure PagerDuty/Slack alerts for worker failures
2. **Implement job queue**: Use Celery or RabbitMQ for distributed job processing
3. **Add autoscaling**: Kubernetes HPA based on queue depth and CPU usage
4. **Enhance monitoring**: Add custom dashboards for business metrics
5. **CI/CD pipeline**: Automate worker deployment on code changes

---

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Prometheus Metrics Best Practices](https://prometheus.io/docs/practices/naming/)
- [Optuna Optimization Guide](https://optuna.readthedocs.io/)
- [Grafana Dashboard Setup](https://grafana.com/docs/grafana/latest/dashboards/)
