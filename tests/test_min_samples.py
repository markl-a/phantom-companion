"""P1-M1 — MIN_SAMPLES is the single source of truth for the statistical gate.

A statistical correlation must not be reported until at least ``MIN_SAMPLES``
days of paired data exist. The constant lives in exactly ONE place and every
thresholding code path imports it, so the gate cannot be silently bypassed by
a stray hard-coded number drifting out of sync.
"""

from __future__ import annotations

import ast
from pathlib import Path

from phantom_companion.thresholds import MIN_SAMPLES, has_min_samples


PKG = Path(__file__).resolve().parents[1] / "phantom_companion"


def test_min_samples_is_about_two_weeks() -> None:
    # The statistical window is ~14 days; pin the documented default.
    assert MIN_SAMPLES == 14
    assert isinstance(MIN_SAMPLES, int)


def test_has_min_samples_gate() -> None:
    assert has_min_samples(MIN_SAMPLES) is True
    assert has_min_samples(MIN_SAMPLES + 1) is True
    assert has_min_samples(MIN_SAMPLES - 1) is False
    assert has_min_samples(0) is False


def _assigns_min_samples(py_file: Path) -> bool:
    """True if the file BINDS ``MIN_SAMPLES`` to a literal (plain or annotated).

    An ``import``/``from ... import MIN_SAMPLES`` does NOT count as a definition;
    only a literal assignment (``MIN_SAMPLES = 14`` / ``MIN_SAMPLES: int = 14``)
    does. That is exactly the drift we are guarding against.
    """
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MIN_SAMPLES":
                    if isinstance(node.value, ast.Constant):
                        return True
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if (
                isinstance(target, ast.Name)
                and target.id == "MIN_SAMPLES"
                and isinstance(node.value, ast.Constant)
            ):
                return True
    return False


def test_min_samples_defined_in_exactly_one_module() -> None:
    """No other module may DEFINE MIN_SAMPLES — they must import it."""
    definers = [p for p in PKG.rglob("*.py") if _assigns_min_samples(p)]
    rel = sorted(p.relative_to(PKG).as_posix() for p in definers)
    assert rel == ["thresholds.py"], f"MIN_SAMPLES defined in unexpected files: {rel}"


def test_statistical_modules_import_the_constant() -> None:
    """Every module that gates on the sample window imports MIN_SAMPLES.

    Currently the health-vs-output statistical correlation is the gate; if a
    new statistical module starts referencing MIN_SAMPLES it must import it
    from :mod:`phantom_companion.thresholds`, never redefine it.
    """
    from phantom_companion.insight_modules import health_productivity_correlation as h

    assert h.MIN_SAMPLES is MIN_SAMPLES


def test_correlation_gate_blocks_below_min_samples() -> None:
    from phantom_companion.insight_modules.health_productivity_correlation import (
        correlate_health_output,
    )

    # Fewer than MIN_SAMPLES paired days -> not ready, regardless of values.
    short = [
        {"sleep_hr": 7.0 + (i % 3), "commits": 2 + (i % 4)}
        for i in range(MIN_SAMPLES - 1)
    ]
    out = correlate_health_output(short)
    assert out["baseline_ready"] is False
    assert out["details"]["n_samples"] == MIN_SAMPLES - 1
    # The waiting message must reference the single-source threshold, not a
    # drifting hard-coded literal.
    assert str(MIN_SAMPLES) in out["summary"]


def test_correlation_gate_opens_at_min_samples() -> None:
    from phantom_companion.insight_modules.health_productivity_correlation import (
        correlate_health_output,
    )

    # MIN_SAMPLES paired days with a real linear relationship -> ready + r computed.
    samples = [
        {"sleep_hr": 5.0 + 0.2 * i, "commits": i}
        for i in range(MIN_SAMPLES)
    ]
    out = correlate_health_output(samples)
    assert out["baseline_ready"] is True
    assert out["details"]["n_samples"] == MIN_SAMPLES
    assert "pearson_r" in out["details"]
    # Perfect monotone relationship -> strong positive correlation.
    assert out["details"]["pearson_r"] > 0.9
