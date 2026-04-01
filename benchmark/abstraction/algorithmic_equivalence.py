"""Algorithmic Equivalence Layer (AEL) for program similarity.

The final abstraction layer: maps code implementations → algorithmic intent.

Sits above SAL (Semantic Abstraction Layer), enabling:

  Before: "Are these code fragments similar?" (syntactic/structural)
  After:  "Are these implementing the same algorithmic idea?" (semantic)

AEL Responsibilities:
1. Algorithm intent detection (sorting → "ordering algorithm")
2. Strategy pattern normalization (bubble sort, quick sort → "sorting")
3. Implementation equivalence classes (for-loop → recursion → builtin → same algorithm)
4. Complexity class inference (O(n²) vs O(n log n) patterns)

Pipeline: code → canonicalize → semantic_abstract → algorithmic_class → similarity

Usage:
    from benchmark.abstraction.algorithmic_equivalence import AlgorithmicEquivalenceDetector
    
    detector = AlgorithmicEquivalenceDetector()
    result_a = detector.detect(code_a)
    result_b = detector.detect(code_b)
    equivalent = detector.is_equivalent(result_a, result_b)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class AlgorithmicSignature:
    """Algorithmic signature extracted from code."""
    original_code: str
    algorithm_class: str = ""  # "sorting", "searching", "accumulation", etc.
    algorithm_name: str = ""   # "bubble_sort", "linear_search", etc.
    strategy: str = ""         # "brute_force", "divide_conquer", etc.
    complexity_class: str = "" # "O(n)", "O(n^2)", "O(n log n)", etc.
    intent_patterns: List[str] = field(default_factory=list)
    control_signature: str = ""  # "nested_loop_compare_swap"
    data_flow: str = ""          # "accumulate_reduce"
    recursive: bool = False
    equivalent_to: List[str] = field(default_factory=list)  # Known equivalent algorithms


@dataclass
class EquivalenceResult:
    """Result of algorithmic equivalence comparison."""
    sig_a: AlgorithmicSignature
    sig_b: AlgorithmicSignature
    algorithmic_equivalent: bool
    semantic_similarity: float  # 0.0 - 1.0
    strategy_equivalent: bool
    complexity_equivalent: bool
    reasoning: str = ""


# =============================================================================
# Algorithm Pattern Registry
# =============================================================================

ALGORITHM_PATTERNS = {
    # === SORTING ALGORITHMS ===
    "bubble_sort": {
        "class": "sorting",
        "strategy": "brute_force_comparison",
        "complexity": "O(n^2)",
        "patterns": [
            r'for\s+.*\n\s*for\s+.*\n\s*if.*\[[^\]]+\].*[<>].*\[[^\]]+\]',  # nested loop compare swap
            r'while.*\n\s*(?:for|if)',  # while with inner loop
        ],
        "equivalents": ["selection_sort", "insertion_sort"],
    },
    "selection_sort": {
        "class": "sorting",
        "strategy": "brute_force_minimum",
        "complexity": "O(n^2)",
        "patterns": [
            r'\bmin\b.*\bfor\b',  # find min in loop
            r'min_idx.*for.*range',  # min index pattern
        ],
        "equivalents": ["bubble_sort", "insertion_sort"],
    },
    "insertion_sort": {
        "class": "sorting",
        "strategy": "incremental_building",
        "complexity": "O(n^2)",
        "patterns": [
            r'while\s+\w+\s*>=\s*0.*\[[^\]]+\]\s*>',  # shifting while condition
            r'key\s*=\s*\w+\[',  # key-based insertion
        ],
        "equivalents": ["bubble_sort", "selection_sort"],
    },
    "quick_sort": {
        "class": "sorting",
        "strategy": "divide_and_conquer",
        "complexity": "O(n log n)",
        "patterns": [
            r'pivot\s*=',  # pivot selection
            r'partition',  # partition function
            r'recursive.*split|split.*recursive',
        ],
        "equivalents": ["merge_sort"],
    },
    "merge_sort": {
        "class": "sorting",
        "strategy": "divide_and_conquer",
        "complexity": "O(n log n)",
        "patterns": [
            r'mid\s*=\s*len\(\w+\)\s*//\s*2',  # midpoint split
            r'merge.*left.*right',  # merge step
            r'recursive.*split.*merge',
        ],
        "equivalents": ["quick_sort"],
    },
    "builtin_sort": {
        "class": "sorting",
        "strategy": "library_call",
        "complexity": "O(n log n)",
        "patterns": [
            r'\bsorted\s*\(',
            r'\.sort\s*\(',
        ],
        "equivalents": ["quick_sort", "merge_sort", "tim_sort"],
    },

    # === SEARCHING ALGORITHMS ===
    "linear_search": {
        "class": "searching",
        "strategy": "sequential_check",
        "complexity": "O(n)",
        "patterns": [
            r'for\s+.*\n\s*if\s+.*==',  # loop with equality check
            r'for\s+.*if\s+.*==.*return',
        ],
        "equivalents": ["filter_search", "find_in_list"],
    },
    "binary_search": {
        "class": "searching",
        "strategy": "divide_and_conquer",
        "complexity": "O(log n)",
        "patterns": [
            r'left\s*=.*right\s*=',  # boundary initialization
            r'mid\s*=.*//\s*2',  # midpoint calculation
            r'while\s+left\s*<=\s*right',  # binary search loop
        ],
        "equivalents": ["bisect_search"],
    },

    # === ACCUMULATION / REDUCTION ===
    "sum_reduction": {
        "class": "accumulation",
        "strategy": "sequential_sum",
        "complexity": "O(n)",
        "patterns": [
            r'total\s*=\s*0.*for.*\+=',  # accumulator loop
            r'sum\s*\(',
            r'reduce.*lambda.*\+.*',
        ],
        "equivalents": ["sum_builtin", "fold_sum", "accumulate_add"],
    },
    "product_reduction": {
        "class": "accumulation",
        "strategy": "sequential_product",
        "complexity": "O(n)",
        "patterns": [
            r'product\s*=\s*1.*for.*\*=',
            r'math\.prod\b',
        ],
        "equivalents": ["fold_product"],
    },
    "map_transform": {
        "class": "transformation",
        "strategy": "element_wise_mapping",
        "complexity": "O(n)",
        "patterns": [
            r'\bmap\s*\(',
            r'\[.*for\s+\w+\s+in.*\]',  # list comprehension
            r'\{.*for\s+\w+\s+in.*\}',  # set/dict comprehension
        ],
        "equivalents": ["list_comprehension", "generator_expression"],
    },
    "filter_pattern": {
        "class": "filtering",
        "strategy": "conditional_selection",
        "complexity": "O(n)",
        "patterns": [
            r'\bfilter\s*\(',
            r'\[.*for\s+.*if\s+',  # filtering comprehension
        ],
        "equivalents": ["conditional_filter", "predicate_select"],
    },

    # === RECURSIVE PATTERNS ===
    "recursive_factorial": {
        "class": "recursive_math",
        "strategy": "recursive_multiplication",
        "complexity": "O(n)",
        "patterns": [
            r'def\s+factorial.*return\s+n\s*\*?\s*\w+\(n\s*-\s*1\)',
            r'if\s+n\s*<=?\s*1.*return\s*1',
        ],
        "equivalents": ["iterative_factorial", "reduce_multiply_range"],
    },
    "recursive_fibonacci": {
        "class": "recursive_math",
        "strategy": "recursive_addition",
        "complexity": "O(2^n)",
        "patterns": [
            r'def\s+fib.*fib\(.*-.*1\).*fib\(.*-.*2\)',
        ],
        "equivalents": ["iterative_fibonacci", "matrix_fibonacci"],
    },

    # === GRAPH / TREE TRAVERSAL ===
    "dfs_traversal": {
        "class": "graph_traversal",
        "strategy": "depth_first",
        "complexity": "O(V+E)",
        "patterns": [
            r'visited\s*=\s*set\s*\(\)',  # visited tracking
            r'stack.*append.*pop',  # stack-based DFS
        ],
        "equivalents": ["recursive_dfs", "stack_dfs"],
    },
    "bfs_traversal": {
        "class": "graph_traversal",
        "strategy": "breadth_first",
        "complexity": "O(V+E)",
        "patterns": [
            r'visited\s*=\s*set\s*\(\)',
            r'queue.*append.*popleft',  # queue-based BFS
            r'collections\.deque',
        ],
        "equivalents": ["queue_bfs"],
    },
}

# High-level algorithm class mapping
ALGORITHM_CLASSES = {
    "sorting": {"bubble_sort", "selection_sort", "insertion_sort", "quick_sort", "merge_sort", "builtin_sort"},
    "searching": {"linear_search", "binary_search"},
    "accumulation": {"sum_reduction", "product_reduction"},
    "transformation": {"map_transform"},
    "filtering": {"filter_pattern"},
    "recursive_math": {"recursive_factorial", "recursive_fibonacci"},
    "graph_traversal": {"dfs_traversal", "bfs_traversal"},
}


class AlgorithmicEquivalenceDetector:
    """Detects algorithmic equivalence between code implementations.
    
    Goes beyond syntactic/structural similarity to answer:
    "Are these two implementations of the same algorithmic idea?"
    
    Usage:
        detector = AlgorithmicEquivalenceDetector()
        sig_a = detector.detect(code_a)
        sig_b = detector.detect(code_b)
        result = detector.compare(sig_a, sig_b)
        print(f"Equivalent: {result.algorithmic_equivalent}")
    """
    
    def __init__(self, strict: bool = False):
        """Initialize detector.
        
        Args:
            strict: If True, requires exact algorithm match.
                   If False, allows class-level equivalence.
        """
        self._strict = strict
    
    def detect(self, code: str) -> AlgorithmicSignature:
        """Extract algorithmic signature from code.
        
        Args:
            code: Source code string.
            
        Returns:
            AlgorithmicSignature with detected patterns.
        """
        sig = AlgorithmicSignature(original_code=code)
        
        # 1. Match against known algorithm patterns
        best_match = None
        best_score = 0
        
        for algo_name, algo_info in ALGORITHM_PATTERNS.items():
            score = self._match_algorithm(code, algo_info)
            if score > best_score:
                best_score = score
                best_match = (algo_name, algo_info)
        
        if best_match and best_score > 0.3:
            algo_name, algo_info = best_match
            sig.algorithm_class = algo_info["class"]
            sig.algorithm_name = algo_name
            sig.strategy = algo_info.get("strategy", "")
            sig.complexity_class = algo_info.get("complexity", "")
            sig.equivalent_to = algo_info.get("equivalents", [])
            
            # Extract intent patterns
            sig.intent_patterns = self._extract_intent(code, algo_info)
            
            # Build control signature
            sig.control_signature = self._build_control_signature(code)
            
            # Build data flow signature
            sig.data_flow = self._build_data_flow_signature(code)
            
            # Detect recursion
            sig.recursive = self._detect_recursion(code)
        
        return sig
    
    def compare(
        self, sig_a: AlgorithmicSignature, sig_b: AlgorithmicSignature
    ) -> EquivalenceResult:
        """Compare two algorithmic signatures for equivalence.
        
        Args:
            sig_a: First signature.
            sig_b: Second signature.
            
        Returns:
            EquivalenceResult with detailed comparison.
        """
        # 1. Check exact algorithm match
        exact_match = (
            sig_a.algorithm_name == sig_b.algorithm_name
            and sig_a.algorithm_name != ""
        )
        
        # 2. Check class-level equivalence
        same_class = sig_a.algorithm_class == sig_b.algorithm_class
        cross_equivalent = (
            sig_a.algorithm_name in sig_b.equivalent_to
            or sig_b.algorithm_name in sig_a.equivalent_to
        )
        algorithmic_equivalent = exact_match or same_class or cross_equivalent
        
        # 3. Strategy equivalence
        strategy_same = sig_a.strategy == sig_b.strategy
        strategy_classes = self._get_strategy_class(sig_a.strategy) == self._get_strategy_class(sig_b.strategy)
        strategy_equivalent = strategy_same or strategy_classes
        
        # 4. Complexity class equivalence
        complexity_equiv = sig_a.complexity_class == sig_b.complexity_class
        
        # 5. Semantic similarity (pattern overlap)
        semantic_sim = self._semantic_overlap(sig_a, sig_b)
        
        # Build reasoning
        reasoning = self._build_reasoning(
            sig_a, sig_b, algorithmic_equivalent, semantic_sim
        )
        
        return EquivalenceResult(
            sig_a=sig_a,
            sig_b=sig_b,
            algorithmic_equivalent=algorithmic_equivalent,
            semantic_similarity=semantic_sim,
            strategy_equivalent=strategy_equivalent,
            complexity_equivalent=complexity_equiv,
            reasoning=reasoning,
        )
    
    def is_equivalent(
        self, sig_a: AlgorithmicSignature, sig_b: AlgorithmicSignature
    ) -> bool:
        """Quick equivalence check.
        
        Args:
            sig_a: First signature.
            sig_b: Second signature.
            
        Returns:
            True if algorithmically equivalent.
        """
        if self._strict:
            return sig_a.algorithm_name == sig_b.algorithm_name
        return self.compare(sig_a, sig_b).algorithmic_equivalent
    
    def _match_algorithm(self, code: str, algo_info: Dict[str, Any]) -> float:
        """Match code against a single algorithm pattern.
        
        Args:
            code: Source code.
            algo_info: Algorithm pattern definition.
            
        Returns:
            Match score [0, 1].
        """
        scores = []
        for pattern in algo_info.get("patterns", []):
            if re.search(pattern, code, re.DOTALL | re.IGNORECASE):
                scores.append(1.0)
            else:
                scores.append(0.0)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _extract_intent(
        self, code: str, algo_info: Dict[str, Any]
    ) -> List[str]:
        """Extract intent patterns from code.
        
        Args:
            code: Source code.
            algo_info: Algorithm pattern info.
            
        Returns:
            List of intent pattern names.
        """
        intents = []
        algo_class = algo_info.get("class", "")
        
        if algo_class == "sorting":
            if re.search(r'\bsorted\b|\.sort\b', code):
                intents.append("builtin_ordering")
            elif re.search(r'for.*for.*if', code, re.DOTALL):
                intents.append("comparison_based_sorting")
            else:
                intents.append("ordering_algorithm")
        elif algo_class == "searching":
            if "binary" in algo_info:
                intents.append("divide_and_conquer_search")
            else:
                intents.append("sequential_search")
        elif algo_class == "accumulation":
            intents.append("reduce_pattern")
        
        return intents
    
    def _build_control_signature(self, code: str) -> str:
        """Build control flow signature.
        
        Args:
            code: Source code.
            
        Returns:
            Control signature string.
        """
        parts = []
        if re.search(r'for.*for', code, re.DOTALL):
            parts.append("nested_loop")
        if re.search(r'\bsort\b', code):
            parts.append("ordering")
        if re.search(r'recurse|def\s+\w+.*\w+\(', code):
            parts.append("recursive")
        if re.search(r'\bsum\b|\breduce\b', code):
            parts.append("reduction")
        if re.search(r'\bsearch\b|\bfind\b|\bindex\b', code):
            parts.append("search")
        if re.search(r'\bfilter\b', code):
            parts.append("filter")
        return '_'.join(parts) if parts else "unknown_control"
    
    def _build_data_flow_signature(self, code: str) -> str:
        """Build data flow signature.
        
        Args:
            code: Source code.
            
        Returns:
            Data flow signature string.
        """
        if re.search(r'\+=\s*\w+\[', code):
            return "accumulate_element"
        if re.search(r'\bsum\b', code):
            return "aggregate_sum"
        if re.search(r'\bmap\b|\[.*for', code):
            return "map_projection"
        if re.search(r'\bfilter\b|\[.*for.*if', code):
            return "filter_projection"
        if re.search(r'\bswap\b|=\s*\w+\[.*\];\s*\w+\[', code):
            return "element_swap"
        return "data_transform"
    
    def _detect_recursion(self, code: str) -> bool:
        """Detect if code is recursive.
        
        Args:
            code: Source code.
            
        Returns:
            True if recursive.
        """
        func_match = re.search(r'def\s+(\w+)', code)
        if func_match:
            func_name = func_match.group(1)
            # Check for self-call (excluding the definition)
            calls = re.findall(rf'\b{func_name}\s*\(', code)
            if len(calls) > 1:  # Definition + at least one call
                return True
        return False
    
    def _semantic_overlap(
        self, sig_a: AlgorithmicSignature, sig_b: AlgorithmicSignature
    ) -> float:
        """Compute semantic overlap between signatures.
        
        Args:
            sig_a: First signature.
            sig_b: Second signature.
            
        Returns:
            Semantic similarity [0, 1].
        """
        score = 0.0
        weight_sum = 0.0
        
        # Algorithm class match (weight: 0.50)
        w_class = 0.50
        if sig_a.algorithm_class and sig_b.algorithm_class:
            score += w_class * (1.0 if sig_a.algorithm_class == sig_b.algorithm_class else 0.0)
        weight_sum += w_class
        
        # Strategy match (weight: 0.25)
        w_strategy = 0.25
        if sig_a.strategy and sig_b.strategy:
            score += w_strategy * (1.0 if sig_a.strategy == sig_b.strategy else 0.0)
        weight_sum += w_strategy
        
        # Intent pattern overlap (weight: 0.15)
        w_intent = 0.15
        intents_a = set(sig_a.intent_patterns)
        intents_b = set(sig_b.intent_patterns)
        if intents_a or intents_b:
            union = intents_a | intents_b
            intersect = intents_a & intents_b
            score += w_intent * (len(intersect) / len(union) if union else 0)
        weight_sum += w_intent
        
        # Control signature match (weight: 0.10)
        w_control = 0.10
        if sig_a.control_signature and sig_b.control_signature:
            score += w_control * (0.5 if sig_a.control_signature == sig_b.control_signature else 0.0)
        weight_sum += w_control
        
        return score / weight_sum if weight_sum > 0 else 0.0
    
    def _build_reasoning(
        self,
        sig_a: AlgorithmicSignature,
        sig_b: AlgorithmicSignature,
        equivalent: bool,
        semantic: float,
    ) -> str:
        """Build human-readable reasoning for equivalence decision.
        
        Args:
            sig_a: First signature.
            sig_b: Second signature.
            equivalent: Whether they're equivalent.
            semantic: Semantic similarity score.
            
        Returns:
            Reasoning string.
        """
        parts = []
        
        if sig_a.algorithm_class == sig_b.algorithm_class:
            parts.append(
                f"Same algorithm class: {sig_a.algorithm_class}"
            )
        
        if sig_a.algorithm_name and sig_b.algorithm_name:
            if sig_a.algorithm_name == sig_b.algorithm_name:
                parts.append(f"Exact match: {sig_a.algorithm_name}")
            elif sig_a.algorithm_name in sig_b.equivalent_to:
                parts.append(
                    f"Known equivalents: {sig_a.algorithm_name} <-> {sig_b.algorithm_name}"
                )
        
        if sig_a.complexity_class != sig_b.complexity_class:
            parts.append(
                f"Different complexity: {sig_a.complexity_class} vs {sig_b.complexity_class}"
            )
        
        if sig_a.recursive != sig_b.recursive:
            parts.append(
                "Different recursion: recursive vs iterative"
            )
        
        return "; ".join(parts) if parts else "No clear equivalence"
    
    def _get_strategy_class(self, strategy: str) -> str:
        """Get high-level strategy class.
        
        Args:
            strategy: Strategy identifier.
            
        Returns:
            High-level strategy class.
        """
        brute_force = {"brute_force_comparison", "brute_force_minimum", "sequential_check"}
        divide_conquer = {"divide_and_conquer"}
        library = {"library_call"}
        
        if strategy in brute_force:
            return "brute_force"
        if strategy in divide_conquer:
            return "divide_and_conquer"
        if strategy in library:
            return "library"
        return strategy


def create_algorithmic_engines(engines: Dict[str, Any]) -> Dict[str, Any]:
    """Create algorithmic-aware versions of engines.
    
    Args:
        engines: Dict of engine_name -> engine instance.
        
    Returns:
        Dict with original + algorithmic-aware versions.
    """
    result = dict(engines)
    detector = AlgorithmicEquivalenceDetector()
    for name, engine in engines.items():
        result[f"{name}_algorithmic"] = AlgorithmicComparePipeline(engine, detector)
    return result


class AlgorithmicComparePipeline:
    """Pipeline that applies algorithmic equivalence before similarity comparison.
    
    Combines algorithmic intent detection with token-based similarity.
    
    Usage:
        from benchmark.similarity.engines import HybridEngine
        from benchmark.abstraction.algorithmic_equivalence import AlgorithmicComparePipeline
        
        pipeline = AlgorithmicComparePipeline(HybridEngine())
        score = pipeline.compare(code_a, code_b)
    """
    
    def __init__(
        self,
        engine,
        detector: Optional[AlgorithmicEquivalenceDetector] = None,
    ):
        """Initialize algorithmic pipeline.
        
        Args:
            engine: Similarity engine instance.
            detector: Algorithmic equivalence detector.
        """
        self._engine = engine
        self._detector = detector or AlgorithmicEquivalenceDetector()
    
    @property
    def name(self) -> str:
        """Return pipeline name."""
        return f"{self._engine.name}_algorithmic"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare with algorithmic equivalence awareness.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Similarity score [0, 1].
        """
        sig_a = self._detector.detect(code_a)
        sig_b = self._detector.detect(code_b)
        
        # Check algorithmic equivalence
        equiv = self._detector.compare(sig_a, sig_b)
        
        # Algorithmic equivalence bonus (0-0.3 boost)
        alg_bonus = 0.0
        if equiv.algorithmic_equivalent:
            alg_bonus = 0.3 * equiv.semantic_similarity
        
        # Token-based similarity on canonical form
        token_sim = self._engine.compare(code_a, code_b)
        
        # Combine: token similarity + algorithmic bonus
        final = min(1.0, token_sim + alg_bonus)
        return final
    
    def compare_with_details(
        self, code_a: str, code_b: str
    ) -> Dict[str, Any]:
        """Compare with detailed breakdown.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Dict with similarity details.
        """
        sig_a = self._detector.detect(code_a)
        sig_b = self._detector.detect(code_b)
        equiv = self._detector.compare(sig_a, sig_b)
        
        token_sim = self._engine.compare(code_a, code_b)
        alg_bonus = 0.3 * equiv.semantic_similarity if equiv.algorithmic_equivalent else 0.0
        
        return {
            "overall": min(1.0, token_sim + alg_bonus),
            "token_similarity": token_sim,
            "algorithmic_bonus": alg_bonus,
            "algorithmic_equivalent": equiv.algorithmic_equivalent,
            "algorithm_class_a": sig_a.algorithm_class,
            "algorithm_class_b": sig_b.algorithm_class,
            "algorithm_name_a": sig_a.algorithm_name,
            "algorithm_name_b": sig_b.algorithm_name,
            "equivalence_reasoning": equiv.reasoning,
        }