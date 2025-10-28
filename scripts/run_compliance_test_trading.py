"""Generate real trading data for compliance monitoring testing.

This script runs a simplified paper trading session to populate the audit trail
with signals, orders, fills, and risk checks that can be analyzed by the
compliance monitoring framework.

Usage:
    python scripts/run_compliance_test_trading.py --symbols AAPL MSFT --duration 60
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import time
import argparse
import random
import logging

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from autotrader.audit import (
    get_audit_trail,
    SignalEvent,
    RiskCheckEvent,
    RiskCheck,
    RiskCheckStatus,
    OrderEvent,
    FillEvent,
    LLMDecisionEvent,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


class ComplianceTestTrader:
    """Generates realistic trading events for compliance testing."""

    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.audit_trail = get_audit_trail()
        self.signal_counter = 0
        self.order_counter = 0
        self.fill_counter = 0

    def generate_signal(self, symbol: str) -> SignalEvent:
        """Generate a trading signal."""
        self.signal_counter += 1
        signal_id = f"test_sig_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.signal_counter:04d}"

        signal = SignalEvent(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id=signal_id,
            instrument=symbol,
            signal_type=random.choice(["momentum", "mean_reversion", "breakout"]),
            signal_strength=round(random.uniform(0.6, 0.95), 3),
            prediction=round(random.uniform(-0.05, 0.05), 4),
            confidence=round(random.uniform(0.6, 0.95), 3),
            model_version="pennyhunter_test_v1",
            features={
                "rsi": round(random.uniform(30, 70), 2),
                "macd": round(random.uniform(-1, 1), 4),
                "volume_ratio": round(random.uniform(0.8, 1.5), 2),
            },
            expected_return=round(random.uniform(0.01, 0.03), 4),
            expected_sharpe=round(random.uniform(0.5, 2.0), 2),
        )

        self.audit_trail.record_signal(signal)
        logger.info(f"Generated signal: {signal_id} - {signal.signal_type} for {symbol}")

        return signal

    def generate_risk_check(self, signal: SignalEvent, should_pass: bool = True) -> RiskCheckEvent:
        """Generate a risk check event."""
        risk_score = random.uniform(0.2, 0.6) if should_pass else random.uniform(0.8, 0.95)
        decision = "approve" if should_pass else "reject"

        checks = [
            RiskCheck(
                name="position_limit",
                status=RiskCheckStatus.PASS if should_pass else RiskCheckStatus.FAIL,
                value=random.uniform(0.3, 0.7),
                limit=0.8,
                message="Position within limits" if should_pass else "Position limit exceeded"
            ),
            RiskCheck(
                name="volatility",
                status=RiskCheckStatus.PASS,
                value=random.uniform(0.1, 0.3),
                limit=0.5,
                message="Volatility within acceptable range"
            ),
            RiskCheck(
                name="correlation",
                status=RiskCheckStatus.PASS,
                value=random.uniform(0.2, 0.4),
                limit=0.6,
                message="Correlation within limits"
            ),
        ]

        risk_event = RiskCheckEvent(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id=signal.signal_id,
            instrument=signal.instrument,
            risk_score=risk_score,
            checks=checks,
            decision=decision,
            reason=f"Risk score {risk_score:.3f} - {decision}"
        )

        self.audit_trail.record_risk_check(risk_event)
        logger.info(f"Risk check: {signal.signal_id} - {decision} (score: {risk_score:.3f})")

        return risk_event

    def generate_order(self, signal: SignalEvent, risk_event: RiskCheckEvent) -> OrderEvent:
        """Generate an order event."""
        # Only create order if risk approved
        if risk_event.decision != "approve":
            logger.info(f"Skipping order for {signal.signal_id} (risk rejected)")
            return None

        self.order_counter += 1
        order_id = f"test_order_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.order_counter:04d}"

        # Determine order parameters
        side = "buy" if signal.prediction > 0 else "sell"
        quantity = random.randint(10, 100)
        limit_price = round(random.uniform(100.0, 200.0), 2)

        order = OrderEvent(
            timestamp=datetime.now(tz=timezone.utc),
            order_id=order_id,
            signal_id=signal.signal_id,
            instrument=signal.instrument,
            side=side,
            quantity=quantity,
            order_type="LIMIT",
            limit_price=limit_price,
            status="SUBMITTED"
        )

        self.audit_trail.record_order(order)
        logger.info(f"Order submitted: {order_id} - {side} {quantity} @ ${limit_price}")

        return order

    def generate_fill(self, order: OrderEvent) -> FillEvent:
        """Generate a fill event."""
        if not order:
            return None

        self.fill_counter += 1
        fill_id = f"test_fill_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.fill_counter:04d}"

        # Simulate partial or full fill
        fill_quantity = order.quantity if random.random() > 0.2 else random.randint(1, order.quantity)
        
        # Simulate slippage
        slippage_bps = random.uniform(1.0, 10.0)  # 1-10 basis points
        slippage_amount = order.limit_price * (slippage_bps / 10000.0)
        fill_price = round(order.limit_price + slippage_amount, 2)

        fill = FillEvent(
            timestamp=datetime.now(tz=timezone.utc),
            fill_id=fill_id,
            order_id=order.order_id,
            instrument=order.instrument,
            side=order.side,
            quantity=fill_quantity,
            price=fill_price,
            fee=round(fill_quantity * fill_price * 0.001, 2),  # 0.1% commission
            fee_currency="USD",
            liquidity="taker",
            slippage_bps=slippage_bps
        )

        self.audit_trail.record_fill(fill)
        logger.info(f"Order filled: {fill_id} - {fill_quantity} @ ${fill_price} (slippage: {slippage_bps:.1f} bps)")

        return fill

    def generate_llm_decision(self, signal: SignalEvent, should_approve: bool = True) -> LLMDecisionEvent:
        """Generate an LLM decision event (optional)."""
        decision = "approve_signal" if should_approve else "reject_signal"

        llm_event = LLMDecisionEvent(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id=signal.signal_id,
            instrument=signal.instrument,
            llm_model="gpt-4-turbo",
            prompt=f"Analyze {signal.signal_type} signal for {signal.instrument}",
            response=f"Market conditions {'favorable' if should_approve else 'unfavorable'} for {signal.instrument}",
            reasoning=f"Based on signal strength {signal.signal_strength:.3f} and confidence {signal.confidence:.3f}",
            decision=decision,
            confidence=round(random.uniform(0.7, 0.95), 3)
        )

        self.audit_trail.record_llm_decision(llm_event)
        logger.info(f"LLM decision: {signal.signal_id} - {decision}")

        return llm_event

    def run_trading_cycle(self, include_violations: bool = False):
        """Run one complete trading cycle."""
        symbol = random.choice(self.symbols)

        # Generate signal
        signal = self.generate_signal(symbol)
        time.sleep(0.1)

        # Randomly include LLM decision (50% chance)
        if random.random() > 0.5:
            llm_event = self.generate_llm_decision(signal)
            time.sleep(0.1)

        # Generate risk check
        # If including violations, occasionally skip risk check or make it fail
        if include_violations and random.random() < 0.1:
            # Violation: No risk check
            logger.warning(f"⚠️  VIOLATION: Skipping risk check for {signal.signal_id}")
            # Create fake risk event for flow control (not recorded)
            risk_event = RiskCheckEvent(
                timestamp=datetime.now(tz=timezone.utc),
                signal_id=signal.signal_id,
                instrument=signal.instrument,
                risk_score=0.0,
                checks=[],
                decision="approve",
                reason="VIOLATION: Risk check bypassed"
            )
        else:
            should_pass = not (include_violations and random.random() < 0.15)
            risk_event = self.generate_risk_check(signal, should_pass=should_pass)
            time.sleep(0.1)

        # Generate order (only if risk approved)
        order = self.generate_order(signal, risk_event)
        if order:
            time.sleep(0.1)

            # If including violations, occasionally create order despite rejection
            if include_violations and risk_event.decision == "reject" and random.random() < 0.05:
                logger.warning(f"⚠️  VIOLATION: Creating order despite risk rejection for {signal.signal_id}")
                violation_order = OrderEvent(
                    timestamp=datetime.now(tz=timezone.utc),
                    order_id=f"violation_order_{self.order_counter:04d}",
                    signal_id=signal.signal_id,
                    instrument=signal.instrument,
                    side="buy",
                    quantity=100,
                    order_type="MARKET",
                    limit_price=None,
                    status="SUBMITTED"
                )
                self.audit_trail.record_order(violation_order)
                order = violation_order

            # Generate fill (80% chance)
            if random.random() > 0.2:
                fill = self.generate_fill(order)
                time.sleep(0.1)

                # If including violations, occasionally exceed notional limit
                if include_violations and random.random() < 0.05:
                    logger.warning(f"⚠️  VIOLATION: Excessive notional for {order.order_id}")
                    # Create violation fill with excessive price
                    violation_fill = FillEvent(
                        timestamp=datetime.now(tz=timezone.utc),
                        fill_id=f"violation_fill_{self.fill_counter:04d}",
                        order_id=order.order_id,
                        instrument=order.instrument,
                        side=order.side,
                        quantity=order.quantity,
                        price=500.0,  # Excessive price to trigger notional limit
                        fee=round(order.quantity * 500.0 * 0.001, 2),
                        fee_currency="USD",
                        liquidity="taker",
                        slippage_bps=100.0  # Excessive slippage
                    )
                    self.audit_trail.record_fill(violation_fill)


def main():
    """Run compliance test trading."""
    parser = argparse.ArgumentParser(description="Generate trading data for compliance testing")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL", "AMZN"],
        help="Symbols to trade (default: AAPL MSFT GOOGL AMZN)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=20,
        help="Number of trading cycles to run (default: 20)",
    )
    parser.add_argument(
        "--include-violations",
        action="store_true",
        help="Include compliance violations (for testing detection)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between cycles in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("Compliance Test Trading - Generating Audit Trail Data")
    print("=" * 80)
    print(f"\n📊 Configuration:")
    print(f"   Symbols: {', '.join(args.symbols)}")
    print(f"   Trading Cycles: {args.cycles}")
    print(f"   Include Violations: {args.include_violations}")
    print(f"   Cycle Delay: {args.delay}s")
    print("\n" + "=" * 80)

    # Initialize trader
    trader = ComplianceTestTrader(args.symbols)

    # Run trading cycles
    start_time = datetime.now()
    for i in range(args.cycles):
        print(f"\n📈 Trading Cycle {i+1}/{args.cycles}")
        print("-" * 80)
        
        trader.run_trading_cycle(include_violations=args.include_violations)
        
        if i < args.cycles - 1:
            time.sleep(args.delay)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Summary
    print("\n" + "=" * 80)
    print("Trading Session Complete!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Duration: {duration:.1f}s")
    print(f"   Signals Generated: {trader.signal_counter}")
    print(f"   Orders Placed: {trader.order_counter}")
    print(f"   Orders Filled: {trader.fill_counter}")
    print(f"   Violations Included: {'Yes' if args.include_violations else 'No'}")
    
    print("\n🔍 Next Steps:")
    print("   1. Run compliance analysis:")
    print("      python scripts/demo_compliance_monitoring.py")
    print("\n   2. Or check specific period:")
    print(f"      # Analyze data from {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"      # to {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.include_violations:
        print("\n⚠️  Violations were included - compliance monitor should detect:")
        print("      - Missing risk checks (CRITICAL)")
        print("      - Risk overrides (CRITICAL)")
        print("      - Excessive order notional (WARNING)")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
