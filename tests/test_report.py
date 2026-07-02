"""Offline tests for report aggregation and markdown rendering (no API key)."""

from comp_evals import results
from comp_evals.models import AXES, AxisScore, Grade
from comp_evals.report import build_report, render_markdown


def _grade(scenario_id: str, model: str, score: int) -> Grade:
    scores = [AxisScore(axis=a, score=score, justification=f"{a} note") for a in AXES]
    return Grade(scenario_id=scenario_id, model=model, scores=scores)


def _seed_run(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "RESULTS_ROOT", tmp_path)
    d = results.ensure_run_dir("run_20260702_145643")
    # claude does well; gpt does poorly on the leveling scenario (a "failed trap").
    results.append_grade(d, _grade("s01_leveling_boundary", "claude", 3))
    results.append_grade(d, _grade("s01_leveling_boundary", "gpt", 0))
    results.append_grade(d, _grade("s05_negotiation_gap", "claude", 3))
    results.append_grade(d, _grade("s05_negotiation_gap", "gpt", 2))
    results.write_raw(d, "s01_leveling_boundary", "gpt", "I would place her at L6 based on her Staff title. That is the right call.")
    return d


def test_build_report_aggregates(tmp_path, monkeypatch) -> None:
    d = _seed_run(tmp_path, monkeypatch)
    rep = build_report(d)

    assert set(rep.models) == {"claude", "gpt"}
    assert rep.grade_count == 4
    assert rep.scenario_count == 2
    # claude 3s -> total 12; gpt on s01 is 0, on s05 is 8 -> mean 4.0
    assert rep.per_model_overall["claude"] == 12.0
    assert rep.per_model_overall["gpt"] == 4.0
    assert rep.per_model_axis["claude"]["accuracy"] == 3.0
    # header reproducibility fields
    assert rep.judge_prompt_version
    assert rep.run_date == "2026-07-02 14:56:43"


def test_failed_trap_picks_worst_scenario(tmp_path, monkeypatch) -> None:
    d = _seed_run(tmp_path, monkeypatch)
    rep = build_report(d)
    # s01 (cross-model mean (12+0)/2 = 6) is worse than s05 ((12+8)/2 = 10).
    worst = rep.failed_traps[0]
    assert worst.scenario.id == "s01_leveling_boundary"
    assert worst.worst_model == "gpt"
    assert worst.worst_total == 0
    assert "L6" in worst.excerpt  # excerpt pulled from the raw response


def test_render_markdown_has_all_sections(tmp_path, monkeypatch) -> None:
    d = _seed_run(tmp_path, monkeypatch)
    md = render_markdown(build_report(d))
    assert "# comp-evals results" in md
    assert "## Leaderboard" in md
    assert "## Per-axis mean" in md
    assert "## Per-category mean total" in md
    assert "## Most-failed traps" in md
    assert "JUDGE_PROMPT_V1" in md  # judge version in header
    assert "2026-07-02" in md  # run date in header
