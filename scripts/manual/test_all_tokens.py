"""
Test all configured tokens: LINK, UNI, AAVE, PEPE
"""
import os
from dotenv import load_dotenv
from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.narrative import NarrativeAnalyzer

load_dotenv()

def test_token(config: TokenConfig):
    print(f"\n{'='*70}")
    print(f"Testing {config.symbol} ({config.coingecko_id})")
    print(f"{'='*70}")
    
    try:
        # Initialize scanner with clients
        coin_client = CoinGeckoClient()
        defi_client = DefiLlamaClient()
        etherscan_client = EtherscanClient(api_key=os.getenv("ETHERSCAN_API_KEY"))
        narrative_analyzer = NarrativeAnalyzer()
        
        scanner = HiddenGemScanner(
            coin_client=coin_client,
            defi_client=defi_client,
            etherscan_client=etherscan_client,
            narrative_analyzer=narrative_analyzer,
            liquidity_threshold=10_000.0
        )
        
        # Run scan
        result, tree = scanner.scan_with_tree(config)
        
        print(f"✅ {config.symbol} - GemScore: {result.gem_score.score:.2f}, Final: {result.final_score:.2f}")
        
        # Check liquidity status
        liquidity_node = None
        for node in tree.iter_nodes():
            if node.key == "D4":
                liquidity_node = node
                break
        
        if liquidity_node:
            status = liquidity_node.outcome.status if liquidity_node.outcome else "unknown"
            print(f"   Liquidity Check: {status}")
        
        coin_client.close()
        defi_client.close()
        etherscan_client.close()
        
        return True
        
    except Exception as e:
        print(f"❌ {config.symbol} - FAILED: {e}")
        return False

if __name__ == "__main__":
    print("[OK] Testing all tokens with volume-based liquidity calculation")
    
    tokens = [
        TokenConfig(
            symbol="LINK",
            coingecko_id="chainlink",
            defillama_slug="chainlink",
            contract_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
            narratives=["Chainlink oracle network"],
            keywords=["chainlink", "LINK", "oracle"]
        ),
        TokenConfig(
            symbol="UNI",
            coingecko_id="uniswap",
            defillama_slug="uniswap",
            contract_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
            narratives=["Uniswap DEX protocol"],
            keywords=["uniswap", "UNI", "dex"]
        ),
        TokenConfig(
            symbol="AAVE",
            coingecko_id="aave",
            defillama_slug="aave",
            contract_address="0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
            narratives=["Aave lending protocol"],
            keywords=["aave", "AAVE", "lending"]
        ),
        TokenConfig(
            symbol="PEPE",
            coingecko_id="pepe",
            defillama_slug="pepe",
            contract_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
            narratives=["Pepe meme token"],
            keywords=["pepe", "PEPE", "meme"]
        ),
    ]
    
    results = {}
    for token in tokens:
        results[token.symbol] = test_token(token)
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    for symbol, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{symbol:6s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tokens scanning successfully")
