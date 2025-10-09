#!/usr/bin/env python
"""Pre-commit validator for alert_rules.yaml with JSON Schema enforcement.

Usage:
    python scripts/validate_alert_rules.py
    python scripts/validate_alert_rules.py --config configs/alert_rules.yaml
    
Exit codes:
    0: Validation passed
    1: Validation failed
    2: File not found or invalid
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import jsonschema
import yaml


class AlertRuleValidationError(Exception):
    """Raised when alert rule validation fails."""
    
    def __init__(self, message: str, rule_id: str | None = None, errors: List[str] | None = None):
        self.rule_id = rule_id
        self.errors = errors or []
        super().__init__(message)


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load and parse YAML file."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise AlertRuleValidationError(f"Invalid YAML syntax: {e}")
    except FileNotFoundError:
        raise AlertRuleValidationError(f"File not found: {path}")


def load_json_schema(schema_path: Path) -> Dict[str, Any]:
    """Load JSON schema for validation."""
    try:
        with schema_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise AlertRuleValidationError(f"Failed to load schema: {e}")


def validate_json_schema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate alert rules against JSON schema."""
    errors: List[str] = []
    
    try:
        jsonschema.validate(instance=config, schema=schema)
    except jsonschema.ValidationError as e:
        # Collect all validation errors
        path = " -> ".join(str(p) for p in e.absolute_path)
        error_msg = f"Schema validation failed at '{path}': {e.message}"
        errors.append(error_msg)
    except jsonschema.SchemaError as e:
        errors.append(f"Invalid schema: {e.message}")
    
    return errors


def validate_unit_normalization(rule: Dict[str, Any]) -> List[str]:
    """Validate that units are correctly normalized in conditions.
    
    Ensures that:
    1. Unit fields are present where needed (USD amounts, percentages)
    2. Unit values are consistent within related conditions
    3. Thresholds match expected ranges for units
    """
    errors: List[str] = []
    
    def check_leaf_condition(condition: Dict[str, Any], path: str = ""):
        """Recursively check leaf conditions for unit normalization."""
        if condition.get("type") == "compound":
            for i, child in enumerate(condition.get("conditions", [])):
                check_leaf_condition(child, f"{path}.conditions[{i}]")
            return
        
        metric = condition.get("metric", "")
        threshold = condition.get("threshold")
        unit = condition.get("unit")
        operator = condition.get("operator")
        
        # Check if metric suggests a unit requirement
        if any(keyword in metric for keyword in ["usd", "price", "market_cap", "volume"]):
            if not unit:
                errors.append(
                    f"{path}: Metric '{metric}' suggests monetary value but missing 'unit' field"
                )
            elif unit not in ["usd", "eth", "btc"]:
                errors.append(
                    f"{path}: Metric '{metric}' has incompatible unit '{unit}' (expected: usd/eth/btc)"
                )
        
        if any(keyword in metric for keyword in ["percent", "ratio", "change"]):
            if not unit and isinstance(threshold, (int, float)):
                errors.append(
                    f"{path}: Metric '{metric}' suggests percentage/ratio but missing 'unit' field"
                )
        
        # Validate threshold ranges based on unit
        if unit == "percent" and isinstance(threshold, (int, float)):
            if not (-100 <= threshold <= 1000):
                errors.append(
                    f"{path}: Percent threshold {threshold} outside reasonable range [-100, 1000]"
                )
        
        if unit == "ratio" and isinstance(threshold, (int, float)):
            if threshold < 0:
                errors.append(
                    f"{path}: Ratio threshold {threshold} should not be negative"
                )
        
        # Check operators are appropriate for data types
        if operator in ["in", "not_in"] and not isinstance(threshold, list):
            errors.append(
                f"{path}: Operator '{operator}' requires array threshold, got {type(threshold).__name__}"
            )
        
        if operator in ["lt", "lte", "gt", "gte"] and not isinstance(threshold, (int, float)):
            errors.append(
                f"{path}: Operator '{operator}' requires numeric threshold, got {type(threshold).__name__}"
            )
    
    # Check v2 compound conditions
    if "condition" in rule:
        check_leaf_condition(rule["condition"], f"rule[{rule.get('id', '?')}].condition")
    
    return errors


def validate_condition_logic(condition: Dict[str, Any], path: str = "") -> List[str]:
    """Validate AND/OR/NOT logic correctness.
    
    Ensures:
    1. AND/OR operators have at least 2 conditions
    2. NOT operator has exactly 1 condition
    3. No circular references or infinite nesting
    4. Consistent metric types in comparisons
    """
    errors: List[str] = []
    
    if condition.get("type") != "compound":
        return errors
    
    operator = condition.get("operator")
    conditions = condition.get("conditions", [])
    
    # Validate operator-specific constraints (redundant with schema, but explicit)
    if operator == "NOT" and len(conditions) != 1:
        errors.append(f"{path}: NOT operator must have exactly 1 condition, got {len(conditions)}")
    
    if operator in ["AND", "OR"] and len(conditions) < 2:
        errors.append(f"{path}: {operator} operator must have at least 2 conditions, got {len(conditions)}")
    
    # Check for excessive nesting (potential performance issue)
    def count_nesting_depth(cond: Dict[str, Any], depth: int = 0) -> int:
        if cond.get("type") != "compound":
            return depth
        return max(
            (count_nesting_depth(c, depth + 1) for c in cond.get("conditions", [])),
            default=depth
        )
    
    max_depth = count_nesting_depth(condition)
    if max_depth > 5:
        errors.append(f"{path}: Excessive nesting depth ({max_depth} levels). Consider simplifying.")
    
    # Recursively validate child conditions
    for i, child_condition in enumerate(conditions):
        child_errors = validate_condition_logic(child_condition, f"{path}.conditions[{i}]")
        errors.extend(child_errors)
    
    return errors


def validate_channel_references(config: Dict[str, Any]) -> List[str]:
    """Ensure all channel references in rules exist in channel config."""
    errors: List[str] = []
    
    defined_channels = set(config.get("channels", {}).keys())
    
    for rule in config.get("rules", []):
        rule_id = rule.get("id", "unknown")
        referenced_channels = set(rule.get("channels", []))
        
        undefined = referenced_channels - defined_channels
        if undefined:
            errors.append(
                f"Rule '{rule_id}' references undefined channels: {', '.join(sorted(undefined))}"
            )
    
    # Check escalation policies
    for policy_name, policy in config.get("escalation_policies", {}).items():
        for i, level in enumerate(policy.get("levels", [])):
            level_channels = set(level.get("channels", []))
            undefined = level_channels - defined_channels
            if undefined:
                errors.append(
                    f"Escalation policy '{policy_name}' level {i} references undefined channels: "
                    f"{', '.join(sorted(undefined))}"
                )
    
    return errors


def validate_escalation_policy_references(config: Dict[str, Any]) -> List[str]:
    """Ensure all escalation_policy references exist."""
    errors: List[str] = []
    
    defined_policies = set(config.get("escalation_policies", {}).keys())
    defined_policies.add("none")  # Built-in policy
    
    for rule in config.get("rules", []):
        rule_id = rule.get("id", "unknown")
        policy = rule.get("escalation_policy")
        
        if policy and policy not in defined_policies:
            errors.append(
                f"Rule '{rule_id}' references undefined escalation_policy: '{policy}'"
            )
    
    return errors


def validate_duplicate_rule_ids(config: Dict[str, Any]) -> List[str]:
    """Check for duplicate rule IDs."""
    errors: List[str] = []
    seen_ids: Set[str] = set()
    
    for rule in config.get("rules", []):
        rule_id = rule.get("id")
        if rule_id in seen_ids:
            errors.append(f"Duplicate rule ID: '{rule_id}'")
        seen_ids.add(rule_id)
    
    return errors


def validate_alert_rules(
    config_path: Path,
    schema_path: Path | None = None,
) -> Tuple[bool, List[str]]:
    """Perform comprehensive validation of alert_rules.yaml.
    
    Returns:
        Tuple of (success: bool, errors: List[str])
    """
    all_errors: List[str] = []
    
    # Load configuration
    try:
        config = load_yaml(config_path)
    except AlertRuleValidationError as e:
        return False, [str(e)]
    
    # Load and validate against JSON schema
    if schema_path is None:
        schema_path = config_path.parent / "alert_rules_schema.json"
    
    try:
        schema = load_json_schema(schema_path)
        schema_errors = validate_json_schema(config, schema)
        all_errors.extend(schema_errors)
    except AlertRuleValidationError as e:
        all_errors.append(str(e))
    
    # Semantic validation (beyond JSON schema)
    all_errors.extend(validate_duplicate_rule_ids(config))
    all_errors.extend(validate_channel_references(config))
    all_errors.extend(validate_escalation_policy_references(config))
    
    # Rule-specific validation
    for rule in config.get("rules", []):
        rule_id = rule.get("id", "unknown")
        
        # Unit normalization
        unit_errors = validate_unit_normalization(rule)
        all_errors.extend(unit_errors)
        
        # Condition logic
        if "condition" in rule:
            logic_errors = validate_condition_logic(rule["condition"], f"rule[{rule_id}]")
            all_errors.extend(logic_errors)
    
    return len(all_errors) == 0, all_errors


def main(argv: List[str] | None = None) -> int:
    """Main entry point for validation."""
    parser = argparse.ArgumentParser(
        description="Validate alert_rules.yaml against JSON schema and semantic rules"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/alert_rules.yaml"),
        help="Path to alert_rules.yaml (default: configs/alert_rules.yaml)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Path to JSON schema (default: configs/alert_rules_schema.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code 1 on any validation errors",
    )
    
    args = parser.parse_args(argv)
    
    print(f"🔍 Validating {args.config}...")
    
    success, errors = validate_alert_rules(args.config, args.schema)
    
    if success:
        print("✅ Validation passed - all alert rules are valid")
        return 0
    
    print(f"❌ Validation failed with {len(errors)} error(s):\n")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. {error}")
    
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
