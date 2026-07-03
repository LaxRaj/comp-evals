"""Offline tests for report aggregation and markdown rendering (no API key)."""

from comp_evals import results
from comp_evals.models import AXES, AxisScore, Grade
from comp_evals.report import build_report, render_markdown, render_site


def _grade(scenario_id: str, model: str, judge: str, score: int) -> Grade:
    scores = [AxisScore(axis=a, score=score, justification=f"{a} note") for a in AXES]
    return Grade(scenario_id=scenario_id, model=model, judge=judge, scores=scores)


def _seed_run(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "RESULTS_ROOT", tmp_path)
    d = results.ensure_run_dir("run_20260702_145643")
    # Two judges. Both rank claude above gpt (agreement), gpt weak on the leveling case.
    for judge in ("claude", "gpt"):
        results.append_grade(d, _grade("s01_leveling_boundary", "claude", judge, 3))
        results.append_grade(d, _grade("s01_leveling_boundary", "gpt", judge, 0))
        results.append_grade(d, _grade("s05_negotiation_gap", "claude", judge, 3))
        results.append_grade(d, _grade("s05_negotiation_gap", "gpt", judge, 2))
    results.write_raw(
        d, "s01_leveling_boundary", "gpt",
        "I would place her at L6 based on her Staff title. That is the right call.",
    )
    return d


def test_build_report_aggregates(tmp_path, monkeypatch) -> None:
    rep = build_report(_seed_run(tmp_path, monkeypatch))
    assert set(rep.models) == {"claude", "gpt"}
    assert set(rep.judges) == {"claude", "gpt"}
    assert rep.grade_count == 8
    assert rep.scenario_count == 2
    assert rep.per_model_overall["claude"] == 12.0  # all 3s
    assert rep.per_model_overall["gpt"] == 4.0  # (0*4 + 8*4)/8 across scenarios -> mean 4
    assert rep.run_date == "2026-07-02 14:56:43"


def test_separation_and_judge_agreement(tmp_path, monkeypatch) -> None:
    rep = build_report(_seed_run(tmp_path, monkeypatch))
    assert rep.separation == 8.0  # 12.0 (claude) - 4.0 (gpt)
    assert "agree" in rep.judge_agreement  # both judges rank claude > gpt
    assert rep.per_judge_overall["claude"]["claude"] == 12.0
    assert rep.per_judge_overall["gpt"]["gpt"] == 4.0


def test_failed_trap_picks_worst_scenario(tmp_path, monkeypatch) -> None:
    rep = build_report(_seed_run(tmp_path, monkeypatch))
    worst = rep.failed_traps[0]
    assert worst.scenario.id == "s01_leveling_boundary"  # mean 6 < s05 mean 10
    assert worst.worst_model == "gpt"
    assert "L6" in worst.excerpt


def test_render_markdown_has_all_sections(tmp_path, monkeypatch) -> None:
    md = render_markdown(build_report(_seed_run(tmp_path, monkeypatch)))
    for section in (
        "# comp-evals results",
        "## Leaderboard",
        "## Per-judge leaderboard",
        "## Per-axis mean",
        "## Per-category mean total",
        "## Most-failed traps",
        "Model separation",
        "Judge agreement",
    ):
        assert section in md, f"missing section: {section}"
    assert "JUDGE_PROMPT_V1" in md
    assert "2026-07-02" in md


def test_render_site_has_front_matter_and_link(tmp_path, monkeypatch) -> None:
    site = render_site(build_report(_seed_run(tmp_path, monkeypatch)))
    assert site.startswith("---\n")  # Jekyll front matter
    assert "title: comp-evals results" in site
    assert "github.com/LaxRaj/comp-evals" in site  # link back to the repo
    # leading H1 dropped (theme banner shows the title instead), tables retained
    assert not site.lstrip("-\n").startswith("# comp-evals results")
    assert "## Leaderboard" in site
