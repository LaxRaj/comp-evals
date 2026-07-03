"""Report: aggregate a run's grades into a per-model leaderboard.

Computes per-model overall means (pooled across judges and repeats), per-axis
and per-category means, a model-separation statistic, per-judge leaderboards and
a judge-agreement read (so a Claude-judges-Claude objection can be checked
against a second judge), and the scenarios models did worst on. Renders both a
RESULTS.md file and a rich terminal view.

Pure aggregation lives in `build_report`; rendering is separate so it can be
tested offline on a synthetic run dir.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from comp_evals.grader import JUDGE_PROMPT_VERSION
from comp_evals.loader import load_all_scenarios
from comp_evals.models import AXES, Grade, Scenario
from comp_evals.results import load_grades

TOP_FAILED = 3


@dataclass
class FailedTrap:
    scenario: Scenario
    cross_model_mean: float
    worst_model: str
    worst_total: float
    accuracy_justification: str
    excerpt: str


@dataclass
class Report:
    run_id: str
    run_date: str
    judge_prompt_version: str
    models: list[str]
    judges: list[str]
    scenario_count: int
    grade_count: int
    per_model_overall: dict[str, float]  # model -> mean total (0-12), pooled over judges
    per_model_axis: dict[str, dict[str, float]]  # model -> axis -> mean (0-3)
    per_model_category: dict[str, dict[str, float]]  # model -> category -> mean total
    per_judge_overall: dict[str, dict[str, float]]  # judge -> model -> mean total
    categories: list[str]
    separation: float  # top model mean minus bottom model mean (0-12)
    judge_agreement: str  # human-readable agreement read
    failed_traps: list[FailedTrap] = field(default_factory=list)


def _run_date(run_path: Path) -> str:
    name = run_path.name
    if name.startswith("run_"):
        try:
            return datetime.strptime(name[4:], "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    grades = run_path / "grades.jsonl"
    if grades.exists():
        return datetime.fromtimestamp(grades.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return "unknown"


def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 2) if values else 0.0


def _excerpt(text: str, max_chars: int = 300) -> str:
    """First ~2 sentences of a response, collapsed to one line and truncated."""
    flat = " ".join(text.split())
    if not flat:
        return "(no response captured)"
    sentences: list[str] = []
    buf = ""
    for ch in flat:
        buf += ch
        if ch in ".!?" and len(buf) > 20:
            sentences.append(buf.strip())
            if len(sentences) >= 2:
                break
            buf = ""
    excerpt = " ".join(sentences) if sentences else flat
    return excerpt[: max_chars - 1] + "…" if len(excerpt) > max_chars else excerpt


def _ranking(overall: dict[str, float]) -> list[str]:
    return sorted(overall, key=lambda m: overall[m], reverse=True)


def _judge_agreement(per_judge_overall: dict[str, dict[str, float]]) -> str:
    judges = list(per_judge_overall)
    if len(judges) < 2:
        return "single judge — no cross-check (add a second judge for agreement)"
    rankings = {j: _ranking(per_judge_overall[j]) for j in judges}
    orders = {tuple(r) for r in rankings.values()}
    tops = {r[0] for r in rankings.values() if r}
    if len(orders) == 1:
        return f"judges agree — identical ranking ({' > '.join(next(iter(orders)))})"
    if len(tops) == 1:
        return f"judges agree on #1 (`{next(iter(tops))}`) but differ on lower ranks"
    return "judges disagree on #1 — ranking is judge-dependent, read with caution"


def build_report(run_path: Path) -> Report:
    grades = load_grades(run_path)
    scenarios_by_id: dict[str, Scenario] = {s.id: s for s in load_all_scenarios()}

    models = sorted({g.model for g in grades})
    judges = sorted({g.judge for g in grades})
    categories = sorted({s.category for s in scenarios_by_id.values()})

    per_model_overall: dict[str, float] = {}
    per_model_axis: dict[str, dict[str, float]] = {}
    per_model_category: dict[str, dict[str, float]] = {}
    for model in models:
        mg = [g for g in grades if g.model == model]
        per_model_overall[model] = _mean([g.total for g in mg])
        per_model_axis[model] = {
            axis: _mean([s.score for g in mg for s in g.scores if s.axis == axis]) for axis in AXES
        }
        per_model_category[model] = {}
        for cat in categories:
            totals = [
                g.total
                for g in mg
                if (sc := scenarios_by_id.get(g.scenario_id)) is not None and sc.category == cat
            ]
            if totals:
                per_model_category[model][cat] = _mean(totals)

    per_judge_overall: dict[str, dict[str, float]] = {}
    for judge in judges:
        per_judge_overall[judge] = {
            model: _mean([g.total for g in grades if g.judge == judge and g.model == model])
            for model in models
            if any(g.judge == judge and g.model == model for g in grades)
        }

    overalls = list(per_model_overall.values())
    separation = round(max(overalls) - min(overalls), 2) if len(overalls) >= 2 else 0.0
    judge_agreement = _judge_agreement(per_judge_overall)

    # Most-failed traps: scenarios with the lowest cross-model mean total (pooled).
    scenario_means = {
        sid: _mean([g.total for g in grades if g.scenario_id == sid])
        for sid in {g.scenario_id for g in grades}
    }
    worst_ids = sorted(scenario_means, key=lambda sid: (scenario_means[sid], sid))[:TOP_FAILED]
    failed_traps: list[FailedTrap] = []
    for sid in worst_ids:
        scenario = scenarios_by_id.get(sid)
        if scenario is None:
            continue
        sid_grades = [g for g in grades if g.scenario_id == sid]
        # Worst model = lowest mean total across its grades on this scenario.
        model_means = {
            m: _mean([g.total for g in sid_grades if g.model == m])
            for m in {g.model for g in sid_grades}
        }
        worst_model = min(model_means, key=lambda m: model_means[m])
        worst = min(
            (g for g in sid_grades if g.model == worst_model), key=lambda g: g.total
        )
        acc = next((s.justification for s in worst.scores if s.axis == "accuracy"), "")
        raw_path = run_path / "raw" / f"{sid}__{worst_model}.txt"
        raw = raw_path.read_text() if raw_path.exists() else ""
        failed_traps.append(
            FailedTrap(
                scenario=scenario,
                cross_model_mean=scenario_means[sid],
                worst_model=worst_model,
                worst_total=model_means[worst_model],
                accuracy_justification=acc,
                excerpt=_excerpt(raw),
            )
        )

    return Report(
        run_id=run_path.name,
        run_date=_run_date(run_path),
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        models=models,
        judges=judges,
        scenario_count=len({g.scenario_id for g in grades}),
        grade_count=len(grades),
        per_model_overall=per_model_overall,
        per_model_axis=per_model_axis,
        per_model_category=per_model_category,
        per_judge_overall=per_judge_overall,
        categories=categories,
        separation=separation,
        judge_agreement=judge_agreement,
        failed_traps=failed_traps,
    )


def render_markdown(report: Report) -> str:
    ranked = _ranking(report.per_model_overall)
    L: list[str] = []
    L.append("# comp-evals results")
    L.append("")
    L.append(
        "> Open-source eval scoring frontier models on **synthetic** compensation-reasoning "
        "scenarios, judged by an LLM on four axes (accuracy, completeness, assumptions, "
        "usability). Axes are inspired by Compa's public Evals page; this is not a claim "
        "about their internal methodology."
    )
    L.append("")
    L.append(f"- **Run:** `{report.run_id}`  ·  **Date:** {report.run_date}")
    L.append(
        f"- **Judges:** {', '.join(f'`{j}`' for j in report.judges)} "
        f"({report.judge_prompt_version}) — LLM-as-judge, not human experts (a documented "
        "limitation). Grading is blind to which model wrote each answer."
    )
    L.append(
        f"- **Models:** {', '.join(f'`{m}`' for m in ranked)}  ·  "
        f"**Scenarios:** {report.scenario_count}  ·  **Grades:** {report.grade_count}"
    )
    L.append(
        f"- **Model separation:** {report.separation:.2f} points (top − bottom, 0–12)  ·  "
        f"**Judge agreement:** {report.judge_agreement}"
    )
    L.append("")

    L.append("## Leaderboard (mean total, 0–12)")
    L.append("")
    L.append("| Rank | Model | Mean total | " + " | ".join(a.capitalize() for a in AXES) + " |")
    L.append("|---|---|---|" + "|".join(["---"] * len(AXES)) + "|")
    for i, m in enumerate(ranked, 1):
        axis_cells = " | ".join(f"{report.per_model_axis[m][a]:.2f}" for a in AXES)
        L.append(f"| {i} | `{m}` | **{report.per_model_overall[m]:.2f}** | {axis_cells} |")
    L.append("")

    if len(report.judges) >= 2:
        L.append("## Per-judge leaderboard (mean total, 0–12)")
        L.append("")
        L.append("| Judge | " + " | ".join(f"`{m}`" for m in ranked) + " |")
        L.append("|---|" + "|".join(["---"] * len(ranked)) + "|")
        for j in report.judges:
            cells = " | ".join(
                f"{report.per_judge_overall[j].get(m, float('nan')):.2f}"
                if m in report.per_judge_overall[j]
                else "—"
                for m in ranked
            )
            L.append(f"| `{j}` | {cells} |")
        L.append("")
        L.append(f"*{report.judge_agreement}.*")
        L.append("")

    L.append("## Per-axis mean (0–3)")
    L.append("")
    L.append("| Axis | " + " | ".join(f"`{m}`" for m in ranked) + " |")
    L.append("|---|" + "|".join(["---"] * len(ranked)) + "|")
    for axis in AXES:
        cells = " | ".join(f"{report.per_model_axis[m][axis]:.2f}" for m in ranked)
        L.append(f"| {axis} | {cells} |")
    L.append("")

    L.append("## Per-category mean total (0–12)")
    L.append("")
    L.append("| Category | " + " | ".join(f"`{m}`" for m in ranked) + " |")
    L.append("|---|" + "|".join(["---"] * len(ranked)) + "|")
    for cat in report.categories:
        cells = " | ".join(
            f"{report.per_model_category[m][cat]:.2f}" if cat in report.per_model_category[m] else "—"
            for m in ranked
        )
        L.append(f"| {cat} | {cells} |")
    L.append("")

    L.append("## Most-failed traps (lowest cross-model scores)")
    L.append("")
    for ft in report.failed_traps:
        L.append(f"### {ft.scenario.title}  ·  `{ft.scenario.id}`")
        L.append(
            f"*Category: {ft.scenario.category} · cross-model mean {ft.cross_model_mean:.2f}/12 · "
            f"worst: `{ft.worst_model}` at {ft.worst_total:.2f}/12*"
        )
        L.append("")
        L.append(f"- **Trap:** {ft.scenario.trap}")
        if ft.accuracy_justification:
            L.append(f"- **Judge (accuracy):** {ft.accuracy_justification}")
        L.append(f"- **Excerpt (`{ft.worst_model}`):** {ft.excerpt}")
        L.append("")

    L.append("---")
    L.append(
        "*Limitations: scenarios are synthetic and few (small n); grading is by LLM judges "
        "rather than human experts, and one model under test shares a family with a judge — "
        "read the per-judge table and treat results as a directional signal, not ground truth.*"
    )
    L.append("")
    return "\n".join(L)


# GitHub repo, linked from the published leaderboard page.
REPO_URL = "https://github.com/LaxRaj/comp-evals"


def render_site(report: Report) -> str:
    """The RESULTS.md leaderboard as a Jekyll page for GitHub Pages.

    Adds front matter (the Cayman theme renders title/description as a banner, so
    the body's leading H1 is dropped to avoid duplication) and a link back to the
    repo. Reuses `render_markdown` so the page never drifts from RESULTS.md.
    """
    body = render_markdown(report)
    heading = "# comp-evals results\n"
    if body.startswith(heading):
        body = body[len(heading):].lstrip("\n")
    front_matter = (
        "---\n"
        "title: comp-evals results\n"
        "description: Frontier models on synthetic compensation-reasoning scenarios, "
        "judged by two independent LLMs.\n"
        "---\n\n"
    )
    link = f"[View the code and reproduce on GitHub →]({REPO_URL})\n\n"
    return front_matter + link + body
