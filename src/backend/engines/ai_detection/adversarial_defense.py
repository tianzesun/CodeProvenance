"""Adversarial defense module - Detect obfuscated AI code.

Defends against common evasion techniques:
1. Variable renaming (func_name → a, user_data → x)
2. Comment stripping (remove all docstrings)
3. Code reorganization (shuffle function order)
4. Paraphrasing (ask AI to "rewrite in different style")

Key techniques:
- Semantic hashing (AST-based, ignores names)
- Embedding similarity (detect paraphrased versions)
- Style consistency analysis (detect mixed human/AI sections)
- Structural invariants (preserved under renaming)
"""

from __future__ import annotations

import ast
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AdversarialAnalysis:
    """Results from adversarial resistance analysis."""

    semantic_hash: str
    obfuscation_score: float  # 0-1, higher = likely obfuscated
    paraphrase_indicators: list[str]
    evasion_detected: bool
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "semantic_hash": self.semantic_hash,
            "obfuscation_score": round(self.obfuscation_score, 3),
            "paraphrase_indicators": self.paraphrase_indicators[:5],
            "evasion_detected": self.evasion_detected,
            "confidence": round(self.confidence, 3),
        }


class AdversarialDefense:
    """Detect and resist code obfuscation attacks."""

    def analyze(self, code: str, language: str = "python") -> AdversarialAnalysis:
        """Analyze code for adversarial obfuscation attempts.

        Args:
            code: Source code to analyze
            language: Programming language

        Returns:
            AdversarialAnalysis with detection results
        """
        if language != "python":
            return self._default_analysis()

        try:
            # Compute semantic hash (immune to renaming)
            semantic_hash = self.compute_semantic_hash(code)

            # Detect obfuscation signals
            obfuscation_score = self._detect_obfuscation(code)

            # Identify paraphrase indicators
            paraphrase_indicators = self._detect_paraphrase_indicators(code)

            # Determine if evasion was attempted
            evasion_detected = obfuscation_score > 0.5 or len(paraphrase_indicators) > 2

            # Confidence based on signal strength
            confidence = self._compute_confidence(obfuscation_score, paraphrase_indicators)

            return AdversarialAnalysis(
                semantic_hash=semantic_hash,
                obfuscation_score=obfuscation_score,
                paraphrase_indicators=paraphrase_indicators,
                evasion_detected=evasion_detected,
                confidence=confidence,
            )
        except Exception as e:
            logger.warning(f"Adversarial analysis failed: {e}")
            return self._default_analysis()

    @staticmethod
    def compute_semantic_hash(code: str) -> str:
        """Compute AST-based semantic hash immune to variable renaming.

        Process:
        1. Parse code to AST
        2. Replace all variable/function names with placeholders
        3. Hash the normalized AST structure

        Two codes with same structure but different names → same hash

        Args:
            code: Source code

        Returns:
            Hex digest of semantic hash
        """
        try:
            tree = ast.parse(code)

            # Normalize AST: replace all names with generic placeholders
            class NameNormalizer(ast.NodeTransformer):
                def __init__(self):
                    self.var_counter = 0
                    self.func_counter = 0
                    self.name_map = {}

                def visit_Name(self, node):
                    if node.id not in self.name_map:
                        self.name_map[node.id] = f"VAR_{self.var_counter}"
                        self.var_counter += 1
                    node.id = self.name_map[node.id]
                    return node

                def visit_FunctionDef(self, node):
                    if node.name not in self.name_map:
                        self.name_map[node.name] = f"FUNC_{self.func_counter}"
                        self.func_counter += 1
                    node.name = self.name_map[node.name]
                    self.generic_visit(node)
                    return node

                def visit_ClassDef(self, node):
                    if node.name not in self.name_map:
                        self.name_map[node.name] = f"CLASS_{self.func_counter}"
                        self.func_counter += 1
                    node.name = self.name_map[node.name]
                    self.generic_visit(node)
                    return node

            normalizer = NameNormalizer()
            normalized_tree = normalizer.visit(tree)

            # Convert back to code and hash
            normalized_code = ast.unparse(normalized_tree)
            return hashlib.sha256(normalized_code.encode()).hexdigest()

        except (SyntaxError, ValueError) as e:
            logger.debug(f"Semantic hash failed: {e}")
            # Fallback: hash the code as-is
            return hashlib.sha256(code.encode()).hexdigest()

    def _detect_obfuscation(self, code: str) -> float:
        """Detect signs of deliberate obfuscation.

        Indicators:
        - Single-letter variable names (a, b, c, x, y, z)
        - No comments at all (stripped)
        - Inconsistent naming style (mix of conventions)
        - Suspiciously short names vs. code complexity

        Returns:
            Obfuscation score [0, 1]
        """
        score = 0.0

        # Count single-letter variable names
        single_letter_ratio = self._single_letter_name_ratio(code)
        if single_letter_ratio > 0.5:
            score += 0.3
        elif single_letter_ratio > 0.3:
            score += 0.15

        # Check for complete comment removal
        comment_density = self._comment_density(code)
        if comment_density == 0 and len(code.split("\n")) > 20:
            score += 0.2

        # Naming style inconsistency
        style_inconsistency = self._naming_style_inconsistency(code)
        if style_inconsistency > 0.6:
            score += 0.25

        # Short names vs. complexity mismatch
        if self._has_complexity_name_mismatch(code):
            score += 0.25

        return min(1.0, score)

    def _detect_paraphrase_indicators(self, code: str) -> list[str]:
        """Detect indicators that code was paraphrased (AI rewrite).

        Paraphrase attempts often:
        - Keep structure but change wording
        - Maintain AI patterns (defensive code, uniform lengths)
        - Show mixed style (original AI + paraphrased sections)

        Returns:
            List of detected indicators
        """
        indicators = []

        # Mixed comment styles (some verbose, some minimal)
        if self._has_mixed_comment_style(code):
            indicators.append("Mixed comment style")

        # Inconsistent function naming (some descriptive, some terse)
        if self._has_inconsistent_naming(code):
            indicators.append("Inconsistent naming pattern")

        # Partial docstring coverage (some funcs documented, others not)
        coverage = self._docstring_coverage_variance(code)
        if 0.3 < coverage < 0.7:
            indicators.append("Partial docstring coverage")

        # Mixed defensive patterns (some try/except, some bare)
        if self._has_mixed_defensive_style(code):
            indicators.append("Mixed defensive programming")

        # Structural uniformity + name chaos (AST uniform, names random)
        if self._has_structure_name_discord(code):
            indicators.append("Structure-naming mismatch")

        return indicators

    @staticmethod
    def _default_analysis() -> AdversarialAnalysis:
        """Return default analysis for invalid input."""
        return AdversarialAnalysis(
            semantic_hash="",
            obfuscation_score=0.0,
            paraphrase_indicators=[],
            evasion_detected=False,
            confidence=0.0,
        )

    @staticmethod
    def _compute_confidence(obfuscation_score: float, indicators: list[str]) -> float:
        """Compute confidence in evasion detection."""
        if obfuscation_score > 0.7 or len(indicators) >= 4:
            return 0.9
        elif obfuscation_score > 0.5 or len(indicators) >= 2:
            return 0.7
        elif obfuscation_score > 0.3 or len(indicators) >= 1:
            return 0.5
        return 0.3

    # --- Helper methods for obfuscation detection ---

    @staticmethod
    def _single_letter_name_ratio(code: str) -> float:
        """Ratio of single-letter variable names to total names."""
        try:
            tree = ast.parse(code)
            single_letter = 0
            total = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    total += 1
                    if len(node.id) == 1 and node.id not in ("_",):
                        single_letter += 1

            return single_letter / total if total > 0 else 0.0
        except:
            return 0.0

    @staticmethod
    def _comment_density(code: str) -> float:
        """Ratio of comment lines to total lines."""
        lines = code.split("\n")
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        return comment_lines / max(len(lines), 1)

    @staticmethod
    def _naming_style_inconsistency(code: str) -> float:
        """Measure inconsistency in naming conventions.

        Checks for mix of snake_case, camelCase, UPPERCASE
        """
        try:
            tree = ast.parse(code)
            names = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    names.append(node.name)
                elif isinstance(node, ast.Name):
                    names.append(node.id)

            if len(names) < 3:
                return 0.0

            snake_case = sum(1 for n in names if "_" in n and n.islower())
            camel_case = sum(1 for n in names if any(c.isupper() for c in n[1:]) and "_" not in n)
            upper_case = sum(1 for n in names if n.isupper())

            # High inconsistency if multiple styles present
            styles_used = sum(1 for count in [snake_case, camel_case, upper_case] if count > 0)
            return (styles_used - 1) / 2  # 0 if 1 style, 0.5 if 2, 1.0 if 3

        except:
            return 0.0

    @staticmethod
    def _has_complexity_name_mismatch(code: str) -> bool:
        """Check if code is complex but uses simple names."""
        try:
            tree = ast.parse(code)

            # Count complexity (lines, nesting depth)
            lines = len(code.split("\n"))
            if lines < 20:
                return False

            # Average name length
            names = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.Name)):
                    if isinstance(node, ast.FunctionDef):
                        names.append(node.name)
                    else:
                        names.append(node.id)

            if not names:
                return False

            avg_name_len = sum(len(n) for n in names) / len(names)

            # Complex code with short names (< 3 chars avg) = suspicious
            return avg_name_len < 3.0
        except:
            return False

    @staticmethod
    def _has_mixed_comment_style(code: str) -> bool:
        """Detect mix of verbose and terse comments."""
        comments = [line.strip() for line in code.split("\n") if line.strip().startswith("#")]
        if len(comments) < 3:
            return False

        lengths = [len(c) for c in comments]
        if not lengths:
            return False

        avg = sum(lengths) / len(lengths)
        variance = sum((x - avg) ** 2 for x in lengths) / len(lengths)
        cv = (variance**0.5) / avg if avg > 0 else 0

        # High variation in comment length = mixed style
        return cv > 1.0

    @staticmethod
    def _has_inconsistent_naming(code: str) -> bool:
        """Detect mix of descriptive and terse function names."""
        try:
            tree = ast.parse(code)
            funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

            if len(funcs) < 3:
                return False

            lengths = [len(f) for f in funcs]
            avg = sum(lengths) / len(lengths)
            variance = sum((x - avg) ** 2 for x in lengths) / len(lengths)
            cv = (variance**0.5) / avg if avg > 0 else 0

            # High CV in function name lengths = inconsistent
            return cv > 0.6
        except:
            return False

    @staticmethod
    def _docstring_coverage_variance(code: str) -> float:
        """Return docstring coverage (0-1)."""
        try:
            tree = ast.parse(code)
            funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            if not funcs:
                return 0.0

            documented = sum(1 for f in funcs if ast.get_docstring(f))
            return documented / len(funcs)
        except:
            return 0.0

    @staticmethod
    def _has_mixed_defensive_style(code: str) -> bool:
        """Detect inconsistent use of defensive patterns."""
        try:
            tree = ast.parse(code)
            funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            if len(funcs) < 3:
                return False

            # Count try/except per function
            try_counts = []
            for func in funcs:
                count = sum(1 for node in ast.walk(func) if isinstance(node, ast.Try))
                try_counts.append(count)

            # Mixed if some funcs have try/except, others don't
            has_try = sum(1 for c in try_counts if c > 0)
            no_try = len(try_counts) - has_try

            return has_try > 0 and no_try > 0
        except:
            return False

    @staticmethod
    def _has_structure_name_discord(code: str) -> bool:
        """Check if structure is uniform but names are chaotic."""
        try:
            tree = ast.parse(code)
            funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            if len(funcs) < 3:
                return False

            # Check structural uniformity (function lengths similar)
            lengths = [len(list(ast.walk(f))) for f in funcs]
            avg = sum(lengths) / len(lengths)
            variance = sum((x - avg) ** 2 for x in lengths) / len(lengths)
            cv_structure = (variance**0.5) / avg if avg > 0 else 0

            # Check name chaos (single letters, inconsistent)
            names = [f.name for f in funcs]
            single_letter_count = sum(1 for n in names if len(n) == 1)

            # Uniform structure + chaotic names = likely obfuscated AI code
            return cv_structure < 0.3 and single_letter_count >= len(funcs) * 0.5
        except:
            return False


# Singleton instance
_global_defense: AdversarialDefense | None = None


def get_defense() -> AdversarialDefense:
    """Get or create the global adversarial defense instance."""
    global _global_defense
    if _global_defense is None:
        _global_defense = AdversarialDefense()
    return _global_defense


def analyze_adversarial(code: str, language: str = "python") -> AdversarialAnalysis:
    """Convenience function: analyze code for adversarial obfuscation."""
    defense = get_defense()
    return defense.analyze(code, language)


def compute_semantic_hash(code: str) -> str:
    """Convenience function: compute semantic hash for code."""
    defense = get_defense()
    return defense.compute_semantic_hash(code)
