"""M1 tests: the scenario set is the product, so validate it hard.

All scenarios must parse against the schema, carry a non-empty trap and gold
notes, and split across the four categories exactly 4/4/4/4. No API key needed.
"""

from collections import Counter

import pytest

from comp_evals.loader import load_all_scenarios
from comp_evals.models import Scenario

EXPECTED_CATEGORY_COUNTS = {
    "leveling": 6,
    "pay-equity": 6,
    "offer-vs-market": 6,
    "equity": 6,
}
EXPECTED_TOTAL = sum(EXPECTED_CATEGORY_COUNTS.values())

# Loaded once; load_all_scenarios validates each against the Scenario schema.
SCENARIOS = load_all_scenarios()


def test_all_scenarios_parse() -> None:
    assert len(SCENARIOS) == EXPECTED_TOTAL, (
        f"expected {EXPECTED_TOTAL} scenarios, found {len(SCENARIOS)}"
    )
    assert all(isinstance(s, Scenario) for s in SCENARIOS)


def test_scenario_ids_are_unique() -> None:
    ids = [s.id for s in SCENARIOS]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    assert not dupes, f"duplicate scenario ids: {dupes}"


def test_category_counts_are_4_4_4_4() -> None:
    counts = Counter(s.category for s in SCENARIOS)
    assert dict(counts) == EXPECTED_CATEGORY_COUNTS, (
        f"category counts off: got {dict(counts)}, want {EXPECTED_CATEGORY_COUNTS}"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_scenario_has_required_content(scenario: Scenario) -> None:
    assert scenario.trap.strip(), f"{scenario.id}: trap must be non-empty"
    assert scenario.context.strip(), f"{scenario.id}: context must be non-empty"
    assert scenario.question.strip(), f"{scenario.id}: question must be non-empty"
    assert 3 <= len(scenario.gold_notes) <= 5, (
        f"{scenario.id}: expected 3-5 gold_notes, found {len(scenario.gold_notes)}"
    )
    assert all(note.strip() for note in scenario.gold_notes), (
        f"{scenario.id}: gold_notes must all be non-empty"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_scenarios_are_labeled_synthetic(scenario: Scenario) -> None:
    # A non-goal of the project is using real comp data; scenarios must say so.
    assert "SYNTHETIC" in scenario.context.upper(), (
        f"{scenario.id}: context must be labeled synthetic"
    )
