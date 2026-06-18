"""End-to-end: subjective(mood) × objective(commits) correlation via the REAL trends CLI.

The cross-domain keystone. These tests do NOT call correlate_subjective_output
directly (that is the unit test, and calling the fn directly is exactly how the
'mood never correlated' gap hid). Instead they write output-<day>.json (commits)
per day, record a nightly mood that rises WITH commits through the real checkin
CLI, drive the real trends CLI, and assert the rendered '## Mood × output'
section carries a real Pearson r with a 'positive' direction once n >= MIN_SAMPLES
— plus a no-checkin CONTROL where the section is ABSENT.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from phantom_companion.cli import main
from phantom_companion.reporter import shame_free_check


def _write_output_sample(mesh_root: Path, day: str, commits: int) -> None:
    d = mesh_root / 'logs' / 'phantom-companion'
    d.mkdir(parents=True, exist_ok=True)
    (d / f'output-{day}.json').write_text(
        json.dumps({'commits': commits, 'lines_changed': commits * 30}),
        encoding='utf-8',
    )


def _days_ending(end: str, n: int) -> list[str]:
    e = date.fromisoformat(end)
    return [(e - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def test_trends_cli_emits_mood_output_correlation_from_real_checkins(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mesh = tmp_path / 'mesh'
    out = tmp_path / 'out'
    end = '2026-05-30'
    days = _days_ending(end, 30)
    for i, day in enumerate(days):
        _write_output_sample(mesh, day, commits=i)
        rc = main(['checkin', f'{day} gut=4 mood={1 + i // 6} sleep=7.{i % 10}', '--out', str(out)])
        assert rc == 0
        capsys.readouterr()

    rc = main(['--mesh-root', str(mesh), 'trends', '--period', 'monthly',
               '--end', end, '--out', str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding='utf-8')

    assert '## Mood × output' in body
    assert '30 days observed' in body
    assert 'association r=' in body
    assert 'positive' in body
    assert 'Spearman' in body
    low = body.lower()
    for word in ('causes', 'because of', 'due to', 'leads to'):
        assert word not in low, f'causation leaked: {word!r}'
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_trends_cli_without_checkins_omits_mood_output_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mesh = tmp_path / 'mesh'
    out = tmp_path / 'out'
    end = '2026-05-30'
    for i, day in enumerate(_days_ending(end, 30)):
        _write_output_sample(mesh, day, commits=i)

    rc = main(['--mesh-root', str(mesh), 'trends', '--period', 'monthly',
               '--end', end, '--out', str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding='utf-8')
    assert '## Mood × output' not in body
    ok, reason = shame_free_check(body)
    assert ok, reason
