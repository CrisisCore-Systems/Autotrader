#!/usr/bin/env python3
"""CLI for managing experiment configurations.

Provides commands to list, view, compare, and manage experiment
configurations for reproducibility.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from src.utils.experiment_tracker import ExperimentConfig, ExperimentRegistry


def cmd_list(args: argparse.Namespace) -> int:
    """List all experiments."""
    registry = ExperimentRegistry(args.db)
    experiments = registry.list_all(limit=args.limit)
    
    if not experiments:
        print("No experiments found.")
        return 0
    
    print(f"Found {len(experiments)} experiments:\n")
    
    for exp in experiments:
        print(f"  {exp.config_hash[:12]} - {exp.created_at}")
        if exp.description:
            print(f"    Description: {exp.description}")
        if exp.tags:
            print(f"    Tags: {', '.join(exp.tags)}")
        print(f"    Features: {len(exp.feature_names)}")
        print()
    
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show details of an experiment."""
    registry = ExperimentRegistry(args.db)
    exp = registry.get(args.hash)
    
    if not exp:
        print(f"❌ Experiment {args.hash} not found")
        return 1
    
    if args.json:
        print(exp.to_json())
    else:
        print(exp.summary())
    
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two experiments."""
    registry = ExperimentRegistry(args.db)
    
    comparison = registry.compare(args.hash1, args.hash2)
    
    if "error" in comparison:
        print(f"❌ {comparison['error']}")
        return 1
    
    if args.json:
        print(json.dumps(comparison, indent=2))
        return 0
    
    print(f"\n🔍 Comparing Experiments:")
    print(f"  Config 1: {comparison['config1_hash']}")
    print(f"  Config 2: {comparison['config2_hash']}")
    print()
    
    features = comparison["features"]
    print("Feature Set Differences:")
    if features["only_in_config1"]:
        print(f"  Only in Config 1: {', '.join(features['only_in_config1'])}")
    if features["only_in_config2"]:
        print(f"  Only in Config 2: {', '.join(features['only_in_config2'])}")
    print(f"  Common features: {len(features['common'])}")
    print()
    
    weight_diffs = comparison["weight_differences"]
    if weight_diffs:
        print("Weight Differences:")
        for feature, diff in sorted(weight_diffs.items(), key=lambda x: abs(x[1]["diff"]), reverse=True):
            print(f"  {feature}:")
            print(f"    Config 1: {diff['config1']:.4f}")
            print(f"    Config 2: {diff['config2']:.4f}")
            print(f"    Difference: {diff['diff']:+.4f}")
    else:
        print("No weight differences found.")
    print()
    
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search experiments by tag."""
    registry = ExperimentRegistry(args.db)
    experiments = registry.search_by_tag(args.tag)
    
    if not experiments:
        print(f"No experiments found with tag '{args.tag}'")
        return 0
    
    print(f"Found {len(experiments)} experiments with tag '{args.tag}':\n")
    
    for exp in experiments:
        print(f"  {exp.config_hash[:12]} - {exp.created_at}")
        if exp.description:
            print(f"    Description: {exp.description}")
        print()
    
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete an experiment."""
    registry = ExperimentRegistry(args.db)
    
    # Show experiment before deletion
    exp = registry.get(args.hash)
    if not exp:
        print(f"❌ Experiment {args.hash} not found")
        return 1
    
    if not args.force:
        print(f"About to delete experiment: {exp.config_hash[:12]}")
        if exp.description:
            print(f"Description: {exp.description}")
        response = input("Are you sure? (yes/no): ")
        if response.lower() not in ("yes", "y"):
            print("Deletion cancelled.")
            return 0
    
    if registry.delete(exp.config_hash):
        print(f"✅ Deleted experiment {exp.config_hash[:12]}")
        return 0
    else:
        print(f"❌ Failed to delete experiment")
        return 1


def cmd_export(args: argparse.Namespace) -> int:
    """Export an experiment to a file."""
    registry = ExperimentRegistry(args.db)
    exp = registry.get(args.hash)
    
    if not exp:
        print(f"❌ Experiment {args.hash} not found")
        return 1
    
    output_path = Path(args.output)
    output_path.write_text(exp.to_json())
    
    print(f"✅ Exported experiment to {output_path}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import an experiment from a file."""
    registry = ExperimentRegistry(args.db)
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return 1
    
    try:
        exp = ExperimentConfig.from_json(input_path.read_text())
        config_hash = registry.register(exp)
        print(f"✅ Imported experiment: {config_hash[:12]}")
        return 0
    except Exception as e:
        print(f"❌ Failed to import experiment: {e}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Manage experiment configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db",
        default="experiments.sqlite",
        help="Path to experiment database (default: experiments.sqlite)",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all experiments")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum number to list")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show experiment details")
    show_parser.add_argument("hash", help="Experiment hash (full or partial)")
    show_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two experiments")
    compare_parser.add_argument("hash1", help="First experiment hash")
    compare_parser.add_argument("hash2", help="Second experiment hash")
    compare_parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search experiments by tag")
    search_parser.add_argument("tag", help="Tag to search for")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an experiment")
    delete_parser.add_argument("hash", help="Experiment hash to delete")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export experiment to file")
    export_parser.add_argument("hash", help="Experiment hash to export")
    export_parser.add_argument("output", help="Output file path")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import experiment from file")
    import_parser.add_argument("input", help="Input file path")
    
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "compare": cmd_compare,
        "search": cmd_search,
        "delete": cmd_delete,
        "export": cmd_export,
        "import": cmd_import,
    }
    
    handler = commands.get(args.command)
    if not handler:
        print(f"Unknown command: {args.command}")
        return 1
    
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.command in ("show", "compare"):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
