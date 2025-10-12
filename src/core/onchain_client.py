"""Client for on-chain wallet monitoring and large transfer detection."""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import asyncio
import httpx

from src.core.clients import BaseClient
from src.core.rate_limit import RateLimit
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class OnChainClient(BaseClient):
    """Client for on-chain wallet monitoring and transaction analysis."""

    # Rate limits for blockchain APIs
    BLOCKCHAIN_RATE_LIMITS = {
        "api.etherscan.io": RateLimit(5, 1.0),      # 5 requests per second
        "api.bscscan.com": RateLimit(5, 1.0),       # BSC Scan
        "api.polygonscan.com": RateLimit(5, 1.0),   # Polygon Scan
        "api.snowtrace.io": RateLimit(5, 1.0),      # Avalanche
        "api.ftmscan.com": RateLimit(5, 1.0),       # Fantom
        "api.arbiscan.io": RateLimit(5, 1.0),       # Arbitrum
        "api.optimistic.etherscan.io": RateLimit(5, 1.0),  # Optimism
    }

    # Known CEX wallet addresses (sample - would need comprehensive list)
    CEX_WALLETS = {
        "binance": {
            "ethereum": [
                "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",  # Hot wallet
                "0xd551234ae421e3bcba99a0da6d736074f22192ff",  # Deposit wallet
                "0x8894e0a0c962cb723c1976a4421c95949be2d4e3",  # Cold wallet
            ],
            "bsc": [
                "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",
            ]
        },
        "coinbase": {
            "ethereum": [
                "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",  # Prime Brokerage
                "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740",  # Custody
            ]
        },
        "kraken": {
            "ethereum": [
                "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",  # Deposit
                "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13",  # Withdrawal
            ]
        },
        "bybit": {
            "ethereum": [
                "0xf89d7b9c894bf2a0c8c5b5c8a6b8f2a0c8c5b5c8",  # Main wallet
            ]
        },
        "okx": {
            "ethereum": [
                "0x6cC5F688a315f3dC28A77817163b4a662a81E55C",  # Main wallet
            ]
        }
    }

    def __init__(
        self,
        *,
        etherscan_api_key: Optional[str] = None,
        bscscan_api_key: Optional[str] = None,
        timeout: float = 15.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        session = client or httpx.Client(timeout=timeout)
        super().__init__(session, rate_limits=self.BLOCKCHAIN_RATE_LIMITS)
        self.etherscan_api_key = etherscan_api_key
        self.bscscan_api_key = bscscan_api_key

    async def get_large_transfers_to_cex(
        self,
        token_address: str,
        min_value_usd: float = 100000,  # $100k minimum
        hours_back: int = 24,
        network: str = "ethereum"
    ) -> List[Dict[str, Any]]:
        """Get large transfers to CEX wallets for a token."""
        try:
            if network.lower() == "ethereum":
                return await self._get_ethereum_transfers_to_cex(token_address, min_value_usd, hours_back)
            elif network.lower() == "bsc":
                return await self._get_bsc_transfers_to_cex(token_address, min_value_usd, hours_back)
            else:
                logger.warning(f"Unsupported network: {network}")
                return []
        except Exception as e:
            logger.error(f"Error getting large transfers for {token_address}: {e}")
            return []

    async def _get_ethereum_transfers_to_cex(
        self,
        token_address: str,
        min_value_usd: float,
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Get ERC20 transfers to CEX wallets on Ethereum."""
        if not self.etherscan_api_key:
            logger.warning("Etherscan API key not provided")
            return []

        # Get all CEX wallet addresses for Ethereum
        cex_addresses = set()
        for exchange_wallets in self.CEX_WALLETS.values():
            cex_addresses.update(exchange_wallets.get("ethereum", []))

        large_transfers = []

        # Get token transfers for each CEX wallet
        for cex_address in cex_addresses:
            try:
                transfers = await self._get_erc20_transfers(
                    token_address, cex_address, hours_back
                )

                for transfer in transfers:
                    # Estimate USD value (simplified - would need price data)
                    usd_value = self._estimate_transfer_value_usd(transfer)

                    if usd_value >= min_value_usd:
                        large_transfers.append({
                            "network": "ethereum",
                            "token_address": token_address,
                            "from_address": transfer["from"],
                            "to_address": transfer["to"],
                            "cex_exchange": self._identify_cex_exchange(transfer["to"]),
                            "value": float(transfer["value"]),
                            "usd_value": usd_value,
                            "transaction_hash": transfer["hash"],
                            "timestamp": datetime.fromtimestamp(int(transfer["timeStamp"])),
                            "block_number": int(transfer["blockNumber"])
                        })

            except Exception as e:
                logger.warning(f"Error getting transfers for CEX wallet {cex_address}: {e}")
                continue

        return large_transfers

    async def _get_bsc_transfers_to_cex(
        self,
        token_address: str,
        min_value_usd: float,
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Get BEP20 transfers to CEX wallets on BSC."""
        if not self.bscscan_api_key:
            logger.warning("BSCScan API key not provided")
            return []

        # Similar implementation for BSC
        cex_addresses = set()
        for exchange_wallets in self.CEX_WALLETS.values():
            cex_addresses.update(exchange_wallets.get("bsc", []))

        large_transfers = []

        for cex_address in cex_addresses:
            try:
                transfers = await self._get_bep20_transfers(
                    token_address, cex_address, hours_back
                )

                for transfer in transfers:
                    usd_value = self._estimate_transfer_value_usd(transfer)

                    if usd_value >= min_value_usd:
                        large_transfers.append({
                            "network": "bsc",
                            "token_address": token_address,
                            "from_address": transfer["from"],
                            "to_address": transfer["to"],
                            "cex_exchange": self._identify_cex_exchange(transfer["to"]),
                            "value": float(transfer["value"]),
                            "usd_value": usd_value,
                            "transaction_hash": transfer["hash"],
                            "timestamp": datetime.fromtimestamp(int(transfer["timeStamp"])),
                            "block_number": int(transfer["blockNumber"])
                        })

            except Exception as e:
                logger.warning(f"Error getting BSC transfers for CEX wallet {cex_address}: {e}")
                continue

        return large_transfers

    async def _get_erc20_transfers(
        self,
        token_address: str,
        wallet_address: str,
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Get ERC20 token transfers to a specific wallet."""
        start_block = await self._get_block_number_hours_ago(hours_back)

        response = await self.requester.arequest(
            "GET",
            "https://api.etherscan.io/api",
            params={
                "module": "account",
                "action": "tokentx",
                "contractaddress": token_address,
                "address": wallet_address,
                "startblock": start_block,
                "endblock": 99999999,
                "sort": "desc",
                "apikey": self.etherscan_api_key
            }
        )

        data = response.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []

    async def _get_bep20_transfers(
        self,
        token_address: str,
        wallet_address: str,
        hours_back: int
    ) -> List[Dict[str, Any]]:
        """Get BEP20 token transfers to a specific wallet."""
        start_block = await self._get_bsc_block_number_hours_ago(hours_back)

        response = await self.requester.arequest(
            "GET",
            "https://api.bscscan.com/api",
            params={
                "module": "account",
                "action": "tokentx",
                "contractaddress": token_address,
                "address": wallet_address,
                "startblock": start_block,
                "endblock": 99999999,
                "sort": "desc",
                "apikey": self.bscscan_api_key
            }
        )

        data = response.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []

    async def _get_block_number_hours_ago(self, hours: int) -> int:
        """Get Ethereum block number from X hours ago."""
        response = await self.requester.arequest(
            "GET",
            "https://api.etherscan.io/api",
            params={
                "module": "block",
                "action": "getblocknobytime",
                "timestamp": int((datetime.now() - timedelta(hours=hours)).timestamp()),
                "closest": "before",
                "apikey": self.etherscan_api_key
            }
        )

        data = response.json()
        return int(data.get("result", 0))

    async def _get_bsc_block_number_hours_ago(self, hours: int) -> int:
        """Get BSC block number from X hours ago."""
        response = await self.requester.arequest(
            "GET",
            "https://api.bscscan.com/api",
            params={
                "module": "block",
                "action": "getblocknobytime",
                "timestamp": int((datetime.now() - timedelta(hours=hours)).timestamp()),
                "closest": "before",
                "apikey": self.bscscan_api_key
            }
        )

        data = response.json()
        return int(data.get("result", 0))

    def _estimate_transfer_value_usd(self, transfer: Dict[str, Any]) -> float:
        """Estimate USD value of a token transfer (simplified)."""
        # This is a placeholder - in production you'd need current token price
        # For now, just return the raw token amount as a proxy
        try:
            # Convert from wei/base units to token units
            decimals = int(transfer.get("tokenDecimal", "18"))
            value = float(transfer["value"]) / (10 ** decimals)
            # Placeholder: assume $1 per token for demo
            return value * 1.0
        except (KeyError, ValueError):
            return 0.0

    def _identify_cex_exchange(self, address: str) -> Optional[str]:
        """Identify which CEX an address belongs to."""
        for exchange, networks in self.CEX_WALLETS.items():
            for network, addresses in networks.items():
                if address.lower() in [addr.lower() for addr in addresses]:
                    return exchange
        return None

    def add_cex_wallet(self, exchange: str, network: str, address: str) -> None:
        """Add a new CEX wallet address to monitor."""
        if exchange not in self.CEX_WALLETS:
            self.CEX_WALLETS[exchange] = {}
        if network not in self.CEX_WALLETS[exchange]:
            self.CEX_WALLETS[exchange][network] = []
        if address not in self.CEX_WALLETS[exchange][network]:
            self.CEX_WALLETS[exchange][network].append(address)

    def get_monitored_cex_wallets(self, network: str = "ethereum") -> Dict[str, List[str]]:
        """Get all monitored CEX wallets for a network."""
        wallets = {}
        for exchange, networks in self.CEX_WALLETS.items():
            if network in networks:
                wallets[exchange] = networks[network].copy()
        return wallets