from pathlib import Path
from phantom_companion.cli import main
from phantom_companion.reporter import write_daily_report


def _set_violated_goal(out: Path):
    # a goal that will be 'violated' with no mesh data: jobs_applied >= 3 over 7d,
    # actual 0 -> violated (sum metric, density met by the 7 aggregated days).
    main(["goal", "set", "jobs_applied", "at-least", "3", "--label", "Apply weekly",
          "--out", str(out)])


def test_daily_report_emits_throttled_nudge_for_violation(tmp_path):
    out = tmp_path
    _set_violated_goal(out)
    # run the daily report twice for the same day
    write_daily_report(day="2026-06-15", out_root=out)
    outbox = out / "outbox"
    first = list(outbox.glob("goal_nudge-*.json"))
    assert len(first) == 1, "a violated goal should emit exactly one nudge"
    write_daily_report(day="2026-06-15", out_root=out)   # same day -> throttled
    second = list(outbox.glob("goal_nudge-*.json"))
    assert len(second) == 1, "same day must not re-nudge (throttled)"


def test_daily_report_no_goals_creates_no_outbox(tmp_path):
    out = tmp_path
    write_daily_report(day="2026-06-15", out_root=out)
    assert not (out / "outbox").exists()
