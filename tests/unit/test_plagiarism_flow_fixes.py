"""Regression tests for Plagiarism Checker upload, job and review handling."""

import asyncio
import zipfile

import pytest
from fastapi import HTTPException

from src.backend.api import server

CODE = "def solve(values):\n    return sorted(values)\n"


def test_uppercase_extensions_are_read(tmp_path) -> None:
    (tmp_path / "Alice.PY").write_text(CODE)
    (tmp_path / "Bob.Java").write_text("class Bob { int x = 1; int y = 2; }\n")

    assert len(server._read_files_from_dir(tmp_path)) == 2


def test_macos_archive_junk_is_not_extracted(tmp_path) -> None:
    archive = tmp_path / "upload.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("sub/carol.py", CODE)
        zf.writestr("__MACOSX/sub/._carol.py", b"\x00\x05\x16\x07binary")
        zf.writestr("sub/._dave.py", b"\x00\x05\x16\x07binary")
    out = tmp_path / "out"
    out.mkdir()

    extracted = server._extract_zip(archive, out)

    assert [p.replace(str(out), "") for p in extracted] == ["/sub/carol.py"]


def test_too_few_files_fails_the_job_visibly(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server, "_jobs", {})
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(server, "_update_job_status_in_db", lambda *a, **k: None)
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "only.py").write_text(CODE)

    asyncio.run(
        server._run_analysis(
            "job-few", job_dir, "C", "A", None, "", 0.5, None, "", "", []
        )
    )

    job = server._jobs["job-few"]
    assert job["status"] == "failed"
    assert "At least 2 code files" in job["error"]


def test_analysis_failure_does_not_expose_the_exception(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server, "_jobs", {})
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(server, "_update_job_status_in_db", lambda *a, **k: None)

    def boom(*args, **kwargs):
        raise RuntimeError("password=hunter2 at /srv/secret/path.py")

    monkeypatch.setattr(server, "_read_files_from_dir", boom)
    job_dir = tmp_path / "job"
    job_dir.mkdir()

    asyncio.run(
        server._run_analysis(
            "job-boom", job_dir, "C", "A", None, "", 0.5, None, "", "", []
        )
    )

    job = server._jobs["job-boom"]
    assert job["status"] == "failed"
    assert "hunter2" not in str(job)
    assert "job-boom" in job["error"]


def _pairs(*statuses_and_scores):
    return [
        {"file_a": f"a{i}", "file_b": f"b{i}", "score": score, "review_status": status}
        for i, (status, score) in enumerate(statuses_and_scores)
    ]


@pytest.mark.parametrize(
    ("pairs", "expected"),
    [
        (_pairs(("confirmed", 0.9), ("dismissed", 0.8)), "confirmed"),
        (_pairs(("dismissed", 0.9), ("escalated", 0.8)), "escalated"),
        (_pairs(("dismissed", 0.9), ("unreviewed", 0.8)), "needs_review"),
        (_pairs(("dismissed", 0.9), ("dismissed", 0.8)), "dismissed"),
        (_pairs(("unreviewed", 0.9)), "unreviewed"),
        # Pairs below the threshold do not hold the job open.
        (_pairs(("dismissed", 0.9), ("unreviewed", 0.1)), "dismissed"),
    ],
)
def test_job_status_is_derived_from_flagged_pairs(pairs, expected) -> None:
    assert server._derive_job_review_status(pairs, 0.5) == expected


@pytest.mark.parametrize(
    "raw",
    [
        {"a::b": {"status": "made_up"}},
        {"a::b": {"notes": 5}},
        {"a::b": "confirmed"},
        ["a::b"],
    ],
)
def test_invalid_pair_reviews_are_rejected(raw) -> None:
    with pytest.raises(HTTPException) as excinfo:
        server._validated_pair_reviews(raw)
    assert excinfo.value.status_code == 400


def test_pair_reviews_accept_legacy_keys_and_strip_notes() -> None:
    cleaned = server._validated_pair_reviews(
        {"a::b": {"review_status": "confirmed", "review_notes": "  same bug  "}}
    )

    assert cleaned == {"a::b": {"status": "confirmed", "notes": "same bug"}}
