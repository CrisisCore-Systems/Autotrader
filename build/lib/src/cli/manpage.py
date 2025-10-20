"""
Manpage Generator for AutoTrader CLI

Generates Unix manual pages (groff format) and Markdown documentation
by introspecting the argparse parser. Ensures CLI documentation stays
synchronized with actual implementation.

Usage:
    autotrader-scan --generate-manpage           # Output to stdout (man format)
    autotrader-scan --generate-manpage-path FILE # Write to file
    autotrader-scan --man-format md              # Markdown format

Formats:
    - man: Traditional groff/troff format for Unix man pages
    - md:  Markdown format for documentation sites
"""

import argparse
import datetime
import os
import sys
from enum import IntEnum
from typing import Dict, List, Optional, TextIO, Tuple

# Version info
try:
    from src import __version__
except ImportError:
    __version__ = "0.1.0"


class ManpageGenerator:
    """Generate manual pages from argparse parser."""

    def __init__(
        self,
        parser: argparse.ArgumentParser,
        prog_name: str = "autotrader-scan",
        section: int = 1,
        version: str = __version__,
        date: Optional[str] = None,
        authors: Optional[List[str]] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize manpage generator.

        Args:
            parser: Argparse parser to introspect
            prog_name: Program name for manual page
            section: Manual section (1 = user commands)
            version: Program version
            date: Manual date (defaults to today)
            authors: List of author names
            description: Program description (uses parser.description if None)
        """
        self.parser = parser
        self.prog_name = prog_name
        self.section = section
        self.version = version
        self.date = date or datetime.date.today().strftime("%B %Y")
        self.authors = authors or ["AutoTrader Development Team"]
        self.description = description or parser.description or "Automated trading strategy scanner"

    def generate(self, format: str = "man") -> str:
        """
        Generate manual page in specified format.

        Args:
            format: Output format ('man' or 'md')

        Returns:
            Generated manual page as string

        Raises:
            ValueError: If format is not supported
        """
        if format == "man":
            return self._generate_groff()
        elif format == "md":
            return self._generate_markdown()
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'man' or 'md'")

    def _generate_groff(self) -> str:
        """Generate groff/troff manual page."""
        lines = []

        # Header
        lines.append(f'.TH {self.prog_name.upper()} {self.section} "{self.date}" "{self.version}" "User Commands"')
        lines.append("")

        # NAME
        lines.append(".SH NAME")
        lines.append(f"{self.prog_name} \\- {self.description}")
        lines.append("")

        # SYNOPSIS
        lines.append(".SH SYNOPSIS")
        lines.append(f".B {self.prog_name}")
        lines.append(".RI [ OPTIONS ]")
        lines.append("")

        # DESCRIPTION
        lines.append(".SH DESCRIPTION")
        if self.parser.description:
            lines.extend(self._wrap_groff_text(self.parser.description))
        lines.append("")

        # OPTIONS
        lines.append(".SH OPTIONS")
        lines.extend(self._generate_groff_options())
        lines.append("")

        # ENVIRONMENT
        lines.append(".SH ENVIRONMENT")
        lines.extend(self._generate_groff_environment())
        lines.append("")

        # EXIT STATUS
        lines.append(".SH EXIT STATUS")
        lines.extend(self._generate_groff_exit_codes())
        lines.append("")

        # FILES
        lines.append(".SH FILES")
        lines.extend(self._generate_groff_files())
        lines.append("")

        # EXAMPLES
        lines.append(".SH EXAMPLES")
        lines.extend(self._generate_groff_examples())
        lines.append("")

        # SEE ALSO
        lines.append(".SH SEE ALSO")
        lines.extend(self._generate_groff_see_also())
        lines.append("")

        # AUTHORS
        lines.append(".SH AUTHORS")
        for author in self.authors:
            lines.append(author)
        lines.append("")

        # VERSION
        lines.append(".SH VERSION")
        lines.append(f"{self.version}")
        lines.append("")

        return "\n".join(lines)

    def _generate_markdown(self) -> str:
        """Generate Markdown documentation."""
        lines = []

        # Title
        lines.append(f"# {self.prog_name}({self.section})")
        lines.append("")
        lines.append(f"**{self.date}** | **Version {self.version}**")
        lines.append("")

        # NAME
        lines.append("## NAME")
        lines.append("")
        lines.append(f"{self.prog_name} - {self.description}")
        lines.append("")

        # SYNOPSIS
        lines.append("## SYNOPSIS")
        lines.append("")
        lines.append(f"```bash")
        lines.append(f"{self.prog_name} [OPTIONS]")
        lines.append("```")
        lines.append("")

        # DESCRIPTION
        lines.append("## DESCRIPTION")
        lines.append("")
        if self.parser.description:
            lines.append(self.parser.description)
        lines.append("")

        # OPTIONS
        lines.append("## OPTIONS")
        lines.append("")
        lines.extend(self._generate_markdown_options())
        lines.append("")

        # ENVIRONMENT
        lines.append("## ENVIRONMENT")
        lines.append("")
        lines.extend(self._generate_markdown_environment())
        lines.append("")

        # EXIT STATUS
        lines.append("## EXIT STATUS")
        lines.append("")
        lines.extend(self._generate_markdown_exit_codes())
        lines.append("")

        # FILES
        lines.append("## FILES")
        lines.append("")
        lines.extend(self._generate_markdown_files())
        lines.append("")

        # EXAMPLES
        lines.append("## EXAMPLES")
        lines.append("")
        lines.extend(self._generate_markdown_examples())
        lines.append("")

        # SEE ALSO
        lines.append("## SEE ALSO")
        lines.append("")
        lines.extend(self._generate_markdown_see_also())
        lines.append("")

        # AUTHORS
        lines.append("## AUTHORS")
        lines.append("")
        for author in self.authors:
            lines.append(f"- {author}")
        lines.append("")

        return "\n".join(lines)

    def _generate_groff_options(self) -> List[str]:
        """Generate OPTIONS section in groff format."""
        lines = []

        for action in self.parser._actions:
            # Skip help action (already documented)
            if isinstance(action, argparse._HelpAction):
                continue

            # Skip store_true/store_false without explicit help
            if action.help == argparse.SUPPRESS:
                continue

            # Build option string
            option_str = ", ".join(action.option_strings) if action.option_strings else action.dest
            
            # Add metavar for non-flag options
            if action.option_strings and action.nargs != 0 and not isinstance(action, argparse._StoreTrueAction) and not isinstance(action, argparse._StoreFalseAction):
                metavar = action.metavar or action.dest.upper()
                option_str += f" {metavar}"

            lines.append(f".TP")
            lines.append(f".B {option_str}")
            
            if action.help:
                help_text = action.help.replace("%", "%%")  # Escape % for groff
                lines.extend(self._wrap_groff_text(help_text))
            
            # Add default value if present
            if action.default is not None and action.default != argparse.SUPPRESS:
                lines.append(f"(default: {action.default})")

        return lines

    def _generate_markdown_options(self) -> List[str]:
        """Generate OPTIONS section in Markdown format."""
        lines = []

        for action in self.parser._actions:
            # Skip help action
            if isinstance(action, argparse._HelpAction):
                continue

            if action.help == argparse.SUPPRESS:
                continue

            # Build option string
            option_str = ", ".join(f"`{opt}`" for opt in action.option_strings) if action.option_strings else f"`{action.dest}`"
            
            # Add metavar
            if action.option_strings and action.nargs != 0 and not isinstance(action, argparse._StoreTrueAction) and not isinstance(action, argparse._StoreFalseAction):
                metavar = action.metavar or action.dest.upper()
                option_str += f" `{metavar}`"

            lines.append(f"### {option_str}")
            lines.append("")
            
            if action.help:
                lines.append(action.help)
            
            # Add default value
            if action.default is not None and action.default != argparse.SUPPRESS:
                lines.append(f"  ")
                lines.append(f"**Default**: `{action.default}`")
            
            lines.append("")

        return lines

    def _generate_groff_environment(self) -> List[str]:
        """Generate ENVIRONMENT section in groff format."""
        lines = []
        
        env_vars = [
            ("AUTOTRADER_CONFIG", "Path to configuration file (overrides default locations)"),
            ("AUTOTRADER_LOG_LEVEL", "Logging level (DEBUG, INFO, WARNING, ERROR)"),
            ("AUTOTRADER_METRICS_PORT", "Port for Prometheus metrics endpoint"),
            ("AUTOTRADER_DATA_DIR", "Directory for data files and cache"),
            ("AUTOTRADER_LOCK_TTL", "Default lock timeout in seconds"),
            ("AUTOTRADER_API_KEY", "API key for data providers"),
            ("AUTOTRADER_DETERMINISTIC", "Enable deterministic mode (1/true/yes)"),
        ]

        for var_name, var_desc in env_vars:
            lines.append(f".TP")
            lines.append(f".B {var_name}")
            lines.extend(self._wrap_groff_text(var_desc))

        return lines

    def _generate_markdown_environment(self) -> List[str]:
        """Generate ENVIRONMENT section in Markdown format."""
        lines = []
        
        env_vars = [
            ("AUTOTRADER_CONFIG", "Path to configuration file (overrides default locations)"),
            ("AUTOTRADER_LOG_LEVEL", "Logging level (DEBUG, INFO, WARNING, ERROR)"),
            ("AUTOTRADER_METRICS_PORT", "Port for Prometheus metrics endpoint"),
            ("AUTOTRADER_DATA_DIR", "Directory for data files and cache"),
            ("AUTOTRADER_LOCK_TTL", "Default lock timeout in seconds"),
            ("AUTOTRADER_API_KEY", "API key for data providers"),
            ("AUTOTRADER_DETERMINISTIC", "Enable deterministic mode (1/true/yes)"),
        ]

        for var_name, var_desc in env_vars:
            lines.append(f"### `{var_name}`")
            lines.append("")
            lines.append(var_desc)
            lines.append("")

        return lines

    def _generate_groff_exit_codes(self) -> List[str]:
        """Generate EXIT STATUS section in groff format."""
        lines = []

        # Try to import exit codes
        try:
            from src.cli.exit_codes import ExitCode, EXIT_CODE_DESCRIPTIONS
            # Get unique exit codes (deduplicate aliases)
            seen_values = set()
            exit_codes = []
            for code in ExitCode:
                if code.value not in seen_values:
                    seen_values.add(code.value)
                    desc = EXIT_CODE_DESCRIPTIONS.get(code, "")
                    exit_codes.append((code.value, code.name, desc))
        except ImportError:
            # Fallback to standard codes
            exit_codes = [
                (0, "OK", "Scan completed successfully"),
                (1, "CONFIG", "Configuration error"),
                (2, "INPUT", "Input/argument error"),
                (10, "RUNTIME", "Runtime error"),
                (20, "TIMEOUT", "Operation timed out"),
                (21, "LOCKED", "Lock acquisition failed"),
                (30, "VALIDATION", "Validation error"),
                (130, "INTERRUPTED", "User interrupted (Ctrl+C)"),
            ]

        for code, name, desc in exit_codes:
            lines.append(f".TP")
            lines.append(f".B {code} ({name})")
            if desc:
                lines.extend(self._wrap_groff_text(desc))

        return lines

    def _generate_markdown_exit_codes(self) -> List[str]:
        """Generate EXIT STATUS section in Markdown format."""
        lines = []

        # Try to import exit codes
        try:
            from src.cli.exit_codes import ExitCode, EXIT_CODE_DESCRIPTIONS
            # Get unique exit codes (deduplicate aliases)
            seen_values = set()
            exit_codes = []
            for code in ExitCode:
                if code.value not in seen_values:
                    seen_values.add(code.value)
                    desc = EXIT_CODE_DESCRIPTIONS.get(code, "")
                    exit_codes.append((code.value, code.name, desc))
        except ImportError:
            # Fallback
            exit_codes = [
                (0, "OK", "Scan completed successfully"),
                (1, "CONFIG", "Configuration error"),
                (2, "INPUT", "Input/argument error"),
                (10, "RUNTIME", "Runtime error"),
                (20, "TIMEOUT", "Operation timed out"),
                (21, "LOCKED", "Lock acquisition failed"),
                (30, "VALIDATION", "Validation error"),
                (130, "INTERRUPTED", "User interrupted (Ctrl+C)"),
            ]

        lines.append("| Code | Name | Description |")
        lines.append("|------|------|-------------|")
        
        for code, name, desc in exit_codes:
            lines.append(f"| `{code}` | `{name}` | {desc or 'N/A'} |")

        return lines

    def _generate_groff_files(self) -> List[str]:
        """Generate FILES section in groff format."""
        lines = []

        files = [
            ("~/.config/autotrader/config.yaml", "User configuration file"),
            ("/etc/autotrader/config.yaml", "System-wide configuration file"),
            ("./config.yaml", "Project-local configuration file"),
            ("configs/metrics_registry.yaml", "Metrics definitions and validation rules"),
            ("~/.cache/autotrader/", "Cache directory for downloaded data"),
            ("/var/lock/autotrader.lock", "Lock file to prevent concurrent runs"),
        ]

        for path, desc in files:
            lines.append(f".TP")
            lines.append(f".B {path}")
            lines.extend(self._wrap_groff_text(desc))

        return lines

    def _generate_markdown_files(self) -> List[str]:
        """Generate FILES section in Markdown format."""
        lines = []

        files = [
            ("~/.config/autotrader/config.yaml", "User configuration file"),
            ("/etc/autotrader/config.yaml", "System-wide configuration file"),
            ("./config.yaml", "Project-local configuration file"),
            ("configs/metrics_registry.yaml", "Metrics definitions and validation rules"),
            ("~/.cache/autotrader/", "Cache directory for downloaded data"),
            ("/var/lock/autotrader.lock", "Lock file to prevent concurrent runs"),
        ]

        for path, desc in files:
            lines.append(f"- `{path}`: {desc}")

        return lines

    def _generate_groff_examples(self) -> List[str]:
        """Generate EXAMPLES section in groff format."""
        lines = []

        examples = [
            ("Basic scan with default configuration", f"{self.prog_name}"),
            ("Scan with specific config file", f"{self.prog_name} --config /path/to/config.yaml"),
            ("Scan with custom lock timeout", f"{self.prog_name} --lock-ttl 3600"),
            ("Print effective configuration", f"{self.prog_name} --print-effective-config"),
            ("Generate reproducibility stamp", f"{self.prog_name} --enable-repro-stamp"),
            ("Verbose logging", f"{self.prog_name} --log-level DEBUG"),
        ]

        for desc, cmd in examples:
            lines.append(f".TP")
            lines.extend(self._wrap_groff_text(desc))
            lines.append(f".B {cmd}")

        return lines

    def _generate_markdown_examples(self) -> List[str]:
        """Generate EXAMPLES section in Markdown format."""
        lines = []

        examples = [
            ("Basic scan with default configuration", f"{self.prog_name}"),
            ("Scan with specific config file", f"{self.prog_name} --config /path/to/config.yaml"),
            ("Scan with custom lock timeout", f"{self.prog_name} --lock-ttl 3600"),
            ("Print effective configuration", f"{self.prog_name} --print-effective-config"),
            ("Generate reproducibility stamp", f"{self.prog_name} --enable-repro-stamp"),
            ("Verbose logging", f"{self.prog_name} --log-level DEBUG"),
        ]

        for desc, cmd in examples:
            lines.append(f"**{desc}**")
            lines.append("")
            lines.append("```bash")
            lines.append(cmd)
            lines.append("```")
            lines.append("")

        return lines

    def _generate_groff_see_also(self) -> List[str]:
        """Generate SEE ALSO section in groff format."""
        return [
            ".BR autotrader-config (5),",
            ".BR autotrader-strategies (7),",
            "Online documentation: https://github.com/CrisisCore-Systems/Autotrader",
        ]

    def _generate_markdown_see_also(self) -> List[str]:
        """Generate SEE ALSO section in Markdown format."""
        return [
            "- autotrader-config(5) - Configuration file format",
            "- autotrader-strategies(7) - Strategy plugin development",
            "- [Online Documentation](https://github.com/CrisisCore-Systems/Autotrader)",
        ]

    def _wrap_groff_text(self, text: str, width: int = 72) -> List[str]:
        """
        Wrap text for groff output.
        
        Args:
            text: Text to wrap
            width: Maximum line width
            
        Returns:
            List of wrapped lines
        """
        # Simple word wrapping
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            if current_length + word_length + len(current_line) > width:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    lines.append(word)
            else:
                current_line.append(word)
                current_length += word_length

        if current_line:
            lines.append(" ".join(current_line))

        return lines


def add_manpage_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add manpage generation arguments to parser.

    Args:
        parser: ArgumentParser to extend
    """
    manpage_group = parser.add_argument_group("manpage generation")
    
    manpage_group.add_argument(
        "--generate-manpage",
        action="store_true",
        help="Generate manual page and exit (outputs to stdout)"
    )
    
    manpage_group.add_argument(
        "--generate-manpage-path",
        metavar="PATH",
        help="Write manual page to specified path"
    )
    
    manpage_group.add_argument(
        "--man-format",
        choices=["man", "md"],
        default="man",
        help="Manual page output format (default: man)"
    )


def handle_manpage_generation(args: argparse.Namespace, parser: argparse.ArgumentParser) -> bool:
    """
    Handle manpage generation if requested.

    Args:
        args: Parsed arguments
        parser: ArgumentParser instance

    Returns:
        True if manpage was generated (caller should exit), False otherwise
    """
    if not (args.generate_manpage or args.generate_manpage_path):
        return False

    # Create generator
    generator = ManpageGenerator(
        parser=parser,
        prog_name="autotrader-scan",
        version=__version__,
    )

    # Generate manpage
    output = generator.generate(format=args.man_format)

    # Write output
    if args.generate_manpage_path:
        with open(args.generate_manpage_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Manual page written to: {args.generate_manpage_path}", file=sys.stderr)
    else:
        print(output)

    return True


if __name__ == "__main__":
    # Test manpage generation
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
    
    add_manpage_arguments(parser)
    
    args = parser.parse_args()
    
    if handle_manpage_generation(args, parser):
        sys.exit(0)
    
    print("No manpage generation requested. Use --generate-manpage")
