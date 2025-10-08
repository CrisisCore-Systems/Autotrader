"""Quick test script to debug token scanning"""
import os

# API keys must be set via environment variables before running
# Example: export GROQ_API_KEY="your-key-here"
if not os.environ.get('GROQ_API_KEY'):
    print("ERROR: GROQ_API_KEY not set")
    exit(1)
if not os.environ.get('ETHERSCAN_API_KEY'):
    print("ERROR: ETHERSCAN_API_KEY not set")
    exit(1)
if not os.environ.get('COINGECKO_API_KEY'):
    print("ERROR: COINGECKO_API_KEY not set")
    exit(1)

from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient

# Create scanner with real API clients
scanner = HiddenGemScanner(
    coin_client=CoinGeckoClient(),
    defi_client=DefiLlamaClient(),
    etherscan_client=EtherscanClient(api_key=os.environ['ETHERSCAN_API_KEY']),
)

# Test with Chainlink (proper ERC-20 token)
link_config = TokenConfig(
    symbol="LINK",
    coingecko_id="chainlink",
    defillama_slug="chainlink",
    contract_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
    narratives=["Chainlink expands oracle services"],
    unlocks=[],
)

print("Starting scan for LINK...")
context = None
tree = None
try:
    # Build context and tree manually to see what fails
    from src.core.pipeline import ScanContext
    context = ScanContext(config=link_config)
    tree = scanner._build_execution_tree(context)
    tree.run(context)
    
    if context.result is None:
        print("\n[FAIL] Scan failed: context.result is None after tree execution")
    else:
        print(f"\n[OK] Scan successful!")
        print(f"GemScore: {context.result.gem_score.score:.2f}")
        print(f"Final Score: {context.result.final_score:.2f}")
        print(f"Flagged: {context.result.flag}")
except Exception as e:
    print(f"\n[FAIL] Scan failed with exception: {e}")
    import traceback
    traceback.print_exc()

# Print tree state to see where it failed
print("\n\nTree execution state:")
if tree is not None:
    def print_tree(node, depth=0):
        status = node.outcome.status if node.outcome else "not-run"
        print(f"{'  ' * depth}[{node.key}] {node.title}: {status}")
        if node.outcome and node.outcome.status == "failure":
            print(f"{'  ' * depth}  Error: {node.outcome.summary}")
        for child in node.children:
            print_tree(child, depth + 1)
    print_tree(tree)
else:
    print("Tree was not created")
