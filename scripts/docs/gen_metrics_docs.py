#!/usr/bin/env python3
"""
Generate metrics documentation from metrics_registry.yaml.

Usage:
    python scripts/docs/gen_metrics_docs.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

import yaml


def load_metrics_registry():
    """Load metrics registry from YAML file."""
    registry_path = project_root / "config" / "metrics_registry.yaml"
    with open(registry_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_registry_md():
    """Generate metrics registry documentation."""
    registry = load_metrics_registry()

    # Extract metrics (handle both flat and nested structures)
    if "metrics" in registry and isinstance(registry["metrics"], dict):
        metrics_dict = registry["metrics"]
    else:
        metrics_dict = {
            k: v
            for k, v in registry.items()
            if isinstance(v, dict) and "type" in v
        }

    metrics_list = []
    for name, details in metrics_dict.items():
        metric = {"name": name}
        metric.update(details)
        metrics_list.append(metric)

    category_count = len(
        {
            metric.get("category", "General")
            for metric in metrics_list
        }
    )

    lines = [
        "# Metrics Registry",
        "",
        "Complete reference for all metrics tracked by AutoTrader.",
        "",
        "!!! tip \"Auto-Generated\"",
        "    This page is automatically generated from `configs/metrics_registry.yaml`.",
        "",
        "## Overview",
        "",
        f"AutoTrader tracks **{len(metrics_list)} metrics** across {category_count} categories.",
        "",
    ]

    by_category = {}
    for metric in metrics_list:
        category = metric.get("category", "General")
        by_category.setdefault(category, []).append(metric)

    lines.append("## Categories")
    lines.append("")
    for category in sorted(by_category.keys()):
        slug = category.lower().replace(" ", "-")
        lines.append(f"- [{category}](#{slug}): {len(by_category[category])} metrics")
    lines.append("")

    for category in sorted(by_category.keys()):
        lines.append(f"## {category}")
        lines.append("")

        metrics = sorted(by_category[category], key=lambda m: m["name"])
        for metric in metrics:
            lines.append(f"### `{metric['name']}`")
            lines.append("")

            metric_type = metric["type"].upper()
            badge = {
                "COUNTER": "🔢 Counter",
                "GAUGE": "📊 Gauge",
                "HISTOGRAM": "📈 Histogram",
                "SUMMARY": "📉 Summary",
            }.get(metric_type, f"❓ {metric_type}")
            lines.append(f"**Type**: {badge}")
            lines.append("")

            if "description" in metric:
                lines.append(metric["description"])
                lines.append("")

            if metric.get("labels"):
                lines.append("**Labels**:")
                lines.append("")
                for label in metric["labels"]:
                    lines.append(f"- `{label}`")
                lines.append("")

            if "unit" in metric:
                lines.append(f"**Unit**: {metric['unit']}")
                lines.append("")

            if "buckets" in metric:
                lines.append(f"**Buckets**: `{metric['buckets']}`")
                lines.append("")

            if "example" in metric:
                lines.append("**Example**:")
                lines.append("")
                lines.append("```")
                lines.append(metric["example"])
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


def generate_validation_md():
    """Generate metrics validation rules documentation."""
    registry = load_metrics_registry()

    lines = [
        "# Metrics Validation Rules",
        "",
        "Rules and patterns for metric naming and validation.",
        "",
        "## Naming Patterns",
        "",
        "AutoTrader enforces consistent metric naming patterns:",
        "",
    ]

    if "patterns" in registry:
        lines.append("| Pattern | Type | Description |")
        lines.append("|---------|------|-------------|")
        for pattern in registry["patterns"]:
            pattern_str = pattern.get("pattern", "N/A")
            pattern_type = pattern.get("type", pattern.get("applies_to", "N/A"))
            description = pattern.get("description", "")
            lines.append(
                f"| `{pattern_str}` | {pattern_type} | {description} |"
            )
        lines.append("")

    lines.extend([
        "## Validation Constraints",
        "",
    ])

    if "validation" in registry:
        validation = registry["validation"]

        lines.append("### Label Constraints")
        lines.append("")
        lines.append(
            f"- **Maximum labels per metric**: {validation.get('max_labels', 'N/A')}"
        )
        lines.append("")

        if "forbidden_label_names" in validation:
            lines.append("**Forbidden label names**:")
            lines.append("")
            for name in validation["forbidden_label_names"]:
                lines.append(f"- `{name}`")
            lines.append("")

    lines.extend([
        "",
        "## Deprecated Metrics",
        "",
        "The following metrics are deprecated and will be removed in future versions:",
        "",
    ])

    if "deprecated" in registry:
        lines.append("| Deprecated | Replacement | Since | Removal |")
        lines.append("|------------|-------------|-------|---------|")
        for old_name, info in registry["deprecated"].items():
            lines.append(
                f"| `{old_name}` | `{info['replacement']}` | "
                f"{info.get('since', 'N/A')} | {info.get('removal', 'TBD')} |"
            )
        lines.append("")
    else:
        lines.append("*No deprecated metrics at this time.*")
        lines.append("")

    lines.extend([
        "",
        "## Using the Registry",
        "",
        "### Python Example",
        "",
        "```python",
        "from src.core.metrics_registry import MetricsRegistry",
        "",
        "registry = MetricsRegistry()",
        "",
        "try:",
        '    registry.validate_metric(',
        '        name="scan_duration_seconds",',
        '        type="histogram",',
        '        labels=["strategy", "status"],',
        "    )",
        '    print("✅ Metric is valid")',
        "except ValueError as exc:",
        '    print(f"❌ Invalid metric: {exc}")',
        "```",
        "",
        "### CLI Validation",
        "",
        "```bash",
        "python -m src.core.metrics_registry --validate",
        "```",
    ])

    return "\n".join(lines)


def main() -> None:
    """Generate all metrics documentation."""
    docs_dir = project_root / "docs" / "metrics"
    docs_dir.mkdir(parents=True, exist_ok=True)

    print("Generating metrics documentation...")

    print("  - registry.md")
    (docs_dir / "registry.md").write_text(
        generate_registry_md(),
        encoding="utf-8",
    )

    print("  - validation.md")
    (docs_dir / "validation.md").write_text(
        generate_validation_md(),
        encoding="utf-8",
    )

    print(f"\n✅ Metrics documentation generated in: {docs_dir}")


if __name__ == "__main__":
    main()
