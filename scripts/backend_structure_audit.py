#!/usr/bin/env python3
"""Audit the backend package for structural drift.

This script reports duplicate Python basenames, legacy directories that should
be quarantined, and benchmark/evaluation code that still lives under the
production backend package tree.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "src" / "backend"
LEGACY_DIRECTORIES = {
    "bootstrap_disabled": "Deprecated bootstrap code that should not be used by production paths.",
}
PRODUCTION_TREE_EXCEPTIONS = {
    "benchmark": "Benchmark code is still imported from production paths and needs migration shims before moving.",
    "evaluation": "Evaluation modules overlap with benchmark concerns and need consolidation.",
    "evalforge": "Experimental evaluation framework overlapping with benchmark/evaluation packages.",
}
CRITICAL_DUPLICATE_BASENAMES = {
    "report_generator.py",
    "ast_similarity.py",
    "winnowing_similarity.py",
    "token_similarity.py",
    "database.py",
    "ai_detection.py",
    "config.py",
    "registry.py",
    "runner.py",
    "loader.py",
}
PRODUCTION_IMPORT_ROOTS = {
    "api",
    "application",
    "config",
    "contracts",
    "core",
    "domain",
    "engines",
    "infrastructure",
    "integrations",
    "models",
    "pipeline",
    "services",
    "utils",
    "workers",
}


def iter_python_files(root: Path) -> Iterable[Path]:
    """Yield Python files under ``root`` excluding caches."""
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def find_duplicate_basenames(root: Path) -> dict[str, list[Path]]:
    """Return duplicated Python basenames under ``root``."""
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in iter_python_files(root):
        grouped[path.name].append(path)
    return {
        basename: sorted(paths) for basename, paths in grouped.items() if len(paths) > 1
    }


def count_python_files(root: Path) -> int:
    """Return the number of Python files under ``root``."""
    return sum(1 for _ in iter_python_files(root))


def count_critical_duplicates(
    duplicate_basenames: dict[str, list[Path]],
) -> dict[str, list[Path]]:
    """Return only the duplicate basenames that are risky for backend maintenance."""
    return {
        basename: paths
        for basename, paths in duplicate_basenames.items()
        if basename in CRITICAL_DUPLICATE_BASENAMES
    }


def find_bootstrap_disabled_importers(root: Path) -> list[Path]:
    """Find production modules that import the deprecated bootstrap package."""
    importers: list[Path] = []
    for path in iter_python_files(root):
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] not in PRODUCTION_IMPORT_ROOTS:
            continue

        content = path.read_text(encoding="utf-8")
        if "bootstrap_disabled" in content:
            importers.append(path)

    return sorted(importers)


def format_paths(paths: Iterable[Path]) -> list[str]:
    """Convert paths to repo-relative strings."""
    return [str(path.relative_to(REPO_ROOT)) for path in paths]


def main() -> int:
    """Run the audit and print a concise report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit non-zero when duplicate basenames or legacy directories are found.",
    )
    args = parser.parse_args()

    duplicate_basenames = find_duplicate_basenames(BACKEND_ROOT)
    critical_duplicates = count_critical_duplicates(duplicate_basenames)
    legacy_hits = {
        name: BACKEND_ROOT / name
        for name in LEGACY_DIRECTORIES
        if (BACKEND_ROOT / name).exists()
    }
    production_tree_hits = {
        name: BACKEND_ROOT / name
        for name in PRODUCTION_TREE_EXCEPTIONS
        if (BACKEND_ROOT / name).exists()
    }
    production_python_file_counts = {
        name: count_python_files(path)
        for name, path in sorted(production_tree_hits.items())
    }
    legacy_python_file_counts = {
        name: count_python_files(path) for name, path in sorted(legacy_hits.items())
    }
    bootstrap_importers = find_bootstrap_disabled_importers(BACKEND_ROOT)
    duplicate_counter = Counter(
        {basename: len(paths) for basename, paths in duplicate_basenames.items()}
    )

    print("Backend structure audit")
    print(f"- backend root: {BACKEND_ROOT.relative_to(REPO_ROOT)}")
    print(f"- duplicate basenames: {len(duplicate_basenames)}")
    print(f"- critical duplicate basenames: {len(critical_duplicates)}")
    print(f"- legacy directories: {len(legacy_hits)}")
    print(
        f"- production-tree benchmark/evaluation directories: {len(production_tree_hits)}"
    )
    print(f"- production imports of bootstrap_disabled: {len(bootstrap_importers)}")

    if critical_duplicates:
        print("\nCritical duplicate basenames")
        for basename, count in duplicate_counter.most_common():
            if basename not in critical_duplicates:
                continue
            print(f"- {basename}: {count}")
            for path in format_paths(critical_duplicates[basename]):
                print(f"  - {path}")

    if duplicate_basenames:
        print("\nMost duplicated basenames")
        for basename, count in duplicate_counter.most_common(15):
            print(f"- {basename}: {count}")

    if legacy_hits:
        print("\nLegacy directories")
        for name, path in sorted(legacy_hits.items()):
            python_file_count = legacy_python_file_counts[name]
            print(
                f"- {path.relative_to(REPO_ROOT)}: "
                f"{LEGACY_DIRECTORIES[name]} ({python_file_count} Python files)"
            )

    if production_tree_hits:
        print("\nProduction-tree benchmark/evaluation directories")
        for name, path in sorted(production_tree_hits.items()):
            python_file_count = production_python_file_counts[name]
            print(
                f"- {path.relative_to(REPO_ROOT)}: "
                f"{PRODUCTION_TREE_EXCEPTIONS[name]} ({python_file_count} Python files)"
            )

    if bootstrap_importers:
        print("\nProduction imports of bootstrap_disabled")
        for path in format_paths(bootstrap_importers):
            print(f"- {path}")

    if args.fail_on_findings and duplicate_basenames:
        print("\nAll duplicate basenames")
        for basename, paths in sorted(duplicate_basenames.items()):
            print(f"- {basename}")
            for path in format_paths(paths):
                print(f"  - {path}")

    has_findings = bool(critical_duplicates or legacy_hits or bootstrap_importers)
    return 1 if args.fail_on_findings and has_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
