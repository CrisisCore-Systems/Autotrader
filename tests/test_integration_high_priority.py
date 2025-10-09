"""Integration tests for high-priority issue resolutions.

Tests all five major enhancements working together:
1. Alert rule validation
2. Security scanning (simulated)
3. Backtest statistics
4. LLM client with fallback
5. Docker deployment (configuration validation)
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

# Issue 1: Alert Rule Validation
from scripts.validate_alert_rules import (
    validate_alert_rules,
    validate_condition_logic,
    validate_unit_normalization,
)

# Issue 3: Backtest Statistics
try:
    from src.pipeline.backtest_statistics import (
        bootstrap_confidence_interval,
        compute_ic_distribution,
        compute_risk_adjusted_metrics,
    )
    STATISTICS_AVAILABLE = True
except ImportError:
    STATISTICS_AVAILABLE = False

# Issue 4: LLM Configuration
from src.core.llm_config import (
    create_default_llm_config,
    create_groq_config,
    create_openai_config,
    LLMProvider,
    SchemaEnforcementMode,
)


class TestIntegration:
    """Integration tests for all high-priority resolutions."""
    
    def test_alert_rule_validation_integration(self):
        """Test end-to-end alert rule validation."""
        # Valid alert rule
        config = {
            "rules": [
                {
                    "id": "test_rule",
                    "description": "Test rule for integration",
                    "version": "v2",
                    "severity": "high",
                    "channels": ["slack"],
                    "condition": {
                        "type": "compound",
                        "operator": "AND",
                        "conditions": [
                            {
                                "metric": "gem_score",
                                "operator": "gte",
                                "threshold": 70,
                            },
                            {
                                "metric": "liquidity_usd",
                                "operator": "gte",
                                "threshold": 10000,
                                "unit": "usd"
                            }
                        ]
                    },
                    "escalation_policy": "immediate",
                    "suppression_duration": 3600,
                }
            ],
            "channels": {
                "slack": {"enabled": True, "rate_limit": 10}
            },
            "escalation_policies": {
                "immediate": {
                    "levels": [
                        {"delay": 0, "channels": ["slack"]}
                    ]
                }
            }
        }
        
        # Test condition logic validation
        condition = config["rules"][0]["condition"]
        errors = validate_condition_logic(condition)
        assert len(errors) == 0, f"Condition logic errors: {errors}"
        
        # Test unit normalization
        errors = validate_unit_normalization(config["rules"][0])
        assert len(errors) == 0, f"Unit normalization errors: {errors}"
    
    @pytest.mark.skipif(not STATISTICS_AVAILABLE, reason="Statistics module not available")
    def test_backtest_statistics_integration(self):
        """Test backtest statistics with realistic data."""
        # Simulate backtest returns
        returns = [0.05, 0.03, -0.02, 0.08, 0.01, -0.01, 0.06, 0.04, 0.02, -0.03]
        
        # Bootstrap confidence interval
        bootstrap_result = bootstrap_confidence_interval(returns, n_bootstrap=1000)
        
        assert bootstrap_result.mean > 0, "Expected positive mean return"
        assert bootstrap_result.ci_lower < bootstrap_result.mean < bootstrap_result.ci_upper
        assert bootstrap_result.std > 0
        
        # Risk-adjusted metrics
        risk_metrics = compute_risk_adjusted_metrics(returns)
        
        assert risk_metrics.total_return > 0
        assert risk_metrics.volatility > 0
        assert -5 < risk_metrics.sharpe_ratio < 5  # Reasonable range
        assert risk_metrics.max_drawdown >= 0
        assert 0 <= risk_metrics.win_rate <= 1
        
        # IC distribution (requires window data)
        window_predictions = [[0.05, 0.03, 0.08] for _ in range(5)]
        window_actuals = [[0.06, 0.02, 0.09] for _ in range(5)]
        
        ic_dist = compute_ic_distribution(window_predictions, window_actuals)
        
        assert -1 <= ic_dist.mean_ic <= 1  # Correlation range
        assert ic_dist.std_ic >= 0
        assert 0 <= ic_dist.positive_pct <= 100
    
    def test_llm_config_integration(self):
        """Test LLM configuration with multiple providers."""
        # Create config with fallback
        config = create_default_llm_config(enable_openai_fallback=True)
        
        # Verify primary provider
        assert config.primary_provider.provider == LLMProvider.GROQ
        assert config.primary_provider.model == "llama-3.1-70b-versatile"
        
        # Verify fallback chain
        assert len(config.fallback_providers) == 1
        assert config.fallback_providers[0].provider == LLMProvider.OPENAI
        
        # Test quota enforcement
        groq_config = create_groq_config()
        
        # Check quota reservation
        allowed, reason = groq_config.quota.check_and_reserve(
            tokens=1000,
            estimated_cost=0.01,
        )
        assert allowed, f"Quota check failed: {reason}"
        
        # Verify cost estimation
        cost = groq_config.estimate_cost(input_tokens=1000, output_tokens=500)
        assert cost > 0, "Cost should be positive"
        
        # Test global quota
        allowed, reason = config.check_global_quota(estimated_cost=10.0)
        assert allowed, "Global quota should allow reasonable cost"
        
        # Test schema enforcement modes
        assert config.schema_enforcement_mode in [
            SchemaEnforcementMode.STRICT,
            SchemaEnforcementMode.WARN,
            SchemaEnforcementMode.DISABLED,
        ]
    
    def test_docker_compose_validation(self):
        """Test docker-compose.yml configuration."""
        import yaml
        
        compose_path = Path("infra/docker-compose.yml")
        
        if not compose_path.exists():
            pytest.skip("docker-compose.yml not found")
        
        with compose_path.open() as f:
            compose_config = yaml.safe_load(f)
        
        # Verify all services have resource limits
        services_with_limits = [
            "api", "worker", "postgres", "vector"
        ]
        
        for service_name in services_with_limits:
            service = compose_config["services"][service_name]
            
            # Check resource limits exist
            assert "deploy" in service, f"{service_name} missing deploy config"
            assert "resources" in service["deploy"], f"{service_name} missing resources"
            
            resources = service["deploy"]["resources"]
            assert "limits" in resources, f"{service_name} missing limits"
            assert "reservations" in resources, f"{service_name} missing reservations"
            
            # Check health checks
            assert "healthcheck" in service, f"{service_name} missing healthcheck"
            
            # Check restart policy
            assert "restart" in service, f"{service_name} missing restart policy"
            
            # Check security (except postgres which needs some privileges)
            if service_name != "postgres":
                assert "security_opt" in service, f"{service_name} missing security_opt"
        
        # Verify persistent volumes
        volumes = compose_config["volumes"]
        assert "postgres-data" in volumes
        assert "milvus-data" in volumes
        
        # Verify network configuration
        assert "networks" in compose_config
        assert "autotrader-net" in compose_config["networks"]
    
    def test_security_pipeline_configuration(self):
        """Test GitHub Actions security pipeline."""
        import yaml
        
        workflow_path = Path(".github/workflows/security-scan.yml")
        
        if not workflow_path.exists():
            pytest.skip("security-scan.yml not found")
        
        with workflow_path.open() as f:
            workflow = yaml.safe_load(f)
        
        # Verify all required security jobs exist
        required_jobs = [
            "semgrep",
            "bandit",
            "trivy",
            "gitleaks",
            "trufflehog",
            "pip-audit",
            "sbom",
            "license-check",
        ]
        
        jobs = workflow["jobs"]
        
        for job_name in required_jobs:
            assert job_name in jobs, f"Missing required job: {job_name}"
        
        # Verify actions are pinned (not using @master or @latest)
        for job_name, job_config in jobs.items():
            if "steps" in job_config:
                for step in job_config["steps"]:
                    if "uses" in step:
                        uses = step["uses"]
                        # Should have SHA pinning (format: repo@sha256)
                        if "@" in uses:
                            version = uses.split("@")[1]
                            # Check it's not a branch/tag reference
                            assert not version.startswith("v"), \
                                f"Job {job_name} step uses tag instead of SHA: {uses}"
                            assert version not in ["master", "main", "latest"], \
                                f"Job {job_name} step uses unpinned version: {uses}"
    
    def test_semgrep_rules_coverage(self):
        """Test Semgrep rules configuration."""
        import yaml
        
        semgrep_path = Path("ci/semgrep.yml")
        
        if not semgrep_path.exists():
            pytest.skip("semgrep.yml not found")
        
        with semgrep_path.open() as f:
            semgrep_config = yaml.safe_load(f)
        
        rules = semgrep_config["rules"]
        
        # Verify critical security rules exist
        critical_rules = [
            "python-no-eval",
            "python-no-exec",
            "dangerous-yaml-load",
            "sql-injection-f-string",
            "hardcoded-private-key",
            "api-key-in-code",
        ]
        
        rule_ids = [rule["id"] for rule in rules]
        
        for critical_rule in critical_rules:
            assert critical_rule in rule_ids, f"Missing critical rule: {critical_rule}"
        
        # Verify all rules have required fields
        for rule in rules:
            assert "id" in rule
            assert "message" in rule
            assert "severity" in rule
            assert "languages" in rule
            assert rule["severity"] in ["ERROR", "WARNING", "INFO"]
    
    def test_production_deployment_documentation(self):
        """Verify production deployment documentation exists."""
        docs = [
            "PRODUCTION_DEPLOYMENT.md",
            "HIGH_PRIORITY_RESOLUTION_SUMMARY.md",
            ".env.production.template",
        ]
        
        for doc in docs:
            doc_path = Path(doc)
            assert doc_path.exists(), f"Missing documentation: {doc}"
            
            # Check file is not empty
            assert doc_path.stat().st_size > 0, f"Empty file: {doc}"


class TestEndToEndScenario:
    """End-to-end scenario tests."""
    
    @pytest.mark.skipif(not STATISTICS_AVAILABLE, reason="Statistics module not available")
    def test_complete_backtest_with_statistics(self):
        """Test complete backtest flow with enhanced statistics."""
        # Simulate backtest results
        precision_values = [0.65, 0.70, 0.68, 0.72, 0.69]
        returns = [0.05, 0.08, 0.03, 0.10, 0.06]
        
        # Bootstrap confidence intervals
        precision_ci = bootstrap_confidence_interval(precision_values, n_bootstrap=1000)
        returns_ci = bootstrap_confidence_interval(returns, n_bootstrap=1000)
        
        # Risk-adjusted metrics
        risk_metrics = compute_risk_adjusted_metrics(returns)
        
        # Build report
        report = {
            "precision_at_k": {
                "mean": round(sum(precision_values) / len(precision_values), 4),
                "bootstrap_ci": precision_ci.to_dict(),
            },
            "forward_return": {
                "median": round(sorted(returns)[len(returns) // 2], 4),
                "bootstrap_ci": returns_ci.to_dict(),
            },
            "risk_adjusted": risk_metrics.to_dict(),
        }
        
        # Validate report structure
        assert "precision_at_k" in report
        assert "forward_return" in report
        assert "risk_adjusted" in report
        
        # Validate metrics are reasonable
        assert 0 < report["precision_at_k"]["mean"] < 1
        assert report["risk_adjusted"]["sharpe_ratio"] > 0  # Positive returns
        assert report["risk_adjusted"]["win_rate"] > 0
    
    def test_llm_client_with_fallback_simulation(self):
        """Simulate LLM client with fallback chain."""
        # Create config with multiple providers
        primary = create_groq_config(
            tokens_per_minute=1000,
            max_cost_per_day=5.0,
        )
        fallback = create_openai_config(
            tokens_per_minute=500,
            max_cost_per_day=10.0,
        )
        
        # Verify provider chain
        from src.core.llm_config import LLMConfig
        
        config = LLMConfig(
            primary_provider=primary,
            fallback_providers=[fallback],
            schema_enforcement_mode=SchemaEnforcementMode.STRICT,
            max_total_cost_per_day_usd=20.0,
        )
        
        provider_chain = config.get_provider_chain()
        
        assert len(provider_chain) == 2
        assert provider_chain[0].provider == LLMProvider.GROQ
        assert provider_chain[1].provider == LLMProvider.OPENAI
        
        # Simulate cost tracking
        config.record_request(cost=0.50)
        assert config.total_cost_today_usd == 0.50
        
        config.record_request(cost=1.25)
        assert config.total_cost_today_usd == 1.75


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
