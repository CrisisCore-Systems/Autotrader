"""
Test liquidity values for tokens
"""
import os
from dotenv import load_dotenv
from src.core.clients import CoinGeckoClient, DefiLlamaClient

load_dotenv()

def test_liquidity(symbol, coingecko_id, defillama_slug):
    print(f"\n{'='*60}")
    print(f"Testing {symbol}")
    print(f"CoinGecko ID: {coingecko_id}")
    print(f"DefiLlama Slug: {defillama_slug}")
    print(f"{'='*60}\n")
    
    coin_client = CoinGeckoClient()
    defi_client = DefiLlamaClient()
    
    # Test CoinGecko market chart
    try:
        chart = coin_client.fetch_market_chart(coingecko_id, vs_currency="usd", days=14)
        if chart and "prices" in chart:
            print(f"[OK] CoinGecko market chart: {len(chart['prices'])} price points")
            if chart['prices']:
                latest_price = chart['prices'][-1][1]
                print(f"     Latest price: ${latest_price:.6f}")
        else:
            print(f"[FAIL] CoinGecko returned no data")
    except Exception as e:
        print(f"[ERROR] CoinGecko: {e}")
    
    # Test DefiLlama protocol metrics
    try:
        metrics = defi_client.fetch_protocol(defillama_slug)
        if metrics:
            tvl = metrics.get("tvl")
            print(f"[OK] DefiLlama metrics found")
            if isinstance(tvl, (int, float)):
                print(f"     TVL: ${tvl:,.2f}")
            elif isinstance(tvl, list) and tvl:
                # TVL might be a list, take the last value
                latest_tvl = tvl[-1] if isinstance(tvl[-1], (int, float)) else tvl[-1].get('totalLiquidityUSD', 0)
                print(f"     TVL (latest): ${latest_tvl:,.2f}")
            else:
                print(f"     TVL: {tvl} (type: {type(tvl)})")
        else:
            print(f"[FAIL] DefiLlama returned no data")
    except Exception as e:
        print(f"[ERROR] DefiLlama: {e}")
    
    coin_client.close()
    defi_client.close()

if __name__ == "__main__":
    test_liquidity("LINK", "chainlink", "chainlink")
    test_liquidity("UNI", "uniswap", "uniswap")
    test_liquidity("AAVE", "aave", "aave")
    test_liquidity("PEPE", "pepe", "pepe")
