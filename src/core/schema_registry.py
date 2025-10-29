"""Output Schema Registry for AutoTrader.

This module provides versioned schema definitions and validation for all
artifacts and notebook outputs. Ensures backward compatibility and enables
schema evolution tracking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4


class SchemaType(Enum):
    """Types of schemas in the registry."""
    
    ARTIFACT = "artifact"
    NOTEBOOK_OUTPUT = "notebook_output"
    API_RESPONSE = "api_response"
    METRIC = "metric"
    ALERT = "alert"


@dataclass
class FieldDefinition:
    """Definition of a single field in a schema."""
    
    name: str
    field_type: str  # e.g., "string", "float", "int", "boolean", "object", "array"
    required: bool = True
    nullable: bool = False
    description: str = ""
    default: Any = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    deprecated: bool = False
    deprecated_reason: Optional[str] = None
    added_in_version: Optional[str] = None
    deprecated_in_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.field_type,
            "required": self.required,
            "nullable": self.nullable,
            "description": self.description,
            "default": self.default,
            "constraints": self.constraints,
            "deprecated": self.deprecated,
            "deprecated_reason": self.deprecated_reason,
            "added_in_version": self.added_in_version,
            "deprecated_in_version": self.deprecated_in_version,
        }


@dataclass
class SchemaVersion:
    """A versioned schema definition."""
    
    schema_id: str
    schema_type: SchemaType
    version: str
    fields: List[FieldDefinition]
    created_at: datetime
    description: str = ""
    backward_compatible: bool = True
    breaking_changes: List[str] = field(default_factory=list)
    migration_guide: Optional[str] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schema_id": self.schema_id,
            "schema_type": self.schema_type.value,
            "version": self.version,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "backward_compatible": self.backward_compatible,
            "breaking_changes": self.breaking_changes,
            "migration_guide": self.migration_guide,
            "examples": self.examples,
            "metadata": self.metadata,
        }
    
    def validate(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate data against this schema.
        
        Parameters
        ----------
        data : Dict[str, Any]
            Data to validate.
            
        Returns
        -------
        tuple[bool, List[str]]
            Tuple of (is_valid, error_messages).
        """
        errors = []
        
        # Check required fields
        for field_def in self.fields:
            if field_def.required and field_def.name not in data:
                if field_def.default is None:
                    errors.append(f"Required field missing: {field_def.name}")
        
        # Validate field types
        for field_name, value in data.items():
            field_def = next((f for f in self.fields if f.name == field_name), None)
            
            if field_def is None:
                # Unknown field - warning but not error
                continue
            
            # Check nullable
            if value is None:
                if not field_def.nullable:
                    errors.append(f"Field '{field_name}' cannot be null")
                continue
            
            # Type validation
            expected_type = field_def.field_type
            if not self._validate_type(value, expected_type):
                errors.append(
                    f"Field '{field_name}' has wrong type. "
                    f"Expected {expected_type}, got {type(value).__name__}"
                )
            
            # Constraint validation
            for constraint_name, constraint_value in field_def.constraints.items():
                if not self._validate_constraint(value, constraint_name, constraint_value):
                    errors.append(
                        f"Field '{field_name}' violates constraint: "
                        f"{constraint_name}={constraint_value}"
                    )
        
        return len(errors) == 0, errors
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type."""
        type_map = {
            "string": str,
            "int": int,
            "integer": int,
            "float": (int, float),
            "number": (int, float),
            "boolean": bool,
            "bool": bool,
            "array": list,
            "list": list,
            "object": dict,
            "dict": dict,
        }
        
        expected_python_type = type_map.get(expected_type.lower())
        if expected_python_type is None:
            return True  # Unknown type, skip validation
        
        return isinstance(value, expected_python_type)
    
    def _validate_constraint(self, value: Any, constraint: str, constraint_value: Any) -> bool:
        """Validate a specific constraint."""
        validators = {
            "min": lambda v, cv: v >= cv,
            "max": lambda v, cv: v <= cv,
            "min_length": lambda v, cv: len(v) >= cv,
            "max_length": lambda v, cv: len(v) <= cv,
            "pattern": lambda v, cv: bool(__import__('re').match(cv, str(v))),
            "enum": lambda v, cv: v in cv,
        }
        
        validator = validators.get(constraint)
        if validator is None:
            return True  # Unknown constraint, skip
        
        return validator(value, constraint_value)


class SchemaRegistry:
    """Central registry for managing schemas."""
    
    def __init__(self, registry_dir: Optional[Path] = None):
        """Initialize schema registry.
        
        Parameters
        ----------
        registry_dir : Optional[Path]
            Directory to store schemas, defaults to ./schemas
        """
        self.registry_dir = registry_dir or Path("./schemas")
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.schemas: Dict[str, Dict[str, SchemaVersion]] = {}  # schema_id -> version -> schema
        self._load_schemas()
    
    def _load_schemas(self) -> None:
        """Load schemas from registry directory."""
        for schema_file in self.registry_dir.glob("*.json"):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    schema = self._deserialize_schema(data)
                    
                    if schema.schema_id not in self.schemas:
                        self.schemas[schema.schema_id] = {}
                    
                    self.schemas[schema.schema_id][schema.version] = schema
            except Exception as e:
                print(f"Warning: Failed to load schema {schema_file}: {e}")
    
    def _deserialize_schema(self, data: Dict[str, Any]) -> SchemaVersion:
        """Deserialize schema from dict."""
        fields = [
            FieldDefinition(
                name=f["name"],
                field_type=f["type"],
                required=f.get("required", True),
                nullable=f.get("nullable", False),
                description=f.get("description", ""),
                default=f.get("default"),
                constraints=f.get("constraints", {}),
                deprecated=f.get("deprecated", False),
                deprecated_reason=f.get("deprecated_reason"),
                added_in_version=f.get("added_in_version"),
                deprecated_in_version=f.get("deprecated_in_version"),
            )
            for f in data["fields"]
        ]
        
        return SchemaVersion(
            schema_id=data["schema_id"],
            schema_type=SchemaType(data["schema_type"]),
            version=data["version"],
            fields=fields,
            created_at=datetime.fromisoformat(data["created_at"]),
            description=data.get("description", ""),
            backward_compatible=data.get("backward_compatible", True),
            breaking_changes=data.get("breaking_changes", []),
            migration_guide=data.get("migration_guide"),
            examples=data.get("examples", []),
            metadata=data.get("metadata", {}),
        )
    
    def register_schema(self, schema: SchemaVersion) -> None:
        """Register a new schema version.
        
        Parameters
        ----------
        schema : SchemaVersion
            Schema to register.
        """
        if schema.schema_id not in self.schemas:
            self.schemas[schema.schema_id] = {}
        
        if schema.version in self.schemas[schema.schema_id]:
            raise ValueError(f"Schema {schema.schema_id} version {schema.version} already exists")
        
        self.schemas[schema.schema_id][schema.version] = schema
        
        # Save to disk
        filename = f"{schema.schema_id}_v{schema.version.replace('.', '_')}.json"
        filepath = self.registry_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(schema.to_dict(), f, indent=2, default=str)
        
        print(f"✓ Registered schema: {schema.schema_id} v{schema.version}")
    
    def get_schema(self, schema_id: str, version: Optional[str] = None) -> Optional[SchemaVersion]:
        """Get schema by ID and version.
        
        Parameters
        ----------
        schema_id : str
            Schema identifier.
        version : Optional[str]
            Version string, if None returns latest version.
            
        Returns
        -------
        Optional[SchemaVersion]
            Schema if found, None otherwise.
        """
        if schema_id not in self.schemas:
            return None
        
        if version is None:
            # Return latest version
            versions = list(self.schemas[schema_id].keys())
            if not versions:
                return None
            latest_version = max(versions, key=lambda v: [int(x) for x in v.split('.')])
            return self.schemas[schema_id][latest_version]
        
        return self.schemas[schema_id].get(version)
    
    def validate_data(
        self,
        schema_id: str,
        data: Dict[str, Any],
        version: Optional[str] = None,
    ) -> tuple[bool, List[str]]:
        """Validate data against schema.
        
        Parameters
        ----------
        schema_id : str
            Schema identifier.
        data : Dict[str, Any]
            Data to validate.
        version : Optional[str]
            Schema version, defaults to latest.
            
        Returns
        -------
        tuple[bool, List[str]]
            Tuple of (is_valid, error_messages).
        """
        schema = self.get_schema(schema_id, version)
        if schema is None:
            return False, [f"Schema not found: {schema_id} v{version}"]
        
        return schema.validate(data)
    
    def list_schemas(self, schema_type: Optional[SchemaType] = None) -> List[SchemaVersion]:
        """List all schemas, optionally filtered by type.
        
        Parameters
        ----------
        schema_type : Optional[SchemaType]
            Filter by schema type.
            
        Returns
        -------
        List[SchemaVersion]
            List of schemas (latest version of each).
        """
        result = []
        for schema_id, versions in self.schemas.items():
            if not versions:
                continue
            
            # Get latest version
            latest_version = max(versions.keys(), key=lambda v: [int(x) for x in v.split('.')])
            schema = versions[latest_version]
            
            if schema_type is None or schema.schema_type == schema_type:
                result.append(schema)
        
        return result
    
    def get_version_history(self, schema_id: str) -> List[SchemaVersion]:
        """Get version history for a schema.
        
        Parameters
        ----------
        schema_id : str
            Schema identifier.
            
        Returns
        -------
        List[SchemaVersion]
            List of all versions, sorted by version number.
        """
        if schema_id not in self.schemas:
            return []
        
        versions = list(self.schemas[schema_id].values())
        return sorted(versions, key=lambda s: [int(x) for x in s.version.split('.')])
    
    def export_documentation(self, output_path: Optional[Path] = None) -> Path:
        """Export schema documentation.
        
        Parameters
        ----------
        output_path : Optional[Path]
            Output file path.
            
        Returns
        -------
        Path
            Path to generated documentation.
        """
        if output_path is None:
            output_path = self.registry_dir / "SCHEMA_DOCS.md"
        
        lines = [
            "# Schema Registry Documentation",
            "",
            f"**Generated:** {datetime.utcnow().isoformat()}",
            f"**Total Schemas:** {len(self.schemas)}",
            "",
        ]
        
        # Group by type
        by_type: Dict[SchemaType, List[SchemaVersion]] = {}
        for schema in self.list_schemas():
            if schema.schema_type not in by_type:
                by_type[schema.schema_type] = []
            by_type[schema.schema_type].append(schema)
        
        for schema_type, schemas in by_type.items():
            lines.extend([
                f"## {schema_type.value.replace('_', ' ').title()} Schemas",
                "",
            ])
            
            for schema in sorted(schemas, key=lambda s: s.schema_id):
                lines.extend([
                    f"### {schema.schema_id} v{schema.version}",
                    "",
                    f"**Description:** {schema.description}",
                    "",
                    "**Fields:**",
                    "",
                    "| Field | Type | Required | Description |",
                    "|-------|------|----------|-------------|",
                ])
                
                for field in schema.fields:
                    required = "✓" if field.required else "✗"
                    deprecated = " _(deprecated)_" if field.deprecated else ""
                    lines.append(
                        f"| `{field.name}` | {field.field_type} | {required} | "
                        f"{field.description}{deprecated} |"
                    )
                
                lines.append("")
                
                if schema.examples:
                    lines.extend([
                        "**Example:**",
                        "",
                        "```json",
                        json.dumps(schema.examples[0], indent=2),
                        "```",
                        "",
                    ])
                
                if schema.breaking_changes:
                    lines.extend([
                        "**Breaking Changes:**",
                        "",
                    ])
                    for change in schema.breaking_changes:
                        lines.append(f"- {change}")
                    lines.append("")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✓ Exported documentation to: {output_path}")
        return output_path


# Global registry instance
_global_registry: Optional[SchemaRegistry] = None


def get_schema_registry() -> SchemaRegistry:
    """Get global schema registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SchemaRegistry()
    return _global_registry
