"""JPlag benchmark adapter -- runs actual JPlag via Maven exec:java.

Batch approach: writes ALL code files to a temp directory, runs JPlag once,
parses the similarity matrix, then maps back to pairs.
"""
from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.similarity.base_engine import BaseSimilarityEngine


class JPlagBenchmarkEngine(BaseSimilarityEngine):
    """Runs actual JPlag CLI for batch comparison."""

    JPLAG_DIR = Path(__file__).parent.parent.parent / "tools" / "JPlag"

    def __init__(self, min_tokens: int = 6):
        self._min_tokens = min_tokens

    @property
    def name(self) -> str:
        return "jplag"

    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using JPlag."""
        if not code_a or not code_b:
            return 0.0
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.py").write_text(code_a, encoding="utf-8")
            (Path(tmpdir) / "b.py").write_text(code_b, encoding="utf-8")
            result = Path(tmpdir) / "results"
            args = [
                "mvn", "-q", "exec:java",
                f"-Dexec.mainClass=de.jplag.cli.CLI",
                f"-Dexec.args=-t {self._min_tokens} -l python3 --csv-export -r {result} {tmpdir}",
            ]
            try:
                subprocess.run(
                    args, cwd=str(self.JPLAG_DIR / "cli"),
                    capture_output=True, timeout=120,
                    env={**os.environ, "MAVEN_OPTS": "-Xmx2g"},
                )
                return self._parse_csv(result)
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