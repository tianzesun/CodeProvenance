"""Semantic Abstraction Layer (SAL) for program similarity.

Bridges structural similarity → semantic equivalence reasoning.

SAL Responsibilities:
1. Loop abstraction (for/while → ITERATIVE pattern)
2. Recursion signature extraction
3. API substitution normalization
4. Control-flow equivalence detection
5. Data-flow pattern matching

This handles cases canonicalization cannot:
- Same logic, different implementation (for vs reduce)
- API substitutions (map vs list comprehension vs for-loop)
- Algorithmic equivalents (nested if vs elif chain)

Pipeline: code → canonicalize → semantic_abstract → similarity

Usage:
    from src.benchmark.abstraction.semantic_abstraction import SemanticAbstractor
    
    abstractor = SemanticAbstractor()
    abs_result = abstractor.abstract(code)
    print(abs_result.semantic_form)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SemanticAbstractionResult:
    """Result of semantic abstraction."""
    original: str
    semantic_form: str
    control_patterns: List[str] = field(default_factory=list)
    data_patterns: List[str] = field(default_factory=list)
    api_calls: List[str] = field(default_factory=list)
    semantic_fingerprint: str = ""
    complexity_metrics: Dict[str, int] = field(default_factory=dict)


class SemanticAbstractor:
    """Extracts semantic abstraction from source code.
    
    Identifies:
    - Control flow patterns (iteration, branching, recursion)
    - Data flow patterns (accumulation, filtering, mapping)
    - API call patterns (substitutable groups)
    - Algorithmic signatures
    
    Usage:
        abstractor = SemanticAbstractor()
        result = abstractor.abstract(code)
        print(result.semantic_form)
        print(result.control_patterns)
    """
    
    # API substitution groups: APIs that achieve similar effects
    API_SUBSTITUTIONS = {
        "iteration": {
            "for_in": r'for\s+\w+\s+in\s+',
            "map": r'\bmap\s*\(',
            "list_comp": r'\[.*for\s+\w+\s+in\s+',
            "generator": r'\(.*for\s+\w+\s+in\s+',
        },
        "filtering": {
            "filter": r'\bfilter\s*\(',
            "list_if": r'\[.*for\s+.*\s+if\s+',
            "if_inside_for": r'for\s+.*\n\s*if\s+',
        },
        "accumulation": {
            "sum_builtin": r'\bsum\s*\(',
            "reduce": r'\breduce\s*\(',
            "fold": r'\bfold\s*\(',
            "accumulator": r'\w+\s*[+\-*/]=',
        },
        "aggregation": {
            "max": r'\bmax\s*\(',
            "min": r'\bmin\s*\(',
            "sorted": r'\bsorted\s*\(',
            "sort": r'\.sort\s*\(',
        },
    }
    
    def __init__(self, aggressive: bool = False):
        """Initialize semantic abstractor.
        
        Args:
            aggressive: If True, apply more aggressive abstractions.
        """
        self._aggressive = aggressive
    
    def abstract(self, code: str) -> SemanticAbstractionResult:
        """Extract semantic abstraction from code.
        
        Args:
            code: Source code string.
            
        Returns:
            SemanticAbstractionResult with semantic form and metadata.
        """
        result = SemanticAbstractionResult(original=code, semantic_form=code)
        
        # 1. Extract control patterns
        result.control_patterns = self._extract_control_patterns(code)
        
        # 2. Extract data patterns
        result.data_patterns = self._extract_data_patterns(code)
        
        # 3. Extract API calls
        result.api_calls = self._extract_api_calls(code)
        
        # 4. Build semantic form (normalized representation)
        semantic = code
        
        # Normalize loops
        if self._aggressive:
            semantic = self._normalize_loops(semantic)
        
        # Normalize function call patterns
        semantic = self._normalize_api_patterns(semantic)
        
        # Normalize accumulator patterns
        semantic = self._normalize_accumulators(semantic)
        
        result.semantic_form = semantic
        
        # 5. Compute semantic fingerprint
        result.semantic_fingerprint = self._compute_fingerprint(result)
        
        # 6. Compute complexity metrics
        result.complexity_metrics = self._compute_complexity(code)
        
        return result
    
    def semantic_similarity(
        self, result_a: SemanticAbstractionResult, result_b: SemanticAbstractionResult
    ) -> float:
        """Compute semantic similarity between two abstraction results.
        
        This measures overlap in patterns, not token similarity.
        
        Args:
            result_a: First abstraction result.
            result_b: Second abstraction result.
            
        Returns:
            Semantic similarity score [0, 1].
        """
        score = 0.0
        weight_sum = 0.0
        
        # Control pattern overlap (weight: 0.40)
        w_ctrl = 0.40
        ctrl_a = set(result_a.control_patterns)
        ctrl_b = set(result_b.control_patterns)
        if ctrl_a or ctrl_b:
            ctrl_intersect = len(ctrl_a & ctrl_b)
            ctrl_union = len(ctrl_a | ctrl_b)
            score += w_ctrl * (ctrl_intersect / ctrl_union if ctrl_union > 0 else 0)
            weight_sum += w_ctrl
        
        # Data pattern overlap (weight: 0.30)
        w_data = 0.30
        data_a = set(result_a.data_patterns)
        data_b = set(result_b.data_patterns)
        if data_a or data_b:
            data_intersect = len(data_a & data_b)
            data_union = len(data_a | data_b)
            score += w_data * (data_intersect / data_union if data_union > 0 else 0)
            weight_sum += w_data
        
        # API pattern overlap (weight: 0.20)
        w_api = 0.20
        api_a = set(result_a.api_calls)
        api_b = set(result_b.api_calls)
        if api_a or api_b:
            api_intersect = len(api_a & api_b)
            api_union = len(api_a | api_b)
            score += w_api * (api_intersect / api_union if api_union > 0 else 0)
            weight_sum += w_api
        
        # Complexity similarity (weight: 0.10)
        w_complex = 0.10
        if result_a.complexity_metrics and result_b.complexity_metrics:
            a_complex = sum(result_a.complexity_metrics.values())
            b_complex = sum(result_b.complexity_metrics.values())
            max_complex = max(a_complex, b_complex, 1)
            diff = abs(a_complex - b_complex)
            score += w_complex * (1.0 - diff / max_complex)
            weight_sum += w_complex
        
        return score / weight_sum if weight_sum > 0 else 0.0
    
    def _extract_control_patterns(self, code: str) -> List[str]:
        """Extract control flow patterns from code.
        
        Args:
            code: Source code.
            
        Returns:
            List of control pattern identifiers.
        """
        patterns = []
        
        # Loops
        if re.search(r'\bfor\b', code):
            if re.search(r'\bfor\s+\w+\s+in\s+range\b', code):
                patterns.append("COUNTED_LOOP")
            elif re.search(r'\bfor\s+\w+\s+in\s+\w+', code):
                patterns.append("ITERATION")
            else:
                patterns.append("FOR_LOOP_GENERIC")
        if re.search(r'\bwhile\b', code):
            if re.search(r'\bwhile\s+True\b', code):
                patterns.append("INFINITE_LOOP")
            else:
                patterns.append("CONDITIONAL_LOOP")
        
        # Branching
        if re.search(r'\bif\b', code):
            if_count = len(re.findall(r'\bif\b', code))
            elif_count = len(re.findall(r'\belif\b', code))
            else_count = len(re.findall(r'\belse\b', code))
            
            if elif_count > 0:
                patterns.append("MULTIWAY_BRANCH")
            if if_count == 1 and elif_count == 0 and else_count == 0:
                patterns.append("SIMPLE_CONDITION")
            if else_count > 0 and elif_count == 0:
                patterns.append("BINARY_CHOICE")
        
        # Recursion
        func_match = re.search(r'def\s+(\w+)', code)
        if func_match and re.search(rf'\b{func_match.group(1)}\s*\(', code):
            pattern_count = len(re.findall(rf'\b{func_match.group(1)}\s*\(', code))
            if pattern_count > 1:  # Self-call + definition
                patterns.append("RECURSIVE")
        
        # Exception handling
        if re.search(r'\btry\b', code):
            patterns.append("EXCEPTION_HANDLING")
        
        # Context manager
        if re.search(r'\bwith\b', code):
            patterns.append("RESOURCE_MANAGEMENT")
        
        return patterns
    
    def _extract_data_patterns(self, code: str) -> List[str]:
        """Extract data flow patterns.
        
        Args:
            code: Source code.
            
        Returns:
            List of data pattern identifiers.
        """
        patterns = []
        
        # Accumulation pattern
        if re.search(r'\w+\s*[+\-*/]=', code):
            if re.search(r'\bfor\b.*\w+\s*[+\-*/]=', code, re.DOTALL):
                patterns.append("LOOP_ACCUMULATION")
            elif re.search(r'\bsum\b|\breduce\b', code):
                patterns.append("FUNCTIONAL_ACCUMULATION")
            else:
                patterns.append("IN_PLACE_MODIFICATION")
        
        # Mapping pattern
        if re.search(r'\bfor\b.*(?:=|append|yield)', code, re.DOTALL):
            if re.search(r'\.append\s*\(', code):
                patterns.append("BUILD_LIST")
            else:
                patterns.append("TRANSFORMATION")
        
        # Filtering pattern
        if re.search(r'\bif\b.*\bfor\b', code):
            patterns.append("COMPREHENSION_FILTER")
        elif re.search(r'\bfor\b.*\n\s*if\b', code):
            patterns.append("LOOP_FILTER")
        
        # Search pattern
        if re.search(r'\breturn\b.*\bif\b', code):
            patterns.append("EARLY_RETURN")
        if re.search(r'\bbreak\b', code):
            patterns.append("EARLY_EXIT")
        
        # Sorting/searching
        if re.search(r'\bsorted\b|\bsort\b', code):
            patterns.append("SORTING")
        
        return patterns
    
    def _extract_api_calls(self, code: str) -> List[str]:
        """Extract normalized API call patterns.
        
        Args:
            code: Source code.
            
        Returns:
            List of API pattern identifiers.
        """
        apis = []
        
        for group_name, patterns in self.API_SUBSTITUTIONS.items():
            for pattern_name, regex in patterns.items():
                if re.search(regex, code):
                    apis.append(f"{group_name}_{pattern_name}")
        
        # Specific function calls
        func_calls = re.findall(r'\b(len|range|append|extend|insert|pop|remove|'
                                r'setdefault|get|keys|values|items|join|split|'
                                r'strip|replace|format|upper|lower|title)\s*\(', code)
        for call in set(func_calls):
            apis.append(f"builtin_{call}")
        
        return apis
    
    def _normalize_loops(self, code: str) -> str:
        """Normalize different loop patterns to a common form.
        
        Args:
            code: Source code.
            
        Returns:
            Code with normalized loops.
        """
        # Normalize for-in-range to ITERATE_RANGE
        code = re.sub(
            r'for\s+(\w+)\s+in\s+range\s*\(([^)]*)\)',
            r'ITERATE_RANGE (\2)',
            code
        )
        
        # Normalize for-in to ITERATE_COLLECTION
        code = re.sub(
            r'for\s+(\w+)\s+in\s+(\w+)',
            r'ITERATE_COLLECTION (\2)',
            code
        )
        
        # Normalize while to ITERATE_WHILE
        code = re.sub(
            r'while\s+(.+):',
            r'ITERATE_WHILE (CONDITION):',
            code
        )
        
        return code
    
    def _normalize_api_patterns(self, code: str) -> str:
        """Normalize API call patterns.
        
        Args:
            code: Source code.
            
        Returns:
            Code with normalized API patterns.
        """
        # Normalize list comprehension
        code = re.sub(
            r'\[.*?for\s+\w+\s+in\s+.*?\]',
            'COMPREHENSION_EXP',
            code,
            flags=re.DOTALL
        )
        
        # Normalize map call
        code = re.sub(r'\bmap\s*\([^)]*\)', 'MAP_EXPRESSION', code)
        
        # Normalize filter call
        code = re.sub(r'\bfilter\s*\([^)]*\)', 'FILTER_EXPRESSION', code)
        
        return code
    
    def _normalize_accumulators(self, code: str) -> str:
        """Normalize accumulator patterns.
        
        Args:
            code: Source code.
            
        Returns:
            Code with normalized accumulator patterns.
        """
        # Normalize in-place addition
        code = re.sub(r'(\w+)\s*\+=', 'ACCUM_ADD(\1,', code)
        code = re.sub(r'(\w+)\s*\-=', 'ACCUM_SUB(\1,', code)
        
        # Normalize sum()
        code = re.sub(r'\bsum\s*\([^)]*\)', 'SUM_AGGREGATE', code)
        
        # Normalize reduce()
        code = re.sub(r'\breduce\s*\([^)]*\)', 'REDUCE_AGGREGATE', code)
        
        return code
    
    def _compute_fingerprint(self, result: SemanticAbstractionResult) -> str:
        """Compute semantic fingerprint.
        
        Args:
            result: Abstraction result.
            
        Returns:
            Fingerprint string.
        """
        parts = sorted(result.control_patterns)
        parts.extend(sorted(result.data_patterns))
        parts.extend(sorted(result.api_calls))
        return '|'.join(parts)
    
    def _compute_complexity(self, code: str) -> Dict[str, int]:
        """Compute code complexity metrics.
        
        Args:
            code: Source code.
            
        Returns:
            Dict of metric name to value.
        """
        lines = [l for l in code.split('\n') if l.strip()]
        
        return {
            "logical_lines": len(lines),
            "for_loops": len(re.findall(r'\bfor\b', code)),
            "while_loops": len(re.findall(r'\bwhile\b', code)),
            "branches": len(re.findall(r'\bif\b', code)),
            "function_calls": len(re.findall(r'\w+\s*\(', code)),
            "nesting_depth": max(
                (len(line) - len(line.lstrip())) // 4
                for line in lines
            ) if lines else 0,
        }


class SemanticComparePipeline:
    """Pipeline that applies semantic abstraction before similarity comparison.
    
    Wraps any engine to provide semantic-aware comparison.
    
    Usage:
        from src.benchmark.similarity.engines import HybridEngine
        from src.benchmark.abstraction.semantic_abstraction import (
            SemanticComparePipeline, SemanticAbstractor
        )
        
        pipeline = SemanticComparePipeline(HybridEngine(), SemanticAbstractor())
        score = pipeline.compare(code_a, code_b)
    """
    
    def __init__(
        self,
        engine,
        abstractor: Optional[SemanticAbstractor] = None,
    ):
        """Initialize semantic pipeline.
        
        Args:
            engine: Similarity engine instance.
            abstractor: Semantic abstractor instance.
        """
        self._engine = engine
        self._abstractor = abstractor or SemanticAbstractor()
    
    @property
    def name(self) -> str:
        """Return pipeline name."""
        return f"{self._engine.name}_semantic"
    
    def compare(self, code_a: str, code_b: str) -> float:
        """Compare with semantic abstraction.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Combined similarity score [0, 1].
        """
        abs_a = self._abstractor.abstract(code_a)
        abs_b = self._abstractor.abstract(code_b)
        
        # Semantic similarity based on pattern overlap
        sem_sim = self._abstractor.semantic_similarity(abs_a, abs_b)
        
        # Token-based similarity on semantic form
        token_sim = self._engine.compare(abs_a.semantic_form, abs_b.semantic_form)
        
        # Weighted combination: 40% semantic, 60% token
        return 0.4 * sem_sim + 0.6 * token_sim
    
    def compare_with_details(
        self, code_a: str, code_b: str
    ) -> Dict[str, Any]:
        """Compare with detailed breakdown.
        
        Args:
            code_a: First code string.
            code_b: Second code string.
            
        Returns:
            Dict with score and breakdown.
        """
        abs_a = self._abstractor.abstract(code_a)
        abs_b = self._abstractor.abstract(code_b)
        
        sem_sim = self._abstractor.semantic_similarity(abs_a, abs_b)
        token_sim = self._engine.compare(abs_a.semantic_form, abs_b.semantic_form)
        
        return {
            "overall": 0.4 * sem_sim + 0.6 * token_sim,
            "semantic_similarity": sem_sim,
            "token_similarity": token_sim,
            "semantic_a": abs_a,
            "semantic_b": abs_b,
        }


def create_semantic_engines(engines: Dict[str, Any]) -> Dict[str, Any]:
    """Create semantic-aware versions of engines.
    
    Args:
        engines: Dict of engine_name -> engine instance.
        
    Returns:
        Dict with original + semantic versions.
    """
    result = dict(engines)
    abstractor = SemanticAbstractor()
    for name, engine in engines.items():
        result[f"{name}_semantic"] = SemanticComparePipeline(engine, abstractor)
    return result