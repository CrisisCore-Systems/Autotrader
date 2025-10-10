"""
Example: Phase 2 Model Upgrade with Cross-Exchange Features

Demonstrates:
1. Multi-exchange data streaming (Binance, Bybit, Coinbase)
2. Cross-exchange dislocation feature extraction
3. LightGBM model training with engineered features
4. Meta-labeling for FP reduction
5. Spectral Residual anomaly detection
6. Walk-forward optimization
7. Hyperparameter sweeps with Optuna
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.logging_config import get_logger
from src.features.cross_exchange_features import CrossExchangeFeatureExtractor
from src.microstructure.multi_exchange_stream import (
    BinanceOrderBookStream,
    BybitOrderBookStream,
    CoinbaseOrderBookStream,
    MultiExchangeAggregator,
)
from src.models.lightgbm_pipeline import LightGBMPipeline
from src.models.meta_labeling import MetaLabeler, MetaLabelingConfig
from src.models.spectral_residual import SpectralResidualDetector, BurstConfirmationFilter
from src.models.walk_forward import WalkForwardOptimizer
from src.models.hyperparameter_optimization import HyperparameterOptimizer

logger = get_logger(__name__)


async def demo_multi_exchange_streaming():
    """Demo multi-exchange streaming with cross-exchange features."""
    print("\n" + "=" * 80)
    print("PHASE 2: MULTI-EXCHANGE STREAMING")
    print("=" * 80)

    symbol_binance = "BTC/USDT"
    symbol_bybit = "BTC/USDT:USDT"  # Linear perpetual
    symbol_coinbase = "BTC/USD"

    # Create streams
    binance_stream = BinanceOrderBookStream(symbol=symbol_binance, depth=20)
    bybit_stream = BybitOrderBookStream(symbol=symbol_bybit, depth=20)
    coinbase_stream = CoinbaseOrderBookStream(symbol=symbol_coinbase, depth=20)

    # Create aggregator
    aggregator = MultiExchangeAggregator({
        "binance": binance_stream,
        "bybit": bybit_stream,
        "coinbase": coinbase_stream,
    })

    # Create feature extractor
    feature_extractor = CrossExchangeFeatureExtractor(
        lookback_window=100,
        price_history_size=1000,
    )

    # Stats
    update_count = 0
    arb_count = 0

    print(f"\n📡 Starting multi-exchange streams...")
    print(f"   Binance: {symbol_binance}")
    print(f"   Bybit: {symbol_bybit}")
    print(f"   Coinbase: {symbol_coinbase}")
    print("\nPress Ctrl+C to stop...")

    try:
        # Start streams
        await asyncio.sleep(2)  # Give streams time to connect

        # Run for 60 seconds
        for _ in range(60):
            await asyncio.sleep(1)

            # Get current market state
            best_bids_asks = aggregator.get_best_bid_ask()

            if len(best_bids_asks) >= 2:
                update_count += 1

                # Detect arbitrage
                arb_opportunities = aggregator.get_arbitrage_opportunities(min_profit_bps=5.0)

                if arb_opportunities:
                    arb_count += len(arb_opportunities)
                    print(f"\n🔥 Arbitrage Opportunity!")
                    for opp in arb_opportunities[:1]:  # Show best one
                        print(f"   Buy on {opp['buy_exchange']}: ${opp['buy_price']:.2f}")
                        print(f"   Sell on {opp['sell_exchange']}: ${opp['sell_price']:.2f}")
                        print(f"   Profit: {opp['profit_bps']:.2f} bps")

                # Extract features
                features = feature_extractor.extract_features(
                    best_bids_asks,
                    arb_opportunities,
                )

                if features:
                    # Update price history
                    for exchange, data in best_bids_asks.items():
                        mid_price = (data["best_bid"] + data["best_ask"]) / 2
                        volume = data["bid_size"] + data["ask_size"]
                        feature_extractor.update(exchange, mid_price, volume, data["timestamp"])

                    if update_count % 10 == 0:
                        print(f"\n📊 Cross-Exchange Features (Update #{update_count})")
                        print(f"   Price Dispersion: {features.price_dispersion:.6f}")
                        print(f"   Max Spread: {features.max_price_spread_bps:.2f} bps")
                        print(f"   Arb Opportunities: {features.arb_opportunity_count}")
                        print(f"   Best Arb: {features.best_arb_opportunity_bps:.2f} bps")
                        print(f"   Price Sync Correlation: {features.price_sync_correlation:.3f}")
                        print(f"   Dominant Exchange: {features.dominant_exchange}")

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping streams...")
    finally:
        await aggregator.stop_all()

    print("\n" + "=" * 80)
    print(f"Total Updates: {update_count}")
    print(f"Total Arbitrage Opportunities: {arb_count}")
    print("=" * 80)


def demo_lightgbm_training():
    """Demo LightGBM training with cross-exchange features."""
    print("\n" + "=" * 80)
    print("PHASE 2: LIGHTGBM MODEL TRAINING")
    print("=" * 80)

    # Create synthetic training data
    np.random.seed(42)
    n_samples = 5000

    # Generate features
    df = pd.DataFrame({
        "price_dispersion": np.random.exponential(0.001, n_samples),
        "max_price_spread_bps": np.random.gamma(2, 5, n_samples),
        "best_arb_opportunity_bps": np.random.gamma(1.5, 3, n_samples),
        "arb_opportunity_count": np.random.poisson(2, n_samples),
        "vw_price_dispersion": np.random.exponential(0.0008, n_samples),
        "volume_concentration": np.random.beta(2, 5, n_samples),
        "price_sync_correlation": np.random.uniform(0.5, 0.99, n_samples),
        "depth_imbalance_ratio": np.random.gamma(1.2, 1.5, n_samples),
        "cross_exchange_vol_ratio": np.random.gamma(1.5, 1.2, n_samples),
    })

    # Generate target (gems have higher arb opportunities and dispersion)
    prob_gem = (
        (df["best_arb_opportunity_bps"] > 10).astype(float) * 0.4
        + (df["price_dispersion"] > 0.002).astype(float) * 0.3
        + np.random.uniform(0, 0.3, n_samples)
    )
    df["is_gem"] = (prob_gem > 0.6).astype(int)

    print(f"\n📊 Training Data:")
    print(f"   Samples: {len(df)}")
    print(f"   Features: {len([c for c in df.columns if c != 'is_gem'])}")
    print(f"   Positive Rate: {df['is_gem'].mean():.2%}")

    # Train model
    model_dir = Path("models/phase2_lightgbm")
    pipeline = LightGBMPipeline(model_dir=model_dir)

    feature_cols = [c for c in df.columns if c != "is_gem"]
    X, y = pipeline.prepare_features(df, feature_cols, "is_gem")

    print("\n🚀 Training LightGBM model...")
    metrics = pipeline.train(X, y, num_boost_round=500, early_stopping_rounds=30)

    print("\n✅ Training Complete!")
    print(f"   Precision: {metrics.precision:.3f}")
    print(f"   Recall: {metrics.recall:.3f}")
    print(f"   F1 Score: {metrics.f1_score:.3f}")
    print(f"   ROC AUC: {metrics.roc_auc:.3f}")

    # Show top features
    print("\n🔝 Top 5 Features:")
    top_features = sorted(
        metrics.feature_importance.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]
    for feat, importance in top_features:
        print(f"   {feat}: {importance:.1f}")

    return pipeline, X, y


def demo_meta_labeling(pipeline, X, y):
    """Demo meta-labeling for false positive reduction."""
    print("\n" + "=" * 80)
    print("PHASE 2: META-LABELING SYSTEM")
    print("=" * 80)

    # Create meta labeler
    meta_dir = Path("models/phase2_meta_labeling")
    config = MetaLabelingConfig(
        primary_threshold=0.5,
        meta_threshold=0.7,
        min_confidence_gap=0.2,
    )

    meta_labeler = MetaLabeler(
        primary_model=pipeline,
        meta_model_dir=meta_dir,
        config=config,
    )

    print("\n🔧 Training meta model...")

    # Split data for meta training
    split_idx = int(len(X) * 0.7)
    X_meta_train = X.iloc[:split_idx]
    y_meta_train = y.iloc[:split_idx]
    X_meta_test = X.iloc[split_idx:]
    y_meta_test = y.iloc[split_idx:]

    meta_metrics = meta_labeler.train_meta_model(
        X_meta_train,
        y_meta_train,
        num_boost_round=300,
    )

    print("\n✅ Meta Model Trained!")
    print(f"   Precision: {meta_metrics.precision:.3f}")
    print(f"   Recall: {meta_metrics.recall:.3f}")
    print(f"   F1 Score: {meta_metrics.f1_score:.3f}")

    # Evaluate on test set
    print("\n📊 Evaluating Meta System...")
    evaluation = meta_labeler.evaluate_meta_system(X_meta_test, y_meta_test)

    print("\n📈 Primary Model Performance:")
    print(f"   Precision: {evaluation['primary']['precision']:.3f}")
    print(f"   Recall: {evaluation['primary']['recall']:.3f}")
    print(f"   F1: {evaluation['primary']['f1']:.3f}")
    print(f"   Predictions: {evaluation['primary']['n_predictions']}")

    print("\n🎯 Meta-Filtered Performance:")
    print(f"   Precision: {evaluation['meta_filtered']['precision']:.3f}")
    print(f"   Recall: {evaluation['meta_filtered']['recall']:.3f}")
    print(f"   F1: {evaluation['meta_filtered']['f1']:.3f}")
    print(f"   Predictions: {evaluation['meta_filtered']['n_predictions']}")

    print("\n📊 Improvement:")
    print(f"   Precision Gain: {evaluation['improvement']['precision_gain']:.3f}")
    print(f"   Recall Loss: {evaluation['improvement']['recall_loss']:.3f}")


def demo_spectral_residual():
    """Demo Spectral Residual anomaly detection."""
    print("\n" + "=" * 80)
    print("PHASE 2: SPECTRAL RESIDUAL ANOMALY DETECTION")
    print("=" * 80)

    # Create synthetic time series with anomalies
    np.random.seed(42)
    n_points = 500

    # Normal pattern
    t = np.linspace(0, 10, n_points)
    series = np.sin(t) + np.random.normal(0, 0.1, n_points)

    # Add anomalies (bursts)
    burst_indices = [100, 250, 400]
    for idx in burst_indices:
        series[idx : idx + 10] += np.random.uniform(2, 4, 10)

    print(f"\n📊 Time Series:")
    print(f"   Length: {n_points}")
    print(f"   Injected Anomalies: {len(burst_indices)}")

    # Detect anomalies
    detector = SpectralResidualDetector(
        window_size=20,
        threshold_multiplier=3.0,
    )

    print("\n🔍 Running Spectral Residual detection...")
    detections = detector.detect(series)

    detected_anomalies = [d for d in detections if d.is_anomaly]

    print(f"\n✅ Detection Complete!")
    print(f"   Total Anomalies Detected: {len(detected_anomalies)}")
    print(f"   Detection Rate: {len(detected_anomalies) / len(burst_indices) * 3:.1f}x")

    # Detect bursts
    bursts = detector.detect_bursts(series, min_duration=3, max_gap=2)

    print(f"\n🔥 Burst Detection:")
    print(f"   Bursts Found: {len(bursts)}")
    for i, burst in enumerate(bursts):
        print(f"\n   Burst {i + 1}:")
        print(f"      Start Index: {burst['start_idx']}")
        print(f"      Duration: {burst['duration_points']} points")
        print(f"      Max Score: {burst['max_score']:.2f}")
        print(f"      Mean Score: {burst['mean_score']:.2f}")


def demo_walk_forward():
    """Demo walk-forward optimization."""
    print("\n" + "=" * 80)
    print("PHASE 2: WALK-FORWARD OPTIMIZATION")
    print("=" * 80)

    # Create synthetic time series data
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="H")
    n_samples = len(dates)

    df = pd.DataFrame({
        "timestamp": dates,
        "feature_1": np.random.randn(n_samples),
        "feature_2": np.random.randn(n_samples),
        "feature_3": np.random.randn(n_samples),
        "is_gem": np.random.binomial(1, 0.1, n_samples),
    })

    print(f"\n📊 Dataset:")
    print(f"   Date Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"   Samples: {len(df)}")
    print(f"   Positive Rate: {df['is_gem'].mean():.2%}")

    # Create walk-forward optimizer
    optimizer = WalkForwardOptimizer(
        train_window_size=timedelta(days=30),
        test_window_size=timedelta(days=7),
        step_size=timedelta(days=7),
        expanding_window=False,
        results_dir=Path("models/walk_forward_results"),
    )

    print("\n🔧 Creating walk-forward windows...")
    windows = optimizer.create_windows(df, time_column="timestamp")

    print(f"\n✅ Windows Created: {len(windows)}")
    for i, window in enumerate(windows[:3]):
        print(f"\n   Window {i + 1}:")
        print(f"      Train: {window.train_start} to {window.train_end}")
        print(f"      Test: {window.test_start} to {window.test_end}")
        print(f"      Train Size: {window.train_size}")
        print(f"      Test Size: {window.test_size}")

    if len(windows) > 3:
        print(f"   ... and {len(windows) - 3} more windows")

    print("\n🚀 Running walk-forward optimization...")
    print("   (This may take a few minutes...)")

    feature_cols = ["feature_1", "feature_2", "feature_3"]
    results = optimizer.run_optimization(
        df,
        feature_columns=feature_cols,
        target_column="is_gem",
        num_boost_round=100,  # Reduced for demo
    )

    print(f"\n✅ Optimization Complete!")
    print(f"   Windows Evaluated: {len(results)}")

    # Show aggregate metrics
    agg_metrics = optimizer.get_aggregate_metrics()
    print("\n📊 Aggregate Metrics:")
    print(f"   Mean Precision: {agg_metrics['mean_precision']:.3f} ± {agg_metrics['std_precision']:.3f}")
    print(f"   Mean Recall: {agg_metrics['mean_recall']:.3f} ± {agg_metrics['std_recall']:.3f}")
    print(f"   Mean F1: {agg_metrics['mean_f1']:.3f} ± {agg_metrics['std_f1']:.3f}")
    print(f"   Mean ROC AUC: {agg_metrics['mean_roc_auc']:.3f} ± {agg_metrics['std_roc_auc']:.3f}")


def demo_hyperparameter_optimization():
    """Demo hyperparameter optimization with Optuna."""
    print("\n" + "=" * 80)
    print("PHASE 2: HYPERPARAMETER OPTIMIZATION")
    print("=" * 80)

    # Create synthetic data
    np.random.seed(42)
    n_samples = 2000

    X_train = pd.DataFrame({
        "feature_1": np.random.randn(n_samples),
        "feature_2": np.random.randn(n_samples),
        "feature_3": np.random.randn(n_samples),
    })
    y_train = pd.Series(np.random.binomial(1, 0.15, n_samples))

    X_val = pd.DataFrame({
        "feature_1": np.random.randn(500),
        "feature_2": np.random.randn(500),
        "feature_3": np.random.randn(500),
    })
    y_val = pd.Series(np.random.binomial(1, 0.15, 500))

    print(f"\n📊 Training Data: {len(X_train)} samples")
    print(f"📊 Validation Data: {len(X_val)} samples")

    # Create optimizer
    optimizer = HyperparameterOptimizer(
        study_name="phase2_lgbm_optimization",
        storage_dir=Path("models/optuna_studies"),
        direction="maximize",
        n_trials=20,  # Reduced for demo
        n_jobs=1,
    )

    print("\n🚀 Starting Optuna optimization...")
    print("   Optimizing for F1 score")
    print(f"   Trials: {optimizer.n_trials}")

    best_params = optimizer.optimize_lightgbm(
        X_train,
        y_train,
        X_val,
        y_val,
        metric="f1",
    )

    print("\n✅ Optimization Complete!")
    print(f"   Best F1 Score: {optimizer.best_score:.3f}")
    print("\n🏆 Best Hyperparameters:")
    for param, value in best_params.items():
        print(f"   {param}: {value}")


def main():
    """Run all Phase 2 demos."""
    print("\n" + "=" * 80)
    print("🚀 PHASE 2: MODEL UPGRADE + CROSS-EXCHANGE")
    print("=" * 80)
    print("\nWeeks 3-4 Implementation Demo")
    print("\nComponents:")
    print("  1. Multi-exchange data feeds (Binance, Bybit, Coinbase)")
    print("  2. Cross-exchange dislocation features")
    print("  3. LightGBM model training")
    print("  4. Meta-labeling system")
    print("  5. Spectral Residual anomaly detection")
    print("  6. Walk-forward optimization")
    print("  7. Hyperparameter sweeps (Optuna)")

    # Run demos
    try:
        # 1. LightGBM Training (synchronous)
        pipeline, X, y = demo_lightgbm_training()

        # 2. Meta-Labeling
        demo_meta_labeling(pipeline, X, y)

        # 3. Spectral Residual
        demo_spectral_residual()

        # 4. Walk-Forward (can take time)
        # demo_walk_forward()  # Uncomment to run

        # 5. Hyperparameter Optimization (can take time)
        # demo_hyperparameter_optimization()  # Uncomment to run

        # 6. Multi-Exchange Streaming (requires async)
        print("\n💡 To demo multi-exchange streaming, run:")
        print("   python -c \"import asyncio; from examples.phase2_example import demo_multi_exchange_streaming; asyncio.run(demo_multi_exchange_streaming())\"")

    except Exception as exc:
        logger.error("demo_failed", error=str(exc))
        raise

    print("\n" + "=" * 80)
    print("✅ PHASE 2 DEMO COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
