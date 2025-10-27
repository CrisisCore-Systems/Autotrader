"""
Full Optuna Optimization Runner

Runs comprehensive hyperparameter optimization across all symbols.
This script orchestrates multiple optimization runs and aggregates results.

Usage:
    python scripts/validation/run_full_optimization.py --trials 200
    python scripts/validation/run_full_optimization.py --trials 50 --symbols AAPL MSFT
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import time


def run_single_optimization(
    symbol: str,
    data_dir: str,
    n_trials: int,
    n_splits: int,
    objective: str,
    output_dir: str
) -> Dict:
    """
    Run Optuna optimization for a single symbol.
    
    Args:
        symbol: Symbol to optimize
        data_dir: Data directory path
        n_trials: Number of optimization trials
        n_splits: Number of CV splits
        objective: Objective metric (sharpe/sortino/calmar)
        output_dir: Output directory for results
        
    Returns:
        Dict with results (symbol, best_value, strategy, duration)
    """
    print(f"\n{'='*60}")
    print(f"Optimizing {symbol}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Build command
    cmd = [
        sys.executable,
        "scripts/validation/optuna_optimization.py",
        "--data-dir", data_dir,
        "--symbol", symbol,
        "--n-trials", str(n_trials),
        "--n-splits", str(n_splits),
        "--objective", objective,
        "--output-dir", output_dir
    ]
    
    try:
        # Run optimization
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        
        end_time = time.time()
        duration = (end_time - start_time) / 60  # minutes
        
        # Load results
        result_file = Path(output_dir) / f"{symbol}_best_params.json"
        if result_file.exists():
            with open(result_file, 'r') as f:
                opt_result = json.load(f)
            
            print(f"\n✓ {symbol} complete in {duration:.1f} minutes")
            print(f"  Best {objective}: {opt_result['best_value']:.6f}")
            print(f"  Strategy: {opt_result['best_params']['strategy_type']}")
            
            return {
                'symbol': symbol,
                'best_value': opt_result['best_value'],
                'strategy': opt_result['best_params']['strategy_type'],
                'duration_minutes': round(duration, 1),
                'status': 'success'
            }
        else:
            print(f"\n✗ {symbol} - results file not found")
            return {
                'symbol': symbol,
                'status': 'failed',
                'error': 'results file not found'
            }
    
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {symbol} failed with exit code {e.returncode}")
        return {
            'symbol': symbol,
            'status': 'failed',
            'error': f'exit code {e.returncode}'
        }
    except Exception as e:
        print(f"\n✗ {symbol} failed with error: {e}")
        return {
            'symbol': symbol,
            'status': 'failed',
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run full Optuna optimization across all symbols"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["AAPL", "MSFT", "NVDA", "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD"],
        help="Symbols to optimize (default: all 7)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/processed/features",
        help="Data directory"
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=200,
        help="Number of trials per symbol (default: 200)"
    )
    parser.add_argument(
        "--splits",
        type=int,
        default=5,
        help="Number of CV splits (default: 5)"
    )
    parser.add_argument(
        "--objective",
        type=str,
        default="sharpe",
        choices=["sharpe", "sortino", "calmar"],
        help="Objective metric (default: sharpe)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/optuna",
        help="Output directory"
    )
    
    args = parser.parse_args()
    
    # Display configuration
    print("="*60)
    print("FULL OPTUNA OPTIMIZATION")
    print("="*60)
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Trials per symbol: {args.trials}")
    print(f"CV splits: {args.splits}")
    print(f"Objective: {args.objective}")
    print(f"Estimated runtime: {args.trials * len(args.symbols) * 0.2 / 60:.1f} minutes")
    print("="*60)
    
    overall_start = time.time()
    results = []
    
    # Run optimization for each symbol
    for i, symbol in enumerate(args.symbols, 1):
        print(f"\n[{i}/{len(args.symbols)}] Processing {symbol}...")
        
        result = run_single_optimization(
            symbol=symbol,
            data_dir=args.data_dir,
            n_trials=args.trials,
            n_splits=args.splits,
            objective=args.objective,
            output_dir=args.output_dir
        )
        results.append(result)
    
    overall_end = time.time()
    total_duration = (overall_end - overall_start) / 60
    
    # Display summary
    print("\n" + "="*60)
    print("OPTIMIZATION COMPLETE")
    print("="*60)
    print(f"Total runtime: {total_duration:.1f} minutes")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nResults Summary:")
    print("-"*60)
    
    # Print results table
    print(f"{'Symbol':<10} {'Status':<10} {'Best Sharpe':<12} {'Strategy':<15} {'Duration (min)':<15}")
    print("-"*60)
    
    for result in results:
        if result['status'] == 'success':
            print(f"{result['symbol']:<10} {result['status']:<10} "
                  f"{result['best_value']:<12.6f} {result['strategy']:<15} "
                  f"{result['duration_minutes']:<15.1f}")
        else:
            print(f"{result['symbol']:<10} {result['status']:<10} "
                  f"{'N/A':<12} {'N/A':<15} {'N/A':<15}")
    
    # Save summary
    os.makedirs(args.output_dir, exist_ok=True)
    summary_file = Path(args.output_dir) / "optimization_summary.json"
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_duration_minutes': round(total_duration, 1),
        'trials_per_symbol': args.trials,
        'symbols_optimized': len(args.symbols),
        'objective': args.objective,
        'results': results
    }
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nSummary saved to: {summary_file}")
    print("="*60)
    
    # Exit with error if any optimizations failed
    failed = [r for r in results if r['status'] != 'success']
    if failed:
        print(f"\n⚠️  {len(failed)} optimization(s) failed")
        sys.exit(1)
    else:
        print("\n✓ All optimizations completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
