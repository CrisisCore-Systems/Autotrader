# Health & Observability API Documentation

## Overview

The Health API provides endpoints for monitoring system health, data freshness, broker connectivity, rate limits, worker queues, and security checks. These endpoints power the Operations & Observability Dashboard.

## Base URL

```
/api/health
```

## Endpoints

### GET /api/health/freshness

Returns freshness status for all data ingestion sources.

**Response:**
```json
{
  "sources": {
    "coingecko": {
      "display_name": "CoinGecko",
      "last_success_at": "2025-10-22T05:30:00Z",
      "data_age_seconds": 120.5,
      "freshness_level": "fresh",
      "is_free": true,
      "update_frequency_seconds": 300,
      "error_rate": 0.02,
      "latency_ms": 450.2
    }
  },
  "timestamp": "2025-10-22T05:32:00Z"
}
```

**Freshness Levels:**
- `fresh`: < 5 minutes old
- `recent`: < 1 hour old
- `stale`: < 24 hours old
- `outdated`: > 24 hours old

### GET /api/health/sla

Returns SLA metrics for all monitored data sources.

**Response:**
```json
[
  {
    "source_name": "coingecko",
    "status": "HEALTHY",
    "latency_p50": 200.5,
    "latency_p95": 450.2,
    "latency_p99": 800.1,
    "success_rate": 0.98,
    "uptime_percentage": 99.5
  }
]
```

**Status Values:**
- `HEALTHY`: All metrics within thresholds
- `DEGRADED`: Some metrics approaching thresholds
- `FAILED`: One or more metrics exceeding thresholds

### GET /api/health/circuit-breakers

Returns circuit breaker status for all services.

**Response:**
```json
[
  {
    "breaker_name": "coingecko_api",
    "state": "CLOSED",
    "failure_count": 0
  }
]
```

**Circuit States:**
- `CLOSED`: Normal operation, requests flow through
- `HALF_OPEN`: Testing if service recovered
- `OPEN`: Service unavailable, requests rejected

### GET /api/health/overview

Returns overall system health combining all metrics.

**Response:**
```json
{
  "overall_status": "HEALTHY",
  "healthy_sources": [...],
  "degraded_sources": [...],
  "failed_sources": [...],
  "circuit_breakers": {...},
  "cache_stats": {...}
}
```

### GET /api/health/rate-limits

Returns rate limiting status for all APIs.

**Response:**
```json
{
  "rate_limits": {
    "coingecko": {
      "name": "CoinGecko API",
      "is_free": true,
      "limit_per_minute": 30,
      "estimated_usage": 15,
      "status": "healthy",
      "reset_at": null
    }
  },
  "timestamp": "2025-10-22T05:32:00Z"
}
```

### GET /api/health/queues

Returns worker queue status for background jobs.

**Response:**
```json
{
  "queues": {
    "scanner": {
      "name": "Token Scanner Queue",
      "pending_jobs": 0,
      "active_workers": 1,
      "completed_today": 24,
      "avg_processing_time_ms": 1500,
      "status": "healthy"
    }
  },
  "timestamp": "2025-10-22T05:32:00Z"
}
```

### GET /api/health/security

Returns security check status including credential scrubbing and vulnerability scanning.

**Response:**
```json
{
  "checks": {
    "ibkr_fa_scrubbing": {
      "name": "IBKR FA Credential Scrubbing",
      "status": "active",
      "last_check": "2025-10-22T05:30:00Z",
      "issues_found": 0,
      "description": "Ensures IBKR FA account credentials are not logged"
    },
    "dependency_scan": {
      "name": "Dependency Vulnerability Scan",
      "status": "passing",
      "last_check": "2025-10-22T05:30:00Z",
      "critical_issues": 0,
      "high_issues": 0,
      "medium_issues": 0,
      "description": "Scans Python dependencies for known vulnerabilities"
    }
  },
  "overall_status": "passing",
  "timestamp": "2025-10-22T05:32:00Z"
}
```

## Rate Limits

All health endpoints have a rate limit of **60 requests per minute per IP address**.

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK`: Request successful
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Dashboard Integration

These endpoints are used by the Operations & Observability Dashboard components:
- **FreshnessPanel**: Uses `/api/health/freshness`
- **BrokerStatus**: Uses `/api/trading/broker-status` (existing)
- **SLADashboard**: Uses `/api/health/sla` and `/api/health/circuit-breakers`
- **RateLimitingPanel**: Uses `/api/health/rate-limits`
- **WorkerQueuesPanel**: Uses `/api/health/queues`
- **SecurityChecksPanel**: Uses `/api/health/security`

## Monitoring Best Practices

1. **Automatic Refresh**: All dashboard panels auto-refresh every 10-60 seconds
2. **Color Coding**: 
   - Green: Healthy/Normal
   - Yellow: Warning/Degraded
   - Red: Error/Failed
3. **Alerting**: Set up alerts when `overall_status` is not `HEALTHY`
4. **Runbooks**: See [Operations Runbooks](./OPERATIONS_RUNBOOKS.md) for troubleshooting guides
