"""
Comprehensive feature test for VoidBloom Scanner
Tests all major features and reports their status
"""
import os
import sys
from pathlib import Path

# API keys must be set via environment variables before running this script
# Example: export GROQ_API_KEY="your-key-here"
# Example: export ETHERSCAN_API_KEY="your-key-here"
# Example: export COINGECKO_API_KEY="your-key-here"
if not os.environ.get('GROQ_API_KEY'):
    print("WARNING: GROQ_API_KEY not set. Some features may not work.")
if not os.environ.get('ETHERSCAN_API_KEY'):
    print("WARNING: ETHERSCAN_API_KEY not set. Some features may not work.")
if not os.environ.get('COINGECKO_API_KEY'):
    print("WARNING: COINGECKO_API_KEY not set. Some features may not work.")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.pipeline import HiddenGemScanner, TokenConfig, ScanContext
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient


def test_all_features():
    """Test all scanner features"""
    print("=" * 80)
    print("VoidBloom Scanner - Comprehensive Feature Test")
    print("=" * 80)
    
    # Initialize scanner
    print("\n[1/6] Initializing scanner...")
    try:
        scanner = HiddenGemScanner(
            coin_client=CoinGeckoClient(),
            defi_client=DefiLlamaClient(),
            etherscan_client=EtherscanClient(api_key=os.environ['ETHERSCAN_API_KEY']),
        )
        print("✅ Scanner initialized")
    except Exception as e:
        print(f"❌ Scanner initialization failed: {e}")
        return
    
    # Test tokens
    test_tokens = [
        TokenConfig(
            symbol="LINK",
            coingecko_id="chainlink",
            defillama_slug="chainlink",
            contract_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
            narratives=["Chainlink expands oracle services"],
        ),
        TokenConfig(
            symbol="UNI",
            coingecko_id="uniswap",
            defillama_slug="uniswap",
            contract_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
            narratives=["Uniswap launches V4 with new features"],
        ),
        TokenConfig(
            symbol="AAVE",
            coingecko_id="aave",
            defillama_slug="aave",
            contract_address="0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
            narratives=["AAVE governance proposes new lending markets"],
        ),
        TokenConfig(
            symbol="PEPE",
            coingecko_id="pepe",
            defillama_slug="pepe",
            contract_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
            narratives=["PEPE meme coin sees renewed community interest"],
        ),
    ]
    
    results = {}
    for idx, token_cfg in enumerate(test_tokens, 1):
        print(f"\n[{idx+1}/6] Testing {token_cfg.symbol} ({token_cfg.contract_address[:10]}...)...")
        
        try:
            # Create context and run scan
            context = ScanContext(config=token_cfg)
            tree = scanner._build_execution_tree(context)
            tree.run(context)
            
            if context.result:
                result = context.result
                results[token_cfg.symbol] = result
                
                # Check what features worked
                features = {
                    "Price Data": result.market_snapshot is not None and result.market_snapshot.price_usd > 0,
                    "Liquidity": result.market_snapshot is not None and result.market_snapshot.liquidity_usd > 0,
                    "GemScore": result.gem_score is not None and result.gem_score.score > 0,
                    "Final Score": result.final_score > 0,
                    "Confidence": result.gem_score is not None and result.gem_score.confidence > 0,
                    "AI Narrative": result.narrative is not None and len(result.narrative.themes) > 0,
                    "Safety Check": result.safety_report is not None,
                }
                
                print(f"✅ {token_cfg.symbol} scan completed")
                print(f"   GemScore: {result.gem_score.score:.2f}")
                print(f"   Final Score: {result.final_score:.2f}")
                print(f"   Price: ${result.market_snapshot.price_usd:.4f}")
                print(f"   Liquidity: ${result.market_snapshot.liquidity_usd:,.0f}")
                print(f"   Confidence: {result.gem_score.confidence:.0f}%")
                print(f"   Flagged: {result.flag}")
                
                # Feature status
                working_features = sum(1 for v in features.values() if v)
                print(f"   Features: {working_features}/{len(features)} working")
                for feature, status in features.items():
                    symbol = "✅" if status else "❌"
                    print(f"     {symbol} {feature}")
                    
            else:
                print(f"❌ {token_cfg.symbol} scan returned None result")
                # Print tree state to see where it failed
                if tree:
                    print("   Tree execution trace:")
                    def print_tree(node, depth=0):
                        status = node.outcome.status if node.outcome else "not-run"
                        print(f"   {'  ' * depth}[{node.key}] {node.title}: {status}")
                        if node.outcome and node.outcome.status == "failure":
                            print(f"   {'  ' * depth}  Error: {node.outcome.summary}")
                        for child in node.children:
                            print_tree(child, depth + 1)
                    print_tree(tree)
                
        except Exception as e:
            print(f"❌ {token_cfg.symbol} scan failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if results:
        print(f"\n✅ Successfully scanned {len(results)}/{len(test_tokens)} tokens")
        print("\nToken Rankings (by Final Score):")
        sorted_tokens = sorted(results.items(), key=lambda x: x[1].final_score, reverse=True)
        for rank, (symbol, result) in enumerate(sorted_tokens, 1):
            print(f"   {rank}. {symbol}: {result.final_score:.2f} (Gem: {result.gem_score.score:.2f}, Conf: {result.gem_score.confidence:.0f}%)")
        
        # Feature availability across all tokens
        print("\nFeature Availability:")
        feature_checks = [
            ("Price Data", lambda r: r.market_snapshot and r.market_snapshot.price_usd > 0),
            ("Liquidity Data", lambda r: r.market_snapshot and r.market_snapshot.liquidity_usd > 0),
            ("GemScore Calculation", lambda r: r.gem_score and r.gem_score.score > 0),
            ("Final Score", lambda r: r.final_score > 0),
            ("Confidence Score", lambda r: r.gem_score and r.gem_score.confidence > 0),
            ("AI Narrative", lambda r: r.narrative and len(r.narrative.themes) > 0),
            ("Safety Analysis", lambda r: r.safety_report is not None),
        ]
        
        for feature_name, check_fn in feature_checks:
            working_count = sum(1 for r in results.values() if check_fn(r))
            total_count = len(results)
            percentage = (working_count / total_count * 100) if total_count > 0 else 0
            status = "✅" if percentage == 100 else "⚠️" if percentage >= 50 else "❌"
            print(f"   {status} {feature_name}: {working_count}/{total_count} ({percentage:.0f}%)")
        
        print("\n🎉 Scanner is operational!")
        print(f"\nBackend API: http://127.0.0.1:8000/api/tokens")
        print(f"Frontend Dashboard: http://localhost:5173/")
        
    else:
        print("❌ No tokens scanned successfully")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_all_features()
