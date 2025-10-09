#!/usr/bin/env python3
"""
Validate LLM prompt outputs against JSON schemas and golden test fixtures.

This script ensures that LLM responses conform to defined contracts by:
1. Loading JSON Schema definitions from schemas/prompt_outputs/
2. Validating golden test fixtures against these schemas
3. Checking schema_version consistency
4. Enforcing additionalProperties: false to catch schema drift

Usage:
    python scripts/validate_prompt_outputs.py                     # Validate all fixtures
    python scripts/validate_prompt_outputs.py --fail-on-extra     # Fail on undocumented properties
    python scripts/validate_prompt_outputs.py --prompt narrative_analyzer  # Validate specific prompt
    python scripts/validate_prompt_outputs.py --create-template narrative_analyzer  # Create template
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from jsonschema import Draft202012Validator, ValidationError
    from jsonschema.exceptions import SchemaError
except ImportError:
    print("[ERROR] jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(1)


class PromptOutputValidator:
    """Validates LLM prompt outputs against JSON schemas."""

    def __init__(self, schemas_dir: Path, fixtures_dir: Path, fail_on_extra: bool = False):
        self.schemas_dir = schemas_dir
        self.fixtures_dir = fixtures_dir
        self.fail_on_extra = fail_on_extra
        self.schema_cache: Dict[str, Dict[str, Any]] = {}

    def load_json(self, path: Path) -> Dict[str, Any]:
        """Load and parse JSON file."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON in {path}: {e}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"[ERROR] Failed to read {path}: {e}", file=sys.stderr)
            raise

    def load_schema(self, prompt_name: str) -> Dict[str, Any]:
        """Load schema for a prompt, with caching."""
        if prompt_name in self.schema_cache:
            return self.schema_cache[prompt_name]

        schema_path = self.schemas_dir / f"{prompt_name}.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        schema = self.load_json(schema_path)

        # Enforce additionalProperties: false if requested
        if self.fail_on_extra and "additionalProperties" not in schema:
            schema["additionalProperties"] = False

        # Validate schema itself
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            print(f"[ERROR] Invalid schema {schema_path}: {e}", file=sys.stderr)
            raise

        self.schema_cache[prompt_name] = schema
        return schema

    def validate_fixture(self, prompt_name: str, fixture_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a single fixture against its schema.

        Returns:
            (success: bool, errors: List[str])
        """
        errors = []

        try:
            schema = self.load_schema(prompt_name)
        except Exception as e:
            return False, [f"Failed to load schema: {e}"]

        try:
            data = self.load_json(fixture_path)
        except Exception as e:
            return False, [f"Failed to load fixture: {e}"]

        # Check schema_version presence
        if "schema_version" not in data:
            errors.append("Missing required field: schema_version")

        # Validate against JSON Schema
        validator = Draft202012Validator(schema)
        validation_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))

        for error in validation_errors:
            path = " -> ".join([str(x) for x in error.path]) or "(root)"
            errors.append(f"{path}: {error.message}")

        return len(errors) == 0, errors

    def create_template(self, prompt_name: str) -> Dict[str, Any]:
        """Create a template fixture from schema examples."""
        schema = self.load_schema(prompt_name)

        if "examples" in schema and schema["examples"]:
            return schema["examples"][0]

        # Generate minimal valid template from required fields
        template = {}
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field in properties:
                prop = properties[field]
                prop_type = prop.get("type", "string")

                if prop_type == "string":
                    if "enum" in prop:
                        template[field] = prop["enum"][0]
                    elif field == "schema_version":
                        template[field] = "v1.0.0"
                    else:
                        template[field] = ""
                elif prop_type == "number":
                    template[field] = 0.0
                elif prop_type == "boolean":
                    template[field] = False
                elif prop_type == "array":
                    template[field] = []
                elif prop_type == "object":
                    template[field] = {}

        return template

    def validate_all(self, specific_prompt: str = None) -> int:
        """
        Validate all fixtures (or specific prompt's fixtures).

        Returns:
            Exit code (0 = success, 1 = failures)
        """
        if not self.schemas_dir.exists():
            print(f"[ERROR] Schemas directory not found: {self.schemas_dir}", file=sys.stderr)
            return 1

        if not self.fixtures_dir.exists():
            print(f"[ERROR] Fixtures directory not found: {self.fixtures_dir}", file=sys.stderr)
            return 1

        # Build schema index
        schema_files = list(self.schemas_dir.glob("*.schema.json"))
        if not schema_files:
            print(f"[ERROR] No schemas found in {self.schemas_dir}", file=sys.stderr)
            return 1

        schema_index = {s.stem.replace(".schema", ""): s for s in schema_files}
        print(f"[INFO] Found {len(schema_index)} schemas: {', '.join(sorted(schema_index.keys()))}")

        # Find fixtures to validate
        fixture_files = list(self.fixtures_dir.glob("*.json"))
        if not fixture_files:
            print(f"[WARN] No fixtures found in {self.fixtures_dir}")
            return 0

        total_fixtures = 0
        failures = 0

        for fixture in sorted(fixture_files):
            # Extract prompt name from fixture filename
            # narrative_analyzer_golden.json -> narrative_analyzer
            name = fixture.stem.replace("_golden", "").replace("_test", "")

            if specific_prompt and name != specific_prompt:
                continue

            if name not in schema_index:
                print(f"[WARN] No schema for fixture {fixture.name} (expected {name}.schema.json)")
                continue

            total_fixtures += 1
            success, errors = self.validate_fixture(name, fixture)

            if success:
                print(f"[OK] {fixture.name} ✓")
            else:
                failures += 1
                print(f"[FAIL] {fixture.name} ✗")
                for error in errors:
                    print(f"  - {error}")

        print(f"\n{'='*70}")
        print(f"Validated {total_fixtures} fixtures: {total_fixtures - failures} passed, {failures} failed")
        print(f"{'='*70}")

        return 1 if failures > 0 else 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate LLM prompt outputs against JSON schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all fixtures
  python validate_prompt_outputs.py

  # Fail on undocumented properties
  python validate_prompt_outputs.py --fail-on-extra

  # Validate specific prompt
  python validate_prompt_outputs.py --prompt narrative_analyzer

  # Create golden fixture template
  python validate_prompt_outputs.py --create-template narrative_analyzer > narrative_analyzer_golden.json
        """,
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        default=Path("schemas/prompt_outputs"),
        help="Directory containing JSON schemas (default: schemas/prompt_outputs)",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path("tests/fixtures/prompt_outputs"),
        help="Directory containing test fixtures (default: tests/fixtures/prompt_outputs)",
    )
    parser.add_argument(
        "--fail-on-extra",
        action="store_true",
        help="Fail if fixtures contain properties not in schema (additionalProperties: false)",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Validate only fixtures for this specific prompt",
    )
    parser.add_argument(
        "--create-template",
        type=str,
        metavar="PROMPT",
        help="Create a template fixture for the specified prompt (outputs to stdout)",
    )

    args = parser.parse_args()

    validator = PromptOutputValidator(
        schemas_dir=args.schemas_dir,
        fixtures_dir=args.fixtures_dir,
        fail_on_extra=args.fail_on_extra,
    )

    # Handle template creation mode
    if args.create_template:
        try:
            template = validator.create_template(args.create_template)
            print(json.dumps(template, indent=2))
            return 0
        except Exception as e:
            print(f"[ERROR] Failed to create template: {e}", file=sys.stderr)
            return 1

    # Validate fixtures
    return validator.validate_all(specific_prompt=args.prompt)


if __name__ == "__main__":
    sys.exit(main())
