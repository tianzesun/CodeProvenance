"""
Two-Stage Similarity Pipeline.

Implements the high precision two-pass architecture:
1. FAST PASS: High recall, low precision filtering to get Top-10 candidates
2. HEAVY VERIFICATION: High precision, slow verification only on the candidates

This architecture achieves >90% precision while maintaining acceptable overall performance
by only running expensive algorithms on a tiny subset of candidates.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .boilerplate_filter import BoilerplateFilter, global_boilerplate_filter
from .deep_analysis import DeepVerify
from .winnowing_similarity import EnhancedWinnowingSimilarity

logger = logging.getLogger(__name__)


class TwoStageSimilarityPipeline:
    """
    Two stage similarity detection pipeline optimized for high precision.

    Stage 1: Fast Winnowing + lightweight token matching (100% recall, ~50% precision)
    Stage 2: Deep heavy verification on Top-10 candidates (>90% precision)
    """

    def __init__(
        self,
        top_n_candidates: int = 10,
        stage2_verifier: DeepVerify | None = None,
        boilerplate_filter: BoilerplateFilter | None = None,
    ):
        """
        Initialize pipeline.

        Args:
            top_n_candidates: Number of candidates to pass from stage 1 to stage 2
            stage2_verifier: Optional verifier (default: a new :class:`DeepVerify`)
            boilerplate_filter: Optional filter (default: the process-wide one; pass
                ``global_boilerplate_filter.copy()`` for per-job template isolation)
        """
        # Stage 1 used ``WinnowingSimilarity(window_size=13, k_gram_size=5)``, a class
        # that does not exist, so importing this module raised ImportError. Plain
        # single-pass winnowing with k=5, t=13 is what that call asked for.
        self.stage1_engine = EnhancedWinnowingSimilarity(
            k=5, t=13, multi_pass=False, adaptive=False, ai_detection=False
        )
        self.stage2_verifier = stage2_verifier or DeepVerify()
        self.top_n = max(1, int(top_n_candidates))
        self.boilerplate_filter = boilerplate_filter or global_boilerplate_filter

    def _stage1_score(self, content_a: str, content_b: str) -> float:
        """Fast fingerprint similarity of two sources as a float.

        The engine takes parsed dicts and returns a ``Finding``; this pipeline used to
        pass raw strings (``AttributeError`` on ``.get``) and then sort the Findings.
        """
        result = self.stage1_engine.compare({"raw": content_a or ""}, {"raw": content_b or ""})
        return float(getattr(result, "score", result))

    @property
    def confidence_floor(self) -> float:
        # ``DeepVerify.VERIFICATION_THRESHOLDS`` did not exist (AttributeError); the
        # effective value also honours the engine-weights configuration.
        return float(self.stage2_verifier.thresholds["final_confidence_floor"])

    def _apply_boilerplate(self, query_parsed: dict[str, Any], result: dict[str, Any], reject_into: dict[str, Any]) -> bool:
        """Discount boilerplate overlap; return True if the result was demoted."""
        adjusted = self.boilerplate_filter.adjust_similarity_score(
            result["final_score"], query_parsed, result.get("parsed", {})
        )
        result["final_score"] = adjusted
        if adjusted < self.confidence_floor:
            result["verified"] = False
            reject_into["rejection_reason"] = "BOILERPLATE_ADJUSTMENT_FAIL"
            return True
        return False

    def analyze_submission(
        self,
        query_submission: dict[str, Any],
        corpus: list[dict[str, Any]],
        language: str = "default",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Run full two-stage analysis pipeline.

        Args:
            query_submission: The submission to check for plagiarism
            corpus: All other submissions in the job
            language: Programming language

        Returns:
            Tuple of (verified_results, performance_metrics)
        """
        metrics = {
            "stage1_count": len(corpus),
            "stage2_count": 0,
            "stage1_time_ms": 0,
            "stage2_time_ms": 0,
            "total_time_ms": 0,
            "verified_matches": 0,
            "rejected_candidates": 0,
            "semantic_filtered": 0,
        }

        total_start = time.perf_counter()

        # ------------------------------
        # STAGE 1: FAST RETRIEVAL PASS
        # ------------------------------
        stage1_start = time.perf_counter()

        query_filename = str(query_submission.get("filename", ""))
        filtered_results: list[dict[str, Any]] = []
        semantic_filtered = 0
        for candidate in corpus:
            # The file-type filter compared the candidate's ID against the query's
            # FILE NAME (and called ``.lower()`` on it, failing for non-string ids).
            candidate_filename = str(candidate.get("filename") or candidate.get("id", ""))
            if self.boilerplate_filter.should_skip_comparison(query_filename, candidate_filename):
                semantic_filtered += 1
                logger.debug("Skipped semantic-incompatible pair: %s vs %s", query_filename, candidate_filename)
                continue

            # Fast winnowing similarity: runs on every remaining pair
            filtered_results.append(
                {
                    "candidate_id": candidate["id"],
                    "score": self._stage1_score(query_submission["content"], candidate["content"]),
                    "content": candidate["content"],
                    "parsed": candidate.get("parsed", {}),
                }
            )

        metrics["semantic_filtered"] = semantic_filtered

        # Filter and sort to get Top-N candidates
        filtered_results.sort(key=lambda r: r["score"], reverse=True)
        top_candidates = filtered_results[: self.top_n]

        metrics["stage1_time_ms"] = int((time.perf_counter() - stage1_start) * 1000)
        metrics["stage2_count"] = len(top_candidates)

        # ------------------------------
        # STAGE 2: DEEP VERIFICATION PASS
        # ------------------------------
        stage2_start = time.perf_counter()

        query_parsed = query_submission.get("parsed", {})
        verified_results = self.stage2_verifier.verify_top_candidates(
            query_parsed, top_candidates, language, self.top_n
        )

        for result in verified_results:
            if result["verified"] and self._apply_boilerplate(query_parsed, result, result["deep_verification"]):
                metrics["rejected_candidates"] += 1

        metrics["stage2_time_ms"] = int((time.perf_counter() - stage2_start) * 1000)
        metrics["total_time_ms"] = int((time.perf_counter() - total_start) * 1000)
        metrics["verified_matches"] = sum(1 for r in verified_results if r["verified"])

        logger.info(
            "Two-stage pipeline completed: %d candidates -> %d verified matches. "
            "Stage1: %dms, Stage2: %dms, Total: %dms",
            metrics["stage1_count"],
            metrics["verified_matches"],
            metrics["stage1_time_ms"],
            metrics["stage2_time_ms"],
            metrics["total_time_ms"],
        )

        return verified_results, metrics

    def compare_pair(
        self,
        submission_a: dict[str, Any],
        submission_b: dict[str, Any],
        language: str = "default",
    ) -> dict[str, Any]:
        """
        Compare a single pair using full two stage verification.

        For use when you already know exactly which pair to verify.
        """
        stage1_score = self._stage1_score(submission_a["content"], submission_b["content"])

        # Always run deep verification for explicit pair comparison
        verification = self.stage2_verifier.verify_pair(
            submission_a.get("parsed", {}),
            submission_b.get("parsed", {}),
            stage1_score,
            language,
        )

        if verification["verified"]:
            adjusted = self.boilerplate_filter.adjust_similarity_score(
                verification["final_score"],
                submission_a.get("parsed", {}),
                submission_b.get("parsed", {}),
            )
            verification["final_score"] = adjusted
            if adjusted < self.confidence_floor:
                verification["verified"] = False
                verification["rejection_reason"] = "BOILERPLATE_ADJUSTMENT_FAIL"

        return verification
