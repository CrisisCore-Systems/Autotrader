"""CLI entrypoint for agentic BounceHunter system."""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

# Handle both direct execution and module import
try:
    from .agentic import Policy, AgentMemory, Orchestrator
except ImportError:
    # Direct execution - add parent to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from bouncehunter.agentic import Policy, AgentMemory, Orchestrator


def load_policy_from_yaml(yaml_path: Path) -> tuple[Policy, Any]:
    """Load policy and config from YAML config file."""
    try:
        from .config import BounceHunterConfig
    except ImportError:
        from bouncehunter.config import BounceHunterConfig

    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Extract scanner section (nested structure)
    scanner_cfg = cfg.get("scanner", {})

    # Parse tickers (can be list or comma-separated string)
    tickers_raw = scanner_cfg.get("tickers", [])
    if isinstance(tickers_raw, str):
        tickers = [t.strip() for t in tickers_raw.split(",")]
    else:
        tickers = tickers_raw

    # Map YAML field names to BounceHunterConfig field names
    config = BounceHunterConfig(
        tickers=tickers,
        start=scanner_cfg.get("start", "2018-01-01"),
        z_score_drop=scanner_cfg.get("z_drop", -1.5),
        rsi2_max=scanner_cfg.get("rsi2_max", 10),
        max_dist_200dma=scanner_cfg.get("dist200_min", -0.12),
        bcs_threshold=scanner_cfg.get("bcs_threshold", 0.65),
        skip_earnings=not scanner_cfg.get("allow_earnings", False),
        earnings_window_days=scanner_cfg.get("earnings_window", 5),
        skip_earnings_for_etfs=scanner_cfg.get("skip_earnings_for_etfs", True),
        min_adv_usd=scanner_cfg.get("min_adv_usd", 5_000_000),
        bcs_threshold_highvix=scanner_cfg.get("bcs_threshold_highvix", 0.70),
        vix_lookback_days=scanner_cfg.get("vix_lookback_days", 252),
        highvix_percentile=scanner_cfg.get("highvix_percentile", 0.80),
        spy_stress_multiplier=scanner_cfg.get("spy_stress_multiplier", 0.9),
        size_pct_base=scanner_cfg.get("size_pct_base", 0.012),
        size_pct_highvix=scanner_cfg.get("size_pct_highvix", 0.006),
        max_concurrent=scanner_cfg.get("max_concurrent", 8),
        max_per_sector=scanner_cfg.get("max_per_sector", 3),
        rebound_pct=scanner_cfg.get("rebound", 0.03),
        stop_pct=scanner_cfg.get("stop", 0.03),
        horizon_days=scanner_cfg.get("horizon", 5),
    )

    # Build Policy with config reference
    policy = Policy(
        config=config,
        live_trading=scanner_cfg.get("live_trading", False),
        min_bcs=scanner_cfg.get("bcs_threshold", 0.65),
        min_bcs_highvix=scanner_cfg.get("bcs_threshold_highvix", 0.70),
        risk_pct_normal=scanner_cfg.get("size_pct_base", 0.012),
        risk_pct_highvix=scanner_cfg.get("size_pct_highvix", 0.006),
        max_concurrent=scanner_cfg.get("max_concurrent", 8),
        max_per_sector=scanner_cfg.get("max_per_sector", 3),
        allow_earnings=scanner_cfg.get("allow_earnings", False),
        news_veto_enabled=scanner_cfg.get("news_veto_enabled", False),
        base_rate_floor=scanner_cfg.get("base_rate_floor", 0.40),
        min_sample_size=scanner_cfg.get("min_sample_size", 10),
        auto_adapt_thresholds=scanner_cfg.get("auto_adapt_thresholds", True),
    )

    return policy, config


async def run_scan(policy: Policy, db_path: str, broker: Any = None) -> Dict[str, Any]:
    """Execute daily scan."""
    memory = AgentMemory(db_path)
    orchestrator = Orchestrator(policy, memory, broker)
    result = await orchestrator.run_daily_scan()
    return result


async def run_audit(policy: Policy, db_path: str) -> Dict[str, Any]:
    """Execute nightly audit."""
    memory = AgentMemory(db_path)
    orchestrator = Orchestrator(policy, memory)
    result = await orchestrator.run_nightly_audit()
    return result


def format_result(result: Dict[str, Any]) -> str:
    """Format orchestrator result for display."""
    lines = [
        f"Timestamp: {result['timestamp']}",
        "",
        "Context:",
        f"  Date: {result['context'].dt}",
        f"  Regime: {result['context'].regime}",
        f"  VIX Percentile: {result['context'].vix_percentile:.1f}",
        f"  SPY vs 200DMA: {result['context'].spy_dist_200dma:.1%}",
        f"  Market Hours: {result['context'].is_market_hours}",
        "",
        f"Signals: {result['signals']}",
        f"Approved: {result['approved']}",
        "",
    ]

    if result.get("actions"):
        lines.append("Actions:")
        for action in result["actions"]:
            lines.append(f"  {action['ticker']}:")
            lines.append(f"    Action: {action['action']}")
            lines.append(f"    Entry: ${action['entry']:.2f}")
            lines.append(f"    Stop: ${action['stop']:.2f}")
            lines.append(f"    Target: ${action['target']:.2f}")
            lines.append(f"    Size: {action['size_pct']:.2%}")
            lines.append(f"    BCS: {action['probability']:.1%}")
            lines.append(f"    Regime: {action['regime']}")
            lines.append("")
    else:
        lines.append("No actions generated.")
        if "filtered" in result:
            lines.append(f"Reason: {result['filtered']}")

    return "\n".join(lines)


def format_audit_result(result: Dict[str, Any]) -> str:
    """Format audit result for display."""
    lines = [
        f"Updated tickers: {result['updated_tickers']}",
        "",
    ]

    if result.get("stats"):
        lines.append("Ticker Statistics:")
        for stat in result["stats"]:
            lines.append(f"  {stat['ticker']}:")
            lines.append(f"    Base Rate: {stat['base_rate']:.1%}")
            lines.append(f"    Avg Reward: {stat['avg_reward']:.3f}")
            lines.append(f"    Total Outcomes: {stat['total_outcomes']}")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main entrypoint."""
    parser = argparse.ArgumentParser(description="Agentic BounceHunter")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/telegram_pro.yaml",
        help="Path to config YAML",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="bouncehunter_memory.db",
        help="Path to SQLite memory database",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["scan", "audit"],
        default="scan",
        help="Operation mode: scan (daily) or audit (nightly)",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Send results to Telegram (requires telegram_bot config)",
    )
    parser.add_argument(
        "--broker",
        type=str,
        choices=["paper", "alpaca", "questrade", "ibkr"],
        help="Broker to use for live trading (default: None/alert-only)",
    )
    parser.add_argument(
        "--broker-key",
        type=str,
        help="Broker API key (alpaca) or refresh token (questrade)",
    )
    parser.add_argument(
        "--broker-secret",
        type=str,
        help="Broker secret key (required for alpaca)",
    )
    parser.add_argument(
        "--broker-host",
        type=str,
        default="127.0.0.1",
        help="IBKR host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--broker-port",
        type=int,
        default=7497,
        help="IBKR port (7497=paper, 7496=live)",
    )

    args = parser.parse_args()

    # Load policy
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    policy, _ = load_policy_from_yaml(config_path)

    # Initialize broker if specified
    broker = None
    if args.broker:
        try:
            from .broker import create_broker
        except ImportError:
            from bouncehunter.broker import create_broker

        if args.broker == "paper":
            broker = create_broker("paper", initial_cash=100_000.0)
            print("Using PaperBroker (simulated trading)")
        elif args.broker == "alpaca":
            if not args.broker_key or not args.broker_secret:
                print("Error: --broker-key and --broker-secret required for Alpaca", file=sys.stderr)
                sys.exit(1)
            broker = create_broker(
                "alpaca",
                api_key=args.broker_key,
                secret_key=args.broker_secret,
                paper=not policy.live_trading,  # Use paper if not live trading
            )
            print(f"Using Alpaca ({'paper' if not policy.live_trading else 'live'} trading)")
        elif args.broker == "questrade":
            if not args.broker_key:
                print("Error: --broker-key (refresh token) required for Questrade", file=sys.stderr)
                sys.exit(1)
            broker = create_broker(
                "questrade",
                refresh_token=args.broker_key,
                paper=not policy.live_trading,
            )
            print(f"Using Questrade (Canadian broker, {'paper' if not policy.live_trading else 'live'} trading)")
        elif args.broker == "ibkr":
            broker = create_broker(
                "ibkr",
                host=args.broker_host,
                port=args.broker_port,
                client_id=1,
            )
            mode = "paper" if args.broker_port == 7497 else "live"
            print(f"Using Interactive Brokers ({mode} trading)")

    # Run operation
    if args.mode == "scan":
        result = asyncio.run(run_scan(policy, args.db, broker))
        output = format_result(result)
        print(output)

        # Optionally send to Telegram
        if args.telegram and result.get("actions"):
            try:
                try:
                    from .telegram_bot import TelegramNotifier
                except ImportError:
                    from bouncehunter.telegram_bot import TelegramNotifier

                # Convert actions back to signal-like objects for formatting
                # This is a simplified approach - you may want to store full signal data
                _ = TelegramNotifier.from_yaml(config_path)
                # For now, just print that we would send
                print("\n[Telegram notification would be sent here]")
            except ImportError:
                print("\nWarning: Telegram bot not available", file=sys.stderr)

    elif args.mode == "audit":
        result = asyncio.run(run_audit(policy, args.db))
        output = format_audit_result(result)
        print(output)


if __name__ == "__main__":
    main()
