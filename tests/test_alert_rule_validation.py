"""Unit tests for alert rule validation and condition evaluation."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any, Dict

from scripts.validate_alert_rules import (
    AlertRuleValidationError,
    validate_unit_normalization,
    validate_condition_logic,
    validate_channel_references,
    validate_escalation_policy_references,
    validate_duplicate_rule_ids,
    validate_alert_rules,
)


class TestUnitNormalization:
    """Test unit normalization validation."""
    
    def test_usd_metric_requires_unit(self):
        """Metrics with 'usd' should require unit field."""
        rule = {
            "id": "test_rule",
            "condition": {
                "metric": "liquidity_usd",
                "operator": "gt",
                "threshold": 10000,
                # Missing 'unit' field
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) > 0
        assert any("missing 'unit' field" in e for e in errors)
    
    def test_usd_metric_with_correct_unit(self):
        """USD metric with correct unit should pass."""
        rule = {
            "id": "test_rule",
            "condition": {
                "metric": "liquidity_usd",
                "operator": "gt",
                "threshold": 10000,
                "unit": "usd"
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) == 0
    
    def test_percent_threshold_range(self):
        """Percent values should be within reasonable range."""
        rule = {
            "id": "test_rule",
            "condition": {
                "metric": "price_change_24h",
                "operator": "gt",
                "threshold": 5000,  # Unreasonable: 5000%
                "unit": "percent"
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) > 0
        assert any("outside reasonable range" in e for e in errors)
    
    def test_ratio_must_be_positive(self):
        """Ratio values should not be negative."""
        rule = {
            "id": "test_rule",
            "condition": {
                "metric": "buy_sell_ratio",
                "operator": "lt",
                "threshold": -5.0,  # Invalid negative ratio
                "unit": "ratio"
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) > 0
        assert any("should not be negative" in e for e in errors)
    
    def test_in_operator_requires_array(self):
        """'in' operator should have array threshold."""
        rule = {
            "id": "test_rule",
            "condition": {
                "metric": "status",
                "operator": "in",
                "threshold": "active"  # Should be array
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) > 0
        assert any("requires array threshold" in e for e in errors)
    
    def test_comparison_operator_requires_numeric(self):
        """Comparison operators should have numeric thresholds."""
        rule = {
            "id": "test_rule",
            "condition": {
                "metric": "gem_score",
                "operator": "gte",
                "threshold": "high"  # Should be number
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) > 0
        assert any("requires numeric threshold" in e for e in errors)
    
    def test_nested_compound_condition_validation(self):
        """Unit validation should work on nested conditions."""
        rule = {
            "id": "test_rule",
            "condition": {
                "type": "compound",
                "operator": "AND",
                "conditions": [
                    {
                        "metric": "market_cap_usd",
                        "operator": "gt",
                        "threshold": 100000,
                        # Missing unit
                    },
                    {
                        "metric": "volume_24h",
                        "operator": "gt",
                        "threshold": 50000,
                        "unit": "usd"
                    }
                ]
            }
        }
        
        errors = validate_unit_normalization(rule)
        assert len(errors) > 0


class TestConditionLogic:
    """Test AND/OR/NOT condition logic validation."""
    
    def test_and_requires_minimum_two_conditions(self):
        """AND operator must have at least 2 conditions."""
        condition = {
            "type": "compound",
            "operator": "AND",
            "conditions": [
                {"metric": "gem_score", "operator": "gte", "threshold": 70}
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) > 0
        assert any("must have at least 2 conditions" in e for e in errors)
    
    def test_or_requires_minimum_two_conditions(self):
        """OR operator must have at least 2 conditions."""
        condition = {
            "type": "compound",
            "operator": "OR",
            "conditions": [
                {"metric": "gem_score", "operator": "gte", "threshold": 70}
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) > 0
    
    def test_not_requires_exactly_one_condition(self):
        """NOT operator must have exactly 1 condition."""
        condition = {
            "type": "compound",
            "operator": "NOT",
            "conditions": [
                {"metric": "honeypot_detected", "operator": "eq", "threshold": True},
                {"metric": "scam_detected", "operator": "eq", "threshold": True}
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) > 0
        assert any("must have exactly 1 condition" in e for e in errors)
    
    def test_valid_and_condition(self):
        """Valid AND condition with 2+ conditions should pass."""
        condition = {
            "type": "compound",
            "operator": "AND",
            "conditions": [
                {"metric": "gem_score", "operator": "gte", "threshold": 70},
                {"metric": "liquidity_usd", "operator": "gte", "threshold": 10000}
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) == 0
    
    def test_valid_not_condition(self):
        """Valid NOT condition with 1 condition should pass."""
        condition = {
            "type": "compound",
            "operator": "NOT",
            "conditions": [
                {"metric": "honeypot_detected", "operator": "eq", "threshold": True}
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) == 0
    
    def test_excessive_nesting_warning(self):
        """Excessive nesting should produce warning."""
        # Create deeply nested condition (6 levels)
        condition = {
            "type": "compound",
            "operator": "AND",
            "conditions": [
                {"metric": "a", "operator": "gt", "threshold": 1},
                {
                    "type": "compound",
                    "operator": "OR",
                    "conditions": [
                        {"metric": "b", "operator": "gt", "threshold": 2},
                        {
                            "type": "compound",
                            "operator": "AND",
                            "conditions": [
                                {"metric": "c", "operator": "gt", "threshold": 3},
                                {
                                    "type": "compound",
                                    "operator": "OR",
                                    "conditions": [
                                        {"metric": "d", "operator": "gt", "threshold": 4},
                                        {
                                            "type": "compound",
                                            "operator": "AND",
                                            "conditions": [
                                                {"metric": "e", "operator": "gt", "threshold": 5},
                                                {
                                                    "type": "compound",
                                                    "operator": "OR",
                                                    "conditions": [
                                                        {"metric": "f", "operator": "gt", "threshold": 6},
                                                        {"metric": "g", "operator": "gt", "threshold": 7},
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) > 0
        assert any("Excessive nesting depth" in e for e in errors)
    
    def test_recursive_validation_of_nested_conditions(self):
        """Nested conditions should be recursively validated."""
        condition = {
            "type": "compound",
            "operator": "AND",
            "conditions": [
                {"metric": "gem_score", "operator": "gte", "threshold": 70},
                {
                    "type": "compound",
                    "operator": "OR",
                    "conditions": [
                        # This inner condition is invalid (NOT with 2 conditions)
                        {
                            "type": "compound",
                            "operator": "NOT",
                            "conditions": [
                                {"metric": "a", "operator": "eq", "threshold": 1},
                                {"metric": "b", "operator": "eq", "threshold": 2},
                            ]
                        }
                    ]
                }
            ]
        }
        
        errors = validate_condition_logic(condition)
        assert len(errors) > 0


class TestChannelReferences:
    """Test channel reference validation."""
    
    def test_undefined_channel_in_rule(self):
        """Rule referencing undefined channel should error."""
        config = {
            "channels": {
                "slack": {"enabled": True}
            },
            "rules": [
                {
                    "id": "test_rule",
                    "channels": ["slack", "undefined_channel"]
                }
            ]
        }
        
        errors = validate_channel_references(config)
        assert len(errors) > 0
        assert any("undefined_channel" in e for e in errors)
    
    def test_all_channels_defined(self):
        """All referenced channels defined should pass."""
        config = {
            "channels": {
                "slack": {"enabled": True},
                "telegram": {"enabled": True}
            },
            "rules": [
                {
                    "id": "test_rule",
                    "channels": ["slack", "telegram"]
                }
            ]
        }
        
        errors = validate_channel_references(config)
        assert len(errors) == 0
    
    def test_undefined_channel_in_escalation_policy(self):
        """Escalation policy with undefined channel should error."""
        config = {
            "channels": {
                "slack": {"enabled": True}
            },
            "escalation_policies": {
                "progressive": {
                    "levels": [
                        {"delay": 0, "channels": ["slack"]},
                        {"delay": 300, "channels": ["undefined_pagerduty"]}
                    ]
                }
            }
        }
        
        errors = validate_channel_references(config)
        assert len(errors) > 0
        assert any("undefined_pagerduty" in e for e in errors)


class TestEscalationPolicyReferences:
    """Test escalation policy reference validation."""
    
    def test_undefined_escalation_policy(self):
        """Rule with undefined escalation_policy should error."""
        config = {
            "escalation_policies": {
                "immediate": {"levels": []}
            },
            "rules": [
                {
                    "id": "test_rule",
                    "escalation_policy": "undefined_policy"
                }
            ]
        }
        
        errors = validate_escalation_policy_references(config)
        assert len(errors) > 0
        assert any("undefined_policy" in e for e in errors)
    
    def test_builtin_none_policy_allowed(self):
        """Built-in 'none' policy should be allowed."""
        config = {
            "escalation_policies": {},
            "rules": [
                {
                    "id": "test_rule",
                    "escalation_policy": "none"
                }
            ]
        }
        
        errors = validate_escalation_policy_references(config)
        assert len(errors) == 0


class TestDuplicateRuleIds:
    """Test duplicate rule ID detection."""
    
    def test_duplicate_rule_ids(self):
        """Duplicate rule IDs should be detected."""
        config = {
            "rules": [
                {"id": "rule_1"},
                {"id": "rule_2"},
                {"id": "rule_1"},  # Duplicate
            ]
        }
        
        errors = validate_duplicate_rule_ids(config)
        assert len(errors) > 0
        assert any("rule_1" in e for e in errors)
    
    def test_unique_rule_ids(self):
        """Unique rule IDs should pass."""
        config = {
            "rules": [
                {"id": "rule_1"},
                {"id": "rule_2"},
                {"id": "rule_3"},
            ]
        }
        
        errors = validate_duplicate_rule_ids(config)
        assert len(errors) == 0


class TestConditionEvaluation:
    """Test runtime evaluation of AND/OR/NOT conditions."""
    
    def evaluate_condition(self, condition: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """Evaluate a condition tree against metric values."""
        if condition.get("type") == "compound":
            operator = condition["operator"]
            conditions = condition["conditions"]
            
            if operator == "AND":
                return all(self.evaluate_condition(c, metrics) for c in conditions)
            elif operator == "OR":
                return any(self.evaluate_condition(c, metrics) for c in conditions)
            elif operator == "NOT":
                return not self.evaluate_condition(conditions[0], metrics)
            else:
                raise ValueError(f"Unknown operator: {operator}")
        
        # Leaf condition
        metric_name = condition["metric"]
        operator = condition["operator"]
        threshold = condition["threshold"]
        value = metrics.get(metric_name)
        
        if operator == "eq":
            return value == threshold
        elif operator == "ne":
            return value != threshold
        elif operator == "lt":
            return value < threshold
        elif operator == "lte":
            return value <= threshold
        elif operator == "gt":
            return value > threshold
        elif operator == "gte":
            return value >= threshold
        elif operator == "in":
            return value in threshold
        elif operator == "not_in":
            return value not in threshold
        elif operator == "contains":
            return threshold in str(value)
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    def test_and_evaluation(self):
        """Test AND condition evaluation."""
        condition = {
            "type": "compound",
            "operator": "AND",
            "conditions": [
                {"metric": "gem_score", "operator": "gte", "threshold": 70},
                {"metric": "liquidity_usd", "operator": "gte", "threshold": 10000}
            ]
        }
        
        # Both conditions true
        assert self.evaluate_condition(condition, {"gem_score": 80, "liquidity_usd": 15000}) is True
        
        # One condition false
        assert self.evaluate_condition(condition, {"gem_score": 80, "liquidity_usd": 5000}) is False
        
        # Both conditions false
        assert self.evaluate_condition(condition, {"gem_score": 60, "liquidity_usd": 5000}) is False
    
    def test_or_evaluation(self):
        """Test OR condition evaluation."""
        condition = {
            "type": "compound",
            "operator": "OR",
            "conditions": [
                {"metric": "gem_score", "operator": "gte", "threshold": 70},
                {"metric": "liquidity_usd", "operator": "gte", "threshold": 10000}
            ]
        }
        
        # Both conditions true
        assert self.evaluate_condition(condition, {"gem_score": 80, "liquidity_usd": 15000}) is True
        
        # One condition true
        assert self.evaluate_condition(condition, {"gem_score": 80, "liquidity_usd": 5000}) is True
        assert self.evaluate_condition(condition, {"gem_score": 60, "liquidity_usd": 15000}) is True
        
        # Both conditions false
        assert self.evaluate_condition(condition, {"gem_score": 60, "liquidity_usd": 5000}) is False
    
    def test_not_evaluation(self):
        """Test NOT condition evaluation."""
        condition = {
            "type": "compound",
            "operator": "NOT",
            "conditions": [
                {"metric": "honeypot_detected", "operator": "eq", "threshold": True}
            ]
        }
        
        assert self.evaluate_condition(condition, {"honeypot_detected": False}) is True
        assert self.evaluate_condition(condition, {"honeypot_detected": True}) is False
    
    def test_nested_compound_evaluation(self):
        """Test complex nested condition evaluation."""
        # (A AND B) OR (C AND NOT D)
        condition = {
            "type": "compound",
            "operator": "OR",
            "conditions": [
                {
                    "type": "compound",
                    "operator": "AND",
                    "conditions": [
                        {"metric": "A", "operator": "gt", "threshold": 10},
                        {"metric": "B", "operator": "lt", "threshold": 5}
                    ]
                },
                {
                    "type": "compound",
                    "operator": "AND",
                    "conditions": [
                        {"metric": "C", "operator": "eq", "threshold": True},
                        {
                            "type": "compound",
                            "operator": "NOT",
                            "conditions": [
                                {"metric": "D", "operator": "eq", "threshold": True}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # First branch true: A=15, B=3
        assert self.evaluate_condition(condition, {"A": 15, "B": 3, "C": False, "D": True}) is True
        
        # Second branch true: C=True, D=False
        assert self.evaluate_condition(condition, {"A": 5, "B": 10, "C": True, "D": False}) is True
        
        # Both branches false
        assert self.evaluate_condition(condition, {"A": 5, "B": 10, "C": False, "D": True}) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
