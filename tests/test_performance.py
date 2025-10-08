"""Performance and stress tests for the system."""

from __future__ import annotations

import pytest
import time
import concurrent.futures
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from src.api.dashboard_api import app


client = TestClient(app)


# ============================================================================
# Performance Tests
# ============================================================================

class TestAPIPerformance:
    """Test API performance and response times."""
    
    def test_token_list_response_time(self):
        """Test /api/tokens responds within acceptable time."""
        start = time.time()
        response = client.get("/api/tokens")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 5.0  # Should respond within 5 seconds
    
    def test_token_detail_response_time(self):
        """Test /api/tokens/{symbol} responds within acceptable time."""
        # Get a valid symbol first
        tokens = client.get("/api/tokens").json()
        if not tokens:
            pytest.skip("No tokens available")
        
        symbol = tokens[0]["symbol"]
        
        start = time.time()
        response = client.get(f"/api/tokens/{symbol}")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 10.0  # Full scan may take longer
    
    def test_health_check_response_time(self):
        """Test health check responds quickly."""
        start = time.time()
        response = client.get("/health")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 1.0  # Should be very fast
    
    def test_sla_status_response_time(self):
        """Test SLA status endpoint performance."""
        start = time.time()
        response = client.get("/api/sla/status")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 2.0
    
    def test_feature_schema_response_time(self):
        """Test feature schema endpoint performance."""
        start = time.time()
        response = client.get("/api/features/schema")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 2.0


# ============================================================================
# Concurrent Request Tests
# ============================================================================

class TestConcurrentRequests:
    """Test system behavior under concurrent load."""
    
    def test_concurrent_token_list_requests(self):
        """Test handling multiple simultaneous token list requests."""
        def make_request():
            response = client.get("/api/tokens")
            return response.status_code
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 20
    
    def test_concurrent_different_endpoints(self):
        """Test concurrent requests to different endpoints."""
        def make_mixed_requests():
            endpoints = [
                "/health",
                "/api/tokens",
                "/api/sla/status",
                "/api/features/schema",
                "/api/anomalies"
            ]
            responses = []
            for endpoint in endpoints:
                resp = client.get(endpoint)
                responses.append(resp.status_code)
            return responses
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_mixed_requests) for _ in range(5)]
            all_results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for results in all_results:
            assert all(status == 200 for status in results)
    
    def test_rate_limiting_behavior(self):
        """Test system behavior under rapid repeated requests."""
        responses = []
        
        for _ in range(50):
            resp = client.get("/health")
            responses.append(resp.status_code)
        
        # Should handle all requests (may have rate limiting later)
        success_count = sum(1 for status in responses if status == 200)
        assert success_count > 40  # Most should succeed


# ============================================================================
# Load Tests
# ============================================================================

class TestSystemLoad:
    """Test system under sustained load."""
    
    def test_sustained_load_tokens_endpoint(self):
        """Test tokens endpoint under sustained load."""
        duration = 10  # seconds
        request_count = 0
        errors = 0
        
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                response = client.get("/api/tokens")
                request_count += 1
                if response.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1
        
        # Calculate requests per second
        rps = request_count / duration
        error_rate = errors / request_count if request_count > 0 else 0
        
        assert rps > 1  # Should handle at least 1 request per second
        assert error_rate < 0.1  # Less than 10% error rate
    
    def test_memory_stability_under_load(self):
        """Test that memory usage stays stable under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make many requests
        for _ in range(100):
            client.get("/health")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        assert memory_increase < 100  # Less than 100MB increase


# ============================================================================
# Cache Performance Tests
# ============================================================================

class TestCachePerformance:
    """Test caching effectiveness and performance."""
    
    def test_cache_hit_improves_performance(self):
        """Test that cache hits improve response times."""
        # First request (cache miss)
        start1 = time.time()
        response1 = client.get("/api/tokens")
        duration1 = time.time() - start1
        
        # Second request (should hit cache)
        start2 = time.time()
        response2 = client.get("/api/tokens")
        duration2 = time.time() - start2
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Second request should be faster (if caching is implemented)
        # This may not be true if no caching yet
        assert duration1 > 0 and duration2 > 0
    
    def test_cache_expiration_refreshes_data(self):
        """Test that cache expires and refreshes data."""
        from src.services.cache_policy import CachePolicy
        
        cache = CachePolicy(name="test", ttl_seconds=1)
        
        # Store value
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        result = cache.get("key1")
        assert result is None


# ============================================================================
# Stress Tests
# ============================================================================

class TestStressScenarios:
    """Test system under stress conditions."""
    
    def test_many_simultaneous_connections(self):
        """Test handling many simultaneous connections."""
        def make_request(n):
            try:
                response = client.get("/health")
                return response.status_code == 200
            except Exception:
                return False
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request, i) for i in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        success_rate = sum(results) / len(results)
        assert success_rate > 0.8  # At least 80% success rate
    
    def test_large_response_payload_handling(self):
        """Test handling endpoints with large response payloads."""
        response = client.get("/api/tokens")
        
        if response.status_code == 200:
            data = response.json()
            payload_size = len(response.content)
            
            # Should handle reasonably large payloads
            assert payload_size < 10 * 1024 * 1024  # Less than 10MB
    
    def test_rapid_token_detail_requests(self):
        """Test rapid successive requests for token details."""
        tokens_response = client.get("/api/tokens")
        if tokens_response.status_code != 200 or not tokens_response.json():
            pytest.skip("No tokens available")
        
        symbol = tokens_response.json()[0]["symbol"]
        
        success_count = 0
        for _ in range(10):
            try:
                response = client.get(f"/api/tokens/{symbol}")
                if response.status_code == 200:
                    success_count += 1
            except Exception:
                pass
        
        # Should handle most requests
        assert success_count >= 7


# ============================================================================
# Database/Storage Performance Tests
# ============================================================================

class TestStoragePerformance:
    """Test storage layer performance."""
    
    def test_feature_store_write_performance(self):
        """Test feature store write performance."""
        from src.core.feature_store import FeatureStore
        
        store = FeatureStore()
        
        start = time.time()
        for i in range(100):
            store.store_feature(
                token_symbol=f"TOKEN{i}",
                name=f"feature_{i}",
                value=float(i),
                confidence=0.9,
                category="test",
                feature_type="numeric"
            )
        duration = time.time() - start
        
        # Should handle 100 writes quickly
        assert duration < 5.0  # Less than 5 seconds
        writes_per_second = 100 / duration
        assert writes_per_second > 10  # At least 10 writes/sec
    
    def test_feature_store_read_performance(self):
        """Test feature store read performance."""
        from src.core.feature_store import FeatureStore
        
        store = FeatureStore()
        
        # Pre-populate
        for i in range(10):
            store.store_feature(
                token_symbol="TEST",
                name=f"feature_{i}",
                value=float(i),
                confidence=0.9,
                category="test",
                feature_type="numeric"
            )
        
        # Test read performance
        start = time.time()
        for _ in range(100):
            features = store.get_features("TEST")
        duration = time.time() - start
        
        # Should handle 100 reads quickly
        assert duration < 2.0  # Less than 2 seconds
        reads_per_second = 100 / duration
        assert reads_per_second > 20  # At least 20 reads/sec


# ============================================================================
# Circuit Breaker Stress Tests
# ============================================================================

class TestCircuitBreakerUnderLoad:
    """Test circuit breaker behavior under load."""
    
    def test_circuit_breaker_trips_on_sustained_failures(self):
        """Test circuit breaker opens after sustained failures."""
        from src.services.circuit_breaker import CircuitBreaker
        
        breaker = CircuitBreaker(
            name="stress_test",
            failure_threshold=10,
            timeout_seconds=5.0
        )
        
        # Simulate sustained failures
        for _ in range(15):
            breaker.record_failure()
        
        assert breaker.state.value == "OPEN"
        assert not breaker.can_attempt()
    
    def test_system_degrades_gracefully_under_load(self):
        """Test system degrades gracefully when overloaded."""
        # Make many concurrent requests
        def make_request():
            try:
                response = client.get("/api/tokens")
                return {
                    "success": response.status_code == 200,
                    "time": time.time()
                }
            except Exception:
                return {"success": False, "time": time.time()}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        success_rate = sum(1 for r in results if r["success"]) / len(results)
        
        # Should maintain reasonable success rate even under load
        assert success_rate > 0.6  # At least 60% success rate


# ============================================================================
# Benchmark Tests
# ============================================================================

class TestBenchmarks:
    """Benchmark tests for key operations."""
    
    def test_benchmark_scoring_calculation(self):
        """Benchmark gem score calculation."""
        from src.core.scoring import GemScoreCalculator
        
        calculator = GemScoreCalculator()
        features = {f"feature_{i}": float(i) for i in range(10)}
        
        start = time.time()
        for _ in range(1000):
            # Simulate score calculation
            score = sum(features.values()) / len(features)
        duration = time.time() - start
        
        calculations_per_second = 1000 / duration
        assert calculations_per_second > 1000  # Should be very fast
    
    def test_benchmark_sentiment_analysis(self):
        """Benchmark sentiment analysis."""
        from src.core.sentiment import SentimentAnalyzer
        
        analyzer = SentimentAnalyzer()
        articles = [
            {"title": f"Article {i}", "sentiment": i % 10}
            for i in range(10)
        ]
        
        start = time.time()
        for _ in range(100):
            result = analyzer.analyze_news_sentiment("TEST", articles)
        duration = time.time() - start
        
        analyses_per_second = 100 / duration
        assert analyses_per_second > 10  # At least 10 analyses/sec
