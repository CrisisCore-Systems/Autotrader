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
import random
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterable, Dict, List, Optional

import yaml


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from autotrader.execution.adapters import OrderSide, OrderType
from autotrader.execution.adapters.paper import PaperTradingAdapter
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


def _extract_symbols(strategy_config: Dict[str, Any]) -> List[str]:
    explicit_symbols = strategy_config.get("symbols") or {}
    if isinstance(explicit_symbols, dict) and explicit_symbols:
        return list(explicit_symbols.keys())

    asset_tiers = ((strategy_config.get("portfolio_routing") or {}).get("asset_priority_tiers") or [])
    routed_symbols = [str(item.get("symbol")) for item in asset_tiers if item.get("symbol")]
    if routed_symbols:
        return routed_symbols

    return ["BTC/USD", "ETH/USD"]


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

    strategy_config = _load_yaml(config_path)
    policy = _load_json(policy_path)

    if str(policy.get("status", "")).upper() != "PASS":
        raise SystemExit(f"Policy handoff is not PASS: {policy.get('status')}")

    selected_policy = policy.get("operational_optimum") or policy.get("theoretical_optimum") or {}
    symbols = _extract_symbols(strategy_config)

    mode = str(args.mode).strip().lower()
    if mode not in {"synthetic", "testnet"}:
        raise SystemExit(f"Unsupported mode: {args.mode}")

    venue = "SIM" if mode == "synthetic" else "BINANCE_TESTNET"
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

    paper_adapter = PaperTradingAdapter(initial_balance=float(args.initial_balance))
    await paper_adapter.connect()

    replay: Optional[MockLiveTickReplay] = None
    testnet_transport: Optional[BinanceTestnetTransportAdapter] = None
    transport_stream_provider = None

    if mode == "synthetic":
        replay = MockLiveTickReplay(
            symbols=symbols,
            bar_interval_minutes=args.bar_interval_minutes,
            bars_to_emit=args.bars,
            ticks_per_bar=args.ticks_per_bar,
            sleep_seconds=args.tick_sleep_seconds,
            seed=args.seed,
        )
    else:
        testnet_transport = BinanceTestnetTransportAdapter(
            websocket_url=args.testnet_ws_url,
            reconnect_delay_seconds=args.testnet_reconnect_seconds,
            quote_asset=args.testnet_quote_asset,
        )
        transport_stream_provider = testnet_transport.stream

    completed_bars = 0
    probe_order_submitted = False

    async def on_completed_bar(bar: OHLCV, engine: LiveExecutionEngine) -> None:
        nonlocal completed_bars, probe_order_submitted

        paper_adapter.set_price(bar.symbol, float(bar.close))
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

        if args.probe_order and not probe_order_submitted:
            probe_order_submitted = True
            order = await engine.submit_order(
                symbol=bar.symbol,
                side=OrderSide.BUY,
                quantity=float(args.probe_order_quantity),
                order_type=OrderType.MARKET,
                time_in_force="IOC",
            )
            logger.info(
                "PROBE ORDER | id=%s | symbol=%s | side=%s | qty=%.6f | status=%s | fill=%.6f @ %.4f",
                order.order_id,
                order.symbol,
                order.side.value,
                order.quantity,
                order.status.value,
                order.filled_quantity,
                order.avg_fill_price,
            )

        if mode == "synthetic" and completed_bars >= args.bars:
            engine.request_stop(f"target bars reached: {completed_bars}")

    def exchange_snapshot_provider() -> PortfolioStateSnapshot:
        return _build_portfolio_snapshot(paper_adapter, source="paper_exchange")

    engine = LiveExecutionEngine(
        broker_adapter=paper_adapter,
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
            await paper_adapter.disconnect()

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
                "testnet_ws_url": args.testnet_ws_url,
                "testnet_reconnect_seconds": args.testnet_reconnect_seconds,
                "testnet_duration_seconds": args.testnet_duration_seconds,
            },
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2, sort_keys=True)
        handle.write("\n")

    logger.info("Wrote staging status snapshot to %s", output_path)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 5 live staging harness.")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "testnet"],
        default="synthetic",
        help="Transport mode: deterministic replay or live testnet websocket",
    )
    parser.add_argument("--config", default="configs/crypto_strategy_multimag_sweep.yaml", help="Strategy template YAML to load")
    parser.add_argument("--policy-json", default="reports/crypto/policy_handoff_pass.json", help="Phase 4 policy handoff JSON")
    parser.add_argument("--status-output", default="reports/crypto/live_staging_status.json", help="Path to write the final status snapshot")
    parser.add_argument("--bar-interval-minutes", type=int, default=15, help="Virtual bar interval used by the replay stream")
    parser.add_argument("--bars", type=int, default=3, help="Number of virtual bars to replay before stopping")
    parser.add_argument("--ticks-per-bar", type=int, default=6, help="Synthetic ticks emitted per virtual bar and symbol")
    parser.add_argument("--tick-sleep-seconds", type=float, default=0.05, help="Real-time delay between synthetic tick batches")
    parser.add_argument("--initial-balance", type=float, default=100_000.0, help="Starting paper balance")
    parser.add_argument("--probe-order", dest="probe_order", action="store_true", help="Submit a small paper probe order on the first completed bar")
    parser.add_argument("--no-probe-order", dest="probe_order", action="store_false", help="Disable the probe order")
    parser.set_defaults(probe_order=True)
    parser.add_argument("--probe-order-quantity", type=float, default=0.001, help="Probe order quantity used when the probe is enabled")
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