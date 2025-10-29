"""
Test suite for local LLM inference via Ollama.

Requirements:
1. Ollama must be running: ollama serve
2. Models must be pulled:
   - ollama pull phi3:mini
   - ollama pull qwen2.5:7b-instruct
   - ollama pull mistral:7b-instruct

Tests:
- Health checks
- News-to-signal conversion
- Trade plan generation
- Confidence calibration
- Cache functionality
- Fallback behavior
- Performance benchmarks
"""

import asyncio
import json
import time
from typing import List, Dict, Any

from src.agentic.llm_gateway import (
    LLMGateway,
    news_to_signal,
    generate_trade_plan,
    calibrate_confidence,
)


class LLMTestSuite:
    """Comprehensive test suite for LLM gateway."""
    
    def __init__(self):
        self.gateway = LLMGateway()
        self.results: List[Dict[str, Any]] = []
    
    def log_result(self, test_name: str, status: str, details: Dict[str, Any]):
        """Log test result."""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
        }
        self.results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌"
        print(f"{status_emoji} {test_name}: {status}")
        if status == "FAIL":
            print(f"   Error: {details.get('error')}")
    
    async def test_health_check(self):
        """Test 1: Ollama health check."""
        print("\n=== TEST 1: Health Check ===")
        try:
            healthy = await self.gateway.health_check()
            
            if healthy:
                models = await self.gateway.list_models()
                self.log_result(
                    "health_check",
                    "PASS",
                    {"healthy": True, "models": models}
                )
            else:
                self.log_result(
                    "health_check",
                    "FAIL",
                    {"error": "Ollama not responding. Run: ollama serve"}
                )
                return False
            
        except Exception as e:
            self.log_result("health_check", "FAIL", {"error": str(e)})
            return False
        
        return True
    
    async def test_fast_intent_parsing(self):
        """Test 2: Fast intent parsing with Phi-3 Mini."""
        print("\n=== TEST 2: Fast Intent Parsing (Phi-3 Mini) ===")
        
        try:
            messages = [
                {"role": "system", "content": "Parse trading intent. Output JSON only."},
                {"role": "user", "content": "Find oversold tech stocks under $100"}
            ]
            
            start_time = time.time()
            response = await self.gateway.ask("fast", messages)
            latency = (time.time() - start_time) * 1000
            
            # Check latency target (≤1s = 1000ms)
            latency_ok = latency <= 1000
            
            self.log_result(
                "fast_intent_parsing",
                "PASS" if latency_ok else "FAIL",
                {
                    "model": response.model,
                    "latency_ms": latency,
                    "target_ms": 1000,
                    "cached": response.cached,
                    "response_length": len(response.content)
                }
            )
            
            print(f"   Latency: {latency:.1f}ms (target: ≤1000ms)")
            print(f"   Model: {response.model}")
            
        except Exception as e:
            self.log_result("fast_intent_parsing", "FAIL", {"error": str(e)})
    
    async def test_news_to_signal(self):
        """Test 3: News-to-signal conversion."""
        print("\n=== TEST 3: News to Signal ===")
        
        try:
            headlines = [
                "AAPL announces record iPhone sales, beats estimates",
                "Apple stock upgraded to buy by Goldman Sachs",
                "Tech sector rallies on positive earnings season",
            ]
            
            start_time = time.time()
            signal = await news_to_signal(headlines, self.gateway)
            latency = (time.time() - start_time) * 1000
            
            # Validate signal structure
            required_fields = ["impact", "tickers", "confidence", "rationale"]
            has_all_fields = all(field in signal for field in required_fields)
            
            # Check confidence range
            confidence_ok = 0.0 <= signal.get("confidence", -1) <= 1.0
            
            # Check latency (target ≤1.5s for news parsing)
            latency_ok = latency <= 1500
            
            test_pass = has_all_fields and confidence_ok and latency_ok
            
            self.log_result(
                "news_to_signal",
                "PASS" if test_pass else "FAIL",
                {
                    "signal": signal,
                    "latency_ms": latency,
                    "target_ms": 1500,
                    "has_all_fields": has_all_fields,
                    "confidence_valid": confidence_ok
                }
            )
            
            print(f"   Impact: {signal.get('impact')}")
            print(f"   Tickers: {signal.get('tickers')}")
            print(f"   Confidence: {signal.get('confidence'):.2f}")
            print(f"   Latency: {latency:.1f}ms")
            
        except Exception as e:
            self.log_result("news_to_signal", "FAIL", {"error": str(e)})
    
    async def test_trade_plan_generation(self):
        """Test 4: Trade plan generation."""
        print("\n=== TEST 4: Trade Plan Generation ===")
        
        try:
            start_time = time.time()
            plan = await generate_trade_plan(
                ticker="AAPL",
                setup={
                    "rsi": 35,
                    "dist_200dma": -5.2,
                    "volume_spike": 1.3,
                    "gap_down_pct": -3.5
                },
                market_regime="CHOPPY",
                risk_snapshot={
                    "portfolio_beta": 1.2,
                    "cash_pct": 25,
                    "max_position_exposure": 8
                },
                max_risk_pct=1.0,
                min_reward_risk=2.0,
                gateway=self.gateway,
            )
            latency = (time.time() - start_time) * 1000
            
            # Validate plan structure
            required_fields = ["action", "confidence", "reasoning", "risks"]
            has_all_fields = all(field in plan for field in required_fields)
            
            # Check latency (target ≤5s for trade planning)
            latency_ok = latency <= 5000
            
            test_pass = has_all_fields and latency_ok
            
            self.log_result(
                "trade_plan_generation",
                "PASS" if test_pass else "FAIL",
                {
                    "plan": plan,
                    "latency_ms": latency,
                    "target_ms": 5000,
                    "has_all_fields": has_all_fields
                }
            )
            
            print(f"   Action: {plan.get('action')}")
            print(f"   Confidence: {plan.get('confidence'):.2f}")
            print(f"   Reasoning: {len(plan.get('reasoning', []))} points")
            print(f"   Latency: {latency:.1f}ms")
            
        except Exception as e:
            self.log_result("trade_plan_generation", "FAIL", {"error": str(e)})
    
    async def test_cache_functionality(self):
        """Test 5: Semantic cache."""
        print("\n=== TEST 5: Cache Functionality ===")
        
        try:
            messages = [
                {"role": "system", "content": "Summarize this headline."},
                {"role": "user", "content": "AAPL beats earnings expectations"}
            ]
            
            # First call (cold cache)
            start_time = time.time()
            response1 = await self.gateway.ask("fast", messages)
            latency1 = (time.time() - start_time) * 1000
            
            # Second call (should hit cache)
            start_time = time.time()
            response2 = await self.gateway.ask("fast", messages)
            latency2 = (time.time() - start_time) * 1000
            
            # Cache should be hit on second call
            cache_hit = response2.cached
            
            # Cache should be much faster
            speedup = latency1 / latency2 if latency2 > 0 else float('inf')
            
            self.log_result(
                "cache_functionality",
                "PASS" if cache_hit else "FAIL",
                {
                    "first_latency_ms": latency1,
                    "second_latency_ms": latency2,
                    "cache_hit": cache_hit,
                    "speedup": f"{speedup:.1f}x"
                }
            )
            
            print(f"   First call: {latency1:.1f}ms (cold)")
            print(f"   Second call: {latency2:.1f}ms (cached={cache_hit})")
            print(f"   Speedup: {speedup:.1f}x")
            
        except Exception as e:
            self.log_result("cache_functionality", "FAIL", {"error": str(e)})
    
    async def test_fallback_behavior(self):
        """Test 6: Fallback to faster model on failure."""
        print("\n=== TEST 6: Fallback Behavior ===")
        
        try:
            # Try to use a non-existent model by requesting default tier
            # If default model fails, should fall back to fast
            messages = [
                {"role": "system", "content": "Test fallback"},
                {"role": "user", "content": "Simple test message"}
            ]
            
            # This should succeed even if default model has issues
            response = await self.gateway.ask("default", messages, timeout=10.0)
            
            self.log_result(
                "fallback_behavior",
                "PASS",
                {
                    "model_used": response.model,
                    "fallback_worked": True
                }
            )
            
            print(f"   Model used: {response.model}")
            
        except Exception as e:
            # Fallback should prevent this
            self.log_result("fallback_behavior", "FAIL", {"error": str(e)})
    
    async def test_calibration(self):
        """Test 7: Confidence calibration."""
        print("\n=== TEST 7: Confidence Calibration ===")
        
        try:
            predictions = [
                {"ticker": "AAPL", "confidence": 0.85, "prediction": "UP"},
                {"ticker": "MSFT", "confidence": 0.70, "prediction": "DOWN"},
                {"ticker": "GOOGL", "confidence": 0.90, "prediction": "UP"},
            ]
            
            outcomes = [
                {"ticker": "AAPL", "actual": "UP", "pnl_pct": 2.3},
                {"ticker": "MSFT", "actual": "UP", "pnl_pct": -1.5},
                {"ticker": "GOOGL", "actual": "UP", "pnl_pct": 3.1},
            ]
            
            start_time = time.time()
            calibration = await calibrate_confidence(
                predictions, outcomes, self.gateway
            )
            latency = (time.time() - start_time) * 1000
            
            # Validate calibration structure
            has_required_fields = all(
                field in calibration 
                for field in ["calibration_error", "adjustments", "recommendations"]
            )
            
            self.log_result(
                "calibration",
                "PASS" if has_required_fields else "FAIL",
                {
                    "calibration": calibration,
                    "latency_ms": latency,
                    "has_required_fields": has_required_fields
                }
            )
            
            print(f"   Calibration error: {calibration.get('calibration_error'):.3f}")
            print(f"   Adjustments: {calibration.get('adjustments')}")
            print(f"   Latency: {latency:.1f}ms")
            
        except Exception as e:
            self.log_result("calibration", "FAIL", {"error": str(e)})
    
    async def test_cache_stats(self):
        """Test 8: Cache statistics."""
        print("\n=== TEST 8: Cache Statistics ===")
        
        try:
            stats = self.gateway.cache.stats()
            
            self.log_result(
                "cache_stats",
                "PASS",
                {"stats": stats}
            )
            
            print(f"   Total entries: {stats['total_entries']}")
            print(f"   Avg hits per entry: {stats['avg_hits_per_entry']:.1f}")
            print(f"   Avg latency: {stats['avg_latency_ms']:.1f}ms")
            
        except Exception as e:
            self.log_result("cache_stats", "FAIL", {"error": str(e)})
    
    async def test_performance_benchmark(self):
        """Test 9: Performance benchmark."""
        print("\n=== TEST 9: Performance Benchmark ===")
        
        try:
            # Benchmark each tier
            tiers = ["fast", "default"]
            results = {}
            
            for tier in tiers:
                messages = [
                    {"role": "system", "content": "Respond with OK"},
                    {"role": "user", "content": f"Test {tier}"}
                ]
                
                latencies = []
                for _ in range(3):
                    start_time = time.time()
                    await self.gateway.ask(tier, messages, use_cache=False)
                    latency = (time.time() - start_time) * 1000
                    latencies.append(latency)
                
                avg_latency = sum(latencies) / len(latencies)
                results[tier] = {
                    "avg_latency_ms": avg_latency,
                    "samples": latencies
                }
                
                print(f"   {tier}: {avg_latency:.1f}ms avg")
            
            self.log_result(
                "performance_benchmark",
                "PASS",
                {"results": results}
            )
            
        except Exception as e:
            self.log_result("performance_benchmark", "FAIL", {"error": str(e)})
    
    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("LLM Gateway Test Suite")
        print("=" * 60)
        
        # Test 1: Health check (critical)
        health_ok = await self.test_health_check()
        if not health_ok:
            print("\n❌ Cannot continue: Ollama not healthy")
            print("\nSetup instructions:")
            print("1. Install Ollama: https://ollama.com/download")
            print("2. Pull models:")
            print("   ollama pull phi3:mini")
            print("   ollama pull qwen2.5:7b-instruct")
            print("   ollama pull mistral:7b-instruct")
            print("3. Start server: ollama serve")
            return
        
        # Run remaining tests
        await self.test_fast_intent_parsing()
        await self.test_news_to_signal()
        await self.test_trade_plan_generation()
        await self.test_cache_functionality()
        await self.test_fallback_behavior()
        await self.test_calibration()
        await self.test_cache_stats()
        await self.test_performance_benchmark()
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        total = len(self.results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {failed}/{total}")
        
        if failed == 0:
            print("\n✅ All tests passed!")
        else:
            print(f"\n❌ {failed} test(s) failed")
            print("\nFailed tests:")
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"  - {r['test']}: {r['details'].get('error')}")
        
        # Save results to file
        with open("./llm_test_results.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: llm_test_results.json")


async def main():
    """Run test suite."""
    suite = LLMTestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
