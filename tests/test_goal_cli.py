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
    assert main(["goals", "--out", str(out)]) == 0
