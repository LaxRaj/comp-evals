"""Load synthetic scenarios from the scenarios/ directory."""

from __future__ import annotations

import json
from pathlib import Path

from comp_evals.models import Scenario

# scenarios/ lives at the repo root, one level above the package.
SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def load_scenario(scenario_id: str) -> Scenario:
    """Load one scenario by id (filename stem), e.g. 's01_leveling_boundary'."""
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    return Scenario.model_validate_json(path.read_text())


def load_all_scenarios() -> list[Scenario]:
    """Load every scenario in the directory, sorted by id for deterministic order."""
    scenarios = [
        Scenario.model_validate_json(p.read_text())
        for p in sorted(SCENARIOS_DIR.glob("*.json"))
    ]
    return scenarios
