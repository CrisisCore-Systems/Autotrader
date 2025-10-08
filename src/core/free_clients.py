"""FREE blockchain data clients (no API keys required)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from src.core.clients import BaseClient
from src.core.http_manager import CachePolicy
from src.core.rate_limit import RateLimit


class BlockscoutClient(BaseClient):
    """Client for Blockscout blockchain explorer (FREE Etherscan alternative).

    Blockscout provides contract verification and blockchain data with NO API KEY REQUIRED.
    This is a completely free alternative to Etherscan V1/V2 API.
    
    Benefits:
    - ✅ NO API KEY required
    - ✅ NO deprecation warnings
    - ✅ Same data as Etherscan
    - ✅ Multiple networks supported
    """

    def __init__(
        self,
        *,
        base_url: str = "https://eth.blockscout.com/api",
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        """Initialize Blockscout client.

        Args:
            base_url: Blockscout API base URL (default: Ethereum mainnet)
            timeout: Request timeout in seconds
            client: Optional httpx client instance

        Other networks:
            - Polygon: https://polygon.blockscout.com/api
            - BSC: https://bsc.blockscout.com/api
            - Arbitrum: https://arbitrum.blockscout.com/api
            - Optimism: https://optimism.blockscout.com/api
        """
        session = client or httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(
            session,
            rate_limits={"blockscout.com": RateLimit(10, 1.0)},  # Conservative limit
        )

    def fetch_contract_source(self, address: str) -> Dict[str, Any]:
        """Fetch contract source code and verification status.

        Args:
            address: Contract address

        Returns:
            Dict with IsVerified, ABI, SourceCode, and other metadata
            Compatible with Etherscan response format
        """
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        }

        response = self.requester.request(
            "GET",
            "",
            params=params,
            cache_policy=CachePolicy(ttl_seconds=3600.0),  # Contract code doesn't change
        )
        response.raise_for_status()
        payload = response.json()

        # Blockscout returns similar format to Etherscan
        if payload.get("status") != "1":
            error_msg = payload.get("message", "unknown error")
            raise RuntimeError(f"Blockscout error: {error_msg}")

        results = payload.get("result", [])
        if results and len(results) > 0:
            # Normalize response to match Etherscan format
            result = results[0]
            # Add HolderCount if not present (not all Blockscout instances provide this)
            if "HolderCount" not in result:
                result["HolderCount"] = "0"
            return result

        return {}


class EthereumRPCClient(BaseClient):
    """Client for free Ethereum RPC nodes (NO API KEY REQUIRED).

    Provides on-chain data including token balances, holder counts, and supply
    without relying on Etherscan or DeFiLlama.
    
    Benefits:
    - ✅ NO API KEY required
    - ✅ Direct blockchain access
    - ✅ Real-time data
    - ✅ Multiple free providers available
    """

    def __init__(
        self,
        *,
        base_url: str = "https://eth.llamarpc.com",
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        """Initialize Ethereum RPC client.

        Args:
            base_url: RPC endpoint URL
            timeout: Request timeout in seconds
            client: Optional httpx client instance

        Free RPC providers:
            - https://eth.llamarpc.com (LlamaNodes) ← Default, most reliable
            - https://rpc.ankr.com/eth (Ankr)
            - https://ethereum.publicnode.com (PublicNode)
            - https://eth.drpc.org (dRPC)
        """
        session = client or httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(
            session,
            rate_limits={"llamarpc.com": RateLimit(30, 1.0)},  # Conservative public node limit
        )

    def get_token_supply(self, token_address: str) -> Dict[str, Any]:
        """Get total supply of an ERC20 token.

        Args:
            token_address: Token contract address

        Returns:
            Dict with total_supply value
        """
        # ERC20 totalSupply() function signature
        data = "0x18160ddd"  # totalSupply() method ID

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {"to": token_address, "data": data},
                "latest",
            ],
            "id": 1,
        }

        response = self.requester.request(
            "POST",
            "",
            json=payload,
            cache_policy=CachePolicy(ttl_seconds=60.0),
        )
        result = response.json()

        if "result" in result:
            # Convert hex to decimal
            total_supply = int(result["result"], 16) if result["result"] != "0x" else 0
            return {"total_supply": total_supply}

        return {"total_supply": 0}

    def get_token_balance(self, token_address: str, holder_address: str) -> Dict[str, Any]:
        """Get token balance for a specific address.

        Args:
            token_address: Token contract address
            holder_address: Address to check balance for

        Returns:
            Dict with balance value
        """
        # ERC20 balanceOf(address) function signature
        # Method ID: 0x70a08231
        # Parameter: address (padded to 32 bytes)
        holder_padded = holder_address[2:].zfill(64) if holder_address.startswith("0x") else holder_address.zfill(64)
        data = f"0x70a08231{holder_padded}"

        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {"to": token_address, "data": data},
                "latest",
            ],
            "id": 1,
        }

        response = self.requester.request(
            "POST",
            "",
            json=payload,
            cache_policy=CachePolicy(ttl_seconds=10.0),
        )
        result = response.json()

        if "result" in result:
            balance = int(result["result"], 16) if result["result"] != "0x" else 0
            return {"balance": balance}

        return {"balance": 0}

    def get_block_number(self) -> int:
        """Get current block number.

        Returns:
            Current Ethereum block number
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1,
        }

        response = self.requester.request(
            "POST",
            "",
            json=payload,
            cache_policy=CachePolicy(ttl_seconds=5.0),  # Block number changes frequently
        )
        result = response.json()

        if "result" in result:
            return int(result["result"], 16)

        return 0
