"""Runner: send a scenario to one model and capture its answer text.

One interface, `run_scenario(scenario, model)`, dispatches to a provider adapter
(Anthropic / OpenAI / Google) selected from the MODELS registry. Each call has a
per-call timeout and retries with exponential backoff. Model ids live in one
place (MODELS) so swapping the model under test for a provider is a one-line edit.
"""

from __future__ import annotations

import time
from typing import Callable

from comp_evals.models import Scenario

# The models under test, keyed by a short label used everywhere (leaderboard,
# results filenames, Grade.model). Edit the model_id here to change which model
# represents a provider. These ids are current, capable defaults; adjust freely.
MODELS: dict[str, dict[str, str]] = {
    "claude": {"provider": "anthropic", "model_id": "claude-sonnet-4-6"},
    "gpt": {"provider": "openai", "model_id": "gpt-4o"},
}
DEFAULT_MODEL = "claude"
ALL_MODELS = tuple(MODELS.keys())

DEFAULT_TIMEOUT = 120.0  # seconds per model call
MAX_RETRIES = 3  # total attempts per call
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


def _with_retries(fn: Callable[[], str]) -> str:
    """Call `fn` with up to MAX_RETRIES attempts and exponential backoff (1s, 2s, ...)."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry any transient API/network error
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)
    assert last_exc is not None
    raise last_exc


def _answer_anthropic(system: str, prompt: str, model_id: str, timeout: float) -> str:
    import anthropic

    client = anthropic.Anthropic(timeout=timeout)
    response = client.messages.create(
        model=model_id,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _answer_openai(system: str, prompt: str, model_id: str, timeout: float) -> str:
    from openai import OpenAI

    client = OpenAI(timeout=timeout)
    response = client.chat.completions.create(
        model=model_id,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


_ADAPTERS: dict[str, Callable[[str, str, str, float], str]] = {
    "anthropic": _answer_anthropic,
    "openai": _answer_openai,
}


def run_scenario(
    scenario: Scenario, model: str = DEFAULT_MODEL, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Ask `model` (a MODELS key) the scenario's question and return its answer text."""
    if model not in MODELS:
        raise KeyError(f"unknown model '{model}'; known: {', '.join(MODELS)}")
    spec = MODELS[model]
    adapter = _ADAPTERS[spec["provider"]]
    system, prompt = _SYSTEM, _build_prompt(scenario)
    return _with_retries(lambda: adapter(system, prompt, spec["model_id"], timeout))
