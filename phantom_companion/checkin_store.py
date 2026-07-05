"""Real, accumulating nightly check-in store (local-only JSON lines).

This is the persistent backing for the subjective nightly check-in habit
(``checkin.SubjectiveCheckin`` — "每晚 1 行"). Where :mod:`phantom_companion.demo_loop`
writes a *synthetic* seed timeline for open-source demos, this module is the
**real** store: it appends the check-ins a user actually records and reads them
back for reporting.

Design constraints:

- Local-only. No network. The store is a plain JSONL file under the phantom-mesh
  data dir (``~/.phantom-mesh/logs/phantom-companion/checkins.jsonl`` by default),
  the same file the ``companion checkin`` CLI already appends to.
- Honest emptiness. :func:`companion_demo_report` reads the **real** accumulated
  data. When the store is empty it returns an explicit ``"no_data_yet"`` status —
  never fabricated seed numbers. A report that invents data it does not have is a
  trust leak, which this project treats as a hard defect.
- Append-only writes, last-write-wins reads. A later nightly correction for the
  same day overrides the earlier line (delegated to :func:`checkin.read_checkins`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .checkin import SubjectiveCheckin, read_checkins

CHECKIN_FILENAME = "checkins.jsonl"


def default_store_dir() -> Path:
    """Return the default data-dir that holds the real check-in store.

    Kept as a function (not a module constant) so the single source of truth
    for the phantom-companion data root stays in :mod:`reporter`, and so tests
    that redirect ``$HOME`` see the redirected path.
    """
    from .reporter import DEFAULT_REPORT_ROOT

    return DEFAULT_REPORT_ROOT


def _resolve_path(path: str | Path | None) -> Path:
    """Resolve a caller-supplied path to a concrete ``checkins.jsonl`` file.

    ``path`` may be the JSONL file itself, a directory containing it, or ``None``
    (use the default data dir). A path that does not yet exist is treated as a
    directory (the common "point me at an output dir" case).
    """
    if path is None:
        return default_store_dir() / CHECKIN_FILENAME
    p = Path(path)
    if p.is_file():
        return p
    if p.is_dir():
        return p / CHECKIN_FILENAME
    # Non-existent: a bare filename ending in the store name is a file; else a dir.
    if p.name == CHECKIN_FILENAME:
        return p
    return p / CHECKIN_FILENAME


def append_checkin(
    checkin: SubjectiveCheckin, *, path: str | Path | None = None
) -> Path:
    """Append one nightly check-in to the real, accumulating store.

    Creates the parent directory on first use. Returns the JSONL path written.
    This is the single real write path; the ``companion checkin`` CLI delegates
    here so the CLI and programmatic callers share one store format.
    """
    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(checkin.to_dict(), ensure_ascii=False) + "\n")
    return target


def load_checkins(
    *, path: str | Path | None = None
) -> dict[str, SubjectiveCheckin]:
    """Read the real check-in store back into a ``{day: SubjectiveCheckin}`` map.

    Missing store -> empty map (never raises). Last write for a given day wins.
    """
    return read_checkins(_resolve_path(path))


def companion_demo_report(*, path: str | Path | None = None) -> dict[str, Any]:
    """Build a report from the **real** accumulated check-in store.

    Reads whatever the user has actually recorded and summarizes it. When the
    store is empty, returns an honest ``status == "no_data_yet"`` payload with a
    zero count and no fabricated numbers — NOT synthetic seed data.

    The returned ``summary`` line is deliberately descriptive (shame-free): it
    reports what was captured, never grades the user for gaps.
    """
    checkins = load_checkins(path=path)
    store_path = _resolve_path(path)

    if not checkins:
        return {
            "status": "no_data_yet",
            "source": "real_checkin_store",
            "store_path": store_path.as_posix(),
            "count": 0,
            "days": [],
            "first_day": None,
            "last_day": None,
            "averages": None,
            "summary": (
                "No check-ins recorded yet — record one with "
                "`companion checkin '<YYYY-MM-DD> gut=4 mood=3 sleep=7.2'` "
                "and this report will accumulate real data over time."
            ),
        }

    days = sorted(checkins)
    count = len(days)
    gut_avg = sum(checkins[d].gut for d in days) / count
    mood_avg = sum(checkins[d].mood for d in days) / count
    sleep_avg = sum(checkins[d].sleep_hr for d in days) / count

    return {
        "status": "ok",
        "source": "real_checkin_store",
        "store_path": store_path.as_posix(),
        "count": count,
        "days": days,
        "first_day": days[0],
        "last_day": days[-1],
        "averages": {
            "gut": round(gut_avg, 2),
            "mood": round(mood_avg, 2),
            "sleep_hr": round(sleep_avg, 2),
        },
        "summary": (
            f"{count} real check-in(s) recorded from {days[0]} to {days[-1]} — "
            f"average gut {gut_avg:.1f}/5, mood {mood_avg:.1f}/5, "
            f"sleep {sleep_avg:.1f}h."
        ),
    }


__all__ = [
    "CHECKIN_FILENAME",
    "default_store_dir",
    "append_checkin",
    "load_checkins",
    "companion_demo_report",
]
