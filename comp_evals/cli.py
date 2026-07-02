"""comp-evals command-line interface."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from comp_evals.grader import JUDGE_MODEL, JUDGE_PROMPT_VERSION, grade
from comp_evals.loader import load_scenario
from comp_evals.models import AXES, Grade
from comp_evals.runner import DEFAULT_MODEL, run_scenario

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


if __name__ == "__main__":
    app()
