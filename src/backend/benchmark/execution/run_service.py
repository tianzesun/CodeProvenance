from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import threading
import time
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
    pid: int | None = None
    process_group_id: int | None = None
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
            stdout_path=str(self._stdout_path(run_id)),
            stderr_path=str(self._stderr_path(run_id)),
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
        if record.status == "cancelled":
            self._save_record(record)
            return

        record.status = "running"
        record.started_at_utc = utc_now()
        self._save_record(record)

        stdout_path = Path(record.stdout_path)
        stderr_path = Path(record.stderr_path)
        Path(record.output_dir).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update(plan.env or {})

        popen_kwargs: dict[str, Any] = {
            "cwd": plan.cwd,
            "env": env,
            "stdout": None,
            "stderr": None,
            "text": True,
        }

        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        try:
            with stdout_path.open("w", encoding="utf-8") as stdout_fh, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_fh:
                popen_kwargs["stdout"] = stdout_fh
                popen_kwargs["stderr"] = stderr_fh

                process = subprocess.Popen(plan.command, **popen_kwargs)
                record.pid = int(process.pid)
                if os.name != "nt":
                    try:
                        record.process_group_id = int(os.getpgid(process.pid))
                    except Exception:
                        record.process_group_id = None
                self._save_record(record)

                return_code = process.wait()
                record.return_code = int(return_code)
                record.finished_at_utc = utc_now()

                refreshed = self._load_record(run_id)
                if refreshed.status == "cancelled":
                    record.status = "cancelled"
                else:
                    record.status = "completed" if return_code == 0 else "failed"
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
        return path.read_text(encoding="utf-8", errors="replace")[-max_chars:]

    def get_run_stderr(self, run_id: str, max_chars: int = 20000) -> str:
        path = self._stderr_path(run_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")[-max_chars:]

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

    def _terminate_process_group(self, record: BenchmarkRunRecord) -> None:
        if not record.pid:
            return

        if os.name == "nt":
            try:
                os.kill(record.pid, signal.SIGTERM)
            except Exception:
                pass
            time.sleep(1)
            try:
                os.kill(record.pid, signal.SIGKILL)
            except Exception:
                pass
            return

        pgid = record.process_group_id
        if not pgid:
            try:
                pgid = os.getpgid(record.pid)
            except Exception:
                pgid = None

        if pgid:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                pass
            time.sleep(1)
            try:
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
        else:
            try:
                os.kill(record.pid, signal.SIGTERM)
            except Exception:
                pass
            time.sleep(1)
            try:
                os.kill(record.pid, signal.SIGKILL)
            except Exception:
                pass

    def cancel_run(self, run_id: str) -> BenchmarkRunRecord:
        record = self._load_record(run_id)
        if record.status in {"completed", "failed", "cancelled"}:
            return record

        record.status = "cancelled"
        record.finished_at_utc = utc_now()
        record.error = "Cancellation requested by user."
        self._save_record(record)

        self._terminate_process_group(record)
        return self._load_record(run_id)


_service: BenchmarkRunService | None = None


def get_benchmark_run_service() -> BenchmarkRunService:
    global _service
    if _service is None:
        _service = BenchmarkRunService()
    return _service
