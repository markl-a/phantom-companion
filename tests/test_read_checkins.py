"""read_checkins — dedicated coverage for its documented guarantees:
last-write-per-day-wins, never-raises on malformed input, dir- and
file-path resolution, and missing-file -> {}.
"""
from __future__ import annotations

import json

from phantom_companion.checkin import read_checkins


def _line(day, mood=3, gut=3, sleep_hr=0.0):
    return json.dumps({"day": day, "gut": gut, "mood": mood, "sleep_hr": sleep_hr})


def test_missing_file_returns_empty_dict(tmp_path):
    assert read_checkins(tmp_path / "absent.jsonl") == {}
    assert read_checkins(tmp_path) == {}  # dir with no checkins.jsonl at all


def test_last_write_per_day_wins(tmp_path):
    p = tmp_path / "checkins.jsonl"
    p.write_text(
        _line("2026-06-27", mood=2) + "\n" + _line("2026-06-27", mood=5) + "\n",
        encoding="utf-8",
    )
    out = read_checkins(p)
    assert out["2026-06-27"].mood == 5


def test_malformed_blank_and_non_dict_lines_are_skipped_without_raising(tmp_path):
    p = tmp_path / "checkins.jsonl"
    p.write_text(
        "\n"                                    # blank line
        "   \n"                                 # whitespace-only line
        "{not json at all\n"                    # malformed JSON
        + json.dumps([1, 2, 3]) + "\n"           # valid JSON, not a dict
        + json.dumps("just a string") + "\n"     # valid JSON, not a dict
        + json.dumps({"gut": 4}) + "\n"          # dict but no 'day' -> day="" -> skipped
        + _line("2026-06-28", mood=4) + "\n",    # the one good line
        encoding="utf-8",
    )
    out = read_checkins(p)
    assert list(out.keys()) == ["2026-06-28"]
    assert out["2026-06-28"].mood == 4


def test_dir_path_and_file_path_both_resolve_to_same_result(tmp_path):
    (tmp_path / "checkins.jsonl").write_text(_line("2026-06-29", mood=1) + "\n", encoding="utf-8")
    via_dir = read_checkins(tmp_path)
    via_file = read_checkins(tmp_path / "checkins.jsonl")
    assert via_dir.keys() == via_file.keys() == {"2026-06-29"}
    assert via_dir["2026-06-29"].mood == via_file["2026-06-29"].mood == 1
