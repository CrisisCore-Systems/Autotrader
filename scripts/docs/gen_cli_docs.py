#!/usr/bin/env python
"""
Generate CLI reference documentation from argparse parser.

This script reuses the manpage generator's extraction logic to create
Markdown documentation for the MkDocs site.

Usage:
    python scripts/docs/gen_cli_docs.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.cli.manpage import ManpageGenerator


def create_cli_parser():
    """Import actual CLI parser from manpage script."""
    # Reuse the parser definition from gen_manpage.py
    from scripts.docs.gen_manpage import create_cli_parser

    return create_cli_parser()


def generate_options_md():
    """Generate CLI options documentation."""
    parser = create_cli_parser()
    generator = ManpageGenerator(parser=parser)

    # Get options section from markdown generation
    lines = [
        "# Command-Line Options",
        "",
        "Complete reference for all `autotrader-scan` command-line options.",
        "",
        "!!! tip \"Auto-Generated\"",
        "    This page is automatically generated from the CLI parser definition.",
        "    Last updated: " + generator.date,
        "",
    ]

    lines.extend(generator._generate_markdown_options())

    return "\n".join(lines)


def generate_exit_codes_md():
    """Generate exit codes documentation."""
    parser = create_cli_parser()
    generator = ManpageGenerator(parser=parser)

    lines = [
        "# Exit Codes",
        "",
        "AutoTrader CLI uses specific exit codes to indicate different failure modes.",
        "This helps with scripting and automation.",
        "",
        "## Exit Code Reference",
        "",
    ]

    lines.extend(generator._generate_markdown_exit_codes())

    lines.extend([
        "",
        "## Using Exit Codes in Scripts",
        "",
        "### Bash Example",
        "",
        "```bash",
        "autotrader-scan --config production.yaml",
        "EXIT_CODE=$?",
        "",
        "if [ $EXIT_CODE -eq 0 ]; then",
        "    echo \"Scan completed successfully\"",
        "elif [ $EXIT_CODE -eq 1 ]; then",
        "    echo \"Configuration error - check your config file\"",
        "elif [ $EXIT_CODE -eq 21 ]; then",
        "    echo \"Another scan is running - please wait\"",
        "else",
        "    echo \"Scan failed with exit code $EXIT_CODE\"",
        "fi",
        "```",
        "",
        "### PowerShell Example",
        "",
        "```powershell",
        "autotrader-scan --config production.yaml",
        "$exitCode = $LASTEXITCODE",
        "",
        "switch ($exitCode) {",
        "    0  { Write-Host \"Scan completed successfully\" }",
        "    1  { Write-Host \"Configuration error - check your config file\" }",
        "    21 { Write-Host \"Another scan is running - please wait\" }",
        "    default { Write-Host \"Scan failed with exit code $exitCode\" }",
        "}",
        "```",
        "",
        "## Deprecation Notice",
        "",
        "Some exit code names have been deprecated in v2.0.0 and will be removed in v3.0.0:",
        "",
        "| Deprecated | New Name | Removal Version |",
        "|------------|----------|----------------|",
        "| `SUCCESS` | `OK` | v3.0.0 |",
        "| `CONFIG_ERROR` | `CONFIG` | v3.0.0 |",
        "| `MISUSE` | `INPUT` | v3.0.0 |",
        "| `RUNTIME_ERROR` | `RUNTIME` | v3.0.0 |",
        "| `LOCK_ERROR` | `LOCKED` | v3.0.0 |",
        "| `SIGINT` | `INTERRUPTED` | v3.0.0 |",
        "",
        "Use `--print-deprecation-warnings` to see which deprecated names you're using.",
    ])

    return "\n".join(lines)


def generate_environment_md():
    """Generate environment variables documentation."""
    parser = create_cli_parser()
    generator = ManpageGenerator(parser=parser)

    lines = [
        "# Environment Variables",
        "",
        "AutoTrader CLI can be configured using environment variables.",
        "These variables are prefixed with `AUTOTRADER_`.",
        "",
        "## Configuration Precedence",
        "",
        "Settings are applied in the following order (later values override earlier):",
        "",
        "1. **Defaults** - Built-in default values",
        "2. **Config file** - Values from `config.yaml`",
        "3. **Environment variables** - `AUTOTRADER_*` variables",
        "4. **Command-line flags** - Explicit CLI arguments",
        "",
        "Use `--print-effective-config` to see the final merged configuration.",
        "",
        "## Available Variables",
        "",
    ]

    lines.extend(generator._generate_markdown_environment())

    lines.extend([
        "",
        "## Nested Configuration",
        "",
        "For nested configuration keys, use double underscores (`__`):",
        "",
        "```bash",
        "# Set nested value: data.provider = \"yahoo\"",
        "export AUTOTRADER_DATA__PROVIDER=yahoo",
        "",
        "# Set nested value: metrics.port = 9091",
        "export AUTOTRADER_METRICS__PORT=9091",
        "```",
        "",
        "## Boolean Values",
        "",
        "Boolean environment variables accept:",
        "",
        "- **True**: `1`, `true`, `yes`, `on` (case-insensitive)",
        "- **False**: `0`, `false`, `no`, `off` (case-insensitive)",
        "",
        "```bash",
        "export AUTOTRADER_DETERMINISTIC=true",
        "export AUTOTRADER_DETERMINISTIC=1",
        "export AUTOTRADER_DETERMINISTIC=yes",
        "```",
        "",
        "## Examples",
        "",
        "### Development Configuration",
        "",
        "```bash",
        "export AUTOTRADER_LOG_LEVEL=DEBUG",
        "export AUTOTRADER_METRICS_PORT=9091",
        "export AUTOTRADER_DATA_DIR=./cache",
        "autotrader-scan",
        "```",
        "",
        "### Production Configuration",
        "",
        "```bash",
        "export AUTOTRADER_CONFIG=/etc/autotrader/production.yaml",
        "export AUTOTRADER_LOG_LEVEL=WARNING",
        "export AUTOTRADER_LOG_FILE=/var/log/autotrader.log",
        "export AUTOTRADER_LOCK_TTL=1800",
        "autotrader-scan",
        "```",
        "",
        "### CI/CD Configuration",
        "",
        "```bash",
        "export AUTOTRADER_DETERMINISTIC=true",
        "export AUTOTRADER_RANDOM_SEED=42",
        "export AUTOTRADER_ENABLE_REPRO_STAMP=true",
        "export AUTOTRADER_NO_LOCK=true  # Allow parallel CI builds",
        "autotrader-scan --output results.json",
        "```",
    ])

    return "\n".join(lines)


def generate_examples_md():
    """Generate CLI examples documentation."""
    parser = create_cli_parser()
    generator = ManpageGenerator(parser=parser)

    lines = [
        "# CLI Examples",
        "",
        "Practical examples of using the AutoTrader CLI.",
        "",
        "## Basic Usage",
        "",
    ]

    lines.extend(generator._generate_markdown_examples())

    lines.extend([
        "",
        "## Advanced Examples",
        "",
        "### Reproducible Scan with Stamp",
        "",
        "```bash",
        "autotrader-scan \\",
        "    --enable-repro-stamp \\",
        "    --deterministic \\",
        "    --random-seed 42 \\",
        "    --output results.json",
        "```",
        "",
        "The output will include a `repro_stamp` field:",
        "",
        "```json",
        "{",
        '  "repro_stamp": {',
        '    "timestamp": "2025-10-08T12:00:00Z",',
        '    "git_commit": "abc123...",',
        '    "git_branch": "main",',
        '    "config_hash": "def456...",',
        '    "input_hashes": {"data.csv": "789abc..."},',
        '    "random_seed": 42',
        "  }",
        "}",
        "```",
        "",
        "### Validate Configuration Before Scan",
        "",
        "```bash",
        "# Check effective configuration",
        "autotrader-scan --print-effective-config",
        "",
        "# Then run actual scan",
        "autotrader-scan",
        "```",
        "",
        "### Production Scan with Monitoring",
        "",
        "```bash",
        "autotrader-scan \\",
        "    --config /etc/autotrader/production.yaml \\",
        "    --lock-ttl 1800 \\",
        "    --log-file /var/log/autotrader.log \\",
        "    --metrics-port 9090 \\",
        "    --enable-tracing \\",
        "    --output /var/lib/autotrader/results.json",
        "```",
        "",
        "### Custom Strategy with Parameters",
        "",
        "```bash",
        "autotrader-scan \\",
        "    --strategy my_strategy \\",
        "    --strategy-params '{\"threshold\": 0.8, \"lookback\": 30}' \\",
        "    --output custom-results.json",
        "```",
        "",
        "### Debugging Configuration Issues",
        "",
        "```bash",
        "# See all deprecation warnings",
        "autotrader-scan --print-deprecation-warnings",
        "",
        "# See effective configuration with origins",
        "autotrader-scan --print-effective-config --man-format md > config-debug.md",
        "",
        "# Validate schema",
        "autotrader-scan --validate-schema --schema-version 1.0.0",
        "```",
        "",
        "## Scripting Patterns",
        "",
        "### Retry on Lock Failure",
        "",
        "```bash",
        "#!/bin/bash",
        "MAX_RETRIES=3",
        "RETRY_DELAY=60",
        "",
        "for i in $(seq 1 $MAX_RETRIES); do",
        "    autotrader-scan",
        "    EXIT_CODE=$?",
        "    ",
        "    if [ $EXIT_CODE -eq 0 ]; then",
        "        echo \"Scan completed successfully\"",
        "        exit 0",
        "    elif [ $EXIT_CODE -eq 21 ]; then",
        "        echo \"Lock held, retrying in ${RETRY_DELAY}s (attempt $i/$MAX_RETRIES)\"",
        "        sleep $RETRY_DELAY",
        "    else",
        "        echo \"Scan failed with exit code $EXIT_CODE\"",
        "        exit $EXIT_CODE",
        "    fi",
        "done",
        "",
        "echo \"Failed after $MAX_RETRIES attempts\"",
        "exit 21",
        "```",
        "",
        "### Parallel Scans with Different Configs",
        "",
        "```bash",
        "#!/bin/bash",
        "# Run multiple scans in parallel with different strategies",
        "",
        "autotrader-scan --strategy momentum --output momentum.json --no-lock &",
        "autotrader-scan --strategy mean_reversion --output mean_reversion.json --no-lock &",
        "autotrader-scan --strategy breakout --output breakout.json --no-lock &",
        "",
        "wait  # Wait for all scans to complete",
        "echo \"All scans completed\"",
        "```",
        "",
        "!!! warning \"Lock Disabled\"",
        "    The `--no-lock` flag disables concurrency control. Only use this when",
        "    you're certain the scans won't interfere with each other.",
    ])

    return "\n".join(lines)


def main():
    """Generate all CLI documentation."""
    docs_dir = project_root / "docs" / "cli"
    docs_dir.mkdir(parents=True, exist_ok=True)

    print("Generating CLI documentation...")

    # Generate options
    print("  - options.md")
    (docs_dir / "options.md").write_text(generate_options_md(), encoding="utf-8")

    # Generate exit codes
    print("  - exit-codes.md")
    (docs_dir / "exit-codes.md").write_text(generate_exit_codes_md(), encoding="utf-8")

    # Generate environment variables
    print("  - environment.md")
    (docs_dir / "environment.md").write_text(
        generate_environment_md(),
        encoding="utf-8",
    )

    # Generate examples
    print("  - examples.md")
    (docs_dir / "examples.md").write_text(generate_examples_md(), encoding="utf-8")

    print(f"\n✅ CLI documentation generated in: {docs_dir}")


if __name__ == "__main__":
    main()
