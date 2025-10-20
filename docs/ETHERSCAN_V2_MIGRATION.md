# Etherscan API V2 Migration Guide

## Overview

Etherscan has deprecated their V1 API and migrated to V2. This guide explains the changes and how to update your configuration.

## Key Differences

### V1 API (Deprecated)
- **Base URL**: `https://api.etherscan.io/api`
- **API Key**: Optional for basic usage, limited rate limits
- **Parameters**: module, action, address, apikey

### V2 API (Current)
- **Base URL**: `https://api.etherscan.io/v2/api`
- **API Key**: **Required** - Get one at https://etherscan.io/apis
- **Additional Parameters**: Requires `chainid` (e.g., "1" for Ethereum mainnet)
- **Rate Limits**: Better rate limits with valid API key

## Current Status

The AutoTrader scanner currently uses **graceful degradation** for Etherscan API failures:
- Contract verification failures don't block scans
- System continues with reduced security analysis features
- All tokens scan successfully without contract data

## Migration Options

### Option 1: Continue with Graceful Degradation (Current - Recommended)
✅ **No action needed**
- System works without Etherscan contract verification
- All tokens scan successfully
- Security analysis uses neutral defaults

### Option 2: Upgrade to V2 API (For Enhanced Security Analysis)
1. **Get Etherscan API Key** (if you don't have one)
   - Go to https://etherscan.io/apis
   - Sign up for a free account
   - Generate an API key

2. **Update `.env` file**:
   ```bash
   ETHERSCAN_API_KEY=your_new_v2_api_key
   ETHERSCAN_API_VERSION=v2  # Optional: defaults to v1
   ETHERSCAN_BASE_URL=https://api.etherscan.io/v2/api  # Optional
   ETHERSCAN_CHAIN_ID=1  # Optional: defaults to 1 (Ethereum mainnet)
   ```

3. **Update configuration in code** (if not using env vars):
   ```python
   from src.core.clients import EtherscanClient
   
   # V2 API with explicit configuration
   etherscan_client = EtherscanClient(
       api_key="your_api_key",
       base_url="https://api.etherscan.io/v2/api",
       api_version="v2",
       chain_id=1  # Ethereum mainnet
   )
   
   # Or let it auto-detect from base_url
   etherscan_client = EtherscanClient(
       api_key="your_api_key",
       base_url="https://api.etherscan.io/v2/api"
   )
   ```

## Benefits of V2 Migration

With a valid V2 API key, you'll gain:
- ✅ Contract source code verification
- ✅ Enhanced security analysis
- ✅ Better rate limits
- ✅ Support for multiple chains

## Testing Your Configuration

Run the test script to verify your API setup:

```bash
python test_etherscan_v2.py
```

This will test both V1 and V2 endpoints and show you what's working.

## Troubleshooting

### "Missing/Invalid API Key" Error
- V2 API **requires** a valid API key
- Free tier keys from V1 may not work with V2
- Generate a new key at https://etherscan.io/apis

### "Missing chainid parameter" Error
- V2 API requires the `chainid` parameter
- For Ethereum mainnet, use `chainid=1`
- See https://api.etherscan.io/v2/chainlist for other chains

### Contract Verification Still Failing
- Ensure your API key is valid and active
- Check rate limits (5 requests per second on free tier)
- Verify the base_url includes `/v2/`

## Current Implementation

The scanner's `EtherscanClient` now supports both V1 and V2:

```python
# V1 (default, gracefully fails)
EtherscanClient(api_key="your_key")

# V2 (requires valid API key)
EtherscanClient(
    api_key="your_key",
    api_version="v2",
    chain_id=1
)
```

## Recommendation

**For most users**: Keep the current graceful degradation approach. The scanner works perfectly without Etherscan contract verification, and all tokens scan successfully with volume-based liquidity checks.

**For advanced users**: Upgrade to V2 if you need enhanced security analysis and contract verification features.
