# Research Workspace API Documentation

This document describes the API endpoints for the Research workspace with FREE-first capabilities.

## Overview

The Research API provides:
- Ranked token lists with advanced filters
- Token drilldown pages with evidence panels
- Data provenance tracking
- Freshness badges for data sources
- FREE/paid capability indicators

## Endpoints

### GET /api/tokens

Get all scanned tokens with summary information and filters.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `min_score` | float | Minimum final score (0-1) | `0.7` |
| `min_confidence` | float | Minimum confidence level (0-1) | `0.75` |
| `min_liquidity` | float | Minimum liquidity in USD | `1000000` |
| `max_liquidity` | float | Maximum liquidity in USD | `10000000` |
| `safety_filter` | string | Safety filter: "safe", "flagged", "all" | `"safe"` |
| `time_window_hours` | integer | Only include tokens updated within this many hours | `24` |
| `include_provenance` | boolean | Include provenance information | `true` |
| `include_freshness` | boolean | Include freshness badges | `true` |

**Response:**

```json
[
  {
    "symbol": "LINK",
    "price": 15.42,
    "liquidity_usd": 250000000,
    "gem_score": 0.85,
    "final_score": 0.82,
    "confidence": 0.95,
    "flagged": false,
    "narrative_momentum": 0.78,
    "sentiment_score": 0.65,
    "holders": 450000,
    "updated_at": "2025-10-22T03:49:47Z",
    "provenance": {
      "artifact_id": "token_LINK_1729567787",
      "data_sources": ["coingecko", "dexscreener", "blockscout"],
      "pipeline_version": "2.0.0",
      "created_at": "2025-10-22T03:49:47Z"
    },
    "freshness": {
      "coingecko": {
        "source_name": "coingecko",
        "last_updated": "2025-10-22T03:49:47Z",
        "data_age_seconds": 0.5,
        "freshness_level": "fresh",
        "is_free": true,
        "update_frequency_seconds": 300
      },
      "dexscreener": {
        "source_name": "dexscreener",
        "last_updated": "2025-10-22T03:49:47Z",
        "data_age_seconds": 1.2,
        "freshness_level": "fresh",
        "is_free": true,
        "update_frequency_seconds": 300
      },
      "blockscout": {
        "source_name": "blockscout",
        "last_updated": "2025-10-22T03:49:47Z",
        "data_age_seconds": 0.8,
        "freshness_level": "fresh",
        "is_free": true,
        "update_frequency_seconds": 300
      }
    }
  }
]
```

**Example Requests:**

```bash
# Get all tokens
curl "http://localhost:8000/api/tokens"

# Get high-scoring tokens only
curl "http://localhost:8000/api/tokens?min_score=0.7"

# Get safe tokens with high confidence
curl "http://localhost:8000/api/tokens?min_confidence=0.75&safety_filter=safe"

# Get recently updated tokens
curl "http://localhost:8000/api/tokens?time_window_hours=1"
```

### GET /api/tokens/{symbol}

Get detailed information for a specific token with evidence panels.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `symbol` | string | Token symbol (e.g., LINK, UNI, AAVE, PEPE) |

**Query Parameters:**

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `include_provenance` | boolean | Include provenance information | `true` |
| `include_freshness` | boolean | Include freshness badges | `true` |

**Response:**

```json
{
  "symbol": "LINK",
  "price": 15.42,
  "liquidity_usd": 250000000,
  "gem_score": 0.85,
  "final_score": 0.82,
  "confidence": 0.95,
  "flagged": false,
  "narrative_momentum": 0.78,
  "sentiment_score": 0.65,
  "holders": 450000,
  "updated_at": "2025-10-22T03:49:47Z",
  
  "provenance": {
    "artifact_id": "token_LINK_1729567787",
    "data_sources": ["coingecko", "dexscreener", "blockscout"],
    "pipeline_version": "2.0.0",
    "created_at": "2025-10-22T03:49:47Z",
    "clickable_links": {
      "coingecko": "https://www.coingecko.com/en/coins/chainlink",
      "dexscreener": "https://dexscreener.com/ethereum/0x514910771AF9Ca656af840dff83E8264EcF986CA",
      "blockscout": "https://eth.blockscout.com/token/0x514910771AF9Ca656af840dff83E8264EcF986CA"
    }
  },
  
  "freshness": {
    "coingecko": {
      "source_name": "coingecko",
      "last_updated": "2025-10-22T03:49:47Z",
      "data_age_seconds": 0.5,
      "freshness_level": "fresh",
      "is_free": true,
      "update_frequency_seconds": 300
    }
  },
  
  "evidence_panels": {
    "price_volume": {
      "title": "Price & Volume Analysis",
      "confidence": 0.95,
      "freshness": "fresh",
      "source": "coingecko",
      "is_free": true,
      "data": {
        "price": 15.42,
        "volume_24h": 250000000
      }
    },
    "liquidity": {
      "title": "Liquidity Analysis",
      "confidence": 0.95,
      "freshness": "fresh",
      "source": "dexscreener",
      "is_free": true,
      "data": {
        "liquidity_usd": 250000000
      }
    },
    "narrative": {
      "title": "Narrative Analysis (NVI)",
      "confidence": 0.855,
      "freshness": "fresh",
      "source": "groq_ai",
      "is_free": true,
      "data": {
        "sentiment_score": 0.65,
        "momentum": 0.78,
        "themes": ["DeFi", "Oracle", "Smart Contracts"],
        "volatility": 0.45,
        "meme_momentum": 0.3
      }
    },
    "tokenomics": {
      "title": "Tokenomics & Unlocks",
      "confidence": 0.95,
      "freshness": "fresh",
      "source": "blockscout",
      "is_free": true,
      "data": {
        "holders": 450000,
        "unlock_events": []
      }
    },
    "safety": {
      "title": "Contract Safety Checks",
      "confidence": 0.95,
      "freshness": "fresh",
      "source": "blockscout",
      "is_free": true,
      "data": {
        "score": 0.9,
        "severity": "low",
        "findings": [],
        "flags": {}
      }
    }
  },
  
  "market_snapshot": { ... },
  "narrative": { ... },
  "safety_report": { ... },
  "news_items": [ ... ],
  "sentiment_metrics": { ... },
  "technical_metrics": { ... },
  "security_metrics": { ... },
  "unlock_events": [ ... ],
  "narratives": [ ... ],
  "keywords": [ ... ],
  "artifact": { ... },
  "tree": { ... }
}
```

**Example Requests:**

```bash
# Get detailed token information
curl "http://localhost:8000/api/tokens/LINK"

# Get token information without provenance
curl "http://localhost:8000/api/tokens/LINK?include_provenance=false"
```

## Data Freshness Levels

The API tracks data freshness and classifies it into four levels:

| Level | Description | Age |
|-------|-------------|-----|
| `fresh` | 🟢 Fresh | < 5 minutes |
| `recent` | 🔵 Recent | < 1 hour |
| `stale` | 🟡 Stale | < 24 hours |
| `outdated` | 🔴 Outdated | > 24 hours |

## FREE Data Sources

All data sources used in the Research workspace are FREE:

- **CoinGecko** - Price, volume, and market data
- **Dexscreener** - DEX liquidity and trading data
- **Blockscout** - On-chain contract and holder data
- **Groq AI** - Narrative analysis (FREE tier)

## Performance

The API is designed to meet the following performance targets:

- **List endpoint** (`/api/tokens`): < 2.5s p75 latency
- **Detail endpoint** (`/api/tokens/{symbol}`): < 3s p75 latency
- **Data freshness**: Tracked in real-time
- **Caching**: 5-minute TTL for scan results

## Error Responses

All endpoints return standard HTTP error codes:

- `400 Bad Request` - Invalid query parameters
- `404 Not Found` - Token not found
- `500 Internal Server Error` - Server error

Example error response:

```json
{
  "detail": "Token not found"
}
```

## Rate Limiting

The API uses rate limiting to ensure fair usage:

- Token list endpoint: 30 requests/minute per IP
- Token detail endpoint: 10 requests/minute per IP

## Frontend Integration

The dashboard UI automatically fetches and displays:

- Token list with freshness indicators (🟢🔵🟡🔴)
- FREE data badges (🆓)
- Evidence panels with confidence levels
- Clickable provenance links
- Filter options (All, High Score, High Confidence, Flagged, FREE Only, Fresh Data)

## See Also

- [Project README](../README.md)
- [API Integration Tests](../tests/test_research_api.py)
- [Dashboard Components](../dashboard/src/components/)
