"""Service for on-chain wallet monitoring and large transfer analysis."""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

from src.core.onchain_client import OnChainClient
from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class LargeTransfer:
    """Large transfer to CEX wallet."""
    network: str
    token_address: str
    from_address: str
    to_address: str
    cex_exchange: Optional[str]
    value: float
    usd_value: float
    transaction_hash: str
    timestamp: datetime
    block_number: int


@dataclass
class OnChainAlert:
    """Alert for significant on-chain activity."""
    token_address: str
    alert_type: str  # "large_cex_inflow", "whale_movement", etc.
    severity: str    # "low", "medium", "high", "critical"
    description: str
    transfers: List[LargeTransfer]
    total_value_usd: float
    timestamp: datetime


class OnChainMonitor:
    """Monitor for on-chain wallet activity and large transfers."""

    def __init__(
        self,
        client: Optional[OnChainClient] = None,
        etherscan_api_key: Optional[str] = None,
        bscscan_api_key: Optional[str] = None
    ):
        self.client = client or OnChainClient(
            etherscan_api_key=etherscan_api_key,
            bscscan_api_key=bscscan_api_key
        )
        self._alert_cache: Dict[str, List[OnChainAlert]] = {}
        self._last_check: Dict[str, datetime] = {}

    async def scan_for_large_cex_transfers(
        self,
        token_addresses: List[str],
        min_value_usd: float = 100000,
        hours_back: int = 24,
        networks: Optional[List[str]] = None
    ) -> List[OnChainAlert]:
        """Scan for large transfers to CEX wallets across multiple tokens."""
        if networks is None:
            networks = ["ethereum", "bsc"]

        alerts = []

        for token_address in token_addresses:
            try:
                token_alerts = await self._scan_token_for_cex_transfers(
                    token_address, min_value_usd, hours_back, networks
                )
                alerts.extend(token_alerts)

                # Add small delay to avoid rate limits
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error scanning token {token_address}: {e}")
                continue

        return alerts

    async def _scan_token_for_cex_transfers(
        self,
        token_address: str,
        min_value_usd: float,
        hours_back: int,
        networks: List[str]
    ) -> List[OnChainAlert]:
        """Scan a specific token for large CEX transfers."""
        all_transfers = []

        # Collect transfers from all networks
        for network in networks:
            try:
                transfers = await self.client.get_large_transfers_to_cex(
                    token_address, min_value_usd, hours_back, network
                )

                # Convert to LargeTransfer objects
                for transfer_data in transfers:
                    transfer = LargeTransfer(**transfer_data)
                    all_transfers.append(transfer)

            except Exception as e:
                logger.warning(f"Error scanning {network} for {token_address}: {e}")
                continue

        if not all_transfers:
            return []

        # Group transfers by time window (e.g., hourly)
        time_windows = self._group_transfers_by_time(all_transfers, hours=1)

        alerts = []
        for window_start, window_transfers in time_windows.items():
            if not window_transfers:
                continue

            total_value = sum(t.usd_value for t in window_transfers)

            # Determine alert severity
            severity = self._calculate_alert_severity(total_value, len(window_transfers))

            if severity != "none":
                alert = OnChainAlert(
                    token_address=token_address,
                    alert_type="large_cex_inflow",
                    severity=severity,
                    description=self._generate_alert_description(
                        window_transfers, total_value, window_start
                    ),
                    transfers=window_transfers,
                    total_value_usd=total_value,
                    timestamp=datetime.now()
                )
                alerts.append(alert)

        return alerts

    def _group_transfers_by_time(
        self,
        transfers: List[LargeTransfer],
        hours: int = 1
    ) -> Dict[datetime, List[LargeTransfer]]:
        """Group transfers by time windows."""
        windows = {}

        for transfer in transfers:
            # Round down to nearest hour
            window_start = transfer.timestamp.replace(minute=0, second=0, microsecond=0)

            if window_start not in windows:
                windows[window_start] = []
            windows[window_start].append(transfer)

        return windows

    def _calculate_alert_severity(self, total_value: float, transfer_count: int) -> str:
        """Calculate alert severity based on value and frequency."""
        # Severity thresholds
        if total_value >= 5000000:  # $5M+
            return "critical"
        elif total_value >= 1000000:  # $1M+
            return "high"
        elif total_value >= 250000 or transfer_count >= 5:  # $250k+ or 5+ transfers
            return "medium"
        elif total_value >= 100000:  # $100k+
            return "low"
        else:
            return "none"

    def _generate_alert_description(
        self,
        transfers: List[LargeTransfer],
        total_value: float,
        window_start: datetime
    ) -> str:
        """Generate human-readable alert description."""
        exchanges = set(t.cex_exchange for t in transfers if t.cex_exchange)
        exchange_str = ", ".join(exchanges) if exchanges else "unknown exchange"

        return (
            f"Large inflows detected to {exchange_str} wallets: "
            f"${total_value:,.0f} across {len(transfers)} transfers "
            f"starting at {window_start.strftime('%Y-%m-%d %H:%M UTC')}"
        )

    async def get_whale_movements(
        self,
        token_address: str,
        min_transfer_value: float = 1000000,  # $1M minimum
        hours_back: int = 24,
        network: str = "ethereum"
    ) -> List[Dict[str, Any]]:
        """Detect large whale movements (not necessarily to CEX)."""
        # This would require monitoring all large transfers, not just to CEX
        # For now, return a subset of CEX transfers as proxy
        try:
            transfers = await self.client.get_large_transfers_to_cex(
                token_address, min_transfer_value, hours_back, network
            )

            whale_movements = []
            for transfer in transfers:
                whale_movements.append({
                    "token_address": token_address,
                    "from_address": transfer["from_address"],
                    "to_address": transfer["to_address"],
                    "value": transfer["value"],
                    "usd_value": transfer["usd_value"],
                    "transaction_hash": transfer["transaction_hash"],
                    "timestamp": transfer["timestamp"],
                    "is_cex_destination": transfer["cex_exchange"] is not None,
                    "cex_exchange": transfer["cex_exchange"]
                })

            return whale_movements

        except Exception as e:
            logger.error(f"Error detecting whale movements for {token_address}: {e}")
            return []

    def add_cex_wallet(self, exchange: str, network: str, address: str) -> None:
        """Add a new CEX wallet to monitor."""
        self.client.add_cex_wallet(exchange, network, address)

    def get_monitored_wallets(self, network: str = "ethereum") -> Dict[str, List[str]]:
        """Get all monitored CEX wallets for a network."""
        return self.client.get_monitored_cex_wallets(network)

    async def get_recent_alerts(
        self,
        token_address: Optional[str] = None,
        hours_back: int = 24
    ) -> List[OnChainAlert]:
        """Get recent alerts, optionally filtered by token."""
        all_alerts = []

        # Get alerts from cache
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        for token_alerts in self._alert_cache.values():
            for alert in token_alerts:
                if alert.timestamp >= cutoff_time:
                    if token_address is None or alert.token_address == token_address:
                        all_alerts.append(alert)

        # Sort by timestamp (most recent first)
        all_alerts.sort(key=lambda x: x.timestamp, reverse=True)

        return all_alerts