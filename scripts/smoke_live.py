#!/usr/bin/env python3
"""Release smoke test: walk the professor workflow against a running deployment.

Talks to the site over HTTPS exactly like the browser does (TLS verification
stays on), so it catches deployment faults the in-process tests cannot: stale
frontend builds, proxy routing, a backend that never came up, a dead worker.

Without credentials it runs as a guest (jobs live in memory only and nothing is
written to the database). With ``SMOKE_EMAIL`` / ``SMOKE_PASSWORD`` it signs in
as that account, also checks the signed-in pages, and deletes the checks it
created. ``SMOKE_EMAIL2`` / ``SMOKE_PASSWORD2`` (a second account in the same
workspace) add a privacy check: that account must not be able to open them.

Usage:
    python scripts/smoke_live.py [--base-url URL] [--with-case]

``--with-case`` also opens a case on the copied pair; cases cannot be deleted
through the API, so it is off by default.

Exit code is 0 when every check passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
import zipfile
from urllib.parse import urljoin

import requests

DEFAULT_BASE_URL = "https://neurosmx10.utsc.utoronto.ca/codeprovenance"
JOB_TIMEOUT_SECONDS = 300
FINAL_STATUSES = {"completed", "failed", "cancelled"}

ORIGINAL = """def mean(values):
    total = 0
    for value in values:
        total += value
    return total / len(values)


def variance(values):
    avg = mean(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


print(mean([1, 2, 3]), variance([1, 2, 3]))
"""

# Renamed identifiers only: the classic copy a detector must catch.
RENAMED_COPY = """def mean(nums):
    acc = 0
    for n in nums:
        acc += n
    return acc / len(nums)


def variance(nums):
    m = mean(nums)
    return sum((n - m) ** 2 for n in nums) / len(nums)


print(mean([1, 2, 3]), variance([1, 2, 3]))
"""

UNRELATED = """import math


def circle_area(radius):
    return math.pi * radius ** 2


for r in range(1, 4):
    print(r, round(circle_area(r), 2))
"""

# Instructor-provided scaffold both students keep verbatim.
STARTER = '''import csv
import sys


def load_rows(path):
    """Read the assignment CSV into a list of dicts."""
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def print_report(rows, title):
    """Print rows as an aligned table under a title."""
    print("=" * 40)
    print(title)
    print("=" * 40)
    for row in rows:
        print(" | ".join(f"{key}: {value}" for key, value in row.items()))


def main(argv):
    if len(argv) != 2:
        print("usage: report.py data.csv")
        return 1
    rows = load_rows(argv[1])
    print_report(summarize(rows), "Summary")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''

STUDENT_X = STARTER + '''

def summarize(rows):
    by_city = {}
    for row in rows:
        by_city.setdefault(row["city"], []).append(float(row["temp"]))
    return [{"city": c, "max": max(t)} for c, t in sorted(by_city.items())]
'''

STUDENT_Y = STARTER + '''

def summarize(rows):
    counts = {}
    for record in rows:
        key = record.get("department", "unknown").strip().lower()
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [{"department": name, "staff": n} for name, n in ranked]
'''


# STUDENT_Y's own code with names changed: copying hidden under shared starter code.
STUDENT_Y_COPY = (
    STUDENT_Y.replace("counts", "tally").replace("record", "entry").replace("ranked", "ordered")
)


class Smoke:
    """Runs checks against one deployment and records pass/fail lines."""

    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.failures: list[str] = []
        self.created_jobs: list[str] = []
        # The workspace default the upload page applies; replaced after sign-in.
        self.threshold = 0.82

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" ({detail})" if detail else ""))
        if not ok:
            self.failures.append(name)
        return ok

    def url(self, path: str) -> str:
        return f"{self.base}{path}"

    # -- steps -----------------------------------------------------------

    def frontend(self) -> None:
        page = self.session.get(self.url(""), timeout=30)
        self.check("dashboard page loads", page.status_code == 200, f"HTTP {page.status_code}")
        assets = re.findall(r'(/[^"\']*_next/static/chunks/[^"\']+\.(?:js|css))', page.text)
        if not self.check("page references build assets", bool(assets)):
            return
        # One script and one stylesheet: a stale build 404s these as text/plain.
        expected = {"js": "javascript", "css": "text/css"}
        for kind, content_kind in expected.items():
            asset = next((a for a in assets if a.endswith(f".{kind}")), None)
            if asset is None:
                continue
            resp = self.session.get(urljoin(page.url, asset), timeout=30)
            content_type = resp.headers.get("content-type", "")
            self.check(
                f"build asset serves ({kind})",
                resp.status_code == 200 and content_kind in content_type,
                f"HTTP {resp.status_code} {content_type}",
            )

    def sign_in(self, email: str | None, password: str | None) -> bool:
        if email:
            resp = self.session.post(
                self.url("/api/auth/login"), json={"email": email, "password": password}, timeout=30
            )
            label = "sign in"
        else:
            resp = self.session.post(self.url("/api/auth/guest"), timeout=30)
            label = "guest sign in"
        if not self.check(label, resp.status_code == 200, f"HTTP {resp.status_code}"):
            return False
        me = self.session.get(self.url("/api/auth/me"), timeout=30)
        if not self.check("session is recognised (/api/auth/me)", me.status_code == 200, f"HTTP {me.status_code}"):
            return False
        upload_settings = self.session.get(self.url("/api/upload-settings"), timeout=30)
        if self.check("upload settings load", upload_settings.status_code == 200, f"HTTP {upload_settings.status_code}"):
            self.threshold = float(upload_settings.json().get("default_threshold", self.threshold))
            print(f"       using the workspace default threshold {self.threshold}")
        return True

    def run_job(self, label: str, files: dict[str, str], starter: dict[str, str] | None = None,
                zipped: bool = False) -> dict | None:
        data = {"threshold": str(self.threshold), "course_name": "Smoke Test", "assignment_name": label}
        if zipped:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                for name, code in files.items():
                    archive.writestr(f"submissions/{name}", code)
            upload = [("file", ("submissions.zip", buffer.getvalue(), "application/zip"))]
            endpoint = "/api/upload-zip"
        else:
            upload = [("files", (name, code, "text/x-python")) for name, code in files.items()]
            endpoint = "/api/upload"
        upload += [("starter_files", (name, code, "text/x-python")) for name, code in (starter or {}).items()]
        resp = self.session.post(self.url(endpoint), files=upload, data=data, timeout=120)
        job_id = resp.json().get("job_id") if resp.status_code == 200 else None
        if not self.check(f"{label}: upload accepted", bool(job_id), f"HTTP {resp.status_code} {resp.text[:200]}"):
            return None
        self.created_jobs.append(job_id)
        started = time.time()
        job: dict = {}
        while time.time() - started < JOB_TIMEOUT_SECONDS:
            job = self.session.get(self.url(f"/api/job/{job_id}"), timeout=30).json()
            if job.get("status") in FINAL_STATUSES:
                break
            time.sleep(3)
        elapsed = int(time.time() - started)
        ok = job.get("status") == "completed"
        self.check(f"{label}: analysis completes", ok,
                   f"status={job.get('status')} after {elapsed}s" + (f", error={job.get('error')}" if job.get("error") else ""))
        return job if ok else None

    @staticmethod
    def pair_score(job: dict, a: str, b: str) -> float | None:
        for result in job.get("results") or []:
            if {result.get("file_a"), result.get("file_b")} == {a, b}:
                return float(result.get("score") or 0.0)
        return None

    def detection(self) -> dict | None:
        job = self.run_job("detection", {"original.py": ORIGINAL, "renamed_copy.py": RENAMED_COPY,
                                         "unrelated.py": UNRELATED})
        if not job:
            return None
        copied = self.pair_score(job, "original.py", "renamed_copy.py")
        clean = self.pair_score(job, "original.py", "unrelated.py")
        self.check("renamed copy is flagged", copied is not None and copied >= 0.8, f"score={copied}")
        self.check("unrelated pair stays below threshold", clean is not None and clean < self.threshold,
                   f"score={clean}")
        ai = job.get("ai_detection") or {}
        self.check("AI detection ran on every file", ai.get("enabled") is True and ai.get("total_files") == 3,
                   f"method={ai.get('method')}, files={ai.get('total_files')}")
        return job

    def starter_code(self) -> None:
        files = {"student_x.py": STUDENT_X, "student_y.py": STUDENT_Y, "student_y_copy.py": STUDENT_Y_COPY}
        without = self.run_job("starter: without starter", files)
        with_starter = self.run_job("starter: with starter", files, starter={"report.py": STARTER})
        if not (without and with_starter):
            return
        before = self.pair_score(without, "student_x.py", "student_y.py")
        after = self.pair_score(with_starter, "student_x.py", "student_y.py")
        self.check("starter code lowers the shared-scaffold score",
                   before is not None and after is not None and after < before - 0.1,
                   f"without={before}, with={after}")
        self.check("shared starter alone is not flagged", after is not None and after < self.threshold,
                   f"score={after}")
        hidden = self.pair_score(with_starter, "student_y.py", "student_y_copy.py")
        self.check("copy under shared starter is still flagged", hidden is not None and hidden >= self.threshold,
                   f"score={hidden}")

    def zip_upload(self) -> None:
        job = self.run_job("zip upload", {"original.py": ORIGINAL, "renamed_copy.py": RENAMED_COPY,
                                          "unrelated.py": UNRELATED}, zipped=True)
        if job:
            self.check("zip upload finds all submissions", len(job.get("results") or []) == 3,
                       f"{len(job.get('results') or [])} pairs")

    def reports(self, job: dict) -> None:
        job_id = job["id"]
        expected = {
            f"/report/{job_id}/download": "text/html",
            f"/report/{job_id}/download-json": "application/json",
            f"/report/{job_id}/download-pdf": "application/pdf",
            f"/report/{job_id}/download-csv": "text/csv",
            f"/dossier/{job_id}/download-pdf": "application/pdf",
        }
        for path, content_type in expected.items():
            resp = self.session.get(self.url(path), timeout=180)
            got = resp.headers.get("content-type", "")
            self.check(f"report {path.replace(job_id, '<job>')}",
                       resp.status_code == 200 and content_type in got and len(resp.content) > 200,
                       f"HTTP {resp.status_code} {got} {len(resp.content)}B")

    def signed_in_pages(self, job: dict, with_case: bool) -> None:
        for path in ("/api/courses", "/api/jobs", "/api/cases"):
            resp = self.session.get(self.url(path), timeout=30)
            self.check(f"GET {path}", resp.status_code == 200, f"HTTP {resp.status_code}")
        if with_case:
            resp = self.session.post(self.url("/api/cases/from-pair"), timeout=30, json={
                "job_id": job["id"], "file_a": "original.py", "file_b": "renamed_copy.py"})
            self.check("open a case on the copied pair", resp.status_code in (200, 201),
                       f"HTTP {resp.status_code} {resp.text[:200]}")

    def privacy(self, job: dict, email: str, password: str) -> None:
        other = requests.Session()
        resp = other.post(self.url("/api/auth/login"), json={"email": email, "password": password}, timeout=30)
        if not self.check("second account signs in", resp.status_code == 200, f"HTTP {resp.status_code}"):
            return
        for path in (f"/api/job/{job['id']}", f"/report/{job['id']}/download-pdf"):
            resp = other.get(self.url(path), timeout=60)
            self.check(f"second account cannot open {path.replace(job['id'], '<job>')}",
                       resp.status_code in (403, 404), f"HTTP {resp.status_code}")

    def cleanup(self) -> None:
        for job_id in self.created_jobs:
            resp = self.session.delete(self.url(f"/api/job/{job_id}"), timeout=60)
            self.check(f"delete check {job_id[:8]}", resp.status_code in (200, 204), f"HTTP {resp.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=os.environ.get("SMOKE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--with-case", action="store_true", help="also open a case (not deletable)")
    args = parser.parse_args()

    email, password = os.environ.get("SMOKE_EMAIL"), os.environ.get("SMOKE_PASSWORD")
    smoke = Smoke(args.base_url)
    print(f"Smoke test against {smoke.base} as {'signed-in user' if email else 'guest'}\n")
    try:
        smoke.frontend()
        if smoke.sign_in(email, password):
            job = smoke.detection()
            smoke.starter_code()
            smoke.zip_upload()
            if job:
                smoke.reports(job)
                if email:
                    smoke.signed_in_pages(job, args.with_case)
                    if os.environ.get("SMOKE_EMAIL2"):
                        smoke.privacy(job, os.environ["SMOKE_EMAIL2"], os.environ.get("SMOKE_PASSWORD2", ""))
    except requests.RequestException as exc:
        smoke.check("site reachable", False, type(exc).__name__)
    finally:
        if email:
            smoke.cleanup()

    print(f"\n{len(smoke.failures)} check(s) failed" if smoke.failures else "\nAll checks passed")
    return 1 if smoke.failures else 0


if __name__ == "__main__":
    sys.exit(main())
