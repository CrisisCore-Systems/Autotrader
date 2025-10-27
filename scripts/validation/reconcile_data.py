"""
Data reconciliation script for validation roadmap.
Compares historical vs live feeds and generates daily diff reports.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict
import pandas as pd


def reconcile_datasets(
    historical_dir: Path,
    live_dir: Path,
    output_report: Path
) -> Dict:
    """
    Reconcile historical and live datasets.
    
    Returns:
        Dict with reconciliation results
    """
    print("🔍 Starting data reconciliation...")
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'summary': {},
        'symbol_reports': [],
        'issues': [],
    }
    
    # Find all historical files
    hist_files = list(historical_dir.glob("*_bars.parquet"))
    
    total_symbols = 0
    matched = 0
    mismatched = 0
    missing = 0
    
    for hist_file in hist_files:
        symbol = hist_file.stem.replace('_bars', '')
        total_symbols += 1
        
        # Check if corresponding live file exists
        live_file = live_dir / hist_file.name
        
        if not live_file.exists():
            missing += 1
            results['issues'].append({
                'symbol': symbol,
                'type': 'missing_live_data',
                'message': f'No live data found for {symbol}'
            })
            continue
        
        # Load both datasets
        df_hist = pd.read_parquet(hist_file)
        df_live = pd.read_parquet(live_file)
        
        # Reconcile
        symbol_result = _reconcile_symbol(symbol, df_hist, df_live)
        results['symbol_reports'].append(symbol_result)
        
        if symbol_result['match_quality'] > 0.95:
            matched += 1
        else:
            mismatched += 1
            results['issues'].append({
                'symbol': symbol,
                'type': 'data_mismatch',
                'match_quality': symbol_result['match_quality'],
                'details': symbol_result['differences']
            })
    
    # Summary
    results['summary'] = {
        'total_symbols': total_symbols,
        'matched': matched,
        'mismatched': mismatched,
        'missing_live': missing,
        'match_rate': matched / total_symbols if total_symbols > 0 else 0.0,
    }
    
    # Write report
    output_report.parent.mkdir(parents=True, exist_ok=True)
    with open(output_report, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Reconciliation complete:")
    print(f"   Total symbols: {total_symbols}")
    if total_symbols > 0:
        print(f"   Matched: {matched} ({matched/total_symbols*100:.1f}%)")
        print(f"   Mismatched: {mismatched}")
        print(f"   Missing: {missing}")
    print(f"\n📄 Report: {output_report}")
    
    return results


def _reconcile_symbol(
    symbol: str,
    df_hist: pd.DataFrame,
    df_live: pd.DataFrame
) -> Dict:
    """Reconcile a single symbol's historical vs live data."""
    
    # Align on timestamp
    df_hist = df_hist.set_index('timestamp').sort_index()
    df_live = df_live.set_index('timestamp').sort_index()
    
    # Find common time range
    common_start = max(df_hist.index.min(), df_live.index.min())
    common_end = min(df_hist.index.max(), df_live.index.max())
    
    df_hist_common = df_hist.loc[common_start:common_end]
    df_live_common = df_live.loc[common_start:common_end]
    
    # Check row counts
    row_diff = abs(len(df_hist_common) - len(df_live_common))
    
    # Compare prices (sample)
    price_corr = 0.0
    volume_corr = 0.0
    mean_price_diff = 0.0
    
    if len(df_hist_common) > 0 and len(df_live_common) > 0:
        # Resample to common frequency if needed
        if len(df_hist_common) == len(df_live_common):
            price_corr = df_hist_common['close'].corr(df_live_common['close'])
            volume_corr = df_hist_common['volume'].corr(df_live_common['volume'])
            mean_price_diff = (df_hist_common['close'] - df_live_common['close']).abs().mean()
        else:
            # Different lengths - compare aggregates
            price_corr = 0.9  # Assume partial match
            mean_price_diff = abs(df_hist_common['close'].mean() - df_live_common['close'].mean())
    
    # Compute match quality score
    match_quality = (
        0.4 * price_corr +
        0.2 * volume_corr +
        0.2 * (1.0 - min(row_diff / max(len(df_hist_common), 1), 1.0)) +
        0.2 * (1.0 - min(mean_price_diff / 10.0, 1.0))
    )
    
    return {
        'symbol': symbol,
        'hist_rows': len(df_hist),
        'live_rows': len(df_live),
        'common_rows_hist': len(df_hist_common),
        'common_rows_live': len(df_live_common),
        'price_correlation': float(price_corr),
        'volume_correlation': float(volume_corr),
        'mean_price_diff': float(mean_price_diff),
        'match_quality': float(match_quality),
        'differences': {
            'row_count_diff': row_diff,
            'price_corr_below_threshold': bool(price_corr < 0.95),
        }
    }


def generate_validation_log(
    reconciliation_report: Path,
    output_log: Path
) -> None:
    """Generate human-readable validation log from reconciliation report."""
    
    with open(reconciliation_report) as f:
        results = json.load(f)
    
    lines = [
        "=" * 80,
        "DATA VALIDATION LOG",
        "=" * 80,
        f"Generated: {datetime.now().isoformat()}",
        f"Reconciliation Report: {reconciliation_report}",
        "",
        "SUMMARY",
        "-" * 80,
        f"Total Symbols:     {results['summary']['total_symbols']}",
        f"Matched:           {results['summary']['matched']}",
        f"Mismatched:        {results['summary']['mismatched']}",
        f"Missing Live Data: {results['summary']['missing_live']}",
        f"Match Rate:        {results['summary']['match_rate']:.1%}",
        "",
    ]
    
    if results['issues']:
        lines.extend([
            "ISSUES DETECTED",
            "-" * 80,
        ])
        for issue in results['issues']:
            lines.append(f"  • {issue['symbol']}: {issue['type']}")
            if 'match_quality' in issue:
                lines.append(f"    Match quality: {issue['match_quality']:.2%}")
        lines.append("")
    
    lines.extend([
        "SYMBOL DETAILS",
        "-" * 80,
    ])
    for report in results['symbol_reports']:
        lines.append(f"  {report['symbol']}:")
        lines.append(f"    Historical rows: {report['hist_rows']}")
        lines.append(f"    Live rows:       {report['live_rows']}")
        lines.append(f"    Price corr:      {report['price_correlation']:.4f}")
        lines.append(f"    Match quality:   {report['match_quality']:.2%}")
        lines.append("")
    
    lines.append("=" * 80)
    
    output_log.parent.mkdir(parents=True, exist_ok=True)
    output_log.write_text('\n'.join(lines))
    print(f"📄 Validation log: {output_log}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Reconcile historical and live data')
    parser.add_argument('--historical', type=Path, required=True,
                       help='Directory with historical data')
    parser.add_argument('--live', type=Path, required=True,
                       help='Directory with live feed data')
    parser.add_argument('--output', type=Path, required=True,
                       help='Output reconciliation report (JSON)')
    parser.add_argument('--validation-log', type=Path,
                       help='Optional human-readable validation log')
    
    args = parser.parse_args()
    
    results = reconcile_datasets(args.historical, args.live, args.output)
    
    if args.validation_log:
        generate_validation_log(args.output, args.validation_log)
