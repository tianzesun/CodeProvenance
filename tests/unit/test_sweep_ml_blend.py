"""Unit tests for the offline blend-weight sweep (scripts/sweep_ml_blend.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sweep_ml_blend.py"


def _row(
    name: str,
    ml: float,
    heuristic: float,
    lines: int,
    probability: float,
    capped: bool,
) -> dict[str, object]:
    """One dumped per-file row in the shape the measurement scripts write."""
    return {
        "name": name,
        "method": "ml",
        "lines": lines,
        "ml_score": ml,
        "heuristic_score": heuristic,
        "ai_probability": probability,
        "disagreement_capped": capped,
    }


def _fixtures(
    tmp_path: Path, student_rows: list[dict[str, object]]
) -> tuple[Path, Path]:
    """Write a measure_human_fp report and a measure_ai_accuracy dump."""
    fp_dir = tmp_path / "fp"
    fp_dir.mkdir()
    (fp_dir / "human_fp_report_20260101_000000.json").write_text(
        json.dumps({"per_file": student_rows}), encoding="utf-8"
    )
    ai_dump = tmp_path / "ai.json"
    ai_dump.write_text(
        json.dumps(
            {
                "ai": [_row("ai.py", 0.9, 0.5, 80, 0.7, False)],
                "human": [_row("human.py", 0.2, 0.2, 80, 0.2, False)],
                "students": [],
            }
        ),
        encoding="utf-8",
    )
    return fp_dir, ai_dump


def _run(fp_dir: Path, ai_dump: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the sweep script the way an operator would."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fp-dump",
            str(fp_dir),
            "--ai-dump",
            str(ai_dump),
            "--weights",
            "0.5,1.0",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=REPO_ROOT,
    )


class TestSweepMlBlend:
    """The sweep must replay the shipped blend exactly, or refuse its own output."""

    def test_replay_matches_the_dumped_caps(self, tmp_path: Path) -> None:
        # Classifier-only conviction (heuristic below the corroboration floor)
        # is what the shipped guard caps, so the replay must count exactly the
        # files the measurement flagged.
        rows = [
            _row("a.py", 0.95, 0.20, 80, 0.35, True),
            _row("b.py", 0.80, 0.45, 80, 0.625, False),
            _row("c.py", 0.95, 0.20, 10, 0.275, False),
        ]
        result = _run(*_fixtures(tmp_path, rows))

        assert result.returncode == 0, result.stderr
        assert "self-check ok" in result.stdout
        assert "weight" in result.stdout

    def test_drifted_dump_is_rejected(self, tmp_path: Path) -> None:
        # Same row, but the dump claims the guard did not fire: the sweep must
        # refuse to report numbers derived from a mismatched replay.
        rows = [_row("a.py", 0.95, 0.20, 80, 0.575, False)]
        result = _run(*_fixtures(tmp_path, rows))

        assert result.returncode == 2
        assert "replay capped 1 files vs dump 0" in result.stderr

    def test_heuristic_only_rows_keep_their_dumped_score(self, tmp_path: Path) -> None:
        row = _row("h.py", 0.0, 0.0, 30, 0.42, False)
        row["ml_score"] = None
        row["heuristic_score"] = None
        result = _run(*_fixtures(tmp_path, [row]))

        assert result.returncode == 0, result.stderr
        # 0.42 stays above the 0.40 band for every candidate weight.
        assert "0.42" in result.stdout
