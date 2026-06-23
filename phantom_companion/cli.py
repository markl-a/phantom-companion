"""``phantom-companion`` command-line entry point.

Subcommands:
- ``daily-report [--day YYYY-MM-DD] [--out DIR]``
- ``weekly-report [--end YYYY-MM-DD] [--out DIR]``

Default output: ``~/.phantom-mesh/logs/phantom-companion/<date>-report.md``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from . import __version__
from .reporter import (
    write_anomaly_alerts,
    write_daily_report,
    write_trend_report,
    write_weekly_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phantom-companion",
        description="Proactive behavior observer for phantom-mesh.",
    )
    parser.add_argument("--version", action="version", version=f"phantom-companion {__version__}")
    parser.add_argument(
        "--mesh-root",
        type=Path,
        default=None,
        help="Override PHANTOM_MESH_HOME (default: ~/.phantom-mesh).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    daily = sub.add_parser("daily-report", help="Write today's daily report.")
    daily.add_argument("--day", default=None, help="ISO YYYY-MM-DD (default: today).")
    daily.add_argument("--out", type=Path, default=None, help="Output directory.")

    weekly = sub.add_parser("weekly-report", help="Write a 7-day weekly report.")
    weekly.add_argument("--end", default=None, help="Last day of the window (ISO).")
    weekly.add_argument("--out", type=Path, default=None, help="Output directory.")

    trends = sub.add_parser(
        "trends", help="Write a monthly (30d) / quarterly (90d) trend digest."
    )
    trends.add_argument(
        "--period", choices=("monthly", "quarterly"), default="monthly",
        help="Trend window (default: monthly).",
    )
    trends.add_argument("--end", default=None, help="Last day of the window (ISO).")
    trends.add_argument("--out", type=Path, default=None, help="Output directory.")

    anomaly = sub.add_parser("anomaly-alerts", help="Write a 30-day anomaly alert summary.")
    anomaly.add_argument(
        "--metric",
        choices=("attention", "llm_cost", "sleep_hr", "hrv_ms", "resting_hr"),
        default="attention",
        help="Metric to inspect (default: attention).",
    )
    anomaly.add_argument("--end", default=None, help="Last day of the window (ISO).")
    anomaly.add_argument("--out", type=Path, default=None, help="Output directory.")

    checkin = sub.add_parser(
        "checkin", help="Record one nightly subjective check-in line (local only)."
    )
    checkin.add_argument(
        "line",
        help="e.g. '2026-05-22 gut=4 mood=3 sleep=7.2' or '2026-05-22, 4, 3, 7.2'.",
    )
    checkin.add_argument("--out", type=Path, default=None, help="Output directory.")

    ingest = sub.add_parser(
        "ingest-output", help="Collect git activity into developer-output samples."
    )
    ingest.add_argument("--repo", type=Path, default=Path.cwd(), help="Git repo to inspect.")
    ingest.add_argument("--day", default=None, help="ISO YYYY-MM-DD day to ingest.")
    ingest.add_argument("--since", default=None, help="ISO YYYY-MM-DD inclusive window start.")

    ingest_health = sub.add_parser(
        "ingest-health",
        help="Parse a secure-connector export into normalized health samples.",
    )
    ingest_health.add_argument(
        "export_file",
        type=Path,
        help="Path to the export JSON (one day object or a list of day rows).",
    )

    goal = sub.add_parser("goal", help="Manage accountability goals.")
    goal_sub = goal.add_subparsers(dest="goal_cmd", required=True)
    g_set = goal_sub.add_parser("set", help="Declare or update a goal.")
    g_set.add_argument("metric", choices=("commits", "activity_min", "sleep_hr",
                                          "mood", "jobs_applied", "llm_calls"))
    g_set.add_argument("direction", choices=("at-least", "at-most"))
    g_set.add_argument("target", type=float)
    g_set.add_argument("--label", default="")
    g_set.add_argument("--window", type=int, default=None, help="Override default window (days).")
    g_set.add_argument("--out", type=Path, default=None)
    g_list = goal_sub.add_parser("list", help="List declared goals.")
    g_list.add_argument("--out", type=Path, default=None)
    g_rm = goal_sub.add_parser("rm", help="Remove a goal by id.")
    g_rm.add_argument("goal_id")
    g_rm.add_argument("--out", type=Path, default=None)

    goals_cmd = sub.add_parser("goals", help="Show current goal status.")
    goals_cmd.add_argument("--end", default=None, help="Last day of the eval window (ISO).")
    goals_cmd.add_argument("--out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "daily-report":
            path = write_daily_report(day=args.day, out_root=args.out, mesh_root=args.mesh_root)
        elif args.cmd == "weekly-report":
            path = write_weekly_report(end_day=args.end, out_root=args.out, mesh_root=args.mesh_root)
        elif args.cmd == "trends":
            path = write_trend_report(
                period=args.period, end_day=args.end, out_root=args.out,
                mesh_root=args.mesh_root,
            )
        elif args.cmd == "anomaly-alerts":
            from .schema import aggregate_window

            end = date.fromisoformat(args.end) if args.end else date.today()
            days = [(end - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
            window = aggregate_window(days, mesh_root=args.mesh_root)
            path = write_anomaly_alerts(window, metric=args.metric, out_root=args.out)
        elif args.cmd == "checkin":
            path = _record_checkin(args.line, out_root=args.out)
        elif args.cmd == "ingest-output":
            from .output_ingest import ingest_output

            mesh_root = args.mesh_root if args.mesh_root else Path.home() / ".phantom-mesh"
            paths = ingest_output(
                repo=args.repo,
                mesh_root=mesh_root,
                days=_ingest_days(args.since, args.day),
            )
            print(f"{len(paths)} output files written")
            for written in paths:
                print(str(written))
            return 0
        elif args.cmd == "ingest-health":
            from .health_ingest import ingest_health

            mesh_root = args.mesh_root if args.mesh_root else Path.home() / ".phantom-mesh"
            paths = ingest_health(export_file=args.export_file, mesh_root=mesh_root)
            print(f"{len(paths)} health files written")
            for written in paths:
                print(str(written))
            return 0
        elif args.cmd == "goal":
            from .goals import add_goal, load_goals, remove_goal
            from .reporter import DEFAULT_REPORT_ROOT
            out_dir = Path(args.out) if args.out else DEFAULT_REPORT_ROOT
            gp = out_dir / "goals.json"
            if args.goal_cmd == "set":
                g = add_goal(gp, metric=args.metric,
                             direction=args.direction.replace("-", "_"),
                             target=args.target, label=args.label, window_days=args.window)
                print(f"goal set: {g.id} ({g.label})")
            elif args.goal_cmd == "list":
                for g in load_goals(gp):
                    print(f"{g.id}\t{g.label}\t{g.metric} {g.direction} {g.target} / {g.window_days}d")
            elif args.goal_cmd == "rm":
                print("removed" if remove_goal(gp, args.goal_id) else "no such goal")
            return 0
        elif args.cmd == "goals":
            from .goals import load_goals
            from .goal_eval import evaluate_goals
            from .checkin import read_checkins
            from .schema import aggregate_window
            from .reporter import DEFAULT_REPORT_ROOT
            out_dir = Path(args.out) if args.out else DEFAULT_REPORT_ROOT
            goals = load_goals(out_dir / "goals.json")
            if not goals:
                print("no goals declared — use `companion goal set ...`")
                return 0
            span = max(g.window_days for g in goals)
            end = date.fromisoformat(args.end) if args.end else date.today()
            days = [(end - timedelta(days=i)).isoformat() for i in range(span - 1, -1, -1)]
            window = aggregate_window(days, mesh_root=args.mesh_root)
            checkins = read_checkins(out_dir)
            for st in evaluate_goals(window, checkins, goals):
                print(f"{st.goal.id}\t{st.status}\t{st.actual}/{st.target}")
            return 0
        else:  # pragma: no cover — argparse rejects unknown subcommands
            parser.error(f"unknown command: {args.cmd}")
            return 2
    except RuntimeError as exc:
        print(f"phantom-companion: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:  # bad check-in line
        print(f"phantom-companion: {exc}", file=sys.stderr)
        return 1
    print(str(path))
    return 0


def _ingest_days(since: str | None, day: str | None) -> list[str] | None:
    if since:
        start = date.fromisoformat(since)
        end = date.fromisoformat(day) if day else date.today()
        if end < start:
            return []
        n_days = (end - start).days + 1
        return [(start + timedelta(days=i)).isoformat() for i in range(n_days)]
    if day:
        return [day]
    return None


def _record_checkin(line: str, out_root: Path | None = None) -> Path:
    """Append one nightly subjective check-in to a LOCAL-ONLY JSONL store."""
    import json

    from .checkin import parse_checkin_line
    from .reporter import DEFAULT_REPORT_ROOT

    checkin = parse_checkin_line(line)
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "checkins.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(checkin.to_dict(), ensure_ascii=False) + "\n")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
