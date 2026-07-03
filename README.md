# comp-evals

[![CI](https://github.com/LaxRaj/comp-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/LaxRaj/comp-evals/actions/workflows/ci.yml)

An open-source eval harness that scores frontier models on **synthetic compensation-reasoning scenarios** — leveling calls, pay-equity edge cases, offer-vs-market judgment, and equity/stock reasoning — using an LLM-as-judge on four axes: **accuracy, completeness, assumptions, usability**.

The four axes are inspired by [Compa](https://compa.as)'s public Evals page. This project is **not** a claim about Compa's internal methodology, and it is **not** affiliated with Compa.

See [`RESULTS.md`](./RESULTS.md) for the latest leaderboard.

## What this is (and isn't)

- **Is:** 24 hand-written, expert-plausible comp-reasoning scenarios, each with a documented "trap" — a plausible-but-wrong path a smart non-expert would take (title-anchoring, percentile-chasing, ignoring geo differentials, vesting-schedule math errors, and so on). Models answer unaided; a judge scores each answer against gold reasoning notes.
- **Isn't:** a product, a hosted service, or a benchmark built on real compensation data. Every scenario is synthetic and labeled as such. Volume is a non-goal — scenario quality is the whole artifact.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and API keys for the models you want to score.

```bash
git clone <repo-url> comp-evals && cd comp-evals
uv sync                       # install into a local .venv
cp .env.example .env          # then add your keys to .env
```

Put your keys in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Then:

```bash
# Sanity-check the judge is consistent (runs one scenario, grades it 3x):
uv run comp-evals spike

# Run all scenarios against all models and grade each response once:
uv run comp-evals run --models all

# Build the leaderboard into RESULTS.md and print it:
uv run comp-evals report --run latest
```

`run` writes grades and raw responses to `results/{run_id}/` (gitignored). Runs are **resumable** — re-running skips scenario-model pairs already graded, and a failure for one model (e.g. a missing key) is recorded and skipped rather than aborting the whole run. To fill in only the missing pairs later: `uv run comp-evals run --resume`.

## How it works

| Piece | What it does |
|---|---|
| `Scenario` | A synthetic comp case: context, question, expert `gold_notes`, and the named `trap`. |
| **Runner** | Sends a scenario to one model (`claude`, `gpt`) behind one interface, with a per-call timeout and retries. Gold notes and the trap are **withheld** from the model. |
| **Grader** | Claude-as-judge scores the answer 0-3 on each axis, via structured outputs against a versioned judge prompt (`JUDGE_PROMPT_V1`). Structured outputs keep grading consistent. |
| **Report** | Aggregates a run into per-model, per-axis, and per-category tables, and surfaces the scenarios models did worst on. |

Adding a model is a one-line edit to the `MODELS` registry in `comp_evals/runner.py`.

### Methodology notes

- **Scenarios** are grounded in publicly described comp practice (Radford/Mercer-style leveling frameworks; US Equal Pay Act / Title VII concepts at a conceptual level; standard vesting mechanics). They are illustrative, not legal advice.
- **Grading** is LLM-as-judge, not a panel of human experts. Before building anything else, the judge's per-axis scoring was measured for consistency (repeat-grading variance <= 1 point) so the leaderboard is meaningful. Because one model under test (Claude) shares a family with the default judge, runs use a **second, independent judge (GPT)** and report per-judge scores plus a judge-agreement read — so a self-preference objection can be checked, not waved away. Grading is blind to which model wrote each answer.
- **Reproducibility:** every `RESULTS.md` header records the judges, judge prompt version, run date, and a model-separation statistic.

## Limitations

This is an honest, small artifact — read the numbers as a directional signal, not ground truth:

- **Synthetic scenarios.** No real compensation data is used, by design (privacy, and credibility). Real-world distributions may differ.
- **LLM judge, not human experts.** The scoring diverges from a human-scored approach, and the judges can share blind spots with the models they grade. In practice the two judges have shown a visible leniency gap (each is somewhat kinder to its own family), which can exceed the gap between the models — so read the per-judge table, not just the pooled leaderboard.
- **Small n and near-ceiling.** 24 scenarios across 4 categories. Strong frontier models rarely take these traps and cluster near the top (separation well under 1 point on a 0–12 scale), so small differences should not be over-interpreted. Widening the separation is an open direction: harder/adversarial scenarios and a stricter judge rubric.

## Development

```bash
uv run pytest            # all tests (offline; no API key needed)
```

## License

MIT - see [`LICENSE`](./LICENSE).
