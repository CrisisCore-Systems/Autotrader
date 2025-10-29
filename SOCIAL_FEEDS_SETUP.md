# Social Feed Integration - Twitter & Reddit

## Overview

The AutoTrader scanning system now supports **Twitter** and **Reddit** social sentiment feeds for token analysis.

## Current Status

### ✅ Reddit - WORKING (No API Keys Required)
- Uses public read-only API
- No authentication needed for basic usage
- Fetches posts from crypto subreddits:
  - r/CryptoCurrency
  - r/CryptoMarkets
  - r/altcoin
  - r/defi
  - r/ethtrader
  - r/Bitcoin

### ⚠️ Twitter - Requires API Key
- Needs Twitter API v2 Bearer Token
- Free tier available (but requires account)
- Enhanced sentiment data with engagement metrics

## Test Results

```
✅ Reddit client working correctly (public API)!
   - Fetched 5 BTC-related posts from multiple subreddits
   - Score: 1063 (top post)
   - Successfully normalized to social post format
```

## Quick Start

### 1. Test Reddit (Works Immediately)

```powershell
python Autotrader\test_social_feeds.py
```

### 2. Enable Twitter (Optional)

#### Get Twitter API Key:
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a project and app (Free tier available)
3. Generate a **Bearer Token** under "Keys and tokens"

#### Set Environment Variable:
```powershell
# PowerShell
$env:TWITTER_BEARER_TOKEN = "your_bearer_token_here"

# Or add to .env file
TWITTER_BEARER_TOKEN=your_bearer_token_here
```

### 3. Use Social Feeds in API

#### Test Social Feed Endpoint:
```powershell
$json = @'
{
  "token_symbol": "BTC",
  "hours_back": 24,
  "limit": 50
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/scan/social-feeds' -Method POST -Body $json -ContentType 'application/json' | ConvertTo-Json -Depth 5
```

#### Expected Response:
```json
{
  "token_symbol": "BTC",
  "twitter_posts": [...],  // If Twitter configured
  "reddit_posts": [
    {
      "id": "1oie58h",
      "platform": "reddit",
      "author": "someuser",
      "content": "Giant Bitcoin drone show in Switzerland...",
      "url": "https://reddit.com/r/CryptoCurrency/comments/...",
      "posted_at": "2025-10-28T12:34:56Z",
      "metrics": {
        "upvotes": 1063,
        "score": 1063,
        "comments": 89,
        "upvote_ratio": 0.95
      },
      "subreddit": "CryptoCurrency"
    }
  ],
  "total_posts": 20,
  "sentiment_summary": {
    "twitter_count": 0,
    "reddit_count": 20,
    "total_engagement": 5432,
    "avg_engagement_per_post": 271.6
  }
}
```

## Integration with Scans

Social feeds are **automatically included** in scans when credentials are configured:

```powershell
$json = @'
{
  "symbol": "ETH",
  "coingecko_id": "ethereum",
  "contract_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
  "narratives": ["DeFi", "Smart Contracts"]
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/scan/run' -Method POST -Body $json -ContentType 'application/json'
```

The scanner will:
1. ✅ Fetch Reddit posts (always works)
2. ⚠️ Fetch Twitter tweets (if TWITTER_BEARER_TOKEN set)
3. Include social sentiment in gem score calculation

## API Limits

### Reddit (Public API)
- **Rate Limit**: 60 requests per minute
- **Cost**: Free, no authentication
- **Data**: Last 1000 posts per subreddit

### Twitter (API v2 Free Tier)
- **Rate Limit**: 450 requests per 15 minutes
- **Cost**: Free tier available
- **Data**: Last 7 days of tweets
- **Search**: Up to 100 tweets per request

## Files Added

1. `src/core/reddit_client.py` - Reddit API client (public + OAuth)
2. `src/core/twitter_client.py` - Twitter API v2 client (existing)
3. `test_social_feeds.py` - Test script for both platforms
4. `src/api/routes/scan.py` - Updated with social feed integration

## Next Steps

- ✅ Reddit working out-of-the-box
- ⚠️ Twitter requires API key (optional but recommended)
- Social sentiment automatically included in gem score when available
- No code changes needed - just set environment variables

## Troubleshooting

### "Reddit client working correctly" but no data in scans
- Check that the scanner is using the latest code (restart API)
- Verify environment variables are set if using Twitter

### Twitter 401 Unauthorized
- Check `TWITTER_BEARER_TOKEN` is correctly set
- Verify token hasn't expired
- Ensure token has read permissions

### Rate Limit Errors
- Reddit: Wait 60 seconds
- Twitter: Wait 15 minutes
- Consider caching responses (already implemented)

## Example Output

```
🔍 Testing Reddit Public API (no credentials required)...
✓ Reddit client initialized (public read-only mode)
✓ Fetched 5 posts
✓ Found 5 BTC-related posts

Top BTC post:
  Content: Giant Bitcoin drone show in Switzerland showing BTC eating fiat currencies...
  Score: 1063
  Subreddit: r/CryptoCurrency
  
✅ Reddit client working correctly (public API)!
```
