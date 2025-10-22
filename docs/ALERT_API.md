# Alert System API Documentation

This document describes the Alert Rule Schema + CRUD + Alerts Inbox MVP API endpoints.

## Table of Contents

1. [Alert Rules CRUD](#alert-rules-crud)
2. [Alerts Inbox](#alerts-inbox)
3. [Analytics](#analytics)
4. [Data Models](#data-models)

---

## Alert Rules CRUD

### Create Alert Rule

**POST** `/api/alerts/rules`

Create a new alert rule with configurable conditions, severity, channels, and suppression.

**Request Body:**
```json
{
  "id": "high_gemscore_alert",  // Optional, auto-generated if not provided
  "description": "High GemScore Alert",
  "enabled": true,
  "condition": {
    "metric": "gem_score",
    "operator": "gte",
    "threshold": 70
  },
  "where": {
    "safety_ok": true
  },
  "severity": "high",
  "channels": ["telegram", "slack"],
  "suppression_duration": 3600,
  "tags": ["gemscore", "high-priority"],
  "version": "v2"
}
```

**Response:** `200 OK`
```json
{
  "id": "high_gemscore_alert",
  "description": "High GemScore Alert",
  "enabled": true,
  "condition": { ... },
  "severity": "high",
  "channels": ["telegram", "slack"],
  "suppression_duration": 3600,
  "tags": ["gemscore", "high-priority"],
  "version": "v2",
  "created_at": "2025-10-22T09:00:00Z",
  "updated_at": "2025-10-22T09:00:00Z"
}
```

---

### List Alert Rules

**GET** `/api/alerts/rules`

List all alert rules with optional filtering.

**Query Parameters:**
- `enabled_only` (boolean, optional): Only return enabled rules

**Response:** `200 OK`
```json
[
  {
    "id": "rule_1",
    "description": "High GemScore Alert",
    "enabled": true,
    ...
  },
  ...
]
```

---

### Get Alert Rule

**GET** `/api/alerts/rules/{rule_id}`

Get details of a specific alert rule.

**Response:** `200 OK` or `404 Not Found`

---

### Update Alert Rule

**PUT** `/api/alerts/rules/{rule_id}`

Update an existing alert rule. Only provided fields will be updated.

**Request Body:**
```json
{
  "description": "Updated description",
  "enabled": false,
  "severity": "critical"
}
```

**Response:** `200 OK` or `404 Not Found`

---

### Delete Alert Rule

**DELETE** `/api/alerts/rules/{rule_id}`

Delete an alert rule.

**Response:** `200 OK` or `404 Not Found`
```json
{
  "status": "deleted",
  "rule_id": "rule_1"
}
```

---

## Alerts Inbox

### List Inbox Alerts

**GET** `/api/alerts/inbox`

List alerts from inbox with pagination and filters.

**Query Parameters:**
- `status` (string, optional): Filter by status (pending, acknowledged, snoozed, resolved)
- `severity` (string, optional): Filter by severity (info, warning, high, critical)
- `limit` (integer, default: 100): Maximum number of alerts to return
- `offset` (integer, default: 0): Pagination offset

**Response:** `200 OK`
```json
{
  "alerts": [
    {
      "id": "alert_1",
      "rule_id": "high_gemscore_alert",
      "token_symbol": "ETH",
      "message": "GemScore threshold exceeded",
      "severity": "high",
      "status": "pending",
      "metadata": {
        "score": 75,
        "confidence": 0.85
      },
      "labels": ["urgent"],
      "provenance_links": {
        "coingecko": "https://coingecko.com/eth"
      },
      "triggered_at": "2025-10-22T09:00:00Z",
      "acknowledged_at": null,
      "snoozed_until": null,
      "resolved_at": null
    },
    ...
  ],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

---

### Acknowledge Alert

**POST** `/api/alerts/inbox/{alert_id}/acknowledge`

Mark an alert as acknowledged.

**Response:** `200 OK` or `404 Not Found`
```json
{
  "id": "alert_1",
  "status": "acknowledged",
  "acknowledged_at": "2025-10-22T09:15:00Z",
  ...
}
```

---

### Snooze Alert

**POST** `/api/alerts/inbox/{alert_id}/snooze`

Snooze an alert for a specified duration.

**Query Parameters:**
- `duration_seconds` (integer, default: 3600): Snooze duration in seconds

**Response:** `200 OK` or `404 Not Found`
```json
{
  "id": "alert_1",
  "status": "snoozed",
  "snoozed_until": "2025-10-22T10:15:00Z",
  ...
}
```

---

### Update Alert Labels

**PUT** `/api/alerts/inbox/{alert_id}/labels`

Update labels for an alert.

**Request Body:**
```json
["reviewed", "escalated", "high-priority"]
```

**Response:** `200 OK` or `404 Not Found`
```json
{
  "id": "alert_1",
  "labels": ["reviewed", "escalated", "high-priority"],
  ...
}
```

---

## Analytics

### Get Delivery Analytics

**GET** `/api/alerts/analytics/delivery`

Get alert delivery latency metrics.

**Response:** `200 OK`
```json
{
  "average_delivery_latency_ms": 245.5,
  "total_deliveries": 1234,
  "dedupe_rate": 12.5
}
```

---

### Get Alert Performance

**GET** `/api/alerts/analytics/performance`

Get alert rule performance metrics.

**Response:** `200 OK`
```json
{
  "total_alerts": 1234,
  "alerts_by_severity": {
    "info": 123,
    "warning": 456,
    "high": 234,
    "critical": 421
  },
  "alerts_by_rule": {
    "high_gemscore_alert": 567,
    "liquidity_threshold": 345,
    ...
  },
  "acknowledgement_rate": 78.5,
  "average_delivery_latency_ms": 245.5,
  "dedupe_rate": 12.5
}
```

---

## Data Models

### AlertRule

```typescript
{
  id: string;
  description: string;
  enabled: boolean;
  condition: {
    metric: string;      // e.g., "gem_score", "confidence", "liquidity_usd"
    operator: string;    // "lt", "lte", "eq", "neq", "gte", "gt"
    threshold: number | string;
  };
  where: Record<string, any>;  // Additional filters
  severity: "info" | "warning" | "high" | "critical";
  channels: string[];  // ["telegram", "slack", "email", "webhook"]
  suppression_duration: number;  // seconds
  tags: string[];
  version: string;  // "v2"
  created_at: string;  // ISO timestamp
  updated_at: string;  // ISO timestamp
}
```

### AlertInboxItem

```typescript
{
  id: string;
  rule_id: string;
  token_symbol: string;
  message: string;
  severity: "info" | "warning" | "high" | "critical";
  status: "pending" | "acknowledged" | "snoozed" | "resolved";
  metadata: Record<string, any>;
  labels: string[];
  provenance_links: Record<string, string>;
  triggered_at: string;  // ISO timestamp
  acknowledged_at?: string;  // ISO timestamp
  snoozed_until?: string;  // ISO timestamp
  resolved_at?: string;  // ISO timestamp
}
```

---

## Features

### Rate Limiting

All notification channels have built-in rate limiting:
- **Telegram**: 20 requests/minute
- **Slack**: 10 requests/minute
- **Email**: 30 requests/minute
- **Webhook**: 60 requests/minute

### Deduplication

Alerts are automatically deduplicated based on channel and message content with a configurable TTL (default: 3600 seconds).

### Suppression

Alert rules support suppression duration to prevent alert fatigue. Once an alert is triggered, subsequent matching alerts within the suppression window are automatically suppressed.

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request data
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error responses include a detail message:

```json
{
  "detail": "Error message here"
}
```
