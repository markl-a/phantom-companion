from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.fixtures import build_mesh_fixture, fixture_days
from phantom_companion.notify import NotifyConfig, RelayConsentError, RelaySink
from phantom_companion.reporter import (
    write_anomaly_alerts,
    write_daily_report,
    write_weekly_report,
)
from phantom_companion.schema import aggregate_window
from phantom_companion.thresholds import MIN_SAMPLES


class CapturingSink:
    def __init__(self) -> None:
        self.notifications = []

    def write(self, notif) -> None:
        self.notifications.append(notif)


def test_daily_report_delivers_to_local_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    sink = CapturingSink()
    relayed = []
    path = write_daily_report(
        day="2026-06-01",
        out_root=tmp_path,
        mesh_root=tmp_path / "mesh",
        local_sink=sink,
        relay_sink=RelaySink(send=relayed.append),
    )

    assert path.exists()
    assert len(sink.notifications) == 1
    assert sink.notifications[0].kind == "daily_report"
    assert relayed == []


def test_weekly_report_delivers_to_local_sink(tmp_path: Path) -> None:
    sink = CapturingSink()
    path = write_weekly_report(
        end_day="2026-06-01",
        out_root=tmp_path,
        mesh_root=tmp_path / "mesh",
        local_sink=sink,
    )

    assert path.exists()
    assert len(sink.notifications) == 1
    assert sink.notifications[0].kind == "weekly_digest"


def test_relay_fires_only_on_optin_and_consent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    sink = CapturingSink()
    relayed = []
    write_daily_report(
        day="2026-06-01",
        out_root=tmp_path,
        mesh_root=tmp_path / "mesh",
        notify_config=NotifyConfig(relay_enabled=True, consent_granted=True),
        local_sink=sink,
        relay_sink=RelaySink(send=relayed.append),
    )

    assert len(relayed) == 1
    payload = relayed[0]
    assert payload["minimized"] is True
    assert "report_path" not in payload
    assert "details" not in payload
    assert "body" not in payload

    with pytest.raises(RelayConsentError):
        write_daily_report(
            day="2026-06-02",
            out_root=tmp_path,
            mesh_root=tmp_path / "mesh",
            notify_config=NotifyConfig(relay_enabled=True, consent_granted=False),
            local_sink=CapturingSink(),
            relay_sink=RelaySink(send=relayed.append),
        )


def test_anomaly_path_delivers_to_local_sink(tmp_path: Path) -> None:
    root = tmp_path / "mesh"
    end_day = "2026-06-03"
    build_mesh_fixture(root, end_day=end_day, n_days=MIN_SAMPLES + 6, seed=42)
    days = fixture_days(end_day, MIN_SAMPLES + 6)

    for i in range(80):
        event_dir = root / "events" / f"{end_day}-spike-{i:02d}"
        event_dir.mkdir(parents=True, exist_ok=True)
        (event_dir / "meta.json").write_text(
            json.dumps(
                {
                    "timestamp": f"{end_day}T12:{i % 60:02d}:00Z",
                    "tags": ["attention"],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (event_dir / "analysis.json").write_text(
            json.dumps({"task_kind": "attention"}, sort_keys=True),
            encoding="utf-8",
        )

    window = aggregate_window(days, mesh_root=root)
    sink = CapturingSink()
    path = write_anomaly_alerts(
        window,
        metric="attention",
        out_root=tmp_path,
        local_sink=sink,
    )

    assert path.exists()
    assert len(sink.notifications) == 1
    assert sink.notifications[0].kind == "anomaly"
    assert sink.notifications[0].details["alert_count"] >= 1
