"""
Autonomous Trading Copilot - Main orchestrator.

Integrates Grok reasoning with 8-agent system for autonomous trading.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from src.agentic.grok_reasoning import GrokReasoner, IntentType, TradingIntent
from src.bouncehunter.engine import BounceHunter
from src.bouncehunter.pennyhunter_agentic import AgenticMemory


@dataclass
class TradePlan:
    """Structured trade plan with reasoning."""
    action: str
    ticker: str
    quantity: int
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasoning: List[str]
    risks: List[str]
    expected_outcome: Dict[str, Any]
    agent_consensus: str
    timestamp: datetime


class TradingCopilot:
    """
    Autonomous trading agent with Grok-powered reasoning.
    
    Similar to coding assistants (GitHub Copilot, Cursor) but for trading:
    - Understands natural language requests
    - Scans markets autonomously
    - Plans trades with reasoning
    - Executes with permission
    - Learns from outcomes
    """
    
    def __init__(
        self,
        grok_api_key: str,
        db_path: str = "./data/agent_memory.db",
        use_cache: bool = True,
    ):
        """
        Initialize Trading Copilot.
        
        Args:
            grok_api_key: X.AI API key for Grok
            db_path: Path to agent memory database
            use_cache: Whether to use model caching
        """
        # Initialize Grok reasoner
        self.grok = GrokReasoner(api_key=grok_api_key)
        
        # Initialize BounceHunter scanner
        self.scanner = BounceHunter(use_cache=use_cache)
        
        # Initialize agent memory
        self.memory = AgenticMemory(db_path)
        
        # Conversation history
        self.conversation: List[Dict[str, str]] = []
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process user message and return response.
        
        This is the main entry point for the autonomous agent.
        
        Args:
            user_message: Natural language message from user
            
        Returns:
            Response with actions taken and results
        """
        # Add to conversation history
        self.conversation.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Parse intent with Grok
        intent = await self.grok.parse_intent(user_message)
        
        # Route to appropriate handler
        if intent.type == IntentType.SCAN:
            response = await self.handle_scan_request(intent)
        elif intent.type == IntentType.ANALYZE:
            response = await self.handle_analysis(intent)
        elif intent.type == IntentType.TRADE:
            response = await self.handle_trade_request(intent)
        elif intent.type == IntentType.PORTFOLIO:
            response = await self.handle_portfolio_query(intent)
        elif intent.type == IntentType.QUESTION:
            response = await self.handle_question(intent)
        elif intent.type == IntentType.MONITOR:
            response = await self.handle_monitor_request(intent)
        else:
            response = {
                "type": "error",
                "message": f"Unknown intent type: {intent.type}",
            }
        
        # Add to conversation history
        self.conversation.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        
        return response
    
    async def handle_scan_request(self, intent: TradingIntent) -> Dict[str, Any]:
        """
        Handle market scan requests.
        
        Example: "Find oversold tech stocks under $100"
        """
        # Convert intent to scan criteria
        scan_criteria = await self.grok.generate_scan_criteria(intent.raw_message)
        
        # Determine scanner type
        if scan_criteria["scanner_type"] == "BOUNCEHUNTER":
            # Run BounceHunter scan
            results = await self._run_bouncehunter_scan(scan_criteria)
        else:
            return {
                "type": "error",
                "message": f"Scanner type {scan_criteria['scanner_type']} not yet implemented",
            }
        
        # Generate natural language summary
        summary = f"Found {len(results)} opportunities matching your criteria:\n\n"
        
        for i, result in enumerate(results[:5], 1):
            summary += f"{i}. **{result['ticker']}** - {result['confidence']*100:.1f}% confidence\n"
            summary += f"   Entry: ${result['entry']:.2f}, Target: ${result['target']:.2f} (+{result['gain_pct']:.1f}%)\n"
        
        return {
            "type": "scan_results",
            "intent": intent.__dict__,
            "criteria": scan_criteria,
            "results": results,
            "summary": summary,
            "count": len(results),
        }
    
    async def handle_analysis(self, intent: TradingIntent) -> Dict[str, Any]:
        """
        Handle analysis requests for specific tickers.
        
        Example: "Should I sell my TSLA position?"
        """
        ticker = intent.parameters.get("ticker")
        if not ticker:
            return {
                "type": "error",
                "message": "No ticker specified for analysis",
            }
        
        # Get current position info from memory
        position = self.memory.get_position(ticker)
        
        # Get market data
        market_data = await self._get_market_data(ticker)
        
        # Get agent signals
        agent_signals = self.memory.get_recent_signals(ticker, limit=10)
        
        # Generate explanation with Grok
        explanation = await self.grok.explain_market_situation(
            ticker=ticker,
            price_data=market_data["price_data"],
            news=market_data["news"],
            technical_signals=market_data["technical_signals"],
        )
        
        return {
            "type": "analysis",
            "ticker": ticker,
            "position": position,
            "market_data": market_data,
            "explanation": explanation,
            "signals": agent_signals,
        }
    
    async def handle_trade_request(self, intent: TradingIntent) -> Dict[str, Any]:
        """
        Handle trade execution requests.
        
        Example: "Buy 100 shares of AAPL at market"
        """
        # Get market context
        ticker = intent.parameters.get("ticker")
        market_context = await self._get_market_data(ticker)
        
        # Get agent signals
        agent_signals = self.memory.get_recent_signals(ticker, limit=10)
        
        # Generate trade plan with Grok
        trade_plan_raw = await self.grok.generate_trade_plan(
            intent=intent,
            market_context=market_context,
            agent_signals=[s.__dict__ for s in agent_signals],
        )
        
        # Convert to TradePlan
        trade_plan = TradePlan(
            action=trade_plan_raw["action"],
            ticker=trade_plan_raw["ticker"],
            quantity=trade_plan_raw["quantity"],
            entry_price=trade_plan_raw["entry_price"],
            stop_loss=trade_plan_raw["stop_loss"],
            take_profit=trade_plan_raw["take_profit"],
            confidence=trade_plan_raw["confidence"],
            reasoning=trade_plan_raw["reasoning"],
            risks=trade_plan_raw["risks"],
            expected_outcome=trade_plan_raw["expected_outcome"],
            agent_consensus=trade_plan_raw["agent_consensus"],
            timestamp=datetime.now(),
        )
        
        # Request approval (for now, just return plan)
        return {
            "type": "trade_plan",
            "plan": trade_plan.__dict__,
            "requires_approval": True,
            "message": "Trade plan ready for approval. Review and confirm to execute.",
        }
    
    async def handle_portfolio_query(self, intent: TradingIntent) -> Dict[str, Any]:
        """
        Handle portfolio-related queries.
        
        Example: "How's my portfolio doing?"
        """
        # Get all positions from memory
        positions = self.memory.get_all_positions()
        
        # Calculate portfolio metrics
        total_value = sum(p["current_value"] for p in positions)
        total_pnl = sum(p["unrealized_pnl"] for p in positions)
        pnl_pct = (total_pnl / total_value * 100) if total_value > 0 else 0
        
        # Get recent fills
        recent_fills = self.memory.get_recent_fills(limit=10)
        
        # Generate summary
        summary = f"**Portfolio Overview:**\n\n"
        summary += f"Total Value: ${total_value:,.2f}\n"
        summary += f"Total P&L: ${total_pnl:,.2f} ({pnl_pct:+.2f}%)\n"
        summary += f"Open Positions: {len(positions)}\n\n"
        
        summary += "**Top Positions:**\n"
        for pos in sorted(positions, key=lambda x: abs(x["unrealized_pnl"]), reverse=True)[:5]:
            summary += f"- {pos['ticker']}: ${pos['current_value']:,.2f} ({pos['pnl_pct']:+.2f}%)\n"
        
        return {
            "type": "portfolio",
            "total_value": total_value,
            "total_pnl": total_pnl,
            "pnl_pct": pnl_pct,
            "positions": positions,
            "recent_fills": recent_fills,
            "summary": summary,
        }
    
    async def handle_question(self, intent: TradingIntent) -> Dict[str, Any]:
        """
        Handle general trading questions.
        
        Example: "What is mean reversion?"
        """
        # Get portfolio context if relevant
        context = None
        if any(word in intent.raw_message.lower() for word in ["my", "portfolio", "position"]):
            positions = self.memory.get_all_positions()
            context = {"positions": positions}
        
        # Answer with Grok
        answer = await self.grok.answer_question(
            question=intent.raw_message,
            context=context,
        )
        
        return {
            "type": "answer",
            "question": intent.raw_message,
            "answer": answer,
        }
    
    async def handle_monitor_request(self, intent: TradingIntent) -> Dict[str, Any]:
        """
        Handle monitoring/alert requests.
        
        Example: "Watch NVDA and alert me if it drops 2%"
        """
        ticker = intent.parameters.get("ticker")
        condition = intent.parameters.get("condition")
        
        # Store alert in memory (simplified for now)
        alert_id = self.memory.create_alert(
            ticker=ticker,
            condition=condition,
            created_at=datetime.now(),
        )
        
        return {
            "type": "alert_created",
            "alert_id": alert_id,
            "ticker": ticker,
            "condition": condition,
            "message": f"Alert created for {ticker}. You'll be notified when {condition}.",
        }
    
    # Helper methods
    
    async def _run_bouncehunter_scan(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run BounceHunter scan with specified criteria."""
        # Extract tickers from criteria (simplified)
        # In production, this would integrate with a stock screener
        tickers = criteria.get("tickers", ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"])
        
        # Fit scanner if not cached
        if not self.scanner.fitted:
            self.scanner.fit(tickers=tickers[:20])  # Train on sample
        
        # Generate signals
        signals = self.scanner.predict(tickers)
        
        # Filter by criteria
        results = []
        for signal in signals:
            # Apply filters
            if criteria["filters"].get("price_min") and signal.entry < criteria["filters"]["price_min"]:
                continue
            if criteria["filters"].get("price_max") and signal.entry > criteria["filters"]["price_max"]:
                continue
            
            results.append({
                "ticker": signal.ticker,
                "confidence": signal.bounce_prob,
                "entry": signal.entry,
                "stop": signal.stop,
                "target": signal.target,
                "gain_pct": ((signal.target - signal.entry) / signal.entry) * 100,
                "risk_pct": ((signal.entry - signal.stop) / signal.entry) * 100,
                "date": signal.date,
            })
        
        # Sort by confidence
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        return results[:criteria.get("limit", 10)]
    
    async def _get_market_data(self, ticker: str) -> Dict[str, Any]:
        """Get current market data for ticker."""
        # Simplified - in production, integrate with real-time data provider
        return {
            "price_data": {
                "current_price": 175.50,
                "change_percent": -2.3,
                "volume": 85000000,
                "avg_volume": 65000000,
            },
            "news": [
                f"{ticker} recent news 1",
                f"{ticker} recent news 2",
            ],
            "technical_signals": {
                "rsi": 35,
                "dist_200dma": -5.2,
                "volume_spike": 1.3,
            },
        }


# Example usage
async def demo():
    """Demo the Trading Copilot."""
    
    import os
    api_key = os.environ.get("XAI_API_KEY")
    
    if not api_key:
        print("XAI_API_KEY not set. Please set environment variable.")
        return
    
    copilot = TradingCopilot(grok_api_key=api_key)
    
    # Test conversation
    messages = [
        "Find oversold tech stocks under $100",
        "How's my portfolio doing?",
        "Should I buy AAPL?",
        "What is mean reversion?",
    ]
    
    for msg in messages:
        print(f"\n{'='*60}")
        print(f"User: {msg}")
        print(f"{'='*60}")
        
        response = await copilot.process_message(msg)
        print(f"\nResponse Type: {response['type']}")
        print(f"Response: {response}")


if __name__ == "__main__":
    asyncio.run(demo())
