import sys
import os

# Add the Autotrader directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

print("Python Path:", sys.path)

import pytest
import asyncio
import logging
import socket
import time
from autotrader.execution.adapters.ibkr import IBKRAdapter
from autotrader.execution.routing.router import StrategyAllocationRouter
from autotrader.strategy.pipeline import LiveStrategyPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AutoTrader.LiveFireWalk")


def is_gateway_listening(host: str, port: int) -> bool:
    """Probe local TCP socket to check whether IB Gateway/TWS is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        try:
            sock.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

@pytest.mark.asyncio
async def test_live_fire_pipeline_walkthrough():
    """
    CONOPS: Live-Fire Operational Validation Test.
    Connects to a running local TWS or IB Gateway paper instance,
    subscribes to a real streaming ticker, and fires a multi-account order block.
    """
    logger.info("Initializing Live-Fire Integration Sandpit...")

    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "4002"))
    default_client_id = ((os.getpid() % 10000) + int(time.time()) % 10000) % 65535
    client_id = int(os.getenv("IBKR_CLIENT_ID", str(default_client_id)))
    logger.info(f"Using IBKR client id: {client_id}")

    if not is_gateway_listening(host=host, port=port):
        pytest.skip(
            f"Preflight skipped: no active IB Gateway/TWS listener detected on {host}:{port}. "
            "Ensure your broker app is running and socket API access is enabled."
        )
    
    # 1. Spin up the real production adapter targeting the paper gateway port
    # Paper TWS default: 7497 | Paper IB Gateway default: 4002
    adapter = IBKRAdapter(host=host, port=port, client_id=client_id)
    
    # Override risk thresholds slightly for the live-fire verification test
    router = StrategyAllocationRouter(adapter=adapter, safety_cushion_threshold=0.10)
    
    # Define our live multi-account pool targets (replace with active paper account IDs)
    target_accounts = ["DU1111111", "DU2222222"]
    
    # Instantiate the live alpha pipe
    pipeline = LiveStrategyPipeline(router=router, target_accounts=target_accounts, policy="DYNAMIC_NLV")
    
    try:
        # 2. Open the network socket wire
        logger.info("Connecting to local Interactive Brokers network socket...")
        connected = await adapter.connect()
        if not connected or not adapter.isConnected():
            if getattr(adapter, "_global_kill_active", False):
                pytest.skip(
                    "Preflight skipped: startup broker attestation detected drift/ghost orders. "
                    "Flatten paper positions/open orders and reconcile WAL before live-fire execution."
                )
            pytest.fail(
                "Failed to stabilize network socket connection to Gateway. "
                "Ensure IB Gateway/TWS is running, socket API is enabled, and host/port/client-id are valid."
            )
        if adapter is None:
            raise RuntimeError("Adapter object is not initialized.")
        
        # 3. Request streaming Level 1 Top-of-Book market data for validation target
        ticker = "AMD"
        logger.info(f"Registering real-time market data subscription wire for: {ticker}")
        contract = adapter._create_contract(symbol=ticker)
        adapter._ensure_nbbo_subscription(contract)
        
        # 4. Await streaming quote propagation from exchange wire
        logger.info("Awaiting live exchange price feed propagation (Max 5s timeout)...")
        quote_received = False
        for _ in range(10):
            await asyncio.sleep(0.5)
            quotes = adapter.get_nbbo_snapshot(ticker)
            bid = float(quotes.get("bid") or 0.0)
            ask = float(quotes.get("ask") or 0.0)
            if bid > 0.0 and ask > 0.0:
                quote_received = True
                logger.info(f"Live market quote captured for {ticker}: Bid={bid}, Ask={ask}")
                
                # Manually invoke the pipeline processing hook to simulate the alpha trigger sequence
                pipeline.on_quote_update(
                    symbol=ticker,
                    bid=bid,
                    ask=ask,
                    bid_size=quotes.get("bid_size", 100),
                    ask_size=quotes.get("ask_size", 100)
                )
                break
                
        if not quote_received:
            logger.warning("Market data subscription timed out or exchange is dark. Forcing manual order route...")
            # If the market data loop is silent, force-trigger the submission cascade to verify the execution path
            await pipeline.execute_strategy_signal(symbol=ticker, total_qty=10, side="BUY")

        # 5. Cool down and assert execution order IDs were registered durably by TWS
        await asyncio.sleep(2.0)
        assert len(pipeline.active_signals) > 0, "Strategy layer failed to emit execution trace."
        signal_state = pipeline.active_signals.get(ticker, {})
        assert signal_state.get("status") in {"ROUTED", "PARTIAL_FILL", "FILLED"}, (
            "Execution sequence stuck outside broker wire boundaries."
        )
        logger.info(f"Live-Fire Validation Complete. Orders sent successfully: {signal_state.get('order_ids')}")

    except Exception as e:
        logger.error(f"CRITICAL SYSTEM FAILURE IN LIVE FIRE RUN: {str(e)}")
        raise
    finally:
        # 6. Gracefully tear down socket connections to prevent orphan locks on the gateway
        if adapter is not None:
            logger.info("Severing network links safely...")
            adapter.disconnect()
        else:
            logger.error("Adapter object was None. Ensure the connection was initialized properly.")
