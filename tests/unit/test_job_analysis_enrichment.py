"""Tests for assignment-level AI and web analysis payload enrichment."""

import zipfile

from src.backend.api.server import (
    _audit_benchmark_pairs,
    _benchmark_split_guard,
    _build_ai_detection_summary,
    _build_ai_text_trust_report,
    _build_calibration_report,
    _build_fusion_debug,
    _build_reproducibility_report,
    _build_web_analysis_summary,
    _extract_zip,
    _normalize_job,
    _read_files_from_dir,
)
from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
)


def test_build_ai_detection_summary_returns_assignment_payload() -> None:
    submissions = {
        "human.py": """
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
""",
        "ai_like.py": """
# Let us implement a complete processing solution
def process_data(data):
    result = {}
    for item in data:
        result[item.get("key", "unknown")] = item.get("value", 0) * 2
    return result
""",
    }

    summary = _build_ai_detection_summary(submissions)

    assert summary["enabled"] is True
    assert summary["total_files"] == 2
    assert len(summary["submissions"]) == 2
    assert sum(summary["distribution"].values()) == 2
    assert summary["signal_summary"]
    assert (
        summary["submissions"][0]["ai_probability"]
        >= summary["submissions"][1]["ai_probability"]
    )


def test_build_web_analysis_summary_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("INTEGRITYDESK_ENABLE_WEB_ANALYSIS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
    monkeypatch.delenv("STACKEXCHANGE_API_KEY", raising=False)

    summary = _build_web_analysis_summary({"example.py": "print('hello world')"})

    assert summary["enabled"] is False
    assert summary["matched_submissions"] == 0
    assert summary["submissions"] == []
    assert "disabled in admin settings" in summary["status_message"]


def test_build_web_analysis_summary_scans_public_sources(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("STACKEXCHANGE_API_KEY", "key")
    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.WebSearchService."
        "scan_public_sources",
        lambda self, code, language, sites: {
            "web_results": [
                {
                    "name": "org/repo/stats.py",
                    "url": "https://github.com/org/repo/blob/main/stats.py",
                    "source": "github",
                    "similarity": 0.72,
                }
            ],
            "max_web_similarity": 0.72,
            "source_counts": {"github": 1},
            "configured_sources": [],
        },
    )

    summary = _build_web_analysis_summary(
        {"example.py": "def compute_weighted_average(scores, weights):\n    return 0"},
        {"source_scan_enabled": True, "source_scan_sites": []},
    )

    assert summary["enabled"] is True
    assert summary["matched_submissions"] == 1
    assert summary["highest_similarity"] == 0.72
    assert summary["source_totals"] == {"github": 1}
    assert summary["submissions"][0]["sources"][0]["name"] == "org/repo/stats.py"
    assert "Stack Overflow" in summary["status_message"]
    assert "GITHUB_TOKEN" not in summary["status_message"]


def test_build_web_analysis_summary_notes_missing_github_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "src.backend.infrastructure.indexing.web_search.WebSearchService."
        "scan_public_sources",
        lambda self, code, language, sites: {
            "web_results": [],
            "max_web_similarity": 0.0,
            "source_counts": {},
            "configured_sources": [],
        },
    )

    summary = _build_web_analysis_summary(
        {"example.py": "def compute_weighted_average(scores, weights):\n    return 0"},
        {"source_scan_enabled": True, "source_scan_sites": []},
    )

    assert summary["enabled"] is True
    assert "GITHUB_TOKEN is not configured" in summary["status_message"]


def test_normalize_job_preserves_analysis_sections() -> None:
    ai_detection = _build_ai_detection_summary({"sample.py": "print('hello world')"})
    normalized = _normalize_job(
        {
            "id": "job-123",
            "course_name": "Course",
            "assignment_name": "Assignment",
            "threshold": 0.5,
            "status": "completed",
            "results": [],
            "submissions": {"sample.py": "print('hello world')"},
            "ai_detection": ai_detection,
            "web_analysis": {
                "enabled": False,
                "configured": False,
                "status_message": "Web analysis disabled.",
                "matched_submissions": 0,
                "highest_similarity": 0,
                "average_similarity": 0,
                "source_totals": {},
                "submissions": [],
            },
        }
    )

    assert normalized["ai_detection"]["enabled"] is True
    assert normalized["ai_detection"]["total_files"] == 1
    assert normalized["web_analysis"]["enabled"] is False
    assert normalized["web_analysis"]["submissions"] == []


def test_normalize_job_exposes_history_table_aliases() -> None:
    """The history table reads total_submissions / high_similarity_count.

    Regression: the job dict carried file_count and summary.suspicious_pairs,
    but the frontend RawJob type expected total_submissions /
    high_similarity_count, so the Submissions column always showed 0 and
    High Risk always showed "—".
    """
    normalized = _normalize_job(
        {
            "id": "job-alias",
            "course_name": "Course",
            "assignment_name": "Assignment",
            "threshold": 0.7,
            "status": "completed",
            "file_count": 5,
            "results": [
                {"file_a": "a.py", "file_b": "b.py", "score": 0.91},
                {"file_a": "a.py", "file_b": "c.py", "score": 0.32},
                {"file_a": "b.py", "file_b": "c.py", "score": 0.75},
            ],
            "submissions": {"a.py": "x = 1", "b.py": "x = 2", "c.py": "x = 3"},
        }
    )

    assert normalized["total_submissions"] == 5
    # 2 of 3 pairs score >= the 0.7 threshold
    assert normalized["high_similarity_count"] == 2
    assert normalized["summary"]["suspicious_pairs"] == 2


def test_fusion_debug_logs_engine_contributions() -> None:
    """Flagged pairs should explain which engines fired."""

    class Result:
        features = {"ast": 0.8, "token": 0.2, "jplag": 0.9}
        contributions = {"ast": 0.4, "jplag": 0.35}

    debug = _build_fusion_debug(Result(), 0.75)

    assert debug["engines_fired"] == ["jplag", "ast"]
    assert debug["active_evidence"][0]["engine"] == "jplag"
    assert debug["active_evidence"][0]["fired"] is True


def test_calibration_report_includes_fpr_and_overfit_guard() -> None:
    """Professor reports should state FPR guidance and weight-tuning guardrails."""
    report = _build_calibration_report(0.78, "intro_programming")

    assert report["estimated_false_positive_rate"] == 0.02
    assert "locked test" in report["overfit_guard"]
    assert len(report["curve"]) >= 3


def test_reproducibility_report_is_deterministic() -> None:
    """Same submissions should produce the same run hash regardless of order."""
    submissions_a = {"b.py": "print(2)", "a.py": "print(1)"}
    submissions_b = {"a.py": "print(1)", "b.py": "print(2)"}

    class Mode:
        mode_id = "intro_programming"
        version = "1.0.0"

    first = _build_reproducibility_report(submissions_a, ["integritydesk"], Mode())
    second = _build_reproducibility_report(submissions_b, ["integritydesk"], Mode())

    assert first["submission_set_hash"] == second["submission_set_hash"]
    assert first["deterministic_caching"] is True


def test_ai_text_trust_report_documents_humanizer_and_false_positive_policy() -> None:
    """AI-text reporting should be cautious and benchmark-aware."""
    report = _build_ai_text_trust_report({"threshold": 0.4})

    assert report["humanizer_benchmark_required"] is True
    assert "QuillBot" in report["humanizer_tools"]
    assert "never binary accusations" in report["false_positive_policy"]


def test_benchmark_audit_detects_four_cases_and_locked_splits() -> None:
    """Benchmark audit should summarize the four case categories and split readiness."""
    raw_pairs = [
        {
            "label": 1,
            "clone_type": 1,
            "case_category": "true_positive",
            "split": "train",
        },
        {
            "label": 1,
            "clone_type": 3,
            "case_category": "edge_case",
            "split": "validation",
        },
        {
            "label": 0,
            "clone_type": 0,
            "case_category": "true_negative",
            "split": "test",
        },
        {
            "label": 0,
            "clone_type": 0,
            "case_category": "hard_negative",
            "split": "test",
        },
        {
            "label": 0,
            "clone_type": 0,
            "case_category": "hard_negative",
            "split": "validation",
        },
        {
            "label": 0,
            "clone_type": 0,
            "case_category": "hard_negative",
            "split": "train",
        },
    ]

    audit = _audit_benchmark_pairs(raw_pairs)

    assert audit["missing_case_categories"] == []
    assert audit["missing_splits"] == []
    assert audit["hard_negative_count"] == 3
    assert audit["ready_for_weight_tuning"] is True


def test_benchmark_split_guard_blocks_locked_test_tuning() -> None:
    """Locked test split cannot be used for iterative tuning."""
    blocked = _benchmark_split_guard("test", "tuning")
    allowed = _benchmark_split_guard("validation", "tuning")

    assert blocked["allowed"] is False
    assert "cannot be used" in blocked["message"]
    assert allowed["allowed"] is True


def test_compare_all_pairs_keeps_every_pair() -> None:
    """Four submissions should produce all six pairwise rows."""
    submissions = {
        "A.py": "def solve_a(x):\n    return x + 1\n",
        "B.py": "def solve_b(x):\n    return x + 2\n",
        "C.py": "def solve_c(x):\n    return x * 3\n",
        "D.py": "def solve_d(x):\n    return x - 4\n",
    }

    results = BatchDetectionService(threshold=0.99).compare_all_pairs(submissions)
    pairs = {tuple(sorted((result.file_a, result.file_b))) for result in results}

    assert len(results) == 6
    assert pairs == {
        ("A.py", "B.py"),
        ("A.py", "C.py"),
        ("A.py", "D.py"),
        ("B.py", "C.py"),
        ("B.py", "D.py"),
        ("C.py", "D.py"),
    }


def test_zip_upload_preserves_class_submission_paths(tmp_path) -> None:
    """Class ZIPs often contain repeated basenames under student folders."""
    zip_path = tmp_path / "class.zip"
    target_dir = tmp_path / "extract"
    target_dir.mkdir()
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("alice/main.py", "def solve():\n    return 'alice'\n")
        archive.writestr("bob/main.py", "def solve():\n    return 'bob'\n")
        archive.writestr("carol/main.py", "def solve():\n    return 'carol'\n")
        archive.writestr("dan/main.py", "def solve():\n    return 'dan'\n")

    extracted = _extract_zip(zip_path, target_dir)
    submissions = _read_files_from_dir(target_dir)

    assert len(extracted) == 4
    assert sorted(submissions) == ["alice.py", "bob.py", "carol.py", "dan.py"]


def test_zip_student_folders_become_one_submission_each(tmp_path) -> None:
    """A student's several files are one submission, as in MOSS and JPlag."""
    zip_path = tmp_path / "class.zip"
    target_dir = tmp_path / "extract"
    target_dir.mkdir()
    with zipfile.ZipFile(zip_path, "w") as archive:
        # A wrapper folder every file shares is the assignment, not a student.
        archive.writestr("A1/alice/main.py", "def solve():\n    return helper()\n")
        archive.writestr("A1/alice/util.py", "def helper():\n    return 'alice'\n")
        archive.writestr("A1/bob/src/main.py", "def solve():\n    return 'bob!!'\n")
        archive.writestr("A1/bob/src/io.py", "def read():\n    return input()\n")
        archive.writestr("A1/carol/main.py", "def solve():\n    return 'carol'\n")
        archive.writestr("A1/dan.py", "def solve():\n    return 'dan!!'\n")

    _extract_zip(zip_path, target_dir)
    submissions = _read_files_from_dir(target_dir)

    assert sorted(submissions) == [
        "A1__dan.py",
        "alice.py",
        "bob.py",
        "carol.py",
    ]
    assert "return helper()" in submissions["alice.py"]
    assert "return 'alice'" in submissions["alice.py"]
    assert "return input()" in submissions["bob.py"]


def test_student_folder_name_never_overwrites_a_file_submission(tmp_path) -> None:
    (tmp_path / "alice").mkdir()
    (tmp_path / "alice" / "a.py").write_text("print('folder a')\n", encoding="utf-8")
    (tmp_path / "alice" / "b.py").write_text("print('folder b')\n", encoding="utf-8")
    (tmp_path / "alice.py").write_text("print('top level')\n", encoding="utf-8")

    submissions = _read_files_from_dir(tmp_path)

    assert submissions["alice.py"] == "print('top level')\n"
    assert "folder a" in submissions["alice_2.py"]
    assert "folder b" in submissions["alice_2.py"]


def test_folder_grouping_can_be_turned_off_for_labelled_datasets(tmp_path) -> None:
    (tmp_path / "case").mkdir()
    (tmp_path / "case" / "original.py").write_text("x = 'original'\n", encoding="utf-8")
    (tmp_path / "case" / "copy.py").write_text("x = 'the copy'\n", encoding="utf-8")

    submissions = _read_files_from_dir(tmp_path, group_folders=False)

    assert sorted(submissions) == ["case__copy.py", "case__original.py"]


def test_jobs_stored_with_per_file_names_still_load_their_code(
    tmp_path, monkeypatch
) -> None:
    from types import SimpleNamespace

    from src.backend.api import server

    job_dir = tmp_path / "old-job"
    (job_dir / "alice").mkdir(parents=True)
    (job_dir / "alice" / "main.py").write_text("print('alice main')\n", encoding="utf-8")
    (job_dir / "alice" / "util.py").write_text("print('alice util')\n", encoding="utf-8")
    (job_dir / "bob.py").write_text("print('bob only')\n", encoding="utf-8")
    monkeypatch.setattr(server, "UPLOADS_DIR", tmp_path)
    old_row = SimpleNamespace(name="alice__main.py", storage_path=None, file_paths=None)
    new_row = SimpleNamespace(name="alice.py", storage_path=None, file_paths=None)

    sources = server._read_job_submission_sources("old-job", [old_row, new_row])

    assert sources["alice__main.py"] == "print('alice main')\n"
    assert "alice util" in sources["alice.py"]
