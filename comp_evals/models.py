"""Pydantic models for comp-evals: the core data shapes shared across the harness.

A `Scenario` is a synthetic compensation-reasoning case. A model answers it (the
Runner), and Claude-as-judge scores that answer against the four Compa-inspired
axes (the Grader), producing a `Grade` made of four `AxisScore`s.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field

# The four axes, inspired by Compa's public Evals page. Kept as a module-level
# tuple so the grader, report, and tests all agree on the axis set and order.
AXES: tuple[str, ...] = ("accuracy", "completeness", "assumptions", "usability")

Axis = Literal["accuracy", "completeness", "assumptions", "usability"]


class Scenario(BaseModel):
    """A single synthetic compensation-reasoning case.

    `gold_notes` captures the reasoning steps an expert would take; `trap` names
    the plausible-but-wrong path a smart non-expert would fall into. Scenarios
    are the actual artifact of this project — quality here is the whole point.
    """

    id: str = Field(..., description="Stable identifier, e.g. 's01_leveling_boundary'.")
    title: str
    context: str = Field(..., description="Realistic enterprise setup (~150 words).")
    question: str = Field(..., description="The single, specific question posed.")
    gold_notes: list[str] = Field(
        ..., description="The 3-5 reasoning steps an expert would take."
    )
    trap: str = Field(
        ..., description="The plausible-but-wrong path the scenario is designed to bait."
    )
    category: str = Field(
        default="",
        description="Grouping, e.g. leveling / pay-equity / offer-vs-market / equity.",
    )


class AxisScore(BaseModel):
    """A 0-3 score on one axis with the judge's justification."""

    axis: Axis
    score: int = Field(..., ge=0, le=3)
    justification: str


class Grade(BaseModel):
    """A judge's full grading of one model response against one scenario."""

    scenario_id: str
    model: str
    scores: list[AxisScore]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        """Sum of the per-axis scores (0-12 across four axes)."""
        return sum(s.score for s in self.scores)
