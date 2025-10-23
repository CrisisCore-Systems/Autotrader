"""In-memory representation of a Redis-like feature store."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional


@dataclass
class FeatureRecord:
    token_id: str
    values: Dict[str, float]
    timestamp: float = field(default_factory=time.time)


class FeatureValidationError(Exception):
    """Raised when feature validation fails."""
    pass


class InMemoryFeatureStore:
    """Simplified feature store mirroring the Redis Streams contract.
    
    Includes basic validation to prevent invalid feature values from poisoning
    model inputs (e.g., NaN, Inf values).
    """

    def __init__(self, enable_validation: bool = True) -> None:
        """Initialize feature store.
        
        Args:
            enable_validation: Enable basic validation checks for feature values
        """
        self._store: Dict[str, FeatureRecord] = {}
        self.enable_validation = enable_validation

    def put(self, record: FeatureRecord) -> None:
        """Store a feature record.
        
        Args:
            record: Feature record to store
            
        Raises:
            FeatureValidationError: If validation is enabled and values are invalid
        """
        if self.enable_validation:
            self._validate_record(record)
        self._store[record.token_id] = record

    def get(self, token_id: str) -> Optional[FeatureRecord]:
        return self._store.get(token_id)

    def snapshot(self) -> Iterable[FeatureRecord]:
        return list(self._store.values())
    
    def _validate_record(self, record: FeatureRecord) -> None:
        """Validate feature record values.
        
        Args:
            record: Record to validate
            
        Raises:
            FeatureValidationError: If any values are invalid
        """
        errors = []
        
        for feature_name, value in record.values.items():
            # Check for NaN
            if math.isnan(value):
                errors.append(f"{feature_name} is NaN")
            
            # Check for Inf
            if math.isinf(value):
                errors.append(f"{feature_name} is Inf")
        
        if errors:
            raise FeatureValidationError(
                f"Feature validation failed for token {record.token_id}: {'; '.join(errors)}"
            )
