"""comp-evals command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from comp_evals import results
from comp_evals.grader import ALL_JUDGES, JUDGE_MODEL, JUDGE_PROMPT_VERSION, JUDGES, grade
from comp_evals.loader import load_all_scenarios, load_scenario
from comp_evals.models import AXES, Grade
from comp_evals.report import Report, build_report, render_markdown
from comp_evals.runner import ALL_MODELS, DEFAULT_MODEL, MODELS, run_scenario

app = typer.Typer(help="Eval harness scoring frontier models on comp-reasoning scenarios.")
console = Console()

# M0 gate: per-axis score spread across repeat gradings must be <= this.
VARIANCE_THRESHOLD = 1


@app.callback()
def _main() -> None:
    """comp-evals: score frontier models on synthetic compensation-reasoning scenarios."""
    # Load .env before any command runs. override=True so a key placed in .env
    # takes precedence over a stale/invalid ANTHROPIC_API_KEY already in the
    # environment (the key-shadowing trap). This callback also forces subcommands
    # (e.g. `spike`) to be named explicitly, leaving room for `run`/`report` later.
    load_dotenv(override=True)


def _axis_scores(grade_obj: Grade) -> dict[str, int]:
    return {s.axis: s.score for s in grade_obj.scores}


@app.command()
def spike(
    scenario_id: str = typer.Option(
        "s01_leveling_boundary", help="Scenario to run the spike on."
    ),
    model: str = typer.Option(DEFAULT_MODEL, help="Model under test (answers the scenario)."),
    repeats: int = typer.Option(3, help="Number of times to re-grade the same response."),
) -> None:
    """Run ONE scenario end-to-end, grade the response N times, report score variance.

    This is M0's judge-consistency spike: it de-risks the whole project by
    checking that the LLM judge scores the same response consistently enough
    (per-axis spread <= 1 point) to make a leaderboard meaningful.
    """
    scenario = load_scenario(scenario_id)
    console.print(
        Panel(
            f"[bold]{scenario.title}[/bold]\n[dim]{scenario.id} · category: {scenario.category}[/dim]\n\n"
            f"Model under test: [cyan]{model}[/cyan]\n"
            f"Judge: [magenta]{JUDGE_MODEL}[/magenta] ({JUDGE_PROMPT_VERSION})\n"
            f"Repeats: {repeats}",
            title="comp-evals spike",
        )
    )

    console.print("\n[bold]1/2[/bold] Running scenario through the model under test…")
    response = run_scenario(scenario, model=model)
    console.print(Panel(response, title=f"Response from {model}", border_style="cyan"))

    console.print(f"\n[bold]2/2[/bold] Grading the same response {repeats}× with the judge…")
    grades: list[Grade] = []
    for i in range(repeats):
        g = grade(scenario, response, model_under_test=model)
        grades.append(g)
        console.print(f"  · grading {i + 1}/{repeats} → total {g.total}/12")

    # Per-grade detail table.
    detail = Table(title="Grades (per axis)", show_lines=False)
    detail.add_column("Axis", style="bold")
    for i in range(repeats):
        detail.add_column(f"run {i + 1}", justify="center")
    detail.add_column("range", justify="center", style="yellow")

    per_axis = [_axis_scores(g) for g in grades]
    max_range = 0
    for axis in AXES:
        vals = [scores[axis] for scores in per_axis]
        rng = max(vals) - min(vals)
        max_range = max(max_range, rng)
        row = [axis, *[str(v) for v in vals]]
        rng_cell = f"[green]{rng}[/green]" if rng <= VARIANCE_THRESHOLD else f"[red]{rng}[/red]"
        row.append(rng_cell)
        detail.add_row(*row)

    totals = [g.total for g in grades]
    total_range = max(totals) - min(totals)
    detail.add_row(
        "[bold]TOTAL[/bold]",
        *[f"[bold]{t}[/bold]" for t in totals],
        f"[bold]{total_range}[/bold]",
    )
    console.print(detail)

    # Gate verdict.
    passed = max_range <= VARIANCE_THRESHOLD
    if passed:
        console.print(
            Panel(
                f"Max per-axis range across {repeats} gradings = [green]{max_range}[/green] "
                f"(threshold {VARIANCE_THRESHOLD}). Judge is consistent enough — [bold green]GATE PASSED[/bold green].",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"Max per-axis range = [red]{max_range}[/red] (threshold {VARIANCE_THRESHOLD}). "
                f"Judge is too noisy — [bold red]GATE FAILED[/bold red]. Iterate JUDGE_PROMPT "
                f"(bump the version) before building more of the harness.",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)


def _resolve_from(value: str, known: dict, all_keys: tuple, label: str) -> list[str]:
    """Parse an 'all' | comma-list option against a set of known keys."""
    if value.strip().lower() == "all":
        return list(all_keys)
    selected = [x.strip() for x in value.split(",") if x.strip()]
    unknown = [x for x in selected if x not in known]
    if unknown:
        raise typer.BadParameter(
            f"unknown {label}(s): {', '.join(unknown)}. Known: {', '.join(known)} (or 'all')."
        )
    return selected


@app.command()
def run(
    models: str = typer.Option("all", help="'all' or comma-separated model keys (claude,gpt)."),
    judges: str = typer.Option(
        "all", help="'all' or comma-separated judge keys (claude,gpt). Multiple judges enable agreement checks."
    ),
    repeats: int = typer.Option(1, help="Gradings per (scenario, model, judge) — >1 measures grading spread."),
    run_id: str = typer.Option(
        "", help="Resume/continue a specific run id (dir under results/). Blank = new run."
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Resume the most recent run instead of starting a new one."
    ),
    timeout: float = typer.Option(120.0, help="Per-model-call timeout in seconds."),
) -> None:
    """Run every scenario against every selected model, grade each response with
    every selected judge (optionally repeated), and persist grades + raw
    responses under results/{run_id}/.

    Each model is called once per scenario and the response is reused across
    judges and repeats. Resumable: (scenario, model, judge) units already graded
    up to `repeats` are skipped, so a killed run continues without re-calling
    completed work; a failure for one unit (e.g. a missing key) is isolated.
    """
    selected_models = _resolve_from(models, MODELS, ALL_MODELS, "model")
    selected_judges = _resolve_from(judges, JUDGES, ALL_JUDGES, "judge")
    scenarios = load_all_scenarios()

    # Decide the target run directory: explicit id > --resume latest > new run.
    if run_id:
        rid = run_id
    elif resume and (latest := results.latest_run_dir()) is not None:
        rid = latest.name
    else:
        rid = results.new_run_id()
    run_path = results.ensure_run_dir(rid)

    counts = results.grade_counts(run_path)
    # Per (scenario, model): how many more gradings each judge still needs.
    pending: list[tuple] = []  # (scenario, model, {judge: remaining})
    units_todo = 0
    for s in scenarios:
        for m in selected_models:
            remaining = {j: max(0, repeats - counts.get((s.id, m, j), 0)) for j in selected_judges}
            if sum(remaining.values()) > 0:
                pending.append((s, m, remaining))
                units_todo += sum(remaining.values())

    target_units = len(scenarios) * len(selected_models) * len(selected_judges) * repeats
    done_units = target_units - units_todo

    console.print(
        Panel(
            f"Run: [bold]{rid}[/bold]\n"
            f"Models: [cyan]{', '.join(selected_models)}[/cyan] · "
            f"Judges: [magenta]{', '.join(selected_judges)}[/magenta] "
            f"({JUDGE_PROMPT_VERSION}) · repeats: {repeats}\n"
            f"Scenarios: {len(scenarios)} · target grades: {target_units} · "
            f"done: {done_units} · to do: {units_todo}\n"
            f"[dim]{run_path / 'grades.jsonl'}[/dim]",
            title="comp-evals run",
        )
    )
    if not pending:
        console.print("[green]Nothing to do — this run is already complete.[/green]")
        return

    failures: list[tuple[str, str, str]] = []
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("grading", total=units_todo)
        for scenario, model, remaining in pending:
            progress.update(task, description=f"{scenario.id} · {model}")
            # One model call per (scenario, model), reused across judges/repeats.
            response = results.read_raw(run_path, scenario.id, model)
            if response is None:
                try:
                    response = run_scenario(scenario, model=model, timeout=timeout)
                    results.write_raw(run_path, scenario.id, model, response)
                except Exception as exc:  # noqa: BLE001 - model call failed; skip its judge units
                    failures.append((scenario.id, model, f"model call — {type(exc).__name__}: {exc}"))
                    progress.advance(task, sum(remaining.values()))
                    continue
            for judge, n in remaining.items():
                for _ in range(n):
                    try:
                        g = grade(scenario, response, model_under_test=model, judge=judge)
                        results.append_grade(run_path, g)
                    except Exception as exc:  # noqa: BLE001 - isolate one grading unit
                        failures.append((scenario.id, f"{model}/{judge}", f"{type(exc).__name__}: {exc}"))
                    progress.advance(task)

    graded = sum(results.grade_counts(run_path).values())
    console.print(
        Panel(
            f"Persisted [green]{graded}[/green] grades in this run dir "
            f"(target {target_units}).\n"
            f"Failures this pass: [red]{len(failures)}[/red]\n"
            f"Results: [bold]{run_path}[/bold]",
            title="run complete",
            border_style="green" if not failures else "yellow",
        )
    )
    for sid, who, err in failures[:20]:
        console.print(f"  [red]![/red] {sid} · {who} — {err}")
    if len(failures) > 20:
        console.print(f"  [dim]… and {len(failures) - 20} more[/dim]")
    if failures:
        console.print(
            "[dim]Re-run the same command with --resume (or --run-id "
            f"{rid}) to retry only the failed/pending units.[/dim]"
        )


def _print_report(rep: Report) -> None:
    ranked = sorted(rep.models, key=lambda m: rep.per_model_overall[m], reverse=True)

    board = Table(title="Leaderboard (mean total, 0-12)")
    board.add_column("#", justify="right")
    board.add_column("Model", style="bold cyan")
    board.add_column("Total", justify="right", style="bold")
    for axis in AXES:
        board.add_column(axis[:4], justify="right")
    for i, m in enumerate(ranked, 1):
        board.add_row(
            str(i), m, f"{rep.per_model_overall[m]:.2f}",
            *[f"{rep.per_model_axis[m][a]:.2f}" for a in AXES],
        )
    console.print(board)
    console.print(
        f"[dim]separation {rep.separation:.2f} pts (top-bottom) · "
        f"{rep.judge_agreement}[/dim]"
    )

    if len(rep.judges) >= 2:
        jb = Table(title="Per-judge leaderboard (mean total, 0-12)")
        jb.add_column("Judge", style="bold magenta")
        for m in ranked:
            jb.add_column(m, justify="right")
        for j in rep.judges:
            jb.add_row(
                j,
                *[
                    f"{rep.per_judge_overall[j][m]:.2f}" if m in rep.per_judge_overall[j] else "—"
                    for m in ranked
                ],
            )
        console.print(jb)

    cat = Table(title="Per-category mean total (0-12)")
    cat.add_column("Category", style="bold")
    for m in ranked:
        cat.add_column(m, justify="right")
    for c in rep.categories:
        cat.add_row(
            c,
            *[
                f"{rep.per_model_category[m][c]:.2f}" if c in rep.per_model_category[m] else "—"
                for m in ranked
            ],
        )
    console.print(cat)

    console.print("\n[bold]Most-failed traps[/bold] (lowest cross-model scores):")
    for ft in rep.failed_traps:
        console.print(
            f"  [yellow]•[/yellow] [bold]{ft.scenario.id}[/bold] "
            f"({ft.scenario.category}) — mean {ft.cross_model_mean:.2f}/12, "
            f"worst [cyan]{ft.worst_model}[/cyan] {ft.worst_total}/12"
        )


@app.command()
def report(
    run: str = typer.Option("latest", help="Run id to report on, or 'latest'."),
    output: Path = typer.Option(
        None, help="Markdown output path (default: RESULTS.md at the repo root)."
    ),
) -> None:
    """Aggregate a run's grades into RESULTS.md (per-model, per-axis, per-category,
    and the most-failed traps) and print a leaderboard to the terminal."""
    if run == "latest":
        run_path = results.latest_run_dir()
        if run_path is None:
            raise typer.BadParameter("no runs found under results/ — do `comp-evals run` first.")
    else:
        run_path = results.run_dir(run)
        if not run_path.exists():
            raise typer.BadParameter(f"run '{run}' not found under results/.")

    rep = build_report(run_path)
    if not rep.models:
        console.print("[red]No grades in this run — nothing to report.[/red]")
        raise typer.Exit(code=1)

    md = render_markdown(rep)
    out_path = output or (results.RESULTS_ROOT.parent / "RESULTS.md")
    out_path.write_text(md)

    console.print(
        Panel(
            f"Run: [bold]{rep.run_id}[/bold] · {rep.run_date}\n"
            f"Judges: [magenta]{', '.join(rep.judges)}[/magenta] ({rep.judge_prompt_version})\n"
            f"Models: {', '.join(rep.models)} · Scenarios: {rep.scenario_count} · "
            f"Grades: {rep.grade_count}\n"
            f"Wrote [green]{out_path}[/green]",
            title="comp-evals report",
        )
    )
    _print_report(rep)


if __name__ == "__main__":
    app()
