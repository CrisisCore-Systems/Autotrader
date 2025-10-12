"""Feature gating system for controlling costs and compute usage."""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import threading
from contextlib import contextmanager

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class FeatureTier(Enum):
    """Feature access tiers."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class FeatureStatus(Enum):
    """Feature enablement status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    THROTTLED = "throttled"
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass
class FeatureQuota:
    """Quota limits for a feature."""
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    cost_per_request: float = 0.0  # USD
    max_cost_per_hour: float = 10.0  # USD
    max_cost_per_day: float = 50.0   # USD


@dataclass
class FeatureUsage:
    """Current usage statistics for a feature."""
    requests_today: int = 0
    requests_this_hour: int = 0
    cost_today: float = 0.0
    cost_this_hour: float = 0.0
    last_request_time: Optional[datetime] = None
    reset_time: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=1))


@dataclass
class FeatureConfig:
    """Configuration for a feature."""
    name: str
    description: str
    tier: FeatureTier
    quota: FeatureQuota
    enabled_by_default: bool = True
    requires_api_key: bool = False
    cooldown_seconds: int = 0


class FeatureGate:
    """Feature gating system for controlling access and costs."""

    # Default feature configurations
    DEFAULT_FEATURES = {
        "derivatives_funding_rate": FeatureConfig(
            name="derivatives_funding_rate",
            description="Real-time funding rate monitoring",
            tier=FeatureTier.BASIC,
            quota=FeatureQuota(
                requests_per_hour=100,
                requests_per_day=1000,
                cost_per_request=0.01,
                max_cost_per_hour=5.0,
                max_cost_per_day=20.0
            )
        ),
        "derivatives_open_interest": FeatureConfig(
            name="derivatives_open_interest",
            description="Open interest tracking",
            tier=FeatureTier.BASIC,
            quota=FeatureQuota(
                requests_per_hour=100,
                requests_per_day=1000,
                cost_per_request=0.01,
                max_cost_per_hour=5.0,
                max_cost_per_day=20.0
            )
        ),
        "derivatives_liquidations": FeatureConfig(
            name="derivatives_liquidations",
            description="Liquidation event monitoring",
            tier=FeatureTier.PRO,
            quota=FeatureQuota(
                requests_per_hour=50,
                requests_per_day=500,
                cost_per_request=0.02,
                max_cost_per_hour=10.0,
                max_cost_per_day=40.0
            )
        ),
        "onchain_cex_transfers": FeatureConfig(
            name="onchain_cex_transfers",
            description="Large transfers to CEX wallets",
            tier=FeatureTier.PRO,
            quota=FeatureQuota(
                requests_per_hour=20,
                requests_per_day=200,
                cost_per_request=0.05,
                max_cost_per_hour=20.0,
                max_cost_per_day=100.0
            ),
            requires_api_key=True
        ),
        "onchain_whale_tracking": FeatureConfig(
            name="onchain_whale_tracking",
            description="Whale movement detection",
            tier=FeatureTier.ENTERPRISE,
            quota=FeatureQuota(
                requests_per_hour=10,
                requests_per_day=100,
                cost_per_request=0.10,
                max_cost_per_hour=50.0,
                max_cost_per_day=200.0
            ),
            requires_api_key=True
        ),
        "sentiment_analysis": FeatureConfig(
            name="sentiment_analysis",
            description="News and social sentiment analysis",
            tier=FeatureTier.BASIC,
            quota=FeatureQuota(
                requests_per_hour=200,
                requests_per_day=2000,
                cost_per_request=0.005,
                max_cost_per_hour=2.0,
                max_cost_per_day=10.0
            )
        ),
        "technical_analysis": FeatureConfig(
            name="technical_analysis",
            description="Advanced technical indicators",
            tier=FeatureTier.BASIC,
            quota=FeatureQuota(
                requests_per_hour=500,
                requests_per_day=5000,
                cost_per_request=0.001,
                max_cost_per_hour=1.0,
                max_cost_per_day=5.0
            )
        )
    }

    def __init__(self):
        self._features: Dict[str, FeatureConfig] = self.DEFAULT_FEATURES.copy()
        self._usage: Dict[str, FeatureUsage] = {}
        self._user_tiers: Dict[str, FeatureTier] = {}
        self._api_keys: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def register_feature(self, config: FeatureConfig) -> None:
        """Register a new feature."""
        with self._lock:
            self._features[config.name] = config
            self._usage[config.name] = FeatureUsage()

    def set_user_tier(self, user_id: str, tier: FeatureTier) -> None:
        """Set the access tier for a user."""
        with self._lock:
            self._user_tiers[user_id] = tier

    def set_api_key(self, user_id: str, api_key: str) -> None:
        """Set API key for a user."""
        with self._lock:
            self._api_keys[user_id] = api_key

    def check_feature_access(
        self,
        feature_name: str,
        user_id: Optional[str] = None
    ) -> tuple[bool, str, FeatureStatus]:
        """Check if a user can access a feature."""
        with self._lock:
            if feature_name not in self._features:
                return False, f"Feature '{feature_name}' not found", FeatureStatus.DISABLED

            feature = self._features[feature_name]
            user_tier = self._user_tiers.get(user_id, FeatureTier.FREE)

            # Check tier access
            if not self._tier_has_access(user_tier, feature.tier):
                return False, f"Feature requires {feature.tier.value} tier or higher", FeatureStatus.DISABLED

            # Check API key requirement
            if feature.requires_api_key and user_id not in self._api_keys:
                return False, f"Feature requires API key", FeatureStatus.DISABLED

            # Check quota
            usage = self._usage.get(feature_name, FeatureUsage())
            status = self._check_quota_status(feature, usage)

            if status == FeatureStatus.QUOTA_EXCEEDED:
                return False, "Feature quota exceeded", status
            elif status == FeatureStatus.THROTTLED:
                return False, "Feature temporarily throttled", status

            return True, "Access granted", status

    @contextmanager
    def use_feature(
        self,
        feature_name: str,
        user_id: Optional[str] = None,
        estimated_cost: Optional[float] = None
    ):
        """Context manager for using a feature with automatic usage tracking."""
        can_access, message, status = self.check_feature_access(feature_name, user_id)

        if not can_access:
            raise FeatureAccessDeniedError(f"Cannot access feature '{feature_name}': {message}")

        # Record usage
        self._record_usage(feature_name, estimated_cost)

        try:
            yield
        except Exception as e:
            # Could implement cost penalties for failed requests here
            raise e

    def _tier_has_access(self, user_tier: FeatureTier, required_tier: FeatureTier) -> bool:
        """Check if user tier has access to required tier."""
        tier_hierarchy = {
            FeatureTier.FREE: 0,
            FeatureTier.BASIC: 1,
            FeatureTier.PRO: 2,
            FeatureTier.ENTERPRISE: 3
        }

        return tier_hierarchy.get(user_tier, 0) >= tier_hierarchy.get(required_tier, 999)

    def _check_quota_status(self, feature: FeatureConfig, usage: FeatureUsage) -> FeatureStatus:
        """Check if feature is within quota limits."""
        now = datetime.now()

        # Reset counters if needed
        if now >= usage.reset_time:
            usage.requests_today = 0
            usage.requests_this_hour = 0
            usage.cost_today = 0.0
            usage.cost_this_hour = 0.0
            usage.reset_time = now + timedelta(days=1)

        # Check hourly limits
        if usage.requests_this_hour >= feature.quota.requests_per_hour:
            return FeatureStatus.THROTTLED

        if usage.cost_this_hour >= feature.quota.max_cost_per_hour:
            return FeatureStatus.QUOTA_EXCEEDED

        # Check daily limits
        if usage.requests_today >= feature.quota.requests_per_day:
            return FeatureStatus.QUOTA_EXCEEDED

        if usage.cost_today >= feature.quota.max_cost_per_day:
            return FeatureStatus.QUOTA_EXCEEDED

        return FeatureStatus.ENABLED

    def _record_usage(self, feature_name: str, estimated_cost: Optional[float] = None) -> None:
        """Record feature usage."""
        with self._lock:
            if feature_name not in self._usage:
                self._usage[feature_name] = FeatureUsage()

            usage = self._usage[feature_name]
            now = datetime.now()

            # Update request counts
            usage.requests_today += 1
            usage.requests_this_hour += 1
            usage.last_request_time = now

            # Update cost (use estimated or default)
            cost = estimated_cost if estimated_cost is not None else self._features[feature_name].quota.cost_per_request
            usage.cost_today += cost
            usage.cost_this_hour += cost

    def get_usage_stats(self, feature_name: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics."""
        with self._lock:
            if feature_name:
                return {
                    feature_name: self._usage.get(feature_name, FeatureUsage()).__dict__
                }
            else:
                return {
                    name: usage.__dict__ for name, usage in self._usage.items()
                }

    def reset_usage(self, feature_name: Optional[str] = None) -> None:
        """Reset usage counters (admin function)."""
        with self._lock:
            if feature_name:
                if feature_name in self._usage:
                    self._usage[feature_name] = FeatureUsage()
            else:
                self._usage = {name: FeatureUsage() for name in self._features.keys()}

    def get_available_features(self, user_id: Optional[str] = None) -> List[str]:
        """Get list of features available to a user."""
        user_tier = self._user_tiers.get(user_id, FeatureTier.FREE)
        available = []

        for feature_name, feature in self._features.items():
            if self._tier_has_access(user_tier, feature.tier):
                can_access, _, _ = self.check_feature_access(feature_name, user_id)
                if can_access:
                    available.append(feature_name)

        return available

    async def start_cleanup_task(self) -> None:
        """Start background task to clean up old usage data."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop the cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(3600)  # Clean up every hour
                self._cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def _cleanup_old_data(self) -> None:
        """Clean up old usage data."""
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(days=7)  # Keep 7 days of history

            for usage in self._usage.values():
                if usage.last_request_time and usage.last_request_time < cutoff:
                    # Reset old usage data
                    usage.requests_today = 0
                    usage.requests_this_hour = 0
                    usage.cost_today = 0.0
                    usage.cost_this_hour = 0.0


class FeatureAccessDeniedError(Exception):
    """Exception raised when feature access is denied."""
    pass