"""
Grok-powered reasoning for autonomous trading agent.

Uses X.AI's Grok model for natural language understanding,
intent parsing, and trading decision reasoning.
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from openai import OpenAI


class IntentType(str, Enum):
    """Types of trading intents."""
    SCAN = "SCAN"
    ANALYZE = "ANALYZE"
    TRADE = "TRADE"
    PORTFOLIO = "PORTFOLIO"
    QUESTION = "QUESTION"
    MONITOR = "MONITOR"


class Urgency(str, Enum):
    """Request urgency levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class TradingIntent:
    """Structured trading intent parsed from natural language."""
    type: IntentType
    parameters: Dict[str, Any]
    urgency: Urgency
    confidence: float
    reasoning: str
    raw_message: str


class GrokReasoner:
    """Grok-powered reasoning for trading agent."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "grok-beta",
    ):
        """
        Initialize Grok reasoner.
        
        Args:
            api_key: X.AI API key (defaults to XAI_API_KEY env var)
            model: Grok model to use
        """
        self.api_key = api_key or os.environ.get("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY not set. Please provide API key.")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self.model = model
    
    async def parse_intent(self, user_message: str) -> TradingIntent:
        """
        Parse user intent from natural language using Grok.
        
        Examples:
            "Find oversold tech stocks" -> SCAN intent
            "Should I sell TSLA?" -> ANALYZE intent
            "Buy 100 shares of AAPL" -> TRADE intent
            "How's my portfolio doing?" -> PORTFOLIO intent
        
        Args:
            user_message: Natural language trading request
            
        Returns:
            TradingIntent with parsed structure
        """
        prompt = f"""
You are an expert trading assistant parsing user requests.

User message: "{user_message}"

Parse this into structured JSON with:
{{
    "type": "SCAN|ANALYZE|TRADE|PORTFOLIO|QUESTION|MONITOR",
    "parameters": {{
        // Relevant parameters extracted from message
        // Examples: ticker, sector, condition, price_range, timeframe, etc.
    }},
    "urgency": "LOW|MEDIUM|HIGH|CRITICAL",
    "confidence": 0.0-1.0,  // How confident you are in this parsing
    "reasoning": "Brief explanation of why you parsed it this way"
}}

Intent Types:
- SCAN: Find/discover opportunities ("find oversold stocks", "scan for gaps")
- ANALYZE: Evaluate specific ticker/position ("should I sell TSLA?", "what's AAPL doing?")
- TRADE: Execute orders ("buy 100 AAPL", "sell half my position")
- PORTFOLIO: Portfolio queries ("how am I doing?", "show my positions")
- QUESTION: General questions ("what's mean reversion?", "how does the scanner work?")
- MONITOR: Set alerts/watchlists ("watch NVDA", "alert me if SPY drops 2%")

Return only valid JSON, no other text.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise trading intent parser. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temp for consistent parsing
        )
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        return TradingIntent(
            type=IntentType(parsed["type"]),
            parameters=parsed["parameters"],
            urgency=Urgency(parsed["urgency"]),
            confidence=parsed["confidence"],
            reasoning=parsed["reasoning"],
            raw_message=user_message,
        )
    
    async def generate_trade_plan(
        self,
        intent: TradingIntent,
        market_context: Dict[str, Any],
        agent_signals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate detailed trade plan with reasoning using Grok.
        
        Args:
            intent: Parsed trading intent
            market_context: Current market conditions
            agent_signals: Signals from 8-agent system
            
        Returns:
            Trade plan with reasoning and confidence
        """
        prompt = f"""
You are an expert trading strategist creating a trade plan.

**User Intent:**
{json.dumps(intent.__dict__, indent=2, default=str)}

**Market Context:**
{json.dumps(market_context, indent=2)}

**Agent Signals:**
{json.dumps(agent_signals, indent=2)}

Create a detailed trade plan in JSON:
{{
    "action": "BUY|SELL|HOLD|WATCH",
    "ticker": "string",
    "quantity": number,
    "entry_price": number,
    "stop_loss": number,
    "take_profit": number,
    "confidence": 0.0-1.0,
    "reasoning": [
        "Reason 1 (backed by data)",
        "Reason 2 (backed by data)",
        "Reason 3 (backed by data)"
    ],
    "risks": [
        "Risk 1 with mitigation",
        "Risk 2 with mitigation"
    ],
    "similar_patterns": [
        "Historical pattern 1 with outcome",
        "Historical pattern 2 with outcome"
    ],
    "agent_consensus": "Summary of what agents agree/disagree on",
    "expected_outcome": {{
        "win_probability": 0.0-1.0,
        "expected_gain": "percentage",
        "max_loss": "percentage",
        "holding_period": "timeframe"
    }}
}}

Be specific, data-driven, and honest about risks.
Return only valid JSON, no other text.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise trading strategist. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Slightly higher for creative reasoning
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    
    async def explain_market_situation(
        self,
        ticker: str,
        price_data: Dict[str, Any],
        news: List[str],
        technical_signals: Dict[str, Any],
    ) -> str:
        """
        Generate human-friendly explanation of market situation.
        
        Args:
            ticker: Stock ticker
            price_data: Current price, volume, etc.
            news: Recent news headlines
            technical_signals: Technical indicator values
            
        Returns:
            Natural language explanation
        """
        prompt = f"""
You are a market analyst explaining a situation to a trader.

**Ticker:** {ticker}

**Price Data:**
{json.dumps(price_data, indent=2)}

**Recent News:**
{json.dumps(news, indent=2)}

**Technical Signals:**
{json.dumps(technical_signals, indent=2)}

Provide a clear, concise explanation (3-4 sentences) of:
1. What's happening right now
2. Why it's happening (key drivers)
3. What to watch for next

Be direct, specific, and actionable. No fluff.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a concise market analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        
        return response.choices[0].message.content
    
    async def analyze_past_trade(
        self,
        trade_details: Dict[str, Any],
        outcome: Dict[str, Any],
        market_conditions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze why a past trade succeeded or failed.
        
        Args:
            trade_details: Original trade parameters
            outcome: Actual result
            market_conditions: Market state during trade
            
        Returns:
            Analysis with lessons learned
        """
        prompt = f"""
You are a trading coach analyzing a past trade to extract lessons.

**Trade Details:**
{json.dumps(trade_details, indent=2)}

**Outcome:**
{json.dumps(outcome, indent=2)}

**Market Conditions:**
{json.dumps(market_conditions, indent=2)}

Provide analysis in JSON:
{{
    "verdict": "SUCCESS|PARTIAL_SUCCESS|FAILURE",
    "what_went_right": ["specific thing 1", "specific thing 2"],
    "what_went_wrong": ["specific thing 1", "specific thing 2"],
    "key_lessons": ["actionable lesson 1", "actionable lesson 2"],
    "should_do_differently": ["specific change 1", "specific change 2"],
    "pattern_to_remember": "One-line summary of pattern",
    "confidence_in_analysis": 0.0-1.0
}}

Be honest and specific. Focus on actionable insights.
Return only valid JSON, no other text.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an honest trading coach. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    
    async def answer_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Answer general trading questions.
        
        Args:
            question: User's question
            context: Optional context (portfolio, positions, etc.)
            
        Returns:
            Natural language answer
        """
        context_str = ""
        if context:
            context_str = f"\n\n**Context:**\n{json.dumps(context, indent=2)}"
        
        prompt = f"""
You are an expert trading assistant answering questions.

**Question:** {question}{context_str}

Provide a clear, accurate answer. If relevant to context, reference specific data.
Be concise but complete. If you don't know, say so.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a knowledgeable trading assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        
        return response.choices[0].message.content
    
    async def generate_scan_criteria(
        self,
        natural_language_request: str,
    ) -> Dict[str, Any]:
        """
        Convert natural language to structured scan criteria.
        
        Examples:
            "oversold tech stocks under $100" -> structured parameters
            "stocks with gap down and high volume" -> scan filters
        
        Args:
            natural_language_request: User's scan request
            
        Returns:
            Structured scan parameters
        """
        prompt = f"""
You are converting natural language to structured scan criteria.

Request: "{natural_language_request}"

Convert to JSON scan parameters:
{{
    "scanner_type": "BOUNCEHUNTER|HIDDENGEM|CUSTOM",
    "filters": {{
        "price_min": number or null,
        "price_max": number or null,
        "volume_min": number or null,
        "sector": "string" or null,
        "market_cap_min": number or null,
        "market_cap_max": number or null,
        "technical_conditions": ["RSI_OVERSOLD", "GAP_DOWN", "VOLUME_SPIKE", etc.]
    }},
    "sort_by": "PROBABILITY|PRICE|VOLUME|MARKET_CAP",
    "limit": number,
    "confidence": 0.0-1.0
}}

Return only valid JSON, no other text.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise parameter parser. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        
        content = response.choices[0].message.content
        return json.loads(content)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        """Demo Grok reasoning capabilities."""
        
        # Initialize
        grok = GrokReasoner()
        
        # Test 1: Parse intent
        print("=== TEST 1: Intent Parsing ===")
        intent = await grok.parse_intent("Find oversold tech stocks under $100")
        print(f"Type: {intent.type}")
        print(f"Parameters: {intent.parameters}")
        print(f"Urgency: {intent.urgency}")
        print(f"Confidence: {intent.confidence}")
        print(f"Reasoning: {intent.reasoning}")
        print()
        
        # Test 2: Generate scan criteria
        print("=== TEST 2: Scan Criteria ===")
        criteria = await grok.generate_scan_criteria(
            "stocks with gap down and high volume in tech sector"
        )
        print(json.dumps(criteria, indent=2))
        print()
        
        # Test 3: Answer question
        print("=== TEST 3: Question Answering ===")
        answer = await grok.answer_question(
            "What is mean reversion and when does it work best?"
        )
        print(answer)
    
    asyncio.run(demo())
