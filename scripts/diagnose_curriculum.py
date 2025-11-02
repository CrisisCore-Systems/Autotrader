"""
Diagnostic script to check curriculum advancement logic.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Simulate the curriculum check logic
def test_curriculum_advancement():
    """Test if 0.0 >= 0.0 evaluates correctly for curriculum advancement."""
    
    # Bootstrap stage requirements
    min_timesteps = 0
    target_win_rate = 0.0
    
    # Simulated metrics
    current_timesteps = 10000
    current_win_rate = 0.0  # What we're seeing in training
    
    print("="*60)
    print("CURRICULUM ADVANCEMENT DIAGNOSTIC")
    print("="*60)
    print(f"\nBootstrap → Confidence Stage Requirements:")
    print(f"  Min timesteps: {min_timesteps:,}")
    print(f"  Target win rate: {target_win_rate}%")
    print(f"\nCurrent Training State:")
    print(f"  Current timesteps: {current_timesteps:,}")
    print(f"  Current win rate: {current_win_rate}%")
    
    # Test the logic from CurriculumLearningManager.maybe_advance()
    meets_time = current_timesteps >= min_timesteps
    meets_win_rate = current_win_rate >= target_win_rate if current_win_rate is not None else False
    
    print(f"\nCondition Checks:")
    print(f"  meets_time: {meets_time} ({current_timesteps:,} >= {min_timesteps:,})")
    print(f"  meets_win_rate: {meets_win_rate} ({current_win_rate} >= {target_win_rate})")
    print(f"  win_rate is not None: {current_win_rate is not None}")
    
    should_advance = meets_time and meets_win_rate
    
    print(f"\n🎯 Should Advance: {should_advance}")
    print(f"  Logic: {meets_time} AND {meets_win_rate} = {should_advance}")
    
    if should_advance:
        print("\n✅ Advancement SHOULD work!")
    else:
        print("\n❌ Advancement BLOCKED!")
        if not meets_time:
            print("   Reason: Not enough timesteps")
        if not meets_win_rate:
            print("   Reason: Win rate too low")
    
    print("\n" + "="*60)
    
    # Test edge case: what if win_rate is None or missing from dict?
    print("\nEDGE CASE TESTS:")
    print("-"*60)
    
    test_cases = [
        ("win_rate = 0.0", 0.0),
        ("win_rate = None", None),
        ("win_rate missing (using .get())", None),
    ]
    
    for desc, test_win_rate in test_cases:
        metrics = {'win_rate': test_win_rate} if test_win_rate is not None else {}
        win_rate = metrics.get('win_rate', 0.0)
        meets_wr = win_rate >= target_win_rate if win_rate is not None else False
        
        print(f"\n{desc}:")
        print(f"  metrics.get('win_rate', 0.0) = {win_rate}")
        print(f"  win_rate is not None = {win_rate is not None}")
        print(f"  {win_rate} >= {target_win_rate} = {meets_wr}")
        print(f"  Would advance: {meets_time and meets_wr}")
    
    print("\n" + "="*60)

def test_win_rate_calculation():
    """Test how win rate is calculated from episode data."""
    
    print("\nWIN RATE CALCULATION TEST:")
    print("-"*60)
    
    # Simulate what we see in logs: all losses
    episode_pnls = [-183.99, -159.79, -213.35, -216.34, -185.08]  # First 5 episodes from log
    episode_wins = [1 if pnl > 0 else 0 for pnl in episode_pnls]
    
    print(f"\nSample Episodes (first 5):")
    for i, pnl in enumerate(episode_pnls, 1):
        print(f"  Episode {i}: ${pnl:.2f} → {'WIN' if pnl > 0 else 'LOSS'}")
    
    win_rate = (sum(episode_wins) / len(episode_wins)) * 100 if episode_wins else 0
    
    print(f"\nWin Rate Calculation:")
    print(f"  Wins: {sum(episode_wins)}")
    print(f"  Total episodes: {len(episode_wins)}")
    print(f"  Win rate: {win_rate:.1f}%")
    
    print("\n" + "="*60)

def test_metrics_passing():
    """Test how metrics are passed between callbacks."""
    
    print("\nMETRICS PASSING TEST:")
    print("-"*60)
    
    # Simulate WinRateCallback
    class MockWinRateCallback:
        def __init__(self):
            self.last_metrics = {}
            self.episode_pnls = []
        
        def get_recent_metrics(self):
            """This is what curriculum callback calls."""
            return dict(self.last_metrics)
    
    callback = MockWinRateCallback()
    
    print("\nScenario 1: No episodes collected yet")
    metrics = callback.get_recent_metrics()
    print(f"  Returned metrics: {metrics}")
    print(f"  metrics.get('win_rate', 0.0) = {metrics.get('win_rate', 0.0)}")
    
    print("\nScenario 2: Episodes collected, 0% win rate")
    callback.episode_pnls = [-100, -200, -150]
    callback.last_metrics = {'win_rate': 0.0, 'avg_pnl': -150}
    metrics = callback.get_recent_metrics()
    print(f"  Returned metrics: {metrics}")
    print(f"  metrics.get('win_rate', 0.0) = {metrics.get('win_rate', 0.0)}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_curriculum_advancement()
    test_win_rate_calculation()
    test_metrics_passing()
    
    print("\n✅ Diagnostic complete!")
    print("\nNext steps:")
    print("  1. If advancement logic works → check callback is actually running")
    print("  2. If win_rate = None → WinRateCallback not collecting episodes")
    print("  3. If win_rate = 0.0 but not advancing → check curriculum_enabled flag")
