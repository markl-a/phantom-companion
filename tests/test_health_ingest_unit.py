"""Focused unit coverage for ``phantom_companion.health_ingest`` helpers.

The end-to-end suites (``test_ingest_health_e2e`` / ``test_health_output_wiring``)
drive the *happy path* of the ④ secure-connector ingest through the CLI. This
module pins the documented *contracts of the individual functions* — the
total-parsing guarantees, the coercion rules, and the best-effort "skip, never
raise" disk readers — so a regression in any single helper is caught directly
instead of only as a downstream e2e symptom.

Everything here is offline and deterministic: no network, no decryption, no git.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.health_ingest import (
    HealthExportError,
    ingest_health,
    parse_export_stream,
    parse_secure_connector_export,
    read_health_window,
    read_output_window,
    write_health_samples,
)
from phantom_companion.schema import HealthSample


# ---------------------------------------------------------------------------
# parse_secure_connector_export — coercion + total-parsing contract
# ---------------------------------------------------------------------------

def test_parse_export_rejects_non_dict() -> None:
    # The docstring promises a JSON object; a list/str/None must raise, not crash
    # later with an AttributeError.
    for bad in ([], "not a dict", 42, None):
        with pytest.raises(HealthExportError):
            parse_secure_connector_export(bad)  # type: ignore[arg-type]


def test_parse_export_resting_hr_rounds_from_string_float() -> None:
    # _as_int tolerates "52.0" and rounds "51.6" -> 52 (round-half-to-even on .5
    # is fine; we assert a non-half value to stay deterministic).
    s = parse_secure_connector_export(
        {"day": "2026-05-22", "resting_hr": "51.6", "activity_min": "40.0"}
    )
    assert s.resting_hr == 52
    assert s.activity_min == 40


def test_parse_export_garbage_numbers_fall_back_to_defaults() -> None:
    # Unparseable numerics degrade to documented defaults rather than raising.
    s = parse_secure_connector_export(
        {"day": "2026-05-22", "sleep_hr": "n/a", "hrv_ms": "??", "resting_hr": "x"}
    )
    assert s.sleep_hr == 0.0
    assert s.hrv_ms == 0.0
    assert s.resting_hr == 0


def test_parse_export_first_present_alias_wins() -> None:
    # Both snake_case and camelCase present: the first key in the alias tuple wins
    # (sleep_hr precedes sleepHours), proving deterministic alias resolution.
    s = parse_secure_connector_export(
        {"day": "2026-05-22", "sleep_hr": 7.0, "sleepHours": 9.9}
    )
    assert s.sleep_hr == 7.0


def test_parse_export_empty_day_string_is_rejected() -> None:
    # A falsy day ("" / 0) cannot be placed in the window.
    with pytest.raises(HealthExportError):
        parse_secure_connector_export({"day": "", "sleep_hr": 6.0})


# ---------------------------------------------------------------------------
# parse_export_stream — skip-malformed, last-write-wins
# ---------------------------------------------------------------------------

def test_parse_stream_skips_rows_without_day() -> None:
    rows = [
        {"day": "2026-05-20", "sleep_hr": 6.0},
        {"sleep_hr": 7.0},  # no day -> skipped, not fatal
        {"date": "2026-05-21", "sleep_hr": 8.0},
    ]
    out = parse_export_stream(rows)
    assert set(out) == {"2026-05-20", "2026-05-21"}
    assert out["2026-05-21"].sleep_hr == 8.0


def test_parse_stream_last_row_wins_on_duplicate_day() -> None:
    rows = [
        {"day": "2026-05-20", "sleep_hr": 6.0},
        {"day": "2026-05-20", "sleep_hr": 7.5},
    ]
    out = parse_export_stream(rows)
    assert len(out) == 1
    assert out["2026-05-20"].sleep_hr == 7.5


# ---------------------------------------------------------------------------
# read_health_window — best-effort disk reader (skip, never raise)
# ---------------------------------------------------------------------------

def _write_health_file(mesh: Path, day: str, payload: object) -> Path:
    d = mesh / "logs" / "phantom-secure-connector"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"health-{day}.json"
    p.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )
    return p


def test_read_health_window_skips_missing_days(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    _write_health_file(mesh, "2026-05-20", {"sleep_hr": 7.0, "source": "garmin"})
    out = read_health_window(mesh, ["2026-05-19", "2026-05-20", "2026-05-21"])
    assert set(out) == {"2026-05-20"}
    # Returned dict is the normalized HealthSample shape WITHOUT a redundant day key.
    assert "day" not in out["2026-05-20"]
    assert out["2026-05-20"]["sleep_hr"] == 7.0


def test_read_health_window_skips_corrupt_and_non_dict_json(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    _write_health_file(mesh, "2026-05-20", "{ not json ::")
    _write_health_file(mesh, "2026-05-21", [1, 2, 3])  # valid JSON, wrong type
    _write_health_file(mesh, "2026-05-22", {"sleep_hr": 6.5})
    out = read_health_window(mesh, ["2026-05-20", "2026-05-21", "2026-05-22"])
    # Only the well-formed dict day survives; the reader never raises.
    assert set(out) == {"2026-05-22"}


def test_read_health_window_injects_day_when_file_omits_it(tmp_path: Path) -> None:
    # The on-disk file has no 'day' field; the reader injects the requested day so
    # parse does not reject it. Accepts the file purely on filename-derived date.
    mesh = tmp_path / "mesh"
    _write_health_file(mesh, "2026-05-22", {"sleep_hr": 8.1, "source": "apple_health"})
    out = read_health_window(mesh, ["2026-05-22"])
    assert out["2026-05-22"]["sleep_hr"] == 8.1
    assert out["2026-05-22"]["source"] == "apple_health"


def test_read_health_window_empty_for_nonexistent_root(tmp_path: Path) -> None:
    out = read_health_window(tmp_path / "nope", ["2026-05-22"])
    assert out == {}


# ---------------------------------------------------------------------------
# read_output_window — coercion + best-effort skip
# ---------------------------------------------------------------------------

def _write_output_file(mesh: Path, day: str, payload: object) -> Path:
    d = mesh / "logs" / "phantom-companion"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"output-{day}.json"
    p.write_text(
        payload if isinstance(payload, str) else json.dumps(payload),
        encoding="utf-8",
    )
    return p


def test_read_output_window_coerces_bad_values_to_zero(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    _write_output_file(mesh, "2026-05-22", {"commits": "oops", "lines_changed": None})
    out = read_output_window(mesh, ["2026-05-22"])
    assert out == {"2026-05-22": {"commits": 0, "lines_changed": 0}}


def test_read_output_window_defaults_missing_keys(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    _write_output_file(mesh, "2026-05-22", {"commits": 3})  # no lines_changed
    out = read_output_window(mesh, ["2026-05-22"])
    assert out == {"2026-05-22": {"commits": 3, "lines_changed": 0}}


def test_read_output_window_skips_corrupt_and_non_dict(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    _write_output_file(mesh, "2026-05-20", "}{ broken")
    _write_output_file(mesh, "2026-05-21", "[1,2]")
    _write_output_file(mesh, "2026-05-22", {"commits": 2, "lines_changed": 60})
    out = read_output_window(mesh, ["2026-05-20", "2026-05-21", "2026-05-22"])
    assert set(out) == {"2026-05-22"}
    assert out["2026-05-22"] == {"commits": 2, "lines_changed": 60}


# ---------------------------------------------------------------------------
# write_health_samples — overwrite flag + round-trip through read_health_window
# ---------------------------------------------------------------------------

def test_write_then_read_round_trips(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    samples = {
        "2026-05-22": HealthSample(
            day="2026-05-22", sleep_hr=7.4, hrv_ms=56.0, resting_hr=54,
            activity_min=41, source="garmin",
        ),
    }
    written = write_health_samples(mesh, samples)
    assert len(written) == 1 and written[0].exists()
    back = read_health_window(mesh, ["2026-05-22"])
    assert back["2026-05-22"]["sleep_hr"] == 7.4
    assert back["2026-05-22"]["resting_hr"] == 54
    assert back["2026-05-22"]["source"] == "garmin"


def test_write_health_samples_overwrite_false_preserves_existing(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    first = {"2026-05-22": HealthSample(day="2026-05-22", sleep_hr=6.0)}
    write_health_samples(mesh, first)
    # overwrite=False must NOT clobber the existing file, and must report it skipped.
    second = {"2026-05-22": HealthSample(day="2026-05-22", sleep_hr=9.0)}
    written = write_health_samples(mesh, second, overwrite=False)
    assert written == []
    back = read_health_window(mesh, ["2026-05-22"])
    assert back["2026-05-22"]["sleep_hr"] == 6.0  # original preserved


# ---------------------------------------------------------------------------
# ingest_health — top-level dispatch (single dict / list / invalid)
# ---------------------------------------------------------------------------

def test_ingest_health_single_object_file(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    export = tmp_path / "one.json"
    export.write_text(json.dumps({"day": "2026-05-22", "sleep_hr": 7.0}), encoding="utf-8")
    written = ingest_health(export, mesh)
    assert [p.name for p in written] == ["health-2026-05-22.json"]


def test_ingest_health_rejects_scalar_top_level(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh"
    export = tmp_path / "bad.json"
    export.write_text(json.dumps(42), encoding="utf-8")  # neither dict nor list
    with pytest.raises(HealthExportError):
        ingest_health(export, mesh)
