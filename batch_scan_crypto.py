"""Batch scan script for multiple cryptocurrencies."""

import json
import time
from datetime import datetime
from typing import List, Dict, Any

import httpx


# Expanded cryptocurrency list with major tokens
CRYPTO_TOKENS = [
    # Top Market Cap
    {
        "symbol": "BTC",
        "coingecko_id": "bitcoin",
        "contract_address": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC on Ethereum
        "narratives": ["Store of Value", "Digital Gold"],
    },
    {
        "symbol": "ETH",
        "coingecko_id": "ethereum",
        "contract_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "narratives": ["Smart Contracts", "DeFi", "NFT"],
    },
    # DeFi Blue Chips
    {
        "symbol": "UNI",
        "coingecko_id": "uniswap",
        "contract_address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "narratives": ["DeFi", "DEX", "AMM"],
    },
    {
        "symbol": "AAVE",
        "coingecko_id": "aave",
        "contract_address": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "narratives": ["DeFi", "Lending", "Money Market"],
    },
    {
        "symbol": "MKR",
        "coingecko_id": "maker",
        "contract_address": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
        "narratives": ["DeFi", "Stablecoin", "Governance"],
    },
    {
        "symbol": "COMP",
        "coingecko_id": "compound-governance-token",
        "contract_address": "0xc00e94Cb662C3520282E6f5717214004A7f26888",
        "narratives": ["DeFi", "Lending", "Governance"],
    },
    {
        "symbol": "CRV",
        "coingecko_id": "curve-dao-token",
        "contract_address": "0xD533a949740bb3306d119CC777fa900bA034cd52",
        "narratives": ["DeFi", "DEX", "Stableswaps"],
    },
    # Infrastructure & Oracles
    {
        "symbol": "LINK",
        "coingecko_id": "chainlink",
        "contract_address": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "narratives": ["Oracle", "DeFi Infrastructure"],
    },
    {
        "symbol": "GRT",
        "coingecko_id": "the-graph",
        "contract_address": "0xc944E90C64B2c07662A292be6244BDf05Cda44a7",
        "narratives": ["Indexing", "Web3", "Infrastructure"],
    },
    # Layer 2 & Scaling
    {
        "symbol": "MATIC",
        "coingecko_id": "matic-network",
        "contract_address": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
        "narratives": ["Layer 2", "Scaling", "Polygon"],
    },
    {
        "symbol": "ARB",
        "coingecko_id": "arbitrum",
        "contract_address": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "narratives": ["Layer 2", "Rollup", "Ethereum Scaling"],
    },
    {
        "symbol": "OP",
        "coingecko_id": "optimism",
        "contract_address": "0x4200000000000000000000000000000000000042",
        "narratives": ["Layer 2", "Optimistic Rollup", "Scaling"],
    },
    # Meme & Community
    {
        "symbol": "PEPE",
        "coingecko_id": "pepe",
        "contract_address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        "narratives": ["Meme", "Community"],
    },
    {
        "symbol": "SHIB",
        "coingecko_id": "shiba-inu",
        "contract_address": "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE",
        "narratives": ["Meme", "DeFi"],
    },
    # Liquid Staking
    {
        "symbol": "LDO",
        "coingecko_id": "lido-dao",
        "contract_address": "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32",
        "narratives": ["Liquid Staking", "DeFi", "Ethereum"],
    },
    {
        "symbol": "RPL",
        "coingecko_id": "rocket-pool",
        "contract_address": "0xD33526068D116cE69F19A9ee46F0bd304F21A51f",
        "narratives": ["Liquid Staking", "Decentralized", "Ethereum"],
    },
    # RWA & Stablecoins
    {
        "symbol": "MKR",
        "coingecko_id": "maker",
        "contract_address": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
        "narratives": ["RWA", "Stablecoin", "DeFi"],
    },
    # Gaming & Metaverse
    {
        "symbol": "IMX",
        "coingecko_id": "immutable-x",
        "contract_address": "0xF57e7e7C23978C3cAEC3C3548E3D615c346e79fF",
        "narratives": ["Gaming", "NFT", "Layer 2"],
    },
    {
        "symbol": "SAND",
        "coingecko_id": "the-sandbox",
        "contract_address": "0x3845badAde8e6dFF049820680d1F14bD3903a5d0",
        "narratives": ["Metaverse", "Gaming", "NFT"],
    },
    # Privacy
    {
        "symbol": "TORN",
        "coingecko_id": "tornado-cash",
        "contract_address": "0x77777FeDdddFfC19Ff86DB637967013e6C6A116C",
        "narratives": ["Privacy", "DeFi"],
    },
]


def scan_token(api_url: str, token_config: Dict[str, Any]) -> Dict[str, Any]:
    """Scan a single token via API.
    
    Args:
        api_url: Base API URL
        token_config: Token configuration dict
        
    Returns:
        Scan result dict with status and data
    """
    try:
        response = httpx.post(
            f"{api_url}/api/scan/run",
            json=token_config,
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        return {
            "status": "success",
            "symbol": token_config["symbol"],
            "data": result,
        }
    except httpx.HTTPError as exc:
        return {
            "status": "error",
            "symbol": token_config["symbol"],
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "status": "error",
            "symbol": token_config["symbol"],
            "error": str(exc),
        }


def batch_scan(
    tokens: List[Dict[str, Any]],
    api_url: str = "http://127.0.0.1:8000",
    delay_seconds: float = 2.0,
) -> List[Dict[str, Any]]:
    """Execute batch scan of multiple tokens.
    
    Args:
        tokens: List of token configurations
        api_url: Base API URL
        delay_seconds: Delay between requests to avoid rate limits
        
    Returns:
        List of scan results
    """
    results = []
    total = len(tokens)
    
    print("=" * 80)
    print(f"Starting Batch Scan: {total} tokens")
    print("=" * 80)
    print()
    
    for i, token in enumerate(tokens, 1):
        symbol = token["symbol"]
        print(f"[{i}/{total}] Scanning {symbol}...", end=" ", flush=True)
        
        start_time = time.time()
        result = scan_token(api_url, token)
        duration = time.time() - start_time
        
        if result["status"] == "success":
            gem_score = result["data"].get("gem_score", 0)
            confidence = result["data"].get("confidence", 0)
            flagged = result["data"].get("flagged", False)
            print(f"✓ Score: {gem_score:.1f} (confidence: {confidence:.0f}%) {'🚩' if flagged else ''}")
        else:
            print(f"✗ Error: {result['error'][:50]}")
        
        result["duration"] = duration
        results.append(result)
        
        # Rate limiting delay
        if i < total:
            time.sleep(delay_seconds)
    
    return results


def print_summary(results: List[Dict[str, Any]]) -> None:
    """Print summary statistics of batch scan.
    
    Args:
        results: List of scan results
    """
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]
    
    print()
    print("=" * 80)
    print("Batch Scan Summary")
    print("=" * 80)
    print(f"Total Tokens: {len(results)}")
    print(f"Successful: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"Failed: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
    print()
    
    if successful:
        # Sort by gem score
        sorted_results = sorted(
            successful,
            key=lambda r: r["data"].get("gem_score", 0),
            reverse=True,
        )
        
        print("Top 10 Gem Scores:")
        print("-" * 80)
        print(f"{'Rank':<6} {'Symbol':<8} {'Score':<8} {'Confidence':<12} {'Flagged':<10} {'Liquidity'}")
        print("-" * 80)
        
        for i, result in enumerate(sorted_results[:10], 1):
            data = result["data"]
            symbol = result["symbol"]
            score = data.get("gem_score", 0)
            confidence = data.get("confidence", 0)
            flagged = "🚩 Yes" if data.get("flagged", False) else "No"
            liquidity_ok = "✓" if data.get("liquidity_ok", False) else "✗"
            
            print(f"{i:<6} {symbol:<8} {score:<8.1f} {confidence:<12.1f} {flagged:<10} {liquidity_ok}")
        
        print()
        print("Bottom 5 Gem Scores:")
        print("-" * 80)
        for i, result in enumerate(sorted_results[-5:], len(sorted_results) - 4):
            data = result["data"]
            symbol = result["symbol"]
            score = data.get("gem_score", 0)
            confidence = data.get("confidence", 0)
            flagged = "🚩 Yes" if data.get("flagged", False) else "No"
            liquidity_ok = "✓" if data.get("liquidity_ok", False) else "✗"
            
            print(f"{i:<6} {symbol:<8} {score:<8.1f} {confidence:<12.1f} {flagged:<10} {liquidity_ok}")
        
        print()
        print("Statistics:")
        print("-" * 80)
        scores = [r["data"].get("gem_score", 0) for r in successful]
        confidences = [r["data"].get("confidence", 0) for r in successful]
        durations = [r["duration"] for r in successful]
        
        print(f"Average Gem Score: {sum(scores)/len(scores):.2f}")
        print(f"Max Gem Score: {max(scores):.2f}")
        print(f"Min Gem Score: {min(scores):.2f}")
        print(f"Average Confidence: {sum(confidences)/len(confidences):.2f}%")
        print(f"Average Scan Duration: {sum(durations)/len(durations):.2f}s")
        print(f"Total Scan Time: {sum(durations):.2f}s")
    
    if failed:
        print()
        print("Failed Scans:")
        print("-" * 80)
        for result in failed:
            print(f"  {result['symbol']}: {result['error'][:60]}")
    
    print("=" * 80)


def save_results(results: List[Dict[str, Any]], filename: str | None = None) -> None:
    """Save results to JSON file.
    
    Args:
        results: List of scan results
        filename: Output filename (auto-generated if None)
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_scan_results_{timestamp}.json"
    
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✓ Results saved to: {filename}")


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch scan multiple cryptocurrencies")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="API base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between scans in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of tokens to scan (default: all)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["defi", "infrastructure", "layer2", "meme", "staking", "gaming", "privacy", "all"],
        default=["all"],
        help="Token categories to scan (default: all)",
    )
    
    args = parser.parse_args()
    
    # Filter tokens by category if specified
    tokens_to_scan = CRYPTO_TOKENS
    if "all" not in args.categories:
        category_map = {
            "defi": ["UNI", "AAVE", "MKR", "COMP", "CRV"],
            "infrastructure": ["LINK", "GRT"],
            "layer2": ["MATIC", "ARB", "OP", "IMX"],
            "meme": ["PEPE", "SHIB"],
            "staking": ["LDO", "RPL"],
            "gaming": ["IMX", "SAND"],
            "privacy": ["TORN"],
        }
        
        selected_symbols = set()
        for category in args.categories:
            selected_symbols.update(category_map.get(category, []))
        
        tokens_to_scan = [t for t in CRYPTO_TOKENS if t["symbol"] in selected_symbols]
    
    # Apply limit if specified
    if args.limit:
        tokens_to_scan = tokens_to_scan[:args.limit]
    
    # Execute batch scan
    results = batch_scan(tokens_to_scan, api_url=args.api_url, delay_seconds=args.delay)
    
    # Print summary
    print_summary(results)
    
    # Save results if requested
    if args.save:
        save_results(results)


if __name__ == "__main__":
    main()
