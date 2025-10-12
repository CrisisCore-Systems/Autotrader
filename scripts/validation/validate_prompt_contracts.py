#!/usr/bin/env python3
"""
Validate LLM prompt outputs against JSON schemas.

Usage:
    python scripts/validation/validate_prompt_contracts.py
    python scripts/validation/validate_prompt_contracts.py --prompt narrative_analyzer
    python scripts/validation/validate_prompt_contracts.py --golden-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import jsonschema

project_root = Path(__file__).resolve().parents[2]


class PromptContractValidator:
    """Validator for LLM prompt output contracts."""

    def __init__(self, schemas_dir: Path, fixtures_dir: Path):
        self.schemas_dir = schemas_dir
        self.fixtures_dir = fixtures_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_schema(self, prompt_name: str) -> Dict[str, Any]:
        schema_path = self.schemas_dir / f"{prompt_name}.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        with open(schema_path, encoding="utf-8") as handle:
            return json.load(handle)

    def load_fixture(self, prompt_name: str) -> Dict[str, Any]:
        fixture_path = self.fixtures_dir / f"{prompt_name}_golden.json"
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")

        with open(fixture_path, encoding="utf-8") as handle:
            return json.load(handle)

    def validate_output(
        self,
        output: Dict[str, Any],
        schema: Dict[str, Any],
        prompt_name: str,
    ) -> bool:
        try:
            jsonschema.validate(output, schema)
            return True
        except jsonschema.ValidationError as exc:
            self.errors.append(f"[{prompt_name}] Schema validation failed: {exc.message}")
            return False
        except jsonschema.SchemaError as exc:
            self.errors.append(f"[{prompt_name}] Invalid schema: {exc.message}")
            return False

    def check_schema_version(self, output: Dict[str, Any], prompt_name: str) -> None:
        if "schema_version" not in output:
            self.errors.append(f"[{prompt_name}] Missing required field: schema_version")
        elif not isinstance(output["schema_version"], str):
            self.errors.append(f"[{prompt_name}] schema_version must be a string")

    def check_no_extra_keys(
        self,
        output: Dict[str, Any],
        schema: Dict[str, Any],
        prompt_name: str,
    ) -> None:
        if schema.get("additionalProperties") is False:
            expected_keys = set(schema.get("properties", {}).keys())
            actual_keys = set(output.keys())
            extra_keys = actual_keys - expected_keys

            if extra_keys:
                self.warnings.append(
                    f"[{prompt_name}] Extra keys not in schema: {', '.join(sorted(extra_keys))}"
                )

    def test_prompt(self, prompt_name: str) -> bool:
        print(f"Testing prompt: {prompt_name}")

        try:
            schema = self.load_schema(prompt_name)
            fixture = self.load_fixture(prompt_name)
        except FileNotFoundError as exc:
            self.errors.append(str(exc))
            return False

        valid = self.validate_output(fixture, schema, prompt_name)
        self.check_schema_version(fixture, prompt_name)
        self.check_no_extra_keys(fixture, schema, prompt_name)
        return valid and not self.errors

    def test_all_prompts(self) -> bool:
        if not self.schemas_dir.exists():
            self.errors.append(f"Schemas directory not found: {self.schemas_dir}")
            return False

        schema_files = list(self.schemas_dir.glob("*.json"))
        if not schema_files:
            self.errors.append(f"No schemas found in {self.schemas_dir}")
            return False

        all_passed = True
        for schema_file in sorted(schema_files):
            prompt_name = schema_file.stem
            if not self.test_prompt(prompt_name):
                all_passed = False

        return all_passed

    def print_results(self) -> None:
        if self.errors:
            print("\n❌ VALIDATION FAILED\n", file=sys.stderr)
            print("Errors:", file=sys.stderr)
            for error in self.errors:
                print(f"  • {error}", file=sys.stderr)
            print(file=sys.stderr)

        if self.warnings:
            print("\n⚠️  WARNINGS\n")
            for warning in self.warnings:
                print(f"  • {warning}")
            print()

        if not self.errors and not self.warnings:
            print("\n✅ All prompt contract validations passed!")
        elif not self.errors:
            print("\n✅ Validation passed with warnings.")


def create_golden_fixture_template(
    prompt_name: str,
    schema_path: Path,
    output_path: Path,
) -> None:
    with open(schema_path, encoding="utf-8") as handle:
        schema = json.load(handle)

    fixture: Dict[str, Any] = {}
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for key in required:
        prop = properties.get(key, {})
        prop_type = prop.get("type", "string")

        if key == "schema_version":
            fixture[key] = prop.get("const", "1.0.0")
        elif prop_type == "string":
            fixture[key] = prop.get("enum", [f"example_{key}"])[0]
        elif prop_type == "number":
            minimum = prop.get("minimum", 0.0)
            maximum = prop.get("maximum", minimum + 1)
            fixture[key] = (minimum + maximum) / 2
        elif prop_type == "boolean":
            fixture[key] = False
        elif prop_type == "array":
            fixture[key] = []
        elif prop_type == "object":
            fixture[key] = {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(fixture, handle, indent=2)

    print(f"✅ Created template fixture: {output_path}")
    print("⚠️  Please edit this file with realistic example data!")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate LLM prompt output contracts",
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        default=project_root / "schemas" / "prompt_outputs",
        help="Directory containing JSON schemas",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=project_root / "tests" / "fixtures" / "prompt_outputs",
        help="Directory containing golden fixtures",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Test a specific prompt (e.g., narrative_analyzer)",
    )
    parser.add_argument(
        "--create-fixture",
        type=str,
        metavar="PROMPT_NAME",
        help="Create a golden fixture template for a prompt",
    )
    parser.add_argument(
        "--golden-test",
        action="store_true",
        help="Run all golden fixture tests",
    )

    args = parser.parse_args()

    if args.create_fixture:
        schema_path = args.schemas_dir / f"{args.create_fixture}.json"
        fixture_path = args.fixtures_dir / f"{args.create_fixture}_golden.json"

        if not schema_path.exists():
            print(f"❌ Schema not found: {schema_path}", file=sys.stderr)
            return 1

        create_golden_fixture_template(args.create_fixture, schema_path, fixture_path)
        return 0

    validator = PromptContractValidator(args.schemas_dir, args.fixtures_dir)

    if args.prompt:
        success = validator.test_prompt(args.prompt)
    else:
        success = validator.test_all_prompts()

    validator.print_results()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
