"""Test Grok integration."""

import asyncio
import json
from src.agentic.grok_reasoning import GrokReasoner


async def test_intent_parsing():
    """Test intent parsing with Grok."""
    
    print("=== TEST 1: Intent Parsing ===")
    grok = GrokReasoner()
    
    test_messages = [
        "Find oversold tech stocks under $100",
        "Should I sell my TSLA position?",
        "Buy 100 shares of AAPL at market",
        "How's my portfolio performing?",
        "Watch NVDA and alert me if it drops 2%",
    ]
    
    for msg in test_messages:
        print(f"\nMessage: '{msg}'")
        try:
            intent = await grok.parse_intent(msg)
            print(f"  Type: {intent.type}")
            print(f"  Parameters: {intent.parameters}")
            print(f"  Urgency: {intent.urgency}")
            print(f"  Confidence: {intent.confidence}")
            print(f"  Reasoning: {intent.reasoning}")
        except Exception as e:
            print(f"  ERROR: {e}")


async def test_scan_criteria():
    """Test scan criteria generation."""
    
    print("\n\n=== TEST 2: Scan Criteria Generation ===")
    grok = GrokReasoner()
    
    requests = [
        "stocks with gap down and high volume in tech sector",
        "oversold small caps under 50 million market cap",
        "high volume breakouts above 200 day moving average",
    ]
    
    for req in requests:
        print(f"\nRequest: '{req}'")
        try:
            criteria = await grok.generate_scan_criteria(req)
            print(json.dumps(criteria, indent=2))
        except Exception as e:
            print(f"  ERROR: {e}")


async def test_question_answering():
    """Test question answering."""
    
    print("\n\n=== TEST 3: Question Answering ===")
    grok = GrokReasoner()
    
    questions = [
        "What is mean reversion and when does it work best?",
        "How do I know if a stock is oversold?",
        "What's the difference between RSI and Stochastic?",
    ]
    
    for q in questions:
        print(f"\nQuestion: '{q}'")
        try:
            answer = await grok.answer_question(q)
            print(f"Answer: {answer}")
        except Exception as e:
            print(f"  ERROR: {e}")


async def test_market_explanation():
    """Test market situation explanation."""
    
    print("\n\n=== TEST 4: Market Explanation ===")
    grok = GrokReasoner()
    
    try:
        explanation = await grok.explain_market_situation(
            ticker="AAPL",
            price_data={
                "current_price": 175.50,
                "change_percent": -2.3,
                "volume": 85000000,
                "avg_volume": 65000000,
            },
            news=[
                "Apple announces new iPhone delay",
                "Supply chain concerns in Asia",
                "Analyst downgrades to neutral",
            ],
            technical_signals={
                "rsi": 35,
                "dist_200dma": -5.2,
                "volume_spike": 1.3,
            },
        )
        print(f"Explanation: {explanation}")
    except Exception as e:
        print(f"  ERROR: {e}")


async def main():
    """Run all tests."""
    
    print("Testing Grok Integration")
    print("=" * 60)
    
    await test_intent_parsing()
    await test_scan_criteria()
    await test_question_answering()
    await test_market_explanation()
    
    print("\n" + "=" * 60)
    print("Tests Complete!")


if __name__ == "__main__":
    asyncio.run(main())
