"""Technique Detector for code similarity detection.

Detects code transformation techniques used to create clones:
- Variable renaming
- Control flow restructuring
- API substitution
- Code insertion/deletion
- Statement reordering

Usage:
    from benchmark.forensics.clone_taxonomy.technique_detector import TechniqueDetector

    detector = TechniqueDetector()
    report = detector.detect(code_a, code_b)
    print(report.summary())
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TechniqueType(Enum):
    """Code transformation technique types.
    
    - VARIABLE_RENAMING: Variable/method name changes
    - CONTROL_FLOW_RESTRUCTURING: If/else, loop restructuring
    - API_SUBSTITUTION: Different API calls for same effect
    - CODE_INSERTION: Additional code inserted
    - CODE_DELETION: Code removed
    - STATEMENT_REORDERING: Statement order changed
    - TYPE_CHANGE: Variable type changes
    - LITERAL_CHANGE: Constant/literal value changes
    """
    VARIABLE_RENAMING = "variable_renaming"
    CONTROL_FLOW_RESTRUCTURING = "control_flow_restructuring"
    API_SUBSTITUTION = "api_substitution"
    CODE_INSERTION = "code_insertion"
    CODE_DELETION = "code_deletion"
    STATEMENT_REORDERING = "statement_reordering"
    TYPE_CHANGE = "type_change"
    LITERAL_CHANGE = "literal_change"


@dataclass
class DetectedTechnique:
    """A detected code transformation technique.
    
    Attributes:
        technique_type: Type of technique detected.
        confidence: Confidence in detection (0.0 to 1.0).
        description: Human-readable description.
        evidence: Evidence supporting the detection.
    """
    technique_type: TechniqueType
    confidence: float = 1.0
    description: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TechniqueReport:
    """Report on detected transformation techniques.
    
    Attributes:
        pair_id: Identifier for the code pair.
        techniques_detected: List of detected techniques.
        primary_technique: Primary technique used.
        complexity_score: Complexity of transformations (0.0 to 1.0).
    """
    pair_id: str = ""
    techniques_detected: List[DetectedTechnique] = field(default_factory=list)
    primary_technique: Optional[TechniqueType] = None
    complexity_score: float = 0.0
    
    def summary(self) -> str:
        """Generate human-readable summary.
        
        Returns:
            Summary string.
        """
        lines = [
            "=" * 70,
            "TECHNIQUE DETECTION REPORT",
            "=" * 70,
            "",
            f"Pair ID: {self.pair_id}",
            f"Techniques Detected: {len(self.techniques_detected)}",
            f"Primary Technique: {self.primary_technique.value if self.primary_technique else 'None'}",
            f"Complexity Score: {self.complexity_score:.2f}",
            "",
            "DETECTED TECHNIQUES:",
        ]
        
        for technique in self.techniques_detected:
            lines.append(
                f"  - {technique.technique_type.value} "
                f"(confidence: {technique.confidence:.2f})"
            )
            if technique.description:
                lines.append(f"    {technique.description}")
        
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return {
            "pair_id": self.pair_id,
            "techniques_detected": [
                {
                    "technique_type": t.technique_type.value,
                    "confidence": t.confidence,
                    "description": t.description,
                }
                for t in self.techniques_detected
            ],
            "primary_technique": self.primary_technique.value if self.primary_technique else None,
            "complexity_score": self.complexity_score,
        }


class TechniqueDetector:
    """Detects code transformation techniques.
    
    Analyzes code pairs to identify specific transformation techniques
    used to create code clones.
    
    Usage:
        detector = TechniqueDetector()
        report = detector.detect(code_a, code_b)
        print(report.summary())
    """
    
    def detect(
        self,
        code_a: str,
        code_b: str,
        pair_id: str = "",
    ) -> TechniqueReport:
        """Detect transformation techniques in code pair.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            pair_id: Identifier for the pair.
            
        Returns:
            TechniqueReport with detected techniques.
        """
        report = TechniqueReport(pair_id=pair_id)
        
        # Detect each technique type
        techniques = []
        
        # Variable renaming
        rename_technique = self._detect_variable_renaming(code_a, code_b)
        if rename_technique:
            techniques.append(rename_technique)
        
        # Control flow restructuring
        control_technique = self._detect_control_flow_restructuring(code_a, code_b)
        if control_technique:
            techniques.append(control_technique)
        
        # API substitution
        api_technique = self._detect_api_substitution(code_a, code_b)
        if api_technique:
            techniques.append(api_technique)
        
        # Code insertion/deletion
        insertion_technique = self._detect_code_insertion(code_a, code_b)
        if insertion_technique:
            techniques.append(insertion_technique)
        
        deletion_technique = self._detect_code_deletion(code_a, code_b)
        if deletion_technique:
            techniques.append(deletion_technique)
        
        # Statement reordering
        reorder_technique = self._detect_statement_reordering(code_a, code_b)
        if reorder_technique:
            techniques.append(reorder_technique)
        
        # Type change
        type_technique = self._detect_type_change(code_a, code_b)
        if type_technique:
            techniques.append(type_technique)
        
        # Literal change
        literal_technique = self._detect_literal_change(code_a, code_b)
        if literal_technique:
            techniques.append(literal_technique)
        
        report.techniques_detected = techniques
        
        # Determine primary technique
        if techniques:
            report.primary_technique = max(
                techniques,
                key=lambda t: t.confidence
            ).technique_type
        
        # Compute complexity score
        report.complexity_score = self._compute_complexity(techniques)
        
        return report
    
    def _detect_variable_renaming(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect variable renaming technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        # Extract identifiers
        identifiers_a = set(re.findall(r'\b[a-zA-Z_]\w*\b', code_a))
        identifiers_b = set(re.findall(r'\b[a-zA-Z_]\w*\b', code_b))
        
        # Remove keywords
        keywords = {
            'if', 'else', 'for', 'while', 'def', 'class', 'return',
            'import', 'try', 'except', 'finally', 'with', 'as',
            'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
        }
        
        vars_a = identifiers_a - keywords
        vars_b = identifiers_b - keywords
        
        # Check if variables are different but structure is similar
        common_vars = vars_a & vars_b
        different_vars_a = vars_a - common_vars
        different_vars_b = vars_b - common_vars
        
        if different_vars_a and different_vars_b:
            # Estimate confidence based on proportion of renamed variables
            total_vars = len(vars_a | vars_b)
            renamed_count = min(len(different_vars_a), len(different_vars_b))
            confidence = min(1.0, renamed_count / total_vars * 2) if total_vars > 0 else 0.0
            
            if confidence > 0.3:
                return DetectedTechnique(
                    technique_type=TechniqueType.VARIABLE_RENAMING,
                    confidence=confidence,
                    description=f"Detected {renamed_count} variable renames",
                    evidence={
                        "renamed_from": list(different_vars_a)[:5],
                        "renamed_to": list(different_vars_b)[:5],
                    },
                )
        
        return None
    
    def _detect_control_flow_restructuring(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect control flow restructuring technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        # Extract control flow patterns
        def extract_control_flow(code: str) -> List[str]:
            patterns = []
            # If-else patterns
            if re.search(r'\bif\b.*\belse\b', code):
                patterns.append("if-else")
            if re.search(r'\belif\b', code):
                patterns.append("elif")
            # Loop patterns
            if re.search(r'\bfor\b', code):
                patterns.append("for")
            if re.search(r'\bwhile\b', code):
                patterns.append("while")
            # Exception handling
            if re.search(r'\btry\b.*\bexcept\b', code):
                patterns.append("try-except")
            return patterns
        
        patterns_a = set(extract_control_flow(code_a))
        patterns_b = set(extract_control_flow(code_b))
        
        # Check if patterns are different but both present
        if patterns_a != patterns_b and patterns_a and patterns_b:
            common = patterns_a & patterns_b
            different_a = patterns_a - common
            different_b = patterns_b - common
            
            if different_a or different_b:
                confidence = 0.6
                return DetectedTechnique(
                    technique_type=TechniqueType.CONTROL_FLOW_RESTRUCTURING,
                    confidence=confidence,
                    description="Control flow patterns differ between code snippets",
                    evidence={
                        "patterns_a": list(patterns_a),
                        "patterns_b": list(patterns_b),
                    },
                )
        
        return None
    
    def _detect_api_substitution(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect API substitution technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        # Common API substitution patterns
        api_pairs = [
            (r'\.append\(', r'\.extend\('),
            (r'for\b.*\bin\b', r'\.map\('),
            (r'\bif\b.*\breturn\b', r'\.filter\('),
            (r'\bprint\(', r'\blogging\.info\('),
        ]
        
        for pattern_a, pattern_b in api_pairs:
            if re.search(pattern_a, code_a) and re.search(pattern_b, code_b):
                return DetectedTechnique(
                    technique_type=TechniqueType.API_SUBSTITUTION,
                    confidence=0.7,
                    description="Different API calls for similar functionality",
                    evidence={
                        "api_a": pattern_a,
                        "api_b": pattern_b,
                    },
                )
        
        return None
    
    def _detect_code_insertion(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect code insertion technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        lines_a = len(code_a.split('\n'))
        lines_b = len(code_b.split('\n'))
        
        # Check if one code has significantly more lines
        if lines_b > lines_a * 1.5 and lines_b - lines_a > 3:
            return DetectedTechnique(
                technique_type=TechniqueType.CODE_INSERTION,
                confidence=0.6,
                description=f"Code B has {lines_b - lines_a} more lines than Code A",
                evidence={
                    "lines_a": lines_a,
                    "lines_b": lines_b,
                    "inserted_lines": lines_b - lines_a,
                },
            )
        
        return None
    
    def _detect_code_deletion(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect code deletion technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        lines_a = len(code_a.split('\n'))
        lines_b = len(code_b.split('\n'))
        
        # Check if one code has significantly fewer lines
        if lines_a > lines_b * 1.5 and lines_a - lines_b > 3:
            return DetectedTechnique(
                technique_type=TechniqueType.CODE_DELETION,
                confidence=0.6,
                description=f"Code B has {lines_a - lines_b} fewer lines than Code A",
                evidence={
                    "lines_a": lines_a,
                    "lines_b": lines_b,
                    "deleted_lines": lines_a - lines_b,
                },
            )
        
        return None
    
    def _detect_statement_reordering(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect statement reordering technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        # Extract statements (lines with assignments or function calls)
        def extract_statements(code: str) -> List[str]:
            statements = []
            for line in code.split('\n'):
                line = line.strip()
                if '=' in line or '(' in line:
                    statements.append(line)
            return statements
        
        statements_a = extract_statements(code_a)
        statements_b = extract_statements(code_b)
        
        # Check if same statements but different order
        if len(statements_a) == len(statements_b) and len(statements_a) > 2:
            set_a = set(statements_a)
            set_b = set(statements_b)
            
            if set_a == set_b and statements_a != statements_b:
                return DetectedTechnique(
                    technique_type=TechniqueType.STATEMENT_REORDERING,
                    confidence=0.5,
                    description="Same statements in different order",
                    evidence={
                        "num_statements": len(statements_a),
                    },
                )
        
        return None
    
    def _detect_type_change(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect type change technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        # Look for type annotations
        type_pattern = r':\s*(\w+)'
        types_a = re.findall(type_pattern, code_a)
        types_b = re.findall(type_pattern, code_b)
        
        if types_a and types_b and set(types_a) != set(types_b):
            return DetectedTechnique(
                technique_type=TechniqueType.TYPE_CHANGE,
                confidence=0.5,
                description="Type annotations differ",
                evidence={
                    "types_a": types_a,
                    "types_b": types_b,
                },
            )
        
        return None
    
    def _detect_literal_change(
        self,
        code_a: str,
        code_b: str,
    ) -> Optional[DetectedTechnique]:
        """Detect literal change technique.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            
        Returns:
            DetectedTechnique if detected, None otherwise.
        """
        # Extract numeric literals
        literals_a = set(re.findall(r'\b\d+\b', code_a))
        literals_b = set(re.findall(r'\b\d+\b', code_b))
        
        if literals_a and literals_b and literals_a != literals_b:
            common = literals_a & literals_b
            different_a = literals_a - common
            different_b = literals_b - common
            
            if different_a and different_b:
                return DetectedTechnique(
                    technique_type=TechniqueType.LITERAL_CHANGE,
                    confidence=0.6,
                    description="Numeric literals differ",
                    evidence={
                        "literals_a": list(different_a)[:5],
                        "literals_b": list(different_b)[:5],
                    },
                )
        
        return None
    
    def _compute_complexity(self, techniques: List[DetectedTechnique]) -> float:
        """Compute complexity score based on detected techniques.
        
        Args:
            techniques: List of detected techniques.
            
        Returns:
            Complexity score (0.0 to 1.0).
        """
        if not techniques:
            return 0.0
        
        # Weight each technique type
        weights = {
            TechniqueType.VARIABLE_RENAMING: 0.2,
            TechniqueType.CONTROL_FLOW_RESTRUCTURING: 0.4,
            TechniqueType.API_SUBSTITUTION: 0.3,
            TechniqueType.CODE_INSERTION: 0.3,
            TechniqueType.CODE_DELETION: 0.3,
            TechniqueType.STATEMENT_REORDERING: 0.2,
            TechniqueType.TYPE_CHANGE: 0.2,
            TechniqueType.LITERAL_CHANGE: 0.1,
        }
        
        total_weight = sum(
            weights.get(t.technique_type, 0.2) * t.confidence
            for t in techniques
        )
        
        # Normalize to 0-1 range
        return min(1.0, total_weight / 2)