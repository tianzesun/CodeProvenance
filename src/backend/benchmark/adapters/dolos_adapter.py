"""Canonical Dolos benchmark adapter backed by the bundled Dolos CLI."""

from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.backend.benchmark.adapters.base_adapter import BaseAdapter
from src.backend.benchmark.contracts.evaluation_result import (
    EnrichedPair,
    EvaluationResult,
)


class DolosBenchmarkEngine(BaseAdapter):
    """Run the real Dolos CLI and parse its CSV pair report."""

    TOOL_DIRS = (
        Path(__file__).resolve().parents[4] / "tools" / "external" / "dolos-cli",
        Path(__file__).resolve().parents[4] / "tools" / "external" / "dolos",
    )

    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = threshold

    @property
    def name(self) -> str:
        """Return the adapter name."""
        return "dolos"

    @property
    def version(self) -> str:
        """Return the adapter version."""
        return "real-dolos-cli"

    def is_available(self) -> bool:
        """Return whether the Dolos CLI is available."""
        return self._find_cli() is not None

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate one pair through the same batch runner used by dashboards."""
        payload = self.run_batch(
            {"a.py": pair.code_a, "b.py": pair.code_b}, [("a.py", "b.py")]
        )
        score = payload["pairs"][0]["score"] if payload.get("pairs") else 0.0
        return self._make_result(
            pair,
            score,
            self._threshold,
            metadata={"real_dolos": True},
        )

    def run_batch(
        self,
        submissions: Dict[str, str],
        pairs: Iterable[tuple[str, str]],
        progress_cb=None,
    ) -> Dict[str, Any]:
        """Run Dolos for all submissions and return requested pair scores."""
        cli_path = self._find_cli()
        if not cli_path:
            return {"pairs": []}

        similarity_by_pair: Dict[str, float] = {}
        with tempfile.TemporaryDirectory(prefix="dolos-adapter-") as temp_dir:
            source_root = Path(temp_dir) / "subs"
            report_dir = Path(temp_dir) / "report"
            source_root.mkdir(parents=True, exist_ok=True)
            written_paths = self._write_submissions(source_root, submissions)

            env = os.environ.copy()
            node_bin_dir = cli_path.parents[2] / "node20" / "bin"
            if node_bin_dir.exists():
                env["PATH"] = f"{node_bin_dir}:{env.get('PATH', '')}"

            command_prefix = (
                ["node", str(cli_path)] if cli_path.suffix == ".js" else [str(cli_path)]
            )
            proc = subprocess.Popen(
                [
                    *command_prefix,
                    "run",
                    "--output-format",
                    "csv",
                    "--output-destination",
                    str(report_dir),
                    *written_paths.values(),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Stream output
            if proc.stdout:
                for line in proc.stdout:
                    line = line.rstrip()
                    if progress_cb:
                        progress_cb(line)
            else:
                proc.wait()

            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Dolos exited with code {proc.returncode}. See logs for details."
                )

            pairs_path = report_dir / "pairs.csv"
            if pairs_path.exists():
                similarity_by_pair.update(self._parse_pairs_csv(pairs_path))

        return {
            "pairs": [
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "score": similarity_by_pair.get(
                        self._pair_key(file_a, file_b), 0.0
                    ),
                }
                for file_a, file_b in pairs
            ]
        }

    def compare(self, code1: str, code2: str) -> float:
        """Compare two code strings using the real Dolos CLI."""
        payload = self.run_batch({"a.py": code1, "b.py": code2}, [("a.py", "b.py")])
        return payload["pairs"][0]["score"] if payload.get("pairs") else 0.0

    def _parse_pairs_csv(self, pairs_path: Path) -> Dict[str, float]:
        """Parse Dolos pairs.csv into pair scores."""
        scores: Dict[str, float] = {}
        with pairs_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                left_name = Path(row.get("leftFilePath", "")).name
                right_name = Path(row.get("rightFilePath", "")).name
                if not left_name or not right_name:
                    continue
                try:
                    similarity = float(row.get("similarity", 0.0))
                except (TypeError, ValueError):
                    continue
                scores[self._pair_key(left_name, right_name)] = max(
                    0.0, min(1.0, similarity)
                )
        return scores

    def _find_cli(self) -> Optional[Path]:
        """Find the Dolos plagiarism CLI."""
        candidates = []
        for tool_dir in self.TOOL_DIRS:
            candidates.extend(
                [
                    tool_dir / "node_modules" / ".bin" / "dolos",
                    tool_dir / "cli" / "node_modules" / ".bin" / "dolos",
                    tool_dir / "cli" / "dist" / "cli.js",
                    tool_dir / "dolos",
                ]
            )
        for candidate in candidates:
            if candidate.exists() and self._is_dolos_cli(candidate):
                return candidate
        return None

    def _is_dolos_cli(self, candidate: Path) -> bool:
        """Return whether a candidate binary is the Dolos plagiarism CLI."""
        command = (
            ["node", str(candidate)] if candidate.suffix == ".js" else [str(candidate)]
        )
        try:
            result = subprocess.run(
                [*command, "--help"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except Exception:
            return False
        help_text = f"{result.stdout}\n{result.stderr}".lower()
        return (
            "code similarity" in help_text
            or "plagiarism" in help_text
            or "--output-format" in help_text
        )

    def _write_submissions(
        self, target_dir: Path, submissions: Dict[str, str]
    ) -> Dict[str, str]:
        """Write submissions to a temporary directory."""
        written_paths: Dict[str, str] = {}
        for filename, content in sorted(submissions.items()):
            file_path = target_dir / Path(filename).name
            file_path.write_text(content, encoding="utf-8")
            written_paths[filename] = str(file_path)
        return written_paths

    def _pair_key(self, file_a: str, file_b: str) -> str:
        """Build a stable unordered pair key."""
        return "::".join(sorted((file_a, file_b)))


def run_dolos_batch(
    submissions: Dict[str, str],
    pairs: Iterable[tuple[str, str]],
    progress_cb=None,
) -> Dict[str, Any]:
    """Run the canonical Dolos batch adapter used by benchmark APIs."""
    return DolosBenchmarkEngine().run_batch(submissions, pairs, progress_cb=progress_cb)
