#!/usr/bin/env python
"""
Generate all auto-generated documentation for MkDocs site.

This script runs all documentation generators in the correct order:
1. CLI reference (from argparse)
2. Metrics documentation (from metrics_registry.yaml)
3. Manpage (for reference section)

Usage:
    python scripts/docs/gen_all_docs.py
"""

import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def run_script(script_path: Path, description: str):
    """Run a documentation generation script."""
    print(f"\n{'='*70}")
    print(f"Running: {description}")
    print(f"{'='*70}")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Failed to run {script_path.name}")
        return False

    print(f"✅ {description} completed")
    return True


def main():
    """Generate all documentation."""
    print("=" * 70)
    print("AutoTrader Documentation Generator")
    print("=" * 70)

    scripts = [
        (
            project_root / "scripts" / "docs" / "gen_cli_docs.py",
            "CLI Reference Documentation",
        ),
        (
            project_root / "scripts" / "docs" / "gen_metrics_docs.py",
            "Metrics Documentation",
        ),
        (
            project_root / "scripts" / "docs" / "gen_manpage.py",
            "Manual Page (Markdown)",
        ),
    ]

    success_count = 0
    fail_count = 0

    for script_path, description in scripts:
        if not script_path.exists():
            print(f"⚠️  Script not found: {script_path}")
            fail_count += 1
            continue

        if run_script(script_path, description):
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 70)
    print("Documentation Generation Complete")
    print("=" * 70)
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print("=" * 70)

    if fail_count > 0:
        return 1

    print("\n🎉 All documentation generated successfully!")
    print(f"\nNext steps:")
    print("  1. Review generated files in docs/")
    print("  2. Run: mkdocs serve")
    print("  3. Visit: http://localhost:8000")

    return 0


if __name__ == "__main__":
    sys.exit(main())
