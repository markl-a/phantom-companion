# phantom-companion Goal-Aware Accountability Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn companion from passive analysis into active accountability: declare goals → deterministic, density-gated evaluation against real metrics → shame-free violation nudge + report section.

**Architecture:** Two new modules — `goals.py` (Goal schema + `goals.json` store) and `goal_eval.py` (deterministic evaluator over the existing `AggregateWindow` + check-ins) — plus three integrations: a throttled shame-free nudge via the existing `notify.deliver`, a "🎯 Goal tracking" section in `reporter`, and `goal`/`goals` CLI subcommands. Goal-violation judgment is ALWAYS deterministic (never LLM); AI only phrases.

**Tech Stack:** Python ≥3.10, stdlib only, pytest. Tests live at `tests/` (repo convention). Run: `python -m pytest -q`.

**Spec:** `docs/specs/2026-06-23-goal-aware-accountability-loop-design.md` (owner-locked §8 defaults).

**Verified APIs (use exactly these):**
- `from phantom_companion.schema import AggregateWindow, aggregate_window` — `AggregateWindow.days: list[DayAggregate]`; `DayAggregate(day:str, events:list[NormalizedEvent], health:HealthSample|None, output:OutputSample|None, ...)`; `NormalizedEvent(applied:bool, provider:str, ...)`; `HealthSample(sleep_hr:float, activity_min:int, ...)`; `OutputSample(commits:int, ...)`.
- `from phantom_companion.checkin import read_checkins` — `read_checkins(out_dir: Path) -> dict[str, SubjectiveCheckin]`; `SubjectiveCheckin(day, gut, mood:int, sleep_hr)`.
- `from phantom_companion.reporter import DEFAULT_REPORT_ROOT, shame_free_check` — `DEFAULT_REPORT_ROOT: Path`; `shame_free_check(text:str) -> tuple[bool, ...]` (first element True iff no shame pattern).
- `from phantom_companion.notify import Notification, deliver, LocalSink` — `Notification(kind, title, body="", details={})`; `deliver(notif, config=None, local_sink=None, relay_sink=None)`.
- `from phantom_companion.thresholds import MIN_SAMPLES` (=14; correlation gate — NOT used as the goal density gate; goals use a window-proportional gate defined below).

**Metric vocabulary (grounded in real fields):** `commits` (OutputSample.commits, mean), `activity_min` (HealthSample.activity_min, mean), `sleep_hr` (HealthSample.sleep_hr, mean), `mood` (SubjectiveCheckin.mood, mean), `jobs_applied` (count events `applied=True`, sum), `llm_calls` (count events with non-empty `provider`, sum — companion tracks call counts, not cost). Default windows (spec §8): commits/sleep_hr/activity_min=1, jobs_applied=7, mood=7, llm_calls=30.

**Status semantics (operationalizes spec §8's ~20% margin):**
- `at_least`: `on_track` if actual≥target; `drifting` if 0.8·target≤actual<target; `violated` if actual<0.8·target.
- `at_most`: `on_track` if actual≤target; `drifting` if target<actual≤1.2·target; `violated` if actual>1.2·target.
- `insufficient_data` if observed days < `max(1, ceil(window_days/2))` (the window-proportional density gate).

---

## File Structure
- **Create** `phantom_companion/goals.py` — `Goal`, `DEFAULT_WINDOWS`, `METRICS`, `load_goals`/`save_goals`/`add_goal`/`remove_goal`.
- **Create** `phantom_companion/goal_eval.py` — `GoalStatus`, `has_goal_density`, `evaluate_goals`.
- **Create** `phantom_companion/goal_nudge.py` — `build_goal_nudges`, `should_nudge` (throttle), `emit_goal_nudges`.
- **Modify** `phantom_companion/reporter.py` — `render_goal_section` + wire into daily/weekly builders.
- **Modify** `phantom_companion/cli.py` — `goal set/list/rm` + `goals` subcommands.
- **Create** tests under `tests/`.

---

### Task 1: `goals.py` — Goal schema + JSON store

**Files:** Create `phantom_companion/goals.py`, `tests/test_goals.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goals.py
import pytest
from phantom_companion.goals import (
    Goal, METRICS, DEFAULT_WINDOWS, load_goals, save_goals, add_goal, remove_goal,
)


def test_goal_roundtrips():
    g = Goal(id="move", label="Move daily", metric="activity_min",
             direction="at_least", target=30.0, window_days=1)
    assert Goal.from_dict(g.to_dict()) == g


def test_metric_vocabulary_is_fixed():
    assert set(METRICS) == {
        "commits", "activity_min", "sleep_hr", "mood", "jobs_applied", "llm_calls",
    }


def test_add_uses_default_window_and_slug(tmp_path):
    p = tmp_path / "goals.json"
    g = add_goal(p, metric="jobs_applied", direction="at_least", target=3, label="Apply weekly")
    assert g.window_days == DEFAULT_WINDOWS["jobs_applied"] == 7
    assert g.id and g.id == g.id.lower()
    assert load_goals(p) == [g]


def test_add_rejects_unknown_metric(tmp_path):
    with pytest.raises(ValueError):
        add_goal(tmp_path / "goals.json", metric="vibes", direction="at_least", target=1)


def test_remove_goal(tmp_path):
    p = tmp_path / "goals.json"
    add_goal(p, metric="commits", direction="at_least", target=1, label="Ship")
    g2 = add_goal(p, metric="sleep_hr", direction="at_least", target=7, label="Sleep")
    assert remove_goal(p, g2.id) is True
    assert [g.metric for g in load_goals(p)] == ["commits"]
    assert remove_goal(p, "nope") is False


def test_load_missing_file_is_empty(tmp_path):
    assert load_goals(tmp_path / "absent.json") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_goals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phantom_companion.goals'`

- [ ] **Step 3: Write minimal implementation**

```python
# phantom_companion/goals.py
"""User-declared goals: a metric, a direction, a target, a window. Stored as a
human-readable goals.json. Pure data — evaluation lives in goal_eval.py."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# metric -> default evaluation window in days (spec §8).
DEFAULT_WINDOWS: dict[str, int] = {
    "commits": 1, "activity_min": 1, "sleep_hr": 1,
    "mood": 7, "jobs_applied": 7, "llm_calls": 30,
}
METRICS = tuple(DEFAULT_WINDOWS)
_DIRECTIONS = ("at_least", "at_most")


@dataclass(frozen=True)
class Goal:
    id: str
    label: str
    metric: str
    direction: str
    target: float
    window_days: int

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "metric": self.metric,
            "direction": self.direction, "target": self.target,
            "window_days": self.window_days,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        return cls(
            id=str(d["id"]), label=str(d.get("label", "")),
            metric=str(d["metric"]), direction=str(d["direction"]),
            target=float(d["target"]), window_days=int(d["window_days"]),
        )


def _slug(metric: str, label: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or metric
    return base[:40]


def load_goals(path: Path) -> list[Goal]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Goal.from_dict(d) for d in data]


def save_goals(path: Path, goals: list[Goal]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps([g.to_dict() for g in goals], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_goal(path: Path, metric: str, direction: str, target: float,
             label: str = "", window_days: int | None = None) -> Goal:
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; known: {', '.join(METRICS)}")
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}")
    goals = load_goals(path)
    label = label or f"{metric} {direction} {target}"
    gid = _slug(metric, label)
    # de-dupe id
    existing = {g.id for g in goals}
    suffix = 2
    base = gid
    while gid in existing:
        gid = f"{base}-{suffix}"
        suffix += 1
    goal = Goal(
        id=gid, label=label, metric=metric, direction=direction,
        target=float(target),
        window_days=window_days if window_days is not None else DEFAULT_WINDOWS[metric],
    )
    goals.append(goal)
    save_goals(path, goals)
    return goal


def remove_goal(path: Path, goal_id: str) -> bool:
    goals = load_goals(path)
    kept = [g for g in goals if g.id != goal_id]
    if len(kept) == len(goals):
        return False
    save_goals(path, kept)
    return True


__all__ = [
    "Goal", "METRICS", "DEFAULT_WINDOWS",
    "load_goals", "save_goals", "add_goal", "remove_goal",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_goals.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add phantom_companion/goals.py tests/test_goals.py
git commit -m "feat(goals): goal schema + human-readable goals.json store"
```

---

### Task 2: `goal_eval.py` — deterministic, density-gated evaluation

**Files:** Create `phantom_companion/goal_eval.py`, `tests/test_goal_eval.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goal_eval.py
import math
from phantom_companion.schema import (
    AggregateWindow, DayAggregate, HealthSample, OutputSample, NormalizedEvent,
)
from phantom_companion.checkin import SubjectiveCheckin
from phantom_companion.goals import Goal
from phantom_companion.goal_eval import evaluate_goals, has_goal_density


def _day(day, commits=None, activity=None, sleep=None, applied=0, providers=0):
    events = []
    for i in range(applied):
        events.append(NormalizedEvent(event_id=f"a{i}", day=day, applied=True))
    for i in range(providers):
        events.append(NormalizedEvent(event_id=f"p{i}", day=day, provider="codex"))
    return DayAggregate(
        day=day, events=events,
        health=HealthSample(day=day, activity_min=activity or 0, sleep_hr=sleep or 0.0)
        if (activity is not None or sleep is not None) else None,
        output=OutputSample(day=day, commits=commits) if commits is not None else None,
    )


def test_density_gate_is_window_proportional():
    assert has_goal_density(observed=1, window_days=1) is True
    assert has_goal_density(observed=3, window_days=7) is False   # need ceil(7/2)=4
    assert has_goal_density(observed=4, window_days=7) is True


def test_at_least_violation_when_well_below():
    win = AggregateWindow(days=[_day("2026-06-01", activity=5)])
    g = Goal(id="move", label="Move", metric="activity_min",
             direction="at_least", target=30, window_days=1)
    [st] = evaluate_goals(win, {}, [g])
    assert st.status == "violated" and st.actual == 5 and st.target == 30


def test_at_least_drifting_within_margin():
    win = AggregateWindow(days=[_day("2026-06-01", activity=27)])  # 27 >= 0.8*30=24, <30
    g = Goal(id="m", label="", metric="activity_min", direction="at_least", target=30, window_days=1)
    assert evaluate_goals(win, {}, [g])[0].status == "drifting"


def test_at_least_on_track():
    win = AggregateWindow(days=[_day("2026-06-01", commits=3)])
    g = Goal(id="ship", label="", metric="commits", direction="at_least", target=1, window_days=1)
    assert evaluate_goals(win, {}, [g])[0].status == "on_track"


def test_sum_metric_jobs_applied_over_week():
    days = [_day(f"2026-06-0{i}", applied=1) for i in range(1, 6)]  # 5 days, 5 applications
    win = AggregateWindow(days=days)
    g = Goal(id="apply", label="", metric="jobs_applied", direction="at_least",
             target=3, window_days=7)
    [st] = evaluate_goals(win, {}, [g])
    assert st.actual == 5 and st.status == "on_track"


def test_at_most_llm_calls_violation():
    days = [_day(f"2026-06-{i:02d}", providers=10) for i in range(1, 21)]  # 200 calls
    win = AggregateWindow(days=days)
    g = Goal(id="ai", label="", metric="llm_calls", direction="at_most",
             target=100, window_days=30)
    [st] = evaluate_goals(win, {}, [g])
    assert st.actual == 200 and st.status == "violated"


def test_mood_uses_checkins_and_insufficient_data():
    win = AggregateWindow(days=[_day(f"2026-06-0{i}") for i in range(1, 8)])
    checkins = {"2026-06-01": SubjectiveCheckin(day="2026-06-01", mood=4)}  # only 1 day
    g = Goal(id="mood", label="", metric="mood", direction="at_least",
             target=4, window_days=7)
    [st] = evaluate_goals(win, checkins, [g])
    assert st.status == "insufficient_data"   # need ceil(7/2)=4 observed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_goal_eval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phantom_companion.goal_eval'`

- [ ] **Step 3: Write minimal implementation**

```python
# phantom_companion/goal_eval.py
"""Deterministic, density-gated evaluation of goals against an AggregateWindow.

NEVER uses an LLM: whether a goal is violated is pure arithmetic. A goal is only
judged when enough of its window has observed data (window-proportional gate),
otherwise it is `insufficient_data` and raises no nudge."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .goals import Goal
from .schema import AggregateWindow

# metrics whose window value is a SUM of per-day counts (vs a MEAN of per-day values).
_SUM_METRICS = {"jobs_applied", "llm_calls"}


@dataclass(frozen=True)
class GoalStatus:
    goal: Goal
    status: str          # on_track | drifting | violated | insufficient_data
    actual: float
    target: float
    observed_days: int

    @property
    def gap(self) -> float:
        return self.actual - self.target


def has_goal_density(observed: int, window_days: int) -> bool:
    """Window-proportional density gate: need data for at least half the window."""
    return observed >= max(1, math.ceil(window_days / 2))


def _per_day(window: AggregateWindow, metric: str, checkins_by_day: dict):
    """Yield this metric's observed per-day values. For SUM metrics every day is an
    observation (count, possibly 0); for MEAN metrics only days with the underlying
    record are observed."""
    for d in window.days:
        if metric == "commits":
            if d.output is not None:
                yield d.output.commits
        elif metric == "activity_min":
            if d.health is not None:
                yield d.health.activity_min
        elif metric == "sleep_hr":
            if d.health is not None:
                yield d.health.sleep_hr
        elif metric == "mood":
            c = checkins_by_day.get(d.day)
            if c is not None:
                yield c.mood
        elif metric == "jobs_applied":
            yield sum(1 for e in d.events if e.applied)
        elif metric == "llm_calls":
            yield sum(1 for e in d.events if e.provider)


def _status_for(direction: str, actual: float, target: float) -> str:
    if direction == "at_least":
        if actual >= target:
            return "on_track"
        return "drifting" if actual >= 0.8 * target else "violated"
    # at_most
    if actual <= target:
        return "on_track"
    return "drifting" if actual <= 1.2 * target else "violated"


def evaluate_goals(window: AggregateWindow, checkins_by_day: dict,
                   goals: list[Goal]) -> list[GoalStatus]:
    out: list[GoalStatus] = []
    for g in goals:
        values = list(_per_day(window, g.metric, checkins_by_day))
        observed = len(values)
        if not has_goal_density(observed, g.window_days):
            out.append(GoalStatus(g, "insufficient_data", 0.0, g.target, observed))
            continue
        actual = float(sum(values)) if g.metric in _SUM_METRICS else (sum(values) / observed)
        out.append(GoalStatus(g, _status_for(g.direction, actual, g.target),
                              round(actual, 3), g.target, observed))
    return out


__all__ = ["GoalStatus", "has_goal_density", "evaluate_goals"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_goal_eval.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add phantom_companion/goal_eval.py tests/test_goal_eval.py
git commit -m "feat(goal_eval): deterministic density-gated goal evaluation"
```

---

### Task 3: `goal_nudge.py` — throttled shame-free violation nudges

**Files:** Create `phantom_companion/goal_nudge.py`, `tests/test_goal_nudge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goal_nudge.py
from phantom_companion.goals import Goal
from phantom_companion.goal_eval import GoalStatus
from phantom_companion.goal_nudge import build_goal_nudges, should_nudge, emit_goal_nudges
from phantom_companion.reporter import shame_free_check


def _status(status):
    g = Goal(id="move", label="Move daily", metric="activity_min",
             direction="at_least", target=30, window_days=1)
    return GoalStatus(g, status, actual=5, target=30, observed_days=1)


def test_only_violated_become_nudges():
    statuses = [_status("violated"), _status("on_track"), _status("drifting"),
                _status("insufficient_data")]
    nudges = build_goal_nudges(statuses, window_key="2026-06-01")
    assert len(nudges) == 1 and nudges[0].kind == "goal_nudge"


def test_nudge_body_is_shame_free():
    n = build_goal_nudges([_status("violated")], window_key="2026-06-01")[0]
    ok, _ = shame_free_check(n.body)
    assert ok, f"nudge body tripped shame lint: {n.body!r}"


def test_throttle_one_per_goal_per_window(tmp_path):
    state = tmp_path / "nudge_state.jsonl"
    assert should_nudge("move", "2026-06-01", state) is True
    # record + re-check
    emit_goal_nudges([_status("violated")], window_key="2026-06-01",
                     outbox=tmp_path / "outbox", state_path=state)
    assert should_nudge("move", "2026-06-01", state) is False      # same window: throttled
    assert should_nudge("move", "2026-06-02", state) is True       # new window: allowed


def test_emit_writes_local_outbox(tmp_path):
    outbox = tmp_path / "outbox"
    emitted = emit_goal_nudges([_status("violated")], window_key="2026-06-01",
                               outbox=outbox, state_path=tmp_path / "s.jsonl")
    assert emitted == 1
    assert list(outbox.glob("goal_nudge-*.json"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_goal_nudge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'phantom_companion.goal_nudge'`

- [ ] **Step 3: Write minimal implementation**

```python
# phantom_companion/goal_nudge.py
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
    # Supportive, never-blame phrasing. Kept deterministic and lint-clean.
    body = (f"Heads-up on “{label}”: you're at {st.actual} vs a target of "
            f"{st.target}. A small step back toward it today is enough.")
    ok, _ = shame_free_check(body)
    if ok:
        return body
    return f"Worth a gentle nudge on “{label}” today."  # safe fallback


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
        deliver(notif, local_sink=sink)   # local-only: relay stays opt-in elsewhere
        _record(gid, window_key, state_path)
        emitted += 1
    return emitted


__all__ = ["build_goal_nudges", "should_nudge", "emit_goal_nudges"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_goal_nudge.py -v`
Expected: PASS (4 passed). If `shame_free_check` is not importable at module level from `reporter`, locate its definition and import accordingly (do NOT weaken the test) — report the actual location.

- [ ] **Step 5: Commit**

```bash
git add phantom_companion/goal_nudge.py tests/test_goal_nudge.py
git commit -m "feat(goal_nudge): throttled shame-free goal-violation nudges"
```

---

### Task 4: Report integration — "🎯 Goal tracking" section

**Files:** Modify `phantom_companion/reporter.py`; Create `tests/test_goal_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goal_report.py
from phantom_companion.goals import Goal
from phantom_companion.goal_eval import GoalStatus
from phantom_companion.reporter import render_goal_section, shame_free_check


def _st(status, label="Move daily", metric="activity_min"):
    g = Goal(id="m", label=label, metric=metric, direction="at_least",
             target=30, window_days=1)
    return GoalStatus(g, status, actual=5, target=30, observed_days=1)


def test_section_lists_each_goal_with_status_marker():
    lines = render_goal_section([_st("on_track"), _st("violated", label="Sleep 7h")])
    text = "\n".join(lines)
    assert "## 🎯 Goal tracking" in text
    assert "Move daily" in text and "Sleep 7h" in text


def test_section_is_shame_free():
    lines = render_goal_section([_st("violated"), _st("drifting")])
    ok, _ = shame_free_check("\n".join(lines))
    assert ok


def test_empty_goals_returns_no_section():
    assert render_goal_section([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_goal_report.py -v`
Expected: FAIL — `cannot import name 'render_goal_section'`.

- [ ] **Step 3: Write the implementation (append to `reporter.py`)**

```python
# --- goal tracking section (append near the other section builders) ---
_GOAL_MARKERS = {
    "on_track": "✅ on track",
    "drifting": "➰ drifting",
    "violated": "🌱 worth a nudge",
    "insufficient_data": "… still gathering data",
}


def render_goal_section(statuses) -> list:
    """Render a shame-free '🎯 Goal tracking' section from GoalStatus list.

    Empty list -> no section (returns []). Phrasing is supportive: a missed goal
    reads as 'worth a nudge', never as failure."""
    if not statuses:
        return []
    lines = ["## 🎯 Goal tracking", ""]
    for st in statuses:
        label = st.goal.label or st.goal.metric
        marker = _GOAL_MARKERS.get(st.status, st.status)
        if st.status == "insufficient_data":
            lines.append(f"- **{label}** — {marker}.")
        else:
            lines.append(
                f"- **{label}** — {marker} ({st.actual} vs target {st.target})."
            )
    lines.append("")
    return lines
```

Then wire it into the daily and weekly report builders. In `write_daily_report` (and `write_weekly_report`), after the insights/coach sections are appended and before the report is written, load goals + checkins, evaluate, and extend `lines`:

```python
    # goal tracking (deterministic; no-op when no goals declared)
    from .goals import load_goals
    from .goal_eval import evaluate_goals
    from .checkin import read_checkins
    out_dir = DEFAULT_REPORT_ROOT if out_root is None else Path(out_root)
    goals = load_goals(out_dir / "goals.json")
    if goals:
        checkins_by_day = read_checkins(out_dir)
        lines.extend(render_goal_section(evaluate_goals(window, checkins_by_day, goals)))
```

Use the `window`/`out_root` variables already in scope in each builder (the daily builder builds a 1-day window; the weekly builder already has a 7-day `window`). For the daily builder, build the 1-day window via the existing `aggregate_window([day], ...)` if a window object is not already in scope — match the file's existing pattern. Keep the rest of each builder unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_goal_report.py -v`
Then the whole suite: `python -m pytest -q`
Expected: new tests pass; all pre-existing reporter tests still pass.

- [ ] **Step 5: Commit**

```bash
git add phantom_companion/reporter.py tests/test_goal_report.py
git commit -m "feat(reporter): shame-free goal-tracking section in daily/weekly reports"
```

---

### Task 5: CLI — `goal set/list/rm` + `goals` status

**Files:** Modify `phantom_companion/cli.py`; Create `tests/test_goal_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goal_cli.py
from phantom_companion.cli import main
from phantom_companion.goals import load_goals


def test_goal_set_persists(tmp_path, capsys):
    out = tmp_path
    rc = main(["goal", "set", "activity_min", "at-least", "30",
               "--label", "Move daily", "--out", str(out)])
    assert rc == 0
    goals = load_goals(out / "goals.json")
    assert len(goals) == 1 and goals[0].metric == "activity_min"


def test_goal_list_and_rm(tmp_path, capsys):
    out = tmp_path
    main(["goal", "set", "commits", "at-least", "1", "--label", "Ship", "--out", str(out)])
    main(["goal", "list", "--out", str(out)])
    listed = capsys.readouterr().out
    assert "Ship" in listed
    gid = load_goals(out / "goals.json")[0].id
    assert main(["goal", "rm", gid, "--out", str(out)]) == 0
    assert load_goals(out / "goals.json") == []


def test_goals_status_runs(tmp_path):
    out = tmp_path
    main(["goal", "set", "commits", "at-least", "1", "--label", "Ship", "--out", str(out)])
    # no mesh data -> insufficient_data, but the command must succeed (rc 0)
    assert main(["goals", "--out", str(out)]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_goal_cli.py -v`
Expected: FAIL — argparse rejects the `goal`/`goals` subcommands.

- [ ] **Step 3: Write the implementation (modify `cli.py`)**

In `_build_parser`, add after the existing subparsers (use `at-least`/`at-most` on the CLI, mapped to the underscore form):

```python
    goal = sub.add_parser("goal", help="Manage accountability goals.")
    goal_sub = goal.add_subparsers(dest="goal_cmd", required=True)
    g_set = goal_sub.add_parser("set", help="Declare or update a goal.")
    g_set.add_argument("metric", choices=("commits", "activity_min", "sleep_hr",
                                          "mood", "jobs_applied", "llm_calls"))
    g_set.add_argument("direction", choices=("at-least", "at-most"))
    g_set.add_argument("target", type=float)
    g_set.add_argument("--label", default="")
    g_set.add_argument("--window", type=int, default=None, help="Override default window (days).")
    g_set.add_argument("--out", type=Path, default=None)
    g_list = goal_sub.add_parser("list", help="List declared goals.")
    g_list.add_argument("--out", type=Path, default=None)
    g_rm = goal_sub.add_parser("rm", help="Remove a goal by id.")
    g_rm.add_argument("goal_id")
    g_rm.add_argument("--out", type=Path, default=None)

    goals_cmd = sub.add_parser("goals", help="Show current goal status.")
    goals_cmd.add_argument("--end", default=None, help="Last day of the eval window (ISO).")
    goals_cmd.add_argument("--out", type=Path, default=None)
```

In `main`, add branches (place before the final `else`). `mesh_root` is `args.mesh_root`:

```python
        elif args.cmd == "goal":
            from .goals import add_goal, load_goals, remove_goal
            from .reporter import DEFAULT_REPORT_ROOT
            out_dir = Path(args.out) if args.out else DEFAULT_REPORT_ROOT
            gp = out_dir / "goals.json"
            if args.goal_cmd == "set":
                g = add_goal(gp, metric=args.metric,
                             direction=args.direction.replace("-", "_"),
                             target=args.target, label=args.label, window_days=args.window)
                print(f"goal set: {g.id} ({g.label})")
            elif args.goal_cmd == "list":
                for g in load_goals(gp):
                    print(f"{g.id}\t{g.label}\t{g.metric} {g.direction} {g.target} / {g.window_days}d")
            elif args.goal_cmd == "rm":
                print("removed" if remove_goal(gp, args.goal_id) else "no such goal")
            return 0
        elif args.cmd == "goals":
            from datetime import date, timedelta
            from .goals import load_goals
            from .goal_eval import evaluate_goals
            from .checkin import read_checkins
            from .schema import aggregate_window
            from .reporter import DEFAULT_REPORT_ROOT
            out_dir = Path(args.out) if args.out else DEFAULT_REPORT_ROOT
            goals = load_goals(out_dir / "goals.json")
            if not goals:
                print("no goals declared — use `companion goal set ...`")
                return 0
            span = max(g.window_days for g in goals)
            end = date.fromisoformat(args.end) if args.end else date.today()
            days = [(end - timedelta(days=i)).isoformat() for i in range(span - 1, -1, -1)]
            window = aggregate_window(days, mesh_root=args.mesh_root)
            checkins = read_checkins(out_dir)
            for st in evaluate_goals(window, checkins, goals):
                print(f"{st.goal.id}\t{st.status}\t{st.actual}/{st.target}")
            return 0
```

(The `goal` subcommand has no `path` final-print; it `return 0` directly, like `ingest-output`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_goal_cli.py -v`
Then: `python -m pytest -q`
Expected: new tests pass; all pre-existing CLI tests still pass.

- [ ] **Step 5: Commit**

```bash
git add phantom_companion/cli.py tests/test_goal_cli.py
git commit -m "feat(cli): goal set/list/rm + goals status subcommands"
```

---

### Task 6: Full-suite verification + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pre-existing tests (131+) PLUS the new goal tests, 0 failed.

- [ ] **Step 2: Manual smoke (offline, deterministic)**

```bash
TMP=$(python -c "import tempfile;print(tempfile.mkdtemp())")
python -m phantom_companion goal set activity_min at-least 30 --label "Move daily" --out "$TMP"
python -m phantom_companion goal set jobs_applied at-least 3 --label "Apply weekly" --out "$TMP"
python -m phantom_companion goal list --out "$TMP"
python -m phantom_companion goals --out "$TMP"
```
Expected: two goals listed; `goals` prints each goal's status (likely `insufficient_data` with no mesh history) and exits 0 — never crashes, never an LLM call.

- [ ] **Step 3: Done**

If green, the goal-aware accountability loop is complete (the vision's closed loop). Deferred per spec §9: monetization packaging (C pack → A hosted subscription → B commitment-device), owned-memory personalization — each its own plan, only after real-data signal.

---

## Self-Review

**Spec coverage (spec §3/§4/§2):**
- §4 goal schema + goals.json → `goals.py` (Task 1) ✅
- §4 deterministic, density-gated eval with the 4 states, mapping to real fields → `goal_eval.py` (Task 2) ✅
- §4 shame-free violation nudge via existing `notify`, throttled (one per goal per window) → `goal_nudge.py` (Task 3) ✅
- §4 "🎯 目標追蹤" report section in daily/weekly → `reporter.render_goal_section` (Task 4) ✅
- §4 CLI `goal set/list/rm` + `goals` → `cli.py` (Task 5) ✅
- §2 red lines: goal judgment deterministic (no LLM in goals/goal_eval/goal_nudge — only arithmetic + shame lint), density-gated (`has_goal_density`), shame-free (lint on nudge body + report lines), local-first (LocalSink default; relay untouched/opt-in), offline (no network) ✅
- §8 locked defaults: drifting 20% margin (`_status_for`), throttle one-per-goal-per-window (`should_nudge`), mood as a goal metric (in `METRICS`), default windows (`DEFAULT_WINDOWS`) ✅

**Grounding deviation (intentional, flagged):** spec §4 listed `llm_cost`; companion only tracks call *counts* (`analyze_llm_usage` tallies calls, no cost field), so the plan uses `llm_calls` — honest to the data. Spec metric list otherwise matches real schema fields.

**Placeholder scan:** none — every step has runnable code + exact commands. The two reporter-builder wiring points (Task 4 Step 3) reference the in-scope `window`/`out_root` variables and instruct matching the file's existing pattern rather than guessing line numbers.

**Type consistency:** `Goal` (Task 1) consumed by `goal_eval` (Task 2), `goal_nudge` (Task 3), `reporter` (Task 4), `cli` (Task 5). `GoalStatus` (Task 2) consumed by Tasks 3–5. `evaluate_goals(window, checkins_by_day, goals)` signature identical across report wiring (Task 4) and CLI (Task 5). CLI `at-least`/`at-most` → `_` mapped before `add_goal` (which expects `at_least`/`at_most` per Task 1).
