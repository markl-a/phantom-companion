"""``phantom-companion`` command-line entry point.

Subcommands:
- ``daily-report [--day YYYY-MM-DD] [--out DIR]``
- ``weekly-report [--end YYYY-MM-DD] [--out DIR]``

Default output: ``~/.phantom-mesh/logs/phantom-companion/<date>-report.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .reporter import write_daily_report, write_weekly_report


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "daily-report":
            path = write_daily_report(day=args.day, out_root=args.out, mesh_root=args.mesh_root)
        elif args.cmd == "weekly-report":
            path = write_weekly_report(end_day=args.end, out_root=args.out, mesh_root=args.mesh_root)
        else:  # pragma: no cover — argparse rejects unknown subcommands
            parser.error(f"unknown command: {args.cmd}")
            return 2
    except RuntimeError as exc:
        print(f"phantom-companion: {exc}", file=sys.stderr)
        return 1
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
