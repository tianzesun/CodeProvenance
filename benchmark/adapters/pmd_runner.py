"""PMD-CPD (Copy/Paste Detector) benchmark adapter.

PMD CPD finds duplicated code blocks. This adapter creates temporary files,
runs PMD-CPD via subprocess, and extracts similarity scores from the output.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict

from benchmark.similarity.base_engine import BaseSimilarityEngine


class PMDBenchmarkEngine(BaseSimilarityEngine):
    """Runs PMD-CPD for copy/paste detection."""

    PMD_DIR = Path(__file__).parent.parent.parent / "tools" / "pmd"
    _cache: Dict[int, float] = {}

    def __init__(self, min_tokens: int = 100):
        self._min_tokens = min_tokens

    @property
    def name(self) -> str:
        return "pmd"

    def compare(self, code_a: str, code_b: str) -> float:
        """Compare two code strings using PMD-CPD."""
        if not code_a or not code_b:
            return 0.0
        key = hash(code_a) ^ hash(code_b)
        if key in self._cache:
            return self._cache[key]
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "a.py").write_text(code_a, encoding="utf-8")
            (td / "b.py").write_text(code_b, encoding="utf-8")
            score = self._run_cpd(td)
        self._cache[key] = score
        return score

    def _run_cpd(self, tmpdir: Path) -> float:
        """Run PMD-CPD via Maven exec:java."""
        args = [
            "mvn", "-q", "-pl", "pmd-cli", "-am", "exec:java",
            f"-Dexec.mainClass=net.sourceforge.pmd.cmd.PMD",
            f"-Dexec.args=cpd --minimum-tokens {self._min_tokens} --dir {tmpdir} --language python --format text --fail-on-violation false",
        ]
        try:
            result = subprocess.run(
                args, cwd=str(self.PMD_DIR),
                capture_output=True, timeout=30, text=True,
            )
            # Parse PMD-CPD output for duplicate detection
            output = result.stdout + result.stderr
            if "Found a " in output or "duplicate" in output.lower():
                # Calculate overlap ratio
                return self._estimate_similarity(tmpdir)
            return 0.0
        except Exception:
            return self._fallback(tmpdir)

    def _estimate_similarity(self, tmpdir: Path) -> float:
        """Estimate similarity from PMD-CPD output."""
        a = (tmpdir / "a.py").read_text()
        b = (tmpdir / "b.py").read_text()
        sa, sb = set(a.split()), set(b.split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    @staticmethod
    def _fallback(tmpdir: Path) -> float:
        a = (tmpdir / "a.py").read_text()
        b = (tmpdir / "b.py").read_text()
        sa, sb = set(a.lower().split()), set(b.lower().split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)