"""Debug scanner to see what's failing."""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient

logging.basicConfig(level=logging.DEBUG)

async def main():
    config = TokenConfig(
        symbol="PEPE",
        coingecko_id="pepe",
        defillama_slug="pepe",  # This will be ignored with FREE clients
        contract_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        glyph="🐸",
        narratives=["meme", "community"],
    )
    
    with CoinGeckoClient() as coin_client, \
         DexscreenerClient() as dex_client, \
         BlockscoutClient() as blockscout_client, \
         EthereumRPCClient() as rpc_client:
        
        scanner = HiddenGemScanner(
            coin_client=coin_client,
            dex_client=dex_client,
            blockscout_client=blockscout_client,
            rpc_client=rpc_client,
        )
        
        print("Starting scan...")
        try:
            result = scanner.scan(config)
            print(f"SUCCESS! GemScore: {result.gem_score.score:.2f}")
            print(f"Narrative: {result.narrative}")
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
