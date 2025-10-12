"""Simple scanner CLI using FREE clients only."""
import argparse
import yaml
from pathlib import Path
from datetime import datetime, timezone
from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient


def main():
    parser = argparse.ArgumentParser(description="Run token scanner with FREE clients")
    parser.add_argument("config", help="Path to config YAML file")
    parser.add_argument("--output-dir", default="./scan_results", help="Output directory")
    args = parser.parse_args()
    
    # Load config
    with open(args.config, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize FREE clients
    with CoinGeckoClient() as coin_client, \
         DexscreenerClient() as dex_client, \
         BlockscoutClient() as blockscout_client, \
         EthereumRPCClient() as rpc_client:
        
        scanner = HiddenGemScanner(
            coin_client=coin_client,
            dex_client=dex_client,
            blockscout_client=blockscout_client,
            rpc_client=rpc_client,
            liquidity_threshold=config.get("scanner", {}).get("liquidity_threshold", 50000),
        )
        
        # Scan each token
        for token in config.get("tokens", []):
            token_config = TokenConfig(
                symbol=token["symbol"],
                coingecko_id=token["coingecko_id"],
                defillama_slug=token.get("defillama_slug", ""),  # Optional with FREE clients
                contract_address=token["contract_address"],
                narratives=token.get("narratives", []),
                glyph=token.get("glyph", "⧗⟡"),
                unlocks=[],  # Simplified for this example
                news_feeds=[],
                keywords=token.get("keywords", [token["symbol"]]),
            )
            
            print(f"\n{'='*60}")
            print(f"Scanning {token_config.symbol} ({token_config.coingecko_id})")
            print(f"{'='*60}\n")
            
            try:
                result = scanner.scan(token_config)
                
                # Print summary
                print(f"✅ SUCCESS!")
                print(f"   GemScore: {result.gem_score.score:.2f} (confidence: {result.gem_score.confidence:.0%})")
                print(f"   Narrative: {result.narrative}")
                if result.flag:
                    print(f"   ⚠️  FLAG: {result.flag}")
                
                # Save markdown artifact
                if result.artifact_markdown:
                    timestamp = datetime.now(timezone.utc)
                    filename = f"{token_config.symbol.lower()}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}.md"
                    output_path = output_dir / filename
                    output_path.write_text(result.artifact_markdown, encoding="utf-8")
                    print(f"   📄 Saved to: {output_path}")
                    
            except Exception as e:
                print(f"❌ FAILED: {e}")
                import traceback
                traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"All scans complete! Check {output_dir} for artifacts.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
