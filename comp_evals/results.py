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


def _iter_grade_records(d: Path):
    path = _grades_path(d)
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def completed_pairs(d: Path) -> set[tuple[str, str]]:
    """The (scenario_id, model) pairs that have at least one grade in this run dir."""
    return {(rec["scenario_id"], rec["model"]) for rec in _iter_grade_records(d)}


def grade_counts(d: Path) -> dict[tuple[str, str, str], int]:
    """Count of grades per (scenario_id, model, judge) — drives N-times resume.

    Older grades without a `judge` field are attributed to the default 'claude'
    judge so existing runs remain resumable.
    """
    counts: dict[tuple[str, str, str], int] = {}
    for rec in _iter_grade_records(d):
        key = (rec["scenario_id"], rec["model"], rec.get("judge", "claude"))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _raw_path(d: Path, scenario_id: str, model: str) -> Path:
    return d / "raw" / f"{scenario_id}__{model}.txt"


def write_raw(d: Path, scenario_id: str, model: str, text: str) -> None:
    _raw_path(d, scenario_id, model).write_text(text)


def read_raw(d: Path, scenario_id: str, model: str) -> str | None:
    """The saved model response for a pair, or None if not yet captured.

    Lets a run reuse one model call across multiple judges and across resumes,
    instead of re-calling the model to re-grade.
    """
    path = _raw_path(d, scenario_id, model)
    return path.read_text() if path.exists() else None


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
