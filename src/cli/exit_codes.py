"""Exit code definitions and documentation for CLI.

Standard exit codes following Unix conventions and best practices.
"""

from __future__ import annotations

import warnings
from enum import IntEnum, EnumMeta
from typing import Any


# Deprecation timeline for backward compatibility aliases
# - v2.0.0 (Current): Deprecation warnings added
# - v2.2.0 (Est. Q1 2026): Warnings become errors
# - v3.0.0 (Est. Q2 2026): Aliases removed entirely
_DEPRECATION_VERSION = "2.0.0"
_REMOVAL_VERSION = "3.0.0"
_DEPRECATED_ALIASES = {
    "SUCCESS": "OK",
    "CONFIG_ERROR": "CONFIG",
    "MISUSE": "INPUT",
    "RUNTIME_ERROR": "RUNTIME",
    "LOCK_ERROR": "LOCKED",
    "SIGINT": "INTERRUPTED",
}


class _ExitCodeMeta(EnumMeta):
    """Metaclass to emit deprecation warnings for old exit code aliases."""
    
    def __getattribute__(cls, name: str):
        """Intercept attribute access to warn about deprecated aliases."""
        # Get the actual value first
        value = super().__getattribute__(name)
        
        # Check if this is a deprecated alias
        if name in _DEPRECATED_ALIASES:
            new_name = _DEPRECATED_ALIASES[name]
            warnings.warn(
                f"ExitCode.{name} is deprecated and will be removed in v{_REMOVAL_VERSION}. "
                f"Use ExitCode.{new_name} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        
        return value


class ExitCode(IntEnum, metaclass=_ExitCodeMeta):
    """Simplified exit codes for AutoTrader CLI.
    
    Canonical categories following Unix conventions:
    - 0: Success (OK)
    - 1: Configuration errors
    - 2: Input/argument errors  
    - 10: Runtime errors
    - 20: Timeout errors
    - 21: Lock acquisition errors
    - 30: Validation errors (output/schema)
    - 130: Interrupted by user (Ctrl+C)
    
    Deprecated Aliases (will be removed in v3.0.0):
    - SUCCESS → OK
    - CONFIG_ERROR → CONFIG
    - MISUSE → INPUT
    - RUNTIME_ERROR → RUNTIME
    - LOCK_ERROR → LOCKED
    - SIGINT → INTERRUPTED
    """
    
    # Success
    OK = 0
    SUCCESS = 0  # DEPRECATED: Use OK instead (removal: v3.0.0)
    
    # Configuration errors (files, settings)
    CONFIG = 1
    CONFIG_ERROR = 1  # DEPRECATED: Use CONFIG instead (removal: v3.0.0)
    
    # Input errors (CLI arguments, data format)
    INPUT = 2
    MISUSE = 2  # DEPRECATED: Use INPUT instead (removal: v3.0.0)
    
    # Runtime errors (execution failures, API errors, strategy errors)
    RUNTIME = 10
    RUNTIME_ERROR = 10  # DEPRECATED: Use RUNTIME instead (removal: v3.0.0)
    
    # Timeout errors (operation took too long)
    TIMEOUT = 20
    
    # Lock errors (concurrent execution prevention)
    LOCKED = 21
    LOCK_ERROR = 21  # DEPRECATED: Use LOCKED instead (removal: v3.0.0)
    
    # Validation errors (output validation, schema checks)
    VALIDATION = 30
    
    # Interrupted (Ctrl+C, SIGINT)
    INTERRUPTED = 130
    SIGINT = 130  # DEPRECATED: Use INTERRUPTED instead (removal: v3.0.0)
    
    def __str__(self) -> str:
        """Get string representation."""
        return f"{self.name} ({self.value})"


# Exit code descriptions
EXIT_CODE_DESCRIPTIONS = {
    ExitCode.OK: "Success - operation completed successfully",
    ExitCode.CONFIG: "Configuration error - invalid config file or settings",
    ExitCode.INPUT: "Input error - invalid command-line arguments or data format",
    ExitCode.RUNTIME: "Runtime error - execution failure, API error, or strategy error",
    ExitCode.TIMEOUT: "Timeout - operation exceeded time limit",
    ExitCode.LOCKED: "Lock error - another instance is running or lock acquisition failed",
    ExitCode.VALIDATION: "Validation error - output failed schema or format validation",
    ExitCode.INTERRUPTED: "Interrupted - user cancelled operation (Ctrl+C)",
}


# Exit code categories
EXIT_CODE_CATEGORIES = {
    "Success": [ExitCode.OK],
    "Configuration": [ExitCode.CONFIG],
    "Input/Arguments": [ExitCode.INPUT],
    "Runtime": [ExitCode.RUNTIME],
    "Timeout": [ExitCode.TIMEOUT],
    "Concurrency/Lock": [ExitCode.LOCKED],
    "Validation": [ExitCode.VALIDATION],
    "Interrupted": [ExitCode.INTERRUPTED],
}


def print_exit_codes() -> None:
    """Print all exit codes in a formatted table."""
    print("\n" + "=" * 80)
    print("AUTOTRADER CLI EXIT CODES (Simplified)")
    print("=" * 80)
    print("""
8 Canonical Exit Code Categories:
    0  - OK         : Success
    1  - CONFIG     : Configuration errors
    2  - INPUT      : Invalid arguments or data
    10 - RUNTIME    : Execution failures (API, strategy, etc.)
    20 - TIMEOUT    : Operation exceeded time limit
    21 - LOCKED     : Lock acquisition failed
    30 - VALIDATION : Output/schema validation failed
    130- INTERRUPTED: User cancelled (Ctrl+C)
    """)
    
    for category, codes in EXIT_CODE_CATEGORIES.items():
        print(f"\n{category}:")
        print("-" * 80)
        for code in codes:
            description = EXIT_CODE_DESCRIPTIONS.get(code, "No description")
            print(f"  {code.value:3d} | {code.name:30s} | {description}")
    
    print("\n" + "=" * 80)
    print("USAGE IN SCRIPTS:")
    print("=" * 80)
    print("""
Check exit codes in shell scripts:

Bash/Zsh:
    autotrader-scan --config config.yaml
    case $? in
        0) echo "Success" ;;
        1) echo "Configuration error" ;;
        2) echo "Invalid input" ;;
        10) echo "Runtime error" ;;
        20) echo "Timeout" ;;
        21) echo "Lock error" ;;
        30) echo "Validation error" ;;
        130) echo "Interrupted" ;;
    esac

PowerShell:
    autotrader-scan --config config.yaml
    switch ($LASTEXITCODE) {
        0   { Write-Host "Success" }
        1   { Write-Host "Configuration error" }
        2   { Write-Host "Invalid input" }
        10  { Write-Host "Runtime error" }
        20  { Write-Host "Timeout" }
        21  { Write-Host "Lock error" }
        30  { Write-Host "Validation error" }
        130 { Write-Host "Interrupted" }
    }

Python:
    import subprocess
    result = subprocess.run(["autotrader-scan", "--config", "config.yaml"])
    
    EXIT_CODES = {
        0: "Success",
        1: "Configuration error",
        2: "Invalid input",
        10: "Runtime error",
        20: "Timeout",
        21: "Lock error",
        30: "Validation error",
        130: "Interrupted"
    }
    
    print(EXIT_CODES.get(result.returncode, "Unknown error"))
    """)
    
    print("=" * 80 + "\n")


def get_deprecation_info() -> dict[str, Any]:
    """Get information about deprecated exit code aliases.
    
    Returns:
        Dictionary with deprecation information
    """
    return {
        "deprecated_aliases": _DEPRECATED_ALIASES,
        "deprecation_version": _DEPRECATION_VERSION,
        "removal_version": _REMOVAL_VERSION,
        "migration_guide": {
            alias: f"Replace ExitCode.{alias} with ExitCode.{new_name}"
            for alias, new_name in _DEPRECATED_ALIASES.items()
        }
    }


def print_deprecation_warnings() -> None:
    """Print deprecation warnings for exit code aliases."""
    print("\n" + "=" * 80)
    print("EXIT CODE DEPRECATION WARNINGS")
    print("=" * 80)
    print(f"""
The following exit code aliases are DEPRECATED as of v{_DEPRECATION_VERSION}
and will be REMOVED in v{_REMOVAL_VERSION}:

""")
    
    for old_name, new_name in _DEPRECATED_ALIASES.items():
        print(f"  ❌ ExitCode.{old_name:15s} → ✅ ExitCode.{new_name}")
    
    print(f"""
MIGRATION TIMELINE:
  • v{_DEPRECATION_VERSION} (Current): Deprecation warnings added
  • v2.2.0 (Q1 2026): Warnings become errors  
  • v{_REMOVAL_VERSION} (Q2 2026): Aliases removed entirely

ACTION REQUIRED:
  Update your code to use the new canonical names before v{_REMOVAL_VERSION}.
  Use IDE search/replace or the migration script:
  
    python scripts/migrate_exit_codes.py --check     # Check usage
    python scripts/migrate_exit_codes.py --fix       # Auto-fix
""")
    print("=" * 80 + "\n")


def get_exit_code_info(code: int) -> dict[str, str]:
    """Get information about an exit code.
    
    Args:
        code: Exit code value
        
    Returns:
        Dictionary with code information
    """
    try:
        exit_code = ExitCode(code)
        return {
            "code": str(code),
            "name": exit_code.name,
            "description": EXIT_CODE_DESCRIPTIONS.get(exit_code, "Unknown exit code"),
        }
    except ValueError:
        return {
            "code": str(code),
            "name": "UNKNOWN",
            "description": f"Non-standard exit code: {code}",
        }


def list_exit_codes_json() -> str:
    """Get exit codes as JSON string.
    
    Returns:
        JSON string with all exit codes
    """
    import json
    
    codes = {}
    for code in ExitCode:
        codes[code.value] = {
            "name": code.name,
            "description": EXIT_CODE_DESCRIPTIONS.get(code, "No description"),
        }
    
    return json.dumps(codes, indent=2, sort_keys=True)


def get_category_for_exception(exception: Exception) -> ExitCode:
    """Map exception type to appropriate exit code.
    
    Args:
        exception: Exception instance
        
    Returns:
        Appropriate exit code for the exception
    """
    exception_type = type(exception).__name__
    
    # Config-related errors
    if 'Config' in exception_type or exception_type in ['FileNotFoundError', 'YAMLError']:
        return ExitCode.CONFIG
    
    # Input/argument errors
    if exception_type in ['ValueError', 'TypeError', 'KeyError', 'IndexError']:
        return ExitCode.INPUT
    
    # Timeout errors
    if 'Timeout' in exception_type or exception_type == 'TimeoutError':
        return ExitCode.TIMEOUT
    
    # Lock errors
    if 'Lock' in exception_type:
        return ExitCode.LOCKED
    
    # Validation errors
    if 'Validation' in exception_type or 'Schema' in exception_type:
        return ExitCode.VALIDATION
    
    # Interrupted
    if exception_type == 'KeyboardInterrupt':
        return ExitCode.INTERRUPTED
    
    # Default to runtime error for everything else
    return ExitCode.RUNTIME


def format_exit_code_table() -> str:
    """Format exit codes as a markdown table.
    
    Returns:
        Markdown-formatted table string
    """
    lines = [
        "# Exit Codes Reference",
        "",
        "| Code | Name | Description |",
        "|------|------|-------------|",
    ]
    
    for category, codes in EXIT_CODE_CATEGORIES.items():
        lines.append(f"| **{category}** |||")
        for code in codes:
            description = EXIT_CODE_DESCRIPTIONS.get(code, "No description")
            lines.append(f"| {code.value} | `{code.name}` | {description} |")
        lines.append("|||||")
    
    return "\n".join(lines)


# Convenience function
def exit_with_code(code: ExitCode, message: str | None = None) -> None:
    """Exit with specified code and optional message.
    
    Args:
        code: Exit code
        message: Optional message to print
    """
    import sys
    
    if message:
        print(f"Error: {message}", file=sys.stderr)
    
    sys.exit(code.value)
