"""Deterministic mock-mesh fixture harness for offline end-to-end tests.

Real ``~/.phantom-mesh`` data is encrypted and only materialises after weeks
of daily use, so there is no way to exercise the full aggregate → insight →
report pipeline against it in CI. This module synthesises a fake mesh tree
that the aggregator reads exactly like the real one, plus the parallel
health-sample and commit streams the statistical modules consume.

Determinism is the whole point: :func:`build_mesh_fixture` is seeded and
writes JSON with ``sort_keys=True``, so two builds with the same seed produce
byte-identical trees. That lets report tests assert on stable output without
flaking. Nothing here touches the network or shells out to ``phantom``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Mirror of aggregator.SATELLITES; imported lazily to avoid a hard cycle and to
# keep the fixture self-describing if the aggregator list ever changes.
from .aggregator import SATELLITES

# Event "kinds" the fixture rotates through — matches the analysis blob shape
# the insight modules look for (provider / task_kind / company / tags).
_PROVIDERS = ("claude", "mlx", "groq", "gemini")
_TASK_KINDS = ("code_review", "doc", "research", "chat", "refactor")
_COMPANIES = ("Garmin", "Anthropic", "Micron", "南亞科")


@dataclass
class MeshFixture:
    """Handle returned by :func:`build_mesh_fixture`.

    Carries the on-disk root plus the in-memory *parallel streams* (health
    samples and commit lists per day) so statistical tests can compare what
    they read back against what was generated.
    """

    root: Path
    days: list[str]
    health_by_day: dict[str, dict[str, Any]] = field(default_factory=dict)
    commits_by_day: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    events_by_day: dict[str, int] = field(default_factory=dict)


def fixture_days(end_day: str, n_days: int) -> list[str]:
    """Return ``n_days`` contiguous ISO dates ending on ``end_day`` (inclusive)."""
    if n_days < 1:
        raise ValueError("n_days must be >= 1")
    end = date.fromisoformat(end_day)
    days = [(end - timedelta(days=i)).isoformat() for i in range(n_days - 1, -1, -1)]
    return days


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    # sort_keys=True keeps the bytes stable across runs -> deterministic trees.
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _health_sample(rng: random.Random) -> dict[str, Any]:
    return {
        "sleep_hr": round(rng.uniform(5.5, 8.5), 2),
        "hrv_ms": round(rng.uniform(35.0, 75.0), 1),
        "resting_hr": rng.randint(48, 66),
    }


def build_mesh_fixture(
    root: Path,
    end_day: str = "2026-05-22",
    n_days: int = 14,
    seed: int = 0,
) -> MeshFixture:
    """Build a deterministic fake ``~/.phantom-mesh`` tree under ``root``.

    Produces, for each of ``n_days`` days ending at ``end_day``:

    - ``events/<day>-<i>/{meta.json, analysis.json}`` — a handful of events
      whose ``meta.timestamp`` falls strictly inside that day.
    - ``logs/phantom-ai-feed/<day>.md`` — a digest with headings + Q&A blocks.
    - ``logs/phantom-flow/<day>.log`` — a short activity line.
    - parallel ``health_by_day`` and ``commits_by_day`` streams (returned, not
      part of the encrypted mesh tree the aggregator scans).

    Plus per-satellite heartbeat files. Returns a :class:`MeshFixture`.
    """
    root = Path(root)
    days = fixture_days(end_day, n_days)
    events_dir = root / "events"
    logs_dir = root / "logs"
    feed_dir = logs_dir / "phantom-ai-feed"
    flow_dir = logs_dir / "phantom-flow"
    for d in (events_dir, feed_dir, flow_dir):
        d.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    fx = MeshFixture(root=root, days=days)

    for di, day in enumerate(days):
        # Deterministic-but-varying event count per day (2..5).
        n_events = 2 + (rng.randrange(4))
        fx.events_by_day[day] = n_events
        for ei in range(n_events):
            hour = 8 + ((di * 3 + ei * 5) % 13)  # within 08..20
            minute = (ei * 7 + di) % 60
            ts = f"{day}T{hour:02d}:{minute:02d}:00Z"
            ev_id = f"{day}-{ei:02d}"
            ev_dir = events_dir / ev_id
            ev_dir.mkdir(parents=True, exist_ok=True)
            tags = ["jobseek"]
            applied = rng.random() < 0.4
            if applied:
                tags.append("applied")
            meta = {
                "timestamp": ts,
                "tags": tags,
                "company": _COMPANIES[(di + ei) % len(_COMPANIES)],
                "applied": applied,
            }
            analysis = {
                "provider": _PROVIDERS[(di + ei) % len(_PROVIDERS)],
                "task_kind": _TASK_KINDS[(di * 2 + ei) % len(_TASK_KINDS)],
                "summary": f"synthetic event {ev_id}",
            }
            _write_json(ev_dir / "meta.json", meta)
            _write_json(ev_dir / "analysis.json", analysis)

        # ai-feed digest: a few headings + Q&A so learning_roi fires.
        n_items = 2 + (di % 3)
        feed_lines: list[str] = []
        for k in range(n_items):
            feed_lines.append(f"## Item {day}-{k}")
            if k % 2 == 0:
                feed_lines.append("Q: what is the takeaway?")
        (feed_dir / f"{day}.md").write_text("\n".join(feed_lines) + "\n", encoding="utf-8")

        # flow activity line.
        (flow_dir / f"{day}.log").write_text(f"flow ran on {day}\n", encoding="utf-8")

        # Parallel streams (NOT in the encrypted mesh; consumed directly by
        # statistical modules). Health correlates loosely with commit count by
        # construction so the Pearson path has signal once the window fills.
        health = _health_sample(rng)
        fx.health_by_day[day] = health
        base = int(round((health["sleep_hr"] - 5.0) * 1.5))
        n_commits = max(0, base + rng.randrange(2))
        fx.commits_by_day[day] = [
            {"sha": f"{day}-{c:02d}", "day": day} for c in range(n_commits)
        ]

    # Heartbeats: mark a deterministic subset alive (non-empty) vs idle (empty).
    for i, sat in enumerate(SATELLITES):
        hb = logs_dir / f"{sat}-heartbeat.log"
        hb.write_text("alive\n" if i % 2 == 0 else "", encoding="utf-8")

    return fx


def correlation_samples(fx: MeshFixture) -> list[dict[str, Any]]:
    """Flatten a :class:`MeshFixture`'s parallel streams into the shape
    :func:`correlate_health_output` consumes: one ``{sleep_hr, commits}`` row
    per day, in day order.
    """
    rows: list[dict[str, Any]] = []
    for day in fx.days:
        rows.append(
            {
                "day": day,
                "sleep_hr": fx.health_by_day[day]["sleep_hr"],
                "commits": len(fx.commits_by_day[day]),
            }
        )
    return rows


__all__ = [
    "MeshFixture",
    "build_mesh_fixture",
    "fixture_days",
    "correlation_samples",
]
