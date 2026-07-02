# comp-evals results

> Open-source eval scoring frontier models on **synthetic** compensation-reasoning scenarios, judged by an LLM on four axes (accuracy, completeness, assumptions, usability). Axes are inspired by Compa's public Evals page; this is not a claim about their internal methodology.

- **Run:** `run_20260702_145643`  ·  **Date:** 2026-07-02 14:56:43
- **Judge:** `claude-opus-4-8` (JUDGE_PROMPT_V1) — LLM-as-judge, not human experts (a documented limitation).
- **Models:** `claude`, `gpt`  ·  **Scenarios:** 16  ·  **Grades:** 32

## Leaderboard (mean total, 0–12)

| Rank | Model | Mean total | Accuracy | Completeness | Assumptions | Usability |
|---|---|---|---|---|---|---|
| 1 | `claude` | **11.94** | 3.00 | 3.00 | 2.94 | 3.00 |
| 2 | `gpt` | **11.75** | 3.00 | 2.88 | 2.94 | 2.94 |

## Per-axis mean (0–3)

| Axis | `claude` | `gpt` |
|---|---|---|
| accuracy | 3.00 | 3.00 |
| completeness | 3.00 | 2.88 |
| assumptions | 2.94 | 2.94 |
| usability | 3.00 | 2.94 |

## Per-category mean total (0–12)

| Category | `claude` | `gpt` |
|---|---|---|
| equity | 12.00 | 11.25 |
| leveling | 11.75 | 12.00 |
| offer-vs-market | 12.00 | 11.75 |
| pay-equity | 12.00 | 12.00 |

## Most-failed traps (lowest cross-model scores)

### The one-year cliff and 18-month math  ·  `s13_vesting_cliff_math`
*Category: equity · cross-model mean 11.00/12 · worst: `gpt` at 10/12*

- **Trap:** Computing vested units by linearly prorating the 4-year grant (18/48 -> ~18,000), ignoring that the 1-year cliff front-loads 25% at month 12 and nothing vests before it — a method that happens to hit the right number here but is fundamentally wrong.
- **Judge (accuracy):** Correctly computes 12,000 + 6,000 = 18,000 and identifies the colleague's linear method as invalid despite the coincidental match.
- **Excerpt (`gpt`):** To determine how many units will have vested by the 18-month mark, begin by understanding the RSU vesting schedule and the mechanics of the one-year cliff. ### Vesting Schedule Breakdown - **1-Year Cliff**: At the 12-month mark, 25% of the total RSUs (48,000 units) vest, equating to 12,000 units.

### The startup 'Head of' title  ·  `s04_startup_title_inflation`
*Category: leveling · cross-model mean 11.50/12 · worst: `claude` at 11/12*

- **Trap:** Honoring the impressive 'Head of Product' title at director level (L7) — treating a startup title as portable evidence of large-org scope instead of scoring her demonstrated scope against this company's rubric.
- **Judge (accuracy):** Correctly recommends L5 senior IC and identifies the core principle of scope-based leveling over title portability, fully aligned with gold reasoning.
- **Excerpt (`claude`):** # Sofia's Level Placement Analysis ## Recommendation: **L5 (Senior IC PM)** This is the correct placement, and the hiring manager should not be torn about it. --- ## Core Principle > **Level reflects demonstrated scope and skills, not title inflation from a structurally incomparable context.

### The competing offer above band  ·  `s11_competing_offer_band`
*Category: offer-vs-market · cross-model mean 11.50/12 · worst: `gpt` at 11/12*

- **Trap:** Matching the $260k competing base to win the candidate — busting the band ceiling and topping all internal peers, rather than comparing total comp and closing the gap with sign-on or equity.
- **Judge (accuracy):** Correctly rejects matching the $260k base and recommends closing the gap via sign-on/equity while protecting the band, fully consistent with gold reasoning.
- **Excerpt (`gpt`):** To address this scenario, we need to carefully consider the strategic implications of setting a precedent for paying above established compensation bands, as well as the broader context of total compensation competitiveness. ### Assumptions: 1. **Bands are established for a reason**: To maintain in…

---
*Limitations: scenarios are synthetic and few (small n); grading is a single LLM judge rather than human experts. Treat as a directional signal, not ground truth.*
