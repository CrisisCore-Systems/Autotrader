from src.services.feedback import PrecisionTracker, RecommendationOutcome, WeightOptimizer


def test_precision_tracker_updates_metrics() -> None:
    tracker = PrecisionTracker(window=3)
    tracker.log_run(
        "run-1",
        [
            RecommendationOutcome(
                token="AAA",
                rank=1,
                score=0.9,
                flagged=True,
                executed=True,
                realized_return=0.12,
            ),
            RecommendationOutcome(
                token="BBB",
                rank=2,
                score=0.8,
                flagged=False,
                executed=True,
                realized_return=-0.05,
            ),
        ],
    )
    tracker.log_run(
        "run-2",
        [
            RecommendationOutcome(
                token="CCC",
                rank=1,
                score=0.95,
                flagged=True,
                executed=False,
            )
        ],
    )

    assert tracker.precision_at_k(1) == 0.5
    assert round(tracker.average_return_at_k(2), 3) == 0.035
    assert tracker.flagged_assets() == ["AAA", "CCC"]

    tracker.update_outcomes("run-2", {"CCC": {"executed": True, "realized_return": 0.2}})
    assert tracker.precision_at_k(1) == 1.0
    assert tracker.recent_runs(limit=1)[0].outcomes[0].executed is True


def test_weight_optimizer_balances_scores() -> None:
    optimizer = WeightOptimizer()
    weights = optimizer.optimise(
        {
            "alpha": [0.1, 0.2, 0.15],
            "beta": [0.05, -0.02, 0.04],
            "gamma": [],
        },
        floor=0.0,
    )
    assert set(weights.keys()) == {"alpha", "beta", "gamma"}
    assert round(sum(weights.values()), 5) == 1.0
    assert weights["alpha"] > weights["beta"] > weights["gamma"]
