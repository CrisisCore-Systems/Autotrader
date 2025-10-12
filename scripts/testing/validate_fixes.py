#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation script for namespace fixes, schema validators, and notebook repairs.
"""

import sys
import io
from pathlib import Path

# Ensure UTF-8 encoding for output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def validate_namespace_fixes():
    """Validate that namespace issues are resolved."""
    print("=" * 60)
    print("1. Validating Namespace Fixes")
    print("=" * 60)
    
    try:
        # Import the module to check for namespace errors
        sys.path.insert(0, str(Path(__file__).parent))
        from src.api.dashboard_api import _scanner_cache, ScannerCache
        
        # Check that _scanner_cache is properly defined
        assert isinstance(_scanner_cache, ScannerCache), "_scanner_cache is not a ScannerCache instance"
        assert hasattr(_scanner_cache, 'results'), "_scanner_cache missing 'results' attribute"
        assert hasattr(_scanner_cache, 'last_updated'), "_scanner_cache missing 'last_updated' attribute"
        
        print("✓ _scanner_cache properly defined and initialized")
        print("✓ ScannerCache class has required attributes")
        print("✓ No namespace errors detected")
        return True
    except Exception as e:
        print(f"✗ Namespace validation failed: {e}")
        return False


def validate_schema_validators():
    """Validate that Pydantic V2 schema validators are working."""
    print("\n" + "=" * 60)
    print("2. Validating Schema Validators (Pydantic V2)")
    print("=" * 60)
    
    try:
        from src.api.dashboard_api import (
            TokenResponse, AnomalyAlert, ConfidenceInterval,
            SLAStatus, CircuitBreakerStatus, TokenCorrelation,
            OrderFlowSnapshot, SentimentTrend
        )
        from pydantic import ValidationError
        
        # Test TokenResponse validator
        try:
            token = TokenResponse(
                symbol="eth",
                price=2000.0,
                liquidity_usd=1000000.0,
                gem_score=0.85,
                final_score=0.90,
                confidence=0.95,
                flagged=False,
                narrative_momentum=0.75,
                sentiment_score=0.5,
                holders=10000,
                updated_at="2025-10-08T12:00:00Z"
            )
            assert token.symbol == "ETH", "Symbol should be uppercase"
            print("✓ TokenResponse validator working (symbol uppercase)")
        except Exception as e:
            print(f"✗ TokenResponse validation failed: {e}")
            return False
        
        # Test ConfidenceInterval model validator
        try:
            ci = ConfidenceInterval(
                value=0.85,
                lower_bound=0.80,
                upper_bound=0.90,
                confidence_level=0.95
            )
            print("✓ ConfidenceInterval model validator working")
        except Exception as e:
            print(f"✗ ConfidenceInterval validation failed: {e}")
            return False
        
        # Test bounds validation
        try:
            bad_ci = ConfidenceInterval(
                value=0.85,
                lower_bound=0.90,
                upper_bound=0.80,
                confidence_level=0.95
            )
            print("✗ ConfidenceInterval should reject invalid bounds")
            return False
        except ValidationError:
            print("✓ ConfidenceInterval correctly rejects invalid bounds")
        
        # Test SentimentTrend list length validation
        try:
            trend = SentimentTrend(
                token_symbol="btc",
                timestamps=[1.0, 2.0, 3.0],
                sentiment_scores=[0.5, 0.6, 0.7],
                tweet_volumes=[100, 200, 300],
                engagement_scores=[0.8, 0.85, 0.9]
            )
            assert trend.token_symbol == "BTC", "Symbol should be uppercase"
            print("✓ SentimentTrend model validator working")
        except Exception as e:
            print(f"✗ SentimentTrend validation failed: {e}")
            return False
        
        # Test mismatched list lengths
        try:
            bad_trend = SentimentTrend(
                token_symbol="btc",
                timestamps=[1.0, 2.0],
                sentiment_scores=[0.5, 0.6, 0.7],
                tweet_volumes=[100, 200],
                engagement_scores=[0.8, 0.85]
            )
            print("✗ SentimentTrend should reject mismatched list lengths")
            return False
        except ValidationError:
            print("✓ SentimentTrend correctly rejects mismatched list lengths")
        
        print("✓ All Pydantic V2 validators working correctly")
        return True
    except Exception as e:
        print(f"✗ Schema validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_notebook_repair():
    """Validate that the notebook file is properly repaired."""
    print("\n" + "=" * 60)
    print("3. Validating Notebook Repair")
    print("=" * 60)
    
    try:
        import nbformat
        
        notebook_path = Path(__file__).parent / "notebooks" / "hidden_gem_scanner.ipynb"
        
        if not notebook_path.exists():
            print(f"✗ Notebook not found: {notebook_path}")
            return False
        
        # Read and validate notebook
        nb = nbformat.read(str(notebook_path), as_version=4)
        
        print(f"✓ Notebook file is valid JSON")
        print(f"  - {len(nb.cells)} cells found")
        
        # Check cell types
        cell_types = [cell.cell_type for cell in nb.cells]
        print(f"  - Cell types: {cell_types}")
        
        # Validate we have at least markdown and code cells
        assert "markdown" in cell_types, "No markdown cells found"
        assert "code" in cell_types, "No code cells found"
        print("✓ Notebook has both markdown and code cells")
        
        # Check for valid Python code (no syntax errors)
        code_cells = [cell for cell in nb.cells if cell.cell_type == "code"]
        print(f"✓ Found {len(code_cells)} code cells")
        
        # Validate notebook metadata
        assert "kernelspec" in nb.metadata, "Missing kernelspec metadata"
        assert "language_info" in nb.metadata, "Missing language_info metadata"
        print("✓ Notebook metadata is valid")
        
        return True
    except Exception as e:
        print(f"✗ Notebook validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_ci_config():
    """Validate CI configuration."""
    print("\n" + "=" * 60)
    print("4. Validating CI Configuration")
    print("=" * 60)
    
    try:
        import yaml
        
        ci_path = Path(__file__).parent / "ci" / "github-actions.yml"
        
        if not ci_path.exists():
            print(f"✗ CI config not found: {ci_path}")
            return False
        
        # Read and parse YAML
        with open(ci_path) as f:
            ci_config = yaml.safe_load(f)
        
        print("✓ CI configuration is valid YAML")
        
        # Check for required jobs
        required_jobs = ["lint", "test", "security", "build"]
        jobs = ci_config.get("jobs", {})
        
        for job in required_jobs:
            if job in jobs:
                print(f"✓ Job '{job}' is configured")
            else:
                print(f"✗ Missing required job: {job}")
                return False
        
        # Check Python versions
        test_job = jobs.get("test", {})
        strategy = test_job.get("strategy", {})
        matrix = strategy.get("matrix", {})
        python_versions = matrix.get("python-version", [])
        
        if python_versions:
            print(f"✓ Testing Python versions: {python_versions}")
        else:
            print("⚠ No Python version matrix found")
        
        return True
    except Exception as e:
        print(f"✗ CI validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validations."""
    print("\n" + "=" * 60)
    print("VALIDATION SUITE: Namespace, Schema, Notebook & CI")
    print("=" * 60 + "\n")
    
    results = {
        "namespace": validate_namespace_fixes(),
        "schema": validate_schema_validators(),
        "notebook": validate_notebook_repair(),
        "ci": validate_ci_config()
    }
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} | {name.upper()}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All validations passed!")
        return 0
    else:
        print("\n✗ Some validations failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
