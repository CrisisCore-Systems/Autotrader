"""Example demonstrating GemScore delta explainability.

This script shows how to:
1. Create snapshots from GemScore calculations
2. Compute deltas between snapshots
3. Interpret feature contributions
4. Generate narratives
"""

import time
from typing import Dict

from src.core.scoring import compute_gem_score
from src.core.score_explainer import ScoreExplainer, create_snapshot_from_result
from src.core.feature_store import FeatureStore


def create_features(sentiment: float, liquidity: float, onchain: float) -> Dict[str, float]:
    """Create a feature vector with specified key values."""
    return {
        "SentimentScore": sentiment,
        "AccumulationScore": 0.75,
        "OnchainActivity": onchain,
        "LiquidityDepth": liquidity,
        "TokenomicsRisk": 0.85,
        "ContractSafety": 0.90,
        "NarrativeMomentum": 0.70,
        "CommunityGrowth": 0.65,
        "Recency": 0.95,
        "DataCompleteness": 0.90,
    }


def example_1_basic_delta():
    """Example 1: Basic delta computation."""
    print("=" * 80)
    print("EXAMPLE 1: Basic Delta Computation")
    print("=" * 80)
    
    # Simulate two scans 1 hour apart
    token = "ETH"
    
    # Initial scan: moderate sentiment
    features_t1 = create_features(sentiment=0.60, liquidity=0.70, onchain=0.65)
    score_t1 = compute_gem_score(features_t1)
    
    print(f"\n📊 Initial Scan (t=0)")
    print(f"   GemScore: {score_t1.score:.2f}")
    print(f"   Confidence: {score_t1.confidence:.2f}")
    
    # Second scan: improved sentiment and activity
    features_t2 = create_features(sentiment=0.85, liquidity=0.68, onchain=0.80)
    score_t2 = compute_gem_score(features_t2)
    
    print(f"\n📊 Second Scan (t=1 hour)")
    print(f"   GemScore: {score_t2.score:.2f}")
    print(f"   Confidence: {score_t2.confidence:.2f}")
    
    # Create snapshots and compute delta
    explainer = ScoreExplainer()
    snapshot_t1 = create_snapshot_from_result(token, score_t1, features_t1, timestamp=1000.0)
    snapshot_t2 = create_snapshot_from_result(token, score_t2, features_t2, timestamp=4600.0)
    
    delta = explainer.compute_delta(snapshot_t1, snapshot_t2)
    
    # Display results
    print(f"\n📈 Score Change")
    print(f"   Delta: {delta.delta_score:+.2f} points")
    print(f"   Percent Change: {delta.percent_change:+.1f}%")
    print(f"   Time Elapsed: {delta.time_delta_hours:.1f} hours")
    
    print(f"\n✅ Top Positive Contributors:")
    for i, fd in enumerate(delta.top_positive_contributors[:3], 1):
        print(f"   {i}. {fd.feature_name}")
        print(f"      Value: {fd.previous_value:.3f} → {fd.current_value:.3f} ({fd.percent_change:+.1f}%)")
        print(f"      Impact: {fd.delta_contribution * 100:+.2f} points")
    
    if delta.top_negative_contributors:
        print(f"\n❌ Top Negative Contributors:")
        for i, fd in enumerate(delta.top_negative_contributors[:3], 1):
            print(f"   {i}. {fd.feature_name}")
            print(f"      Value: {fd.previous_value:.3f} → {fd.current_value:.3f} ({fd.percent_change:+.1f}%)")
            print(f"      Impact: {fd.delta_contribution * 100:.2f} points")
    
    print(f"\n📝 Narrative:")
    print(f"{delta.get_narrative()}")
    print()


def example_2_feature_store_integration():
    """Example 2: Using FeatureStore for automatic tracking."""
    print("=" * 80)
    print("EXAMPLE 2: FeatureStore Integration")
    print("=" * 80)
    
    store = FeatureStore(enable_validation=False)
    token = "BTC"
    
    print(f"\n🔄 Simulating 5 scans over time...")
    
    # Simulate 5 scans with varying scores
    scan_configs = [
        (0.50, 0.60, 0.55),  # Low sentiment
        (0.60, 0.65, 0.60),  # Improving
        (0.75, 0.70, 0.72),  # Strong
        (0.70, 0.68, 0.68),  # Slight decline
        (0.85, 0.75, 0.80),  # Strong recovery
    ]
    
    for i, (sentiment, liquidity, onchain) in enumerate(scan_configs):
        features = create_features(sentiment, liquidity, onchain)
        score = compute_gem_score(features)
        
        timestamp = 1000.0 + i * 3600.0  # 1 hour apart
        snapshot = create_snapshot_from_result(token, score, features, timestamp=timestamp)
        store.write_snapshot(snapshot)
        
        print(f"\n   Scan {i+1}: GemScore = {score.score:.2f}")
    
    # Display history
    print(f"\n📜 Score History:")
    history = store.read_snapshot_history(token)
    for i, snapshot in enumerate(reversed(history), 1):
        print(f"   {i}. {snapshot.score:.2f} (t={snapshot.timestamp:.0f})")
    
    # Compute and display deltas
    print(f"\n📊 Delta Analysis:")
    for i in range(len(history) - 1):
        current = history[i]
        previous = history[i + 1]
        
        delta = store.compute_score_delta(token, current)
        if delta:
            direction = "📈" if delta.delta_score > 0 else "📉"
            print(f"\n   {direction} Scan {len(history)-i} → {len(history)-i-1}")
            print(f"      Change: {delta.delta_score:+.2f} points ({delta.percent_change:+.1f}%)")
            
            if delta.top_positive_contributors:
                top_pos = delta.top_positive_contributors[0]
                print(f"      Top driver: {top_pos.feature_name} ({top_pos.delta_contribution * 100:+.2f})")
    
    print()


def example_3_api_response_format():
    """Example 3: API response format simulation."""
    print("=" * 80)
    print("EXAMPLE 3: API Response Format")
    print("=" * 80)
    
    # Create delta
    token = "SOL"
    features_t1 = create_features(sentiment=0.55, liquidity=0.65, onchain=0.60)
    score_t1 = compute_gem_score(features_t1)
    
    features_t2 = create_features(sentiment=0.80, liquidity=0.62, onchain=0.75)
    score_t2 = compute_gem_score(features_t2)
    
    explainer = ScoreExplainer()
    snapshot_t1 = explainer.create_snapshot(token, score_t1, features_t1, timestamp=1000.0)
    snapshot_t2 = explainer.create_snapshot(token, score_t2, features_t2, timestamp=2800.0)
    
    delta = explainer.compute_delta(snapshot_t1, snapshot_t2)
    
    # Format like API response
    print("\n🌐 GET /api/gemscore/delta/SOL")
    print("-" * 80)
    
    import json
    summary = delta.get_summary(top_n=3)
    print(json.dumps(summary, indent=2))
    
    print("\n🌐 GET /api/gemscore/delta/SOL/narrative")
    print("-" * 80)
    
    narrative_response = {
        "token": token,
        "narrative": delta.get_narrative(),
        "timestamp": snapshot_t2.timestamp,
    }
    print(json.dumps(narrative_response, indent=2))
    
    print()


def example_4_alerts_and_thresholds():
    """Example 4: Using deltas for alerting."""
    print("=" * 80)
    print("EXAMPLE 4: Alerts and Thresholds")
    print("=" * 80)
    
    store = FeatureStore(enable_validation=False)
    token = "LINK"
    
    # Scan 1: Normal
    features_t1 = create_features(sentiment=0.70, liquidity=0.75, onchain=0.70)
    score_t1 = compute_gem_score(features_t1)
    snapshot_t1 = create_snapshot_from_result(token, score_t1, features_t1, timestamp=1000.0)
    store.write_snapshot(snapshot_t1)
    
    print(f"\n📊 Initial Scan: GemScore = {score_t1.score:.2f}")
    
    # Scan 2: Sharp drop in liquidity
    features_t2 = create_features(sentiment=0.68, liquidity=0.30, onchain=0.65)
    score_t2 = compute_gem_score(features_t2)
    snapshot_t2 = create_snapshot_from_result(token, score_t2, features_t2, timestamp=1600.0)
    store.write_snapshot(snapshot_t2)
    
    print(f"📊 Second Scan: GemScore = {score_t2.score:.2f}")
    
    # Compute delta
    delta = store.compute_score_delta(token)
    
    # Alert logic
    print(f"\n🚨 Alert System Check:")
    
    # Check 1: Large score drop
    if delta and delta.delta_score < -5.0:
        print(f"   ⚠️ ALERT: Large score drop detected!")
        print(f"      Token: {token}")
        print(f"      Drop: {delta.delta_score:.2f} points")
        print(f"      Time: {delta.time_delta_hours:.1f} hours")
    
    # Check 2: Liquidity concerns
    for fd in delta.top_negative_contributors:
        if fd.feature_name == "LiquidityDepth" and fd.percent_change < -30:
            print(f"   ⚠️ ALERT: Liquidity dropping!")
            print(f"      Token: {token}")
            print(f"      Change: {fd.percent_change:.1f}%")
            print(f"      Impact: {fd.delta_contribution * 100:.2f} points")
    
    # Check 3: Multiple negative signals
    negative_count = sum(1 for fd in delta.feature_deltas if fd.delta_contribution < -0.5)
    if negative_count >= 3:
        print(f"   ⚠️ ALERT: Multiple negative signals!")
        print(f"      Count: {negative_count} features declining")
    
    print()


def example_5_trend_analysis():
    """Example 5: Analyzing trends over time."""
    print("=" * 80)
    print("EXAMPLE 5: Trend Analysis")
    print("=" * 80)
    
    store = FeatureStore(enable_validation=False)
    token = "UNI"
    
    # Simulate upward trend in sentiment
    print(f"\n📈 Simulating upward sentiment trend...")
    
    for i in range(6):
        sentiment = 0.50 + i * 0.08  # Increasing
        liquidity = 0.70 - i * 0.02  # Slightly decreasing
        onchain = 0.65 + i * 0.03    # Increasing
        
        features = create_features(sentiment, liquidity, onchain)
        score = compute_gem_score(features)
        
        timestamp = 1000.0 + i * 1800.0  # 30 min apart
        snapshot = create_snapshot_from_result(token, score, features, timestamp=timestamp)
        store.write_snapshot(snapshot)
    
    # Analyze trends
    history = store.read_snapshot_history(token)
    
    print(f"\n📊 Feature Trends:")
    
    # Track each feature over time
    feature_trends = {}
    for snapshot in reversed(history):
        for feature, value in snapshot.features.items():
            if feature not in feature_trends:
                feature_trends[feature] = []
            feature_trends[feature].append(value)
    
    # Identify strongest trends
    print(f"\n   Strongest trends:")
    for feature, values in feature_trends.items():
        if len(values) >= 2:
            trend = values[-1] - values[0]  # Total change
            if abs(trend) > 0.1:
                direction = "↑" if trend > 0 else "↓"
                print(f"   {direction} {feature}: {trend:+.3f}")
    
    # Show delta contributions over time
    print(f"\n   Impact over time:")
    explainer = ScoreExplainer()
    
    for i in range(len(history) - 1):
        current = history[i]
        previous = history[i + 1]
        
        delta = explainer.compute_delta(previous, current)
        
        # Find most impactful feature
        if delta.feature_deltas:
            max_impact = max(delta.feature_deltas, key=lambda fd: abs(fd.delta_contribution))
            sign = "+" if max_impact.delta_contribution > 0 else ""
            print(f"   Period {len(history)-i-1}→{len(history)-i}: {max_impact.feature_name} "
                  f"({sign}{max_impact.delta_contribution * 100:.2f} pts)")
    
    print()


def main():
    """Run all examples."""
    print("\n" + "🎯 GemScore Delta Explainability Examples".center(80, " ") + "\n")
    
    example_1_basic_delta()
    input("Press Enter to continue...\n")
    
    example_2_feature_store_integration()
    input("Press Enter to continue...\n")
    
    example_3_api_response_format()
    input("Press Enter to continue...\n")
    
    example_4_alerts_and_thresholds()
    input("Press Enter to continue...\n")
    
    example_5_trend_analysis()
    
    print("=" * 80)
    print("✅ All examples completed!")
    print("=" * 80)
    print("\nFor more information, see:")
    print("  - docs/GEMSCORE_DELTA_EXPLAINABILITY.md")
    print("  - docs/GEMSCORE_DELTA_QUICK_REF.md")
    print()


if __name__ == "__main__":
    main()
