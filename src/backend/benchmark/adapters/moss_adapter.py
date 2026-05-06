"""MOSS benchmark adapter backed by the real Stanford MOSS Perl client."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.backend.benchmark.adapters.base_adapter import BaseAdapter
from src.backend.benchmark.contracts.evaluation_result import (
    EnrichedPair,
    EvaluationResult,
)
from src.backend.config.settings import settings


class MossAdapter(BaseAdapter):
    """Run the local ``moss.pl`` client and parse Stanford's HTML report."""

    SCRIPT_PATH = (
        Path(__file__).resolve().parents[4] / "tools" / "external" / "moss" / "moss.pl"
    )
    LANGUAGE_MAP = {
        "python": ("python", ".py"),
        "java": ("java", ".java"),
        "javascript": ("javascript", ".js"),
        "c": ("cc", ".c"),
        "cpp": ("cc", ".cpp"),
        "csharp": ("csharp", ".cs"),
    }

    def __init__(
        self,
        language: str = "python",
        max_matches: int = 10,
        threshold: float = 0.5,
        moss_user_id: Optional[str] = None,
    ) -> None:
        self._language = language
        self._max_matches = max_matches
        self._threshold = threshold
        self._moss_user_id = moss_user_id or settings.MOSS_USER_ID

    @property
    def name(self) -> str:
        """Return the adapter name."""
        return "moss"

    @property
    def version(self) -> str:
        """Return the adapter version."""
        return "real-moss-pl"

    def is_available(self) -> bool:
        """Return whether the local MOSS client can submit real jobs."""
        return (
            bool(self._moss_user_id)
            and self.SCRIPT_PATH.exists()
            and subprocess.run(
                ["perl", "-c", str(self.SCRIPT_PATH)],
                capture_output=True,
                text=True,
                check=False,
            ).returncode
            == 0
        )

    def evaluate(self, pair: EnrichedPair) -> EvaluationResult:
        """Evaluate a pair by submitting only those two files to MOSS."""
        metadata: Dict[str, Any] = {
            "language": getattr(pair, "language", None) or self._language,
            "max_matches": self._max_matches,
            "real_moss": True,
        }
        if not self.is_available():
            metadata["error"] = (
                "MOSS_USER_ID or tools/external/moss/moss.pl is missing."
            )
            return self._make_result(pair, 0.0, self._threshold, metadata=metadata)

        try:
            result = self._compare(
                pair.code_a,
                pair.code_b,
                language=str(metadata["language"]),
            )
            metadata.update(
                {key: value for key, value in result.items() if key != "score"}
            )
            score = float(result.get("score", 0.0))
        except Exception as exc:
            metadata["error"] = str(exc)
            score = 0.0

        return self._make_result(pair, score, self._threshold, metadata=metadata)

    def _compare(self, code_a: str, code_b: str, language: str) -> Dict[str, Any]:
        """Submit two source strings and return the parsed report score."""
        if not code_a or not code_b:
            return {"score": 0.0}

        _moss_language, extension = self._moss_language(language)
        file_a = f"a{extension}"
        file_b = f"b{extension}"
        payload = self.run_batch({file_a: code_a, file_b: code_b}, [(file_a, file_b)])
        result = payload["pairs"][0] if payload["pairs"] else {"score": 0.0}
        if "report_url" in payload and "report_url" not in result:
            result["report_url"] = payload["report_url"]
        return result

    def run_batch(
        self, submissions: Dict[str, str], pairs: Iterable[tuple[str, str]]
    ) -> Dict[str, Any]:
        """Submit grouped files to MOSS and return pair scores for requested pairs."""
        if not self.is_available():
            return {"pairs": []}

        groups: Dict[str, Dict[str, str]] = {}
        score_by_pair: Dict[str, float] = {}
        detail_by_pair: Dict[str, Dict[str, Any]] = {}
        for filename, content in submissions.items():
            groups.setdefault(self._infer_language_from_filename(filename), {})[
                filename
            ] = content

        for language, language_submissions in groups.items():
            if len(language_submissions) < 2:
                continue
            moss_language, _extension = self._moss_language(language)
            report_url, html, written_paths = self._submit_group(
                language_submissions, moss_language
            )
            if not report_url or not html:
                continue

            path_to_filename = {
                path: filename for filename, path in written_paths.items()
            }
            for left_path, left_pct, right_path, right_pct in self._parse_report_rows(
                html
            ):
                left_name = path_to_filename.get(left_path)
                right_name = path_to_filename.get(right_path)
                if not left_name or not right_name:
                    continue

                left_pct_val = float(left_pct)
                right_pct_val = float(right_pct)
                similarity = min(left_pct_val, right_pct_val) / 100.0
                pair_key = self._pair_key(left_name, right_name)
                score_by_pair[pair_key] = max(
                    score_by_pair.get(pair_key, 0.0), similarity
                )
                detail_by_pair[pair_key] = {
                    "file_a_percent": left_pct_val / 100.0,
                    "file_b_percent": right_pct_val / 100.0,
                    "report_url": report_url,
                }

        results = []
        for file_a, file_b in pairs:
            pair_key = self._pair_key(file_a, file_b)
            results.append(
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "score": score_by_pair.get(pair_key, 0.0),
                    **detail_by_pair.get(pair_key, {}),
                }
            )

        report_urls = sorted(
            {
                str(detail.get("report_url"))
                for detail in detail_by_pair.values()
                if detail.get("report_url")
            }
        )
        payload: Dict[str, Any] = {"pairs": results}
        if report_urls:
            payload["report_url"] = report_urls[0]
        return payload

    def _submit_group(
        self, submissions: Dict[str, str], moss_language: str
    ) -> tuple[Optional[str], str, Dict[str, str]]:
        """Submit one language group to MOSS and return report HTML."""
        with tempfile.TemporaryDirectory(prefix="moss-adapter-") as temp_dir:
            run_dir = Path(temp_dir)
            source_root = run_dir / "subs"
            source_root.mkdir(parents=True, exist_ok=True)
            written_paths = self._write_submissions(source_root, submissions)
            run_script = self._patched_script(run_dir)

            env = os.environ.copy()
            env["MOSS_USER_ID"] = str(self._moss_user_id)
            env["MOSS_LOGFILE"] = str(run_dir / "moss.log")
            process = subprocess.run(
                [
                    "perl",
                    str(run_script),
                    "-l",
                    moss_language,
                    "-m",
                    str(self._max_matches),
                    *written_paths.values(),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
                cwd=str(self.SCRIPT_PATH.parent),
                env=env,
            )
            if process.returncode != 0:
                raise RuntimeError(
                    process.stderr.strip()
                    or process.stdout.strip()
                    or "MOSS execution failed"
                )

            report_url = self._extract_report_url(process.stdout)
            if not report_url:
                return None, "", written_paths

            html = self._fetch_report(report_url)
            return report_url, html, written_paths

    def _moss_language(self, language: str) -> tuple[str, str]:
        """Map benchmark language names to MOSS language and file extension."""
        normalized = language.lower()
        if normalized not in self.LANGUAGE_MAP:
            normalized = self._language.lower()
        return self.LANGUAGE_MAP.get(normalized, self.LANGUAGE_MAP["python"])

    def _patched_script(self, run_dir: Path) -> Path:
        """Create a writable, credential-injected copy of ``moss.pl``."""
        run_dir.mkdir(parents=True, exist_ok=True)
        run_script = run_dir / "moss.pl"
        script_text = self.SCRIPT_PATH.read_text(encoding="utf-8")
        safe_user_id = re.sub(r"[^0-9]", "", str(self._moss_user_id or "")) or "0"
        log_literal = repr(str(run_dir / "moss.log"))

        script_text = re.sub(
            r"my\s+\$logfile\s*=\s*[^;]+;",
            f"my $logfile = $ENV{{'MOSS_LOGFILE'}} || {log_literal};",
            script_text,
            count=1,
        )
        script_text = re.sub(
            r"\$userid\s*=\s*[^;]+;",
            "$userid = $ENV{'MOSS_USER_ID'} || " f"{safe_user_id};",
            script_text,
            count=1,
        )
        script_text = script_text.replace(
            'system("bash", "save_moss_report.sh","$logfile");',
            'system("bash", "save_moss_report.sh", "$logfile") '
            'if -e "save_moss_report.sh";',
        )

        run_script.write_text(script_text, encoding="utf-8")
        run_script.chmod(0o700)
        return run_script

    def _write_submissions(
        self, source_root: Path, submissions: Dict[str, str]
    ) -> Dict[str, str]:
        """Write submissions to a temporary directory and return path mapping."""
        written_paths: Dict[str, str] = {}
        for index, (filename, content) in enumerate(sorted(submissions.items())):
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).name)
            target = source_root / f"{index:04d}_{safe_name}"
            target.write_text(content, encoding="utf-8")
            written_paths[filename] = str(target)
        return written_paths

    def _extract_report_url(self, output: str) -> Optional[str]:
        """Extract the Stanford report URL from MOSS stdout."""
        match = re.search(r"https?://moss\.stanford\.edu/results/[^\s]+", output)
        return match.group(0).rstrip("/") if match else None

    def _fetch_report(self, report_url: str) -> str:
        """Fetch a MOSS HTML report."""
        with urllib.request.urlopen(f"{report_url}/", timeout=30) as response:
            return response.read().decode("utf-8", "ignore")

    def _parse_report_score(self, html: str) -> float:
        """Parse the first pair score from a MOSS report table."""
        scores = [
            min(float(left_pct), float(right_pct)) / 100.0
            for _left, left_pct, _right, right_pct in self._parse_report_rows(html)
        ]
        return max(scores) if scores else 0.0

    def _parse_report_rows(self, html: str) -> list[tuple[str, str, str, str]]:
        """Parse MOSS report rows as path and percent tuples."""
        row_pattern = re.compile(
            r'<TR><TD><A HREF="[^"]+">([^<]+) \((\d+)%\)</A>\s*'
            r'<TD><A HREF="[^"]+">([^<]+) \((\d+)%\)</A>',
            re.IGNORECASE,
        )
        return row_pattern.findall(html)

    def _infer_language_from_filename(self, filename: str) -> str:
        """Infer a MOSS-supported language from a filename."""
        suffix = Path(filename).suffix.lower()
        if suffix == ".py":
            return "python"
        if suffix == ".java":
            return "java"
        if suffix == ".js":
            return "javascript"
        if suffix in {".c", ".h"}:
            return "c"
        if suffix in {".cc", ".cpp", ".cxx", ".hpp"}:
            return "cpp"
        if suffix == ".cs":
            return "csharp"
        return self._language

    def _pair_key(self, file_a: str, file_b: str) -> str:
        """Build a stable unordered pair key."""
        return "::".join(sorted((file_a, file_b)))


def run_moss_batch(
    submissions: Dict[str, str],
    pairs: Iterable[tuple[str, str]],
    moss_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the canonical MOSS batch adapter used by benchmark APIs."""
    return MossAdapter(moss_user_id=moss_user_id).run_batch(submissions, pairs)
