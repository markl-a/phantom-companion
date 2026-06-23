"""Turn `violated` goal statuses into throttled, shame-free local notifications.

Throttle: at most one nudge per (goal_id, window_key). A nudge whose body would
trip the shame-free lint is replaced by a deterministic safe template — the
reporter's never-shame invariant applies here too."""
from __future__ import annotations

import json
from pathlib import Path

from .goal_eval import GoalStatus
from .notify import LocalSink, Notification, deliver
from .reporter import shame_free_check


def _safe_body(st: GoalStatus) -> str:
    label = st.goal.label or st.goal.metric
    body = (f"Heads-up on “{label}”: you're at {st.actual} vs a target of "
            f"{st.target}. A small step back toward it today is enough.")
    ok, _ = shame_free_check(body)
    if ok:
        return body
    return f"Worth a gentle nudge on “{label}” today."


def build_goal_nudges(statuses: list[GoalStatus], window_key: str) -> list[Notification]:
    nudges: list[Notification] = []
    for st in statuses:
        if st.status != "violated":
            continue
        nudges.append(Notification(
            kind="goal_nudge",
            title=f"Goal nudge: {st.goal.label or st.goal.metric}",
            body=_safe_body(st),
            details={"goal_id": st.goal.id, "metric": st.goal.metric,
                     "actual": st.actual, "target": st.target, "window_key": window_key},
        ))
    return nudges


def should_nudge(goal_id: str, window_key: str, state_path: Path) -> bool:
    p = Path(state_path)
    if not p.exists():
        return True
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("goal_id") == goal_id and rec.get("window_key") == window_key:
            return False
    return True


def _record(goal_id: str, window_key: str, state_path: Path) -> None:
    p = Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"goal_id": goal_id, "window_key": window_key}) + "\n")


def emit_goal_nudges(statuses: list[GoalStatus], window_key: str,
                     outbox: Path, state_path: Path) -> int:
    """Deliver one local nudge per newly-violated goal; throttle via state_path."""
    sink = LocalSink(outbox)
    emitted = 0
    for notif in build_goal_nudges(statuses, window_key):
        gid = notif.details["goal_id"]
        if not should_nudge(gid, window_key, state_path):
            continue
        deliver(notif, local_sink=sink)
        _record(gid, window_key, state_path)
        emitted += 1
    return emitted


__all__ = ["build_goal_nudges", "should_nudge", "emit_goal_nudges"]
