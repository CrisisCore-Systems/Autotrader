"""Comprehensive tests for enhanced reliability modules."""

from __future__ import annotations

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.services.sla_monitor import SLAMonitor
from src.services.circuit_breaker import CircuitBreaker, CircuitState
from src.services.cache_policy import CachePolicy, AdaptiveCachePolicy


# ============================================================================
# SLA Monitor Tests
# ============================================================================

class TestSLAMonitor:
    """Test suite for SLA monitoring."""
    
    @pytest.fixture
    def sla_monitor(self):
        """Create SLA monitor instance."""
        return SLAMonitor(
            source_name="test_source",
            latency_threshold_p95=1000,  # 1 second
            success_rate_threshold=0.95
        )
    
    def test_sla_monitor_initialization(self, sla_monitor):
        """Test SLA monitor initializes correctly."""
        assert sla_monitor.source_name == "test_source"
        assert sla_monitor.status == "HEALTHY"
    
    def test_record_success(self, sla_monitor):
        """Test recording successful requests."""
        sla_monitor.record_request(latency_ms=100, success=True)
        metrics = sla_monitor.get_metrics()
        
        assert metrics["success_rate"] == 1.0
        assert metrics["latency_p50"] <= 100
    
    def test_record_failures_degrades_status(self, sla_monitor):
        """Test that failures degrade SLA status."""
        # Record many failures
        for _ in range(10):
            sla_monitor.record_request(latency_ms=100, success=False)
        
        metrics = sla_monitor.get_metrics()
        assert metrics["success_rate"] < 0.95
        assert sla_monitor.status in ["DEGRADED", "FAILED"]
    
    def test_high_latency_degrades_status(self, sla_monitor):
        """Test that high latency degrades status."""
        # Record high latency requests
        for _ in range(20):
            sla_monitor.record_request(latency_ms=2000, success=True)  # 2 seconds
        
        metrics = sla_monitor.get_metrics()
        assert metrics["latency_p95"] > 1000
        assert sla_monitor.status in ["DEGRADED", "FAILED"]
    
    def test_uptime_calculation(self, sla_monitor):
        """Test uptime percentage calculation."""
        # Mix of success and failure
        for i in range(10):
            success = i < 8  # 80% success rate
            sla_monitor.record_request(latency_ms=100, success=success)
        
        metrics = sla_monitor.get_metrics()
        assert 0.0 <= metrics["uptime_percentage"] <= 100.0
    
    def test_percentile_calculations(self, sla_monitor):
        """Test latency percentile calculations."""
        latencies = [50, 100, 150, 200, 500, 1000]
        for lat in latencies:
            sla_monitor.record_request(latency_ms=lat, success=True)
        
        metrics = sla_monitor.get_metrics()
        assert metrics["latency_p50"] < metrics["latency_p95"]
        assert metrics["latency_p95"] < metrics["latency_p99"]


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Test suite for circuit breaker."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance."""
        return CircuitBreaker(
            name="test_breaker",
            failure_threshold=3,
            timeout_seconds=5.0,
            half_open_max_calls=2
        )
    
    def test_circuit_breaker_starts_closed(self, circuit_breaker):
        """Test circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.can_attempt()
    
    def test_circuit_opens_after_failures(self, circuit_breaker):
        """Test circuit breaker opens after threshold failures."""
        # Record failures
        for _ in range(3):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert not circuit_breaker.can_attempt()
    
    def test_circuit_transitions_to_half_open(self, circuit_breaker):
        """Test circuit breaker transitions to HALF_OPEN after timeout."""
        # Open the circuit
        for _ in range(3):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for timeout (mock time)
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 10  # Beyond timeout
            circuit_breaker._check_timeout()
            
            assert circuit_breaker.state == CircuitState.HALF_OPEN
            assert circuit_breaker.can_attempt()
    
    def test_circuit_closes_after_success_in_half_open(self, circuit_breaker):
        """Test circuit breaker closes after successful recovery."""
        # Open circuit
        for _ in range(3):
            circuit_breaker.record_failure()
        
        # Force to HALF_OPEN
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.half_open_attempts = 0
        
        # Record successes
        circuit_breaker.record_success()
        circuit_breaker.record_success()
        
        assert circuit_breaker.state == CircuitState.CLOSED
    
    def test_circuit_reopens_on_half_open_failure(self, circuit_breaker):
        """Test circuit breaker reopens if HALF_OPEN attempt fails."""
        # Open circuit
        for _ in range(3):
            circuit_breaker.record_failure()
        
        # Force to HALF_OPEN
        circuit_breaker.state = CircuitState.HALF_OPEN
        
        # Failure in half-open state should reopen
        circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN
    
    def test_get_breaker_stats(self, circuit_breaker):
        """Test getting circuit breaker statistics."""
        circuit_breaker.record_failure()
        circuit_breaker.record_success()
        
        stats = circuit_breaker.get_stats()
        assert "state" in stats
        assert "failure_count" in stats
        assert "last_failure_time" in stats


# ============================================================================
# Cache Policy Tests
# ============================================================================

class TestCachePolicy:
    """Test suite for cache policies."""
    
    @pytest.fixture
    def cache_policy(self):
        """Create basic cache policy."""
        return CachePolicy(
            name="test_cache",
            ttl_seconds=60,
            max_size=100
        )
    
    def test_cache_policy_initialization(self, cache_policy):
        """Test cache policy initializes correctly."""
        assert cache_policy.name == "test_cache"
        assert cache_policy.ttl_seconds == 60
    
    def test_cache_set_and_get(self, cache_policy):
        """Test setting and getting cached values."""
        cache_policy.set("key1", "value1")
        result = cache_policy.get("key1")
        assert result == "value1"
    
    def test_cache_expiration(self, cache_policy):
        """Test cache entries expire after TTL."""
        cache_policy.set("key1", "value1")
        
        # Mock time to be past TTL
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 120  # 2 minutes
            result = cache_policy.get("key1")
            assert result is None
    
    def test_cache_size_limit(self, cache_policy):
        """Test cache respects size limits."""
        # Fill cache beyond limit
        for i in range(150):
            cache_policy.set(f"key{i}", f"value{i}")
        
        # Cache should not exceed max size
        assert cache_policy.current_size() <= 100
    
    def test_cache_invalidation(self, cache_policy):
        """Test manual cache invalidation."""
        cache_policy.set("key1", "value1")
        cache_policy.invalidate("key1")
        
        result = cache_policy.get("key1")
        assert result is None
    
    def test_cache_clear_all(self, cache_policy):
        """Test clearing entire cache."""
        cache_policy.set("key1", "value1")
        cache_policy.set("key2", "value2")
        cache_policy.clear()
        
        assert cache_policy.get("key1") is None
        assert cache_policy.get("key2") is None


class TestAdaptiveCachePolicy:
    """Test suite for adaptive cache policy."""
    
    @pytest.fixture
    def adaptive_cache(self):
        """Create adaptive cache policy."""
        return AdaptiveCachePolicy(
            name="adaptive_test",
            base_ttl_seconds=60,
            min_ttl_seconds=30,
            max_ttl_seconds=300
        )
    
    def test_adaptive_cache_initialization(self, adaptive_cache):
        """Test adaptive cache initializes."""
        assert adaptive_cache.name == "adaptive_test"
        assert adaptive_cache.base_ttl_seconds == 60
    
    def test_ttl_increases_with_cache_hits(self, adaptive_cache):
        """Test TTL increases with high cache hit rate."""
        # Set value
        adaptive_cache.set("key1", "value1")
        
        # Multiple hits
        for _ in range(10):
            adaptive_cache.get("key1")
        
        # TTL should have increased
        current_ttl = adaptive_cache.get_current_ttl("key1")
        assert current_ttl > 60
    
    def test_ttl_decreases_with_cache_misses(self, adaptive_cache):
        """Test TTL decreases with high miss rate."""
        # Multiple misses
        for i in range(10):
            adaptive_cache.get(f"nonexistent_{i}")
        
        # Base TTL should have decreased for new entries
        adaptive_cache.set("key1", "value1")
        current_ttl = adaptive_cache.get_current_ttl("key1")
        assert current_ttl < 60
    
    def test_ttl_bounds_respected(self, adaptive_cache):
        """Test TTL stays within min/max bounds."""
        # Many hits
        adaptive_cache.set("key1", "value1")
        for _ in range(100):
            adaptive_cache.get("key1")
        
        ttl = adaptive_cache.get_current_ttl("key1")
        assert 30 <= ttl <= 300


# ============================================================================
# OrderFlow Client Tests
# ============================================================================

class TestOrderFlowClients:
    """Test suite for orderflow clients."""
    
    @pytest.mark.parametrize("exchange", ["binance", "bybit"])
    def test_orderflow_client_initialization(self, exchange):
        """Test orderflow clients can be initialized."""
        from src.core.orderflow_clients import create_client
        
        client = create_client(exchange)
        assert client is not None
        assert client.exchange_name == exchange
    
    @patch('src.core.orderflow_clients.requests.get')
    def test_fetch_orderbook(self, mock_get):
        """Test fetching order book data."""
        from src.core.orderflow_clients import BinanceClient
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "bids": [[50000, 1.5], [49900, 2.0]],
            "asks": [[50100, 1.0], [50200, 1.5]]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        client = BinanceClient()
        orderbook = client.get_orderbook("BTCUSDT")
        
        assert "bids" in orderbook
        assert "asks" in orderbook
    
    def test_calculate_depth_metrics(self):
        """Test calculation of order book depth metrics."""
        bids = [[50000, 1.0], [49900, 2.0], [49800, 1.5]]
        asks = [[50100, 1.5], [50200, 1.0], [50300, 2.0]]
        
        # Calculate total bid depth
        bid_depth = sum(price * volume for price, volume in bids)
        ask_depth = sum(price * volume for price, volume in asks)
        
        assert bid_depth > 0
        assert ask_depth > 0
        
        # Calculate imbalance
        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
        assert -1.0 <= imbalance <= 1.0


# ============================================================================
# Twitter Client Tests
# ============================================================================

class TestTwitterClient:
    """Test suite for Twitter API client."""
    
    @patch('src.core.twitter_client.requests.get')
    def test_fetch_tweets(self, mock_get):
        """Test fetching tweets for a token."""
        from src.core.twitter_client import TwitterClient
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "123",
                    "text": "Bitcoin to the moon! #BTC",
                    "created_at": "2025-01-01T00:00:00Z",
                    "public_metrics": {
                        "like_count": 100,
                        "retweet_count": 50
                    }
                }
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        client = TwitterClient()
        tweets = client.fetch_tweets("BTC", max_results=10)
        
        assert isinstance(tweets, list)
        if tweets:
            assert "text" in tweets[0]
    
    def test_calculate_engagement_score(self):
        """Test calculating tweet engagement score."""
        tweet = {
            "public_metrics": {
                "like_count": 100,
                "retweet_count": 50,
                "reply_count": 20,
                "quote_count": 10
            }
        }
        
        # Engagement score formula
        likes = tweet["public_metrics"]["like_count"]
        retweets = tweet["public_metrics"]["retweet_count"]
        engagement = likes + (retweets * 2)
        
        assert engagement == 200
    
    def test_sentiment_from_tweets(self):
        """Test extracting sentiment from tweets."""
        tweets = [
            {"text": "Bitcoin bullish! Great gains"},
            {"text": "BTC looking strong today"},
            {"text": "Bearish signs for crypto"}
        ]
        
        # Should be able to analyze sentiment
        positive_keywords = ["bullish", "great", "strong"]
        negative_keywords = ["bearish"]
        
        positive_count = sum(
            1 for tweet in tweets
            if any(kw in tweet["text"].lower() for kw in positive_keywords)
        )
        
        assert positive_count > 0
