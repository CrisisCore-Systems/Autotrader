"""
Tests for manpage generator.

Validates that generated manual pages contain all required sections,
flags, exit codes, and environment variables.
"""

import argparse
import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.manpage import ManpageGenerator, add_manpage_arguments, handle_manpage_generation


def create_test_parser() -> argparse.ArgumentParser:
    """Create a test argument parser."""
    parser = argparse.ArgumentParser(
        prog="autotrader-scan",
        description="Automated trading strategy scanner and backtesting platform"
    )
    
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       default="INFO", help="Logging level")
    parser.add_argument("--lock-ttl", type=int, metavar="SECONDS", 
                       help="Lock timeout in seconds")
    parser.add_argument("--deterministic", action="store_true", 
                       help="Enable deterministic mode")
    parser.add_argument("--print-effective-config", action="store_true",
                       help="Print effective configuration and exit")
    parser.add_argument("--enable-repro-stamp", action="store_true",
                       help="Generate reproducibility stamp")
    
    add_manpage_arguments(parser)
    
    return parser


def test_groff_generation():
    """Test groff manual page generation."""
    print("Testing groff manual page generation...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    output = generator.generate(format="man")
    
    # Check for required sections
    assert ".TH AUTOTRADER-SCAN" in output, "Missing .TH header"
    assert ".SH NAME" in output, "Missing NAME section"
    assert ".SH SYNOPSIS" in output, "Missing SYNOPSIS section"
    assert ".SH DESCRIPTION" in output, "Missing DESCRIPTION section"
    assert ".SH OPTIONS" in output, "Missing OPTIONS section"
    assert ".SH ENVIRONMENT" in output, "Missing ENVIRONMENT section"
    assert ".SH EXIT STATUS" in output, "Missing EXIT STATUS section"
    assert ".SH FILES" in output, "Missing FILES section"
    assert ".SH EXAMPLES" in output, "Missing EXAMPLES section"
    assert ".SH SEE ALSO" in output, "Missing SEE ALSO section"
    assert ".SH AUTHORS" in output, "Missing AUTHORS section"
    
    # Check that all flags appear
    assert "--config" in output, "Missing --config flag"
    assert "--log-level" in output, "Missing --log-level flag"
    assert "--lock-ttl" in output, "Missing --lock-ttl flag"
    assert "--deterministic" in output, "Missing --deterministic flag"
    assert "--print-effective-config" in output, "Missing --print-effective-config flag"
    assert "--enable-repro-stamp" in output, "Missing --enable-repro-stamp flag"
    
    # Check for environment variables
    assert "AUTOTRADER_CONFIG" in output, "Missing AUTOTRADER_CONFIG"
    assert "AUTOTRADER_LOG_LEVEL" in output, "Missing AUTOTRADER_LOG_LEVEL"
    assert "AUTOTRADER_LOCK_TTL" in output, "Missing AUTOTRADER_LOCK_TTL"
    
    print("✅ Groff generation test passed")
    return output


def test_markdown_generation():
    """Test Markdown manual page generation."""
    print("\nTesting Markdown manual page generation...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    output = generator.generate(format="md")
    
    # Check for required sections
    assert "## NAME" in output, "Missing NAME section"
    assert "## SYNOPSIS" in output, "Missing SYNOPSIS section"
    assert "## DESCRIPTION" in output, "Missing DESCRIPTION section"
    assert "## OPTIONS" in output, "Missing OPTIONS section"
    assert "## ENVIRONMENT" in output, "Missing ENVIRONMENT section"
    assert "## EXIT STATUS" in output, "Missing EXIT STATUS section"
    assert "## FILES" in output, "Missing FILES section"
    assert "## EXAMPLES" in output, "Missing EXAMPLES section"
    assert "## SEE ALSO" in output, "Missing SEE ALSO section"
    assert "## AUTHORS" in output, "Missing AUTHORS section"
    
    # Check for markdown formatting
    assert "```bash" in output, "Missing code blocks"
    assert "`--config`" in output or "--config" in output, "Missing --config flag"
    
    # Check for exit code table
    assert "| Code | Name | Description |" in output, "Missing exit code table"
    
    print("✅ Markdown generation test passed")
    return output


def test_all_flags_present():
    """Verify all parser flags appear in generated manpage."""
    print("\nTesting flag completeness...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    output = generator.generate(format="man")
    
    # Extract all flags from parser (excluding help - it's intentionally omitted)
    flags = []
    for action in parser._actions:
        if action.option_strings and action.help != argparse.SUPPRESS:
            # Skip help action - it's intentionally not documented in manpage
            if not isinstance(action, argparse._HelpAction):
                flags.extend(action.option_strings)
    
    # Check each flag appears in output
    missing_flags = []
    for flag in flags:
        if flag not in output:
            missing_flags.append(flag)
    
    if missing_flags:
        print(f"❌ Missing flags: {', '.join(missing_flags)}")
        return False
    
    print(f"✅ All {len(flags)} flags present in manpage")
    return True


def test_exit_codes_section():
    """Test exit codes section generation."""
    print("\nTesting exit codes section...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    output = generator.generate(format="man")
    
    # Check for exit code entries (at least OK and ERROR/RUNTIME)
    assert re.search(r"\b0\b.*(OK|SUCCESS)", output, re.IGNORECASE), "Missing OK/SUCCESS exit code"
    assert re.search(r"\b[1-9]\d?\b.*(ERROR|RUNTIME|CONFIG)", output, re.IGNORECASE), "Missing error exit codes"
    
    print("✅ Exit codes section test passed")
    return True


def test_environment_variables():
    """Test environment variables section."""
    print("\nTesting environment variables section...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    output = generator.generate(format="man")
    
    required_vars = [
        "AUTOTRADER_CONFIG",
        "AUTOTRADER_LOG_LEVEL",
        "AUTOTRADER_METRICS_PORT",
        "AUTOTRADER_DATA_DIR",
        "AUTOTRADER_LOCK_TTL",
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in output:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print(f"✅ All {len(required_vars)} environment variables present")
    return True


def test_examples_section():
    """Test examples section generation."""
    print("\nTesting examples section...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    output = generator.generate(format="man")
    
    # Check for at least a few examples
    assert "autotrader-scan" in output, "Missing program name in examples"
    assert "--config" in output, "Missing config example"
    assert "--print-effective-config" in output, "Missing effective-config example"
    
    print("✅ Examples section test passed")
    return True


def test_output_formats():
    """Test both output formats are valid."""
    print("\nTesting output format validity...")
    
    parser = create_test_parser()
    generator = ManpageGenerator(parser=parser)
    
    # Test man format
    man_output = generator.generate(format="man")
    assert len(man_output) > 1000, "Man output too short"
    assert man_output.startswith(".TH"), "Man output should start with .TH"
    
    # Test markdown format
    md_output = generator.generate(format="md")
    assert len(md_output) > 1000, "Markdown output too short"
    assert md_output.startswith("#"), "Markdown output should start with #"
    
    # Test invalid format
    try:
        generator.generate(format="invalid")
        print("❌ Should have raised ValueError for invalid format")
        return False
    except ValueError:
        pass  # Expected
    
    print("✅ Output format validation test passed")
    return True


def test_handle_manpage_generation():
    """Test the handle_manpage_generation helper."""
    print("\nTesting handle_manpage_generation helper...")
    
    parser = create_test_parser()
    
    # Test with --generate-manpage
    args = parser.parse_args(["--generate-manpage"])
    should_exit = handle_manpage_generation(args, parser)
    assert should_exit, "Should return True when manpage requested"
    
    # Test without manpage flags
    args = parser.parse_args([])
    should_exit = handle_manpage_generation(args, parser)
    assert not should_exit, "Should return False when manpage not requested"
    
    print("✅ Helper function test passed")
    return True


def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print("Running Manpage Generator Tests")
    print("=" * 70)
    
    tests = [
        ("Groff Generation", test_groff_generation),
        ("Markdown Generation", test_markdown_generation),
        ("Flag Completeness", test_all_flags_present),
        ("Exit Codes Section", test_exit_codes_section),
        ("Environment Variables", test_environment_variables),
        ("Examples Section", test_examples_section),
        ("Output Format Validation", test_output_formats),
        ("Helper Function", test_handle_manpage_generation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result or result is None:  # None means assertion-based test passed
                passed += 1
            else:
                failed += 1
                print(f"❌ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
