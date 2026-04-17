from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkTaskResolved:
    dataset_id: str
    dataset_name: str
    task_id: str
    task_name: str
    language: str
    submissions_root: str
    base_code_path: str | None
    task_manifest_path: str
    submission_count: int
    java_file_count: int
    original_java_file_count: int
    adapter_inputs: dict[str, dict[str, Any]]


class TaskLoaderError(RuntimeError):
    pass


def _discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


class DatasetTaskLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or _discover_repo_root()).resolve()
        self.benchmarks_root = self.repo_root / "tools" / "datasets" / "benchmarks"

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _resolve_repo_relative(self, value: str) -> Path:
        p = Path(value)
        if p.is_absolute():
            return p.resolve()
        return (self.repo_root / p).resolve()

    def _dataset_manifest_path(self, dataset_id: str) -> Path:
        return self.benchmarks_root / dataset_id / "manifest.json"

    def load_dataset_manifest(self, dataset_id: str) -> dict[str, Any]:
        path = self._dataset_manifest_path(dataset_id)
        if not path.exists():
            raise TaskLoaderError(f"Dataset manifest not found: {path}")
        return self._read_json(path)

    def load_task_manifest(self, dataset_id: str, task_id: str) -> dict[str, Any]:
        dataset_manifest = self.load_dataset_manifest(dataset_id)
        for task in dataset_manifest.get("tasks", []):
            if task.get("task_id") == task_id:
                task_manifest_path = self._resolve_repo_relative(task["manifest_path"])
                if not task_manifest_path.exists():
                    raise TaskLoaderError(f"Task manifest missing: {task_manifest_path}")
                return self._read_json(task_manifest_path)
        raise TaskLoaderError(f"Task not found: dataset={dataset_id} task={task_id}")

    def list_tasks(self, dataset_id: str) -> list[dict[str, Any]]:
        dataset_manifest = self.load_dataset_manifest(dataset_id)
        return list(dataset_manifest.get("tasks", []))

    def resolve_task(self, dataset_id: str, task_id: str) -> BenchmarkTaskResolved:
        dataset_manifest = self.load_dataset_manifest(dataset_id)
        task_manifest = self.load_task_manifest(dataset_id, task_id)

        submissions_root = self._resolve_repo_relative(task_manifest["submissions_path"])
        base_code_path = None
        if task_manifest.get("base_path"):
            candidate = self._resolve_repo_relative(task_manifest["base_path"])
            if candidate.exists():
                base_code_path = str(candidate)

        if not submissions_root.exists():
            raise TaskLoaderError(f"Submissions root does not exist: {submissions_root}")

        language = str(task_manifest.get("language", dataset_manifest.get("language", "java"))).lower()

        adapter_inputs = {
            "moss": {
                "language": language,
                "directory_mode": True,
                "submissions_root": str(submissions_root),
                "submission_glob": str(submissions_root / "*"),
                "base_code_path": base_code_path,
            },
            "jplag": {
                "language": language,
                "root_dir": str(submissions_root),
                "base_code_dir": base_code_path,
            },
        }

        return BenchmarkTaskResolved(
            dataset_id=dataset_id,
            dataset_name=dataset_manifest.get("dataset_name", dataset_id),
            task_id=task_manifest["task_id"],
            task_name=task_manifest.get("task_name", task_manifest["task_id"]),
            language=language,
            submissions_root=str(submissions_root),
            base_code_path=base_code_path,
            task_manifest_path=str(
                self._resolve_repo_relative(
                    f"tools/datasets/benchmarks/{dataset_id}/tasks/{task_id}/manifest.json"
                )
            ),
            submission_count=int(task_manifest.get("submission_count", 0)),
            java_file_count=int(task_manifest.get("java_file_count", 0)),
            original_java_file_count=int(task_manifest.get("original_java_file_count", 0)),
            adapter_inputs=adapter_inputs,
        )


def list_dataset_tasks(dataset_id: str) -> list[dict[str, Any]]:
    loader = DatasetTaskLoader()
    return loader.list_tasks(dataset_id)


def resolve_dataset_task(dataset_id: str, task_id: str) -> dict[str, Any]:
    loader = DatasetTaskLoader()
    return asdict(loader.resolve_task(dataset_id, task_id))
