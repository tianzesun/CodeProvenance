"""AI Model Fingerprinting - guess which AI tool's *style* a piece of code resembles.

Different assistants have habits in how they comment:
- GPT-4: narrating comments ("Here's", "Let's", "First, we", "Step 1:")
- Claude: "I'll", "Safety check", "Handle edge case", "Ensure ..."
- Gemini: imperative summaries ("Calculates ...", "Implements ...")

READ THIS BEFORE USING THE OUTPUT. Style-based attribution is a heuristic, not evidence that AI
was used, and humans write "# First, we ..." too. This version therefore:
- reads real COMMENTS (tokenizer / scanner), so a ``#`` inside a string, or a ``//`` comment in
  Java or JavaScript, is handled correctly;
- never names a model from structure alone: at least two matching comments are required, and
  structural traits (docstrings everywhere, full annotations, uniform functions, try/except) only
  add a small bonus to that textual evidence - they are what a course style guide asks of every
  student (the UofT CS1 design recipe requires docstrings and annotations);
- no longer reports "Copilot" for any code that happens to have few comments. Copilot has no
  reliable textual signature, so it is not scored; ``# TODO:`` / ``# FIXME:`` are human markers.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass
from typing import Any

from .ast_analyzer import ASTAnalyzer, _parse

# Model-specific comment patterns (matched against "# <comment text>")
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

#: Kept for compatibility only. These are human markers (TODO/FIXME) and generic phrases, not a
#: Copilot signature, and they are NOT used for scoring.
COPILOT_COMMENT_PATTERNS = [
    r"#\s*TODO:",
    r"#\s*FIXME:",
    r"#\s*BUG:",
    r"#\s*HACK:",
    r"#\s*\w+\s+-\s+\w+",
]

GEMINI_COMMENT_PATTERNS = [
    r"#\s*To\s+\w+",
    r"#\s*Implements?\s+",
    r"#\s*Returns?\s+",
    r"#\s*Calculates?\s+",
    r"#\s*Processes?\s+",
]

#: Minimum matching comments before a model may be named.
MIN_MATCHED_COMMENTS = 2
#: Minimum combined score before a model may be named.
DETECTION_FLOOR = 0.35
#: Style attribution is never reported with more confidence than this.
MAX_CONFIDENCE = 0.8
DISCLAIMER = "Style-based attribution is heuristic and is not evidence that AI was used."

_PYTHON = frozenset({"python", "py", "python3"})
_HASH_LANGS = frozenset({"python", "py", "python3", "ruby", "rb", "shell", "bash", "sh", "r", "yaml", "perl"})
_CLIKE_LANGS = frozenset(
    {"java", "javascript", "js", "typescript", "ts", "c", "cpp", "c++", "cc", "cs", "csharp", "c#",
     "go", "rust", "rs", "kotlin", "kt", "swift", "scala", "php", "dart"}
)  # fmt: skip


def extract_comments(code: str, language: str = "python") -> list[tuple[int, str]]:
    """``[(line_number, comment_body)]`` for the real comments in ``code``.

    Python uses the tokenizer (a ``#`` inside a string is not a comment). C-like languages use
    a small scanner for ``//`` and ``/* */`` that skips string literals. Anything unknown falls
    back to full-line ``#`` comments.
    """
    language = str(language or "python").strip().lower()
    if language in _PYTHON:
        return _python_comments(code)
    if language in _CLIKE_LANGS:
        return _clike_comments(code)
    return _line_hash_comments(code)


def _line_hash_comments(code: str) -> list[tuple[int, str]]:
    out = []
    for number, line in enumerate(code.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            out.append((number, stripped[1:]))
    return out


def _python_comments(code: str) -> list[tuple[int, str]]:
    comments: list[tuple[int, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.COMMENT:
                comments.append((token.start[0], token.string.lstrip("#")))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        # Broken source: keep what was read, else fall back to full-line comments.
        return comments or _line_hash_comments(code)
    return comments


def _clike_comments(code: str) -> list[tuple[int, str]]:
    comments: list[tuple[int, str]] = []
    i, n, line = 0, len(code), 1
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if ch == "\n":
            line += 1
            i += 1
        elif ch == "/" and nxt == "/":
            end = code.find("\n", i)
            end = n if end < 0 else end
            comments.append((line, code[i + 2 : end]))
            i = end
        elif ch == "/" and nxt == "*":
            end = code.find("*/", i + 2)
            end = n if end < 0 else end
            body = code[i + 2 : end]
            for offset, part in enumerate(body.split("\n")):
                comments.append((line + offset, part.lstrip("* \t")))
            line += body.count("\n")
            i = end + 2
        elif ch in "\"'`":
            quote, i = ch, i + 1
            while i < n and code[i] != quote:
                if code[i] == "\\":
                    i += 1
                elif code[i] == "\n":
                    line += 1
                    if quote != "`":  # unterminated ordinary string: stop at end of line
                        break
                i += 1
            i += 1
        else:
            i += 1
    return comments


@dataclass
class ModelFingerprint:
    """Results from model fingerprinting analysis."""

    detected_model: str | None
    confidence: float  # 0-1
    model_scores: dict[str, float]  # Model name -> score
    evidence: list[str]  # List of detected patterns

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detected_model": self.detected_model,
            "confidence": round(self.confidence, 3),
            "model_scores": {k: round(v, 3) for k, v in self.model_scores.items()},
            "evidence": self.evidence[:10],  # Limit evidence list
            "note": DISCLAIMER,
        }


class ModelFingerprinter:
    """Guess which AI model's comment style code resembles (see the module warning)."""

    def __init__(self):
        """Initialize fingerprinter with (pre-compiled) pattern libraries."""
        self.patterns = {
            "GPT-4": GPT4_COMMENT_PATTERNS,
            "Claude": CLAUDE_COMMENT_PATTERNS,
            "Gemini": GEMINI_COMMENT_PATTERNS,
        }
        self._compiled = {
            name: [re.compile(p, re.IGNORECASE) for p in patterns] for name, patterns in self.patterns.items()
        }
        self._ast = ASTAnalyzer()

    def analyze(self, code: str, language: str = "python") -> ModelFingerprint:
        """Analyze code and report the model whose comment style it most resembles, if any."""
        if not isinstance(code, str) or len(code.strip()) < 20:
            return ModelFingerprint(detected_model=None, confidence=0.0, model_scores={}, evidence=[])
        language = str(language or "python").strip().lower()

        comments = extract_comments(code, language)
        n_lines = max(1, code.count("\n") + 1)

        text_scores: dict[str, float] = {}
        matches: dict[str, list[str]] = {}
        for model_name in self.patterns:
            score, hits = self._score_model(comments, model_name, n_lines)
            text_scores[model_name], matches[model_name] = score, hits

        bonus, bonus_notes = self._structural_bonus(code, language)
        model_scores: dict[str, float] = {}
        for model_name, score in text_scores.items():
            # Structure only AMPLIFIES textual evidence; it can never name a model by itself.
            model_scores[model_name] = min(1.0, score + bonus.get(model_name, 0.0)) if score > 0 else 0.0

        eligible = {m: s for m, s in model_scores.items() if len(matches[m]) >= MIN_MATCHED_COMMENTS}
        if not eligible or max(eligible.values()) < DETECTION_FLOOR:
            return ModelFingerprint(detected_model=None, confidence=0.0, model_scores=model_scores, evidence=[])

        detected_model, confidence = max(eligible.items(), key=lambda item: item[1])
        runner_up = max((s for m, s in model_scores.items() if m != detected_model), default=0.0)
        if confidence - runner_up < 0.15:
            confidence *= 0.7  # ambiguous between models
        evidence = [f"Comment: {text}" for text in matches[detected_model][:8]]
        evidence += bonus_notes.get(detected_model, [])
        return ModelFingerprint(
            detected_model=detected_model,
            confidence=min(MAX_CONFIDENCE, confidence),
            model_scores=model_scores,
            evidence=evidence[:10],
        )

    def _score_model(
        self, comments: list[tuple[int, str]], model_name: str, n_lines: int
    ) -> tuple[float, list[str]]:
        """Score a model by how many REAL comments match its patterns.

        Each comment counts once per model (overlapping patterns used to double-count it), and the
        score is ``matches / max(3, 3% of the lines)``: one matching comment in a 10-line file
        used to score 1.0 because the density was divided by the total line count.

        Returns:
            (score [0-1], matched comment texts)
        """
        compiled = self._compiled.get(model_name, [])
        hits: list[str] = []
        for _, body in comments:
            text = "# " + body.strip()
            if any(pattern.match(text) for pattern in compiled):
                hits.append(text[:80])
        if not hits:
            return 0.0, []
        return min(1.0, len(hits) / max(3.0, n_lines * 0.03)), hits

    def _structural_bonus(self, code: str, language: str) -> tuple[dict[str, float], dict[str, list[str]]]:
        """Small (<= 0.25 per model) bonuses from structural traits; Python only."""
        bonus: dict[str, float] = {}
        notes: dict[str, list[str]] = {}
        if language not in _PYTHON:
            return bonus, notes
        tree = _parse(code)
        if tree is None:
            return bonus, notes
        features = self._ast.analyze(code, language)
        if features.function_count >= 3:
            if features.docstring_coverage > 0.7:
                bonus["GPT-4"] = bonus.get("GPT-4", 0.0) + 0.15
                notes.setdefault("GPT-4", []).append("Docstrings on most functions")
            if features.function_length_cv < 0.4:
                bonus["GPT-4"] = bonus.get("GPT-4", 0.0) + 0.10
                notes.setdefault("GPT-4", []).append("Uniform function lengths")
            if features.type_hint_coverage > 0.8:
                bonus["Claude"] = bonus.get("Claude", 0.0) + 0.15
                notes.setdefault("Claude", []).append("Near-complete type annotations")
        if self._try_except_ratio(tree) > 0.5:
            bonus["Claude"] = bonus.get("Claude", 0.0) + 0.10
            notes.setdefault("Claude", []).append("try/except around much of the code")
        return bonus, notes

    # --- Structural analysis helpers (AST-based; the regex versions mis-parsed annotations) ---

    @staticmethod
    def _as_tree(code_or_tree: Any) -> ast.AST | None:
        return code_or_tree if isinstance(code_or_tree, ast.AST) else _parse(code_or_tree)

    @classmethod
    def _docstring_ratio(cls, code: Any) -> float:
        """Ratio of functions with docstrings."""
        tree = cls._as_tree(code)
        if tree is None:
            return 0.0
        functions = ASTAnalyzer._find_functions(tree)
        return sum(1 for f in functions if ast.get_docstring(f)) / len(functions) if functions else 0.0

    @classmethod
    def _type_hint_ratio(cls, code: Any) -> float:
        """Ratio of annotated parameters/returns (``Callable[[int], int]`` used to be split on commas)."""
        tree = cls._as_tree(code)
        return ASTAnalyzer._type_hint_coverage(ASTAnalyzer._find_functions(tree)) if tree is not None else 0.0

    @classmethod
    def _try_except_ratio(cls, code: Any) -> float:
        """try statements relative to if/for/while/def/class statements."""
        tree = cls._as_tree(code)
        if tree is None:
            return 0.0
        tries = blocks = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) or type(node).__name__ == "TryStar":
                tries += 1
            elif isinstance(node, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                blocks += 1
        return tries / max(blocks, 1)

    @staticmethod
    def _comment_density(code: str, language: str = "python") -> float:
        """Ratio of comment lines to total lines (real comments, not ``#`` inside strings)."""
        lines = max(1, code.count("\n") + 1)
        return len({n for n, _ in extract_comments(code, language)}) / lines

    @classmethod
    def _function_length_uniformity(cls, code: Any, language: str = "python") -> float:
        """1.0 when function lengths are identical, 0.0 when they vary a lot (needs 3+ functions)."""
        if str(language).lower() not in _PYTHON:
            return 0.0
        tree = cls._as_tree(code)
        if tree is None:
            return 0.0
        functions = ASTAnalyzer._find_functions(tree)
        if len(functions) < 3:
            return 0.0
        lengths = [float(ASTAnalyzer._function_length(f)) for f in functions]
        mean = sum(lengths) / len(lengths)
        cv = (sum((x - mean) ** 2 for x in lengths) / len(lengths)) ** 0.5 / mean if mean else 0.0
        return max(0.0, min(1.0, 1.0 - cv / 2.0))


# Singleton instance
_global_fingerprinter: ModelFingerprinter | None = None


def get_fingerprinter() -> ModelFingerprinter:
    """Get or create the global fingerprinter instance."""
    global _global_fingerprinter
    if _global_fingerprinter is None:
        _global_fingerprinter = ModelFingerprinter()
    return _global_fingerprinter


def detect_model(code: str, language: str = "python") -> ModelFingerprint:
    """Convenience function: guess which AI model's comment style code resembles."""
    return get_fingerprinter().analyze(code, language)
