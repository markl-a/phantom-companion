"""Time-series anomaly detector — stdlib-only port of AHI Detection v2 core.

Algorithm (Tier 1 simplification):

1. **Rolling window.** For each point at index ``i``, compute robust centre
   (median) and scale (MAD) over the trailing ``window`` points. MAD is used
   instead of std-dev because it is robust to the very anomalies we are trying
   to surface.
2. **Robust z-score.** ``score = |x - median| / (1.4826 * MAD + epsilon)``.
   The 1.4826 factor makes MAD a consistent estimator of std-dev for normal
   data.
3. **5-fold CV threshold calibration.** When ground-truth labels are not
   supplied (the common case), ``detect`` uses a default threshold of 3.5.
   When labels are supplied, ``calibrate_threshold`` runs a 5-fold split and
   picks the threshold maximising F1, then applies it globally — this mirrors
   the AHI v2 "calibrated threshold shift" approach without requiring
   scikit-learn's IsotonicRegression.
4. **Score → bool.** An isotonic-style monotone shift: any point whose raw
   robust-z exceeds the threshold is flagged.

Tier 2 work (not done): plug phantom-mesh provider trait for an LLM-assisted
narrative on each flagged point; replace MAD with seasonal-trend decomposition
(STL) for periodic series.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

# Type alias: a single sample = (timestamp_like, value).
Sample = Tuple[object, float]


@dataclass
class AnomalyPoint:
    timestamp: object
    value: float
    is_anomaly: bool
    score: float

    def as_tuple(self) -> Tuple[object, float, bool, float]:
        return (self.timestamp, self.value, self.is_anomaly, self.score)


def _mad(window: Sequence[float], median: float) -> float:
    """Median absolute deviation."""
    if not window:
        return 0.0
    return statistics.median(abs(x - median) for x in window)


def _robust_zscore(value: float, window: Sequence[float]) -> float:
    if len(window) < 2:
        return 0.0
    med = statistics.median(window)
    mad = _mad(window, med)
    # 1.4826 makes MAD consistent with std-dev for normal data.
    scale = 1.4826 * mad + 1e-9
    return abs(value - med) / scale


def detect(
    series: Iterable[Sample],
    window: int = 7,
    threshold: float = 3.5,
    min_window: Optional[int] = None,
) -> List[AnomalyPoint]:
    """Detect anomalies in a univariate time series.

    Parameters
    ----------
    series : iterable of (timestamp, value)
        Time-ordered samples. Timestamps are opaque (any sortable type).
    window : int, default 7
        Trailing-window size for the rolling median/MAD.
    threshold : float, default 3.5
        Robust-z threshold above which a point is flagged.
    min_window : int or None
        Minimum number of trailing points required before a point can be
        flagged. Defaults to ``window`` so early-series points (where MAD
        is unstable) cannot fire false positives. Set to a smaller value
        if you really want flags on warm-up.

    Returns
    -------
    list[AnomalyPoint]
    """
    pts = list(series)
    if min_window is None:
        min_window = window
    out: List[AnomalyPoint] = []
    for i, (ts, val) in enumerate(pts):
        # Use the trailing window — exclude the current point so it does not
        # mask itself.
        start = max(0, i - window)
        win_vals = [v for (_, v) in pts[start:i]]
        score = _robust_zscore(val, win_vals)
        # Require min_window trailing samples AND a non-degenerate MAD.
        # When MAD == 0 the scale collapses and any deviation explodes the
        # score; treat that as "insufficient signal", not an anomaly.
        has_signal = len(win_vals) >= min_window
        if has_signal:
            med = statistics.median(win_vals)
            mad = _mad(win_vals, med)
            has_signal = mad > 1e-6
        is_anom = has_signal and score > threshold
        out.append(AnomalyPoint(ts, val, is_anom, score))
    return out


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def calibrate_threshold(
    series: Sequence[Sample],
    labels: Sequence[bool],
    window: int = 7,
    candidates: Optional[Sequence[float]] = None,
    folds: int = 5,
) -> float:
    """5-fold CV threshold search maximising mean validation F1.

    Returns the best threshold (a float). Mirrors AHI v2 calibration without
    depending on scikit-learn.
    """
    if len(series) != len(labels):
        raise ValueError("series and labels must be same length")
    if candidates is None:
        candidates = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

    n = len(series)
    fold_size = max(1, n // folds)
    indices = list(range(n))

    best_thr = candidates[0]
    best_score = -1.0

    for thr in candidates:
        fold_f1s: List[float] = []
        for f in range(folds):
            val_start = f * fold_size
            val_end = val_start + fold_size if f < folds - 1 else n
            val_idx = set(indices[val_start:val_end])

            # Predict over the whole series with this threshold, then score on
            # the validation slice only.
            preds = detect(series, window=window, threshold=thr)
            tp = fp = fn = 0
            for i in val_idx:
                p = preds[i].is_anomaly
                y = labels[i]
                if p and y:
                    tp += 1
                elif p and not y:
                    fp += 1
                elif (not p) and y:
                    fn += 1
            fold_f1s.append(_f1(tp, fp, fn))
        mean_f1 = sum(fold_f1s) / len(fold_f1s) if fold_f1s else 0.0
        if mean_f1 > best_score:
            best_score = mean_f1
            best_thr = thr
    return best_thr
