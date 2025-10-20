"""Metrics registry validator.

Validates that metrics conform to the registry and naming conventions.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml

logger = logging.getLogger(__name__)


class MetricsRegistryError(Exception):
    """Raised when metrics validation fails."""
    pass


class MetricsRegistry:
    """Registry for validating metrics against standards."""
    
    def __init__(self, registry_path: str | Path | None = None):
        """Initialize metrics registry.
        
        Args:
            registry_path: Path to metrics_registry.yaml
        """
        if registry_path is None:
            # Default to configs/metrics_registry.yaml
            registry_path = Path(__file__).parent.parent.parent / "configs" / "metrics_registry.yaml"
        
        self.registry_path = Path(registry_path)
        self._registry: Dict[str, Any] = {}
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load registry from YAML file."""
        try:
            with open(self.registry_path) as f:
                self._registry = yaml.safe_load(f)
            logger.info(f"✅ Loaded metrics registry from {self.registry_path}")
        except Exception as e:
            logger.warning(f"Failed to load metrics registry: {e}")
            self._registry = {}
    
    def validate_metric(
        self,
        name: str,
        metric_type: str,
        labels: Optional[List[str]] = None,
        raise_on_error: bool = True,
    ) -> bool:
        """Validate a metric against the registry.
        
        Args:
            name: Metric name
            metric_type: Metric type (counter, gauge, histogram, summary)
            labels: List of label names
            raise_on_error: Whether to raise exception on validation failure
        
        Returns:
            True if valid
        
        Raises:
            MetricsRegistryError: If validation fails and raise_on_error is True
        """
        errors = []
        labels = labels or []
        
        # Check if metric is registered
        metrics = self._registry.get("metrics", {})
        if name not in metrics:
            errors.append(f"Metric '{name}' not found in registry")
        else:
            # Validate against registry entry
            metric_def = metrics[name]
            
            # Check type
            expected_type = metric_def.get("type")
            if expected_type != metric_type:
                errors.append(
                    f"Type mismatch for '{name}': "
                    f"expected {expected_type}, got {metric_type}"
                )
            
            # Check labels
            expected_labels = set(metric_def.get("labels", []))
            provided_labels = set(labels)
            
            if expected_labels != provided_labels:
                missing = expected_labels - provided_labels
                extra = provided_labels - expected_labels
                
                if missing:
                    errors.append(f"Missing labels for '{name}': {missing}")
                if extra:
                    errors.append(f"Extra labels for '{name}': {extra}")
        
        # Validate naming patterns
        pattern_errors = self._validate_patterns(name, metric_type, labels)
        errors.extend(pattern_errors)
        
        # Validate constraints
        constraint_errors = self._validate_constraints(name, labels)
        errors.extend(constraint_errors)
        
        if errors:
            error_msg = f"Metric validation failed for '{name}':\n" + "\n".join(f"  - {e}" for e in errors)
            if raise_on_error:
                raise MetricsRegistryError(error_msg)
            else:
                logger.warning(error_msg)
                return False
        
        logger.debug(f"✅ Metric validation passed: {name}")
        return True
    
    def _validate_patterns(
        self,
        name: str,
        metric_type: str,
        labels: List[str],
    ) -> List[str]:
        """Validate metric against naming patterns.
        
        Args:
            name: Metric name
            metric_type: Metric type
            labels: Label names
        
        Returns:
            List of validation errors
        """
        errors = []
        patterns = self._registry.get("patterns", [])
        
        for pattern_def in patterns:
            pattern = pattern_def.get("pattern", "")
            applies_to = pattern_def.get("applies_to", "metric_name")
            expected_type = pattern_def.get("type")
            description = pattern_def.get("description", "")
            
            if applies_to == "metric_name":
                # Pattern applies to metric name
                if expected_type and expected_type == metric_type:
                    if not re.match(pattern, name):
                        errors.append(f"{description}: '{name}' doesn't match pattern '{pattern}'")
            
            elif applies_to == "labels":
                # Pattern applies to label names
                for label in labels:
                    if not re.match(pattern, label):
                        errors.append(f"{description}: label '{label}' doesn't match pattern '{pattern}'")
        
        return errors
    
    def _validate_constraints(
        self,
        name: str,
        labels: List[str],
    ) -> List[str]:
        """Validate metric against constraints.
        
        Args:
            name: Metric name
            labels: Label names
        
        Returns:
            List of validation errors
        """
        errors = []
        validation_rules = self._registry.get("validation", {})
        
        # Check max labels
        max_labels = validation_rules.get("max_labels_per_metric", 10)
        if len(labels) > max_labels:
            errors.append(
                f"Too many labels ({len(labels)} > {max_labels}). "
                "Consider reducing cardinality."
            )
        
        # Check forbidden label names
        forbidden = set(validation_rules.get("forbidden_label_names", []))
        for label in labels:
            if label in forbidden:
                errors.append(
                    f"Forbidden label name: '{label}'. "
                    f"Use more specific name."
                )
        
        return errors
    
    def list_metrics(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered metrics.
        
        Args:
            category: Optional category filter
        
        Returns:
            List of metric definitions
        """
        metrics = self._registry.get("metrics", {})
        result = []
        
        for name, definition in metrics.items():
            if category and definition.get("category") != category:
                continue
            
            result.append({
                "name": name,
                **definition,
            })
        
        return sorted(result, key=lambda m: m["name"])
    
    def get_metric_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a metric.
        
        Args:
            name: Metric name
        
        Returns:
            Metric definition or None if not found
        """
        metrics = self._registry.get("metrics", {})
        return metrics.get(name)
    
    def check_deprecated(self, name: str) -> Optional[str]:
        """Check if metric is deprecated.
        
        Args:
            name: Metric name
        
        Returns:
            New metric name if deprecated, None otherwise
        """
        deprecated = self._registry.get("deprecated_metrics", {})
        return deprecated.get(name)
    
    def get_categories(self) -> List[str]:
        """Get all metric categories.
        
        Returns:
            List of category names
        """
        validation = self._registry.get("validation", {})
        return validation.get("categories", [])
    
    def print_summary(self) -> None:
        """Print registry summary."""
        metrics = self._registry.get("metrics", {})
        
        print("\n" + "=" * 80)
        print("METRICS REGISTRY SUMMARY")
        print("=" * 80)
        print(f"Total Metrics: {len(metrics)}")
        print(f"Registry Version: {self._registry.get('version', 'unknown')}")
        print(f"Namespace: {self._registry.get('namespace', 'unknown')}")
        
        # Group by category
        by_category: Dict[str, int] = {}
        for metric_def in metrics.values():
            category = metric_def.get("category", "unknown")
            by_category[category] = by_category.get(category, 0) + 1
        
        print("\nMetrics by Category:")
        for category, count in sorted(by_category.items()):
            print(f"  {category:20s}: {count:3d} metrics")
        
        # Show deprecated metrics
        deprecated = self._registry.get("deprecated_metrics", {})
        if deprecated:
            print(f"\nDeprecated Metrics: {len(deprecated)}")
            for old, new in deprecated.items():
                print(f"  {old} → {new}")
        
        print("=" * 80 + "\n")


# Global registry instance
_registry: Optional[MetricsRegistry] = None


def get_registry() -> MetricsRegistry:
    """Get global metrics registry instance.
    
    Returns:
        MetricsRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


def validate_metric(
    name: str,
    metric_type: str,
    labels: Optional[List[str]] = None,
    raise_on_error: bool = True,
) -> bool:
    """Validate a metric against the registry.
    
    Convenience function using global registry.
    
    Args:
        name: Metric name
        metric_type: Metric type
        labels: Label names
        raise_on_error: Whether to raise on error
    
    Returns:
        True if valid
    """
    registry = get_registry()
    return registry.validate_metric(name, metric_type, labels, raise_on_error)


def check_metric_deprecated(name: str) -> Optional[str]:
    """Check if metric is deprecated.
    
    Args:
        name: Metric name
    
    Returns:
        New metric name if deprecated, None otherwise
    """
    registry = get_registry()
    return registry.check_deprecated(name)


if __name__ == "__main__":
    # Test the registry
    import sys
    
    registry = MetricsRegistry()
    registry.print_summary()
    
    # Example validations
    print("\nExample Validations:\n")
    
    test_cases = [
        ("feature_validation_failures_total", "counter", ["feature_name", "validation_type", "severity"]),
        ("drift_score", "gauge", ["metric_name"]),
        ("scan_duration_seconds", "histogram", ["strategy", "outcome"]),
        ("invalid_metric_name", "counter", []),  # Should fail
        ("feature_validation_failures_total", "gauge", ["feature_name"]),  # Wrong type
    ]
    
    for name, metric_type, labels in test_cases:
        try:
            registry.validate_metric(name, metric_type, labels, raise_on_error=True)
            print(f"✅ {name}: VALID")
        except MetricsRegistryError as e:
            print(f"❌ {name}: INVALID")
            print(f"   {e}\n")
