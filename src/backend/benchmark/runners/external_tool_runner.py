"""Runner for dashboard external plagiarism-tool benchmarks."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.backend.benchmark.adapters.dolos_adapter import run_dolos_batch
from src.backend.benchmark.adapters.jplag_adapter import run_jplag_batch
from src.backend.benchmark.adapters.moss_adapter import run_moss_batch
from src.backend.benchmark.adapters.pmd_adapter import run_pmd_batch

logger = logging.getLogger(__name__)


SubmissionMap = Dict[str, str]
PairList = List[Tuple[str, str]]
ToolResult = Dict[str, Any]


class ExternalToolRunner:
    """Run selected external benchmark tools and normalize pair scores."""

    def __init__(
        self,
        tools_dir: Optional[Path] = None,
        moss_user_id: str = "",
    ) -> None:
        self.tools_dir = tools_dir or Path(__file__).resolve().parents[4] / "tools"
        self.external_tools_dir = self.tools_dir / "external"
        self.moss_user_id = moss_user_id

    def run_selected_tools(
        self,
        tool_ids: Iterable[str],
        submissions: SubmissionMap,
        pairs: PairList,
    ) -> Dict[str, ToolResult]:
        """Run non-IntegrityDesk tools and preserve per-tool failures."""
        results: Dict[str, ToolResult] = {}
        for tool_id in tool_ids:
            normalized_tool_id = str(tool_id).strip().lower()
            if normalized_tool_id == "integritydesk":
                continue

            started = time.perf_counter()
            try:
                score_data = self.run_tool(normalized_tool_id, submissions, pairs)
                results[normalized_tool_id] = score_data or {
                    "error": f"{normalized_tool_id} not available"
                }
            except Exception as exc:
                logger.exception(
                    "External tool %s failed during benchmark", normalized_tool_id
                )
                results[normalized_tool_id] = {"error": str(exc)}
            finally:
                results.setdefault(normalized_tool_id, {})
                results[normalized_tool_id]["runtime_seconds"] = round(
                    time.perf_counter() - started, 4
                )
        return results

    def run_tool(
        self,
        tool_id: str,
        submissions: SubmissionMap,
        pairs: PairList,
        progress_cb=None,
    ) -> Optional[ToolResult]:
        """Run one external tool and return normalized pair scores."""
        if tool_id == "moss":
            if not self.moss_user_id:
                return None
            return run_moss_batch(
                submissions,
                pairs,
                moss_user_id=self.moss_user_id,
                progress_cb=progress_cb,
            )
        if tool_id == "dolos":
            return run_dolos_batch(submissions, pairs, progress_cb=progress_cb)
        if tool_id == "jplag":
            return run_jplag_batch(submissions, pairs, progress_cb=progress_cb)
        if tool_id == "nicad":
            return self._run_nicad(submissions, pairs, progress_cb=progress_cb)
        if tool_id == "pmd":
            return run_pmd_batch(submissions, pairs, progress_cb=progress_cb)
        if tool_id == "sherlock":
            return self._run_sherlock(submissions, pairs, progress_cb=progress_cb)
        return None

    def _find_tool_dir(self, tool_id: str) -> Optional[Path]:
        """Resolve a benchmark tool directory from canonical and legacy paths."""
        candidates: Dict[str, List[Path]] = {
            "nicad": [
                self.external_tools_dir / "nicad",
                self.external_tools_dir / "NiCad-6.2",
                self.tools_dir / "NiCad-6.2",
                self.tools_dir / "nicad",
            ],
            "sherlock": [
                self.external_tools_dir / "sherlock",
                self.tools_dir / "sherlock",
            ],
        }
        for candidate in candidates.get(tool_id, []):
            if candidate.exists():
                return candidate
        return None

    def _find_nicad_executable(self) -> Optional[Path]:
        """Find a NiCad executable in the configured tool location."""
        nicad_dir = self._find_tool_dir("nicad")
        if not nicad_dir:
            return None
        for candidate in [nicad_dir / "nicad6", nicad_dir / "bin" / "nicad"]:
            if candidate.exists():
                return candidate
        return None

    def _find_txl_executable(self) -> Optional[Path]:
        """Find a TXL executable used by NiCad."""
        nicad_dir = self._find_tool_dir("nicad")
        candidates: List[Path] = []
        if nicad_dir:
            candidates.extend(
                [
                    nicad_dir / "txl",
                    nicad_dir / "bin" / "txl",
                    nicad_dir / "lib" / "nicad" / "txl",
                    nicad_dir / "tools" / "txl",
                ]
            )
        candidates.extend(
            [
                self.tools_dir / "freetxl" / "current" / "bin" / "txl",
                self.external_tools_dir / "freetxl" / "current" / "bin" / "txl",
            ]
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _run_nicad(
        self,
        submissions: SubmissionMap,
        pairs: PairList,
        progress_cb=None,
    ) -> Optional[ToolResult]:
        """Run NiCad and convert clone-class XML output to pair scores."""
        _ = progress_cb
        nicad_path = self._find_nicad_executable()
        txl_path = self._find_txl_executable()
        if not nicad_path or not txl_path:
            return None

        groups: Dict[str, SubmissionMap] = {}
        score_by_pair: Dict[str, float] = {}
        language_map = {
            "python": "py",
            "java": "java",
            "csharp": "cs",
            "php": "php",
            "ruby": "rb",
            "swift": "swift",
            "rust": "rs",
        }

        for filename, content in submissions.items():
            groups.setdefault(self._infer_language(filename), {})[filename] = content

        for language, language_submissions in groups.items():
            if len(language_submissions) < 2:
                continue
            nicad_language = language_map.get(language)
            if not nicad_language:
                continue
            score_by_pair.update(
                self._run_nicad_group(
                    nicad_path, txl_path, nicad_language, language_submissions
                )
            )

        return {
            "pairs": [
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "score": score_by_pair.get(self._pair_key(file_a, file_b), 0.0),
                }
                for file_a, file_b in pairs
            ]
        }

    def _run_nicad_group(
        self,
        nicad_path: Path,
        txl_path: Path,
        nicad_language: str,
        submissions: SubmissionMap,
    ) -> Dict[str, float]:
        """Run NiCad for one language group."""
        with tempfile.TemporaryDirectory(prefix=f"nicad-{nicad_language}-") as temp_dir:
            source_root = Path(temp_dir) / f"submissions_{Path(temp_dir).name}"
            source_root.mkdir(parents=True, exist_ok=True)
            submission_map = self._write_submission_dirs(source_root, submissions)

            env = os.environ.copy()
            env["PATH"] = f"{txl_path.parent}:{env.get('PATH', '')}"
            nicad_cwd = (
                nicad_path.parent.parent
                if nicad_path.parent.name == "bin"
                else nicad_path.parent
            )
            result = subprocess.run(
                [
                    str(nicad_path),
                    "files",
                    nicad_language,
                    str(source_root),
                    "default-report",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=240,
                cwd=str(nicad_cwd),
                env=env,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.strip()
                    or result.stdout.strip()
                    or "NiCad execution failed"
                )

            report_dir = self._extract_nicad_report_dir(result.stdout)
            if not report_dir:
                return {}
            report_path = Path(report_dir)
            if not report_path.is_absolute():
                report_path = nicad_cwd / report_path
            xml_path = self._find_nicad_xml(report_path)
            if not xml_path:
                return {}
            return self._parse_nicad_xml(xml_path, submissions, submission_map)

    def _extract_nicad_report_dir(self, stdout: str) -> Optional[str]:
        """Extract the output directory emitted by NiCad."""
        for line in stdout.splitlines():
            if line.startswith("Results in "):
                return line.replace("Results in ", "", 1).strip()
        return None

    def _find_nicad_xml(self, report_dir: Path) -> Optional[Path]:
        """Find the NiCad XML clone report."""
        candidates = sorted(
            path
            for path in report_dir.glob("*-classes.xml")
            if not path.name.endswith("-classes-withsource.xml")
        )
        if not candidates:
            candidates = sorted(report_dir.glob("*-classes-withsource.xml"))
        if not candidates:
            candidates = sorted(report_dir.glob("*.xml"))
        return candidates[0] if candidates else None

    def _parse_nicad_xml(
        self,
        xml_path: Path,
        submissions: SubmissionMap,
        submission_map: Dict[str, Dict[str, str]],
    ) -> Dict[str, float]:
        """Parse NiCad XML output into pair scores."""
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            return self._parse_nicad_xml_text(xml_path, submissions, submission_map)

        score_by_pair: Dict[str, float] = {}
        root = tree.getroot()
        for class_node in root.findall("class"):
            try:
                similarity = float(class_node.get("similarity", "0")) / 100.0
            except (TypeError, ValueError):
                continue
            source_paths = [
                source_node.get("file", "")
                for source_node in class_node.findall("source")
                if source_node.get("file")
            ]
            self._add_nicad_class_scores(
                score_by_pair, similarity, source_paths, submissions, submission_map
            )
        return score_by_pair

    def _parse_nicad_xml_text(
        self,
        xml_path: Path,
        submissions: SubmissionMap,
        submission_map: Dict[str, Dict[str, str]],
    ) -> Dict[str, float]:
        """Recover NiCad pair scores from malformed XML report text."""
        score_by_pair: Dict[str, float] = {}
        report_text = xml_path.read_text(encoding="utf-8", errors="ignore")
        class_pattern = re.compile(
            r"<class\b(?P<attrs>[^>]*)>(?P<body>.*?)</class>", re.DOTALL
        )
        for class_match in class_pattern.finditer(report_text):
            similarity_match = re.search(
                r'\bsimilarity="(?P<similarity>[^"]+)"',
                class_match.group("attrs"),
            )
            if not similarity_match:
                continue
            try:
                similarity = float(similarity_match.group("similarity")) / 100.0
            except (TypeError, ValueError):
                continue
            source_paths = re.findall(
                r'<source\b[^>]*\bfile="([^"]+)"',
                class_match.group("body"),
            )
            self._add_nicad_class_scores(
                score_by_pair, similarity, source_paths, submissions, submission_map
            )
        return score_by_pair

    def _add_nicad_class_scores(
        self,
        score_by_pair: Dict[str, float],
        similarity: float,
        source_paths: Iterable[str],
        submissions: SubmissionMap,
        submission_map: Dict[str, Dict[str, str]],
    ) -> None:
        """Add pair scores for one NiCad clone class."""
        class_files: List[str] = []
        for source_path in source_paths:
            filename = Path(source_path).name
            if filename in submissions:
                class_files.append(filename)
                continue
            for submission_data in submission_map.values():
                if Path(submission_data["path"]).name == filename:
                    class_files.append(submission_data["filename"])
                    break
        for index, file_a in enumerate(class_files):
            for file_b in class_files[index + 1 :]:
                pair_key = self._pair_key(file_a, file_b)
                score_by_pair[pair_key] = max(
                    score_by_pair.get(pair_key, 0.0), similarity
                )

    def _find_sherlock_executable(self) -> Optional[Path]:
        """Find an executable Sherlock binary."""
        sherlock_dir = self._find_tool_dir("sherlock")
        if not sherlock_dir:
            return None
        candidate = sherlock_dir / "sherlock"
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
        return None

    def _run_sherlock(
        self,
        submissions: SubmissionMap,
        pairs: PairList,
        progress_cb=None,
    ) -> Optional[ToolResult]:
        """Run Sherlock and convert percentage output to pair scores."""
        _ = progress_cb
        sherlock_path = self._find_sherlock_executable()
        if not sherlock_path:
            return None

        groups: Dict[str, SubmissionMap] = {}
        for filename, content in submissions.items():
            suffix = Path(filename).suffix.lower()
            if suffix:
                groups.setdefault(suffix, {})[filename] = content

        score_by_pair: Dict[str, float] = {}
        with tempfile.TemporaryDirectory(prefix="sherlock-benchmark-") as temp_dir:
            source_root = Path(temp_dir) / "subs"
            source_root.mkdir(parents=True, exist_ok=True)
            written_paths = self._write_flat_submissions(source_root, submissions)
            path_to_filename = {
                str(Path(path).resolve()): filename
                for filename, path in written_paths.items()
            }
            name_to_filename = {
                Path(path).name: filename for filename, path in written_paths.items()
            }

            for suffix, suffix_submissions in groups.items():
                if len(suffix_submissions) < 2:
                    continue
                result = subprocess.run(
                    [str(sherlock_path), "-t", "0", "-e", suffix, str(source_root)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=180,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        result.stderr.strip()
                        or result.stdout.strip()
                        or "Sherlock execution failed"
                    )
                self._parse_sherlock_output(
                    result.stdout, path_to_filename, name_to_filename, score_by_pair
                )

        return {
            "pairs": [
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "score": score_by_pair.get(self._pair_key(file_a, file_b), 0.0),
                }
                for file_a, file_b in pairs
            ]
        }

    def _parse_sherlock_output(
        self,
        stdout: str,
        path_to_filename: Dict[str, str],
        name_to_filename: Dict[str, str],
        score_by_pair: Dict[str, float],
    ) -> None:
        """Parse Sherlock semicolon output into pair scores."""
        for raw_line in stdout.splitlines():
            parts = [part.strip() for part in raw_line.split(";")]
            if len(parts) != 3 or not parts[2].endswith("%"):
                continue
            left_name = self._resolve_sherlock_file(
                parts[0], path_to_filename, name_to_filename
            )
            right_name = self._resolve_sherlock_file(
                parts[1], path_to_filename, name_to_filename
            )
            if not left_name or not right_name:
                continue
            try:
                similarity = float(parts[2].rstrip("%")) / 100.0
            except ValueError:
                continue
            pair_key = self._pair_key(left_name, right_name)
            score_by_pair[pair_key] = max(
                score_by_pair.get(pair_key, 0.0), max(0.0, min(1.0, similarity))
            )

    def _resolve_sherlock_file(
        self,
        raw_path: str,
        path_to_filename: Dict[str, str],
        name_to_filename: Dict[str, str],
    ) -> Optional[str]:
        """Map a Sherlock output path or basename to the original submission name."""
        resolved = str(Path(raw_path).resolve())
        if resolved in path_to_filename:
            return path_to_filename[resolved]
        return name_to_filename.get(Path(raw_path).name)

    def _write_submission_dirs(
        self, target_dir: Path, submissions: SubmissionMap
    ) -> Dict[str, Dict[str, str]]:
        """Write submissions in one-directory-per-submission layout."""
        written: Dict[str, Dict[str, str]] = {}
        for index, (filename, content) in enumerate(sorted(submissions.items())):
            submission_id = f"sub{index:03d}"
            submission_dir = target_dir / submission_id
            submission_dir.mkdir(parents=True, exist_ok=True)
            file_path = submission_dir / Path(filename).name
            file_path.write_text(content, encoding="utf-8")
            written[submission_id] = {"filename": filename, "path": str(file_path)}
        return written

    def _write_flat_submissions(
        self, target_dir: Path, submissions: SubmissionMap
    ) -> Dict[str, str]:
        """Write submissions into one directory and return original-name mapping."""
        written: Dict[str, str] = {}
        for filename, content in sorted(submissions.items()):
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).name)
            target = target_dir / safe_name
            target.write_text(content, encoding="utf-8")
            written[filename] = str(target)
        return written

    def _infer_language(self, filename: str) -> str:
        """Infer a coarse language name from a filename suffix."""
        suffix = Path(filename).suffix.lower()
        return {
            ".py": "python",
            ".java": "java",
            ".js": "javascript",
            ".ts": "typescript",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".swift": "swift",
            ".rs": "rust",
        }.get(suffix, "python")

    def _pair_key(self, file_a: str, file_b: str) -> str:
        """Build a stable unordered pair key."""
        return "::".join(sorted((file_a, file_b)))
