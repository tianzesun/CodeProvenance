"""CodeProvenance Engine v3 - Precision Recovery Layer (PRL).

Implements multi-stage filtering pipeline for precision recovery:
1. Structural Sanity Check (fast reject)
2. Semantic Consistency Check (API usage)
3. Behavioral Fingerprint Matching
4. Weighted Score Fusion (re-ranking)
5. Adaptive Threshold

Architecture:
  [Candidate Generation] -> [PRL] -> [Final Decision]
    (token/AST/embedding)   (skeptical reviewer)  (clone/not-clone)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.backend.benchmark.similarity.base_engine import BaseSimilarityEngine


@dataclass
class SimilarityCandidate:
    """Input candidate for Precision Recovery Layer."""
    file_a: str
    file_b: str
    token_sim: float
    ast_sim: float
    embedding_sim: float
    raw_score: float


@dataclass
class RefinedDecision:
    """Output from Precision Recovery Layer."""
    is_clone: bool
    confidence: float
    rejection_reason: Optional[str] = None
    fingerprint_sim: float = 0.0
    api_overlap: float = 0.0


@dataclass
class FunctionFingerprint:
    """Lightweight behavioral fingerprint of a function."""
    num_loops: int = 0
    num_branches: int = 0
    function_calls: List[str] = field(default_factory=list)
    return_type_hint: str = ""
    num_params: int = 0
    has_docstring: bool = False
    has_exception_handling: bool = False


def extract_fingerprint(code: str) -> FunctionFingerprint:
    """Extract behavioral fingerprint from code."""
    fp = FunctionFingerprint()
    
    # Count loops
    fp.num_loops = len(re.findall(r'\b(for|while)\b', code))
    
    # Count branches
    fp.num_branches = len(re.findall(r'\b(if|elif|else|switch|case)\b', code))
    
    # Extract function calls
    calls = re.findall(r'\b([a-zA-Z_]\w*)\s*\(', code)
    exclude = {'if', 'while', 'for', 'switch', 'return', 'def', 'class', 'lambda', 'with'}
    fp.function_calls = sorted(set(c for c in calls if c not in exclude))
    
    # Count parameters
    defs = re.findall(r'def\s+\w+\s*\(([^)]*)\)', code)
    if defs:
        params = [p.strip() for p in defs[0].split(',') if p.strip() if p.strip() != 'self']
        fp.num_params = len(params)
    
    # Check for docstring
    fp.has_docstring = bool(re.search(r'"""', code)) or bool(re.search(r"'''", code))
    
    # Check exception handling
    fp.has_exception_handling = bool(re.search(r'\b(try|except|finally|raise)\b', code))
    
    return fp


def fingerprint_similarity(fp_a: FunctionFingerprint, fp_b: FunctionFingerprint) -> float:
    """Compare two behavioral fingerprints."""
    scores = []
    
    # Loop count similarity (exact match = 1.0)
    if max(fp_a.num_loops, fp_b.num_loops) == 0:
        loop_sim = 1.0
    else:
        loop_sim = 1.0 - abs(fp_a.num_loops - fp_b.num_loops) / max(fp_a.num_loops, fp_b.num_loops)
    scores.append(loop_sim)
    
    # Branch count similarity
    if max(fp_a.num_branches, fp_b.num_branches) == 0:
        branch_sim = 1.0
    else:
        branch_sim = 1.0 - abs(fp_a.num_branches - fp_b.num_branches) / max(fp_a.num_branches, fp_b.num_branches)
    scores.append(branch_sim)
    
    # Function call overlap (Jaccard)
    calls_a = set(fp_a.function_calls)
    calls_b = set(fp_b.function_calls)
    if calls_a or calls_b:
        call_sim = len(calls_a & calls_b) / len(calls_a | calls_b)
    else:
        call_sim = 1.0
    scores.append(call_sim)
    
    # Parameter count similarity
    if max(fp_a.num_params, fp_b.num_params) == 0:
        param_sim = 1.0
    else:
        param_sim = 1.0 - abs(fp_a.num_params - fp_b.num_params) / max(fp_a.num_params, fp_b.num_params)
    scores.append(param_sim)
    
    # Docstring match
    if fp_a.has_docstring == fp_b.has_docstring:
        scores.append(1.0)
    else:
        scores.append(0.5)
    
    # Exception handling match
    if fp_a.has_exception_handling == fp_b.has_exception_handling:
        scores.append(1.0)
    else:
        scores.append(0.7)
    
    return sum(scores) / len(scores)


def compute_api_overlap(code_a: str, code_b: str) -> float:
    """Compute API call overlap between two code snippets."""
    api_pattern = re.compile(r'\b([a-zA-Z_]\w*)\s*\(')
    apis_a = set(m.group(1) for m in api_pattern.finditer(code_a))
    apis_b = set(m.group(1) for m in api_pattern.finditer(code_b))
    
    exclude = {'if', 'while', 'for', 'switch', 'return', 'def', 'class', 'lambda', 'with'}
    apis_a -= exclude
    apis_b -= exclude
    
    if apis_a or apis_b:
        return len(apis_a & apis_b) / len(apis_a | apis_b)
    return 1.0


def compute_var_name_jaccard(code_a: str, code_b: str) -> float:
    """Compute Jaccard similarity of variable names."""
    var_pattern = re.compile(r'\b([a-zA-Z_]\w*)\b')
    var_a = set(m.group(1) for m in var_pattern.finditer(code_a))
    var_b = set(m.group(1) for m in var_pattern.finditer(code_b))
    
    if var_a or var_b:
        return len(var_a & var_b) / len(var_a | var_b)
    return 0.0


class PrecisionRecoveryLayer:
    """Precision Recovery Layer - skeptical reviewer for candidate clones.
    
    Stages:
    1. Structural Sanity Check (fast reject)
    2. Semantic Consistency Check (API usage)
    3. Behavioral Fingerprint Matching
    4. Weighted Score Fusion (re-ranking)
    5. Adaptive Threshold + anti-FP heuristics
    """
    
    # Stage 1: Structural thresholds
    MIN_AST_SIM = 0.15
    MAX_LENGTH_RATIO = 4.0
    MIN_SHARED_IDENTIFIERS = 2
    
    # Stage 2: Semantic thresholds
    MIN_API_OVERLAP_FOR_EMBEDDING = 0.20
    
    # Stage 3: Fingerprint thresholds
    MIN_FINGERPRINT_SIM = 0.20  # More lenient for renamed clones (Type-2)
    
    # Stage 4: Score fusion weights
    WEIGHT_TOKEN = 0.30
    WEIGHT_AST = 0.25
    WEIGHT_EMBED = 0.20
    WEIGHT_FINGERPRINT = 0.25
    
    # Stage 5: Adaptive thresholds
    THRESH_SMALL_FUNC = 0.75
    THRESH_CROSS_FILE = 0.70
    THRESH_DEFAULT = 0.55
    THRESH_EMBEDDING_ANOMALY = 0.95  # If embed high but everything else low

    def evaluate(self, candidate: SimilarityCandidate, 
                 code_a: str, code_b: str) -> RefinedDecision:
        """Evaluate candidate through Precision Recovery Layer.
        
        Args:
            candidate: Similarity candidate from upstream pipeline.
            code_a: Raw code for file A.
            code_b: Raw code for file_b.
            
        Returns:
            RefinedDecision with clone decision and confidence.
        """
        # Stage 1: Structural Sanity Check
        reject = self._structural_check(candidate, code_a, code_b)
        if reject:
            return RefinedDecision(is_clone=False, confidence=0.0, 
                                   rejection_reason=reject)
        
        # Stage 2: Semantic Consistency Check
        api_overlap = compute_api_overlap(code_a, code_b)
        reject = self._semantic_check(candidate, api_overlap)
        if reject:
            return RefinedDecision(is_clone=False, confidence=0.0,
                                   rejection_reason=reject, api_overlap=api_overlap)
        
        # Stage 3: Behavioral Fingerprint Matching
        fp_a = extract_fingerprint(code_a)
        fp_b = extract_fingerprint(code_b)
        fp_sim = fingerprint_similarity(fp_a, fp_b)
        
        # Behavioral fingerprint - more lenient for structural clones (Type-2/3)
        if fp_sim < self.MIN_FINGERPRINT_SIM:
            # Don't reject if AST or token similarity is high
            # (Type-2 clones may have similar structure but different fingerprints)
            if candidate.ast_sim < 0.15 and candidate.token_sim < 0.15:
                return RefinedDecision(is_clone=False, confidence=0.0,
                                       rejection_reason="Different behavior",
                                       fingerprint_sim=fp_sim, api_overlap=api_overlap)
        
        # Stage 4: Weighted Score Fusion
        final_score = self._compute_score(candidate, fp_sim)
        
        # Stage 5: Adaptive Threshold
        reject = self._adaptive_threshold_check(candidate, code_a, code_b, 
                                                 final_score, fp_sim, api_overlap)
        if reject:
            return RefinedDecision(is_clone=False, confidence=0.0,
                                   rejection_reason=reject,
                                   fingerprint_sim=fp_sim, api_overlap=api_overlap)
        
        # Accept
        confidence = max(0.0, min(1.0, final_score))
        return RefinedDecision(is_clone=True, confidence=confidence,
                               fingerprint_sim=fp_sim, api_overlap=api_overlap)
    
    def _structural_check(self, c: SimilarityCandidate, 
                          code_a: str, code_b: str) -> Optional[str]:
        """Stage 1: Fast structural rejection."""
        if c.ast_sim < self.MIN_AST_SIM and c.token_sim < 0.2:
            return "No structural similarity"
        
        len_a = len(code_a.split())
        len_b = len(code_b.split())
        if max(len_a, len_b) > 0:
            ratio = max(len_a, len_b) / max(min(len_a, len_b), 1)
            if ratio > self.MAX_LENGTH_RATIO:
                return "Size mismatch"
        
        vars_a = set(re.findall(r'\b([a-zA-Z_]\w*)\b', code_a))
        vars_b = set(re.findall(r'\b([a-zA-Z_]\w*)\b', code_b))
        shared = len(vars_a & vars_b)
        if shared < self.MIN_SHARED_IDENTIFIERS:
            return "No semantic overlap"
        
        return None
    
    def _semantic_check(self, c: SimilarityCandidate, 
                        api_overlap: float) -> Optional[str]:
        """Stage 2: Semantic consistency check."""
        # Embedding-only match detection
        if c.embedding_sim > 0.85 and api_overlap < self.MIN_API_OVERLAP_FOR_EMBEDDING:
            return "Semantic mismatch (API)"
        
        return None
    
    def _compute_score(self, c: SimilarityCandidate, 
                       fp_sim: float) -> float:
        """Stage 4: Weighted score fusion."""
        return (
            self.WEIGHT_TOKEN * c.token_sim +
            self.WEIGHT_AST * c.ast_sim +
            self.WEIGHT_EMBED * c.embedding_sim +
            self.WEIGHT_FINGERPRINT * fp_sim
        )
    
    def _adaptive_threshold_check(self, c: SimilarityCandidate,
                                   code_a: str, code_b: str,
                                   final_score: float, fp_sim: float,
                                   api_overlap: float) -> Optional[str]:
        """Stage 5: Adaptive threshold + anti-FP heuristics."""
        size = min(len(code_a.split()), len(code_b.split()))
        
        if size < 20:
            threshold = self.THRESH_SMALL_FUNC
        else:
            threshold = self.THRESH_DEFAULT
        
        # If AST is high, trust structural similarity more
        if c.ast_sim > 0.4:
            threshold = max(0.4, threshold - 0.15)
        
        # Anti-FP: Embedding anomaly detector (stricter)
        if c.embedding_sim > 0.95 and c.ast_sim < 0.15 and c.token_sim < 0.15:
            return "Embedding-only match (semantic drift)"
        
        # Anti-FP: Control flow mismatch (more lenient)
        fp_a = extract_fingerprint(code_a)
        fp_b = extract_fingerprint(code_b)
        if abs(fp_a.num_loops - fp_b.num_loops) > 3:
            return "Control flow mismatch"
        
        if final_score < threshold:
            return f"Score {final_score:.2f} below threshold {threshold:.2f}"
        
        return None


class CodeProvenanceEngineV3(BaseSimilarityEngine):
    """CodeProvenance v3 with Precision Recovery Layer.
    
    Achieves high precision through multi-stage filtering while maintaining
    high recall from the upstream candidate generation pipeline.
    """
    
    def __init__(self):
        self._token_engine = None
        self._prl = PrecisionRecoveryLayer()
    
    def _get_token_engine(self):
        if self._token_engine is None:
            from src.backend.benchmark.similarity import TokenWinnowingEngine
            self._token_engine = TokenWinnowingEngine()
        return self._token_engine
    
    @property
    def name(self) -> str:
        return "codeprovenance_v3"
    
    def compare(self, code_a: str, code_b: str) -> float:
        if not code_a or not code_b:
            return 0.0
        
        # Upstream: Compute similarity signals
        token_engine = self._get_token_engine()
        token_sim = token_engine.compare(code_a, code_b)
        ast_sim = self._compute_ast_similarity(code_a, code_b)
        embedding_sim = self._compute_embedding_similarity(code_a, code_b)
        
        raw_score = (0.35 * token_sim + 0.35 * ast_sim + 0.30 * embedding_sim)
        
        # If very low on all signals, fast reject
        if token_sim < 0.1 and ast_sim < 0.1 and embedding_sim < 0.3:
            return 0.0
        # If very high on all signals, fast accept
        if token_sim > 0.9 and ast_sim > 0.8:
            return 1.0
        
        # PRL: Precision Recovery Layer
        candidate = SimilarityCandidate(
            file_a="a", file_b="b",
            token_sim=token_sim, ast_sim=ast_sim,
            embedding_sim=embedding_sim, raw_score=raw_score
        )
        decision = self._prl.evaluate(candidate, code_a, code_b)
        
        if decision.is_clone:
            return decision.confidence
        return 0.0
    
    def _compute_ast_similarity(self, code_a: str, code_b: str) -> float:
        try:
            from src.backend.benchmark.similarity import compare_ast_safe
            return compare_ast_safe(code_a, code_b, max_depth=3)
        except Exception:
            return 0.0
    
    def _compute_embedding_similarity(self, code_a: str, code_b: str) -> float:
        tokens_a = set(code_a.lower().split())
        tokens_b = set(code_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)