"""Data freshness tracking for research workspace.

This module tracks the freshness of data from various sources
(CoinGecko, Dexscreener, Blockscout, etc.) for the Research workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional


class FreshnessLevel(Enum):
    """Freshness level classification."""
    
    FRESH = "fresh"  # < 5 minutes old
    RECENT = "recent"  # < 1 hour old
    STALE = "stale"  # < 24 hours old
    OUTDATED = "outdated"  # > 24 hours old


@dataclass
class DataSourceFreshness:
    """Freshness metadata for a data source."""
    
    source_name: str
    last_updated: datetime
    data_age_seconds: float
    freshness_level: FreshnessLevel
    is_free: bool = True
    update_frequency_seconds: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "source_name": self.source_name,
            "last_updated": self.last_updated.isoformat() + "Z",
            "data_age_seconds": self.data_age_seconds,
            "freshness_level": self.freshness_level.value,
            "is_free": self.is_free,
            "update_frequency_seconds": self.update_frequency_seconds,
        }


class FreshnessTracker:
    """Track data freshness for research workspace."""
    
    def __init__(self):
        """Initialize freshness tracker."""
        self.source_timestamps: Dict[str, datetime] = {}
        
    def record_update(self, source_name: str, timestamp: Optional[datetime] = None) -> None:
        """Record an update from a data source.
        
        Parameters
        ----------
        source_name : str
            Name of the data source (e.g., "coingecko", "dexscreener")
        timestamp : Optional[datetime]
            Timestamp of the update (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        self.source_timestamps[source_name] = timestamp
    
    def get_freshness(
        self,
        source_name: str,
        is_free: bool = True,
        update_frequency_seconds: Optional[int] = None
    ) -> DataSourceFreshness:
        """Get freshness metadata for a data source.
        
        Parameters
        ----------
        source_name : str
            Name of the data source
        is_free : bool
            Whether this is a free data source
        update_frequency_seconds : Optional[int]
            Expected update frequency in seconds
            
        Returns
        -------
        DataSourceFreshness
            Freshness metadata
        """
        now = datetime.utcnow()
        last_updated = self.source_timestamps.get(source_name, now)
        data_age_seconds = (now - last_updated).total_seconds()
        
        # Classify freshness
        if data_age_seconds < 300:  # < 5 minutes
            freshness_level = FreshnessLevel.FRESH
        elif data_age_seconds < 3600:  # < 1 hour
            freshness_level = FreshnessLevel.RECENT
        elif data_age_seconds < 86400:  # < 24 hours
            freshness_level = FreshnessLevel.STALE
        else:
            freshness_level = FreshnessLevel.OUTDATED
        
        return DataSourceFreshness(
            source_name=source_name,
            last_updated=last_updated,
            data_age_seconds=data_age_seconds,
            freshness_level=freshness_level,
            is_free=is_free,
            update_frequency_seconds=update_frequency_seconds,
        )
    
    def get_all_freshness(self) -> Dict[str, DataSourceFreshness]:
        """Get freshness for all tracked sources.
        
        Returns
        -------
        Dict[str, DataSourceFreshness]
            Map of source name to freshness metadata
        """
        result = {}
        for source_name in self.source_timestamps:
            result[source_name] = self.get_freshness(source_name)
        return result


# Global freshness tracker instance
_freshness_tracker: Optional[FreshnessTracker] = None


def get_freshness_tracker() -> FreshnessTracker:
    """Get the global freshness tracker instance.
    
    Returns
    -------
    FreshnessTracker
        The global freshness tracker
    """
    global _freshness_tracker
    if _freshness_tracker is None:
        _freshness_tracker = FreshnessTracker()
    return _freshness_tracker
