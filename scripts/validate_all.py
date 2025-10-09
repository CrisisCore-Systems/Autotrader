#!/usr/bin/env python3
"""
Comprehensive security and configuration validation runner.
Runs all validation checks in a single command for pre-commit or CI.

Usage:
    python scripts/validate_all.py
    python scripts/validate_all.py --strict
    python scripts/validate_all.py --category config
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    name: str
    passed: bool
    message: str
    category: str
    severity: str  # error, warning, info


class ValidationRunner:
    """Orchestrates multiple validation checks."""
    
    def __init__(self, strict: bool = False, verbose: bool = True):
        self.strict = strict
        self.verbose = verbose
        self.results: List[ValidationResult] = []
    
    def run_command(
        self,
        cmd: List[str],
        name: str,
        category: str,
        severity: str = "error",
    ) -> ValidationResult:
        """Run a validation command and capture result."""
        if self.verbose:
            print(f"🔍 Running: {name}...", end=" ")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            
            passed = result.returncode == 0
            message = result.stdout if passed else result.stderr
            
            if self.verbose:
                print("✅" if passed else "❌")
            
            return ValidationResult(
                name=name,
                passed=passed,
                message=message.strip()[:500],  # Truncate long messages
                category=category,
                severity=severity,
            )
        
        except FileNotFoundError:
            if self.verbose:
                print("⚠️  (skipped)")
            
            return ValidationResult(
                name=name,
                passed=True,  # Don't fail if tool not installed
                message=f"Tool not found: {cmd[0]}",
                category=category,
                severity="info",
            )
    
    def validate_config_files(self) -> None:
        """Validate configuration files."""
        print("\n📋 Configuration Validation")
        print("=" * 60)
        
        # Alert rules
        result = self.run_command(
            [
                "python",
                "scripts/validate_alert_rules.py",
                "--config",
                "configs/alert_rules.yaml",
            ],
            name="Alert Rules Validation",
            category="config",
            severity="error",
        )
        self.results.append(result)
        
        # Prompt contracts
        result = self.run_command(
            [
                "python",
                "scripts/validate_prompt_contracts.py",
            ],
            name="Prompt Contract Validation",
            category="config",
            severity="error",
        )
        self.results.append(result)
    
    def validate_security(self) -> None:
        """Run security checks."""
        print("\n🔒 Security Validation")
        print("=" * 60)
        
        # Semgrep
        result = self.run_command(
            [
                "semgrep",
                "--config",
                "ci/semgrep.yml",
                "src/",
                "pipeline/",
                "--quiet",
            ],
            name="Semgrep Security Scan",
            category="security",
            severity="error",
        )
        self.results.append(result)
        
        # Bandit (if installed)
        result = self.run_command(
            [
                "bandit",
                "-r",
                "src",
                "pipeline",
                "-ll",
                "-q",
            ],
            name="Bandit Python Security",
            category="security",
            severity="warning",
        )
        self.results.append(result)
    
    def validate_secrets(self) -> None:
        """Check for secrets in code."""
        print("\n🔐 Secret Scanning")
        print("=" * 60)
        
        # Check staged files for secret patterns
        result = self.run_command(
            [
                "git",
                "diff",
                "--cached",
                "--name-only",
            ],
            name="Get Staged Files",
            category="secrets",
            severity="info",
        )
        
        # Simple pattern check
        result = self.run_command(
            [
                "git",
                "diff",
                "--cached",
            ],
            name="Check for Secret Patterns",
            category="secrets",
            severity="error",
        )
        
        # Check for common secret patterns in diff
        if result.passed and any(
            pattern in result.message.lower()
            for pattern in ["api_key", "password", "secret", "token", "0x"]
        ):
            result.passed = False
            result.message = "Possible secret detected in staged changes"
        
        self.results.append(result)
    
    def validate_code_quality(self) -> None:
        """Run code quality checks."""
        print("\n📊 Code Quality")
        print("=" * 60)
        
        # Ruff
        result = self.run_command(
            [
                "ruff",
                "check",
                "src/",
                "--quiet",
            ],
            name="Ruff Linting",
            category="quality",
            severity="warning",
        )
        self.results.append(result)
        
        # MyPy (type checking)
        result = self.run_command(
            [
                "mypy",
                "src/",
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
            name="MyPy Type Checking",
            category="quality",
            severity="warning",
        )
        self.results.append(result)
    
    def validate_dependencies(self) -> None:
        """Check for dependency vulnerabilities."""
        print("\n📦 Dependency Security")
        print("=" * 60)
        
        # pip-audit
        result = self.run_command(
            [
                "pip-audit",
                "-r",
                "requirements.txt",
                "--desc",
            ],
            name="pip-audit Vulnerability Scan",
            category="dependencies",
            severity="error",
        )
        self.results.append(result)
    
    def print_summary(self) -> int:
        """Print validation summary and return exit code."""
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        errors = [r for r in self.results if not r.passed and r.severity == "error"]
        warnings = [r for r in self.results if not r.passed and r.severity == "warning"]
        passed = [r for r in self.results if r.passed]
        
        print(f"✅ Passed:   {len(passed)}")
        print(f"⚠️  Warnings: {len(warnings)}")
        print(f"❌ Errors:   {len(errors)}")
        
        if errors:
            print("\n❌ FAILED CHECKS:")
            for result in errors:
                print(f"  • {result.name}")
                if self.verbose and result.message:
                    print(f"    {result.message[:200]}")
        
        if warnings and (self.strict or self.verbose):
            print("\n⚠️  WARNINGS:")
            for result in warnings:
                print(f"  • {result.name}")
        
        # Exit code
        if errors:
            return 1
        elif warnings and self.strict:
            return 1
        else:
            print("\n✅ All validations passed!")
            return 0
    
    def run_all(self, categories: Optional[List[str]] = None) -> int:
        """Run all validations.
        
        Args:
            categories: Optional list of categories to run (config, security, etc.)
            
        Returns:
            Exit code (0 = success, 1 = failure)
        """
        print("🚀 Running comprehensive validation checks...")
        print("=" * 60)
        
        all_categories = {
            "config": self.validate_config_files,
            "security": self.validate_security,
            "secrets": self.validate_secrets,
            "quality": self.validate_code_quality,
            "dependencies": self.validate_dependencies,
        }
        
        # Run selected categories
        if categories:
            for cat in categories:
                if cat in all_categories:
                    all_categories[cat]()
        else:
            # Run all
            for validator in all_categories.values():
                validator()
        
        return self.print_summary()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run all validation checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_all.py                    # Run all checks
  python scripts/validate_all.py --strict           # Fail on warnings
  python scripts/validate_all.py --category config  # Only config checks
  python scripts/validate_all.py --quiet            # Minimal output
        """,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings (not just errors)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (only summary)",
    )
    parser.add_argument(
        "--category",
        choices=["config", "security", "secrets", "quality", "dependencies"],
        nargs="+",
        help="Run only specific categories",
    )
    
    args = parser.parse_args()
    
    runner = ValidationRunner(
        strict=args.strict,
        verbose=not args.quiet,
    )
    
    return runner.run_all(categories=args.category)


if __name__ == "__main__":
    sys.exit(main())
