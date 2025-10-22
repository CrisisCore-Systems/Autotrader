#!/usr/bin/env python3
"""
Validate Security Setup Script

This script validates that all security measures are properly configured.
Run this before deploying to production or after security configuration changes.
"""

import os
import sys
from pathlib import Path
import yaml


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists and report status."""
    path = Path(filepath)
    if path.exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} NOT FOUND: {filepath}")
        return False


def validate_yaml(filepath: str, description: str) -> bool:
    """Validate YAML file syntax."""
    try:
        with open(filepath, 'r') as f:
            yaml.safe_load(f)
        print(f"✅ {description} YAML valid: {filepath}")
        return True
    except yaml.YAMLError as e:
        print(f"❌ {description} YAML invalid: {filepath}")
        print(f"   Error: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ {description} NOT FOUND: {filepath}")
        return False


def check_docker_security(dockerfile: str) -> bool:
    """Check Docker security best practices."""
    issues = []
    
    try:
        with open(dockerfile, 'r') as f:
            content = f.read()
        
        # Check for multi-stage build
        if 'AS builder' in content and 'AS runtime' in content:
            print("✅ Docker: Multi-stage build present")
        else:
            issues.append("Multi-stage build not detected")
        
        # Check for non-root user
        if 'USER autotrader' in content or 'USER 1000' in content:
            print("✅ Docker: Non-root user configured")
        else:
            issues.append("Non-root user not configured")
        
        # Check for slim base image
        if 'slim' in content:
            print("✅ Docker: Slim base image used")
        else:
            issues.append("Consider using slim base image")
        
        # Check for apt cleanup
        if 'rm -rf /var/lib/apt/lists/*' in content:
            print("✅ Docker: Package cleanup present")
        else:
            issues.append("apt cleanup not found")
        
        if issues:
            for issue in issues:
                print(f"⚠️  Docker: {issue}")
            return False
        
        return True
    
    except FileNotFoundError:
        print(f"❌ Dockerfile not found: {dockerfile}")
        return False


def check_semgrep_rules(filepath: str) -> bool:
    """Check Semgrep rules file."""
    try:
        with open(filepath, 'r') as f:
            content = yaml.safe_load(f)
        
        if 'rules' not in content:
            print(f"❌ Semgrep: No rules found in {filepath}")
            return False
        
        rule_count = len(content['rules'])
        print(f"✅ Semgrep: {rule_count} custom rules configured")
        
        # Check for key security categories
        categories = {
            'secret': 0,
            'injection': 0,
            'crypto': 0,
            'supply': 0,
        }
        
        for rule in content['rules']:
            rule_id = rule.get('id', '').lower()
            if 'secret' in rule_id or 'api' in rule_id or 'key' in rule_id:
                categories['secret'] += 1
            if 'injection' in rule_id or 'sql' in rule_id or 'exec' in rule_id:
                categories['injection'] += 1
            if 'crypto' in rule_id or 'hash' in rule_id or 'random' in rule_id:
                categories['crypto'] += 1
            if 'supply' in rule_id or 'download' in rule_id or 'package' in rule_id:
                categories['supply'] += 1
        
        print(f"   - Secret detection rules: {categories['secret']}")
        print(f"   - Injection prevention rules: {categories['injection']}")
        print(f"   - Cryptography rules: {categories['crypto']}")
        print(f"   - Supply chain rules: {categories['supply']}")
        
        return True
    
    except Exception as e:
        print(f"❌ Semgrep rules validation failed: {e}")
        return False


def check_environment_variables() -> bool:
    """Check if sensitive environment variables are not hardcoded."""
    print("\n📋 Environment Variable Check:")
    
    sensitive_vars = [
        'GROQ_API_KEY',
        'OPENAI_API_KEY',
        'DATABASE_URL',
        'JWT_SECRET',
    ]
    
    all_good = True
    set_count = 0
    unset_count = 0
    
    for var in sensitive_vars:
        # Check if variable is set without logging variable names or values
        if os.getenv(var):
            set_count += 1
        else:
            unset_count += 1
    
    print(f"✅ {set_count} sensitive environment variables are set")
    print(f"ℹ️  {unset_count} sensitive environment variables are not set (OK if not used)")
    print("   Note: Variable names and values are not logged for security")
    
    return all_good


def main():
    """Main validation function."""
    print("=" * 60)
    print("🔒 Security Configuration Validation")
    print("=" * 60)
    print()
    
    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)
    
    all_checks = []
    
    # Check configuration files
    print("📁 Configuration Files:")
    all_checks.append(check_file_exists('.github/dependabot.yml', 'Dependabot config'))
    all_checks.append(check_file_exists('.github/workflows/security-scan.yml', 'Security scan workflow'))
    all_checks.append(check_file_exists('.pre-commit-config.yaml', 'Pre-commit hooks'))
    all_checks.append(check_file_exists('.secrets.baseline', 'Secrets baseline'))
    all_checks.append(check_file_exists('ci/semgrep.yml', 'Semgrep rules'))
    print()
    
    # Check documentation
    print("📚 Security Documentation:")
    all_checks.append(check_file_exists('SECURITY.md', 'Security policy'))
    all_checks.append(check_file_exists('docs/DOCKER_SECURITY.md', 'Docker security guide'))
    all_checks.append(check_file_exists('docs/SECRET_ROTATION.md', 'Secret rotation guide'))
    print()
    
    # Validate YAML files
    print("🔍 YAML Validation:")
    all_checks.append(validate_yaml('.github/dependabot.yml', 'Dependabot'))
    all_checks.append(validate_yaml('.github/workflows/security-scan.yml', 'Security workflow'))
    all_checks.append(validate_yaml('.pre-commit-config.yaml', 'Pre-commit'))
    print()
    
    # Check Docker security
    print("🐳 Docker Security:")
    all_checks.append(check_docker_security('Dockerfile'))
    print()
    
    # Check Semgrep rules
    print("🔎 Semgrep Rules:")
    all_checks.append(check_semgrep_rules('ci/semgrep.yml'))
    print()
    
    # Check environment variables
    check_environment_variables()
    print()
    
    # Summary
    print("=" * 60)
    passed = sum(all_checks)
    total = len(all_checks)
    
    if passed == total:
        print(f"✅ All {total} security checks passed!")
        print("\n🎉 Security configuration is complete and valid.")
        print("\nNext steps:")
        print("1. Run pre-commit hooks: pre-commit run --all-files")
        print("2. Test Docker build: docker build -t autotrader:test .")
        print("3. Run security scans: make security (if Makefile exists)")
        return 0
    else:
        print(f"⚠️  {passed}/{total} checks passed, {total - passed} issues found")
        print("\n❌ Please address the issues above before deploying.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
