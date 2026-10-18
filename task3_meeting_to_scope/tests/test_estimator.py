import json
from pathlib import Path

from src.estimator import aggregate, build_tasks_from_fixtures

FIX = Path(__file__).parent / "fixtures" / "estimate_fixtures.json"


def test_totals_match_fixture_sums():
    fix = json.loads(FIX.read_text(encoding="utf-8"))
    ids = list(fix.keys())
    tasks = build_tasks_from_fixtures(ids, FIX)
    totals = aggregate(tasks)
    assert totals.low_hours == sum(r["low"] for rows in fix.values() for r in rows)
    assert totals.likely_hours == sum(r["likely"] for rows in fix.values() for r in rows)
    assert totals.high_hours == sum(r["high"] for rows in fix.values() for r in rows)


def test_by_task_and_by_requirement_split():
    ids = list(json.loads(FIX.read_text(encoding="utf-8")).keys())
    totals = aggregate(build_tasks_from_fixtures(ids, FIX))
    assert "testing" in totals.by_task
    assert totals.by_task["testing"]["low"] > 0
    for rid in ids:
        assert rid in totals.by_requirement


def test_all_estimates_start_provisional():
    ids = list(json.loads(FIX.read_text(encoding="utf-8")).keys())
    tasks = build_tasks_from_fixtures(ids, FIX)
    assert all(t.reviewer_status == "provisional_unreviewed" for t in tasks)


def test_deterministic():
    ids = list(json.loads(FIX.read_text(encoding="utf-8")).keys())
    a = aggregate(build_tasks_from_fixtures(ids, FIX))
    b = aggregate(build_tasks_from_fixtures(ids, FIX))
    assert a.low_hours == b.low_hours and a.likely_hours == b.likely_hours and a.high_hours == b.high_hours
