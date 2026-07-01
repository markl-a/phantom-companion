"""Synthetic public demo loop artifacts for open-source readiness.

The demo loop is deliberately local-only and deterministic. It builds a fake
mesh tree, writes normalized health/output streams, records nightly check-ins,
and renders the same report surfaces a user would exercise manually.
"""

from __future__ import annotations

import json
from pathlib import Path

from .aggregator import aggregate_day
from .checkin import SubjectiveCheckin
from .fixtures import build_mesh_fixture
from .health_ingest import write_health_samples
from .output_ingest import write_output_samples
from .reporter import (
    render_daily_report,
    write_trend_report,
    write_weekly_report,
)
from .schema import HealthSample

SCHEMA_VERSION = 1


def write_synthetic_demo_loop(
    *,
    out_root: str | Path,
    end_day: str = "2026-05-30",
    days: int = 30,
    seed: int = 0,
) -> Path:
    """Write a deterministic synthetic mesh + report bundle.

    Returns the manifest path. The bundle contains no real user data, performs
    no network calls, and avoids the optional LLM coach path so two invocations
    with the same arguments produce stable bytes.
    """
    if days < 7:
        raise ValueError("demo-loop requires at least 7 days")
    out = Path(out_root)
    mesh_root = out / "mesh"
    reports_root = out / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)

    fixture = build_mesh_fixture(mesh_root, end_day=end_day, n_days=days, seed=seed)
    health_samples = {
        day: HealthSample.from_dict({"day": day, **sample})
        for day, sample in fixture.health_by_day.items()
    }
    output_samples = {
        day: {
            "commits": len(fixture.commits_by_day[day]),
            "lines_changed": len(fixture.commits_by_day[day]) * 24,
        }
        for day in fixture.days
    }
    health_paths = write_health_samples(mesh_root, health_samples)
    output_paths = write_output_samples(mesh_root, output_samples)
    checkin_path = _write_synthetic_checkins(reports_root, fixture.days)

    daily_path = reports_root / f"{end_day}-report.md"
    daily_text = render_daily_report(
        aggregate_day(end_day, mesh_root=mesh_root),
        coach_enabled=False,
    )
    daily_path.write_text(daily_text, encoding="utf-8")
    weekly_path = write_weekly_report(
        end_day=end_day,
        out_root=reports_root,
        mesh_root=mesh_root,
    )
    trends_path = write_trend_report(
        period="monthly",
        end_day=end_day,
        out_root=reports_root,
        mesh_root=mesh_root,
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "mode": "synthetic_demo_loop",
        "end_day": end_day,
        "days": days,
        "seed": seed,
        "data_policy": "synthetic_only",
        "private_data_included": False,
        "external_network": False,
        "llm_coach": "disabled",
        "mesh_root": _rel(out, mesh_root),
        "reports_root": _rel(out, reports_root),
        "inputs": {
            "event_days": len(fixture.days),
            "health_files": len(health_paths),
            "output_files": len(output_paths),
            "checkins": len(fixture.days),
        },
        "reports": {
            "daily": _rel(out, daily_path),
            "weekly": _rel(out, weekly_path),
            "trends": _rel(out, trends_path),
        },
        "stores": {
            "checkins": _rel(out, checkin_path),
            "health_dir": _rel(out, mesh_root / "logs" / "phantom-secure-connector"),
            "output_dir": _rel(out, mesh_root / "logs" / "phantom-companion"),
        },
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _write_synthetic_checkins(out_root: Path, days: list[str]) -> Path:
    path = out_root / "checkins.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for idx, day in enumerate(days):
            checkin = SubjectiveCheckin(
                day=day,
                gut=3 + (idx % 3 == 0),
                mood=2 + min(3, idx // max(1, len(days) // 4)),
                sleep_hr=6.4 + ((idx % 6) * 0.12),
            )
            fh.write(json.dumps(checkin.to_dict(), sort_keys=True) + "\n")
    return path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


__all__ = ["SCHEMA_VERSION", "write_synthetic_demo_loop"]
