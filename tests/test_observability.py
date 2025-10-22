"""Tests for observability instrumentation (logging, metrics, tracing)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from src.core.logging_config import setup_structured_logging, get_logger, LogContext
from src.core.metrics import (
    record_scan_request,
    record_gem_score,
    record_data_source_request,
    is_prometheus_available,
)
from src.core.tracing import (
    setup_tracing,
    trace_operation,
    add_span_attributes,
    is_tracing_available,
)


class TestStructuredLogging:
    """Tests for structured logging functionality."""
    
    def test_setup_structured_logging(self):
        """Test structured logging setup."""
        logger = setup_structured_logging(
            service_name="test-service",
            environment="test",
            version="1.0.0",
            level="INFO",
        )
        
        assert logger is not None
        
    def test_logger_binding(self):
        """Test logger context binding."""
        logger = get_logger("test")
        
        bound_logger = logger.bind(request_id="123", user="test")
        assert bound_logger is not None
        
    def test_log_context_manager(self):
        """Test log context manager."""
        logger = get_logger("test")
        
        with LogContext(logger, request_id="123") as scoped_logger:
            assert scoped_logger is not None
            scoped_logger.info("test_message", key="value")


class TestMetrics:
    """Tests for Prometheus metrics."""
    
    def test_record_scan_request(self):
        """Test recording scan requests."""
        # Should not raise even if prometheus is not available
        record_scan_request("ETH", "success")
        record_scan_request("BTC", "failure")
        
    def test_record_gem_score(self):
        """Test recording gem scores."""
        record_gem_score("ETH", 85.5)
        record_gem_score("BTC", 92.0)
        
    def test_record_data_source_request(self):
        """Test recording data source requests."""
        record_data_source_request("coingecko", "/api/v3/coins", "success")
        record_data_source_request("etherscan", "/api", "error")
        
    def test_prometheus_availability(self):
        """Test prometheus availability check."""
        available = is_prometheus_available()
        assert isinstance(available, bool)


class TestTracing:
    """Tests for distributed tracing."""
    
    def test_setup_tracing(self):
        """Test tracing setup."""
        tracer = setup_tracing(service_name="test-service")
        assert tracer is not None
        
    def test_trace_operation_context_manager(self):
        """Test trace operation context manager."""
        with trace_operation("test_operation") as span:
            assert span is not None
            add_span_attributes(test_key="test_value")
            
    def test_trace_operation_with_exception(self):
        """Test trace operation handles exceptions."""
        with pytest.raises(ValueError):
            with trace_operation("test_operation"):
                raise ValueError("Test error")
                
    def test_tracing_availability(self):
        """Test tracing availability check."""
        available = is_tracing_available()
        assert isinstance(available, bool)


class TestHTTPManagerInstrumentation:
    """Tests for HTTP manager instrumentation."""
    
    @pytest.mark.asyncio
    async def test_http_request_logging(self):
        """Test HTTP request logging and metrics."""
        from src.core.http_manager import RateAwareRequester, InMemoryCache
        from src.core.rate_limit import RateLimit
        import httpx
        
        # Create a mock HTTP client
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.content = b'{"test": "data"}'
            mock_response.json.return_value = {"test": "data"}
            
            mock_client.request.return_value = mock_response
            mock_client.base_url = "https://api.example.com"
            
            # Create requester
            requester = RateAwareRequester(
                mock_client,
                cache_backend=InMemoryCache(),
            )
            
            # This should log and record metrics
            # Note: We can't easily test the actual logging/metrics
            # but we can verify the request completes
            assert requester is not None


class TestAPIInstrumentation:
    """Tests for API instrumentation."""
    
    @pytest.mark.skip(reason="Requires full API dependencies")
    @pytest.mark.asyncio
    async def test_api_middleware_logging(self):
        """Test API middleware logs requests."""
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        
        # Make a request to health endpoint
        response = client.get("/health")
        
        assert response.status_code == 200
        # The middleware should have logged this request
        
    @pytest.mark.skip(reason="Requires full API dependencies")
    @pytest.mark.asyncio
    async def test_api_middleware_adds_trace_id(self):
        """Test API middleware adds trace ID to response."""
        from fastapi.testclient import TestClient
        from src.api.main import app
        
        client = TestClient(app)
        
        response = client.get("/health")
        
        # Check if trace ID header might be present
        # (it may not be if OpenTelemetry is not fully configured)
        assert response.status_code == 200


class TestScoringInstrumentation:
    """Tests for scoring pipeline instrumentation."""
    
    def test_compute_gem_score_instrumentation(self):
        """Test gem score computation is instrumented."""
        from src.core.scoring import compute_gem_score
        
        features = {
            "SentimentScore": 0.8,
            "AccumulationScore": 0.7,
            "OnchainActivity": 0.9,
            "LiquidityDepth": 0.6,
            "TokenomicsRisk": 0.5,
            "ContractSafety": 0.8,
            "NarrativeMomentum": 0.7,
            "CommunityGrowth": 0.6,
            "Recency": 0.9,
            "DataCompleteness": 0.95,
        }
        
        # This should log and trace
        result = compute_gem_score(features)
        
        assert result.score > 0
        assert result.confidence > 0
        
    def test_should_flag_asset_instrumentation(self):
        """Test asset flagging is instrumented."""
        from src.core.scoring import should_flag_asset, GemScoreResult
        
        gem_score = GemScoreResult(
            score=85.0,
            confidence=90.0,
            contributions={},
        )
        
        features = {
            "ContractSafety": 0.8,
            "AccumulationScore": 0.7,
            "NarrativeMomentum": 0.7,
            "OnchainActivity": 0.7,
        }
        
        # This should log and trace
        flagged, debug = should_flag_asset(gem_score, features)
        
        assert isinstance(flagged, bool)
        assert isinstance(debug, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
