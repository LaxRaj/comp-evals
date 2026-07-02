"""Grader: Claude-as-judge scoring a model response against a scenario.

The judge is given the scenario, the gold reasoning notes, the named trap, and
the model's answer, and scores four axes 0-3 each. We force the judge through
structured outputs (a fixed JSON schema) so every grade is schema-valid and the
score field can only be 0-3 — this is a deliberate lever for grading
consistency, which is exactly what M0's judge-variance spike is de-risking.

The judge prompt is versioned (JUDGE_PROMPT_V1). If variance is too high, iterate
the prompt under a new version rather than editing V1 in place.
"""

from __future__ import annotations

import json

import anthropic

from comp_evals.models import AXES, AxisScore, Grade, Scenario

JUDGE_MODEL = "claude-opus-4-8"
JUDGE_PROMPT_VERSION = "JUDGE_PROMPT_V1"

# Per-axis 0-3 anchors, defined inline so the judge scores against a fixed rubric.
_AXIS_ANCHORS = {
    "accuracy": (
        "Is the core recommendation correct and consistent with the gold reasoning? "
        "0 = wrong / took the trap; 1 = partly right but a key conclusion is wrong; "
        "2 = right conclusion with a minor factual slip; 3 = fully correct and well-grounded."
    ),
    "completeness": (
        "Does the answer cover the key reasoning steps an expert would take (the gold notes)? "
        "0 = misses almost all; 1 = covers a few; 2 = covers most, minor gaps; "
        "3 = covers essentially all the important steps."
    ),
    "assumptions": (
        "Are assumptions surfaced explicitly and handled sensibly (rather than buried or wrong)? "
        "0 = makes unstated wrong assumptions; 1 = implicit assumptions only; "
        "2 = states most assumptions; 3 = states assumptions clearly and reasons about their impact."
    ),
    "usability": (
        "Is the answer clear, actionable, and usable by a practitioner? "
        "0 = vague / non-answer; 1 = an answer but hard to act on; "
        "2 = clear and mostly actionable; 3 = crisp, direct, immediately actionable."
    ),
}

JUDGE_PROMPT_V1 = (
    "You are a strict, consistent evaluator of compensation-reasoning answers. "
    "You will be given a synthetic scenario, the gold reasoning notes an expert "
    "would produce, the named reasoning trap the scenario is designed to bait, "
    "and a model's answer. Score the answer on four axes, each 0-3, using ONLY "
    "the anchors below. Be calibrated and repeatable: the same answer must always "
    "earn the same score. Judge the reasoning and conclusion, not the writing style "
    "beyond what the usability axis covers.\n\n"
    "AXES AND ANCHORS:\n"
    + "\n".join(f"- {axis}: {_AXIS_ANCHORS[axis]}" for axis in AXES)
    + "\n\nFor each axis give an integer 0-3 and a one-sentence justification "
    "citing specific evidence from the answer."
)

# JSON schema for structured outputs. Note: numeric min/max constraints are not
# supported by structured outputs, so score is constrained via an enum instead.
_GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "enum": list(AXES)},
                    "score": {"type": "integer", "enum": [0, 1, 2, 3]},
                    "justification": {"type": "string"},
                },
                "required": ["axis", "score", "justification"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scores"],
    "additionalProperties": False,
}


def _build_grading_prompt(scenario: Scenario, response: str) -> str:
    gold = "\n".join(f"  - {note}" for note in scenario.gold_notes)
    return (
        f"## Scenario context\n{scenario.context}\n\n"
        f"## Question\n{scenario.question}\n\n"
        f"## Gold reasoning notes (expert path)\n{gold}\n\n"
        f"## Named trap to watch for\n{scenario.trap}\n\n"
        f"## Model's answer to grade\n{response}\n\n"
        "Score all four axes now."
    )


def grade(scenario: Scenario, response: str, model_under_test: str) -> Grade:
    """Grade one `response` (produced by `model_under_test`) against `scenario`.

    Uses Claude as judge with structured outputs; returns a validated `Grade`.
    """
    client = anthropic.Anthropic()
    judgement = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=2000,
        system=JUDGE_PROMPT_V1,
        messages=[{"role": "user", "content": _build_grading_prompt(scenario, response)}],
        output_config={"format": {"type": "json_schema", "schema": _GRADE_SCHEMA}},
    )
    text = "".join(block.text for block in judgement.content if block.type == "text")
    data = json.loads(text)
    scores = [AxisScore(**s) for s in data["scores"]]
    return Grade(scenario_id=scenario.id, model=model_under_test, scores=scores)
