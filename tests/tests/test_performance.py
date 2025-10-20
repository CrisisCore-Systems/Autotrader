"""
Performance and Load Tests

Tests system performance, load handling, stress scenarios, and resource usage.
Includes benchmarking, concurrency tests, and memory profiling.

Run with: pytest tests/test_performance.py -v -m performance
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ===== API Performance Tests =====

class TestAPIPerformance:
    """Test API endpoint performance"""

    @pytest.fixture
    def dashboard_client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        # Mock the scan_token_full function directly
        mock_scan_data = {
            "symbol": "MOCK",
            "price": 1.0,
            "liquidity_usd": 1000000.0,
            "gem_score": 0.5,
            "final_score": 0.5,
            "confidence": 0.8,
            "flagged": False,
            "narrative_momentum": 0.5,
            "sentiment_score": 0.5,
            "holders": 1000,
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # Apply patch and return both client and patch context
        patch_context = patch("src.api.dashboard_api.scan_token_full", return_value=mock_scan_data)
        patch_context.start()
        from src.api.dashboard_api import app
        client = TestClient(app)
        
        yield client
        
        # Cleanup
        patch_context.stop()

    @pytest.mark.performance
    def test_api_response_time_tokens(self, dashboard_client):
        """Test /api/tokens response time meets SLA"""
        start = time.time()
        response = dashboard_client.get("/api/tokens")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed < 500  # Should respond within 500ms

    @pytest.mark.performance
    def test_api_response_time_scan(self, dashboard_client):
        """Test /api/features/schema response time"""
        start = time.time()
        response = dashboard_client.get("/api/features/schema")
        elapsed = (time.time() - start) * 1000

        assert response.status_code == 200
        assert elapsed < 2000  # Features schema can take longer

    @pytest.mark.performance
    def test_api_throughput(self, dashboard_client):
        """Test API throughput (requests per second)"""
        num_requests = 100
        start = time.time()

        for _ in range(num_requests):
            response = dashboard_client.get("/api/tokens")
            assert response.status_code == 200

        elapsed = time.time() - start
        rps = num_requests / elapsed

        assert rps > 50  # Should handle at least 50 req/sec

    @pytest.mark.slow
    def test_api_sustained_load(self, dashboard_client):
        """Test API under sustained load"""
        duration_seconds = 30
        end_time = time.time() + duration_seconds
        request_count = 0

        while time.time() < end_time:
            response = dashboard_client.get("/api/tokens")
            assert response.status_code == 200
            request_count += 1
            time.sleep(0.1)

        # Should maintain performance over time
        assert request_count > 100


# ===== Concurrent Request Tests =====

class TestConcurrentRequests:
    """Test handling concurrent requests"""

    @pytest.fixture
    def dashboard_client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        # Mock the scan_token_full function directly
        mock_scan_data = {
            "symbol": "MOCK",
            "price": 1.0,
            "liquidity_usd": 1000000.0,
            "gem_score": 0.5,
            "final_score": 0.5,
            "confidence": 0.8,
            "flagged": False,
            "narrative_momentum": 0.5,
            "sentiment_score": 0.5,
            "holders": 1000,
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # Apply patch and return both client and patch context
        patch_context = patch("src.api.dashboard_api.scan_token_full", return_value=mock_scan_data)
        patch_context.start()
        from src.api.dashboard_api import app
        client = TestClient(app)
        
        yield client
        
        # Cleanup
        patch_context.stop()

    @pytest.mark.performance
    def test_concurrent_reads(self, dashboard_client):
        """Test handling concurrent read requests"""
        num_threads = 10
        requests_per_thread = 5

        def make_requests():
            results = []
            for _ in range(requests_per_thread):
                response = dashboard_client.get("/api/tokens")
                results.append(response.status_code)
            return results

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_requests) for _ in range(num_threads)]
            all_results = []
            for future in as_completed(futures):
                all_results.extend(future.result())

        # All requests should succeed
        assert all(status == 200 for status in all_results)
        assert len(all_results) == num_threads * requests_per_thread

    @pytest.mark.performance
    def test_concurrent_writes(self, dashboard_client):
        """Test handling concurrent write requests"""
        num_threads = 5

        def create_feature():
            return dashboard_client.post("/api/scan", json={"limit": 5})

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_feature) for _ in range(num_threads)]
            results = [f.result() for f in as_completed(futures)]

        # All should complete successfully
        assert all(r.status_code in [200, 201] for r in results)

    @pytest.mark.slow
    def test_high_concurrency(self, dashboard_client):
        """Test handling high concurrency (50+ concurrent requests)"""
        num_threads = 50

        def make_request():
            return dashboard_client.get("/api/tokens")

        start = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_request) for _ in range(num_threads)]
            results = [f.result() for f in as_completed(futures)]
        elapsed = time.time() - start

        # All should succeed
        assert all(r.status_code == 200 for r in results)
        # Should complete in reasonable time
        assert elapsed < 10.0


# ===== Memory and Resource Tests =====

class TestMemoryUsage:
    """Test memory usage and leaks"""

    def get_memory_usage(self):
        """Get current process memory usage in MB"""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

    @pytest.mark.performance
    def test_memory_stability(self):
        """Test memory usage remains stable over iterations"""
        from src.core.pipeline import TokenScanner

        with patch("src.core.pipeline.EtherscanClient"), \
             patch("src.core.pipeline.DexScreenerClient"):

            scanner = TokenScanner()
            initial_memory = self.get_memory_usage()

            # Run multiple scans
            for _ in range(10):
                scanner.scan(chain="ethereum", limit=10)

            final_memory = self.get_memory_usage()
            memory_increase = final_memory - initial_memory

            # Memory increase should be minimal (<50MB)
            assert memory_increase < 50

    @pytest.mark.performance
    def test_large_dataset_memory(self):
        """Test memory usage with large datasets"""
        from src.core.pipeline import process_tokens_parallel

        # Create large dataset
        tokens = [{"address": f"0x{i:040x}", "price": 1.0} for i in range(1000)]

        initial_memory = self.get_memory_usage()
        process_tokens_parallel(tokens, max_workers=4)
        peak_memory = self.get_memory_usage()

        memory_used = peak_memory - initial_memory

        # Should handle 1000 tokens without excessive memory
        assert memory_used < 200  # Less than 200MB


# ===== Database/Storage Performance =====

class TestStoragePerformance:
    """Test storage and database operations performance"""

    @pytest.mark.performance
    def test_feature_store_write_performance(self):
        """Test feature store write performance"""
        from src.services.feature_store import FeatureStore

        store = FeatureStore()
        num_features = 100

        start = time.time()
        for i in range(num_features):
            store.create_feature({
                "feature_id": f"perf_test_{i}",
                "name": f"Test Feature {i}",
                "category": "test",
                "importance": 0.5
            })
        elapsed = time.time() - start

        # Should write quickly
        assert elapsed < 5.0  # 100 features in under 5 seconds

    @pytest.mark.performance
    def test_feature_store_read_performance(self):
        """Test feature store read performance"""
        from src.services.feature_store import FeatureStore

        store = FeatureStore()

        # Create test features
        for i in range(50):
            store.create_feature({
                "feature_id": f"read_test_{i}",
                "name": f"Test {i}",
                "category": "test"
            })

        # Benchmark reads
        start = time.time()
        for i in range(50):
            feature = store.get_feature(f"read_test_{i}")
            assert feature is not None
        elapsed = time.time() - start

        # Should read quickly
        assert elapsed < 1.0

    @pytest.mark.performance
    def test_batch_feature_retrieval(self):
        """Test batch retrieval performance"""
        from src.services.feature_store import FeatureStore

        store = FeatureStore()

        start = time.time()
        features = store.get_all_features()
        elapsed = time.time() - start

        # Batch retrieval should be fast
        assert elapsed < 2.0


# ===== Cache Performance Tests =====

class TestCachePerformance:
    """Test caching performance"""

    @pytest.mark.performance
    def test_cache_hit_performance(self):
        """Test cache hit is faster than miss"""
        from src.services.reliability import CachePolicy

        cache = CachePolicy(ttl_seconds=60)

        # Expensive operation simulation
        def expensive_operation():
            time.sleep(0.1)
            return "result"

        # First call (cache miss)
        start = time.time()
        if cache.get("key1") is None:
            result = expensive_operation()
            cache.set("key1", result)
        miss_time = time.time() - start

        # Second call (cache hit)
        start = time.time()
        result = cache.get("key1")
        hit_time = time.time() - start

        # Cache hit should be much faster
        assert hit_time < miss_time / 10

    @pytest.mark.performance
    def test_cache_throughput(self):
        """Test cache operation throughput"""
        from src.services.reliability import CachePolicy

        cache = CachePolicy(ttl_seconds=60)
        num_operations = 1000

        start = time.time()
        for i in range(num_operations):
            cache.set(f"key_{i}", f"value_{i}")
        elapsed = time.time() - start

        ops_per_second = num_operations / elapsed

        # Should handle high throughput
        assert ops_per_second > 500

    @pytest.mark.performance
    def test_adaptive_cache_efficiency(self):
        """Test adaptive cache improves performance"""
        from src.services.reliability import AdaptiveCachePolicy

        cache = AdaptiveCachePolicy(base_ttl=60)

        # Simulate access patterns
        hot_keys = [f"hot_{i}" for i in range(10)]
        cold_keys = [f"cold_{i}" for i in range(100)]

        # Access hot keys frequently
        for _ in range(100):
            for key in hot_keys:
                cache.get(key)

        # Access cold keys once
        for key in cold_keys:
            cache.get(key)

        # Hot keys should have longer TTL
        hot_ttl = cache.get_ttl(hot_keys[0])
        cold_ttl = cache.get_ttl(cold_keys[0])

        assert hot_ttl > cold_ttl


# ===== Circuit Breaker Performance =====

class TestCircuitBreakerPerformance:
    """Test circuit breaker performance"""

    @pytest.mark.performance
    def test_circuit_breaker_overhead(self):
        """Test circuit breaker adds minimal overhead"""
        from src.services.reliability import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=5)

        # Measure without breaker
        start = time.time()
        for _ in range(1000):
            pass  # Simulate operation
        no_breaker_time = time.time() - start

        # Measure with breaker
        start = time.time()
        for _ in range(1000):
            if breaker.can_request():
                breaker.record_success()
        with_breaker_time = time.time() - start

        # Overhead should be minimal (<10%)
        overhead = (with_breaker_time - no_breaker_time) / no_breaker_time
        assert overhead < 0.1

    @pytest.mark.performance
    def test_circuit_breaker_under_load(self):
        """Test circuit breaker performance under load"""
        from src.services.reliability import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=10)
        num_requests = 10000

        start = time.time()
        for i in range(num_requests):
            if breaker.can_request():
                if i % 20 == 0:  # 5% failure rate
                    breaker.record_failure()
                else:
                    breaker.record_success()
        elapsed = time.time() - start

        # Should handle high request volume
        assert elapsed < 1.0


# ===== Scanning Performance =====

class TestScanningPerformance:
    """Test token scanning performance"""

    @pytest.mark.slow
    def test_scan_performance(self):
        """Test scan completes within target time"""
        from src.core.pipeline import TokenScanner

        with patch("src.core.pipeline.EtherscanClient"), \
             patch("src.core.pipeline.DexScreenerClient"):

            scanner = TokenScanner()

            start = time.time()
            result = scanner.scan(chain="ethereum", limit=50)
            elapsed = time.time() - start

            # Should scan 50 tokens in under 10 seconds
            assert elapsed < 10.0
            assert len(result.get("tokens", [])) <= 50

    @pytest.mark.performance
    def test_parallel_scanning_speedup(self):
        """Test parallel scanning is faster than sequential"""
        from src.core.pipeline import scan_sequential, scan_parallel

        tokens = [f"0x{i:040x}" for i in range(20)]

        with patch("src.core.pipeline.process_token"):
            # Sequential
            start = time.time()
            scan_sequential(tokens)
            sequential_time = time.time() - start

            # Parallel
            start = time.time()
            scan_parallel(tokens, max_workers=4)
            parallel_time = time.time() - start

            # Parallel should be faster
            assert parallel_time < sequential_time


# ===== Feature Extraction Performance =====

class TestFeatureExtractionPerformance:
    """Test feature extraction performance"""

    @pytest.mark.performance
    def test_feature_extraction_speed(self):
        """Test feature extraction completes quickly"""
        from src.core.features import calculate_all_features

        token_data = {
            "address": "0x123",
            "price": 1.5,
            "volume_24h": 100000,
            "liquidity": 500000,
            "holders": 1000
        }

        start = time.time()
        for _ in range(100):
            features = calculate_all_features(token_data)
        elapsed = time.time() - start

        # Should process 100 tokens in under 1 second
        assert elapsed < 1.0

    @pytest.mark.performance
    def test_batch_feature_extraction_performance(self):
        """Test batch feature extraction performance"""
        from src.core.pipeline import batch_extract_features

        tokens = [
            {"address": f"0x{i:040x}", "price": 1.0}
            for i in range(100)
        ]

        start = time.time()
        results = batch_extract_features(tokens)
        elapsed = time.time() - start

        # Should process 100 tokens quickly
        assert elapsed < 5.0
        assert len(results) == 100


# ===== Stress Tests =====

class TestStressScenarios:
    """Test system under stress conditions"""

    @pytest.mark.slow
    def test_sustained_high_load(self):
        """Test system under sustained high load"""
        from fastapi.testclient import TestClient

        with patch("src.api.dashboard_api.TokenScanner"):
            from src.api.dashboard_api import app
            client = TestClient(app)

            duration = 60  # 1 minute
            end_time = time.time() + duration
            request_count = 0
            errors = 0

            while time.time() < end_time:
                try:
                    response = client.get("/api/tokens")
                    if response.status_code != 200:
                        errors += 1
                    request_count += 1
                except Exception:
                    errors += 1

            error_rate = errors / request_count if request_count > 0 else 1
            # Error rate should be low
            assert error_rate < 0.01  # Less than 1% errors

    @pytest.mark.slow
    def test_memory_leak_detection(self):
        """Test for memory leaks under continuous operation"""
        from src.core.pipeline import TokenScanner

        with patch("src.core.pipeline.EtherscanClient"), \
             patch("src.core.pipeline.DexScreenerClient"):

            scanner = TokenScanner()
            process = psutil.Process(os.getpid())

            initial_memory = process.memory_info().rss / 1024 / 1024
            memory_samples = [initial_memory]

            # Run operations
            for i in range(50):
                scanner.scan(chain="ethereum", limit=10)
                if i % 10 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory)

            # Check memory trend
            memory_increase = memory_samples[-1] - memory_samples[0]

            # Should not grow excessively
            assert memory_increase < 100  # Less than 100MB growth


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance", "--tb=short"])
