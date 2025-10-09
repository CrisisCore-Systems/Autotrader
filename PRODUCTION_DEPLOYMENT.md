# Production Deployment Guide for AutoTrader

## Overview

This guide covers production deployment of AutoTrader using Docker Compose with production-hardened configurations.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 16GB RAM minimum (32GB recommended)
- 100GB SSD storage minimum
- Linux host (Ubuntu 22.04 LTS recommended)

## Security Hardening Features

✅ **Resource Limits**: CPU and memory limits prevent resource exhaustion
✅ **Read-Only Filesystems**: Containers run with read-only root filesystems
✅ **No Root**: All services run as non-root users
✅ **Dropped Capabilities**: Minimal Linux capabilities granted
✅ **Persistent Volumes**: Data persisted outside containers
✅ **Health Checks**: Automatic container health monitoring
✅ **Pinned Versions**: No `:latest` tags, all versions explicit
✅ **Network Isolation**: Services communicate on isolated bridge network
✅ **Log Rotation**: Automatic log rotation to prevent disk exhaustion

## Deployment Steps

### 1. Prepare Environment

```bash
# Create data directory
sudo mkdir -p /var/lib/autotrader/{postgres,milvus}
sudo chown -R 1000:1000 /var/lib/autotrader

# Copy environment template
cp .env.production.template .env.production

# Edit with production values
nano .env.production
```

### 2. Configure Secrets

**IMPORTANT**: Never commit `.env.production` to version control!

Update these critical values:
- `POSTGRES_PASSWORD`: Strong random password (20+ characters)
- `GROQ_API_KEY`: Your Groq API key
- `OPENAI_API_KEY`: Your OpenAI API key (for fallback)
- `SECRET_KEY`: Random 32+ character string
- `GRAFANA_PASSWORD`: Grafana admin password

Generate strong secrets:
```bash
# PostgreSQL password
openssl rand -base64 32

# Application secret key
openssl rand -hex 32
```

### 3. Build Images

```bash
cd infra
docker-compose build --no-cache
```

### 4. Deploy Services

```bash
# Start core services
docker-compose up -d

# Start with monitoring (optional)
docker-compose --profile monitoring up -d
```

### 5. Verify Deployment

```bash
# Check service health
docker-compose ps

# View logs
docker-compose logs -f api

# Check database initialization
docker-compose exec postgres psql -U crisiscore -d voidbloom -c "\dt"

# Test API endpoint
curl http://localhost:8000/health
```

### 6. Configure Monitoring (Optional)

If using the monitoring profile:

1. **Prometheus**: http://localhost:9090
2. **Grafana**: http://localhost:3000
   - Default login: admin / (GRAFANA_PASSWORD from .env)
   - Import dashboards from `infra/grafana/dashboards/`

## Resource Allocation

### Minimum Configuration
- **API**: 0.5 CPU, 512MB RAM
- **Worker**: 1.0 CPU, 1GB RAM
- **PostgreSQL**: 0.5 CPU, 1GB RAM
- **Milvus**: 1.0 CPU, 2GB RAM

### Recommended Production
- **API**: 2.0 CPU, 2GB RAM
- **Worker**: 4.0 CPU, 4GB RAM
- **PostgreSQL**: 2.0 CPU, 4GB RAM
- **Milvus**: 4.0 CPU, 8GB RAM

Adjust limits in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

## Scaling

### Horizontal Scaling

Scale workers for increased throughput:
```bash
docker-compose up -d --scale worker=3
```

### Vertical Scaling

Increase resource limits in `docker-compose.yml` and recreate:
```bash
docker-compose up -d --force-recreate worker
```

## Backup & Recovery

### Database Backup

```bash
# Automated daily backups
docker-compose exec postgres pg_dump -U crisiscore voidbloom | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip -c backup_20250101.sql.gz | docker-compose exec -T postgres psql -U crisiscore voidbloom
```

### Milvus Backup

```bash
# Backup Milvus data
docker-compose exec vector /milvus/bin/milvus backup create --collection-name=your_collection

# Data persisted in /var/lib/autotrader/milvus
tar -czf milvus_backup_$(date +%Y%m%d).tar.gz /var/lib/autotrader/milvus/
```

## Monitoring & Alerting

### Key Metrics to Monitor

1. **API Latency**: p50, p95, p99 response times
2. **Worker Queue Depth**: Backlog of pending tasks
3. **Database Connections**: Active connections vs. limit
4. **Milvus Vector Inserts**: Insert rate and latency
5. **LLM Costs**: Daily spend tracking
6. **Error Rates**: 5xx errors per endpoint

### Prometheus Queries

```promql
# API request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Database connections
pg_stat_database_numbackends

# LLM cost tracking
sum(llm_request_cost_usd) by (provider)
```

### Alert Rules

Configure alerts in `prometheus/alerts.yml`:
- API error rate > 5%
- Database connection pool > 80%
- Disk usage > 85%
- LLM daily cost > threshold

## Security Best Practices

### 1. Network Security
- Use firewall to restrict access to exposed ports
- Consider using reverse proxy (nginx/traefik) with TLS
- Enable Docker daemon TLS authentication

### 2. Secrets Management
- Use Docker secrets or external secret managers (Vault, AWS Secrets Manager)
- Rotate API keys quarterly
- Audit secret access logs

### 3. Container Security
- Scan images with Trivy: `trivy image autotrader-api:latest`
- Enable Docker Content Trust: `export DOCKER_CONTENT_TRUST=1`
- Regularly update base images

### 4. Access Control
- Implement API authentication (JWT tokens)
- Use least-privilege database roles
- Enable audit logging

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Inspect container
docker-compose exec api sh

# Check disk space
df -h
```

### Database Connection Issues

```bash
# Test connectivity
docker-compose exec api python -c "import psycopg2; print('OK')"

# Check PostgreSQL logs
docker-compose logs postgres | grep ERROR
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Restart with lower limits
docker-compose restart worker
```

### Milvus Performance Issues

```bash
# Check Milvus metrics
curl http://localhost:9091/metrics

# Flush collections
docker-compose exec vector milvus-cli flush --collection-name your_collection
```

## Maintenance

### Regular Tasks

1. **Weekly**: Review error logs and metrics
2. **Monthly**: Update Docker images (after testing)
3. **Quarterly**: Rotate API keys and passwords
4. **Annually**: Security audit and penetration testing

### Upgrade Procedure

1. Backup all data
2. Test upgrade in staging environment
3. Schedule maintenance window
4. Pull new images
5. Run database migrations
6. Restart services with zero-downtime strategy
7. Verify health checks
8. Monitor for issues

## Support

For issues or questions:
- GitHub Issues: https://github.com/CrisisCore-Systems/AutoTrader/issues
- Documentation: https://docs.autotrader.io
- Email: support@crisiscore.systems
