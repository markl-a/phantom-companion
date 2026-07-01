"""Thirty-day review usefulness scenario for open-source readiness.

The scenario accepts a deterministic ``demo-loop`` bundle and writes a public
evidence package that answers: with 30 synthetic days, what can this companion
actually help review? It re-aggregates the bundle locally and exports only
coverage/readiness summaries, not raw mesh payloads.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .checkin import read_checkins
from .insight_modules.health_productivity_correlation import (
    correlate_health_output,
    correlate_subjective_output,
)
from .reporter import shame_free_check, weekly_rollup
from .schema import aggregate_window
from .trends import build_trends_from_window

SCHEMA_VERSION = 1
MIN_REVIEW_DAYS = 30


def write_review_scenario_bundle(
    *,
    source_bundle: str | Path,
    out_root: str | Path,
) -> Path:
    """Write a deterministic 30-day review scenario bundle.

    Returns the path to ``scenario-manifest.json``.
    """
    source = Path(source_bundle)
    out = Path(out_root)
    source_manifest = _load_source_manifest(source)
    _validate_source_manifest(source_manifest)

    days_count = int(source_manifest.get("days") or 0)
    if days_count < MIN_REVIEW_DAYS:
        raise RuntimeError("review-scenario requires at least 30 days")

    end_day = str(source_manifest.get("end_day") or "")
    days = _window_days(end_day=end_day, days=MIN_REVIEW_DAYS)
    source_root = source.parent if source.is_file() else source
    mesh_root = _bundle_path(source_root, str(source_manifest.get("mesh_root", "mesh")))
    reports_root = _bundle_path(
        source_root,
        str(source_manifest.get("reports_root", "reports")),
    )

    window = aggregate_window(days, mesh_root=mesh_root)
    checkins = read_checkins(reports_root)
    review = _build_review_payload(
        manifest=source_manifest,
        window=window,
        checkins=checkins,
    )

    out.mkdir(parents=True, exist_ok=True)
    review_path = out / "review-scenario.json"
    summary_path = out / "summary.md"
    readme_path = out / "README.md"
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(_render_summary(review), encoding="utf-8")
    readme_path.write_text(_render_readme(review), encoding="utf-8")

    scenario_manifest = {
        "schema_version": SCHEMA_VERSION,
        "mode": "thirty_day_review_scenario",
        "source_mode": source_manifest.get("mode", ""),
        "source_end_day": source_manifest.get("end_day", ""),
        "data_policy": "synthetic_only",
        "private_data_included": False,
        "raw_payloads_included": False,
        "external_network": False,
        "llm_coach": "disabled",
        "files": {
            "readme": _rel(out, readme_path),
            "review": _rel(out, review_path),
            "summary": _rel(out, summary_path),
        },
    }
    manifest_path = out / "scenario-manifest.json"
    manifest_path.write_text(
        json.dumps(scenario_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _load_source_manifest(source: Path) -> dict[str, Any]:
    manifest_path = source if source.is_file() else source / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("review-scenario requires a demo-loop manifest.json")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("review-scenario manifest must be a JSON object")
    return raw


def _validate_source_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("mode") != "synthetic_demo_loop"
        or manifest.get("data_policy") != "synthetic_only"
        or manifest.get("private_data_included") is not False
        or manifest.get("external_network") is not False
        or manifest.get("llm_coach") != "disabled"
    ):
        raise RuntimeError(
            "review-scenario only accepts synthetic demo bundles with private "
            "data, network access, and LLM coaching disabled"
        )


def _window_days(*, end_day: str, days: int) -> list[str]:
    end = date.fromisoformat(end_day)
    return [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def _build_review_payload(
    *,
    manifest: dict[str, Any],
    window: Any,
    checkins: dict[str, Any],
) -> dict[str, Any]:
    rollup = weekly_rollup(window)
    trends = build_trends_from_window(window, checkins)
    wellness_pairs = [
        {"sleep_hr": d.health.sleep_hr, "commits": d.output.commits}
        for d in window.days
        if d.health is not None and d.output is not None
    ]
    mood_pairs = [
        {"mood": checkins[d.day].mood, "commits": d.output.commits}
        for d in window.days
        if d.output is not None and d.day in checkins
    ]
    wellness_assoc = correlate_health_output(wellness_pairs)
    mood_assoc = correlate_subjective_output(mood_pairs)
    ready_trends = [t for t in trends if t.baseline_ready]

    coverage = {
        "days": len(window.days),
        "event_days": sum(1 for d in window.days if d.events),
        "health_source_days": sum(1 for d in window.days if d.health is not None),
        "output_source_days": sum(1 for d in window.days if d.output is not None),
        "nightly_checkins": sum(1 for d in window.days if d.day in checkins),
    }
    readiness = {
        "coverage_complete": all(value >= MIN_REVIEW_DAYS for value in coverage.values()),
        "long_window_trends_ready": len(ready_trends) > 0,
        "wellness_output_association_ready": bool(wellness_assoc["baseline_ready"]),
        "mood_output_association_ready": bool(mood_assoc["baseline_ready"]),
        "weekly_rollup_available": bool(rollup["days_observed"] >= 7),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "thirty_day_review_usefulness",
        "source_mode": manifest.get("mode", ""),
        "source_end_day": manifest.get("end_day", ""),
        "window": {
            "start_day": window.start,
            "end_day": window.end,
            "minimum_days_required": MIN_REVIEW_DAYS,
        },
        "data_policy": {
            "synthetic_only": True,
            "private_data_included": False,
            "raw_payloads_included": False,
            "external_network": False,
            "llm_coach": "disabled",
        },
        "coverage": coverage,
        "readiness": readiness,
        "signals": {
            "trend_metrics_ready": sorted({t.label for t in ready_trends}),
            "weekly_activity": {
                "days_observed": int(rollup["days_observed"]),
                "model_call_total": int(rollup["llm_usage"]["total_calls"]),
                "jobseek_pending_count": int(rollup["jobseek"]["pending"]),
                "jobseek_stale_count": len(rollup["jobseek"].get("stale_leads") or []),
            },
            "wellness_output_association": _association_summary(wellness_assoc),
            "mood_output_association": _association_summary(mood_assoc),
        },
        "review_tasks": [
            "monthly trend review",
            "wellness and output co-movement check",
            "mood and output co-movement check",
            "weekly activity and follow-up review",
            "consent discussion for any deeper local data source",
        ],
        "review_prompts": [
            "Which trend is ready enough to discuss in a monthly review?",
            "Did wellness and output move together enough to deserve local inspection?",
            "Did subjective mood and output move together enough to deserve local inspection?",
            "Which follow-up list should be revisited when there is time?",
            "What extra source would require explicit consent before import?",
        ],
        "boundaries": {
            "medical_advice": "not_supported",
            "causal_claims": "not_supported",
            "cloud_llm_default": "not_supported",
            "live_sensor_default": "not_supported",
            "raw_private_export": "not_supported",
        },
    }


def _association_summary(result: dict[str, Any]) -> dict[str, Any]:
    details = result.get("details") or {}
    return {
        "ready": bool(result.get("baseline_ready")),
        "sample_days": int(details.get("n_samples") or 0),
        "minimum_sample_days": int(details.get("min_samples") or 0),
        "direction": _direction_from_r(details.get("pearson_r")),
    }


def _direction_from_r(value: Any) -> str:
    if value is None:
        return "undefined"
    r = float(value)
    if r > 0:
        return "positive"
    if r < 0:
        return "negative"
    return "flat"


def _render_summary(review: dict[str, Any]) -> str:
    coverage = review["coverage"]
    readiness = review["readiness"]
    wellness = review["signals"]["wellness_output_association"]
    mood = review["signals"]["mood_output_association"]
    lines = [
        "# phantom-companion 30-day review scenario",
        "",
        "This bundle demonstrates what a public synthetic 30-day companion review can support.",
        "",
        "## Coverage",
        f"- Days represented: {coverage['days']}",
        f"- Event days: {coverage['event_days']}",
        f"- Wellness source days: {coverage['health_source_days']}",
        f"- Output source days: {coverage['output_source_days']}",
        f"- Nightly check-ins: {coverage['nightly_checkins']}",
        "",
        "## Readiness",
        f"- Long-window trends ready: {readiness['long_window_trends_ready']}",
        (
            "- The scenario can show whether wellness and output moved together: "
            f"{wellness['ready']} ({wellness['direction']})."
        ),
        (
            "- The scenario can show whether mood and output moved together: "
            f"{mood['ready']} ({mood['direction']})."
        ),
        "",
        "## Boundaries",
        "- No medical advice, causal claims, cloud LLM default, live sensor default, or raw private export.",
        "",
    ]
    text = "\n".join(lines)
    ok, reason = shame_free_check(text)
    if not ok:
        raise RuntimeError(f"refused to emit shame-leaking scenario summary: {reason}")
    return text


def _render_readme(review: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Review Scenario Bundle",
            "",
            "This folder is an open-source evidence bundle for a synthetic 30-day review.",
            "It contains readiness summaries and review prompts only.",
            "",
            f"Source end day: `{review['source_end_day']}`",
            "Data policy: `synthetic_only`",
            "Raw payloads included: `false`",
            "",
        ]
    )


def _bundle_path(root: Path, rel: str) -> Path:
    candidate = Path(rel)
    if candidate.is_absolute():
        raise RuntimeError("review-scenario manifest paths must be bundle-relative")
    root_resolved = root.resolve()
    path = (root / candidate).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError("review-scenario manifest paths must stay inside the bundle") from exc
    return path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


__all__ = [
    "MIN_REVIEW_DAYS",
    "SCHEMA_VERSION",
    "write_review_scenario_bundle",
]
