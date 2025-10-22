"""Tests for loading alert rules from YAML configuration."""

from pathlib import Path
import pytest

from src.alerts.rules import load_rules, AlertRule, CompoundCondition, SimpleCondition


def test_load_v1_and_v2_rules_from_yaml():
    """Test loading both v1 and v2 rules from the config file."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    
    # Should load multiple rules
    assert len(rules) > 0
    
    # Check that we have both v1 and v2 rules
    v1_rules = [r for r in rules if r.version == "v1"]
    v2_rules = [r for r in rules if r.version == "v2"]
    
    assert len(v1_rules) > 0, "Should have at least one v1 rule"
    assert len(v2_rules) > 0, "Should have at least one v2 rule"


def test_v2_rule_has_compound_condition():
    """Test that v2 rules have compound conditions."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    v2_rules = [r for r in rules if r.version == "v2"]
    
    # At least one v2 rule should have a compound condition
    compound_rules = [r for r in v2_rules if isinstance(r.condition, CompoundCondition)]
    assert len(compound_rules) > 0, "Should have v2 rules with compound conditions"


def test_v2_rule_fields_populated():
    """Test that v2-specific fields are populated correctly."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    v2_rules = [r for r in rules if r.version == "v2"]
    
    # Check first v2 rule
    rule = v2_rules[0]
    
    # Should have v2 fields
    assert rule.severity in ["info", "warning", "high", "critical"]
    assert rule.suppression_duration > 0
    assert rule.condition is not None


def test_nested_compound_conditions_loaded():
    """Test that nested compound conditions are loaded correctly."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    
    # Look for a rule with nested conditions
    # Example: "suspicious_high_score_token" has nested AND/OR
    nested_rule = None
    for rule in rules:
        if rule.id == "suspicious_high_score_token":
            nested_rule = rule
            break
    
    if nested_rule is None:
        pytest.skip("Test rule not found in config")
    
    assert isinstance(nested_rule.condition, CompoundCondition)
    assert nested_rule.condition.operator == "AND"
    
    # Should have at least one nested compound condition
    has_nested = any(
        isinstance(cond, CompoundCondition)
        for cond in nested_rule.condition.conditions
    )
    assert has_nested, "Should have nested compound conditions"


def test_v1_rule_backward_compatibility():
    """Test that v1 rules still load correctly."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    v1_rules = [r for r in rules if r.version == "v1"]
    
    # V1 rule should have old-style fields
    rule = v1_rules[0]
    assert rule.score_min >= 0
    assert rule.confidence_min >= 0
    assert isinstance(rule.safety_ok, bool)
    assert rule.cool_off_minutes > 0


def test_rule_evaluation_context():
    """Test that loaded rules can evaluate contexts."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    v2_rules = [r for r in rules if r.version == "v2"]
    
    # Get a simple rule
    rule = None
    for r in v2_rules:
        if isinstance(r.condition, SimpleCondition):
            rule = r
            break
    
    if rule is None:
        # Try with compound condition
        for r in v2_rules:
            rule = r
            break
    
    # Should be able to evaluate with context
    context = {
        "gem_score": 50,
        "confidence": 0.8,
        "safety_ok": True,
        "liquidity_usd": 10000,
        "honeypot_detected": False,
    }
    
    # Should not raise an error
    result = rule.matches_v2(context)
    assert isinstance(result, bool)


def test_all_rules_have_required_fields():
    """Test that all loaded rules have required fields."""
    config_path = Path("configs/alert_rules.yaml")
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    rules = load_rules(config_path)
    
    for rule in rules:
        assert rule.id, f"Rule missing ID"
        assert rule.version in ["v1", "v2"], f"Invalid version for rule {rule.id}"
        
        if rule.version == "v2":
            assert rule.condition is not None, f"V2 rule {rule.id} missing condition"
            assert rule.severity, f"V2 rule {rule.id} missing severity"
