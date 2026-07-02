"""Report: aggregate a run's grades into a per-model leaderboard.

Computes per-model overall means, per-axis means, and per-category means, plus
the scenarios models did worst on (the most-failed traps) with a short excerpt
of the worst model's answer and the judge's reasoning. Renders both a RESULTS.md
file (markdown tables) and a rich terminal view.

Pure aggregation lives in `build_report`; rendering is separate so it can be
tested offline on a synthetic run dir.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from comp_evals.grader import JUDGE_MODEL, JUDGE_PROMPT_VERSION
from comp_evals.loader import load_all_scenarios
from comp_evals.models import AXES, Grade, Scenario
from comp_evals.results import load_grades

# How many of the worst-scoring scenarios to spotlight as most-failed traps.
TOP_FAILED = 3


@dataclass
class FailedTrap:
    scenario: Scenario
    cross_model_mean: float
    worst_model: str
    worst_total: int
    accuracy_justification: str
    excerpt: str


@dataclass
class Report:
    run_id: str
    run_date: str
    judge_model: str
    judge_prompt_version: str
    models: list[str]
    scenario_count: int
    grade_count: int
    per_model_overall: dict[str, float]  # model -> mean total (0-12)
    per_model_axis: dict[str, dict[str, float]]  # model -> axis -> mean (0-3)
    per_model_category: dict[str, dict[str, float]]  # model -> category -> mean total
    categories: list[str]
    failed_traps: list[FailedTrap] = field(default_factory=list)


def _run_date(run_path: Path) -> str:
    """Human-readable date for the run, from the run_id timestamp if possible."""
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


def build_report(run_path: Path) -> Report:
    """Load a run dir and compute all leaderboard aggregates."""
    grades = load_grades(run_path)
    scenarios_by_id: dict[str, Scenario] = {s.id: s for s in load_all_scenarios()}

    models = sorted({g.model for g in grades})
    categories = sorted({s.category for s in scenarios_by_id.values()})

    per_model_overall: dict[str, float] = {}
    per_model_axis: dict[str, dict[str, float]] = {}
    per_model_category: dict[str, dict[str, float]] = {}

    for model in models:
        mgrades = [g for g in grades if g.model == model]
        per_model_overall[model] = _mean([g.total for g in mgrades])
        per_model_axis[model] = {
            axis: _mean([s.score for g in mgrades for s in g.scores if s.axis == axis])
            for axis in AXES
        }
        per_model_category[model] = {}
        for cat in categories:
            totals = [
                g.total
                for g in mgrades
                if (sc := scenarios_by_id.get(g.scenario_id)) is not None and sc.category == cat
            ]
            if totals:
                per_model_category[model][cat] = _mean(totals)

    # Most-failed traps: scenarios with the lowest cross-model mean total.
    scenario_means: dict[str, float] = {}
    for sid in {g.scenario_id for g in grades}:
        totals = [g.total for g in grades if g.scenario_id == sid]
        scenario_means[sid] = _mean(totals)

    worst_ids = sorted(scenario_means, key=lambda sid: (scenario_means[sid], sid))[:TOP_FAILED]
    failed_traps: list[FailedTrap] = []
    for sid in worst_ids:
        scenario = scenarios_by_id.get(sid)
        if scenario is None:
            continue
        sid_grades = [g for g in grades if g.scenario_id == sid]
        worst = min(sid_grades, key=lambda g: g.total)
        acc = next((s.justification for s in worst.scores if s.axis == "accuracy"), "")
        raw_path = run_path / "raw" / f"{sid}__{worst.model}.txt"
        raw = raw_path.read_text() if raw_path.exists() else ""
        failed_traps.append(
            FailedTrap(
                scenario=scenario,
                cross_model_mean=scenario_means[sid],
                worst_model=worst.model,
                worst_total=worst.total,
                accuracy_justification=acc,
                excerpt=_excerpt(raw),
            )
        )

    return Report(
        run_id=run_path.name,
        run_date=_run_date(run_path),
        judge_model=JUDGE_MODEL,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        models=models,
        scenario_count=len({g.scenario_id for g in grades}),
        grade_count=len(grades),
        per_model_overall=per_model_overall,
        per_model_axis=per_model_axis,
        per_model_category=per_model_category,
        categories=categories,
        failed_traps=failed_traps,
    )


def _ranked_models(report: Report) -> list[str]:
    return sorted(report.models, key=lambda m: report.per_model_overall[m], reverse=True)


def render_markdown(report: Report) -> str:
    ranked = _ranked_models(report)
    lines: list[str] = []
    lines.append("# comp-evals results")
    lines.append("")
    lines.append(
        "> Open-source eval scoring frontier models on **synthetic** compensation-reasoning "
        "scenarios, judged by an LLM on four axes (accuracy, completeness, assumptions, "
        "usability). Axes are inspired by Compa's public Evals page; this is not a claim "
        "about their internal methodology."
    )
    lines.append("")
    lines.append(f"- **Run:** `{report.run_id}`  ·  **Date:** {report.run_date}")
    lines.append(
        f"- **Judge:** `{report.judge_model}` ({report.judge_prompt_version}) — LLM-as-judge, "
        "not human experts (a documented limitation)."
    )
    lines.append(
        f"- **Models:** {', '.join(f'`{m}`' for m in ranked)}  ·  "
        f"**Scenarios:** {report.scenario_count}  ·  **Grades:** {report.grade_count}"
    )
    lines.append("")

    # Table 1: leaderboard.
    lines.append("## Leaderboard (mean total, 0–12)")
    lines.append("")
    lines.append("| Rank | Model | Mean total | " + " | ".join(a.capitalize() for a in AXES) + " |")
    lines.append("|---|---|---|" + "|".join(["---"] * len(AXES)) + "|")
    for i, m in enumerate(ranked, 1):
        axis_cells = " | ".join(f"{report.per_model_axis[m][a]:.2f}" for a in AXES)
        lines.append(f"| {i} | `{m}` | **{report.per_model_overall[m]:.2f}** | {axis_cells} |")
    lines.append("")

    # Table 2: per-axis (axes as rows, models as columns).
    lines.append("## Per-axis mean (0–3)")
    lines.append("")
    lines.append("| Axis | " + " | ".join(f"`{m}`" for m in ranked) + " |")
    lines.append("|---|" + "|".join(["---"] * len(ranked)) + "|")
    for axis in AXES:
        cells = " | ".join(f"{report.per_model_axis[m][axis]:.2f}" for m in ranked)
        lines.append(f"| {axis} | {cells} |")
    lines.append("")

    # Table 3: per-category (categories as rows, models as columns).
    lines.append("## Per-category mean total (0–12)")
    lines.append("")
    lines.append("| Category | " + " | ".join(f"`{m}`" for m in ranked) + " |")
    lines.append("|---|" + "|".join(["---"] * len(ranked)) + "|")
    for cat in report.categories:
        cells = " | ".join(
            f"{report.per_model_category[m].get(cat, float('nan')):.2f}"
            if cat in report.per_model_category[m]
            else "—"
            for m in ranked
        )
        lines.append(f"| {cat} | {cells} |")
    lines.append("")

    # Most-failed traps.
    lines.append(f"## Most-failed traps (lowest cross-model scores)")
    lines.append("")
    for ft in report.failed_traps:
        lines.append(f"### {ft.scenario.title}  ·  `{ft.scenario.id}`")
        lines.append(
            f"*Category: {ft.scenario.category} · cross-model mean {ft.cross_model_mean:.2f}/12 · "
            f"worst: `{ft.worst_model}` at {ft.worst_total}/12*"
        )
        lines.append("")
        lines.append(f"- **Trap:** {ft.scenario.trap}")
        if ft.accuracy_justification:
            lines.append(f"- **Judge (accuracy):** {ft.accuracy_justification}")
        lines.append(f"- **Excerpt (`{ft.worst_model}`):** {ft.excerpt}")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Limitations: scenarios are synthetic and few (small n); grading is a single "
        "LLM judge rather than human experts. Treat as a directional signal, not ground truth.*"
    )
    lines.append("")
    return "\n".join(lines)
