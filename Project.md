# comp-evals

> Open-source eval harness scoring frontier models (Claude, GPT, Gemini) on synthetic compensation-reasoning scenarios, scored on Compa's four axes: accuracy, completeness, assumptions, usability.

- **Success metric:** Public repo + results table live; LinkedIn post published tagging Charlie Franklin; DM sent to Joseph Malandruccolo with link.
- **Deadline:** ASAP/ 1 Day from Now.
- **Status:** M4 — shipping (M0-M3 done; Gemini dropped, 2-model eval: claude + gpt)
- **Repo:** ~/projects/comp-evals (public GitHub on ship)

## Non-goals
- NOT a product. No web UI, no auth, no hosted anything. CLI + markdown results only.
- NOT real compensation data. All scenarios are synthetic and clearly labeled as such — real comp data would create privacy exposure and undermine credibility.
- NOT 100 scenarios. 15–20 deep, expert-plausible scenarios with documented reasoning traps. Volume is a non-goal; scenario quality is the whole artifact.
- NOT a claim about Compa's internal methodology. The four axes are inspired by their public Evals page; the README says so explicitly.

## Architecture
- **Stack:** Python 3.12, `anthropic`, `openai`, `google-genai`, `pydantic` v2, `pytest`, `rich` (terminal tables), `typer` (CLI). No framework beyond that.
- **Core abstractions:**
  - `Scenario` — a comp-reasoning case: context, question, gold reasoning notes, trap description
  - `Rubric` — the four axes with 0–3 scoring anchors per axis, versioned
  - `Runner` — sends a scenario to one model, captures the response
  - `Grader` — LLM-as-judge (Claude) scoring a response against the rubric + gold notes, with the judge prompt versioned
  - `Report` — aggregates scores into a per-model leaderboard (markdown + terminal)
- **Faked vs. real:** Scenarios are synthetic (real). Grading is LLM-judge, not human experts (documented limitation in README — this is the honest divergence from Compa's human-scored approach).
- **Riskiest assumption:** That an LLM judge can score consistently enough to make the leaderboard meaningful. M0 de-risks by running the judge 3x on the same response and measuring score variance before anything else gets built.

## Milestones

### [x] M0 — Walking skeleton + judge-consistency spike
- **Deliverable:** Repo scaffolded; ONE scenario runs end-to-end (Claude answers → Claude judges → score prints); judge variance measured across 3 repeated gradings.
- **Prompt:**
  ```
  Create a Python 3.12 project `comp-evals` with uv. Deps: anthropic, openai,
  google-genai, pydantic, pytest, rich, typer. Structure:
  comp_evals/{models.py,runner.py,grader.py,cli.py}, scenarios/, tests/.
  Add .env.example (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY) and
  .gitignore covering .env and results/.
  In models.py: pydantic models Scenario (id, title, context, question,
  gold_notes, trap), AxisScore (axis, score 0-3, justification), Grade
  (scenario_id, model, scores: list[AxisScore], total).
  Write ONE scenario in scenarios/s01_leveling_boundary.json: a candidate
  whose scope straddles L5/L6; trap = anchoring on title instead of scope.
  runner.py: run_scenario(scenario, model="claude-sonnet-4-6") -> response text.
  grader.py: grade(scenario, response) -> Grade using Claude as judge with a
  versioned judge prompt (JUDGE_PROMPT_V1) scoring the 4 axes: accuracy,
  completeness, assumptions, usability, each with 0-3 anchors defined inline.
  cli.py: `comp-evals spike` runs s01 through runner once, grades it 3 times,
  prints all 3 Grades and the per-axis score variance with rich.
  ```
- **Acceptance criteria:**
  - [ ] `comp-evals spike` completes and prints 3 grades + variance
  - [ ] Per-axis score variance ≤1 point across repeat gradings (if not, iterate JUDGE_PROMPT before proceeding — this gate blocks the project)
  - [ ] `.env` pattern works; no key in repo
- **Verify:** `uv run comp-evals spike`

### [x] M1 — Scenario set (the actual product)
- **Deliverable:** 16 scenarios across 4 categories: leveling decisions (4), pay-equity edge cases (4), offer-vs-market judgment (4), equity/stock reasoning (4). Each has gold_notes written from public comp-practice sources and a named trap.
- **Prompt:**
  ```
  Design 15 more scenarios (s02-s16) in scenarios/, following the Scenario
  schema. Categories: leveling (3 more), pay-equity (4), offer-vs-market (4),
  equity/stock (4). Each must have: realistic enterprise context (~150 words),
  one specific question, gold_notes listing the 3-5 reasoning steps an expert
  would take, and a trap field naming the plausible-but-wrong path. Ground
  gold_notes in public comp practice (Radford/Mercer methodology as publicly
  described, pay-equity law basics like US EPA/Title VII at concept level).
  Traps must be genuinely tempting: title-anchoring, percentile-chasing,
  ignoring geo differentials, conflating band penetration with performance,
  vesting-schedule math errors. Add tests/test_scenarios.py validating all
  scenarios parse, have non-empty traps, and category counts are 4/4/4/4.
  ```
- **Acceptance criteria:**
  - [ ] 16 scenarios parse and pass schema tests
  - [ ] Manual read of all 16: each trap is one a smart non-expert would plausibly fall into (Laksh reviews — do not skip)
- **Verify:** `uv run pytest tests/test_scenarios.py -v`

### [x] M2 — Multi-model runner + full grading pass
- **Deliverable:** All 16 scenarios run against Claude, GPT, and Gemini; grades persisted to results/ as JSON.
- **Prompt:**
  ```
  Extend runner.py to support model adapters: claude-sonnet-4-6 (anthropic),
  gpt (openai), gemini (google-genai) behind one run_scenario(scenario, model)
  interface with retries (3, exponential backoff) and a per-call timeout.
  cli.py: `comp-evals run --models all` executes all scenarios x models,
  grading each response once, writing results/{run_id}/grades.jsonl plus
  raw responses. Show a rich progress bar. Make runs resumable: skip
  scenario-model pairs already in the run dir.
  ```
- **Acceptance criteria:**
  - [ ] 48 scenario-model grades persisted in one run
  - [ ] A killed run resumes without re-calling completed pairs
- **Verify:** `uv run comp-evals run --models all && ls results/*/grades.jsonl`

### [x] M3 — Leaderboard report
- **Deliverable:** `comp-evals report` produces RESULTS.md: per-model totals, per-axis breakdown, per-category breakdown, and the 3 most-failed traps with example excerpts.
- **Prompt:**
  ```
  Add report.py: load a run's grades.jsonl, compute per-model mean scores
  overall, per axis, and per category. Identify the 3 scenarios with lowest
  cross-model scores and extract 1-2 sentence response excerpts showing the
  trap being taken. cli.py: `comp-evals report --run latest` writes RESULTS.md
  with markdown tables and prints a rich table. Include the judge prompt
  version and run date in the report header for reproducibility.
  ```
- **Acceptance criteria:**
  - [ ] RESULTS.md renders with all three tables and trap excerpts
  - [ ] Report header shows judge version + date
- **Verify:** `uv run comp-evals report --run latest && cat RESULTS.md`

### [ ] M4 — Ship
- **Deliverable:** Public repo; README (quickstart, methodology, honest limitations incl. LLM-judge vs human-expert scoring, four-axes attribution to Compa's public Evals page); MIT license; terminal demo GIF; LinkedIn post draft; DM draft to Joseph.
- **Acceptance criteria:**
  - [ ] Quickstart works from clean clone with only API keys added
  - [ ] Limitations section explicitly covers: synthetic scenarios, LLM judge, small n
  - [ ] LinkedIn post + DM drafted (use the-compliance-first-outreach-copywriter tone rules: no AI-hype language)
- **Verify:** `git clone <repo> /tmp/ce && cd /tmp/ce && uv sync && uv run comp-evals spike`

## Decision log
<!-- Append-only. Format: date — decision — why -->
- 2026-07-02 — Judge = `claude-opus-4-8` with structured outputs (fixed 0-3 JSON schema), separate from the runner default. — Structured outputs constrain the judge to schema-valid, 0-3 scores; M0's variance spike passed with 0 per-axis variance on s01.
- 2026-07-02 — Runner default kept as `claude-sonnet-4-6`. — It is a real, active model, so the spec's id needed no change.
- 2026-07-02 — Dropped Gemini; shipping a 2-model eval (`claude`, `gpt`). — Owner decision; removed the `google-genai` dependency and the Google adapter so the quickstart needs only two keys. The runner registry still makes adding a model a one-line change.
- 2026-07-02 — Honest finding: strong models cluster near the ceiling (claude 11.94, gpt 11.75 / 12); spread is concentrated in the harder scenarios (e.g. s13 vesting math). — Documented as a limitation (small n) and a future lever (harder scenarios / stricter rubric).