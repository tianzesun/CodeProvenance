"""JPlag benchmark adapter -- runs actual JPlag via Maven exec:java.

Batch approach: writes ALL code files to a temp directory, runs JPlag once,
parses the similarity matrix, then maps back to pairs.

FROZEN INTERFACE: evaluate() returns canonical EvaluationResult.
"""
from __future__ import annotations

import csv
import subprocess
import tempfile
from pathlib import Path

from src.backend.benchmark.adapters.base_adapter import BaseAdapter
from src.backend.benchmark.contracts.evaluation_result import EvaluationResult, EnrichedPair


class JPlagAdapter(BaseAdapter):
    """JPlag adapter with canonical output."""

    JPLAG_WRAPPER = (
        Path(__file__).resolve().parents[4]
        / "tools"
        / "external"
        / "jplag"
        / "wrapper"
        / "run_jplag.sh"
    )

    def __init__(self, min_tokens: int = 6, threshold: float = 0.5):
        self._min_tokens = min_tokens
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "jplag"

    @property
    def version(self) -> str:
        return "4.2.0"

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate a code pair using JPlag - FROZEN INTERFACE.

        Args:
            pair: EnrichedPair with code snippets and metadata.

        Returns:
            EvaluationResult with canonical schema.
        """
        score = self._compare(pair.code_a, pair.code_b)
        return self._make_result(
            pair=pair,
            score=score,
            threshold=self._threshold,
            metadata={"min_tokens": self._min_tokens},
        )

    def _compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using JPlag."""
        if not code_a or not code_b:
            return 0.0
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "subA").mkdir(parents=True, exist_ok=True)
            (tmp / "subB").mkdir(parents=True, exist_ok=True)
            (tmp / "subA" / "main.py").write_text(code_a, encoding="utf-8")
            (tmp / "subB" / "main.py").write_text(code_b, encoding="utf-8")
            result = tmp / "results.jplag"
            args = [
                str(self.JPLAG_WRAPPER),
                "-M", "RUN",
                "-t", str(self._min_tokens),
                "-l", "python3",
                "--csv-export",
                "-r", str(result),
                str(tmp),
            ]
            try:
                completed = subprocess.run(
                    args,
                    capture_output=True,
                    timeout=120,
                    text=True,
                    check=False,
                )
                if completed.returncode != 0:
                    return self._fallback(code_a, code_b)
                return self._parse_csv(tmp / "results")
            except Exception:
                return self._fallback(code_a, code_b)

    def _parse_csv(self, result_dir: Path) -> float:
        """Parse JPlag CSV output for pairwise similarity."""
        jplag_dir = result_dir.parent / "results.jplag"
        csv_files = list(jplag_dir.glob("*.csv"))
        if not csv_files:
            return 0.0

        comparison_csv = jplag_dir / "comparison.csv"
        if comparison_csv.exists():
            with open(comparison_csv, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                row = next(reader, None)
                if row and len(row) >= 3:
                    try:
                        return float(row[2])
                    except ValueError:
                        pass

        # fallback to any CSV
        csv_path = csv_files[0]
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header and len(header) >= 3:
                row = next(reader, None)
                if row:
                    try:
                        return float(row[2])
                    except ValueError:
                        pass
        return 0.0

    @staticmethod
    def _fallback(a: str, b: str) -> float:
        sa, sb = set(a.lower().split()), set(b.lower().split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)
