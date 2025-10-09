"""Schema versioning for AutoTrader outputs.

Provides version tracking and validation for output schemas.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# Schema version history
# Format: MAJOR.MINOR.PATCH (semantic versioning)
# - MAJOR: Breaking changes (incompatible with previous versions)
# - MINOR: Backward-compatible additions (new optional fields)
# - PATCH: Bug fixes, documentation (no schema changes)
SCHEMA_VERSION = "1.0.0"
SCHEMA_MAJOR_VERSION = 1


class SchemaVersionError(Exception):
    """Raised when schema version is incompatible."""
    pass


class SchemaType(Enum):
    """Types of output schemas."""
    SCAN_RESULT = "scan_result"
    MARKET_SNAPSHOT = "market_snapshot"
    NARRATIVE_INSIGHT = "narrative_insight"
    GEM_SCORE = "gem_score"
    SAFETY_REPORT = "safety_report"
    ALERT = "alert"
    DRIFT_DETECTION = "drift_detection"
    EXPERIMENT_RESULT = "experiment_result"


@dataclass
class SchemaMetadata:
    """Metadata about a schema version."""
    version: str
    schema_type: str
    created_at: str
    checksum: str
    fields: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    deprecated_fields: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class SchemaVersioner:
    """Manages schema versions and validation."""
    
    def __init__(self):
        """Initialize schema versioner."""
        self._schemas: Dict[str, SchemaMetadata] = {}
        self._load_schemas()
    
    def _load_schemas(self) -> None:
        """Load schema definitions."""
        # Define current schema versions
        # This would typically be loaded from a file
        
        # Scan Result schema v1.0.0
        self._schemas["scan_result_1.0.0"] = SchemaMetadata(
            version="1.0.0",
            schema_type="scan_result",
            created_at="2024-01-01T00:00:00Z",
            checksum="",  # Computed on-the-fly
            required_fields=[
                "token",
                "gem_score",
                "flag",
                "schema_version",  # NEW: Required in all outputs
                "schema_type",  # NEW: Required in all outputs
            ],
            optional_fields=[
                "market_snapshot",
                "narrative",
                "raw_features",
                "adjusted_features",
                "safety_report",
                "debug",
                "artifact_payload",
                "artifact_markdown",
                "artifact_html",
                "news_items",
                "sentiment_metrics",
                "technical_metrics",
                "security_metrics",
                "final_score",
                "github_events",
                "social_posts",
                "tokenomics_metrics",
                "alerts",
            ],
            deprecated_fields=[],
        )
        
        logger.info(f"✅ Loaded {len(self._schemas)} schema definition(s)")
    
    def validate_output(
        self,
        data: Dict[str, Any],
        schema_type: str,
        raise_on_error: bool = True,
    ) -> bool:
        """Validate output data against schema.
        
        Args:
            data: Output data to validate
            schema_type: Type of schema (e.g., "scan_result")
            raise_on_error: Whether to raise exception on validation failure
        
        Returns:
            True if valid
        
        Raises:
            SchemaVersionError: If validation fails and raise_on_error is True
        """
        errors = []
        
        # Check for schema version field
        if "schema_version" not in data:
            errors.append("Missing required field: schema_version")
        
        if "schema_type" not in data:
            errors.append("Missing required field: schema_type")
        
        if errors:
            error_msg = f"Schema validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            if raise_on_error:
                raise SchemaVersionError(error_msg)
            else:
                logger.warning(error_msg)
                return False
        
        # Validate version compatibility
        data_version = data.get("schema_version", "0.0.0")
        self._validate_version_compatibility(data_version, schema_type)
        
        # Validate required fields
        schema_key = f"{schema_type}_{data_version}"
        if schema_key in self._schemas:
            schema = self._schemas[schema_key]
            
            for field in schema.required_fields:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
            
            # Check for deprecated fields
            for field in data.keys():
                if field in schema.deprecated_fields:
                    logger.warning(
                        f"Field '{field}' is deprecated in schema {schema_type} v{data_version}"
                    )
        
        if errors:
            error_msg = f"Schema validation failed for {schema_type} v{data_version}:\n" + \
                       "\n".join(f"  - {e}" for e in errors)
            if raise_on_error:
                raise SchemaVersionError(error_msg)
            else:
                logger.warning(error_msg)
                return False
        
        logger.debug(f"✅ Schema validation passed: {schema_type} v{data_version}")
        return True
    
    def _validate_version_compatibility(
        self,
        data_version: str,
        schema_type: str,
    ) -> None:
        """Validate version compatibility.
        
        Args:
            data_version: Version from data
            schema_type: Schema type
        
        Raises:
            SchemaVersionError: If version is incompatible
        """
        try:
            parts = data_version.split('.')
            data_major = int(parts[0])
        except (ValueError, IndexError) as e:
            raise SchemaVersionError(
                f"Invalid schema version format: {data_version}. "
                f"Expected format: 'MAJOR.MINOR.PATCH'"
            ) from e
        
        if data_major != SCHEMA_MAJOR_VERSION:
            raise SchemaVersionError(
                f"Incompatible schema version: {data_version} "
                f"(current: {SCHEMA_VERSION}). "
                f"Major version mismatch (data: {data_major}, current: {SCHEMA_MAJOR_VERSION}). "
                f"Data may not be readable. Consider migration."
            )
    
    def add_schema_metadata(
        self,
        data: Dict[str, Any],
        schema_type: str,
    ) -> Dict[str, Any]:
        """Add schema metadata to output data.
        
        Args:
            data: Output data
            schema_type: Type of schema
        
        Returns:
            Data with schema metadata
        """
        data["schema_version"] = SCHEMA_VERSION
        data["schema_type"] = schema_type
        data["schema_generated_at"] = datetime.utcnow().isoformat() + "Z"
        return data
    
    def compute_schema_checksum(self, data: Dict[str, Any]) -> str:
        """Compute checksum of schema structure.
        
        Args:
            data: Data to checksum
        
        Returns:
            SHA256 checksum of field structure
        """
        # Sort fields for consistent checksums
        fields = sorted(data.keys())
        fields_str = ",".join(fields)
        return hashlib.sha256(fields_str.encode()).hexdigest()[:16]
    
    def get_schema_info(
        self,
        schema_type: str,
        version: Optional[str] = None,
    ) -> Optional[SchemaMetadata]:
        """Get schema information.
        
        Args:
            schema_type: Schema type
            version: Optional version (defaults to current)
        
        Returns:
            Schema metadata or None if not found
        """
        if version is None:
            version = SCHEMA_VERSION
        
        schema_key = f"{schema_type}_{version}"
        return self._schemas.get(schema_key)
    
    def compare_schemas(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two schema versions.
        
        Args:
            old_data: Old version data
            new_data: New version data
        
        Returns:
            Comparison report
        """
        old_fields = set(old_data.keys())
        new_fields = set(new_data.keys())
        
        added = new_fields - old_fields
        removed = old_fields - new_fields
        common = old_fields & new_fields
        
        return {
            "added_fields": sorted(added),
            "removed_fields": sorted(removed),
            "common_fields": sorted(common),
            "old_version": old_data.get("schema_version", "unknown"),
            "new_version": new_data.get("schema_version", "unknown"),
            "breaking_changes": len(removed) > 0,
        }
    
    def generate_migration_guide(
        self,
        from_version: str,
        to_version: str,
        schema_type: str,
    ) -> str:
        """Generate migration guide between versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            schema_type: Schema type
        
        Returns:
            Migration guide text
        """
        old_key = f"{schema_type}_{from_version}"
        new_key = f"{schema_type}_{to_version}"
        
        old_schema = self._schemas.get(old_key)
        new_schema = self._schemas.get(new_key)
        
        if not old_schema or not new_schema:
            return f"No migration path found from {from_version} to {to_version}"
        
        old_fields = set(old_schema.required_fields + old_schema.optional_fields)
        new_fields = set(new_schema.required_fields + new_schema.optional_fields)
        
        added = new_fields - old_fields
        removed = old_fields - new_fields
        
        guide = f"""
# Migration Guide: {schema_type} v{from_version} → v{to_version}

## Summary
- From Version: {from_version}
- To Version: {to_version}
- Schema Type: {schema_type}

## Changes

### New Fields ({len(added)})
"""
        for field in sorted(added):
            required = "REQUIRED" if field in new_schema.required_fields else "optional"
            guide += f"- `{field}` ({required})\n"
        
        if removed:
            guide += f"\n### Removed Fields ({len(removed)}) ⚠️\n"
            for field in sorted(removed):
                guide += f"- `{field}` (BREAKING CHANGE)\n"
        
        guide += """
## Action Required

1. Update your code to include new required fields
2. Remove references to removed fields (if any)
3. Test with new schema version
4. Update schema version in your outputs

## Example

```python
# Old format
old_output = {
    "token": "BTC",
    "gem_score": 85.0,
}

# New format
new_output = {
    "token": "BTC",
    "gem_score": 85.0,
    "schema_version": \"""" + to_version + """\",
    "schema_type": \"""" + schema_type + """\",
}
```
"""
        
        return guide


# Global versioner instance
_versioner: Optional[SchemaVersioner] = None


def get_versioner() -> SchemaVersioner:
    """Get global schema versioner instance.
    
    Returns:
        SchemaVersioner instance
    """
    global _versioner
    if _versioner is None:
        _versioner = SchemaVersioner()
    return _versioner


def add_schema_metadata(data: Dict[str, Any], schema_type: str) -> Dict[str, Any]:
    """Add schema metadata to output data.
    
    Convenience function using global versioner.
    
    Args:
        data: Output data
        schema_type: Schema type
    
    Returns:
        Data with schema metadata
    """
    versioner = get_versioner()
    return versioner.add_schema_metadata(data, schema_type)


def validate_output(
    data: Dict[str, Any],
    schema_type: str,
    raise_on_error: bool = True,
) -> bool:
    """Validate output against schema.
    
    Args:
        data: Output data
        schema_type: Schema type
        raise_on_error: Whether to raise on error
    
    Returns:
        True if valid
    """
    versioner = get_versioner()
    return versioner.validate_output(data, schema_type, raise_on_error)


if __name__ == "__main__":
    # Test the schema versioner
    versioner = SchemaVersioner()
    
    print("\n" + "=" * 80)
    print("SCHEMA VERSIONER TEST")
    print("=" * 80)
    
    # Test adding metadata
    test_data = {
        "token": "BTC",
        "gem_score": 85.0,
        "flag": True,
    }
    
    print("\nOriginal data:")
    print(json.dumps(test_data, indent=2))
    
    # Add schema metadata
    with_metadata = add_schema_metadata(test_data.copy(), "scan_result")
    
    print("\nWith schema metadata:")
    print(json.dumps(with_metadata, indent=2))
    
    # Validate
    print("\nValidation:")
    try:
        validate_output(with_metadata, "scan_result")
        print("✅ Valid schema")
    except SchemaVersionError as e:
        print(f"❌ Invalid schema: {e}")
    
    print("\n" + "=" * 80 + "\n")
