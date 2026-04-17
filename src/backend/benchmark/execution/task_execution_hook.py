from __future__ import annotations

import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from src.backend.benchmark.datasets.task_loader import DatasetTaskLoader, TaskLoaderError


@dataclass
class ToolExecutionPlan:
    tool: str
    dataset_id: str
    task_id: str
    command: list[str]
    cwd: str
    env: dict[str, str]
    inputs: dict[str, Any]
    output_dir: str


class TaskExecutionHookError(RuntimeError):
    pass


def _discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


class BenchmarkTaskExecutionHook:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or _discover_repo_root()).resolve()
        self.task_loader = DatasetTaskLoader(repo_root=self.repo_root)

    def build_plan(self, dataset_id: str, task_id: str, tool: str) -> ToolExecutionPlan:
        resolved = self.task_loader.resolve_task(dataset_id, task_id)
        tool_name = tool.lower()

        runs_root = self.repo_root / "tools" / "runs" / "benchmarks" / dataset_id / task_id / tool_name
        runs_root.mkdir(parents=True, exist_ok=True)

        if tool_name == "moss":
            wrapper = self.repo_root / "tools" / "external" / "moss" / "wrapper" / "run_moss.sh"
            if not wrapper.exists():
                raise TaskExecutionHookError(f"MOSS wrapper not found: {wrapper}")

            command = [
                str(wrapper),
                "-l",
                resolved.adapter_inputs["moss"]["language"],
                "-d",
                resolved.adapter_inputs["moss"]["submission_glob"],
            ]

            return ToolExecutionPlan(
                tool="moss",
                dataset_id=dataset_id,
                task_id=task_id,
                command=command,
                cwd=str(self.repo_root),
                env={},
                inputs=resolved.adapter_inputs["moss"],
                output_dir=str(runs_root),
            )

        if tool_name == "jplag":
            jplag_jar = self.repo_root / "tools" / "external" / "jplag" / "jplag.jar"
            if not jplag_jar.exists():
                raise TaskExecutionHookError(f"JPlag jar not found: {jplag_jar}")

            exec_root = runs_root / "input_root"
            if exec_root.exists():
                shutil.rmtree(exec_root)
            exec_root.mkdir(parents=True, exist_ok=True)

            submissions_root = Path(resolved.adapter_inputs["jplag"]["root_dir"])
            for child in submissions_root.iterdir():
                target = exec_root / child.name
                if child.is_dir():
                    shutil.copytree(child, target)
                else:
                    shutil.copy2(child, target)

            base_code_dir = resolved.adapter_inputs["jplag"].get("base_code_dir")
            base_name = None
            if base_code_dir:
                base_name = "original"
                shutil.copytree(base_code_dir, exec_root / base_name, dirs_exist_ok=True)

            command = [
                "java",
                "-jar",
                str(jplag_jar),
                str(exec_root),
                "-l",
                resolved.adapter_inputs["jplag"]["language"],
                "-r",
                str(runs_root / "report"),
            ]

            if base_name:
                command.extend(["-bc", base_name])

            return ToolExecutionPlan(
                tool="jplag",
                dataset_id=dataset_id,
                task_id=task_id,
                command=command,
                cwd=str(self.repo_root),
                env={},
                inputs={
                    **resolved.adapter_inputs["jplag"],
                    "execution_root": str(exec_root),
                    "base_code_dir_name": base_name,
                },
                output_dir=str(runs_root / "report"),
            )

        raise TaskExecutionHookError(f"Unsupported tool: {tool}")


def build_execution_plan(dataset_id: str, task_id: str, tool: str) -> dict[str, Any]:
    hook = BenchmarkTaskExecutionHook()
    return asdict(hook.build_plan(dataset_id, task_id, tool))
