"""P3-M2 — nightly subjective check-in (the spec's "每晚 1 行").

Each night the user records one short line — gut 1-5, mood 1-5, and sleep hours.
It is a local-only subjective complement to the sensor/event streams: where ④
gives objective vitals, this captures how the day *felt*, which the monthly /
quarterly trend views fold in.

Two input forms are accepted so the nightly habit stays frictionless:

- key=value: ``2026-05-22 gut=4 mood=3 sleep=7.2``
- terse CSV: ``2026-05-22, 4, 3, 7.2`` (date, gut, mood, sleep)

Parsing is forgiving by design: out-of-range 1-5 scores are *clamped*, never
rejected — a tracker that scolds you for "wrong" input is itself a shame leak.
The only hard error is a missing date (a check-in must be placeable in time).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_GUT = re.compile(r"gut\s*=\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_MOOD = re.compile(r"mood\s*=\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_SLEEP = re.compile(r"sleep\s*=\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


class CheckinParseError(ValueError):
    """Raised when a check-in line carries no placeable date."""


def _clamp_scale(value: float) -> int:
    """Clamp a 1-5 subjective score into range (never reject)."""
    return max(1, min(5, int(round(value))))


@dataclass(frozen=True)
class SubjectiveCheckin:
    day: str
    gut: int = 3
    mood: int = 3
    sleep_hr: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "gut": self.gut,
            "mood": self.mood,
            "sleep_hr": self.sleep_hr,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SubjectiveCheckin":
        return cls(
            day=str(d.get("day", "")),
            gut=int(d.get("gut", 3)),
            mood=int(d.get("mood", 3)),
            sleep_hr=float(d.get("sleep_hr", 0.0)),
        )


def parse_checkin_line(line: str) -> SubjectiveCheckin:
    """Parse one nightly check-in line into a :class:`SubjectiveCheckin`."""
    text = (line or "").strip()
    m = _DATE.search(text)
    if not m:
        raise CheckinParseError("check-in line is missing a YYYY-MM-DD date")
    day = m.group(1)

    gut_m = _GUT.search(text)
    mood_m = _MOOD.search(text)
    sleep_m = _SLEEP.search(text)

    if gut_m or mood_m or sleep_m:
        gut = _clamp_scale(float(gut_m.group(1))) if gut_m else 3
        mood = _clamp_scale(float(mood_m.group(1))) if mood_m else 3
        sleep_hr = float(sleep_m.group(1)) if sleep_m else 0.0
        return SubjectiveCheckin(day=day, gut=gut, mood=mood, sleep_hr=sleep_hr)

    # Terse CSV fallback: date, gut, mood, sleep.
    rest = text.replace(day, "", 1)
    nums = re.findall(r"-?\d+(?:\.\d+)?", rest)
    gut = _clamp_scale(float(nums[0])) if len(nums) >= 1 else 3
    mood = _clamp_scale(float(nums[1])) if len(nums) >= 2 else 3
    sleep_hr = float(nums[2]) if len(nums) >= 3 else 0.0
    return SubjectiveCheckin(day=day, gut=gut, mood=mood, sleep_hr=sleep_hr)


def read_checkins(path: str | Path) -> dict[str, "SubjectiveCheckin"]:
    """Read the local-only nightly check-in store (checkins.jsonl) back into a
    {day: SubjectiveCheckin} map. path may be the checkins.jsonl file itself
    or the directory containing it. Last write for a given day wins (a later
    nightly correction overrides an earlier line). Missing file -> empty map.
    Blank lines and malformed JSON lines are skipped (best-effort, never raises).
    """
    import json

    p = Path(path)
    if p.is_dir():
        p = p / "checkins.jsonl"
    if not p.exists():
        return {}

    out: dict[str, SubjectiveCheckin] = {}
    try:
        with p.open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                try:
                    c = SubjectiveCheckin.from_dict(obj)
                except (TypeError, ValueError):
                    continue
                if not c.day:
                    continue
                out[c.day] = c
    except (OSError, ValueError):
        # OSError = unreadable file; ValueError covers a UnicodeDecodeError from a
        # corrupt byte during line iteration — keep this best-effort/never-raises.
        return out
    return out


__all__ = [
    "SubjectiveCheckin",
    "CheckinParseError",
    "parse_checkin_line",
    "read_checkins",
]
