#!/usr/bin/env python
"""
Phase 5 live staging runner.

Replays synthetic live-like market ticks through the live execution stack,
applies the Phase 4 policy handoff, and captures a structured status snapshot
for paper/training verification.

Usage:
    python scripts/run_live_staging.py \
        --config configs/crypto_strategy_multimag_sweep.yaml \
        --policy-json reports/crypto/policy_handoff_pass.json
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import random
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterable, Dict, List, Optional
from inspect import isawaitable

import yaml


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autotrader.execution.adapters import OrderSide, OrderType
from autotrader.execution.adapters.paper import PaperTradingAdapter
from autotrader.execution.adapters.binance_testnet import BinanceTestnetAdapter
from autotrader.execution.adapters.kraken import KrakenAdapter
from autotrader.execution.live import (
    BinanceTestnetTransportAdapter,
    LiveExecutionEngine,
    LiveExecutionEngineConfig,
)
from autotrader.execution.live.contracts import PortfolioStateSnapshot
from autotrader.schemas.market_data import AssetClass, OHLCV


logger = logging.getLogger("autotrader.scripts.run_live_staging")


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_local_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _extract_symbols(strategy_config: Dict[str, Any]) -> List[str]:
    explicit_symbols = strategy_config.get("symbols") or {}
    if isinstance(explicit_symbols, dict) and explicit_symbols:
        return list(explicit_symbols.keys())

    asset_tiers = ((strategy_config.get("portfolio_routing") or {}).get("asset_priority_tiers") or [])
    routed_symbols = [str(item.get("symbol")) for item in asset_tiers if item.get("symbol")]
    if routed_symbols:
        return routed_symbols

    return ["BTC/USD", "ETH/USD"]


def _normalize_symbols_for_mode(symbols: List[str], mode: str) -> List[str]:
    normalized: List[str] = []
    for symbol in symbols:
        raw = str(symbol).strip().upper().replace("-", "/")
        if mode == "testnet":
            if raw.endswith("/USD"):
                raw = raw[:-4] + "/USDT"
            raw = raw.replace("/", "")
        elif mode == "kraken":
            if "/" not in raw and raw.endswith("USDT"):
                raw = raw[:-4] + "/USDT"
            elif "/" not in raw and raw.endswith("USD"):
                raw = raw[:-3] + "/USD"
        normalized.append(raw)
    return normalized


def _extract_quote_asset(symbol: str) -> str:
    raw = str(symbol).strip().upper().replace("-", "/")
    if "/" in raw:
        return raw.split("/", 1)[1]
    known_quotes = ["USDT", "USD", "USDC", "EUR", "GBP", "JPY", "BTC", "ETH"]
    for quote in known_quotes:
        if raw.endswith(quote) and len(raw) > len(quote):
            return quote
    return "USD"


def _quote_balance_from_snapshot(balances: Dict[str, float], quote_asset: str) -> float:
    quote = str(quote_asset).upper()
    aliases = {
        "USD": ["USD", "ZUSD", "USDT"],
        "USDT": ["USDT", "USD", "ZUSD"],
        "EUR": ["EUR", "ZEUR"],
        "GBP": ["GBP", "ZGBP"],
        "JPY": ["JPY", "ZJPY"],
    }
    candidates = aliases.get(quote, [quote])
    total = 0.0
    for key in candidates:
        total += float(balances.get(key, 0.0) or 0.0)
    return total


def _default_ibkr_probe_price(symbol: str, sec_type: str, fallback_price: float) -> float:
    """Provide deterministic, low-risk defaults for explicit IBKR paper probes."""
    if str(sec_type).upper() != "STK":
        return float(fallback_price)

    stock_probe_defaults = {
        "SNDL": 2.0,
    }
    return float(stock_probe_defaults.get(str(symbol).upper(), float(fallback_price)))


def _parse_bool(value: str) -> bool:
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected boolean value, got: {value}")


def _symbol_base_prices(symbols: List[str]) -> Dict[str, float]:
    defaults = {
        "BTC/USD": 65_000.0,
        "BTCUSDT": 65_000.0,
        "BTC-USD": 65_000.0,
        "ETH/USD": 3_500.0,
        "ETHUSDT": 3_500.0,
        "ETH-USD": 3_500.0,
    }
    fallback = 100.0
    return {symbol: defaults.get(symbol, fallback + index * 25.0) for index, symbol in enumerate(symbols)}


def _build_portfolio_snapshot(paper_adapter: PaperTradingAdapter, source: str) -> PortfolioStateSnapshot:
    positions = {
        symbol: float(position.quantity)
        for symbol, position in paper_adapter.positions.items()
        if abs(float(position.quantity)) > 0.0
    }
    open_order_ids = [
        order_id
        for order_id, order in paper_adapter.orders.items()
        if order.is_open()
    ]
    account = {
        "cash": float(paper_adapter.balance),
        "position_value": sum(position.quantity * position.current_price for position in paper_adapter.positions.values()),
        "total_equity": float(paper_adapter.balance)
        + sum(position.quantity * position.current_price for position in paper_adapter.positions.values()),
    }
    return PortfolioStateSnapshot(
        timestamp=datetime.now(timezone.utc),
        positions=positions,
        open_order_ids=open_order_ids,
        cash=account["cash"],
        equity=account["total_equity"],
        source=source,
        metadata={"account": account},
    )


class MockLiveTickReplay:
    """Synthetic transport provider for staging and paper verification."""

    def __init__(
        self,
        symbols: List[str],
        bar_interval_minutes: int,
        bars_to_emit: int,
        ticks_per_bar: int,
        sleep_seconds: float,
        seed: int = 7,
    ):
        self.symbols = list(symbols)
        self.bar_interval_minutes = int(bar_interval_minutes)
        self.interval_us = self.bar_interval_minutes * 60 * 1_000_000
        self.bars_to_emit = int(bars_to_emit)
        self.ticks_per_bar = max(1, int(ticks_per_bar))
        self.sleep_seconds = max(0.0, float(sleep_seconds))
        self.random = random.Random(seed)
        self.base_prices = _symbol_base_prices(self.symbols)
        self.current_prices = dict(self.base_prices)
        self.base_time = datetime.now(timezone.utc).replace(microsecond=0)

    async def stream(self, symbols: List[str]) -> AsyncIterable[Dict[str, Any]]:
        active_symbols = [symbol for symbol in symbols if symbol in self.base_prices] or list(self.symbols)
        if not active_symbols:
            active_symbols = list(self.symbols)

        for bar_index in range(self.bars_to_emit):
            bar_open = self.base_time + timedelta(minutes=bar_index * self.bar_interval_minutes)
            bar_open_us = int(bar_open.timestamp() * 1_000_000)

            for tick_index in range(self.ticks_per_bar):
                offset_us = int((tick_index / self.ticks_per_bar) * self.interval_us)
                event_time_us = bar_open_us + offset_us
                exchange_time_us = event_time_us + self.random.randint(0, 2_000)

                for symbol in active_symbols:
                    drift = self.random.uniform(-0.0015, 0.0015)
                    trend = (bar_index + 1) * 0.0002
                    last_price = self.current_prices[symbol]
                    next_price = max(0.01, last_price * (1.0 + drift + trend))
                    self.current_prices[symbol] = next_price

                    quantity = round(max(0.001, self.random.uniform(0.05, 1.5)), 6)
                    yield {
                        "symbol": symbol,
                        "venue": "SIM",
                        "asset_class": "crypto",
                        "event_time_us": event_time_us,
                        "exchange_time_us": exchange_time_us,
                        "price": round(next_price, 6),
                        "quantity": quantity,
                        "side": "BUY" if tick_index % 2 == 0 else "SELL",
                        "sequence_id": bar_index * self.ticks_per_bar + tick_index + 1,
                        "flags": "replay",
                    }

                if self.sleep_seconds:
                    await asyncio.sleep(self.sleep_seconds)


def _build_runtime_config(
    strategy_config: Dict[str, Any],
    policy: Dict[str, Any],
    symbols: List[str],
    bar_interval_minutes: int,
    venue: str,
) -> LiveExecutionEngineConfig:
    optimum = policy.get("operational_optimum") or policy.get("theoretical_optimum") or {}
    merged_config = _deep_merge(strategy_config, {})

    position_sizing = merged_config.setdefault("position_sizing", {})
    position_sizing["high_correlation_scale"] = float(optimum.get("position_scaling_factor", position_sizing.get("high_correlation_scale", 0.5)))

    routing = merged_config.setdefault("portfolio_routing", {})
    routing["latency_lookback_bars"] = int(optimum.get("latency_lookback_bars", routing.get("latency_lookback_bars", 0)))
    routing["correlation_gating_threshold"] = float(optimum.get("correlation_gating_threshold", routing.get("correlation_gating_threshold", 0.75)))
    routing["max_simultaneous_assets"] = int(optimum.get("max_assets", routing.get("max_simultaneous_assets", len(symbols))))

    return LiveExecutionEngineConfig(
        symbols=symbols,
        venue=venue,
        asset_class=AssetClass.CRYPTO,
        bar_interval_minutes=bar_interval_minutes,
        rest_fallback_seconds=1,
        reconciler_interval_seconds=1.0,
        heartbeat_timeout_seconds=30.0,
        drift_tolerance_qty=0.0,
        max_open_orders=100,
        order_timeout_seconds=300.0,
        max_completed_bars=5_000,
        shutdown_timeout_seconds=10.0,
        install_signal_handlers=True,
    )


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )


async def _run_staging(args: argparse.Namespace) -> Dict[str, Any]:
    config_path = (PROJECT_ROOT / args.config).resolve()
    policy_path = (PROJECT_ROOT / args.policy_json).resolve()
    output_path = (PROJECT_ROOT / args.status_output).resolve()
    _load_local_env_file(PROJECT_ROOT / ".env")

    strategy_config = _load_yaml(config_path)
    policy = _load_json(policy_path)

    if str(policy.get("status", "")).upper() != "PASS":
        raise SystemExit(f"Policy handoff is not PASS: {policy.get('status')}")

    selected_policy = policy.get("operational_optimum") or policy.get("theoretical_optimum") or {}
    symbols = _extract_symbols(strategy_config)

    mode = str(args.mode).strip().lower()
    if mode not in {"synthetic", "testnet", "kraken", "ibkr"}:
        raise SystemExit(f"Unsupported mode: {args.mode}")

    symbols = _normalize_symbols_for_mode(symbols, mode)
    venue = "SIM" if mode == "synthetic" else ("BINANCE_TESTNET" if mode == "testnet" else ("KRAKEN" if mode == "kraken" else "IBKR"))
    runtime_config = _build_runtime_config(
        strategy_config,
        policy,
        symbols,
        args.bar_interval_minutes,
        venue=venue,
    )

    logger.info("Loaded staging policy from %s", policy_path)
    logger.info(
        "Policy selection: threshold=%s max_assets=%s scale=%s lookback=%s",
        selected_policy.get("correlation_gating_threshold"),
        selected_policy.get("max_assets"),
        selected_policy.get("position_scaling_factor"),
        selected_policy.get("latency_lookback_bars"),
    )
    logger.info("Loaded strategy template from %s", config_path)
    logger.info("Staging symbols: %s", ", ".join(symbols))
    logger.info("Staging mode: %s", mode)

    effective_transmit = bool(args.transmit)
    if args.paper_only:
        effective_transmit = False

    if args.probe_balance_only and mode not in {"testnet", "kraken", "ibkr"}:
        raise SystemExit("--probe-balance-only requires an authenticated mode (testnet, kraken, or ibkr)")


    if mode == "synthetic":
        logger.info("Initializing Live Staging in SYNTHETIC mode using PaperTradingAdapter.")
        broker_adapter = PaperTradingAdapter(initial_balance=float(args.initial_balance))
        await broker_adapter.connect()
        replay: Optional[MockLiveTickReplay] = None
        testnet_transport: Optional[BinanceTestnetTransportAdapter] = None
        transport_stream_provider = None
        replay = MockLiveTickReplay(
            symbols=symbols,
            bar_interval_minutes=args.bar_interval_minutes,
            bars_to_emit=args.bars,
            ticks_per_bar=args.ticks_per_bar,
            sleep_seconds=args.tick_sleep_seconds,
            seed=args.seed,
        )
    elif mode == "testnet":
        logger.info("Initializing Live Staging in TESTNET mode using Authenticated BinanceTestnetAdapter.")
        broker_adapter = BinanceTestnetAdapter()
        connected = await broker_adapter.connect()
        if not connected:
            raise SystemExit("Failed to establish authenticated session with Binance Testnet.")
        testnet_transport = BinanceTestnetTransportAdapter(
            websocket_url=args.testnet_ws_url,
            reconnect_delay_seconds=args.testnet_reconnect_seconds,
            quote_asset=args.testnet_quote_asset,
        )
        transport_stream_provider = testnet_transport.stream
        replay = None
    elif mode == "kraken":
        logger.info("Initializing Live Staging in KRAKEN mode using Authenticated KrakenAdapter.")
        broker_adapter = KrakenAdapter()
        connected = await broker_adapter.connect()
        if not connected:
            raise SystemExit("Failed to establish authenticated session with Kraken.")
        testnet_transport = None
        # Kraken transport is not yet wired; feed a replay stream so market-data
        # and bar-close callbacks remain active while validating private API flow.
        transport_stream_provider = None
        replay = MockLiveTickReplay(
            symbols=symbols,
            bar_interval_minutes=args.bar_interval_minutes,
            bars_to_emit=args.bars,
            ticks_per_bar=args.ticks_per_bar,
            sleep_seconds=args.tick_sleep_seconds,
            seed=args.seed,
        )
        transport_stream_provider = replay.stream
    elif mode == "ibkr":
        logger.info("Initializing Live Staging in IBKR mode via local IB Gateway/TWS socket.")
        try:
            from autotrader.execution.adapters.ibkr import IBKRAdapter
        except Exception as exc:
            raise SystemExit(
                "IBKR adapter import failed. Ensure ibapi is installed and available (pip install ibapi)."
            ) from exc

        broker_adapter = IBKRAdapter(
            host=args.ibkr_host,
            port=int(args.ibkr_port),
            client_id=int(args.ibkr_client_id),
        )
        connected = await broker_adapter.connect()
        if not connected:
            raise SystemExit(
                f"Could not connect to IBKR at {args.ibkr_host}:{args.ibkr_port}. Ensure IB Gateway/TWS is running with API sockets enabled."
            )
        testnet_transport = None
        replay = MockLiveTickReplay(
            symbols=symbols,
            bar_interval_minutes=args.bar_interval_minutes,
            bars_to_emit=args.bars,
            ticks_per_bar=args.ticks_per_bar,
            sleep_seconds=args.tick_sleep_seconds,
            seed=args.seed,
        )
        transport_stream_provider = replay.stream

    # Read-only auth probe: validate private API credentials and balance schema,
    # then short-circuit before any order-placement pathways are reached.
    if args.probe_balance_only:
        if args.probe_order:
            logger.info("--probe-balance-only enabled; skipping order probe even though --probe-order is set.")

        started_at = datetime.now(timezone.utc)
        balances = await broker_adapter.get_account_balance()
        logger.info(
            "Balance-only probe passed via private endpoint. Assets=%d NonZero=%d",
            len(balances),
            sum(1 for value in balances.values() if float(value) > 0.0),
        )

        status = {
            "running": False,
            "stopping": False,
            "kill_switch_engaged": False,
            "active_orders": 0,
            "symbols": symbols,
            "completed_bars": {symbol: 0 for symbol in symbols},
            "started_at": started_at.isoformat(),
            "stopped_at": datetime.now(timezone.utc).isoformat(),
            "stop_reason": "probe balance-only completed",
            "config_path": str(config_path),
            "policy_path": str(policy_path),
            "policy_status": policy.get("status"),
            "selected_policy": selected_policy,
            "preflight": {
                "mode": mode,
                "balance_only": True,
                "assets_returned": len(balances),
                "non_zero_assets": sum(1 for value in balances.values() if float(value) > 0.0),
                "balances": balances,
            },
            "runtime": {
                "mode": mode,
                "bars_requested": args.bars,
                "ticks_per_bar": args.ticks_per_bar,
                "tick_sleep_seconds": args.tick_sleep_seconds,
                "probe_order_enabled": bool(args.probe_order),
                "probe_order_quantity": args.probe_order_quantity,
                "probe_symbol": args.probe_symbol,
                "probe_sec_type": args.probe_sec_type,
                "probe_currency": args.probe_currency,
                "probe_exchange": args.probe_exchange,
                "probe_balance_only": bool(args.probe_balance_only),
                "probe_requires_balance": bool(args.probe_requires_balance),
                "probe_min_quote_balance": args.probe_min_quote_balance,
                "paper_only": bool(args.paper_only),
                "transmit": bool(args.transmit),
                "effective_transmit": bool(effective_transmit),
                "max_order_notional": float(args.max_order_notional),
                "ibkr_host": args.ibkr_host,
                "ibkr_port": args.ibkr_port,
                "ibkr_client_id": args.ibkr_client_id,
                "testnet_ws_url": args.testnet_ws_url,
                "testnet_reconnect_seconds": args.testnet_reconnect_seconds,
                "testnet_duration_seconds": args.testnet_duration_seconds,
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(status, handle, indent=2, sort_keys=True)
            handle.write("\n")

        logger.info("Wrote staging status snapshot to %s", output_path)
        with contextlib.suppress(Exception):
            disconnect_result = broker_adapter.disconnect()
            if isawaitable(disconnect_result):
                await disconnect_result
        return status
    completed_bars = 0
    probe_order_submitted = False
    probe_order_in_flight = False


    async def on_completed_bar(bar: OHLCV, engine: LiveExecutionEngine) -> None:
        nonlocal completed_bars, probe_order_submitted, probe_order_in_flight

        if mode == "synthetic":
            broker_adapter.set_price(bar.symbol, float(bar.close))
        completed_bars += 1

        logger.info(
            "BAR CLOSE | %s | ts=%s | O=%.4f H=%.4f L=%.4f C=%.4f V=%.4f | completed=%d/%d",
            bar.symbol,
            bar.timestamp.isoformat(),
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
            completed_bars,
            args.bars,
        )

        # Probe order logic for authenticated modes.
        if mode in {"testnet", "kraken", "ibkr"} and args.probe_order and not probe_order_submitted:
            probe_order_submitted = True
            probe_order_in_flight = True
            logger.info("====== STARTING LIVE PRIVATE API PROBE RUN (%s) ======", mode.upper())
            default_probe_symbol = symbols[0] if symbols else ("BTCUSDT" if mode == "testnet" else ("XBT/USD" if mode == "kraken" else "AAPL"))
            probe_symbol = str(args.probe_symbol or default_probe_symbol)
            probe_price = 15000.0 if mode == "testnet" else (10000.0 if mode == "kraken" else float(bar.close))
            if mode == "ibkr":
                probe_price = _default_ibkr_probe_price(
                    symbol=probe_symbol,
                    sec_type=args.probe_sec_type,
                    fallback_price=probe_price,
                )
            try:
                balances = await broker_adapter.get_account_balance()
                logger.info(
                    "Pre-flight auth check passed via private balance endpoint. Assets=%d",
                    len(balances),
                )

                quote_asset = _extract_quote_asset(probe_symbol)
                quote_balance = _quote_balance_from_snapshot(balances, quote_asset)
                required_quote = float(args.probe_order_quantity) * float(probe_price)
                min_required = max(required_quote, float(args.probe_min_quote_balance))

                if args.probe_requires_balance and quote_balance < min_required:
                    logger.warning(
                        "Skipping probe order due to insufficient %s balance: available=%.8f required>=%.8f",
                        quote_asset,
                        quote_balance,
                        min_required,
                    )
                    return

                logger.info(
                    "Submitting private probe order: symbol=%s side=BUY qty=%.6f price=%.4f",
                    probe_symbol,
                    float(args.probe_order_quantity),
                    probe_price,
                )

                probe_notional = float(args.probe_order_quantity) * float(probe_price)
                if mode == "ibkr" and probe_notional > float(args.max_order_notional):
                    logger.warning(
                        "Skipping IBKR probe order because notional %.4f exceeds max-order-notional %.4f",
                        probe_notional,
                        float(args.max_order_notional),
                    )
                    return

                updated_order = await engine.submit_order(
                    symbol=probe_symbol,
                    side=OrderSide.BUY,
                    quantity=float(args.probe_order_quantity),
                    order_type=OrderType.LIMIT,
                    price=probe_price,
                    time_in_force=("DAY" if mode == "ibkr" else "GTC"),
                    ibkr_transmit=effective_transmit,
                    ibkr_symbol=probe_symbol,
                    ibkr_sec_type=args.probe_sec_type,
                    ibkr_currency=args.probe_currency,
                    ibkr_exchange=args.probe_exchange,
                )
                logger.info("Probe order acknowledged by exchange. Assigned ID: %s", updated_order.order_id)
                await asyncio.sleep(1.5)
                logger.info("Initiating cancellation for probe order: %s", updated_order.order_id)
                cancelled = await engine.cancel_order(updated_order.order_id)
                if cancelled:
                    logger.info("Probe order successfully purged from the testnet orderbook. Safety pristine.")
                elif mode == "ibkr" and not effective_transmit:
                    logger.info(
                        "Probe order cleanup already completed for non-transmitting IBKR flow."
                    )
                else:
                    logger.warning("Cancellation request returned false. Manual inspection recommended.")
            except Exception as e:
                logger.error(f"Catastrophic failure during private API execution probe: {str(e)}")
                logger.error("Triggering structural safety engine teardown.")
            finally:
                probe_order_in_flight = False
                logger.info("Private API probe sequence completed. Stopping live execution tracking layer.")
                engine.request_stop("probe sequence completed")
                return

        if mode == "synthetic" and completed_bars >= args.bars:
            engine.request_stop(f"target bars reached: {completed_bars}")


    def exchange_snapshot_provider() -> PortfolioStateSnapshot:
        if mode == "synthetic":
            return _build_portfolio_snapshot(broker_adapter, source="paper_exchange")
        # For testnet, you may want to implement a real snapshot from the exchange
        return PortfolioStateSnapshot(timestamp=datetime.now(timezone.utc), positions={}, open_order_ids=[], source="testnet_exchange")


    engine = LiveExecutionEngine(
        broker_adapter=broker_adapter,
        config=runtime_config,
        local_snapshot_provider=None,
        exchange_snapshot_provider=exchange_snapshot_provider,
        transport_stream_provider=transport_stream_provider,
        rest_snapshot_provider=None,
        strategy_bar_callback=on_completed_bar,
        shutdown_callback=None,
    )

    async def feed_replay() -> None:
        if replay is None:
            return

        async for payload in replay.stream(symbols):
            if not engine.running or engine.stopping:
                break
            engine.market_data.parse_websocket_message(payload)

        # Keep the engine alive briefly if a probe is enabled and still running.
        wait_guard = 0
        while args.probe_order and engine.running and not engine.stopping and (not probe_order_submitted or probe_order_in_flight):
            await asyncio.sleep(0.1)
            wait_guard += 1
            if wait_guard >= 200:  # 20s max guard
                break

        if engine.running and not engine.stopping:
            engine.request_stop("replay stream completed")

    async def stop_after_duration() -> None:
        if mode != "testnet" or args.testnet_duration_seconds <= 0:
            return

        await asyncio.sleep(float(args.testnet_duration_seconds))
        if engine.running and not engine.stopping:
            engine.request_stop(f"testnet duration elapsed: {args.testnet_duration_seconds}s")

    async def monitor_runtime() -> None:
        while not runtime_task.done():
            logger.info(
                "HEARTBEAT | age=%.2fs | last_audit=%s | last_heartbeat=%s | kill_switch=%s | completed_bars=%s",
                engine.reconciler.heartbeat_age_seconds() or 0.0,
                engine.reconciler.last_audit_at.isoformat() if engine.reconciler.last_audit_at else None,
                engine.reconciler.last_heartbeat_at.isoformat() if engine.reconciler.last_heartbeat_at else None,
                engine.oms.kill_switch_engaged,
                {symbol: len(history) for symbol, history in engine.market_data.completed_bars.items()},
            )
            await asyncio.sleep(1.0)

    runtime_task = asyncio.create_task(engine.run())
    replay_task = asyncio.create_task(feed_replay()) if mode == "synthetic" else None
    duration_task = asyncio.create_task(stop_after_duration()) if mode == "testnet" else None
    monitor_task = asyncio.create_task(monitor_runtime())

    try:
        await runtime_task
    finally:
        if replay_task is not None:
            replay_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await replay_task

        if duration_task is not None:
            duration_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await duration_task

        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task

        with contextlib.suppress(Exception):
            await engine.stop("staging runner shutdown")

        if testnet_transport is not None:
            testnet_transport.stop()

        with contextlib.suppress(Exception):
            disconnect_result = broker_adapter.disconnect()
            if isawaitable(disconnect_result):
                await disconnect_result

    status = engine.get_status()
    status.update(
        {
            "config_path": str(config_path),
            "policy_path": str(policy_path),
            "policy_status": policy.get("status"),
            "selected_policy": selected_policy,
            "runtime": {
                "mode": mode,
                "bars_requested": args.bars,
                "ticks_per_bar": args.ticks_per_bar,
                "tick_sleep_seconds": args.tick_sleep_seconds,
                "probe_order_enabled": bool(args.probe_order),
                "probe_order_quantity": args.probe_order_quantity,
                "probe_symbol": args.probe_symbol,
                "probe_sec_type": args.probe_sec_type,
                "probe_currency": args.probe_currency,
                "probe_exchange": args.probe_exchange,
                "probe_balance_only": bool(args.probe_balance_only),
                "probe_requires_balance": bool(args.probe_requires_balance),
                "probe_min_quote_balance": args.probe_min_quote_balance,
                "paper_only": bool(args.paper_only),
                "transmit": bool(args.transmit),
                "effective_transmit": bool(effective_transmit),
                "max_order_notional": float(args.max_order_notional),
                "ibkr_host": args.ibkr_host,
                "ibkr_port": args.ibkr_port,
                "ibkr_client_id": args.ibkr_client_id,
                "testnet_ws_url": args.testnet_ws_url,
                "testnet_reconnect_seconds": args.testnet_reconnect_seconds,
                "testnet_duration_seconds": args.testnet_duration_seconds,
            },
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(status, handle, indent=2, sort_keys=True)
        handle.write("\n")

    logger.info("Wrote staging status snapshot to %s", output_path)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 5 live staging harness.")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "testnet", "kraken", "ibkr"],
        default="synthetic",
        help="Transport mode: deterministic replay, Binance testnet, Kraken authenticated, or IBKR socket mode",
    )
    parser.add_argument("--config", default="configs/crypto_strategy_multimag_sweep.yaml", help="Strategy template YAML to load")
    parser.add_argument("--policy-json", default="reports/crypto/policy_handoff_pass.json", help="Phase 4 policy handoff JSON")
    parser.add_argument("--status-output", default="reports/crypto/live_staging_status.json", help="Path to write the final status snapshot")
    parser.add_argument("--bar-interval-minutes", type=int, default=15, help="Virtual bar interval used by the replay stream")
    parser.add_argument("--bars", type=int, default=3, help="Number of virtual bars to replay before stopping")
    parser.add_argument("--ticks-per-bar", type=int, default=6, help="Synthetic ticks emitted per virtual bar and symbol")
    parser.add_argument("--tick-sleep-seconds", type=float, default=0.05, help="Real-time delay between synthetic tick batches")
    parser.add_argument("--initial-balance", type=float, default=100_000.0, help="Starting paper balance")
    parser.add_argument("--probe-order", dest="probe_order", action="store_true", help="Submit a small probe order on the first completed bar")
    parser.add_argument("--no-probe-order", dest="probe_order", action="store_false", help="Disable the probe order")
    parser.set_defaults(probe_order=True)
    parser.add_argument("--probe-order-quantity", type=float, default=0.001, help="Probe order quantity used when the probe is enabled")
    parser.add_argument("--probe-symbol", default=None, help="Explicit probe symbol/contract root (e.g., SNDL, AAPL, BTC/USD)")
    parser.add_argument("--probe-sec-type", default="STK", help="IBKR security type used for probe contract (e.g., STK, CASH, CRYPTO)")
    parser.add_argument("--probe-currency", default="USD", help="IBKR contract currency used for probe orders")
    parser.add_argument("--probe-exchange", default="SMART", help="IBKR exchange/route used for probe contract")
    parser.add_argument(
        "--probe-balance-only",
        action="store_true",
        help="Read-only authenticated probe: query private balance and exit without placing orders",
    )
    parser.add_argument(
        "--probe-requires-balance",
        dest="probe_requires_balance",
        action="store_true",
        help="Require sufficient quote balance before placing probe order",
    )
    parser.add_argument(
        "--no-probe-requires-balance",
        dest="probe_requires_balance",
        action="store_false",
        help="Allow probe order attempt even when quote balance appears insufficient",
    )
    parser.set_defaults(probe_requires_balance=True)
    parser.add_argument(
        "--probe-min-quote-balance",
        type=float,
        default=0.0,
        help="Minimum quote-asset balance threshold required for probe order (in quote units)",
    )
    parser.add_argument("--paper-only", action="store_true", help="Force non-transmitting behavior for broker probes (safety mode)")
    parser.add_argument(
        "--transmit",
        type=_parse_bool,
        default=False,
        help="Whether broker orders are transmitted (true/false). Default false for safety.",
    )
    parser.add_argument(
        "--max-order-notional",
        type=float,
        default=5.0,
        help="Maximum allowed notional for a probe order before it is skipped.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Seed for the synthetic replay stream")
    parser.add_argument(
        "--testnet-ws-url",
        default="wss://stream.testnet.binance.vision/ws",
        help="WebSocket endpoint for testnet mode",
    )
    parser.add_argument(
        "--testnet-reconnect-seconds",
        type=float,
        default=2.0,
        help="Reconnect delay after testnet websocket interruptions",
    )
    parser.add_argument(
        "--testnet-duration-seconds",
        type=float,
        default=60.0,
        help="Auto-stop duration in testnet mode (<=0 disables timed stop)",
    )
    parser.add_argument(
        "--testnet-quote-asset",
        default="USDT",
        help="Quote asset used when mapping canonical symbols like BTC/USD to exchange symbols",
    )
    parser.add_argument("--ibkr-host", default="127.0.0.1", help="IBKR API socket host (Gateway/TWS)")
    parser.add_argument("--ibkr-port", type=int, default=4002, help="IBKR API socket port (Gateway paper usually 4002; TWS paper often 7497)")
    parser.add_argument("--ibkr-client-id", type=int, default=99, help="IBKR API client ID")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    _configure_logging(args.log_level)

    try:
        status = asyncio.run(_run_staging(args))
    except SystemExit:
        raise
    except Exception as exc:
        logger.exception("Live staging runner failed: %s", exc)
        return 1

    logger.info(
        "Staging complete | running=%s kill_switch=%s completed_bars=%s",
        status.get("running"),
        status.get("kill_switch_engaged"),
        status.get("completed_bars"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())