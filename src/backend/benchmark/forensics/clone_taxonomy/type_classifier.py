"""Clone Type Classifier for code similarity detection.

Classifies code pairs by clone type according to standard taxonomy:
- Type-1: Identical code (only whitespace/formatting differences)
- Type-2: Renamed identifiers (same structure, different names)
- Type-3: Restructured code (same logic, different structure)
- Type-4: Semantic clones (same meaning, different syntax)

Usage:
    from src.backend.benchmark.forensics.clone_taxonomy.type_classifier import CloneTypeClassifier

    classifier = CloneTypeClassifier()
    report = classifier.classify(code_pairs)
    print(report.summary())
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CloneType(Enum):
    """Standard clone type taxonomy.
    
    Based on the four-type clone classification:
    - TYPE_1: Identical code (only whitespace/formatting differences)
    - TYPE_2: Renamed identifiers (same structure, different names)
    - TYPE_3: Restructured code (same logic, different structure)
    - TYPE_4: Semantic clones (same meaning, different syntax)
    """
    TYPE_1 = "type1_identical"
    TYPE_2 = "type2_renamed"
    TYPE_3 = "type3_restructured"
    TYPE_4 = "type4_semantic"
    NON_CLONE = "non_clone"


@dataclass
class CloneTypeResult:
    """Result of clone type classification.
    
    Attributes:
        pair_id: Identifier for the code pair.
        code_a: First code snippet.
        code_b: Second code snippet.
        detected_type: Detected clone type.
        confidence: Confidence in classification (0.0 to 1.0).
        features: Features used for classification.
    """
    pair_id: str
    code_a: str
    code_b: str
    detected_type: CloneType
    confidence: float = 1.0
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CloneTypeReport:
    """Report on clone type classification.
    
    Attributes:
        total_pairs: Total number of pairs classified.
        type_distribution: Distribution of clone types.
        results: Individual classification results.
    """
    total_pairs: int = 0
    type_distribution: Dict[str, int] = field(default_factory=dict)
    results: List[CloneTypeResult] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "CLONE TYPE CLASSIFICATION REPORT",
            "=" * 70,
            "",
            f"Total Pairs Classified: {self.total_pairs}",
            "",
            "TYPE DISTRIBUTION:",
        ]
        
        for clone_type, count in sorted(
            self.type_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            pct = count / self.total_pairs * 100 if self.total_pairs > 0 else 0
            lines.append(f"  {clone_type}: {count} ({pct:.1f}%)")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "total_pairs": self.total_pairs,
            "type_distribution": self.type_distribution,
        }


class CloneTypeClassifier:
    """Classifies code pairs by clone type.
    
    Uses multiple heuristics to classify code pairs:
    - Type-1: Exact match after normalization
    - Type-2: Same structure, different identifiers
    - Type-3: Same logic, different structure
    - Type-4: Same meaning, different syntax
    
    Usage:
        classifier = CloneTypeClassifier()
        report = classifier.classify(code_pairs)
        print(report.summary())
    """
    
    def classify(
        self,
        code_pairs: List[Tuple[str, str, str]],
    ) -> CloneTypeReport:
        """Classify code pairs by clone type.
        
        Args:
            code_pairs: List of (pair_id, code_a, code_b) tuples.
            
        Returns:
            CloneTypeReport with classification results.
        """
        report = CloneTypeReport()
        report.total_pairs = len(code_pairs)
        
        for pair_id, code_a, code_b in code_pairs:
            result = self._classify_single(pair_id, code_a, code_b)
            report.results.append(result)
            
            type_name = result.detected_type.value
            report.type_distribution[type_name] = (
                report.type_distribution.get(type_name, 0) + 1
            )
        
        return report
    
    def _classify_single(
        self,
        pair_id: str,
        code_a: str,
        code_b: str,
    ) -> CloneTypeResult:
        """Classify a single code pair.
        
        Args:
            pair_id: Identifier for the pair.
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            CloneTypeResult with classification.
        """
        # Normalize code for comparison
        norm_a = self._normalize(code_a)
        norm_b = self._normalize(code_b)
        
        # Compute features
        features = self._extract_features(code_a, code_b)
        
        # Type-1: Exact match after normalization
        if norm_a == norm_b:
            return CloneTypeResult(
                pair_id=pair_id,
                code_a=code_a,
                code_b=code_b,
                detected_type=CloneType.TYPE_1,
                confidence=1.0,
                features=features,
            )
        
        # Type-2: Same structure, different identifiers
        if self._is_type2(code_a, code_b, features):
            return CloneTypeResult(
                pair_id=pair_id,
                code_a=code_a,
                code_b=code_b,
                detected_type=CloneType.TYPE_2,
                confidence=0.8,
                features=features,
            )
        
        # Type-3: Same logic, different structure
        if self._is_type3(code_a, code_b, features):
            return CloneTypeResult(
                pair_id=pair_id,
                code_a=code_a,
                code_b=code_b,
                detected_type=CloneType.TYPE_3,
                confidence=0.6,
                features=features,
            )
        
        # Type-4: Same meaning, different syntax (hard to detect)
        if self._is_type4(code_a, code_b, features):
            return CloneTypeResult(
                pair_id=pair_id,
                code_a=code_a,
                code_b=code_b,
                detected_type=CloneType.TYPE_4,
                confidence=0.4,
                features=features,
            )
        
        # Non-clone
        return CloneTypeResult(
            pair_id=pair_id,
            code_a=code_a,
            code_b=code_b,
            detected_type=CloneType.NON_CLONE,
            confidence=0.7,
            features=features,
        )
    
    def _normalize(self, code: str) -> str:
        """Normalize code for comparison.
        
        Args:
            code: Code string.
            
        Returns:
            Normalized code string.
        """
        # Remove comments
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
        code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)
        
        # Normalize whitespace
        code = re.sub(r'\s+', ' ', code)
        code = code.strip()
        
        return code
    
    def _extract_features(
        self,
        code_a: str,
        code_b: str,
    ) -> Dict[str, Any]:
        """Extract features for clone type classification.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            Dictionary of features.
        """
        features: Dict[str, Any] = {}
        
        # Length comparison
        len_a = len(code_a)
        len_b = len(code_b)
        features["length_ratio"] = min(len_a, len_b) / max(len_a, len_b) if max(len_a, len_b) > 0 else 1.0
        
        # Token comparison
        tokens_a = set(re.findall(r'\b\w+\b', code_a))
        tokens_b = set(re.findall(r'\b\w+\b', code_b))
        
        common_tokens = tokens_a & tokens_b
        all_tokens = tokens_a | tokens_b
        features["token_overlap"] = len(common_tokens) / len(all_tokens) if all_tokens else 1.0
        
        # Keyword comparison
        keywords = {'if', 'else', 'for', 'while', 'def', 'class', 'return', 'import', 'try', 'except'}
        keywords_a = {t for t in tokens_a if t in keywords}
        keywords_b = {t for t in tokens_b if t in keywords}
        
        common_keywords = keywords_a & keywords_b
        all_keywords = keywords_a | keywords_b
        features["keyword_overlap"] = len(common_keywords) / len(all_keywords) if all_keywords else 1.0
        
        # Structure comparison (indentation patterns)
        indent_a = self._get_indent_pattern(code_a)
        indent_b = self._get_indent_pattern(code_b)
        features["structure_similarity"] = 1.0 if indent_a == indent_b else 0.5
        
        return features
    
    def _get_indent_pattern(self, code: str) -> str:
        """Get indentation pattern from code.
        
        Args:
            code: Code string.
            
        Returns:
            Indentation pattern string.
        """
        lines = code.split('\n')
        pattern = []
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                pattern.append(str(indent // 4))  # Normalize to 4-space indentation
        return ','.join(pattern)
    
    def _is_type2(
        self,
        code_a: str,
        code_b: str,
        features: Dict[str, Any],
    ) -> bool:
        """Check if code pair is Type-2 (renamed identifiers).
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            features: Extracted features.
            
        Returns:
            True if Type-2 clone.
        """
        # High token overlap but different identifiers
        return (
            features.get("token_overlap", 0) > 0.5 and
            features.get("keyword_overlap", 0) > 0.7 and
            features.get("structure_similarity", 0) > 0.8
        )
    
    def _is_type3(
        self,
        code_a: str,
        code_b: str,
        features: Dict[str, Any],
    ) -> bool:
        """Check if code pair is Type-3 (restructured code).
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            features: Extracted features.
            
        Returns:
            True if Type-3 clone.
        """
        # Medium token overlap, similar keywords, different structure
        return (
            features.get("token_overlap", 0) > 0.3 and
            features.get("keyword_overlap", 0) > 0.5 and
            features.get("structure_similarity", 0) < 0.7
        )
    
    def _is_type4(
        self,
        code_a: str,
        code_b: str,
        features: Dict[str, Any],
    ) -> bool:
        """Check if code pair is Type-4 (semantic clone).
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            features: Extracted features.
            
        Returns:
            True if Type-4 clone.
        """
        # Low token overlap but similar functionality indicators
        return (
            features.get("token_overlap", 0) < 0.4 and
            features.get("length_ratio", 0) > 0.5 and
            features.get("keyword_overlap", 0) > 0.3
        )