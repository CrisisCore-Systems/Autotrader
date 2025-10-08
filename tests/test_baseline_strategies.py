"""Tests for baseline strategy comparators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pytest

from backtest.baseline_strategies import (
    BaselineResult,
    BaselineStrategy,
    CapWeightedStrategy,
    RandomStrategy,
    SimpleMomentumStrategy,
    compare_to_baselines,
    evaluate_all_baselines,
    format_baseline_comparison,
)


@dataclass
class MockTokenSnapshot:
    """Mock token snapshot for testing."""
    
    token: str
    features: Dict[str, float]
    future_return_7d: float


class TestRandomStrategy:
    """Tests for RandomStrategy."""
    
    def test_random_strategy_name(self):
        """Test strategy name."""
        strategy = RandomStrategy()
        assert strategy.get_name() == "random"
    
    def test_random_strategy_selects_k_assets(self):
        """Test that random strategy selects exactly K assets."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.1),
            MockTokenSnapshot("TOKEN2", {}, 0.2),
            MockTokenSnapshot("TOKEN3", {}, -0.05),
            MockTokenSnapshot("TOKEN4", {}, 0.15),
            MockTokenSnapshot("TOKEN5", {}, 0.3),
        ]
        
        strategy = RandomStrategy()
        selected = strategy.select_assets(snapshots, top_k=3, seed=42)
        
        assert len(selected) == 3
        assert all(snap in snapshots for snap in selected)
    
    def test_random_strategy_reproducible(self):
        """Test that random strategy is reproducible with seed."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.1),
            MockTokenSnapshot("TOKEN2", {}, 0.2),
            MockTokenSnapshot("TOKEN3", {}, -0.05),
            MockTokenSnapshot("TOKEN4", {}, 0.15),
            MockTokenSnapshot("TOKEN5", {}, 0.3),
        ]
        
        strategy = RandomStrategy()
        selected1 = strategy.select_assets(snapshots, top_k=3, seed=42)
        selected2 = strategy.select_assets(snapshots, top_k=3, seed=42)
        
        assert selected1 == selected2
    
    def test_random_strategy_evaluate(self):
        """Test random strategy evaluation."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.1),
            MockTokenSnapshot("TOKEN2", {}, 0.2),
            MockTokenSnapshot("TOKEN3", {}, -0.05),
        ]
        
        strategy = RandomStrategy()
        result = strategy.evaluate(snapshots, top_k=2, seed=42)
        
        assert result.strategy_name == "random"
        assert 0.0 <= result.precision_at_k <= 1.0
        assert len(result.selected_assets) == 2


class TestCapWeightedStrategy:
    """Tests for CapWeightedStrategy."""
    
    def test_cap_weighted_strategy_name(self):
        """Test strategy name."""
        strategy = CapWeightedStrategy()
        assert strategy.get_name() == "cap_weighted"
    
    def test_cap_weighted_selects_by_market_cap(self):
        """Test that cap weighted strategy selects by market cap."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"MarketCap": 1000000}, 0.1),
            MockTokenSnapshot("TOKEN2", {"MarketCap": 5000000}, 0.2),
            MockTokenSnapshot("TOKEN3", {"MarketCap": 2000000}, -0.05),
            MockTokenSnapshot("TOKEN4", {"MarketCap": 500000}, 0.15),
        ]
        
        strategy = CapWeightedStrategy()
        selected = strategy.select_assets(snapshots, top_k=2)
        
        assert len(selected) == 2
        assert selected[0].token == "TOKEN2"  # Highest market cap
        assert selected[1].token == "TOKEN3"  # Second highest
    
    def test_cap_weighted_handles_missing_market_cap(self):
        """Test fallback when market cap is missing."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"volume_24h_usd": 10000}, 0.1),
            MockTokenSnapshot("TOKEN2", {"volume_24h_usd": 50000}, 0.2),
            MockTokenSnapshot("TOKEN3", {}, -0.05),
        ]
        
        strategy = CapWeightedStrategy()
        selected = strategy.select_assets(snapshots, top_k=2)
        
        assert len(selected) == 2
        # Should select by volume as fallback
        assert selected[0].token == "TOKEN2"
    
    def test_cap_weighted_evaluate(self):
        """Test cap weighted strategy evaluation."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"MarketCap": 1000000}, 0.1),
            MockTokenSnapshot("TOKEN2", {"MarketCap": 5000000}, 0.2),
            MockTokenSnapshot("TOKEN3", {"MarketCap": 2000000}, -0.05),
        ]
        
        strategy = CapWeightedStrategy()
        result = strategy.evaluate(snapshots, top_k=2)
        
        assert result.strategy_name == "cap_weighted"
        # Selects TOKEN2 (0.2) and TOKEN3 (-0.05) by market cap
        assert result.precision_at_k == 0.5  # Only TOKEN2 has positive return (1/2)
        assert result.average_return_at_k == pytest.approx(0.075, abs=0.001)  # (0.2 + -0.05) / 2


class TestSimpleMomentumStrategy:
    """Tests for SimpleMomentumStrategy."""
    
    def test_momentum_strategy_name(self):
        """Test strategy name."""
        strategy = SimpleMomentumStrategy()
        assert strategy.get_name() == "simple_momentum"
    
    def test_momentum_selects_by_price_change(self):
        """Test that momentum strategy selects by price change."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"PriceChange7d": 0.05}, 0.1),
            MockTokenSnapshot("TOKEN2", {"PriceChange7d": 0.20}, 0.2),
            MockTokenSnapshot("TOKEN3", {"PriceChange7d": 0.10}, -0.05),
            MockTokenSnapshot("TOKEN4", {"PriceChange7d": -0.05}, 0.15),
        ]
        
        strategy = SimpleMomentumStrategy()
        selected = strategy.select_assets(snapshots, top_k=2)
        
        assert len(selected) == 2
        assert selected[0].token == "TOKEN2"  # Highest momentum
        assert selected[1].token == "TOKEN3"  # Second highest
    
    def test_momentum_handles_missing_momentum(self):
        """Test fallback when momentum feature is missing."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"price_usd": 100, "price_usd_7d_ago": 90}, 0.1),
            MockTokenSnapshot("TOKEN2", {"price_usd": 150, "price_usd_7d_ago": 100}, 0.2),
            MockTokenSnapshot("TOKEN3", {}, -0.05),
        ]
        
        strategy = SimpleMomentumStrategy()
        selected = strategy.select_assets(snapshots, top_k=2)
        
        assert len(selected) == 2
        # Should compute from price features
        assert selected[0].token == "TOKEN2"  # (150-100)/100 = 0.5
    
    def test_momentum_evaluate(self):
        """Test momentum strategy evaluation."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"PriceChange7d": 0.05}, 0.1),
            MockTokenSnapshot("TOKEN2", {"PriceChange7d": 0.20}, 0.2),
            MockTokenSnapshot("TOKEN3", {"PriceChange7d": 0.10}, -0.05),
        ]
        
        strategy = SimpleMomentumStrategy()
        result = strategy.evaluate(snapshots, top_k=2)
        
        assert result.strategy_name == "simple_momentum"
        # Selects TOKEN2 and TOKEN3
        assert result.precision_at_k == 0.5  # Only TOKEN2 has positive return
        assert result.average_return_at_k == pytest.approx(0.075, abs=0.001)


class TestEvaluateAllBaselines:
    """Tests for evaluate_all_baselines function."""
    
    def test_evaluate_all_baselines(self):
        """Test that all baselines are evaluated."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"MarketCap": 1000000, "PriceChange7d": 0.05}, 0.1),
            MockTokenSnapshot("TOKEN2", {"MarketCap": 5000000, "PriceChange7d": 0.20}, 0.2),
            MockTokenSnapshot("TOKEN3", {"MarketCap": 2000000, "PriceChange7d": 0.10}, -0.05),
        ]
        
        results = evaluate_all_baselines(snapshots, top_k=2, seed=42)
        
        assert "random" in results
        assert "cap_weighted" in results
        assert "simple_momentum" in results
        
        assert isinstance(results["random"], BaselineResult)
        assert isinstance(results["cap_weighted"], BaselineResult)
        assert isinstance(results["simple_momentum"], BaselineResult)
    
    def test_evaluate_custom_strategies(self):
        """Test evaluating custom strategy list."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {"MarketCap": 1000000}, 0.1),
            MockTokenSnapshot("TOKEN2", {"MarketCap": 5000000}, 0.2),
        ]
        
        strategies = [RandomStrategy()]
        results = evaluate_all_baselines(snapshots, top_k=1, strategies=strategies)
        
        assert len(results) == 1
        assert "random" in results


class TestCompareToBaselines:
    """Tests for compare_to_baselines function."""
    
    def test_compare_to_baselines(self):
        """Test comparison calculation."""
        baseline_results = {
            "random": BaselineResult("random", 0.5, 0.02, ["TOKEN1", "TOKEN2"]),
            "cap_weighted": BaselineResult("cap_weighted", 0.6, 0.03, ["TOKEN1", "TOKEN3"]),
        }
        
        comparisons = compare_to_baselines(0.7, 0.05, baseline_results)
        
        assert "random" in comparisons
        assert "cap_weighted" in comparisons
        
        # Check random comparison
        random_comp = comparisons["random"]
        assert random_comp["precision_improvement"] == pytest.approx(0.2, abs=0.001)
        assert random_comp["return_improvement"] == pytest.approx(0.03, abs=0.001)
        assert random_comp["precision_pct"] == pytest.approx(40.0, abs=0.1)
        assert random_comp["outperforms"] is True
        
        # Check cap_weighted comparison
        cap_comp = comparisons["cap_weighted"]
        assert cap_comp["precision_improvement"] == pytest.approx(0.1, abs=0.001)
        assert cap_comp["return_improvement"] == pytest.approx(0.02, abs=0.001)
        assert cap_comp["outperforms"] is True
    
    def test_compare_underperformance(self):
        """Test comparison when GemScore underperforms."""
        baseline_results = {
            "random": BaselineResult("random", 0.8, 0.10, ["TOKEN1", "TOKEN2"]),
        }
        
        comparisons = compare_to_baselines(0.6, 0.05, baseline_results)
        
        random_comp = comparisons["random"]
        assert random_comp["precision_improvement"] < 0
        assert random_comp["return_improvement"] < 0
        assert random_comp["outperforms"] is False


class TestFormatBaselineComparison:
    """Tests for format_baseline_comparison function."""
    
    def test_format_baseline_comparison(self):
        """Test formatting of baseline comparison."""
        gem_score_result = {
            "precision": 0.7,
            "return": 0.05,
        }
        baseline_results = {
            "random": BaselineResult("random", 0.5, 0.02, ["TOKEN1", "TOKEN2"]),
            "cap_weighted": BaselineResult("cap_weighted", 0.6, 0.03, ["TOKEN1", "TOKEN3"]),
        }
        
        output = format_baseline_comparison(gem_score_result, baseline_results)
        
        assert "BASELINE COMPARISONS" in output
        assert "GemScore Performance" in output
        assert "Precision@K: 0.700" in output
        assert "Avg Return:  0.0500" in output
        assert "Random:" in output
        assert "Cap Weighted:" in output
        assert "✅ Outperforms" in output or "Outperforms" in output


class TestBaselineResult:
    """Tests for BaselineResult dataclass."""
    
    def test_baseline_result_creation(self):
        """Test creating baseline result."""
        result = BaselineResult(
            strategy_name="test",
            precision_at_k=0.5,
            average_return_at_k=0.03,
            selected_assets=["TOKEN1", "TOKEN2"],
        )
        
        assert result.strategy_name == "test"
        assert result.precision_at_k == 0.5
        assert result.average_return_at_k == 0.03
        assert result.selected_assets == ["TOKEN1", "TOKEN2"]
        assert result.metadata is None
    
    def test_baseline_result_with_metadata(self):
        """Test baseline result with metadata."""
        result = BaselineResult(
            strategy_name="test",
            precision_at_k=0.5,
            average_return_at_k=0.03,
            selected_assets=["TOKEN1"],
            metadata={"avg_market_cap": 1000000.0},
        )
        
        assert result.metadata == {"avg_market_cap": 1000000.0}


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_snapshots(self):
        """Test handling of empty snapshots."""
        strategy = RandomStrategy()
        selected = strategy.select_assets([], top_k=5)
        
        assert len(selected) == 0
    
    def test_top_k_larger_than_snapshots(self):
        """Test when top_k is larger than available snapshots."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.1),
            MockTokenSnapshot("TOKEN2", {}, 0.2),
        ]
        
        strategy = RandomStrategy()
        selected = strategy.select_assets(snapshots, top_k=10, seed=42)
        
        assert len(selected) == 2  # Should return all available
    
    def test_all_negative_returns(self):
        """Test precision calculation with all negative returns."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, -0.1),
            MockTokenSnapshot("TOKEN2", {}, -0.2),
            MockTokenSnapshot("TOKEN3", {}, -0.05),
        ]
        
        strategy = RandomStrategy()
        result = strategy.evaluate(snapshots, top_k=2, seed=42)
        
        assert result.precision_at_k == 0.0  # No positive returns
        assert result.average_return_at_k < 0
    
    def test_mixed_returns(self):
        """Test with mixed positive and negative returns."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.1),
            MockTokenSnapshot("TOKEN2", {}, -0.2),
            MockTokenSnapshot("TOKEN3", {}, 0.05),
            MockTokenSnapshot("TOKEN4", {}, -0.1),
        ]
        
        strategy = RandomStrategy()
        result = strategy.evaluate(snapshots, top_k=2, seed=42)
        
        assert 0.0 <= result.precision_at_k <= 1.0
        assert len(result.selected_assets) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
