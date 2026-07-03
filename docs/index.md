---
title: comp-evals results
description: Frontier models on synthetic compensation-reasoning scenarios, judged by two independent LLMs.
---

[View the code and reproduce on GitHub →](https://github.com/LaxRaj/comp-evals)

> Open-source eval scoring frontier models on **synthetic** compensation-reasoning scenarios, judged by an LLM on four axes (accuracy, completeness, assumptions, usability). Axes are inspired by Compa's public Evals page; this is not a claim about their internal methodology.

- **Run:** `run_20260702_165349`  ·  **Date:** 2026-07-02 16:53:49
- **Judges:** `claude`, `gpt` (JUDGE_PROMPT_V1) — LLM-as-judge, not human experts (a documented limitation). Grading is blind to which model wrote each answer.
- **Models:** `claude`, `gpt`  ·  **Scenarios:** 24  ·  **Grades:** 96
- **Model separation:** 0.38 points (top − bottom, 0–12)  ·  **Judge agreement:** judges agree — identical ranking (claude > gpt)

## Leaderboard (mean total, 0–12)

| Rank | Model | Mean total | Accuracy | Completeness | Assumptions | Usability |
|---|---|---|---|---|---|---|
| 1 | `claude` | **11.98** | 3.00 | 3.00 | 2.98 | 3.00 |
| 2 | `gpt` | **11.60** | 2.94 | 2.81 | 2.90 | 2.96 |

## Per-judge leaderboard (mean total, 0–12)

| Judge | `claude` | `gpt` |
|---|---|---|
| `claude` | 12.00 | 11.33 |
| `gpt` | 11.96 | 11.88 |

*judges agree — identical ranking (claude > gpt).*

## Per-axis mean (0–3)

| Axis | `claude` | `gpt` |
|---|---|---|
| accuracy | 3.00 | 2.94 |
| completeness | 3.00 | 2.81 |
| assumptions | 2.98 | 2.90 |
| usability | 3.00 | 2.96 |

## Per-category mean total (0–12)

| Category | `claude` | `gpt` |
|---|---|---|
| equity | 11.92 | 11.67 |
| leveling | 12.00 | 11.67 |
| offer-vs-market | 12.00 | 11.33 |
| pay-equity | 12.00 | 11.75 |

## Most-failed traps (lowest cross-model scores)

### Chasing the 90th percentile  ·  `s09_percentile_chasing`
*Category: offer-vs-market · cross-model mean 11.25/12 · worst: `gpt` at 10.50/12*

- **Trap:** Meeting the candidate's cited '90th percentile base' number by pushing base to $215k — chasing a single base-salary percentile while ignoring total compensation, band structure, and internal equity.
- **Judge (accuracy):** The answer correctly avoids the trap by keeping base within band and emphasizing total comp, but recommending $200k (near band top) contradicts the gold note that a non-outlier should land near/modestly above midpoint, creating the same compression risk it warns against.
- **Excerpt (`gpt`):** ### Assumptions 1. The company's compensation philosophy is consistent and foundational, prioritizing total compensation over base alone, with a preference for positioning base salaries at the 50th percentile but allowing for total compensation to extend to the 75th percentile. 2. The survey data r…

### The competing offer above band  ·  `s11_competing_offer_band`
*Category: offer-vs-market · cross-model mean 11.50/12 · worst: `gpt` at 11.00/12*

- **Trap:** Matching the $260k competing base to win the candidate — busting the band ceiling and topping all internal peers, rather than comparing total comp and closing the gap with sign-on or equity.
- **Judge (accuracy):** Correctly rejects matching the $260k base and recommends closing the gap via sign-on/equity while protecting the band, fully aligned with gold reasoning.
- **Excerpt (`gpt`):** To answer this question, let's analyze the situation by considering the key factors involved: 1. **Internal Equity**: Matching the $260k base salary for the new hire would place them above all current L6 employees, including strong performers, which could lead to dissatisfaction among existing empl…

### A flagged gap in a group of three  ·  `s19_small_sample_gap`
*Category: pay-equity · cross-model mean 11.50/12 · worst: `gpt` at 11.00/12*

- **Trap:** Drawing a conclusion from n=3 in either direction — declaring it proof of discrimination, or dismissing it as statistically meaningless and ignoring it — instead of doing the individualized, documented review a tiny sample actually requires.
- **Judge (accuracy):** The answer avoids the trap in both directions and correctly prescribes an individualized review with documentation, matching the gold path.
- **Excerpt (`gpt`):** To address the flagged gap in compensation among the Level-6 principal designers, the company should take a comprehensive, multi-faceted approach, considering both qualitative and quantitative factors. Here's how to proceed: ### Assumptions 1.

---
*Limitations: scenarios are synthetic and few (small n); grading is by LLM judges rather than human experts, and one model under test shares a family with a judge — read the per-judge table and treat results as a directional signal, not ground truth.*
