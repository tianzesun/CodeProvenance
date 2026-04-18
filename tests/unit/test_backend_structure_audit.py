"""Tests for the backend structure audit helpers."""

from pathlib import Path

from scripts.backend_structure_audit import (
    count_critical_duplicates,
    count_python_files,
    find_bootstrap_disabled_importers,
    find_duplicate_basenames,
)


def test_find_duplicate_basenames_ignores_unique_files(tmp_path: Path) -> None:
    """Duplicate basename detection should only return repeated Python filenames."""
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    alpha.mkdir()
    beta.mkdir()
    (alpha / "report_generator.py").write_text('"""alpha"""', encoding="utf-8")
    (beta / "report_generator.py").write_text('"""beta"""', encoding="utf-8")
    (beta / "unique.py").write_text('"""unique"""', encoding="utf-8")

    duplicates = find_duplicate_basenames(tmp_path)

    assert set(duplicates) == {"report_generator.py"}


def test_count_critical_duplicates_filters_non_critical_names() -> None:
    """Only policy-controlled basenames should be included as critical duplicates."""
    duplicates = {
        "report_generator.py": [Path("a"), Path("b")],
        "__init__.py": [Path("c"), Path("d")],
    }

    critical = count_critical_duplicates(duplicates)

    assert list(critical) == ["report_generator.py"]


def test_count_python_files_counts_python_only(tmp_path: Path) -> None:
    """File counts should ignore non-Python artifacts."""
    (tmp_path / "one.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "two.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# docs\n", encoding="utf-8")

    assert count_python_files(tmp_path) == 2


def test_find_bootstrap_disabled_importers_limits_to_production_roots(
    tmp_path: Path,
) -> None:
    """Only production modules should be flagged for bootstrap imports."""
    api_dir = tmp_path / "api"
    benchmark_dir = tmp_path / "benchmark"
    api_dir.mkdir()
    benchmark_dir.mkdir()
    (api_dir / "server.py").write_text(
        "from src.backend.bootstrap_disabled import get_container\n",
        encoding="utf-8",
    )
    (benchmark_dir / "runner.py").write_text(
        "from src.backend.bootstrap_disabled import get_container\n",
        encoding="utf-8",
    )

    importers = find_bootstrap_disabled_importers(tmp_path)

    assert importers == [api_dir / "server.py"]
