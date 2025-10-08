"""
Enhanced Modules Tests

Tests for enhanced reliability infrastructure including SLA monitoring,
circuit breakers, cache policies, orderflow clients, and Twitter integration.

Run with: pytest tests/test_enhanced_modules.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ===== SLA Monitor Tests =====

class TestSLAMonitor:
    """Test suite for SLA monitoring"""

    @pytest.fixture
    def sla_monitor(self):
        """Create SLA monitor instance"""
        from src.services.reliability import SLAMonitor
        return SLAMonitor()

    def test_register_service(self, sla_monitor):
        """Test registering a service for SLA monitoring"""
        result = sla_monitor.register(
            service_name="api_service",
            target_uptime=99.9,
            max_latency_ms=500
        )
        assert result["registered"] is True

    def test_record_success_metric(self, sla_monitor):
        """Test recording successful request"""
        sla_monitor.register("test_service")
        sla_monitor.record_request("test_service", latency_ms=200, success=True)

        status = sla_monitor.get_status("test_service")
        assert status["success_rate"] > 0

    def test_record_failure_metric(self, sla_monitor):
        """Test recording failed request"""
        sla_monitor.register("test_service")
        sla_monitor.record_request("test_service", latency_ms=1000, success=False)

        status = sla_monitor.get_status("test_service")
        assert status["error_count"] > 0

    def test_calculate_uptime(self, sla_monitor):
        """Test uptime calculation"""
        sla_monitor.register("test_service")

        # Record mix of success/failure
        for i in range(10):
            sla_monitor.record_request("test_service", latency_ms=200, success=i < 9)

        status = sla_monitor.get_status("test_service")
        assert 0 <= status["uptime_pct"] <= 100

    def test_sla_breach_detection(self, sla_monitor):
        """Test detection of SLA breaches"""
        sla_monitor.register("test_service", target_uptime=99.0)

        # Cause enough failures to breach SLA
        for _ in range(10):
            sla_monitor.record_request("test_service", latency_ms=200, success=False)

        status = sla_monitor.get_status("test_service")
        assert status["breach_detected"] is True

    def test_latency_percentiles(self, sla_monitor):
        """Test latency percentile calculations"""
        sla_monitor.register("test_service")

        latencies = [100, 200, 300, 400, 500]
        for lat in latencies:
            sla_monitor.record_request("test_service", latency_ms=lat, success=True)

        stats = sla_monitor.get_latency_stats("test_service")
        assert "p50" in stats or "p95" in stats or "p99" in stats


# ===== Circuit Breaker Tests =====

class TestCircuitBreaker:
    """Test suite for circuit breaker pattern"""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance"""
        from src.services.reliability import CircuitBreaker
        return CircuitBreaker(failure_threshold=3, timeout=5)

    def test_initial_state_closed(self, circuit_breaker):
        """Test circuit breaker starts in closed state"""
        assert circuit_breaker.state == "closed"
        assert circuit_breaker.can_request() is True

    def test_transition_to_open(self, circuit_breaker):
        """Test transition from closed to open"""
        # Record failures to reach threshold
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == "open"
        assert circuit_breaker.can_request() is False

    def test_transition_to_half_open(self, circuit_breaker):
        """Test transition from open to half-open"""
        # Open the circuit
        for _ in range(3):
            circuit_breaker.record_failure()

        # Wait for timeout (use short timeout for testing)
        circuit_breaker.timeout = 0.1
        time.sleep(0.15)

        # Should transition to half-open
        assert circuit_breaker.can_request() is True

    def test_half_open_to_closed_on_success(self, circuit_breaker):
        """Test transition from half-open to closed on success"""
        # Open the circuit
        for _ in range(3):
            circuit_breaker.record_failure()

        # Transition to half-open
        circuit_breaker.timeout = 0.1
        time.sleep(0.15)

        # Record success
        circuit_breaker.record_success()

        # Should close
        assert circuit_breaker.state == "closed"

    def test_half_open_to_open_on_failure(self, circuit_breaker):
        """Test transition from half-open back to open on failure"""
        # Open the circuit
        for _ in range(3):
            circuit_breaker.record_failure()

        # Transition to half-open
        circuit_breaker.timeout = 0.1
        time.sleep(0.15)

        # Record failure
        circuit_breaker.record_failure()

        # Should reopen
        assert circuit_breaker.state == "open"

    def test_success_resets_failure_count(self, circuit_breaker):
        """Test successful requests reset failure count"""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()

        # Should still be closed
        assert circuit_breaker.state == "closed"


# ===== Cache Policy Tests =====

class TestCachePolicy:
    """Test suite for cache policy"""

    @pytest.fixture
    def cache_policy(self):
        """Create cache policy instance"""
        from src.services.reliability import CachePolicy
        return CachePolicy(ttl_seconds=60)

    def test_set_and_get(self, cache_policy):
        """Test basic set and get operations"""
        cache_policy.set("key1", "value1")
        assert cache_policy.get("key1") == "value1"

    def test_get_nonexistent_key(self, cache_policy):
        """Test getting non-existent key returns None"""
        assert cache_policy.get("nonexistent") is None

    def test_ttl_expiration(self, cache_policy):
        """Test cache entries expire after TTL"""
        cache_policy.ttl_seconds = 0.1
        cache_policy.set("key1", "value1")

        time.sleep(0.15)
        assert cache_policy.get("key1") is None

    def test_delete_key(self, cache_policy):
        """Test deleting cache entries"""
        cache_policy.set("key1", "value1")
        cache_policy.delete("key1")
        assert cache_policy.get("key1") is None

    def test_clear_cache(self, cache_policy):
        """Test clearing entire cache"""
        cache_policy.set("key1", "value1")
        cache_policy.set("key2", "value2")
        cache_policy.clear()

        assert cache_policy.get("key1") is None
        assert cache_policy.get("key2") is None

    def test_cache_hit_rate(self, cache_policy):
        """Test cache hit rate tracking"""
        cache_policy.set("key1", "value1")

        # Hits
        cache_policy.get("key1")
        cache_policy.get("key1")

        # Miss
        cache_policy.get("key2")

        stats = cache_policy.get_stats()
        assert stats["hit_rate"] > 0


# ===== Adaptive Cache Policy Tests =====

class TestAdaptiveCachePolicy:
    """Test suite for adaptive cache policy"""

    @pytest.fixture
    def adaptive_cache(self):
        """Create adaptive cache policy instance"""
        from src.services.reliability import AdaptiveCachePolicy
        return AdaptiveCachePolicy(base_ttl=60)

    def test_adjust_ttl_on_access_pattern(self, adaptive_cache):
        """Test TTL adjustment based on access patterns"""
        # Frequently accessed key
        for _ in range(10):
            adaptive_cache.get("hot_key")

        # Check TTL increased
        assert adaptive_cache.get_ttl("hot_key") > 60

    def test_decrease_ttl_for_cold_keys(self, adaptive_cache):
        """Test TTL decrease for rarely accessed keys"""
        adaptive_cache.set("cold_key", "value")

        # Don't access for a while
        time.sleep(0.1)

        # TTL should not have increased
        assert adaptive_cache.get_ttl("cold_key") <= 60

    def test_evict_least_recently_used(self, adaptive_cache):
        """Test LRU eviction"""
        adaptive_cache.max_size = 3

        adaptive_cache.set("key1", "value1")
        adaptive_cache.set("key2", "value2")
        adaptive_cache.set("key3", "value3")

        # Access key1 to make it recently used
        adaptive_cache.get("key1")

        # Add key4, should evict key2
        adaptive_cache.set("key4", "value4")

        assert adaptive_cache.get("key1") is not None
        assert adaptive_cache.get("key2") is None


# ===== OrderFlow Client Tests =====

class TestOrderFlowClients:
    """Test suite for orderflow data clients"""

    def test_binance_client_fetch_trades(self):
        """Test fetching trades from Binance"""
        from src.services.orderflow import BinanceClient

        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = [
                {"price": "50000", "qty": "1.0", "time": 1234567890}
            ]

            client = BinanceClient()
            trades = client.fetch_trades("BTCUSDT", limit=100)

            assert len(trades) > 0
            assert "price" in trades[0]

    def test_coinbase_client_fetch_trades(self):
        """Test fetching trades from Coinbase"""
        from src.services.orderflow import CoinbaseClient

        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = [
                {"price": "50000", "size": "1.0", "time": "2024-01-01T00:00:00Z"}
            ]

            client = CoinbaseClient()
            trades = client.fetch_trades("BTC-USD")

            assert len(trades) > 0

    def test_aggregate_orderflow(self):
        """Test aggregating orderflow from multiple exchanges"""
        from src.services.orderflow import aggregate_orderflow

        with patch("src.services.orderflow.BinanceClient") as mock_binance, \
             patch("src.services.orderflow.CoinbaseClient") as mock_coinbase:

            mock_binance.return_value.fetch_trades.return_value = [{"price": "50000", "qty": "1.0"}]
            mock_coinbase.return_value.fetch_trades.return_value = [{"price": "50010", "size": "0.5"}]

            aggregated = aggregate_orderflow("BTC", ["binance", "coinbase"])

            assert "total_volume" in aggregated or "exchanges" in aggregated

    def test_calculate_order_imbalance(self):
        """Test calculating buy/sell order imbalance"""
        from src.services.orderflow import calculate_order_imbalance

        trades = [
            {"side": "buy", "qty": 10},
            {"side": "buy", "qty": 15},
            {"side": "sell", "qty": 5}
        ]

        imbalance = calculate_order_imbalance(trades)
        assert imbalance > 0  # More buys than sells


# ===== Twitter Client Tests =====

class TestTwitterClient:
    """Test suite for Twitter/X integration"""

    @pytest.fixture
    def twitter_client(self):
        """Create Twitter client instance"""
        from src.services.twitter import TwitterClient
        return TwitterClient(bearer_token="test_token")

    def test_fetch_tweets(self, twitter_client):
        """Test fetching tweets by query"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "data": [
                    {"id": "1", "text": "Bitcoin is bullish!", "created_at": "2024-01-01T00:00:00Z"}
                ]
            }

            tweets = twitter_client.fetch_tweets("Bitcoin", max_results=10)
            assert len(tweets) > 0

    def test_fetch_user_timeline(self, twitter_client):
        """Test fetching user timeline"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "data": [
                    {"id": "1", "text": "Market update", "created_at": "2024-01-01T00:00:00Z"}
                ]
            }

            tweets = twitter_client.fetch_user_timeline("elonmusk")
            assert len(tweets) > 0

    def test_get_tweet_metrics(self, twitter_client):
        """Test getting tweet engagement metrics"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "data": {
                    "public_metrics": {
                        "retweet_count": 100,
                        "like_count": 500,
                        "reply_count": 50
                    }
                }
            }

            metrics = twitter_client.get_tweet_metrics("1234567890")
            assert "retweet_count" in metrics or "like_count" in metrics

    def test_analyze_tweet_sentiment(self, twitter_client):
        """Test analyzing sentiment of tweets"""
        tweets = [
            {"text": "Bitcoin to the moon!"},
            {"text": "Crypto crash incoming"},
            {"text": "Holding steady"}
        ]

        sentiment = twitter_client.analyze_sentiment(tweets)
        assert "overall_score" in sentiment or "distribution" in sentiment

    def test_rate_limit_handling(self, twitter_client):
        """Test handling Twitter API rate limits"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 429  # Rate limit exceeded
            mock_get.return_value.json.return_value = {"error": "Rate limit exceeded"}

            result = twitter_client.fetch_tweets("Bitcoin")
            # Should handle gracefully
            assert result is not None or result == []


# ===== Feature Transform Tests =====

class TestFeatureTransforms:
    """Test suite for feature transformation pipeline"""

    def test_log_transform(self):
        """Test logarithmic transformation"""
        from src.core.transforms import log_transform
        values = [1, 10, 100, 1000]
        transformed = log_transform(values)
        assert all(isinstance(v, float) for v in transformed)

    def test_standardize_transform(self):
        """Test standardization (z-score)"""
        from src.core.transforms import standardize
        values = [1, 2, 3, 4, 5]
        standardized = standardize(values)
        # Mean should be ~0, std should be ~1
        assert abs(sum(standardized) / len(standardized)) < 0.1

    def test_min_max_scaling(self):
        """Test min-max normalization"""
        from src.core.transforms import min_max_scale
        values = [10, 20, 30, 40, 50]
        scaled = min_max_scale(values)
        assert min(scaled) == 0.0
        assert max(scaled) == 1.0

    def test_handle_outliers(self):
        """Test outlier handling"""
        from src.core.transforms import handle_outliers
        values = [1, 2, 3, 4, 5, 100]  # 100 is outlier
        cleaned = handle_outliers(values, method="clip")
        assert max(cleaned) < 100


# ===== Backtest Infrastructure Tests =====

class TestBacktestInfrastructure:
    """Test suite for backtesting infrastructure"""

    def test_create_backtest_scenario(self):
        """Test creating backtest scenario"""
        from src.pipeline.backtest import create_scenario
        scenario = create_scenario(
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000
        )
        assert scenario["initial_capital"] == 10000

    def test_run_backtest(self):
        """Test running a backtest"""
        from src.pipeline.backtest import run_backtest
        with patch("src.pipeline.backtest.load_historical_data") as mock_data:
            mock_data.return_value = [{"date": "2024-01-01", "price": 50000}]

            results = run_backtest(
                strategy="momentum",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )
            assert "total_return" in results or "trades" in results

    def test_calculate_backtest_metrics(self):
        """Test calculating backtest performance metrics"""
        from src.pipeline.backtest import calculate_metrics
        trades = [
            {"entry_price": 100, "exit_price": 110, "qty": 1},
            {"entry_price": 110, "exit_price": 105, "qty": 1}
        ]
        metrics = calculate_metrics(trades)
        assert "win_rate" in metrics or "total_pnl" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
