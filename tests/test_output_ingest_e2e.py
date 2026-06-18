"""End-to-end: git activity becomes real developer-output samples.

This proves production writes ``output-<day>.json`` from git before the existing
health/output readers and trend correlation consume it. The test deliberately
does not pre-write output fixtures; the CLI writer must create them from a real
temporary repository.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path

from phantom_companion.cli import main
from phantom_companion.health_ingest import read_output_window
from phantom_companion.reporter import shame_free_check


def _days_ending(end: str, n: int) -> list[str]:
    e = date.fromisoformat(end)
    return [(e - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=run_env,
    )


def _build_git_repo(repo: Path, days: list[str]) -> dict[str, dict[str, int]]:
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    expected: dict[str, dict[str, int]] = {}
    for day_index, day in enumerate(days):
        commits = day_index + 1
        expected[day] = {"commits": commits, "lines_changed": commits}
        for commit_index in range(commits):
            path = repo / "activity.txt"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"{day} commit {commit_index}\n")
            _git(repo, "add", "activity.txt")
            when = f"{day}T12:00:00"
            _git(
                repo,
                "commit",
                "-m",
                f"activity {day} {commit_index}",
                env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
            )
    return expected


def _write_health_export(mesh_root: Path, day: str, sleep_hr: float) -> None:
    d = mesh_root / "logs" / "phantom-secure-connector"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"health-{day}.json").write_text(
        json.dumps(
            {
                "day": day,
                "sleep_hr": sleep_hr,
                "hrv_ms": 55.0,
                "resting_hr": 53,
                "activity_min": 40,
                "source": "garmin",
            }
        ),
        encoding="utf-8",
    )


def test_git_output_ingest_cli_feeds_monthly_health_output_trend(
    tmp_path: Path,
) -> None:
    mesh = tmp_path / "mesh"
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    end = "2026-05-30"
    days = _days_ending(end, 14)
    first = days[0]
    expected = _build_git_repo(repo, days)

    output_dir = mesh / "logs" / "phantom-companion"
    if output_dir.exists():
        assert not list(output_dir.glob("output-*.json"))

    rc = main(
        [
            "--mesh-root",
            str(mesh),
            "ingest-output",
            "--repo",
            str(repo),
            "--since",
            first,
            "--day",
            end,
        ]
    )
    assert rc == 0

    for day in days:
        path = output_dir / f"output-{day}.json"
        assert path.exists()
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["commits"] > 0
        assert raw["lines_changed"] > 0
        assert raw["commits"] == expected[day]["commits"]
        assert raw["lines_changed"] == expected[day]["lines_changed"]

    output = read_output_window(mesh, days)
    assert output
    assert output == expected

    for i, day in enumerate(days):
        _write_health_export(mesh, day, sleep_hr=5.0 + 0.1 * i)

    rc = main(
        [
            "--mesh-root",
            str(mesh),
            "trends",
            "--period",
            "monthly",
            "--end",
            end,
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    body = (out / f"{end}-monthly-trends.md").read_text(encoding="utf-8")

    assert "## Health × output" in body
    assert "days observed" in body
    assert "0/14 days of paired health+output data" not in body
    assert "association r=" in body
    ok, reason = shame_free_check(body)
    assert ok, reason
