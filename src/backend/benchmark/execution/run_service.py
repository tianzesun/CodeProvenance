from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.backend.benchmark.execution.task_execution_hook import (
    BenchmarkTaskExecutionHook,
    TaskExecutionHookError,
    ToolExecutionPlan,
)
from src.backend.benchmark.datasets.task_loader import TaskLoaderError


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


@dataclass
class BenchmarkRunRecord:
    run_id: str
    dataset_id: str
    task_id: str
    tool: str
    status: str
    created_at_utc: str
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    return_code: int | None = None
    cwd: str = ""
    command: list[str] = field(default_factory=list)
    command_shell: str = ""
    output_dir: str = ""
    stdout_path: str = ""
    stderr_path: str = ""
    metadata_path: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BenchmarkRunError(RuntimeError):
    pass


class BenchmarkRunService:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or discover_repo_root()).resolve()
        self.runs_root = self.repo_root / "tools" / "runs" / "benchmark_jobs"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.execution_hook = BenchmarkTaskExecutionHook(repo_root=self.repo_root)

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def _metadata_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run.json"

    def _stdout_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "stdout.log"

    def _stderr_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "stderr.log"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_record(self, record: BenchmarkRunRecord) -> None:
        self._write_json(self._metadata_path(record.run_id), asdict(record))

    def _load_record(self, run_id: str) -> BenchmarkRunRecord:
        path = self._metadata_path(run_id)
        if not path.exists():
            raise BenchmarkRunError(f"Run not found: {run_id}")
        return BenchmarkRunRecord(**self._read_json(path))

    def start_run(self, dataset_id: str, task_id: str, tool: str) -> BenchmarkRunRecord:
        try:
            plan = self.execution_hook.build_plan(dataset_id=dataset_id, task_id=task_id, tool=tool)
        except (TaskExecutionHookError, TaskLoaderError) as exc:
            raise BenchmarkRunError(str(exc)) from exc

        run_id = str(uuid.uuid4())
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        stdout_path = self._stdout_path(run_id)
        stderr_path = self._stderr_path(run_id)

        record = BenchmarkRunRecord(
            run_id=run_id,
            dataset_id=dataset_id,
            task_id=task_id,
            tool=tool,
            status="queued",
            created_at_utc=utc_now(),
            cwd=plan.cwd,
            command=plan.command,
            command_shell=shlex.join(plan.command),
            output_dir=plan.output_dir,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            metadata_path=str(self._metadata_path(run_id)),
            inputs=plan.inputs,
        )
        self._save_record(record)

        worker = threading.Thread(
            target=self._execute_plan,
            args=(record.run_id, plan),
            daemon=True,
        )
        worker.start()

        return self._load_record(run_id)

    def _execute_plan(self, run_id: str, plan: ToolExecutionPlan) -> None:
        record = self._load_record(run_id)
        record.status = "running"
        record.started_at_utc = utc_now()
        self._save_record(record)

        stdout_path = Path(record.stdout_path)
        stderr_path = Path(record.stderr_path)
        Path(record.output_dir).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update(plan.env or {})

        try:
            with stdout_path.open("w", encoding="utf-8") as stdout_fh, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_fh:
                completed = subprocess.run(
                    plan.command,
                    cwd=plan.cwd,
                    env=env,
                    stdout=stdout_fh,
                    stderr=stderr_fh,
                    text=True,
                    check=False,
                )

            record.return_code = int(completed.returncode)
            record.finished_at_utc = utc_now()
            record.status = "completed" if completed.returncode == 0 else "failed"
            self._save_record(record)

        except Exception as exc:
            record.finished_at_utc = utc_now()
            record.status = "failed"
            record.error = str(exc)
            self._save_record(record)

    def get_run(self, run_id: str) -> BenchmarkRunRecord:
        return self._load_record(run_id)

    def get_run_stdout(self, run_id: str, max_chars: int = 20000) -> str:
        path = self._stdout_path(run_id)
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8", errors="replace")
        return content[-max_chars:]

    def get_run_stderr(self, run_id: str, max_chars: int = 20000) -> str:
        path = self._stderr_path(run_id)
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8", errors="replace")
        return content[-max_chars:]

    def list_runs(self, limit: int = 50) -> list[BenchmarkRunRecord]:
        records: list[BenchmarkRunRecord] = []
        for path in sorted(self.runs_root.glob("*/run.json"), reverse=True):
            try:
                records.append(BenchmarkRunRecord(**self._read_json(path)))
            except Exception:
                continue
            if len(records) >= limit:
                break
        return records

    def cancel_run(self, run_id: str) -> BenchmarkRunRecord:
        record = self._load_record(run_id)
        if record.status in {"completed", "failed", "cancelled"}:
            return record
        record.status = "cancelled"
        record.finished_at_utc = utc_now()
        record.error = "Cancellation requested; hard process termination not yet implemented."
        self._save_record(record)
        return record


_service: BenchmarkRunService | None = None


def get_benchmark_run_service() -> BenchmarkRunService:
    global _service
    if _service is None:
        _service = BenchmarkRunService()
    return _service
