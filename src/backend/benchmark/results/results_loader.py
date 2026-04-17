from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResultSummary:
    run_id: str
    tool: str
    dataset_id: str
    task_id: str
    status: str
    output_dir: str
    primary_artifact: str | None
    result_url: str | None
    top_pairs: list[dict[str, Any]] = field(default_factory=list)
    raw_artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultsLoaderError(RuntimeError):
    pass


def discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


class BenchmarkResultsLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or discover_repo_root()).resolve()
        self.jobs_root = self.repo_root / "tools" / "runs" / "benchmark_jobs"

    def _run_dir(self, run_id: str) -> Path:
        return self.jobs_root / run_id

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def _load_run_record(self, run_id: str) -> dict[str, Any]:
        path = self._run_dir(run_id) / "run.json"
        if not path.exists():
            raise ResultsLoaderError(f"Run not found: {run_id}")
        return self._read_json(path)

    def load(self, run_id: str) -> BenchmarkResultSummary:
        record = self._load_run_record(run_id)
        tool = record["tool"].lower()

        if tool == "jplag":
            return self._load_jplag(run_id, record)
        if tool == "moss":
            return self._load_moss(run_id, record)

        raise ResultsLoaderError(f"Unsupported tool: {tool}")

    def _load_jplag(self, run_id: str, record: dict[str, Any]) -> BenchmarkResultSummary:
        output_dir = Path(record["output_dir"])
        raw_artifacts: list[str] = []

        overview_path = output_dir / "overview.json"
        result_zip = output_dir / "result.zip"

        if not overview_path.exists():
            for candidate in output_dir.rglob("overview.json"):
                overview_path = candidate
                break

        if not result_zip.exists():
            for candidate in output_dir.rglob("result.zip"):
                result_zip = candidate
                break

        overview = {}
        top_pairs: list[dict[str, Any]] = []

        if overview_path.exists():
            overview = self._read_json(overview_path)
            similarities = overview.get("topComparisons") or overview.get("comparisons") or []
            for item in similarities[:25]:
                left = item.get("firstSubmission") or item.get("submissionA") or item.get("left")
                right = item.get("secondSubmission") or item.get("submissionB") or item.get("right")
                score = (
                    item.get("similarity")
                    or item.get("averageSimilarity")
                    or item.get("maxSimilarity")
                    or item.get("similarityScore")
                )
                top_pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "score": score,
                    }
                )

        for path in output_dir.rglob("*"):
            if path.is_file():
                raw_artifacts.append(str(path))

        primary_artifact = str(result_zip) if result_zip.exists() else (str(overview_path) if overview_path.exists() else None)

        return BenchmarkResultSummary(
            run_id=run_id,
            tool="jplag",
            dataset_id=record["dataset_id"],
            task_id=record["task_id"],
            status=record["status"],
            output_dir=str(output_dir),
            primary_artifact=primary_artifact,
            result_url=None,
            top_pairs=top_pairs,
            raw_artifacts=sorted(raw_artifacts),
            metadata={
                "overview_path": str(overview_path) if overview_path.exists() else None,
                "result_zip": str(result_zip) if result_zip.exists() else None,
                "return_code": record.get("return_code"),
            },
        )

    def _extract_first_url(self, text: str) -> str | None:
        match = re.search(r"https?://\S+", text)
        return match.group(0) if match else None

    def _load_moss(self, run_id: str, record: dict[str, Any]) -> BenchmarkResultSummary:
        output_dir = Path(record["output_dir"])
        stdout_path = self._run_dir(run_id) / "stdout.log"
        stderr_path = self._run_dir(run_id) / "stderr.log"

        stdout_text = self._read_text(stdout_path) if stdout_path.exists() else ""
        stderr_text = self._read_text(stderr_path) if stderr_path.exists() else ""

        result_url = self._extract_first_url(stdout_text) or self._extract_first_url(stderr_text)

        raw_artifacts: list[str] = []
        if output_dir.exists():
            for path in output_dir.rglob("*"):
                if path.is_file():
                    raw_artifacts.append(str(path))

        return BenchmarkResultSummary(
            run_id=run_id,
            tool="moss",
            dataset_id=record["dataset_id"],
            task_id=record["task_id"],
            status=record["status"],
            output_dir=str(output_dir),
            primary_artifact=result_url,
            result_url=result_url,
            top_pairs=[],
            raw_artifacts=sorted(raw_artifacts),
            metadata={
                "return_code": record.get("return_code"),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "embed_url": result_url,
            },
        )


def load_benchmark_result(run_id: str) -> dict[str, Any]:
    loader = BenchmarkResultsLoader()
    return asdict(loader.load(run_id))
