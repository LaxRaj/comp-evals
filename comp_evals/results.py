"""Persistence for eval runs.

A run lives in results/{run_id}/ and holds:
  - grades.jsonl   one JSON Grade per line (the source of truth for "completed")
  - raw/{scenario_id}__{model}.txt   the model's raw answer text

Grades are appended as they complete, so a killed run keeps everything already
done. Resuming reads grades.jsonl to skip scenario-model pairs already graded.
The results/ directory is gitignored — runs are regenerated, not versioned.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from comp_evals.models import Grade

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"


def new_run_id() -> str:
    """A timestamped run id, e.g. 'run_20260702_140355'."""
    return "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def run_dir(run_id: str) -> Path:
    return RESULTS_ROOT / run_id


def latest_run_dir() -> Path | None:
    """Most recently created run directory, or None if there are no runs yet."""
    if not RESULTS_ROOT.exists():
        return None
    runs = sorted(p for p in RESULTS_ROOT.iterdir() if p.is_dir())
    return runs[-1] if runs else None


def ensure_run_dir(run_id: str) -> Path:
    d = run_dir(run_id)
    (d / "raw").mkdir(parents=True, exist_ok=True)
    return d


def _grades_path(d: Path) -> Path:
    return d / "grades.jsonl"


def completed_pairs(d: Path) -> set[tuple[str, str]]:
    """The (scenario_id, model) pairs already graded in this run dir."""
    path = _grades_path(d)
    if not path.exists():
        return set()
    pairs: set[tuple[str, str]] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        pairs.add((rec["scenario_id"], rec["model"]))
    return pairs


def write_raw(d: Path, scenario_id: str, model: str, text: str) -> None:
    (d / "raw" / f"{scenario_id}__{model}.txt").write_text(text)


def append_grade(d: Path, grade: Grade) -> None:
    """Append one grade to grades.jsonl (created if absent)."""
    with _grades_path(d).open("a") as f:
        f.write(grade.model_dump_json() + "\n")


def load_grades(d: Path) -> list[Grade]:
    """Load all grades from a run dir."""
    path = _grades_path(d)
    if not path.exists():
        return []
    return [
        Grade.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]
