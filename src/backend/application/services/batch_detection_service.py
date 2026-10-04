"""Batch Detection Service - Process entire folders of student submissions.

Phase 1 features:
- File ingestion (read folder of student submissions)
- All-pairs comparison engine  
- Similarity matrix with ranked suspicious pairs
- Basic report (which pairs scored above threshold)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Callable

logger = logging.getLogger(__name__)

ITERATIVE_BLOCK_TOKEN = "ITERATIVE_BLOCK"
DECISION_BLOCK_TOKEN = "DECISION_BLOCK"
BRANCH_BLOCK_TOKEN = "BRANCH_BLOCK"

#: Ceiling on chunk comparisons performed for a single pair of submissions.
#: Each one is a full engine sweep, so an unbounded pair count turns a large
#: submission into an unbounded job.
MAX_CHUNK_COMPARISONS_PER_PAIR = 400


def _aligned_chunks(chunks_a: list[Any], chunks_b: list[Any]) -> list[tuple[Any, Any]]:
    """Pair chunks from two chunked files by position.

    Chunks are cut at the same target size from the same kind of source, so the
    chunk at index *i* of A corresponds to the chunk at index *i* of B. Comparing
    them positionally keeps the result meaningful and costs ``max(n, m)``
    comparisons instead of the ``n * m`` cross product. When one file yields more
    chunks than the other, the trailing chunks are compared against the last
    chunk of the shorter file so no part of the longer submission is skipped.

    Args:
        chunks_a: Chunks of the first file, ordered by start line.
        chunks_b: Chunks of the second file, ordered by start line.

    Returns:
        ``(chunk_a, chunk_b)`` pairs, at most ``max(len(a), len(b))`` of them.
    """
    if not chunks_a or not chunks_b:
        return []
    pairs = []
    for index in range(max(len(chunks_a), len(chunks_b))):
        chunk_a = chunks_a[index] if index < len(chunks_a) else chunks_a[-1]
        chunk_b = chunks_b[index] if index < len(chunks_b) else chunks_b[-1]
        pairs.append((chunk_a, chunk_b))
    return pairs


@dataclass
class ComparisonResult:
    file_a: str
    file_b: str
    score: float
    risk_level: str
    features: dict[str, float] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    matching_blocks: list[dict[str, Any]] = field(default_factory=list)
    code_a: str | None = None
    code_b: str | None = None


def _risk_level(score: float) -> str:
    """Convert similarity score to review priority level.

    0-35%: low review priority
    35-65%: moderate review priority
    65-85%: high review priority
    85%+: critical review priority, requires corroborating evidence
    """
    if score >= 0.85:
        return "CRITICAL"
    elif score >= 0.65:
        return "HIGH"
    elif score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _logic_flow_tokens(code: str) -> list[str]:
    """Extract identifier-insensitive control and operator tokens from source code."""
    code = _strip_comments(code)
    raw_tokens = re.findall(
        r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--|\S",
        code,
    )
    control_keywords = {
        "if",
        "else",
        "for",
        "while",
        "switch",
        "case",
        "return",
        "break",
        "continue",
        "throw",
        "try",
        "catch",
        "finally",
        "do",
    }
    operator_pattern = re.compile(
        r"==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--|[+\-*/%=<>&|^~!?:;,.()\[\]{}]"
    )
    normalized_tokens = []
    for token in raw_tokens:
        if token in {"for", "while", "do"}:
            normalized_tokens.append(ITERATIVE_BLOCK_TOKEN)
        elif token in {"if", "switch"}:
            normalized_tokens.append(DECISION_BLOCK_TOKEN)
        elif token in {"else", "case", "default", "elif"}:
            normalized_tokens.append(BRANCH_BLOCK_TOKEN)
        elif (
            token in control_keywords
            or token.isdigit()
            or operator_pattern.fullmatch(token)
        ):
            normalized_tokens.append(token)
    return normalized_tokens


def _strip_comments(code: str) -> str:
    """Remove comments before structural token comparison."""
    code = re.sub(r"#.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", "", code, flags=re.DOTALL)
    return code


def _multiset_jaccard(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Calculate multiset Jaccard similarity for two token streams."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    from collections import Counter

    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)
    intersection = sum((counts_a & counts_b).values())
    union = sum((counts_a | counts_b).values())
    return intersection / union if union else 0.0


def _logic_flow_similarity(code_a: str, code_b: str) -> float:
    """Compare the logic-bearing token stream while ignoring names and imports."""
    return _multiset_jaccard(_logic_flow_tokens(code_a), _logic_flow_tokens(code_b))


def _clean_similarity_baseline(scores: list[float]) -> float:
    """Estimate normal similarity from labeled clean pairs."""
    if not scores:
        return 0.0
    return max(0.0, min(0.95, float(median(scores))))


def _subtract_clean_baseline(score: float, baseline: float) -> float:
    """Treat the clean-pair baseline as zero while preserving above-baseline signal."""
    if baseline <= 0.0:
        return max(0.0, min(1.0, score))
    adjusted = (score - baseline) / max(0.01, 1.0 - baseline)
    return max(0.0, min(1.0, adjusted))


def _apply_structure_sensitivity_floor(
    score: float,
    ast_score: float,
    fingerprint_score: float,
    logic_flow: float,
    ngram_score: float = 0.0,
    winnowing_score: float = 0.0,
) -> float:
    """Preserve control-flow/reorder sensitivity when concrete structure agrees."""
    strong_lexical = fingerprint_score >= 0.80 and (
        ngram_score >= 0.70 or winnowing_score >= 0.56
    )
    medium_lexical = fingerprint_score >= 0.65 and (
        ngram_score >= 0.58 or winnowing_score >= 0.48
    )
    if ast_score >= 0.75 and strong_lexical and logic_flow >= 0.90:
        return max(score, 0.88)
    if ast_score >= 0.65 and medium_lexical and logic_flow >= 0.78:
        return max(score, 0.82)
    return score


class BatchDetectionService:
    """Process entire folders of student submissions."""

    def __init__(
        self,
        threshold: float = 0.5,
        weights: dict[str, float] | None = None,
        starter_sources: list[str] | None = None,
    ):
        from src.backend.domain.decision import DecisionEngine
        from src.backend.engines.features.feature_extractor import FeatureExtractor
        from src.backend.engines.scoring.fusion_engine import FusionEngine
        from src.backend.engines.scoring.learned_fusion import LearnedFusionScorer

        self.extractor = FeatureExtractor()
        self.fusion = FusionEngine(weights=weights)
        self.decision = DecisionEngine(threshold)
        self.threshold = threshold
        self.weights = weights
        self.learned_scorer = LearnedFusionScorer()
        self.starter_remover = None
        if starter_sources:
            from src.backend.engines.mvp.starter_code import StarterCodeRemover

            self.starter_remover = StarterCodeRemover(starter_sources)

    def _learned_available(self) -> bool:
        """True when a trained learned-fusion artifact is loaded."""
        learned_scorer = getattr(self, "learned_scorer", None)
        return learned_scorer is not None and learned_scorer.available

    def _primary_score(
        self,
        features: Any,
        logic_flow: float,
        fused: Any,
    ) -> float:
        """Return the effective similarity score for a code pair.

        Uses the learned fusion model's calibrated probability when a trained
        artifact is available; otherwise falls back to the rule-based
        ``FusedScore`` from ``FusionEngine`` unchanged.
        """
        learned_scorer = getattr(self, "learned_scorer", None)
        if learned_scorer is not None and learned_scorer.available:
            learned = learned_scorer.score(
                {
                    "ast": features.ast,
                    "fingerprint": features.fingerprint,
                    "embedding": features.embedding,
                    "ngram": features.ngram,
                    "winnowing": features.winnowing,
                    "logic_flow": logic_flow,
                    "coverage": getattr(features, "coverage", 0.0) or 0.0,
                }
            )
            base = (
                learned if fused.final_score < 0.999 else 1.0
            )  # keep exact-match override
        else:
            base = fused.final_score
        return _apply_structure_sensitivity_floor(
            base,
            features.ast,
            features.fingerprint,
            logic_flow,
            features.ngram,
            features.winnowing,
        )

    def ingest_folder(self, folder: Path) -> dict[str, str]:
        """Read all code files from a folder.

        Returns: {"filename.py": "code content", ...}
        """
        submissions = {}
        ext_map = {
            ".py": "python",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
        }
        for ext in ext_map:
            for f in folder.rglob(f"*{ext}"):
                try:
                    content = f.read_text(encoding="utf-8")
                    if self.starter_remover:
                        content = self.starter_remover.remove(content).filtered_source
                    submissions[f.name] = content
                except UnicodeDecodeError as exc:
                    logger.warning("Skipping file %s: encoding error: %s", f.name, exc)
                except OSError as exc:
                    logger.warning("Skipping file %s: I/O error: %s", f.name, exc)
                except Exception as exc:
                    logger.warning(
                        "Skipping file %s: unexpected error: %s", f.name, exc
                    )
        return submissions

    def compare_all_pairs(
        self,
        submissions: dict[str, str],
        progress_callback: Callable[[int, int, str, str], None] | None = None,
        use_parallel: bool = True,
        max_workers: int | None = None,
    ) -> list[ComparisonResult]:
        """Compare all pairs of submissions and return ranked results.

        Args:
            submissions: Mapping of submission name to source code.
            progress_callback: Optional ``callback(completed, total, file_a,
                file_b)`` invoked after every pair finishes so callers can
                report real progress during long class-wide comparisons.
            use_parallel: Enable parallel execution (3-5x speedup). Default True.
            max_workers: Max thread pool workers. Default: min(8, CPU count).

        Performance:
            - Sequential: ~2-5s per pair
            - Parallel (8 workers): ~0.4-1s per pair (3-5x faster)
            - Recommended for >10 submissions (>45 pairs)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from src.backend.engines.similarity.code_matching import CodeHighlighter
        import os
        import threading

        files = list(submissions.keys())
        total_pairs = len(files) * (len(files) - 1) // 2

        # Build pair list
        pairs_to_compare = [
            (fa, fb) for i, fa in enumerate(files) for fb in files[i + 1 :]
        ]

        # Use parallel execution for larger jobs (>10 pairs)
        if use_parallel and total_pairs > 10:
            return self._compare_pairs_parallel(
                submissions, pairs_to_compare, progress_callback, max_workers
            )
        else:
            # Sequential for small jobs (lower overhead)
            return self._compare_pairs_sequential(
                submissions, pairs_to_compare, progress_callback
            )

    def _compare_pairs_sequential(
        self,
        submissions: dict[str, str],
        pairs: list[tuple[str, str]],
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ) -> list[ComparisonResult]:
        """Sequential pair comparison (original logic)."""
        from src.backend.engines.similarity.code_matching import CodeHighlighter

        results = []
        highlighter = CodeHighlighter(min_match_length=4)
        total_pairs = len(pairs)
        completed_pairs = 0

        for fa, fb in pairs:
            result = self._compare_single_pair(submissions, fa, fb, highlighter)
            results.append(result)
            completed_pairs += 1

            if progress_callback is not None:
                try:
                    progress_callback(completed_pairs, total_pairs, fa, fb)
                except Exception:
                    logger.warning(
                        "Progress callback failed for pair %s / %s",
                        fa,
                        fb,
                        exc_info=True,
                    )

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def _compare_pairs_parallel(
        self,
        submissions: dict[str, str],
        pairs: list[tuple[str, str]],
        progress_callback: Callable[[int, int, str, str], None] | None = None,
        max_workers: int | None = None,
    ) -> list[ComparisonResult]:
        """Parallel pair comparison using ThreadPoolExecutor.

        Achieves 3-5x speedup by comparing multiple pairs concurrently.
        Thread-safe: each pair gets its own CodeHighlighter instance.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from src.backend.engines.similarity.code_matching import CodeHighlighter
        import os
        import threading

        # Auto-configure workers: min(8, CPU count) for balanced throughput
        if max_workers is None:
            cpu_count = os.cpu_count() or 4
            max_workers = min(8, cpu_count)

        total_pairs = len(pairs)
        completed_pairs = 0
        progress_lock = threading.Lock()
        results = []

        def compare_with_progress(pair_tuple):
            nonlocal completed_pairs
            fa, fb = pair_tuple
            # Each thread gets its own highlighter (thread-safe)
            highlighter = CodeHighlighter(min_match_length=4)
            result = self._compare_single_pair(submissions, fa, fb, highlighter)

            # Thread-safe progress tracking
            with progress_lock:
                completed_pairs += 1
                current = completed_pairs

            if progress_callback is not None:
                try:
                    progress_callback(current, total_pairs, fa, fb)
                except Exception:
                    logger.warning(
                        "Progress callback failed for pair %s / %s",
                        fa,
                        fb,
                        exc_info=True,
                    )

            return result

        logger.info(
            f"Parallel comparison: {total_pairs} pairs with {max_workers} workers"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all pairs
            futures = {
                executor.submit(compare_with_progress, pair): pair for pair in pairs
            }

            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    pair = futures[future]
                    logger.error(
                        f"Pair comparison failed for {pair[0]} / {pair[1]}: {exc}",
                        exc_info=True,
                    )

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        logger.info(f"Parallel comparison complete: {len(results)} results")
        return results

    def _compare_single_pair(
        self,
        submissions: dict[str, str],
        fa: str,
        fb: str,
        highlighter,
    ) -> ComparisonResult:
        """Compare a single pair of submissions.

        Handles large files via chunking when necessary.
        Extracted for reuse in both sequential and parallel modes.
        """
        from src.backend.infrastructure.code_chunker import should_chunk

        ca, cb = submissions[fa], submissions[fb]
        starter_remover = getattr(self, "starter_remover", None)
        if starter_remover:
            ca = starter_remover.remove(ca).filtered_source
            cb = starter_remover.remove(cb).filtered_source

        # Check if either file needs chunking (>10k lines)
        needs_chunking = should_chunk(ca, threshold=10000) or should_chunk(
            cb, threshold=10000
        )

        if needs_chunking:
            logger.info(f"Large files in pair {fa}/{fb}, using chunking strategy")
            return self._compare_chunked_pair(ca, cb, fa, fb, highlighter)

        # Standard comparison for normal-sized files
        features = self.extractor.extract(ca, cb, filename_a=fa, filename_b=fb)
        logic_flow = _logic_flow_similarity(ca, cb)
        fused = self.fusion.fuse(features, logic_flow=logic_flow)
        final_score = self._primary_score(features, logic_flow, fused)

        # Compute matching blocks for highlighting
        match_result = highlighter.find_matching_segments(ca, cb)
        matching_blocks = [
            {
                "file_a": fa,
                "file_b": fb,
                "lines_a": f"{seg.start_line_a}-{seg.end_line_a}",
                "lines_b": f"{seg.start_line_b}-{seg.end_line_b}",
                "similarity": seg.similarity,
                "clone_type": seg.clone_type.value if seg.clone_type else None,
            }
            for seg in match_result.segments
        ]

        feature_payload: dict[str, float] = {
            "ast": features.ast,
            "fingerprint": features.fingerprint,
            "embedding": features.embedding,
            "ngram": features.ngram,
            "winnowing": features.winnowing,
            "logic_flow": logic_flow,
            "coverage": getattr(features, "coverage", 0.0) or 0.0,
            "fused_score": fused.final_score,
            "raw_score": final_score,
        }
        if self._learned_available():
            feature_payload["learned_score"] = round(float(final_score), 6)

        return ComparisonResult(
            file_a=fa,
            file_b=fb,
            score=final_score,
            risk_level=_risk_level(final_score),
            features={k: v for k, v in feature_payload.items() if v is not None},
            contributions=dict(fused.contributions),
            matching_blocks=matching_blocks,
            code_a=ca,
            code_b=cb,
        )

    def compare_pairs(
        self, submissions: dict[str, str], pairs: list[dict[str, Any]]
    ) -> list[ComparisonResult]:
        """Compare an explicit set of labeled benchmark pairs."""
        from src.backend.engines.similarity.code_matching import CodeHighlighter

        highlighter = CodeHighlighter(min_match_length=4)
        scored_pairs = []
        for pair in pairs:
            fa = str(pair.get("file_a", ""))
            fb = str(pair.get("file_b", ""))
            if fa not in submissions or fb not in submissions:
                logger.warning(
                    "Skipping benchmark pair with missing files: %s / %s", fa, fb
                )
                continue

            ca, cb = submissions[fa], submissions[fb]
            starter_remover = getattr(self, "starter_remover", None)
            if starter_remover:
                ca = starter_remover.remove(ca).filtered_source
                cb = starter_remover.remove(cb).filtered_source
            features = self.extractor.extract(ca, cb, filename_a=fa, filename_b=fb)
            logic_flow = _logic_flow_similarity(ca, cb)
            fused = self.fusion.fuse(features, logic_flow=logic_flow)
            raw_score = self._primary_score(features, logic_flow, fused)

            # Compute matching blocks
            match_result = highlighter.find_matching_segments(ca, cb)
            matching_blocks = [
                {
                    "file_a": fa,
                    "file_b": fb,
                    "lines_a": f"{seg.start_line_a}-{seg.end_line_a}",
                    "lines_b": f"{seg.start_line_b}-{seg.end_line_b}",
                    "similarity": seg.similarity,
                    "clone_type": seg.clone_type.value if seg.clone_type else None,
                }
                for seg in match_result.segments
            ]

            scored_pairs.append(
                {
                    "file_a": fa,
                    "file_b": fb,
                    "label": int(
                        pair.get("label", pair.get("ground_truth_label", 0)) or 0
                    ),
                    "fused_score": fused.final_score,
                    "raw_score": raw_score,
                    "logic_flow": logic_flow,
                    "features": features,
                    "contributions": dict(fused.contributions),
                    "matching_blocks": matching_blocks,
                    "code_a": ca,
                    "code_b": cb,
                }
            )

        clean_baseline = _clean_similarity_baseline(
            [item["raw_score"] for item in scored_pairs if item["label"] < 2]
        )
        results = []
        for item in scored_pairs:
            features = item["features"]
            fused_score = item["fused_score"]
            raw_score = item["raw_score"]
            baseline_adjusted_score = _subtract_clean_baseline(
                raw_score, clean_baseline
            )
            feature_payload = {
                "ast": features.ast,
                "fingerprint": features.fingerprint,
                "embedding": features.embedding,
                "ngram": features.ngram,
                "winnowing": features.winnowing,
                "logic_flow": item["logic_flow"],
                "coverage": getattr(features, "coverage", 0.0) or 0.0,
                "fused_score": fused_score,
                "raw_score": raw_score,
                "clean_baseline": clean_baseline,
                "baseline_adjusted_score": baseline_adjusted_score,
            }
            if self._learned_available():
                feature_payload["learned_score"] = round(float(raw_score), 6)
            results.append(
                ComparisonResult(
                    file_a=item["file_a"],
                    file_b=item["file_b"],
                    score=raw_score,
                    risk_level=_risk_level(raw_score),
                    features={
                        k: v for k, v in feature_payload.items() if v is not None
                    },
                    contributions=item["contributions"],
                    matching_blocks=item.get("matching_blocks", []),
                    code_a=item.get("code_a"),
                    code_b=item.get("code_b"),
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def generate_report(self, results: list[ComparisonResult]) -> dict[str, Any]:
        """Generate basic report with suspicious pairs above threshold."""
        suspicious = [r for r in results if r.score >= self.threshold]
        total = len(results)

        return {
            "summary": {
                "total_pairs": total,
                "suspicious_pairs": len(suspicious),
                "threshold": self.threshold,
            },
            "suspicious": [
                {
                    "file_a": r.file_a,
                    "file_b": r.file_b,
                    "score": r.score,
                    "risk": r.risk_level,
                    "features": dict(r.features),
                }
                for r in suspicious
            ],
            "all_results": [
                {"file_a": r.file_a, "file_b": r.file_b, "score": r.score}
                for r in results
            ],
        }

    def run_analysis(self, folder: Path, save_to: Path | None = None) -> dict[str, Any]:
        """Full pipeline: ingest -> compare -> report."""
        submissions = self.ingest_folder(folder)
        results = self.compare_all_pairs(submissions)
        report = self.generate_report(results)

        if save_to:
            save_to.parent.mkdir(parents=True, exist_ok=True)
            with open(save_to, "w") as f:
                json.dump(report, f, indent=2)

        return report

    def _compare_chunked_pair(
        self,
        code_a: str,
        code_b: str,
        filename_a: str,
        filename_b: str,
        highlighter,
    ) -> ComparisonResult:
        """Compare two files using chunking strategy for large files.

        Strategy:
        1. Chunk both files at semantic boundaries
        2. Compare corresponding chunks pairwise
        3. Aggregate results with weighted averaging
        4. Adjust matching blocks for original line numbers
        """
        from src.backend.infrastructure.code_chunker import (
            chunk_large_file,
            should_chunk,
        )

        # Determine language from filename
        language = "python"  # Default
        if filename_a.endswith(".java"):
            language = "java"
        elif filename_a.endswith((".js", ".jsx", ".ts", ".tsx")):
            language = "javascript"

        # Chunk files if needed
        if should_chunk(code_a):
            chunking_a = chunk_large_file(code_a, language, filename_a)
            logger.info(
                f"Chunked {filename_a}: {chunking_a.chunk_count} chunks "
                f"({chunking_a.original_size} lines)"
            )
        else:
            chunking_a = None

        if should_chunk(code_b):
            chunking_b = chunk_large_file(code_b, language, filename_b)
            logger.info(
                f"Chunked {filename_b}: {chunking_b.chunk_count} chunks "
                f"({chunking_b.original_size} lines)"
            )
        else:
            chunking_b = None

        # Compare chunks or full files
        chunk_comparisons = []

        if chunking_a and chunking_b:
            # Both chunked: compare aligned chunks, not the full cross product.
            # Pairing every chunk of A against every chunk of B costs O(n*m) full
            # engine sweeps (206 * 206 for a million-line submission) and was the
            # reason a large upload never finished. Chunks come from the same
            # source layout, so matching them positionally keeps the comparison
            # meaningful while costing O(max(n, m)).
            for chunk_a, chunk_b in _aligned_chunks(
                chunking_a.chunks, chunking_b.chunks
            ):
                result = self._compare_chunk_pair(
                    chunk_a.content,
                    chunk_b.content,
                    filename_a,
                    filename_b,
                    highlighter,
                )
                result["chunk_a_id"] = chunk_a.chunk_id
                result["chunk_b_id"] = chunk_b.chunk_id
                result["line_offset_a"] = chunk_a.start_line - 1
                result["line_offset_b"] = chunk_b.start_line - 1
                chunk_comparisons.append(result)
                if len(chunk_comparisons) >= MAX_CHUNK_COMPARISONS_PER_PAIR:
                    logger.warning(
                        "Chunk comparison cap (%d) reached for pair %s/%s; "
                        "remaining chunks were not compared",
                        MAX_CHUNK_COMPARISONS_PER_PAIR,
                        filename_a,
                        filename_b,
                    )
                    break

        elif chunking_a:
            # Only A chunked: compare each chunk against full B
            for chunk_a in chunking_a.chunks:
                result = self._compare_chunk_pair(
                    chunk_a.content, code_b, filename_a, filename_b, highlighter
                )
                result["chunk_a_id"] = chunk_a.chunk_id
                result["line_offset_a"] = chunk_a.start_line - 1
                chunk_comparisons.append(result)

        elif chunking_b:
            # Only B chunked: compare full A against each chunk
            for chunk_b in chunking_b.chunks:
                result = self._compare_chunk_pair(
                    code_a, chunk_b.content, filename_a, filename_b, highlighter
                )
                result["chunk_b_id"] = chunk_b.chunk_id
                result["line_offset_b"] = chunk_b.start_line - 1
                chunk_comparisons.append(result)

        # Aggregate results: take maximum similarity (worst case for plagiarism)
        max_similarity = max(r["score"] for r in chunk_comparisons)

        # Weight by chunk size for feature aggregation
        total_weight = sum(r.get("weight", 1.0) for r in chunk_comparisons)
        aggregated_features = {}

        feature_keys = [
            "ast",
            "fingerprint",
            "embedding",
            "ngram",
            "winnowing",
            "logic_flow",
        ]
        for key in feature_keys:
            values = [r.get(key, 0) for r in chunk_comparisons if key in r]
            if values:
                weights = [r.get("weight", 1.0) for r in chunk_comparisons if key in r]
                aggregated_features[key] = sum(
                    v * w for v, w in zip(values, weights)
                ) / sum(weights)

        # Collect all matching blocks (adjust line numbers)
        all_matching_blocks = []
        for result in chunk_comparisons:
            offset_a = result.get("line_offset_a", 0)
            offset_b = result.get("line_offset_b", 0)
            for block in result.get("matching_blocks", []):
                # Adjust line numbers to original file coordinates
                adjusted_block = block.copy()
                if "-" in str(block.get("lines_a", "")):
                    start, end = map(int, str(block["lines_a"]).split("-"))
                    adjusted_block["lines_a"] = f"{start + offset_a}-{end + offset_a}"
                if "-" in str(block.get("lines_b", "")):
                    start, end = map(int, str(block["lines_b"]).split("-"))
                    adjusted_block["lines_b"] = f"{start + offset_b}-{end + offset_b}"
                all_matching_blocks.append(adjusted_block)

        return ComparisonResult(
            file_a=filename_a,
            file_b=filename_b,
            score=max_similarity,
            risk_level=_risk_level(max_similarity),
            features={
                **aggregated_features,
                "chunked": True,
                "chunk_count_a": chunking_a.chunk_count if chunking_a else 1,
                "chunk_count_b": chunking_b.chunk_count if chunking_b else 1,
            },
            contributions={},
            matching_blocks=all_matching_blocks[:100],  # Limit to top 100 blocks
            code_a=code_a,
            code_b=code_b,
        )

    def _compare_chunk_pair(
        self,
        chunk_a: str,
        chunk_b: str,
        filename_a: str,
        filename_b: str,
        highlighter,
    ) -> dict[str, Any]:
        """Compare two code chunks and return analysis dict."""
        features = self.extractor.extract(
            chunk_a, chunk_b, filename_a=filename_a, filename_b=filename_b
        )
        logic_flow = _logic_flow_similarity(chunk_a, chunk_b)
        fused = self.fusion.fuse(features, logic_flow=logic_flow)
        final_score = self._primary_score(features, logic_flow, fused)

        # Compute matching blocks
        match_result = highlighter.find_matching_segments(chunk_a, chunk_b)
        matching_blocks = [
            {
                "file_a": filename_a,
                "file_b": filename_b,
                "lines_a": f"{seg.start_line_a}-{seg.end_line_a}",
                "lines_b": f"{seg.start_line_b}-{seg.end_line_b}",
                "similarity": seg.similarity,
                "clone_type": seg.clone_type.value if seg.clone_type else None,
            }
            for seg in match_result.segments
        ]

        return {
            "score": final_score,
            "ast": features.ast,
            "fingerprint": features.fingerprint,
            "embedding": features.embedding,
            "ngram": features.ngram,
            "winnowing": features.winnowing,
            "logic_flow": logic_flow,
            "matching_blocks": matching_blocks,
            "weight": len(chunk_a.split("\n")),  # Weight by chunk size
        }
