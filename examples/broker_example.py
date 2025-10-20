"""Example: Using the Broker API directly for testing."""

from bouncehunter.broker import create_broker, OrderSide, OrderType


def example_paper_broker():
    """Example: Paper broker for testing."""
    print("=" * 60)
    print("PAPER BROKER EXAMPLE")
    print("=" * 60)

    # Create paper broker with $100k
    broker = create_broker("paper", initial_cash=100_000.0)

    # Check account
    account = broker.get_account()
    print(f"\nInitial Account:")
    print(f"  Cash: ${account.cash:,.2f}")
    print(f"  Portfolio Value: ${account.portfolio_value:,.2f}")

    # Place a bracket order
    print(f"\nPlacing bracket order for AAPL...")
    orders = broker.place_bracket_order(
        ticker="AAPL",
        quantity=10,
        entry_price=172.50,
        stop_price=168.20,
        target_price=179.80,
    )

    print(f"  Entry Order: {orders['entry'].order_id} ({orders['entry'].status})")
    print(f"  Stop Order: {orders['stop'].order_id}")
    print(f"  Target Order: {orders['target'].order_id}")

    # Check position
    position = broker.get_position("AAPL")
    if position:
        print(f"\nPosition:")
        print(f"  Ticker: {position.ticker}")
        print(f"  Shares: {position.shares}")
        print(f"  Avg Price: ${position.avg_price:.2f}")
        print(f"  Market Value: ${position.market_value:,.2f}")

    # Check account after trade
    account = broker.get_account()
    print(f"\nAccount After Trade:")
    print(f"  Cash: ${account.cash:,.2f}")
    print(f"  Portfolio Value: ${account.portfolio_value:,.2f}")
    print(f"  Positions: {len(account.positions)}")


def example_alpaca_broker():
    """Example: Alpaca broker (requires API keys)."""
    print("\n" + "=" * 60)
    print("ALPACA BROKER EXAMPLE")
    print("=" * 60)

    # Replace with your actual keys
    API_KEY = "YOUR_API_KEY"
    SECRET_KEY = "YOUR_SECRET_KEY"

    try:
        broker = create_broker(
            "alpaca",
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            paper=True,  # Use paper account
        )

        # Check if market is open
        is_open = broker.is_market_open()
        print(f"\nMarket Open: {is_open}")

        # Get account info
        account = broker.get_account()
        print(f"\nAccount:")
        print(f"  Cash: ${account.cash:,.2f}")
        print(f"  Portfolio Value: ${account.portfolio_value:,.2f}")
        print(f"  Buying Power: ${account.buying_power:,.2f}")

        # List positions
        positions = broker.get_positions()
        if positions:
            print(f"\nCurrent Positions:")
            for pos in positions:
                pnl_symbol = "🟢" if pos.unrealized_pnl > 0 else "🔴"
                print(
                    f"  {pnl_symbol} {pos.ticker}: {pos.shares} @ ${pos.avg_price:.2f} | "
                    f"P&L: ${pos.unrealized_pnl:.2f} ({pos.unrealized_pnl_pct:.1%})"
                )
        else:
            print(f"\nNo open positions")

        # Example: Place a market order (BE CAREFUL - this is real!)
        # broker.place_order(
        #     ticker="SPY",
        #     side=OrderSide.BUY,
        #     quantity=1,
        #     order_type=OrderType.MARKET,
        # )

    except ImportError:
        print("\nAlpaca integration not installed.")
        print("Run: pip install alpaca-py")
    except Exception as e:
        print(f"\nError: {e}")
        print("Check your API keys and ensure they're for a paper account.")


def example_position_management():
    """Example: Position tracking and management."""
    print("\n" + "=" * 60)
    print("POSITION MANAGEMENT EXAMPLE")
    print("=" * 60)

    broker = create_broker("paper", initial_cash=100_000.0)

    # Buy multiple tickers
    tickers = ["AAPL", "MSFT", "GOOGL"]
    for ticker in tickers:
        broker.place_order(
            ticker=ticker,
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            limit_price=100.0,  # Simplified price
        )
        print(f"Bought 10 shares of {ticker}")

    # List all positions
    print(f"\nAll Positions:")
    for pos in broker.get_positions():
        print(f"  {pos.ticker}: {pos.shares} shares @ ${pos.avg_price:.2f}")

    # Close a specific position
    print(f"\nClosing MSFT position...")
    order = broker.close_position("MSFT")
    print(f"  Order: {order.order_id} ({order.status})")

    # Check remaining positions
    print(f"\nRemaining Positions:")
    for pos in broker.get_positions():
        print(f"  {pos.ticker}: {pos.shares} shares")


def example_order_tracking():
    """Example: Order status tracking."""
    print("\n" + "=" * 60)
    print("ORDER TRACKING EXAMPLE")
    print("=" * 60)

    broker = create_broker("paper")

    # Place an order
    order = broker.place_order(
        ticker="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        limit_price=172.50,
    )

    print(f"Order ID: {order.order_id}")
    print(f"Status: {order.status}")
    print(f"Submitted: {order.submitted_at}")

    # Check order status
    order = broker.get_order(order.order_id)
    print(f"\nUpdated Status: {order.status}")
    if order.filled_qty > 0:
        print(f"Filled: {order.filled_qty}/{order.quantity}")
        print(f"Fill Price: ${order.filled_price:.2f}")
        print(f"Filled At: {order.filled_at}")

    # Cancel order (if not filled)
    if order.status.value not in ["FILLED", "CANCELLED"]:
        success = broker.cancel_order(order.order_id)
        if success:
            print(f"\nOrder {order.order_id} cancelled")


if __name__ == "__main__":
    # Run examples
    example_paper_broker()
    example_position_management()
    example_order_tracking()

    # Uncomment to test Alpaca (requires API keys)
    # example_alpaca_broker()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
