from phantom_companion.insight_modules.health_productivity_correlation import (
    correlate_subjective_output,
)
from phantom_companion.thresholds import MIN_SAMPLES


def test_subjective_output_positive_correlation_after_min_samples() -> None:
    samples = [
        {"mood": float(i), "commits": i}
        for i in range(1, MIN_SAMPLES + 1)
    ]

    out = correlate_subjective_output(samples)

    assert out["baseline_ready"] is True
    assert out["details"]["pearson_r"] > 0
    assert "positive" in out["summary"]
    assert "association r=" in out["summary"]


def test_subjective_output_stays_in_baseline_mode_before_min_samples() -> None:
    samples = [
        {"mood": float(i), "commits": i}
        for i in range(1, MIN_SAMPLES)
    ]

    out = correlate_subjective_output(samples)

    assert out["baseline_ready"] is False
    assert "baseline mode" in out["summary"]
