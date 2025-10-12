#!/usr/bin/env python3
"""
Validate LLM prompt outputs against JSON schemas and golden fixtures.

Usage:
    python scripts/validation/validate_prompt_outputs.py
    python scripts/validation/validate_prompt_outputs.py --fail-on-extra
    python scripts/validation/validate_prompt_outputs.py --prompt narrative_analyzer
    python scripts/validation/validate_prompt_outputs.py --create-template narrative_analyzer
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

project_root = Path(__file__).resolve().parents[2]


class PromptOutputValidator:
    """Validates LLM prompt outputs against JSON schemas."""

    def __init__(self, schemas_dir: Path, fixtures_dir: Path, fail_on_extra: bool = False):
        self.schemas_dir = schemas_dir
        self.fixtures_dir = fixtures_dir
        self.fail_on_extra = fail_on_extra
        self.schema_cache: Dict[str, Dict[str, Any]] = {}

    def load_json(self, path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Invalid JSON in {path}: {exc}", file=sys.stderr)
            raise
        except Exception as exc:
            print(f"[ERROR] Failed to read {path}: {exc}", file=sys.stderr)
            raise

    def load_schema(self, prompt_name: str) -> Dict[str, Any]:
        if prompt_name in self.schema_cache:
            return self.schema_cache[prompt_name]

        schema_path = self.schemas_dir / f"{prompt_name}.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        schema = self.load_json(schema_path)

        if self.fail_on_extra and "additionalProperties" not in schema:
            schema["additionalProperties"] = False

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            print(f"[ERROR] Invalid schema {schema_path}: {exc}", file=sys.stderr)
            raise

        self.schema_cache[prompt_name] = schema
        return schema

    def validate_fixture(self, prompt_name: str, fixture_path: Path) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        try:
            schema = self.load_schema(prompt_name)
        except Exception as exc:
            return False, [f"Failed to load schema: {exc}"]

        try:
            data = self.load_json(fixture_path)
        except Exception as exc:
            return False, [f"Failed to load fixture: {exc}"]

        if "schema_version" not in data:
            errors.append("Missing required field: schema_version")

        validator = Draft202012Validator(schema)
        validation_errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))

        for error in validation_errors:
            path = " -> ".join(str(part) for part in error.path) or "(root)"
            errors.append(f"{path}: {error.message}")

        return len(errors) == 0, errors

    def create_template(self, prompt_name: str) -> Dict[str, Any]:
        schema = self.load_schema(prompt_name)

        if schema.get("examples"):
            return schema["examples"][0]

        template: Dict[str, Any] = {}
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            prop = properties.get(field, {})
            prop_type = prop.get("type", "string")

            if prop_type == "string":
                if "enum" in prop:
                    template[field] = prop["enum"][0]
                elif field == "schema_version":
                    template[field] = "v1.0.0"
                else:
                    template[field] = ""
            elif prop_type == "number":
                template[field] = prop.get("default", 0.0)
            elif prop_type == "boolean":
                template[field] = prop.get("default", False)
            elif prop_type == "array":
                template[field] = []
            elif prop_type == "object":
                template[field] = {}

        return template

    def validate_all(self, specific_prompt: str | None = None) -> int:
        if not self.schemas_dir.exists():
            print(f"[ERROR] Schemas directory not found: {self.schemas_dir}", file=sys.stderr)
            return 1

        if not self.fixtures_dir.exists():
            print(f"[ERROR] Fixtures directory not found: {self.fixtures_dir}", file=sys.stderr)
            return 1

        schema_files = list(self.schemas_dir.glob("*.schema.json"))
        if not schema_files:
            print(f"[ERROR] No schemas found in {self.schemas_dir}", file=sys.stderr)
            return 1

        schema_index = {s.stem.replace(".schema", ""): s for s in schema_files}
        print(
            f"[INFO] Found {len(schema_index)} schemas: {', '.join(sorted(schema_index.keys()))}"
        )

        fixture_files = list(self.fixtures_dir.glob("*.json"))
        if not fixture_files:
            print(f"[WARN] No fixtures found in {self.fixtures_dir}")
            return 0

        total_fixtures = 0
        failures = 0

        for fixture in sorted(fixture_files):
            name = fixture.stem.replace("_golden", "").replace("_test", "")

            if specific_prompt and name != specific_prompt:
                continue

            if name not in schema_index:
                print(
                    f"[WARN] No schema for fixture {fixture.name} (expected {name}.schema.json)"
                )
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

        print(f"\n{'=' * 70}")
        print(
            f"Validated {total_fixtures} fixtures: {total_fixtures - failures} passed, {failures} failed"
        )
        print(f"{'=' * 70}")

        return 1 if failures > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate LLM prompt outputs against JSON schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/validation/validate_prompt_outputs.py\n"
            "  python scripts/validation/validate_prompt_outputs.py --fail-on-extra\n"
            "  python scripts/validation/validate_prompt_outputs.py --prompt narrative_analyzer\n"
            "  python scripts/validation/validate_prompt_outputs.py --create-template narrative_analyzer\n"
        ),
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
        help="Directory containing test fixtures",
    )
    parser.add_argument(
        "--fail-on-extra",
        action="store_true",
        help="Fail if fixtures contain properties not in schema",
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

    if args.create_template:
        try:
            template = validator.create_template(args.create_template)
            print(json.dumps(template, indent=2))
            return 0
        except Exception as exc:
            print(f"[ERROR] Failed to create template: {exc}", file=sys.stderr)
            return 1

    return validator.validate_all(specific_prompt=args.prompt)


if __name__ == "__main__":
    sys.exit(main())
