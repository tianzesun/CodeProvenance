"""AI Model Fingerprinting - Detect which AI tool generated code.

Different AI models have distinctive "signatures" in their output:
- GPT-4: Verbose comments, "Here's", "Let's", excessive docstrings
- Claude: Type hints everywhere, defensive error handling, "I'll"
- Copilot: Minimal comments, idiomatic code, follows context
- Gemini: Functional style, "To [verb]", explicit naming

This module analyzes code patterns to identify the likely source model.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

# Model-specific comment patterns
GPT4_COMMENT_PATTERNS = [
    r"#\s*Here'?s\s+(?:a|an|the|how)",
    r"#\s*Let'?s\s+",
    r"#\s*This\s+(?:function|code|method|class)\s+",
    r"#\s*The\s+following",
    r"#\s*Now\s+we",
    r"#\s*First,?\s+we",
    r"#\s*Next,?\s+we",
    r"#\s*Finally,?\s+",
    r"#\s*Step\s+\d+:",
    r"#\s*Note\s+that",
    r"#\s*In\s+(?:this|order|summary)",
    r"#\s*To\s+(?:solve|implement|create|handle)",
    r"#\s*This\s+(?:will|should|can)\s+",
    r"#\s*We\s+(?:can|need|should|will)\s+",
]

CLAUDE_COMMENT_PATTERNS = [
    r"#\s*I'?ll\s+",
    r"#\s*We\s+can\s+",
    r"#\s*(?:Important|Note):\s+",
    r"#\s*Safety\s+check",
    r"#\s*Validate\s+",
    r"#\s*Error\s+handling",
    r"#\s*Handle\s+edge\s+case",
    r"#\s*(?:Ensure|Make sure)\s+",
    r"#\s*Type\s+hint",
]

COPILOT_COMMENT_PATTERNS = [
    r"#\s*TODO:",
    r"#\s*FIXME:",
    r"#\s*BUG:",
    r"#\s*HACK:",
    r"#\s*\w+\s+-\s+\w+",  # "foo - does bar" style
]

GEMINI_COMMENT_PATTERNS = [
    r"#\s*To\s+\w+",
    r"#\s*Implements?\s+",
    r"#\s*Returns?\s+",
    r"#\s*Calculates?\s+",
    r"#\s*Processes?\s+",
]


@dataclass
class ModelFingerprint:
    """Results from model fingerprinting analysis."""

    detected_model: str | None
    confidence: float  # 0-1
    model_scores: dict[str, float]  # Model name → score
    evidence: list[str]  # List of detected patterns

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detected_model": self.detected_model,
            "confidence": round(self.confidence, 3),
            "model_scores": {k: round(v, 3) for k, v in self.model_scores.items()},
            "evidence": self.evidence[:10],  # Limit evidence list
        }


class ModelFingerprinter:
    """Detect which AI model likely generated code."""

    def __init__(self):
        """Initialize fingerprinter with pattern libraries."""
        self.patterns = {
            "GPT-4": GPT4_COMMENT_PATTERNS,
            "Claude": CLAUDE_COMMENT_PATTERNS,
            "Copilot": COPILOT_COMMENT_PATTERNS,
            "Gemini": GEMINI_COMMENT_PATTERNS,
        }

    def analyze(self, code: str, language: str = "python") -> ModelFingerprint:
        """Analyze code and detect likely AI model.

        Args:
            code: Source code to analyze
            language: Programming language (affects some patterns)

        Returns:
            ModelFingerprint with detection results
        """
        if not code or len(code.strip()) < 20:
            return ModelFingerprint(
                detected_model=None, confidence=0.0, model_scores={}, evidence=[]
            )

        # Compute scores for each model
        model_scores = {}
        all_evidence = {}

        for model_name in self.patterns:
            score, evidence = self._score_model(code, model_name, language)
            model_scores[model_name] = score
            all_evidence[model_name] = evidence

        # Add structural fingerprints
        structural_scores = self._structural_fingerprints(code, language)
        for model_name, score in structural_scores.items():
            model_scores[model_name] = max(model_scores.get(model_name, 0.0), score)

        # Determine winner
        if not model_scores or max(model_scores.values()) < 0.2:
            return ModelFingerprint(
                detected_model=None, confidence=0.0, model_scores=model_scores, evidence=[]
            )

        best_model = max(model_scores.items(), key=lambda x: x[1])
        detected_model = best_model[0]
        confidence = best_model[1]

        # Lower confidence if scores are close
        sorted_scores = sorted(model_scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] - sorted_scores[1] < 0.15:
            confidence *= 0.7  # Reduce confidence if ambiguous

        return ModelFingerprint(
            detected_model=detected_model,
            confidence=min(1.0, confidence),
            model_scores=model_scores,
            evidence=all_evidence.get(detected_model, [])[:10],
        )

    def _score_model(self, code: str, model_name: str, language: str) -> tuple[float, list[str]]:
        """Score code against a specific model's patterns.

        Returns:
            (score [0-1], list of matched patterns)
        """
        patterns = self.patterns.get(model_name, [])
        if not patterns:
            return 0.0, []

        matches = []
        for pattern in patterns:
            found = re.findall(pattern, code, re.IGNORECASE)
            if found:
                matches.extend(found[:3])  # Limit per pattern

        if not matches:
            return 0.0, []

        # Score based on match density
        lines = code.split("\n")
        match_density = len(matches) / max(len(lines), 1)

        # Normalize: 3+ matches per 100 lines = strong signal
        score = min(1.0, match_density * 100 / 3)

        return score, matches

    def _structural_fingerprints(self, code: str, language: str) -> dict[str, float]:
        """Detect model-specific structural patterns.

        Returns:
            Dict of model_name → structural_score
        """
        scores = {}

        # GPT-4: Excessive docstrings
        if language == "python":
            docstring_ratio = self._docstring_ratio(code)
            if docstring_ratio > 0.7:
                scores["GPT-4"] = 0.6

        # Claude: Type hints everywhere
        if language == "python":
            type_hint_ratio = self._type_hint_ratio(code)
            if type_hint_ratio > 0.8:
                scores["Claude"] = 0.7

        # Claude: Try/except wrapping everything
        try_except_ratio = self._try_except_ratio(code)
        if try_except_ratio > 0.5:
            scores["Claude"] = max(scores.get("Claude", 0.0), 0.5)

        # Copilot: Minimal comments
        comment_density = self._comment_density(code)
        if comment_density < 0.05:
            scores["Copilot"] = 0.4

        # GPT-4: Uniform function lengths
        function_uniformity = self._function_length_uniformity(code, language)
        if function_uniformity > 0.8:
            scores["GPT-4"] = max(scores.get("GPT-4", 0.0), 0.5)

        # Gemini: Functional style (many small functions)
        if language == "python":
            function_density = self._function_density(code)
            if function_density > 0.3:
                scores["Gemini"] = 0.5

        return scores

    # --- Structural analysis helpers ---

    @staticmethod
    def _docstring_ratio(code: str) -> float:
        """Ratio of functions with docstrings."""
        func_pattern = r"^\s*def\s+\w+"
        docstring_pattern = r'^\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')'

        lines = code.split("\n")
        func_count = 0
        docstring_count = 0

        i = 0
        while i < len(lines):
            if re.match(func_pattern, lines[i]):
                func_count += 1
                # Check next few lines for docstring
                for j in range(i + 1, min(i + 5, len(lines))):
                    if re.match(docstring_pattern, lines[j]):
                        docstring_count += 1
                        break
                    if lines[j].strip() and not lines[j].strip().startswith("#"):
                        break  # Found code before docstring
            i += 1

        return docstring_count / func_count if func_count > 0 else 0.0

    @staticmethod
    def _type_hint_ratio(code: str) -> float:
        """Ratio of function parameters with type hints."""
        # Match function definitions
        func_pattern = r"def\s+\w+\s*\((.*?)\)(?:\s*->\s*[\w\[\],\s]+)?:"
        matches = re.findall(func_pattern, code, re.MULTILINE)

        if not matches:
            return 0.0

        total_params = 0
        typed_params = 0

        for params_str in matches:
            params = [p.strip() for p in params_str.split(",") if p.strip()]
            for param in params:
                if param and param != "self" and param != "cls":
                    total_params += 1
                    if ":" in param:
                        typed_params += 1

        return typed_params / total_params if total_params > 0 else 0.0

    @staticmethod
    def _try_except_ratio(code: str) -> float:
        """Ratio of code blocks wrapped in try/except."""
        try_count = len(re.findall(r"\btry\s*:", code))
        statement_count = len(re.findall(r"^\s*(?:if|for|while|def|class)\s+", code, re.MULTILINE))

        return try_count / max(statement_count, 1)

    @staticmethod
    def _comment_density(code: str) -> float:
        """Ratio of comment lines to total lines."""
        lines = code.split("\n")
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        return comment_lines / max(len(lines), 1)

    @staticmethod
    def _function_length_uniformity(code: str, language: str) -> float:
        """Measure uniformity of function lengths (CV coefficient)."""
        if language != "python":
            return 0.0

        # Find function definitions
        func_pattern = r"^\s*def\s+\w+"
        lines = code.split("\n")

        func_lengths = []
        current_length = 0
        in_function = False
        base_indent = 0

        for line in lines:
            if re.match(func_pattern, line):
                if in_function and current_length > 0:
                    func_lengths.append(current_length)
                in_function = True
                current_length = 1
                # Detect indentation level
                base_indent = len(line) - len(line.lstrip())
            elif in_function:
                stripped = line.strip()
                if not stripped:
                    current_length += 1
                elif stripped.startswith("#"):
                    current_length += 1
                else:
                    # Check if we've exited the function
                    indent = len(line) - len(line.lstrip())
                    if indent <= base_indent and stripped:
                        # Exited function
                        func_lengths.append(current_length)
                        in_function = False
                        current_length = 0
                    else:
                        current_length += 1

        if in_function and current_length > 0:
            func_lengths.append(current_length)

        if len(func_lengths) < 2:
            return 0.0

        # Compute coefficient of variation
        mean_length = sum(func_lengths) / len(func_lengths)
        if mean_length == 0:
            return 0.0

        variance = sum((x - mean_length) ** 2 for x in func_lengths) / len(func_lengths)
        cv = (variance**0.5) / mean_length

        # Low CV = uniform = AI-like
        # Return 1.0 - normalized CV (so uniform = high score)
        return max(0.0, min(1.0, 1.0 - cv / 2.0))

    @staticmethod
    def _function_density(code: str) -> float:
        """Ratio of function definitions to total lines."""
        lines = code.split("\n")
        func_count = len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE))
        return func_count / max(len(lines), 1) * 10  # Scale up


# Singleton instance
_global_fingerprinter: ModelFingerprinter | None = None


def get_fingerprinter() -> ModelFingerprinter:
    """Get or create the global fingerprinter instance."""
    global _global_fingerprinter
    if _global_fingerprinter is None:
        _global_fingerprinter = ModelFingerprinter()
    return _global_fingerprinter


def detect_model(code: str, language: str = "python") -> ModelFingerprint:
    """Convenience function: detect which AI model generated code.

    Args:
        code: Source code to analyze
        language: Programming language

    Returns:
        ModelFingerprint with detection results
    """
    fingerprinter = get_fingerprinter()
    return fingerprinter.analyze(code, language)
