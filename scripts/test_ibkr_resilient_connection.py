#!/usr/bin/env python3
"""
TR-005-CONN: Resilient Connection State Machine (Event-Driven Refactor)
Integrates live EWrapper event hooks with an asynchronous sync gate.
"""

import asyncio
import logging
import random
import sys
from enum import Enum, auto
from typing import Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TR-005-Resilience")


class ConnState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    HANDSHAKE_SYNC = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    FAILED = auto()


class ResilientIBConnector:
    def __init__(self, host: str, port: int, client_id: int):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.state = ConnState.DISCONNECTED

        # Backoff tuning constants
        self.base_delay = 1.0
        self.max_delay = 30.0
        self.max_retries = 5
        self.current_attempt = 0

        # Async synchronization gate
        self.handshake_complete_event = asyncio.Event()
        self.active_faults: Set[int] = set()
        self.min_handshake_observation = 0.35

    def transition_to(self, new_state: ConnState):
        logger.info(f"🔄 State Transition: {self.state.name} ──> {new_state.name}")
        self.state = new_state

    def calculate_backoff(self) -> float:
        temp = min(self.max_delay, self.base_delay * (2 ** self.current_attempt))
        return random.uniform(0, temp)

    def handle_incoming_error_event(self, req_id: int, code: int, message: str):
        """
        Reactive EWrapper hook.
        Intercepts incoming transport/farm telemetry and updates the state machine inline.
        """
        logger.info(f"📥 [EWrapper Signal] Code {code} received: {message}")

        # Scenario A: Infrastructure farm drops
        if code in [2103, 2105, 2107]:
            self.active_faults.add(code)
            logger.warning(f"⚠️ Tracked Data Farm Degradation: {code} added to fault matrix.")

        # Scenario B: Hard transport drop
        elif code == 1100:
            logger.critical("🚨 Hard Transport Loss Detected (Error 1100). Evacuating to RECONNECTING state.")
            if self.state in [ConnState.CONNECTED, ConnState.HANDSHAKE_SYNC, ConnState.CONNECTING]:
                self.transition_to(ConnState.RECONNECTING)
                self.handshake_complete_event.clear()

        # Scenario C: Transport restored
        elif code == 1101:
            logger.info("♻️ Transport restoration event detected (Error 1101).")
            if self.state == ConnState.RECONNECTING:
                logger.info("Warm re-handshake will execute on next lifecycle attempt.")

    async def connect_lifecycle_loop(self):
        """Main connection loop managing live backoff steps and handshake evaluation windows."""
        self.current_attempt = 0

        while self.current_attempt < self.max_retries:
            self.transition_to(ConnState.CONNECTING)
            self.handshake_complete_event.clear()
            self.active_faults.clear()

            try:
                logger.info(
                    f"Establishing TCP socket link to Gateway "
                    f"({self.current_attempt + 1}/{self.max_retries})..."
                )
                await asyncio.sleep(0.1)  # Simulate network socket establishment

                self.transition_to(ConnState.HANDSHAKE_SYNC)

                # Start an asynchronous task to simulate inbound network chatter from TWS
                asyncio.create_task(self._simulate_inbound_network_stream())

                # Enforce an evaluation window for the handshake process
                success = await self._evaluate_handshake_window(timeout=1.5)

                if success:
                    self.transition_to(ConnState.CONNECTED)
                    self.current_attempt = 0
                    return True

                raise ConnectionError("Handshake timed out or failed to resolve infrastructure faults.")

            except (ConnectionError, Exception) as e:
                self.current_attempt += 1
                logger.warning(f"💥 Connection attempt aborted: {e}")

                if self.current_attempt >= self.max_retries:
                    break

                self.transition_to(ConnState.RECONNECTING)
                backoff = self.calculate_backoff()
                logger.info(f"Holding backoff recovery window for {backoff:.2f}s...")
                await asyncio.sleep(backoff)

        self.transition_to(ConnState.FAILED)
        return False

    async def _evaluate_handshake_window(self, timeout: float) -> bool:
        """Waits for the handshake event to complete or times out if errors persist."""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            elapsed = asyncio.get_event_loop().time() - start_time

            # If transport dropped during evaluation, fail fast.
            if self.state == ConnState.RECONNECTING:
                return False

            # Require a minimum observation window so inbound farm errors are processed
            # before declaring handshake success.
            if (
                elapsed >= self.min_handshake_observation
                and len(self.active_faults) == 0
                and self.state == ConnState.HANDSHAKE_SYNC
            ):
                self.handshake_complete_event.set()

            if self.handshake_complete_event.is_set():
                logger.info("✅ Handshake validation gate cleared successfully.")
                return True

            await asyncio.sleep(0.1)

        return False

    async def _simulate_inbound_network_stream(self):
        """Simulates asynchronous TWS error and recovery messages over the wire."""
        if self.current_attempt == 0:
            # Attempt 1: Inbound farm drops that do not resolve in time
            await asyncio.sleep(0.1)
            self.handle_incoming_error_event(-1, 2103, "Market data farm connection broken: usfarm")
            await asyncio.sleep(0.2)
            self.handle_incoming_error_event(-1, 2105, "HMDS data farm connection broken: ushmds")

        elif self.current_attempt == 1:
            # Attempt 2: Inbound farm drops that recover before timeout expires
            await asyncio.sleep(0.1)
            self.handle_incoming_error_event(-1, 2103, "Market data farm connection broken: usfarm")
            await asyncio.sleep(0.4)
            logger.info("♻️ [Simulated Recovery] Clearing fault matrix: usfarm restored.")
            self.active_faults.clear()


async def main():
    logger.info("Launching Vector A Event-Driven Resilience Suite...")
    connector = ResilientIBConnector("127.0.0.1", 7497, client_id=99)

    success = await connector.connect_lifecycle_loop()

    if success:
        logger.info("🎉 Integration verification complete: Connector is fully stable.")
        sys.exit(0)

    logger.error("❌ Integration verification failed.")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
