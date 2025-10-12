"""Test script to debug token scanning"""
import os
import sys
import traceback

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# API keys must be set via environment variables
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

try:
    from src.core.pipeline import HiddenGemScanner, TokenConfig, ScanContext
    from src.core.clients import CoinGeckoClient, DefiLlamaClient, EtherscanClient
    
    print("✓ Imports successful")
    
    # Initialize scanner
    scanner = HiddenGemScanner(
        coin_client=CoinGeckoClient(),
        defi_client=DefiLlamaClient(),
        etherscan_client=EtherscanClient(api_key=os.environ['ETHERSCAN_API_KEY']),
    )
    print("✓ Scanner initialized")
    
    # Try scanning PEPE
    token_cfg = TokenConfig(
        symbol="PEPE",
        coingecko_id="pepe",
        defillama_slug="pepe",
        contract_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        narratives=["PEPE market activity"],
    )
    print("✓ Token config created")
    
    context = ScanContext(config=token_cfg)
    print("✓ Scan context created")
    
    tree = scanner._build_execution_tree(context)
    print("✓ Execution tree built")
    
    tree.run(context)
    print("✓ Tree execution completed")
    
    if context.result:
        print(f"✓ Result available: {context.result}")
        if context.result.market_snapshot:
            print(f"  - Price: {context.result.market_snapshot.price}")
            print(f"  - Liquidity: {context.result.market_snapshot.liquidity_usd}")
        else:
            print("  ✗ No market snapshot")
    else:
        print("✗ No result in context")
        
except Exception as e:
    print(f"✗ Error: {e}")
    print(traceback.format_exc())
    sys.exit(1)
