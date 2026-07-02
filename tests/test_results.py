"""Offline tests for run persistence + resume logic (no API key required)."""

from comp_evals import results
from comp_evals.models import AXES, AxisScore, Grade


def _grade(scenario_id: str, model: str) -> Grade:
    scores = [AxisScore(axis=a, score=2, justification="x") for a in AXES]
    return Grade(scenario_id=scenario_id, model=model, scores=scores)


def test_append_and_completed_pairs_roundtrip(tmp_path, monkeypatch) -> None:
    # Point the results root at a temp dir so we don't touch the real results/.
    monkeypatch.setattr(results, "RESULTS_ROOT", tmp_path)

    d = results.ensure_run_dir("run_test")
    assert results.completed_pairs(d) == set()

    results.append_grade(d, _grade("s01_leveling_boundary", "claude"))
    results.append_grade(d, _grade("s02_manager_to_ic", "gpt"))

    pairs = results.completed_pairs(d)
    assert pairs == {("s01_leveling_boundary", "claude"), ("s02_manager_to_ic", "gpt")}

    # Resume semantics: an already-graded pair is reported done, an ungraded one isn't.
    assert ("s01_leveling_boundary", "claude") in pairs
    assert ("s01_leveling_boundary", "gpt") not in pairs

    loaded = results.load_grades(d)
    assert len(loaded) == 2
    assert {g.total for g in loaded} == {8}


def test_write_raw_persists_response(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(results, "RESULTS_ROOT", tmp_path)
    d = results.ensure_run_dir("run_test")
    results.write_raw(d, "s01_leveling_boundary", "claude", "the answer")
    assert (d / "raw" / "s01_leveling_boundary__claude.txt").read_text() == "the answer"


def test_latest_run_dir_picks_most_recent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(results, "RESULTS_ROOT", tmp_path)
    results.ensure_run_dir("run_20260101_000000")
    results.ensure_run_dir("run_20260102_000000")
    assert results.latest_run_dir().name == "run_20260102_000000"
