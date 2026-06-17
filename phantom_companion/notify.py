"""P3-M1 — local-first notification delivery with an opt-in, consent-gated,
payload-minimised off-device relay.

Delivery model (a BIG-GOAL privacy invariant for ⑦):

1. **Local sink is the default and always runs.** A notification is written to
   an on-device outbox. On-device data is the user's own, so the local sink
   receives the *full* notification.
2. **Off-device relay is opt-in.** Nothing leaves the device unless the user has
   explicitly set ``relay_enabled`` in :class:`NotifyConfig`.
3. **And consent-gated.** Even with the relay enabled, each send is gated on an
   explicit ``consent_granted`` flag; a missing consent raises
   :class:`RelayConsentError` rather than silently sending — so the relay can
   never be tripped by a default or a config typo.
4. **And payload-minimised.** What actually crosses the device boundary is the
   output of :func:`minimize_payload`: a coarse, non-identifying signal. Raw
   health values, company names, commit messages, event summaries, and the
   free-form body are all dropped — only the ``kind`` and a fixed, neutral
   notice survive.

The relay transport itself is injected (``RelaySink(send=...)``) so this module
never touches the network; a real deployment wires in the consent-gated Phantom
Relay client.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class RelayConsentError(PermissionError):
    """Raised when an off-device relay is attempted without granted consent."""


@dataclass
class Notification:
    """One thing the companion wants to tell the user.

    ``details`` may hold rich, *sensitive* on-device data (health numbers,
    company names, commit text). That dict is for the local sink only and is
    never forwarded off-device — :func:`minimize_payload` discards it.
    """

    kind: str
    title: str
    body: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class NotifyConfig:
    """Delivery policy. Defaults are the privacy-safe ones: local only."""

    relay_enabled: bool = False
    consent_granted: bool = False


@dataclass
class DeliveryResult:
    delivered_local: bool = False
    relayed: bool = False


class LocalSink:
    """Default on-device sink: writes the full notification to a local outbox."""

    def __init__(self, outbox: Path | str) -> None:
        self.outbox = Path(outbox)

    def write(self, notif: Notification) -> Path:
        self.outbox.mkdir(parents=True, exist_ok=True)
        path = self.outbox / f"{notif.kind}-{uuid.uuid4().hex[:8]}.json"
        path.write_text(
            json.dumps(notif.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


class RelaySink:
    """Off-device relay. The transport is injected, never built here.

    ``send`` is any callable taking the *already minimised* payload dict. Tests
    pass a list-appender; production passes the consent-gated Relay client.
    """

    def __init__(self, send: Callable[[dict[str, Any]], None]) -> None:
        self._send = send

    def send(self, minimal_payload: dict[str, Any]) -> None:
        self._send(minimal_payload)


# A fixed, non-identifying notice per notification kind. The user's device shows
# the rich version locally; what crosses the boundary is only "there is a new X".
_RELAY_NOTICES: dict[str, str] = {
    "weekly_digest": "Your weekly review is ready on your device.",
    "daily_report": "Your daily report is ready on your device.",
    "anomaly": "Something in your recent data is worth a glance on your device.",
}
_DEFAULT_NOTICE = "There is a new companion update on your device."


def minimize_payload(notif: Notification) -> dict[str, Any]:
    """Reduce a notification to the minimal, non-identifying signal safe to relay.

    Keeps only the ``kind`` and a fixed neutral notice. Drops ``details``
    entirely and replaces the free-form ``body`` (which may itself contain
    specifics) with the canned notice. The result carries enough to nudge the
    user to open the app, and nothing that identifies *what* happened.
    """
    return {
        "kind": notif.kind,
        "notice": _RELAY_NOTICES.get(notif.kind, _DEFAULT_NOTICE),
        # An explicit marker so a downstream auditor can confirm minimisation ran.
        "minimized": True,
    }


def deliver(
    notif: Notification,
    config: NotifyConfig | None = None,
    local_sink: LocalSink | None = None,
    relay_sink: RelaySink | None = None,
) -> DeliveryResult:
    """Deliver ``notif`` local-first, relaying only when opted-in + consented.

    Raises :class:`RelayConsentError` if the relay is enabled but consent has not
    been granted — failing closed is the whole point.
    """
    config = config or NotifyConfig()
    result = DeliveryResult()

    if local_sink is not None:
        local_sink.write(notif)
        result.delivered_local = True

    if not config.relay_enabled:
        return result  # local-only: nothing leaves the device.

    if not config.consent_granted:
        # Enabled but not consented -> refuse loudly; never send.
        raise RelayConsentError(
            "off-device relay is enabled but consent has not been granted; "
            "refusing to send"
        )

    if relay_sink is not None:
        relay_sink.send(minimize_payload(notif))
        result.relayed = True

    return result


__all__ = [
    "Notification",
    "NotifyConfig",
    "DeliveryResult",
    "LocalSink",
    "RelaySink",
    "RelayConsentError",
    "minimize_payload",
    "deliver",
]
