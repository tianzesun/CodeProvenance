#!/usr/bin/env python3
"""
Prepare Oscar Karnalim IR-Plag dataset for CodeProvenance benchmark use.

This script converts the extracted IR-Plag dataset into a CodeProvenance-friendly
prepared dataset layout and writes per-task manifests for downstream benchmarking.

Target output structure:
    <repo_root>/tools/datasets/benchmarks/ir_plag/
        manifest.json
        tasks/
            <task_name>/
                manifest.json
                base/
                    original/
                        ...
                submissions/
                    np_<submission_id>/
                        ...
                    pl_<level>_<submission_id>/
                        ...

This layout is suitable for:
- Benchmark preset discovery
- UI card metadata generation
- MOSS directory-mode runs
- Future adapter normalization

Expected source dataset structure (loosely inferred):
    <input_root>/<task>/
        Original/
        non-plagiarized/
        plagiarized/

Usage:
    python3 prepare_ir_plag_for_codeprovenance.py \
        --input ~/CodeProvenance/tools/datasets/raw/sourcecodeplagiarismdataset/IR-Plag-Dataset \
        --repo-root ~/CodeProvenance

Optional:
    --task <task_name>   Filter to one or more tasks
    --overwrite          Replace an existing prepared dataset
    --dataset-id ir_plag_custom
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


LOGGER = logging.getLogger("prepare_ir_plag_for_codeprovenance")


@dataclass
class SubmissionRecord:
    submission_id: str
    category: str
    plagiarism_level: str | None
    source_path: str
    prepared_path: str
    java_file_count: int


@dataclass
class TaskManifest:
    task_id: str
    task_name: str
    dataset_id: str
    language: str = "java"
    base_path: str = ""
    submissions_path: str = ""
    original_java_file_count: int = 0
    submission_count: int = 0
    java_file_count: int = 0
    categories_present: list[str] = field(default_factory=list)
    submissions: list[SubmissionRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DatasetManifest:
    dataset_id: str
    dataset_name: str
    source: str
    prepared_at_utc: str
    language: str
    task_count: int
    submission_count: int
    java_file_count: int
    tasks: list[dict]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s | %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Oscar Karnalim IR-Plag dataset into CodeProvenance benchmark structure."
    )
    parser.add_argument("--input", required=True, type=Path, help="Extracted IR-Plag dataset root")
    parser.add_argument("--repo-root", required=True, type=Path, help="CodeProvenance repo root")
    parser.add_argument(
        "--dataset-id",
        default="ir_plag",
        help="Prepared dataset id under tools/datasets/benchmarks/",
    )
    parser.add_argument(
        "--dataset-name",
        default="IR-Plag Dataset",
        help="Human-readable dataset name",
    )
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        help="Optional task filter; can be provided multiple times",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing prepared dataset directory",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def sanitize_name(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "unknown"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_java_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.java") if p.is_file())


def copy_java_tree(src_root: Path, dst_root: Path) -> int:
    count = 0
    for src_file in list_java_files(src_root):
        rel = src_file.relative_to(src_root)
        dst_file = dst_root / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        count += 1
    return count


def immediate_subdirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(p for p in path.iterdir() if p.is_dir())


def ensure_clean_dir(path: Path, overwrite: bool) -> None:
    if path.exists():
        if overwrite:
            shutil.rmtree(path)
        else:
            raise FileExistsError(f"Path already exists: {path}. Use --overwrite to replace it.")
    path.mkdir(parents=True, exist_ok=True)


def infer_submission_dirs(root: Path) -> list[Path]:
    children = immediate_subdirs(root)
    child_dirs_with_java = [child for child in children if list_java_files(child)]
    if child_dirs_with_java:
        return child_dirs_with_java
    if list_java_files(root):
        return [root]
    return []


def category_dirs(task_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for child in immediate_subdirs(task_dir):
        name = child.name.lower()
        if name == "original":
            found["original"] = child
        elif name in {"non-plagiarized", "non_plagiarized", "nonplagiarized"}:
            found["non_plagiarized"] = child
        elif name == "plagiarized":
            found["plagiarized"] = child
    return found


def discover_task_dirs(dataset_root: Path, requested_tasks: set[str]) -> list[Path]:
    candidates = immediate_subdirs(dataset_root)
    if not requested_tasks:
        return candidates
    requested_norm = {sanitize_name(t).lower() for t in requested_tasks}
    return [
        task for task in candidates
        if sanitize_name(task.name).lower() in requested_norm or task.name.lower() in requested_norm
    ]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def relative_to(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def prepare_original(
    task_dir: Path,
    task_out_dir: Path,
    manifest: TaskManifest,
    repo_root: Path,
) -> None:
    cats = category_dirs(task_dir)
    original_dir = cats.get("original")
    if not original_dir:
        warning = f"No Original/ directory found in task: {task_dir.name}"
        LOGGER.warning(warning)
        manifest.warnings.append(warning)
        return

    dst = task_out_dir / "base" / "original"
    count = copy_java_tree(original_dir, dst)
    manifest.base_path = relative_to(dst, repo_root)
    manifest.original_java_file_count = count


def add_submission(
    manifest: TaskManifest,
    repo_root: Path,
    submission_id: str,
    category: str,
    level: str | None,
    source_path: Path,
    prepared_path: Path,
    java_file_count: int,
) -> None:
    if java_file_count <= 0:
        return
    manifest.submissions.append(
        SubmissionRecord(
            submission_id=submission_id,
            category=category,
            plagiarism_level=level,
            source_path=str(source_path),
            prepared_path=relative_to(prepared_path, repo_root),
            java_file_count=java_file_count,
        )
    )
    manifest.submission_count += 1
    manifest.java_file_count += java_file_count
    if category not in manifest.categories_present:
        manifest.categories_present.append(category)


def prepare_non_plagiarized(
    task_dir: Path,
    task_out_dir: Path,
    manifest: TaskManifest,
    repo_root: Path,
) -> None:
    cats = category_dirs(task_dir)
    np_dir = cats.get("non_plagiarized")
    if not np_dir:
        warning = f"No non-plagiarized/ directory found in task: {task_dir.name}"
        LOGGER.warning(warning)
        manifest.warnings.append(warning)
        return

    submissions = infer_submission_dirs(np_dir)
    if not submissions:
        warning = f"No Java submissions found under non-plagiarized for task: {task_dir.name}"
        LOGGER.warning(warning)
        manifest.warnings.append(warning)
        return

    for idx, submission_dir in enumerate(submissions, start=1):
        raw_name = submission_dir.name if submission_dir != np_dir else f"root_{idx}"
        sub_id = f"np_{sanitize_name(raw_name)}"
        dst = task_out_dir / "submissions" / sub_id
        copied = copy_java_tree(submission_dir, dst)
        add_submission(
            manifest=manifest,
            repo_root=repo_root,
            submission_id=sub_id,
            category="non_plagiarized",
            level=None,
            source_path=submission_dir,
            prepared_path=dst,
            java_file_count=copied,
        )


def prepare_plagiarized(
    task_dir: Path,
    task_out_dir: Path,
    manifest: TaskManifest,
    repo_root: Path,
) -> None:
    cats = category_dirs(task_dir)
    plag_dir = cats.get("plagiarized")
    if not plag_dir:
        warning = f"No plagiarized/ directory found in task: {task_dir.name}"
        LOGGER.warning(warning)
        manifest.warnings.append(warning)
        return

    level_dirs = immediate_subdirs(plag_dir)
    if not level_dirs:
        submissions = infer_submission_dirs(plag_dir)
        if not submissions:
            warning = f"No plagiarism levels or Java submissions found in task: {task_dir.name}"
            LOGGER.warning(warning)
            manifest.warnings.append(warning)
            return
        for idx, submission_dir in enumerate(submissions, start=1):
            raw_name = submission_dir.name if submission_dir != plag_dir else f"root_{idx}"
            level = "unknown"
            sub_id = f"pl_{sanitize_name(level)}_{sanitize_name(raw_name)}"
            dst = task_out_dir / "submissions" / sub_id
            copied = copy_java_tree(submission_dir, dst)
            add_submission(
                manifest=manifest,
                repo_root=repo_root,
                submission_id=sub_id,
                category="plagiarized",
                level=level,
                source_path=submission_dir,
                prepared_path=dst,
                java_file_count=copied,
            )
        return

    for level_dir in level_dirs:
        level = sanitize_name(level_dir.name)
        submissions = infer_submission_dirs(level_dir)
        if not submissions:
            warning = f"No Java submissions found under plagiarized/{level_dir.name} in task: {task_dir.name}"
            LOGGER.warning(warning)
            manifest.warnings.append(warning)
            continue

        for idx, submission_dir in enumerate(submissions, start=1):
            raw_name = submission_dir.name if submission_dir != level_dir else f"root_{idx}"
            sub_id = f"pl_{level}_{sanitize_name(raw_name)}"
            dst = task_out_dir / "submissions" / sub_id
            copied = copy_java_tree(submission_dir, dst)
            add_submission(
                manifest=manifest,
                repo_root=repo_root,
                submission_id=sub_id,
                category="plagiarized",
                level=level,
                source_path=submission_dir,
                prepared_path=dst,
                java_file_count=copied,
            )


def prepare_task(
    task_dir: Path,
    dataset_id: str,
    dataset_root_out: Path,
    repo_root: Path,
) -> TaskManifest:
    task_id = sanitize_name(task_dir.name)
    task_out_dir = dataset_root_out / "tasks" / task_id
    task_out_dir.mkdir(parents=True, exist_ok=True)
    (task_out_dir / "base").mkdir(parents=True, exist_ok=True)
    (task_out_dir / "submissions").mkdir(parents=True, exist_ok=True)

    manifest = TaskManifest(
        task_id=task_id,
        task_name=task_dir.name,
        dataset_id=dataset_id,
        submissions_path=relative_to(task_out_dir / "submissions", repo_root),
    )

    prepare_original(task_dir, task_out_dir, manifest, repo_root)
    prepare_non_plagiarized(task_dir, task_out_dir, manifest, repo_root)
    prepare_plagiarized(task_dir, task_out_dir, manifest, repo_root)

    task_manifest_path = task_out_dir / "manifest.json"
    write_json(task_manifest_path, asdict(manifest))
    LOGGER.info(
        "Prepared task=%s submissions=%s java_files=%s",
        task_id,
        manifest.submission_count,
        manifest.java_file_count + manifest.original_java_file_count,
    )
    return manifest


def print_summary(dataset_root_out: Path, manifests: Iterable[TaskManifest]) -> None:
    manifests = list(manifests)
    print("\nCodeProvenance dataset preparation summary")
    print("=" * 88)
    for m in manifests:
        print(
            f"{m.task_id:24} | submissions={m.submission_count:4d} | "
            f"submission_java={m.java_file_count:5d} | "
            f"base_java={m.original_java_file_count:4d} | "
            f"warnings={len(m.warnings)}"
        )
        for warning in m.warnings:
            print(f"  - WARNING: {warning}")
    print("=" * 88)
    print(f"Prepared dataset root: {dataset_root_out}")
    print(f"Tasks processed      : {len(manifests)}")
    print(f"Total submissions    : {sum(m.submission_count for m in manifests)}")
    print(
        f"Total Java files     : "
        f"{sum(m.java_file_count + m.original_java_file_count for m in manifests)}"
    )


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    input_root = args.input.expanduser().resolve()
    repo_root = args.repo_root.expanduser().resolve()
    dataset_id = sanitize_name(args.dataset_id)

    if not input_root.exists():
        LOGGER.error("Input root does not exist: %s", input_root)
        return 1

    if not repo_root.exists():
        LOGGER.error("Repo root does not exist: %s", repo_root)
        return 2

    dataset_root_out = repo_root / "tools" / "datasets" / "benchmarks" / dataset_id
    ensure_clean_dir(dataset_root_out, overwrite=args.overwrite)

    task_dirs = discover_task_dirs(input_root, set(args.task))
    if not task_dirs:
        LOGGER.error("No task directories found under %s", input_root)
        return 3

    manifests: list[TaskManifest] = []
    for task_dir in task_dirs:
        manifests.append(
            prepare_task(
                task_dir=task_dir,
                dataset_id=dataset_id,
                dataset_root_out=dataset_root_out,
                repo_root=repo_root,
            )
        )

    dataset_manifest = DatasetManifest(
        dataset_id=dataset_id,
        dataset_name=args.dataset_name,
        source=str(input_root),
        prepared_at_utc=now_utc_iso(),
        language="java",
        task_count=len(manifests),
        submission_count=sum(m.submission_count for m in manifests),
        java_file_count=sum(m.java_file_count + m.original_java_file_count for m in manifests),
        tasks=[
            {
                "task_id": m.task_id,
                "task_name": m.task_name,
                "manifest_path": relative_to(dataset_root_out / "tasks" / m.task_id / "manifest.json", repo_root),
                "submissions_path": m.submissions_path,
                "base_path": m.base_path,
                "submission_count": m.submission_count,
                "java_file_count": m.java_file_count,
                "original_java_file_count": m.original_java_file_count,
            }
            for m in manifests
        ],
    )

    write_json(dataset_root_out / "manifest.json", asdict(dataset_manifest))
    print_summary(dataset_root_out, manifests)

    if manifests:
        first_task = manifests[0].task_id
        print("\nExample MOSS run:")
        print(
            f"{repo_root}/tools/external/moss/wrapper/run_moss.sh "
            f"-l java -d "
            f"'{dataset_root_out / 'tasks' / first_task / 'submissions'}'/*"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
