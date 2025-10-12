#!/usr/bin/env python3
"""
Pre-commit validator for `configs/alert_rules.yaml` with JSON Schema enforcement.

Usage:
    python scripts/validation/validate_alert_rules.py
    python scripts/validation/validate_alert_rules.py --config configs/alert_rules.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import jsonschema
import yaml

project_root = Path(__file__).resolve().parents[2]


class AlertRuleValidationError(Exception):
    """Raised when alert rule validation fails."""

    def __init__(
        self,
        message: str,
        rule_id: str | None = None,
        errors: List[str] | None = None,
    ):
        self.rule_id = rule_id
        self.errors = errors or []
        super().__init__(message)


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load and parse YAML file."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise AlertRuleValidationError(f"Invalid YAML syntax: {exc}")
    except FileNotFoundError as exc:
        raise AlertRuleValidationError(f"File not found: {exc}")


def load_json_schema(schema_path: Path) -> Dict[str, Any]:
    """Load JSON schema for validation."""
    try:
        with schema_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        raise AlertRuleValidationError(f"Failed to load schema: {exc}")


def validate_json_schema(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate alert rules against JSON schema."""
    errors: List[str] = []

    try:
        jsonschema.validate(instance=config, schema=schema)
    except jsonschema.ValidationError as exc:
        path = " -> ".join(str(part) for part in exc.absolute_path)
        errors.append(f"Schema validation failed at '{path}': {exc.message}")
    except jsonschema.SchemaError as exc:
        errors.append(f"Invalid schema: {exc.message}")

    return errors


def validate_unit_normalization(rule: Dict[str, Any]) -> List[str]:
    """Validate that units are correctly normalized in conditions."""
    errors: List[str] = []

    def check_leaf_condition(condition: Dict[str, Any], path: str = "") -> None:
        if condition.get("type") == "compound":
            for index, child in enumerate(condition.get("conditions", [])):
                check_leaf_condition(child, f"{path}.conditions[{index}]")
            return

        metric = condition.get("metric", "")
        threshold = condition.get("threshold")
        unit = condition.get("unit")
        operator = condition.get("operator")

        if any(keyword in metric for keyword in ["usd", "price", "market_cap", "volume"]):
            if not unit:
                errors.append(
                    f"{path}: Metric '{metric}' suggests monetary value but missing 'unit' field",
                )
            elif unit not in ["usd", "eth", "btc"]:
                errors.append(
                    f"{path}: Metric '{metric}' has incompatible unit '{unit}' (expected: usd/eth/btc)",
                )

        if any(keyword in metric for keyword in ["percent", "ratio", "change"]):
            if not unit and isinstance(threshold, (int, float)):
                errors.append(
                    f"{path}: Metric '{metric}' suggests percentage/ratio but missing 'unit' field",
                )

        if unit == "percent" and isinstance(threshold, (int, float)):
            if not (-100 <= threshold <= 1000):
                errors.append(
                    f"{path}: Percent threshold {threshold} outside reasonable range [-100, 1000]",
                )

        if unit == "ratio" and isinstance(threshold, (int, float)) and threshold < 0:
            errors.append(
                f"{path}: Ratio threshold {threshold} should not be negative",
            )

        if operator in ["in", "not_in"] and not isinstance(threshold, list):
            errors.append(
                f"{path}: Operator '{operator}' requires array threshold, got {type(threshold).__name__}",
            )

        if operator in ["lt", "lte", "gt", "gte"] and not isinstance(threshold, (int, float)):
            errors.append(
                f"{path}: Operator '{operator}' requires numeric threshold, got {type(threshold).__name__}",
            )

    if "condition" in rule:
        check_leaf_condition(rule["condition"], f"rule[{rule.get('id', '?')}].condition")

    return errors


def validate_condition_logic(condition: Dict[str, Any], path: str = "") -> List[str]:
    """Validate AND/OR/NOT logic correctness."""
    errors: List[str] = []

    if condition.get("type") != "compound":
        return errors

    operator = condition.get("operator")
    conditions = condition.get("conditions", [])

    if operator == "NOT" and len(conditions) != 1:
        errors.append(f"{path}: NOT operator must have exactly 1 condition, got {len(conditions)}")

    if operator in ["AND", "OR"] and len(conditions) < 2:
        errors.append(f"{path}: {operator} operator must have at least 2 conditions, got {len(conditions)}")

    def count_nesting_depth(cond: Dict[str, Any], depth: int = 0) -> int:
        if cond.get("type") != "compound":
            return depth
        return max(
            (count_nesting_depth(child, depth + 1) for child in cond.get("conditions", [])),
            default=depth,
        )

    max_depth = count_nesting_depth(condition)
    if max_depth > 5:
        errors.append(f"{path}: Excessive nesting depth ({max_depth} levels). Consider simplifying.")

    for index, child_condition in enumerate(conditions):
        errors.extend(
            validate_condition_logic(child_condition, f"{path}.conditions[{index}]")
        )

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

    for policy_name, policy in config.get("escalation_policies", {}).items():
        for index, level in enumerate(policy.get("levels", [])):
            level_channels = set(level.get("channels", []))
            undefined = level_channels - defined_channels
            if undefined:
                errors.append(
                    "Escalation policy '{name}' level {idx} references undefined channels: {missing}".format(
                        name=policy_name,
                        idx=index,
                        missing=", ".join(sorted(undefined)),
                    )
                )

    return errors


def validate_escalation_policy_references(config: Dict[str, Any]) -> List[str]:
    """Ensure all escalation_policy references exist."""
    errors: List[str] = []

    defined_policies = set(config.get("escalation_policies", {}).keys())
    defined_policies.add("none")

    for rule in config.get("rules", []):
        policy = rule.get("escalation_policy")
        if policy and policy not in defined_policies:
            errors.append(
                f"Rule '{rule.get('id', 'unknown')}' references undefined escalation_policy: '{policy}'",
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
    """Perform comprehensive validation of alert_rules.yaml."""
    all_errors: List[str] = []

    try:
        config = load_yaml(config_path)
    except AlertRuleValidationError as exc:
        return False, [str(exc)]

    if schema_path is None:
        schema_path = project_root / "configs" / "alert_rules_schema.json"

    try:
        schema = load_json_schema(schema_path)
        all_errors.extend(validate_json_schema(config, schema))
    except AlertRuleValidationError as exc:
        all_errors.append(str(exc))

    all_errors.extend(validate_duplicate_rule_ids(config))
    all_errors.extend(validate_channel_references(config))
    all_errors.extend(validate_escalation_policy_references(config))

    for rule in config.get("rules", []):
        rule_id = rule.get("id", "unknown")
        all_errors.extend(validate_unit_normalization(rule))
        if "condition" in rule:
            all_errors.extend(
                validate_condition_logic(rule["condition"], f"rule[{rule_id}]")
            )

    return len(all_errors) == 0, all_errors


def main(argv: List[str] | None = None) -> int:
    """Main entry point for validation."""
    parser = argparse.ArgumentParser(
        description="Validate alert_rules.yaml against JSON schema and semantic rules",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=project_root / "configs" / "alert_rules.yaml",
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
    parser.add_argument(
        "--fail-on-minutes",
        action="store_true",
        help="Fail if cool_off_minutes found (v1 legacy). Prefer suppression_duration (seconds).",
    )

    args = parser.parse_args(argv)

    print(f"🔍 Validating {args.config}...")

    success, errors = validate_alert_rules(args.config, args.schema)

    if success:
        print("✅ Validation passed - all alert rules are valid")
        return 0

    print(f"❌ Validation failed with {len(errors)} error(s):\n")
    for index, error in enumerate(errors, 1):
        print(f"  {index}. {error}")

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
