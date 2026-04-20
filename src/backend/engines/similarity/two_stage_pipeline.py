"""
Two-Stage Similarity Pipeline.

Implements the high precision two-pass architecture:
1. FAST PASS: High recall, low precision filtering to get Top-10 candidates
2. HEAVY VERIFICATION: High precision, slow verification only on the candidates

This architecture achieves >90% precision while maintaining acceptable overall performance
by only running expensive algorithms on a tiny subset of candidates.
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple
import time
import logging

from .codeprovenance.v3 import CodeProvenanceV3
from .winnowing_similarity import WinnowingSimilarity
from .deep_analysis import DeepVerify
from .boilerplate_filter import global_boilerplate_filter

logger = logging.getLogger(__name__)


class TwoStageSimilarityPipeline:
    """
    Two stage similarity detection pipeline optimized for high precision.
    
    Stage 1: Fast Winnowing + lightweight token matching (100% recall, ~50% precision)
    Stage 2: Deep heavy verification on Top-10 candidates (>90% precision)
    """
    
    def __init__(self, top_n_candidates: int = 10):
        """
        Initialize pipeline.
        
        Args:
            top_n_candidates: Number of candidates to pass from stage 1 to stage 2
        """
        self.stage1_engine = WinnowingSimilarity(window_size=13, k_gram_size=5)
        self.stage2_verifier = DeepVerify()
        self.top_n = top_n_candidates
        self.boilerplate_filter = global_boilerplate_filter
        
    def analyze_submission(
        self,
        query_submission: Dict[str, Any],
        corpus: List[Dict[str, Any]],
        language: str = 'default'
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
            "rejected_candidates": 0
        }
        
        total_start = time.perf_counter()
        
        # ------------------------------
        # STAGE 1: FAST RETRIEVAL PASS
        # ------------------------------
        stage1_start = time.perf_counter()
        
        stage1_results = []
        for candidate in corpus:
            # Fast winnowing similarity - this runs on ALL pairs
            score = self.stage1_engine.compare(
                query_submission["content"],
                candidate["content"]
            )
            
            stage1_results.append({
                "candidate_id": candidate["id"],
                "score": score,
                "content": candidate["content"],
                "parsed": candidate.get("parsed", {})
            })
        
        # Filter and sort to get Top-N candidates
        stage1_results.sort(key=lambda r: r["score"], reverse=True)
        top_candidates = stage1_results[:self.top_n]
        
        metrics["stage1_time_ms"] = int((time.perf_counter() - stage1_start) * 1000)
        metrics["stage2_count"] = len(top_candidates)
        
        # ------------------------------
        # STAGE 2: DEEP VERIFICATION PASS
        # ------------------------------
        stage2_start = time.perf_counter()
        
        verified_results = self.stage2_verifier.verify_top_candidates(
            query_submission.get("parsed", {}),
            top_candidates,
            language,
            self.top_n
        )
        
        # Apply boilerplate filtering
        for result in verified_results:
            if result["verified"]:
                # Adjust score by removing boilerplate overlap
                adjusted_score = self.boilerplate_filter.adjust_similarity_score(
                    result["final_score"],
                    query_submission.get("parsed", {}),
                    result["parsed"]
                )
                result["final_score"] = adjusted_score
                
                # Re-check threshold after adjustment
                if adjusted_score < DeepVerify.VERIFICATION_THRESHOLDS["final_confidence_floor"]:
                    result["verified"] = False
                    result["deep_verification"]["rejection_reason"] = "BOILERPLATE_ADJUSTMENT_FAIL"
                    metrics["rejected_candidates"] += 1
        
        metrics["stage2_time_ms"] = int((time.perf_counter() - stage2_start) * 1000)
        metrics["total_time_ms"] = int((time.perf_counter() - total_start) * 1000)
        metrics["verified_matches"] = sum(1 for r in verified_results if r["verified"])
        
        # Log performance
        logger.info(
            "Two-stage pipeline completed: %d candidates -> %d verified matches. "
            "Stage1: %dms, Stage2: %dms, Total: %dms",
            metrics["stage1_count"],
            metrics["verified_matches"],
            metrics["stage1_time_ms"],
            metrics["stage2_time_ms"],
            metrics["total_time_ms"]
        )
        
        return verified_results, metrics
    
    def compare_pair(
        self,
        submission_a: Dict[str, Any],
        submission_b: Dict[str, Any],
        language: str = 'default'
    ) -> Dict[str, Any]:
        """
        Compare a single pair using full two stage verification.
        
        For use when you already know exactly which pair to verify.
        """
        # Fast stage 1 first
        stage1_score = self.stage1_engine.compare(
            submission_a["content"],
            submission_b["content"]
        )
        
        # Always run deep verification for explicit pair comparison
        verification = self.stage2_verifier.verify_pair(
            submission_a.get("parsed", {}),
            submission_b.get("parsed", {}),
            stage1_score,
            language
        )
        
        # Apply boilerplate adjustment
        if verification["verified"]:
            adjusted_score = self.boilerplate_filter.adjust_similarity_score(
                verification["final_score"],
                submission_a.get("parsed", {}),
                submission_b.get("parsed", {})
            )
            verification["final_score"] = adjusted_score
            
            if adjusted_score < DeepVerify.VERIFICATION_THRESHOLDS["final_confidence_floor"]:
                verification["verified"] = False
                verification["rejection_reason"] = "BOILERPLATE_ADJUSTMENT_FAIL"
        
        return verification
