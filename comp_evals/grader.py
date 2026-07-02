"""Grader: LLM-as-judge scoring a model response against a scenario.

The judge is given the scenario, the gold reasoning notes, the named trap, and
the model's answer (but NOT which model produced it — grading is blind to model
identity), and scores four axes 0-3 each via structured outputs (a fixed JSON
schema) so every grade is schema-valid and scores can only be 0-3.

Two judges are supported behind one interface: `claude` (Anthropic, the default)
and `gpt` (OpenAI). Using a second, independent judge lets the leaderboard be
checked for judge agreement — important because one model under test is Claude,
so a Claude-only judge invites a self-preference objection.

The judge prompt is versioned (JUDGE_PROMPT_V1). If scoring is too noisy or
biased, iterate under a new version rather than editing V1 in place.
"""

from __future__ import annotations

import json

from comp_evals.models import AXES, AxisScore, Grade, Scenario
from comp_evals.util import with_retries

# Judges, keyed by a short label stored on each Grade. Both are asked for the
# same schema; the model_id is the judge doing the scoring.
JUDGES: dict[str, dict[str, str]] = {
    "claude": {"provider": "anthropic", "model_id": "claude-opus-4-8"},
    "gpt": {"provider": "openai", "model_id": "gpt-4o"},
}
DEFAULT_JUDGE = "claude"
ALL_JUDGES = tuple(JUDGES.keys())

# Kept for backward-compatible imports (e.g. reports/CLI headers).
JUDGE_MODEL = JUDGES[DEFAULT_JUDGE]["model_id"]
JUDGE_PROMPT_VERSION = "JUDGE_PROMPT_V1"

_MAX_TOKENS = 2000

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
    "earn the same score. You do not know which model wrote the answer; judge the "
    "reasoning and conclusion, not the writing style beyond what the usability axis "
    "covers.\n\n"
    "AXES AND ANCHORS:\n"
    + "\n".join(f"- {axis}: {_AXIS_ANCHORS[axis]}" for axis in AXES)
    + "\n\nFor each axis give an integer 0-3 and a one-sentence justification "
    "citing specific evidence from the answer."
)

# JSON schema for structured outputs (shared by both judges). Numeric min/max
# constraints aren't supported, so score is constrained via an enum instead.
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


def _judge_anthropic(system: str, prompt: str, model_id: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    judgement = client.messages.create(
        model=model_id,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _GRADE_SCHEMA}},
    )
    text = "".join(block.text for block in judgement.content if block.type == "text")
    return json.loads(text)


def _judge_openai(system: str, prompt: str, model_id: str) -> dict:
    from openai import OpenAI

    client = OpenAI()
    judgement = client.chat.completions.create(
        model=model_id,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "grade", "schema": _GRADE_SCHEMA, "strict": True},
        },
    )
    return json.loads(judgement.choices[0].message.content or "{}")


_JUDGE_ADAPTERS = {
    "anthropic": _judge_anthropic,
    "openai": _judge_openai,
}


def grade(
    scenario: Scenario, response: str, model_under_test: str, judge: str = DEFAULT_JUDGE
) -> Grade:
    """Grade one `response` (from `model_under_test`) against `scenario` using `judge`."""
    if judge not in JUDGES:
        raise KeyError(f"unknown judge '{judge}'; known: {', '.join(JUDGES)}")
    spec = JUDGES[judge]
    adapter = _JUDGE_ADAPTERS[spec["provider"]]
    system, prompt = JUDGE_PROMPT_V1, _build_grading_prompt(scenario, response)
    data = with_retries(lambda: adapter(system, prompt, spec["model_id"]))
    scores = [AxisScore(**s) for s in data["scores"]]
    return Grade(scenario_id=scenario.id, model=model_under_test, judge=judge, scores=scores)
