#!/usr/bin/env python3
"""
Check that all LLM prompt schemas have corresponding tests and golden fixtures.

This script ensures that:
1. Every JSON schema in schemas/prompt_outputs/ has a Pydantic model
2. Every schema has a golden fixture
3. Every schema has validation tests

Exit codes:
    0: All checks passed
    1: Missing schemas, fixtures, or tests
"""

import sys
from pathlib import Path
from typing import Dict, List, Set

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Directories
SCHEMAS_DIR = PROJECT_ROOT / "schemas" / "prompt_outputs"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "prompt_outputs"
PYDANTIC_FILE = PROJECT_ROOT / "src" / "core" / "llm_schemas.py"
TESTS_FILE = PROJECT_ROOT / "tests" / "test_llm_validation.py"


def find_json_schemas() -> Set[str]:
    """Find all JSON schema files."""
    if not SCHEMAS_DIR.exists():
        return set()
    
    schemas = set()
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        # Remove .schema.json suffix
        name = schema_file.stem.replace(".schema", "")
        schemas.add(name)
    
    return schemas


def find_golden_fixtures() -> Set[str]:
    """Find all golden fixture files."""
    if not FIXTURES_DIR.exists():
        return set()
    
    fixtures = set()
    for fixture_file in FIXTURES_DIR.glob("*_golden.json"):
        # Remove _golden.json suffix
        name = fixture_file.stem.replace("_golden", "")
        fixtures.add(name)
    
    return fixtures


def find_pydantic_models() -> Set[str]:
    """Find all Pydantic response models in llm_schemas.py."""
    if not PYDANTIC_FILE.exists():
        return set()
    
    content = PYDANTIC_FILE.read_text()
    models = set()
    
    # Map schema names to expected Pydantic class names
    # e.g., "narrative_analyzer" -> "NarrativeAnalysisResponse"
    # e.g., "contract_safety" -> "ContractSafetyResponse"
    # e.g., "onchain_activity" -> "OnchainActivityResponse"
    # e.g., "technical_pattern" -> "TechnicalPatternResponse"
    
    expected_classes = {
        "narrative_analyzer": "NarrativeAnalysisResponse",
        "contract_safety": "ContractSafetyResponse",
        "onchain_activity": "OnchainActivityResponse",
        "technical_pattern": "TechnicalPatternResponse",
    }
    
    for schema_name, class_name in expected_classes.items():
        if f"class {class_name}(BaseModel):" in content:
            models.add(schema_name)
    
    return models


def find_test_coverage() -> Set[str]:
    """Find schemas that have tests in test_llm_validation.py."""
    if not TESTS_FILE.exists():
        return set()
    
    content = TESTS_FILE.read_text()
    tested = set()
    
    # Check for test functions or golden fixture tests
    test_mappings = {
        "narrative_analyzer": [
            "test_narrative",
            "NarrativeAnalysisResponse",
            "narrative_analyzer_golden"
        ],
        "contract_safety": [
            "test_contract_safety",
            "ContractSafetyResponse",
            "contract_safety_golden"
        ],
        "onchain_activity": [
            "test_onchain",
            "OnchainActivityResponse",
            "onchain_activity_golden"
        ],
        "technical_pattern": [
            "test_technical",
            "TechnicalPatternResponse",
            "technical_pattern_golden"
        ],
    }
    
    for schema_name, keywords in test_mappings.items():
        if any(keyword in content for keyword in keywords):
            tested.add(schema_name)
    
    return tested


def main() -> int:
    """Run all validation checks."""
    print("🔍 Checking LLM validation coverage...\n")
    
    # Find all components
    schemas = find_json_schemas()
    fixtures = find_golden_fixtures()
    models = find_pydantic_models()
    tests = find_test_coverage()
    
    print(f"Found {len(schemas)} JSON schemas: {sorted(schemas)}")
    print(f"Found {len(fixtures)} golden fixtures: {sorted(fixtures)}")
    print(f"Found {len(models)} Pydantic models: {sorted(models)}")
    print(f"Found {len(tests)} tested schemas: {sorted(tests)}\n")
    
    # Check for missing components
    missing_fixtures = schemas - fixtures
    missing_models = schemas - models
    missing_tests = schemas - tests
    
    all_good = True
    
    if missing_fixtures:
        print(f"❌ Missing golden fixtures for: {sorted(missing_fixtures)}")
        print(f"   Expected in: {FIXTURES_DIR}")
        print(f"   Create: <schema_name>_golden.json\n")
        all_good = False
    
    if missing_models:
        print(f"❌ Missing Pydantic models for: {sorted(missing_models)}")
        print(f"   Expected in: {PYDANTIC_FILE}")
        print(f"   Create: <SchemaName>Response(BaseModel)\n")
        all_good = False
    
    if missing_tests:
        print(f"❌ Missing validation tests for: {sorted(missing_tests)}")
        print(f"   Expected in: {TESTS_FILE}")
        print(f"   Create test functions using validate_llm_response()\n")
        all_good = False
    
    if all_good:
        print("✅ All LLM schemas have complete validation coverage!")
        print("   - JSON schemas defined")
        print("   - Pydantic models exist")
        print("   - Golden fixtures present")
        print("   - Validation tests in place")
        return 0
    else:
        print("\n⚠️  Some schemas are missing required components.")
        print("   Run with --help for guidance on adding new prompts.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
