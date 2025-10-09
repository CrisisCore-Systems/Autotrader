#!/usr/bin/env python
"""
Generate metrics documentation from metrics_registry.yaml.

Usage:
    python scripts/gen_metrics_docs.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
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
        # Nested structure: {"metrics": {"metric_name": {...}}}
        metrics_dict = registry["metrics"]
    else:
        # Flat structure: {"metric_name": {...}, "version": "...", etc.}
        metrics_dict = {k: v for k, v in registry.items() 
                       if isinstance(v, dict) and "type" in v}
    
    # Convert to list format
    metrics_list = []
    for name, details in metrics_dict.items():
        metric = {"name": name}
        metric.update(details)
        metrics_list.append(metric)
    
    lines = [
        "# Metrics Registry",
        "",
        "Complete reference for all metrics tracked by AutoTrader.",
        "",
        "!!! tip \"Auto-Generated\"",
        "    This page is automatically generated from `config/metrics_registry.yaml`.",
        "",
        "## Overview",
        "",
        f"AutoTrader tracks **{len(metrics_list)} metrics** across {len(set(m.get('category', 'General') for m in metrics_list))} categories.",
        "",
    ]
    
    # Group metrics by category
    by_category = {}
    for metric in metrics_list:
        category = metric.get("category", "General")
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(metric)
    
    # Generate table of contents
    lines.append("## Categories")
    lines.append("")
    for category in sorted(by_category.keys()):
        lines.append(f"- [{category}](#{category.lower().replace(' ', '-')}): {len(by_category[category])} metrics")
    lines.append("")
    
    # Generate metrics by category
    for category in sorted(by_category.keys()):
        lines.append(f"## {category}")
        lines.append("")
        
        metrics = sorted(by_category[category], key=lambda m: m["name"])
        
        for metric in metrics:
            lines.append(f"### `{metric['name']}`")
            lines.append("")
            
            # Type badge
            metric_type = metric["type"].upper()
            if metric_type == "COUNTER":
                badge = "🔢 Counter"
            elif metric_type == "GAUGE":
                badge = "📊 Gauge"
            elif metric_type == "HISTOGRAM":
                badge = "📈 Histogram"
            elif metric_type == "SUMMARY":
                badge = "📉 Summary"
            else:
                badge = f"❓ {metric_type}"
            
            lines.append(f"**Type**: {badge}")
            lines.append("")
            
            # Description
            if "description" in metric:
                lines.append(metric["description"])
                lines.append("")
            
            # Labels
            if "labels" in metric and metric["labels"]:
                lines.append("**Labels**:")
                lines.append("")
                for label in metric["labels"]:
                    lines.append(f"- `{label}`")
                lines.append("")
            
            # Unit
            if "unit" in metric:
                lines.append(f"**Unit**: {metric['unit']}")
                lines.append("")
            
            # Buckets (for histograms)
            if "buckets" in metric:
                lines.append(f"**Buckets**: `{metric['buckets']}`")
                lines.append("")
            
            # Example
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
            lines.append(f"| `{pattern_str}` | {pattern_type} | {description} |")
        
        lines.append("")
    
    lines.extend([
        "## Validation Constraints",
        "",
    ])
    
    if "validation" in registry:
        validation = registry["validation"]
        
        lines.append("### Label Constraints")
        lines.append("")
        lines.append(f"- **Maximum labels per metric**: {validation.get('max_labels', 'N/A')}")
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
        "# Load registry",
        "registry = MetricsRegistry()",
        "",
        "# Validate a metric",
        "try:",
        '    registry.validate_metric(',
        '        name="scan_duration_seconds",',
        '        type="histogram",',
        '        labels=["strategy", "status"]',
        "    )",
        '    print("✅ Metric is valid")',
        "except ValueError as e:",
        '    print(f"❌ Invalid metric: {e}")',
        "```",
        "",
        "### CLI Validation",
        "",
        "```bash",
        "# Validate all metrics in codebase",
        "python -m src.core.metrics_registry --validate",
        "```",
    ])
    
    return "\n".join(lines)


def main():
    """Generate all metrics documentation."""
    docs_dir = project_root / "docs" / "metrics"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    print("Generating metrics documentation...")
    
    # Generate registry
    print("  - registry.md")
    (docs_dir / "registry.md").write_text(generate_registry_md(), encoding="utf-8")
    
    # Generate validation
    print("  - validation.md")
    (docs_dir / "validation.md").write_text(generate_validation_md(), encoding="utf-8")
    
    print(f"\n✅ Metrics documentation generated in: {docs_dir}")


if __name__ == "__main__":
    main()
