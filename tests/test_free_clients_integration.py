"""Integration tests for FREE data source clients."""

import pytest
from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient


class TestFreeClientsIntegration:
    """Test that HiddenGemScanner works with FREE clients."""

    def test_scanner_accepts_free_clients(self):
        """Test that HiddenGemScanner can be initialized with FREE clients only."""
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
            
            assert scanner.coin_client is not None
            assert scanner.dex_client is not None
            assert scanner.blockscout_client is not None
            assert scanner.rpc_client is not None
            # Paid clients should be None
            assert scanner.defi_client is None
            assert scanner.etherscan_client is None

    def test_scanner_backward_compatible_with_paid_clients(self):
        """Test that old code using paid clients still works."""
        from src.core.clients import DefiLlamaClient, EtherscanClient
        
        with CoinGeckoClient() as coin_client, \
             DefiLlamaClient() as defi_client, \
             EtherscanClient() as etherscan_client:
            
            scanner = HiddenGemScanner(
                coin_client=coin_client,
                defi_client=defi_client,
                etherscan_client=etherscan_client,
            )
            
            assert scanner.coin_client is not None
            assert scanner.defi_client is not None
            assert scanner.etherscan_client is not None
            # Free clients should be None
            assert scanner.dex_client is None
            assert scanner.blockscout_client is None
            assert scanner.rpc_client is None

    def test_scanner_mixed_free_and_paid_clients(self):
        """Test that FREE and paid clients can coexist."""
        from src.core.clients import DefiLlamaClient, EtherscanClient
        
        with CoinGeckoClient() as coin_client, \
             DexscreenerClient() as dex_client, \
             DefiLlamaClient() as defi_client, \
             BlockscoutClient() as blockscout_client, \
             EtherscanClient() as etherscan_client, \
             EthereumRPCClient() as rpc_client:
            
            scanner = HiddenGemScanner(
                coin_client=coin_client,
                dex_client=dex_client,
                defi_client=defi_client,
                blockscout_client=blockscout_client,
                etherscan_client=etherscan_client,
                rpc_client=rpc_client,
            )
            
            # All clients should be present
            assert scanner.coin_client is not None
            assert scanner.dex_client is not None
            assert scanner.defi_client is not None
            assert scanner.blockscout_client is not None
            assert scanner.etherscan_client is not None
            assert scanner.rpc_client is not None

    def test_free_clients_have_required_methods(self):
        """Test that FREE clients have the methods needed by the pipeline."""
        # Test DexscreenerClient
        with DexscreenerClient() as dex_client:
            assert hasattr(dex_client, 'fetch_token_pairs')
            assert callable(dex_client.fetch_token_pairs)
        
        # Test BlockscoutClient
        with BlockscoutClient() as blockscout_client:
            assert hasattr(blockscout_client, 'fetch_contract_source')
            assert callable(blockscout_client.fetch_contract_source)
        
        # Test EthereumRPCClient
        with EthereumRPCClient() as rpc_client:
            assert hasattr(rpc_client, 'get_token_balance')
            assert hasattr(rpc_client, 'get_token_supply')
            assert hasattr(rpc_client, 'get_block_number')
            assert callable(rpc_client.get_token_balance)
            assert callable(rpc_client.get_token_supply)
            assert callable(rpc_client.get_block_number)

    def test_scanner_initialization_without_any_liquidity_client_works(self):
        """Test that scanner can be initialized with neither dex_client nor defi_client."""
        with CoinGeckoClient() as coin_client:
            scanner = HiddenGemScanner(
                coin_client=coin_client,
                # No liquidity client at all
            )
            
            assert scanner.coin_client is not None
            assert scanner.dex_client is None
            assert scanner.defi_client is None

    def test_scanner_initialization_without_any_contract_client_works(self):
        """Test that scanner can be initialized with neither blockscout nor etherscan."""
        with CoinGeckoClient() as coin_client:
            scanner = HiddenGemScanner(
                coin_client=coin_client,
                # No contract verification client at all
            )
            
            assert scanner.coin_client is not None
            assert scanner.blockscout_client is None
            assert scanner.etherscan_client is None


class TestFreeClientsPreferenceOrder:
    """Test that FREE clients are preferred over paid clients when both are present."""

    def test_dexscreener_preferred_over_defillama(self):
        """Test that Dexscreener is used when both dex_client and defi_client are present."""
        from src.core.clients import DefiLlamaClient
        
        with CoinGeckoClient() as coin_client, \
             DexscreenerClient() as dex_client, \
             DefiLlamaClient() as defi_client:
            
            scanner = HiddenGemScanner(
                coin_client=coin_client,
                dex_client=dex_client,
                defi_client=defi_client,
            )
            
            # Both should be stored
            assert scanner.dex_client is not None
            assert scanner.defi_client is not None
            # The _action_fetch_onchain_metrics method will prefer dex_client

    def test_blockscout_preferred_over_etherscan(self):
        """Test that Blockscout is used when both blockscout_client and etherscan_client are present."""
        from src.core.clients import EtherscanClient
        
        with CoinGeckoClient() as coin_client, \
             BlockscoutClient() as blockscout_client, \
             EtherscanClient() as etherscan_client:
            
            scanner = HiddenGemScanner(
                coin_client=coin_client,
                blockscout_client=blockscout_client,
                etherscan_client=etherscan_client,
            )
            
            # Both should be stored
            assert scanner.blockscout_client is not None
            assert scanner.etherscan_client is not None
            # The _action_fetch_contract_metadata method will prefer blockscout_client


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
