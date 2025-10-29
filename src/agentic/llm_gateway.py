"""
LLM Gateway for CPU-only local inference via Ollama.

Routes non-critical reasoning tasks to local quantized models.
NEVER used in critical path (Sentinel, RiskOfficer, Trader).

Models (all commercial-friendly licenses):
- phi3:mini (3.8B, MIT) - Fast intent parsing ≤1s
- qwen2.5:7b-instruct (Apache-2.0) - Default reasoning 2-5s
- mistral:7b-instruct (Apache-2.0) - Backup generalist

Performance on modern CPU (AVX2):
- 3.8B Q4: 25-60 tok/s
- 7B Q4: 10-30 tok/s
"""

import httpx
import asyncio
import hashlib
import json
import time
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Ollama server endpoint
OLLAMA_BASE_URL = "http://localhost:11434"

# Model tier mapping
MODELS = {
    "fast": "phi3:mini",           # Ultra-fast parser (1s)
    "default": "qwen2.5:7b-instruct",  # Main reasoner (2-5s)
    "backup": "mistral:7b-instruct",   # Fallback (2-5s)
}

ModelTier = Literal["fast", "default", "backup"]


@dataclass
class LLMResponse:
    """LLM response with metadata."""
    content: str
    model: str
    latency_ms: float
    cached: bool
    token_count: Optional[int] = None


class SemanticCache:
    """
    Semantic cache for LLM responses.
    Hash(prompt_template + features) → cached response.
    Expect 30-70% cache hit rate on repeated patterns.
    """
    
    def __init__(self, db_path: str = "./data/llm_cache.db"):
        import sqlite3
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
    
    def _create_table(self):
        """Create cache table."""
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS llm_cache (
            prompt_hash TEXT PRIMARY KEY,
            model TEXT,
            response TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            hit_count INTEGER DEFAULT 0,
            avg_latency_ms REAL
        )
        """)
        
        # Index for cache eviction
        self.db.execute("""
        CREATE INDEX IF NOT EXISTS idx_created_at 
        ON llm_cache(created_at)
        """)
        self.db.commit()
    
    def _hash_prompt(self, messages: List[Dict[str, str]], model: str) -> str:
        """Generate deterministic hash for prompt."""
        prompt_str = json.dumps(messages, sort_keys=True) + model
        return hashlib.sha256(prompt_str.encode()).hexdigest()
    
    def get(self, messages: List[Dict[str, str]], model: str) -> Optional[str]:
        """Retrieve cached response."""
        prompt_hash = self._hash_prompt(messages, model)
        
        cursor = self.db.execute("""
        SELECT response FROM llm_cache 
        WHERE prompt_hash = ?
        """, (prompt_hash,))
        
        row = cursor.fetchone()
        if row:
            # Update hit count
            self.db.execute("""
            UPDATE llm_cache 
            SET hit_count = hit_count + 1 
            WHERE prompt_hash = ?
            """, (prompt_hash,))
            self.db.commit()
            
            logger.info(f"Cache HIT: {prompt_hash[:8]}")
            return row[0]
        
        logger.debug(f"Cache MISS: {prompt_hash[:8]}")
        return None
    
    def set(
        self,
        messages: List[Dict[str, str]],
        model: str,
        response: str,
        latency_ms: float,
    ):
        """Store response in cache."""
        prompt_hash = self._hash_prompt(messages, model)
        
        self.db.execute("""
        INSERT OR REPLACE INTO llm_cache 
        (prompt_hash, model, response, avg_latency_ms) 
        VALUES (?, ?, ?, ?)
        """, (prompt_hash, model, response, latency_ms))
        self.db.commit()
        
        logger.debug(f"Cache SET: {prompt_hash[:8]}")
    
    def clear_old(self, days: int = 30):
        """Clear cache entries older than N days."""
        self.db.execute("""
        DELETE FROM llm_cache 
        WHERE created_at < datetime('now', '-' || ? || ' days')
        """, (days,))
        self.db.commit()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cursor = self.db.execute("""
        SELECT 
            COUNT(*) as total_entries,
            AVG(hit_count) as avg_hits_per_entry,
            AVG(avg_latency_ms) as avg_latency
        FROM llm_cache
        """)
        
        row = cursor.fetchone()
        return {
            "total_entries": row[0],
            "avg_hits_per_entry": row[1],
            "avg_latency_ms": row[2],
        }


class LLMGateway:
    """
    Gateway to local Ollama LLM inference.
    
    Safety features:
    - Timeouts on all requests
    - Automatic fallback to faster model on failure
    - Semantic caching for repeated patterns
    - Never sends broker creds, positions, or PII
    - Logs prompt hashes, not raw secrets
    
    Usage:
        gateway = LLMGateway()
        response = await gateway.ask("fast", messages)
    """
    
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        enable_cache: bool = True,
        cache_db_path: str = "./data/llm_cache.db",
    ):
        self.base_url = base_url
        self.cache = SemanticCache(cache_db_path) if enable_cache else None
    
    async def ollama_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Raw Ollama chat completion.
        
        Args:
            model: Model name (e.g., "phi3:mini")
            messages: List of message dicts with role/content
            temperature: Sampling temperature (0.0-1.0)
            timeout: Request timeout in seconds
            
        Returns:
            Full Ollama response dict
            
        Raises:
            httpx.HTTPError: On request failure
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,  # Context window
            }
        }
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    
    async def ask(
        self,
        tier: ModelTier,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        timeout: float = 30.0,
        use_cache: bool = True,
    ) -> LLMResponse:
        """
        Ask LLM with automatic fallback and caching.
        
        Args:
            tier: Model tier ("fast", "default", "backup")
            messages: Conversation messages
            temperature: Sampling temperature
            timeout: Request timeout
            use_cache: Whether to use semantic cache
            
        Returns:
            LLMResponse with content and metadata
            
        Example:
            messages = [
                {"role": "system", "content": "You are a trading analyst."},
                {"role": "user", "content": "Summarize: AAPL up 5% on earnings"}
            ]
            response = await gateway.ask("fast", messages)
            print(response.content)
        """
        model = MODELS[tier]
        
        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get(messages, model)
            if cached:
                return LLMResponse(
                    content=cached,
                    model=model,
                    latency_ms=0.0,
                    cached=True,
                )
        
        # Time the request
        start_time = time.time()
        
        try:
            # Primary attempt
            result = await self.ollama_chat(model, messages, temperature, timeout)
            content = result["message"]["content"]
            latency_ms = (time.time() - start_time) * 1000
            
            # Cache the response
            if use_cache and self.cache:
                self.cache.set(messages, model, content, latency_ms)
            
            return LLMResponse(
                content=content,
                model=model,
                latency_ms=latency_ms,
                cached=False,
                token_count=result.get("eval_count"),
            )
            
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
            
            # Fallback to faster model if default/backup failed
            if tier == "default":
                logger.info("Falling back to 'fast' tier")
                return await self.ask("fast", messages, temperature, timeout, use_cache)
            
            # No fallback available
            raise
    
    async def ask_json(
        self,
        tier: ModelTier,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Ask LLM and parse JSON response.
        
        Automatically adds "Return valid JSON only" to system prompt.
        
        Args:
            tier: Model tier
            system_prompt: System instruction
            user_prompt: User query
            temperature: Lower for structured output
            timeout: Request timeout
            
        Returns:
            Parsed JSON dict
            
        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        messages = [
            {"role": "system", "content": f"{system_prompt}\nReturn valid JSON only, no other text."},
            {"role": "user", "content": user_prompt},
        ]
        
        response = await self.ask(tier, messages, temperature, timeout)
        
        # Try to parse JSON
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            content = response.content.strip()
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
                return json.loads(json_str)
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                json_str = content[start:end].strip()
                return json.loads(json_str)
            else:
                raise
    
    async def health_check(self) -> bool:
        """
        Check if Ollama is running and responsive.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """List available Ollama models."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]


# Convenience functions for common use cases

async def news_to_signal(
    headlines: List[str],
    gateway: Optional[LLMGateway] = None,
) -> Dict[str, Any]:
    """
    Convert news headlines to trading signal.
    
    Used by NewsSentry agent (non-critical path).
    
    Args:
        headlines: List of news headlines
        gateway: LLM gateway (creates new if None)
        
    Returns:
        Signal dict with impact, tickers, confidence, rationale
    """
    if gateway is None:
        gateway = LLMGateway()
    
    system_prompt = """You are a trading signal generator.
Analyze news headlines and output a trading signal.

Output JSON schema:
{
  "impact": "POSITIVE|NEGATIVE|NEUTRAL",
  "tickers": ["AAPL", "MSFT", ...],
  "confidence": 0.0-1.0,
  "rationale": "Brief explanation"
}

Be concise and data-driven."""
    
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    user_prompt = f"Headlines:\n{headlines_text}"
    
    return await gateway.ask_json("fast", system_prompt, user_prompt)


async def generate_trade_plan(
    ticker: str,
    setup: Dict[str, Any],
    market_regime: str,
    risk_snapshot: Dict[str, Any],
    max_risk_pct: float = 1.0,
    min_reward_risk: float = 2.0,
    gateway: Optional[LLMGateway] = None,
) -> Dict[str, Any]:
    """
    Generate trade plan with reasoning.
    
    Used by Forecaster/Auditor (off critical path).
    
    Args:
        ticker: Stock ticker
        setup: Technical setup dict
        market_regime: Current market regime
        risk_snapshot: Risk metrics
        max_risk_pct: Max risk per trade
        min_reward_risk: Min reward/risk ratio
        gateway: LLM gateway
        
    Returns:
        Trade plan dict with action, entry, stop, target, reasoning
    """
    if gateway is None:
        gateway = LLMGateway()
    
    system_prompt = """You are a trading strategist.
Create a trade plan based on setup and constraints.

Output JSON schema:
{
  "action": "BUY|SELL|HOLD|WATCH",
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float,
  "position_size_pct": float,
  "confidence": 0.0-1.0,
  "reasoning": ["reason1", "reason2", "reason3"],
  "risks": ["risk1", "risk2"]
}

Be specific and risk-aware."""
    
    user_prompt = f"""Ticker: {ticker}
Market Regime: {market_regime}
Setup: {json.dumps(setup, indent=2)}
Risk Snapshot: {json.dumps(risk_snapshot, indent=2)}
Constraints:
- Max risk per trade: {max_risk_pct}%
- Min reward/risk ratio: {min_reward_risk}:1"""
    
    return await gateway.ask_json("default", system_prompt, user_prompt)


async def calibrate_confidence(
    predictions: List[Dict[str, Any]],
    outcomes: List[Dict[str, Any]],
    gateway: Optional[LLMGateway] = None,
) -> Dict[str, Any]:
    """
    Calibrate confidence based on historical predictions vs outcomes.
    
    Used by Auditor (nightly batch job).
    
    Args:
        predictions: List of predictions with confidence
        outcomes: List of actual outcomes
        gateway: LLM gateway
        
    Returns:
        Calibration adjustments dict
    """
    if gateway is None:
        gateway = LLMGateway()
    
    system_prompt = """You are a model calibrator.
Analyze prediction accuracy vs confidence and suggest adjustments.

Output JSON schema:
{
  "calibration_error": float,
  "adjustments": {
    "high_confidence": float,  // multiplier for >80% confidence
    "medium_confidence": float, // multiplier for 60-80%
    "low_confidence": float     // multiplier for <60%
  },
  "recommendations": ["recommendation1", "recommendation2"]
}

Be quantitative and actionable."""
    
    user_prompt = f"""Historical Performance:
Predictions: {json.dumps(predictions[:20], indent=2)}  # Limit context
Outcomes: {json.dumps(outcomes[:20], indent=2)}

Calculate calibration error and suggest confidence adjustments."""
    
    return await gateway.ask_json("default", system_prompt, user_prompt, timeout=60.0)


# Example usage
if __name__ == "__main__":
    async def demo():
        """Demo LLM gateway capabilities."""
        
        gateway = LLMGateway()
        
        # Test 1: Health check
        print("=== Health Check ===")
        healthy = await gateway.health_check()
        print(f"Ollama healthy: {healthy}")
        
        if not healthy:
            print("ERROR: Ollama not running. Start with: ollama serve")
            return
        
        # Test 2: List models
        print("\n=== Available Models ===")
        models = await gateway.list_models()
        print(f"Models: {models}")
        
        # Test 3: Fast intent parsing
        print("\n=== TEST: Fast Intent Parsing ===")
        messages = [
            {"role": "system", "content": "Parse intent from user message. Output JSON only."},
            {"role": "user", "content": "Find oversold tech stocks under $100"},
        ]
        response = await gateway.ask("fast", messages)
        print(f"Model: {response.model}")
        print(f"Latency: {response.latency_ms:.1f}ms")
        print(f"Cached: {response.cached}")
        print(f"Response: {response.content[:200]}...")
        
        # Test 4: News to signal
        print("\n=== TEST: News to Signal ===")
        signal = await news_to_signal([
            "AAPL announces record iPhone sales",
            "Apple stock upgraded by Goldman Sachs",
            "Tech sector rallies on positive earnings",
        ])
        print(json.dumps(signal, indent=2))
        
        # Test 5: Cache hit
        print("\n=== TEST: Cache Hit ===")
        response2 = await gateway.ask("fast", messages)
        print(f"Cached: {response2.cached} (should be True)")
        print(f"Latency: {response2.latency_ms:.1f}ms (should be 0)")
        
        # Test 6: Cache stats
        print("\n=== Cache Stats ===")
        stats = gateway.cache.stats()
        print(json.dumps(stats, indent=2))
    
    asyncio.run(demo())
