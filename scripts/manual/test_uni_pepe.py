"""
Debug script to test UNI and PEPE token scans
"""
import os
from dotenv import load_dotenv
from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
from src.core.narrative import NarrativeAnalyzer

# Load environment
load_dotenv()

def test_token(symbol, address, name, coingecko_id, defillama_slug):
    print(f"\n{'='*60}")
    print(f"Testing {symbol} ({name})")
    print(f"Address: {address}")
    print(f"{'='*60}\n")
    
    try:
        # Build token config
        config = TokenConfig(
            symbol=symbol,
            coingecko_id=coingecko_id,
            defillama_slug=defillama_slug,
            contract_address=address,
            narratives=[f"{name} token"],
            keywords=[name.lower(), symbol.lower()]
        )
        
        # Initialize scanner with clients (same as dashboard_api.py)
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
        
        # Run scan - for PEPE we'll need to manually build to see the tree
        print(f"Starting scan_with_tree for {symbol}...")
        tree = None
        result = None
        try:
            result, tree = scanner.scan_with_tree(config)
            print(f"scan_with_tree completed for {symbol}")
        except RuntimeError as scan_err:
            if "did not produce a result" in str(scan_err):
                # Manually build and run tree to see what failed
                print(f"[WARN] Scan did not produce result - building tree manually to inspect...")
                from src.core.pipeline import ScanContext
                context = ScanContext(config=config)
                tree = scanner._build_execution_tree(context)
                tree.run(context)
                result = context.result
                # Don't raise - continue to print tree
            else:
                print(f"[ERROR] scan_with_tree raised RuntimeError for {symbol}:")
                print(f"  {scan_err}")
                raise
        
        if result:
            print(f"[OK] Scan successful for {symbol}!")
            print(f"GemScore: {result.gem_score.score:.2f}")
            print(f"Final Score: {result.final_score:.2f}")
            print(f"Flagged: {result.flag}")
        else:
            print(f"[FAIL] Scan returned None for {symbol}")
            
        # Print tree state
        print(f"\nTree execution state for {symbol}:")
        _print_tree(tree, 0)
        
        return result is not None
        
    except RuntimeError as e:
        if "did not produce a result" in str(e):
            print(f"[FAIL] Scan did not produce a result for {symbol}")
            print(f"  This usually means a critical branch failed")
            # Still print the tree to see what failed
            try:
                if 'tree' in locals():
                    print(f"\nTree execution state for {symbol}:")
                    _print_tree(tree, 0)
                else:
                    print(f"  Tree was not created (early failure)")
            except Exception as tree_err:
                print(f"  Could not print tree: {tree_err}")
        else:
            print(f"[ERROR] RuntimeError during {symbol} scan:")
            print(f"  {e}")
        return False
        
    except Exception as e:
        print(f"[ERROR] Exception during {symbol} scan:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        # Try to print tree if it exists
        try:
            if 'tree' in locals():
                print(f"\nPartial tree execution state for {symbol}:")
                _print_tree(tree, 0)
        except:
            pass
        return False

def _print_tree(node, depth):
    """Print tree structure"""
    indent = "  " * depth
    status_str = f"{node.outcome.status if node.outcome else 'pending'}"
    error_str = f" - {node.outcome.error}" if node.outcome and hasattr(node.outcome, 'error') and node.outcome.error else ""
    print(f"{indent}[{node.key}] {node.title}: {status_str}{error_str}")
    for child in node.children:
        _print_tree(child, depth + 1)

if __name__ == "__main__":
    print("[OK] Groq LLM enabled for narrative analysis")
    
    # Test UNI
    uni_success = test_token(
        symbol="UNI",
        address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        name="Uniswap",
        coingecko_id="uniswap",
        defillama_slug="uniswap"
    )
    
    # Test PEPE
    pepe_success = test_token(
        symbol="PEPE",
        address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        name="Pepe",
        coingecko_id="pepe",
        defillama_slug="pepe"
    )
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"UNI:  {'[OK] PASS' if uni_success else '[FAIL] FAIL'}")
    print(f"PEPE: {'[OK] PASS' if pepe_success else '[FAIL] FAIL'}")
