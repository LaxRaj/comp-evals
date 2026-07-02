"""Offline tests for the core models and loader — no API key required."""

from comp_evals.grader import _GRADE_SCHEMA
from comp_evals.loader import load_scenario
from comp_evals.models import AXES, AxisScore, Grade, Scenario


def test_s01_parses() -> None:
    s = load_scenario("s01_leveling_boundary")
    assert isinstance(s, Scenario)
    assert s.id == "s01_leveling_boundary"
    assert s.trap  # trap is the whole point — must be non-empty
    assert len(s.gold_notes) >= 3
    assert s.category == "leveling"


def test_grade_total_is_sum_of_axes() -> None:
    scores = [AxisScore(axis=axis, score=2, justification="ok") for axis in AXES]
    g = Grade(scenario_id="s01_leveling_boundary", model="claude-sonnet-4-6", scores=scores)
    assert g.total == 8
    # total is a computed field, so it must survive serialization
    assert g.model_dump()["total"] == 8


def test_grade_schema_constrains_score_to_0_3() -> None:
    axis_props = _GRADE_SCHEMA["properties"]["scores"]["items"]["properties"]
    assert axis_props["score"]["enum"] == [0, 1, 2, 3]
    assert axis_props["axis"]["enum"] == list(AXES)
