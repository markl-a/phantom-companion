"""Single source of truth for statistical gating thresholds.

Why this module exists
----------------------
Several insight modules guard their findings behind a "do we have enough
data yet?" check. If each module hard-codes its own number, the gates drift
out of sync and a statistically-unsound correlation can leak into a report.
To make that class of bug impossible, the sample-window threshold is defined
*once* here and imported everywhere it is needed.

``MIN_SAMPLES`` is the minimum number of paired daily observations required
before any statistical correlation (e.g. health vs. output) is allowed to be
reported. ~14 days (two weeks) is the smallest window that gives a Pearson
r enough degrees of freedom to be worth showing the user; below it the
honest answer is "still gathering baseline".
"""

from __future__ import annotations

# The statistical window, in days. The ONE place this is defined.
MIN_SAMPLES: int = 14


def has_min_samples(n: int) -> bool:
    """Return ``True`` iff ``n`` observations meet the statistical-window gate."""
    return n >= MIN_SAMPLES


__all__ = ["MIN_SAMPLES", "has_min_samples"]
