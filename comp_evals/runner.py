"""Runner: send a scenario to one model and capture its answer text.

M0 supports Claude only (the model under test answers the same way a human
would be asked to). M2 will add GPT and Gemini adapters behind this interface.
"""

from __future__ import annotations

import anthropic

from comp_evals.models import Scenario

DEFAULT_MODEL = "claude-sonnet-4-6"

# Max output tokens for a scenario answer. Comfortably under the SDK's
# non-streaming HTTP-timeout ceiling; a reasoning answer is a few paragraphs.
_MAX_TOKENS = 4000

_SYSTEM = (
    "You are an experienced compensation and leveling analyst. You are given a "
    "synthetic (not real) compensation-reasoning scenario. Reason carefully and "
    "answer the specific question asked. State your assumptions explicitly, walk "
    "through the reasoning an expert would use, and give a clear, actionable "
    "recommendation. Do not hedge into a non-answer."
)


def _build_prompt(scenario: Scenario) -> str:
    """Render a scenario into the user turn. Gold notes and trap are NOT shown —
    the model must reason unaided; those fields are only for the judge."""
    return (
        f"# Scenario: {scenario.title}\n\n"
        f"## Context\n{scenario.context}\n\n"
        f"## Question\n{scenario.question}"
    )


def run_scenario(scenario: Scenario, model: str = DEFAULT_MODEL) -> str:
    """Ask `model` the scenario's question and return its answer as plain text."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(scenario)}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
