"""Insight modules — each exposes one ``analyze_*`` function.

Tier 1: deterministic structural stubs (real signal-extraction code path,
canned conclusions when input is empty). Each function returns a dict with
at minimum::

    {"module": str, "summary": str, "details": dict, "baseline_ready": bool}

``baseline_ready`` tells the reporter whether to show "gathering baseline"
language or actual findings.
"""

from .llm_usage import analyze_llm_usage
from .attention_switches import analyze_attention
from .health_productivity_correlation import analyze_health_vs_output
from .learning_roi import analyze_learning_roi
from .jobseek_followup import analyze_jobseek

__all__ = [
    "analyze_llm_usage",
    "analyze_attention",
    "analyze_health_vs_output",
    "analyze_learning_roi",
    "analyze_jobseek",
]
