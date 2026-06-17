"""P3-M1 — local-only by default; off-device relay is opt-in + consent-gated +
payload-minimized.

The companion's delivery is local-first. A notification is written to a local
sink unless the user has *explicitly* opted in to an off-device relay AND the
specific payload clears a consent gate. Even then, only a minimised payload
(coarse signal, no raw sensitive values, no PII) leaves the device.

This is a BIG-GOAL privacy invariant for ⑦: behavioural data is paranoia-grade
sensitive, so the default must be that nothing leaves the device, and the relay
path must be impossible to trip accidentally.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.notify import (
    LocalSink,
    Notification,
    NotifyConfig,
    RelayConsentError,
    RelaySink,
    deliver,
    minimize_payload,
)


def _notif() -> Notification:
    return Notification(
        kind="weekly_digest",
        title="Weekly review ready",
        body="Captured 26 events across 7 days.",
        # Fields a naive impl might leak off-device:
        details={
            "companies": ["Garmin", "Anthropic", "南亞科"],
            "sleep_hr": 5.8,
            "resting_hr": 71,
            "commit_messages": ["fix the GraphQL bug at 00:32"],
            "event_summaries": ["applied to Garmin embedded role"],
        },
    )


# ---------------------------------------------------------------------------
# default = local-only
# ---------------------------------------------------------------------------

def test_default_config_is_local_only() -> None:
    cfg = NotifyConfig()
    assert cfg.relay_enabled is False
    assert cfg.consent_granted is False


def test_deliver_default_writes_local_sink_only(tmp_path: Path) -> None:
    sink = LocalSink(tmp_path / "outbox")
    result = deliver(_notif(), config=NotifyConfig(), local_sink=sink)
    assert result.delivered_local is True
    assert result.relayed is False
    # The local sink got the FULL notification (on-device is allowed full data).
    files = list((tmp_path / "outbox").glob("*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text(encoding="utf-8"))
    assert written["title"] == "Weekly review ready"


def test_deliver_does_not_relay_when_relay_disabled(tmp_path: Path) -> None:
    sent: list[dict] = []
    relay = RelaySink(send=lambda payload: sent.append(payload))
    cfg = NotifyConfig(relay_enabled=False, consent_granted=True)
    result = deliver(
        _notif(), config=cfg, local_sink=LocalSink(tmp_path / "o"), relay_sink=relay
    )
    assert result.relayed is False
    assert sent == [], "nothing may leave the device when relay is disabled"


# ---------------------------------------------------------------------------
# consent gate
# ---------------------------------------------------------------------------

def test_relay_requires_consent_even_if_enabled(tmp_path: Path) -> None:
    sent: list[dict] = []
    relay = RelaySink(send=lambda payload: sent.append(payload))
    # relay_enabled but consent NOT granted -> must refuse, not silently send.
    cfg = NotifyConfig(relay_enabled=True, consent_granted=False)
    with pytest.raises(RelayConsentError):
        deliver(_notif(), config=cfg, local_sink=LocalSink(tmp_path / "o"), relay_sink=relay)
    assert sent == [], "no payload may leave the device without consent"


def test_relay_sends_only_when_enabled_and_consented(tmp_path: Path) -> None:
    sent: list[dict] = []
    relay = RelaySink(send=lambda payload: sent.append(payload))
    cfg = NotifyConfig(relay_enabled=True, consent_granted=True)
    result = deliver(
        _notif(), config=cfg, local_sink=LocalSink(tmp_path / "o"), relay_sink=relay
    )
    assert result.delivered_local is True
    assert result.relayed is True
    assert len(sent) == 1


# ---------------------------------------------------------------------------
# payload minimisation / no-PII
# ---------------------------------------------------------------------------

_PII_NEEDLES = (
    "Garmin",
    "Anthropic",
    "南亞科",
    "5.8",
    "71",
    "GraphQL",
    "applied to Garmin",
    "00:32",
)


def test_minimize_strips_all_pii() -> None:
    minimal = minimize_payload(_notif())
    blob = json.dumps(minimal, ensure_ascii=False)
    for needle in _PII_NEEDLES:
        assert needle not in blob, f"PII leaked into relay payload: {needle!r}"
    # It still carries a non-identifying signal: kind + a coarse flag.
    assert minimal["kind"] == "weekly_digest"
    # raw details dict must be gone entirely.
    assert "details" not in minimal
    assert "companies" not in blob and "commit_messages" not in blob


def test_relayed_payload_is_the_minimized_one(tmp_path: Path) -> None:
    sent: list[dict] = []
    relay = RelaySink(send=lambda payload: sent.append(payload))
    cfg = NotifyConfig(relay_enabled=True, consent_granted=True)
    deliver(_notif(), config=cfg, local_sink=LocalSink(tmp_path / "o"), relay_sink=relay)
    blob = json.dumps(sent[0], ensure_ascii=False)
    for needle in _PII_NEEDLES:
        assert needle not in blob, f"PII reached the relay: {needle!r}"
    # And the body text that did go is itself shame-free.
    from phantom_companion.reporter import shame_free_check

    ok, reason = shame_free_check(json.dumps(sent[0], ensure_ascii=False))
    assert ok, reason


def test_minimize_coarsens_unknown_kind_to_block_pii_in_kind() -> None:
    # `kind` is free-form; a bad caller must not smuggle PII out through it.
    n = Notification(kind="applied to Garmin role; sleep 4.1h", title="t", body="b")
    minimal = minimize_payload(n)
    blob = json.dumps(minimal, ensure_ascii=False)
    assert "Garmin" not in blob and "4.1" not in blob
    assert minimal["kind"] == "update", "unknown kind must be coarsened"


def test_minimize_payload_drops_freeform_body() -> None:
    # The free-form body may itself contain specifics; the minimiser must not
    # forward it verbatim — only a fixed, non-identifying notice.
    n = Notification(kind="anomaly", title="t", body="sleep was 4.1h, very low", details={})
    minimal = minimize_payload(n)
    blob = json.dumps(minimal, ensure_ascii=False)
    assert "4.1" not in blob
    assert "sleep was" not in blob
