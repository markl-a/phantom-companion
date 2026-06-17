"""Generic time-series anomaly detector.

Port of AHI Detection v2 core: rolling robust z-score + 5-fold cross-validation
threshold calibration + isotonic-style monotone score shift. Stdlib-only so it
runs inside the phantom-mesh sandbox without numpy/sklearn.
"""
from .detector import detect, AnomalyPoint, calibrate_threshold
from .gate import (
    AnomalyAlert,
    detect_metric_anomalies,
    gated_anomaly_alerts,
    render_anomaly_alerts,
)

__all__ = [
    "detect",
    "AnomalyPoint",
    "calibrate_threshold",
    "AnomalyAlert",
    "detect_metric_anomalies",
    "gated_anomaly_alerts",
    "render_anomaly_alerts",
]
