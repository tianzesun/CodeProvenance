"""Adversarial defense module - detect obfuscated or paraphrased code.

Evasion techniques considered:
1. Variable / parameter / function renaming
2. Comment and docstring stripping
3. Reordering functions
4. Paraphrasing ("rewrite this in a different style")

Techniques:
- Semantic hash: AST-based, identical under consistent renaming of every name the file binds,
  under comment/docstring removal and under added/removed annotations.
- Function-level hashes, so reordering functions does not defeat a comparison.
- Obfuscation and paraphrase indicators.

The indicators are HEURISTICS, deliberately conservative, and informational: ordinary human code
trips some of them, so ``evasion_detected`` must never be used alone as evidence of misconduct.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

from .ast_analyzer import _FUNC_NODES, _parse
from .model_fingerprinting import extract_comments

logger = logging.getLogger(__name__)

_PYTHON = frozenset({"python", "py", "python3"})
#: Single-letter names that are ordinary loop / index / coordinate conventions, not obfuscation.
_CONVENTIONAL_NAMES = frozenset({"_", "i", "j", "k", "n", "m", "x", "y"})
_MIN_LINES_FOR_INDICATORS = 30


@dataclass
class AdversarialAnalysis:
    """Results from adversarial resistance analysis."""

    semantic_hash: str
    obfuscation_score: float  # 0-1, higher = likely obfuscated
    paraphrase_indicators: list[str]
    evasion_detected: bool
    confidence: float
    #: False when the code could not be analysed (not Python / syntax error): every other field
    #: is then a default meaning "unknown", not "clean".
    analyzed: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "semantic_hash": self.semantic_hash,
            "obfuscation_score": round(self.obfuscation_score, 3),
            "paraphrase_indicators": self.paraphrase_indicators[:5],
            "evasion_detected": self.evasion_detected,
            "confidence": round(self.confidence, 3),
            "analyzed": self.analyzed,
        }


# ---------------------------------------------------------------------------------------------
# Name binding / normalisation
# ---------------------------------------------------------------------------------------------


def _bound_names(tree: ast.AST) -> dict[str, str]:
    """Names the file BINDS, mapped to a role (``F`` function, ``C`` class, ``V`` other).

    Covers assignments and loop/comprehension/walrus targets, function and lambda parameters
    (every kind), function and class names, import aliases, ``except ... as``, ``global`` /
    ``nonlocal`` and match-pattern captures. Free names (``len``, ``print``, imported modules)
    are not bound and keep their identity.
    """
    kinds: dict[str, str] = {}

    def bind(name: str | None, kind: str) -> None:
        if not name:
            return
        current = kinds.get(name)
        if current is None or (kind == "F") or (kind == "C" and current == "V"):
            kinds[name] = kind

    for node in ast.walk(tree):
        if isinstance(node, _FUNC_NODES):
            bind(node.name, "F")
        elif isinstance(node, ast.ClassDef):
            bind(node.name, "C")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bind(node.id, "V")
        elif isinstance(node, ast.arg):
            bind(node.arg, "V")
        elif isinstance(node, ast.ExceptHandler):
            bind(node.name, "V")
        elif isinstance(node, ast.alias):
            bind(node.asname, "V")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                bind(name, "V")
        elif type(node).__name__ in ("MatchAs", "MatchStar"):
            bind(getattr(node, "name", None), "V")
        elif type(node).__name__ == "MatchMapping":
            bind(getattr(node, "rest", None), "V")
    return kinds


class _Normalizer(ast.NodeTransformer):
    """Rename bound names by order of first appearance; drop docstrings and annotations."""

    def __init__(self, kinds: dict[str, str]):
        self._kinds = kinds
        self._map: dict[str, str] = {}
        self._counters = {"F": 0, "C": 0, "V": 0}

    def _rename(self, name: str | None) -> str | None:
        kind = self._kinds.get(name) if name else None
        if kind is None:
            return name  # free name: builtin / imported module / attribute owner
        if name not in self._map:
            self._map[name] = f"{kind}{self._counters[kind]}"
            self._counters[kind] += 1
        return self._map[name]

    @staticmethod
    def _strip_docstring(node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            del body[0]
            if not body:
                body.append(ast.Pass())

    def visit_Module(self, node):
        self._strip_docstring(node)
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._strip_docstring(node)
        node.name = self._rename(node.name)
        return self.generic_visit(node)

    def _visit_function(self, node):
        self._strip_docstring(node)
        node.name = self._rename(node.name)
        node.returns = None  # annotations are removable noise
        return self.generic_visit(node)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_arg(self, node):
        node.arg = self._rename(node.arg)
        node.annotation = None
        return node

    def visit_Name(self, node):
        node.id = self._rename(node.id)
        return node

    def visit_ExceptHandler(self, node):
        node.name = self._rename(node.name)
        return self.generic_visit(node)

    def visit_alias(self, node):
        if node.asname:
            node.asname = self._rename(node.asname)
        return node

    def visit_Global(self, node):
        node.names = [self._rename(n) for n in node.names]
        return node

    visit_Nonlocal = visit_Global

    def visit_MatchAs(self, node):
        node.name = self._rename(node.name)
        return self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        node.rest = self._rename(node.rest)
        return self.generic_visit(node)


def _fallback_hash(code: str) -> str:
    """Hash of whitespace-normalised text (for code that is not parseable Python)."""
    lines = (" ".join(line.split()) for line in str(code).splitlines())
    text = "\n".join(line for line in lines if line)
    return hashlib.sha256(b"text\0" + text.encode("utf-8", "surrogatepass")).hexdigest()


def _normalized_digest(tree: ast.AST) -> str:
    kinds = _bound_names(tree)
    normalized = _Normalizer(kinds).visit(tree)
    ast.fix_missing_locations(normalized)
    return hashlib.sha256(b"ast\0" + ast.unparse(normalized).encode("utf-8", "surrogatepass")).hexdigest()


class AdversarialDefense:
    """Detect and resist code obfuscation attacks."""

    def analyze(self, code: str, language: str = "python") -> AdversarialAnalysis:
        """Analyze code for adversarial obfuscation attempts.

        Args:
            code: Source code to analyze
            language: Programming language (Python only; any case)

        Returns:
            AdversarialAnalysis. ``analyzed`` is False when the code could not be analysed.
        """
        if str(language or "python").strip().lower() not in _PYTHON:
            return self._default_analysis(code)
        tree = _parse(code)
        if tree is None:
            return self._default_analysis(code)
        try:
            semantic_hash = self.compute_semantic_hash(code)
            obfuscation_score = self._detect_obfuscation(tree, code)
            paraphrase_indicators = self._detect_paraphrase_indicators(tree, code)
            evasion_detected = obfuscation_score > 0.5 or len(paraphrase_indicators) > 2
            return AdversarialAnalysis(
                semantic_hash=semantic_hash,
                obfuscation_score=obfuscation_score,
                paraphrase_indicators=paraphrase_indicators,
                evasion_detected=evasion_detected,
                confidence=self._compute_confidence(obfuscation_score, paraphrase_indicators),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Adversarial analysis failed: %s", exc)
            return self._default_analysis(code)

    # ------------------------------------------------------------------ semantic hashing

    @staticmethod
    def compute_semantic_hash(code: str) -> str:
        """AST-based hash that is stable under renaming, comment removal and reformatting.

        Identical for two programs that differ only in the names of everything they bind
        (variables, PARAMETERS, functions, classes, import aliases, exception variables),
        in comments/docstrings/annotations, or in formatting. The old version renamed only
        ``Name`` nodes, so ``def f(x): return x`` and ``def f(y): return y`` hashed differently,
        and it renamed built-ins too, so ``len(a)`` and ``sum(a)`` hashed THE SAME.
        Unparseable code gets a whitespace-normalised text hash instead.
        """
        tree = _parse(code)
        if tree is None:
            return _fallback_hash(code)
        try:
            return _normalized_digest(tree)
        except Exception as exc:  # noqa: BLE001 (e.g. RecursionError in ast.unparse)
            logger.debug("Semantic hash failed: %s", exc)
            return _fallback_hash(code)

    @staticmethod
    def compute_function_hashes(code: str) -> list[str]:
        """One normalised hash per function (sorted), independent of function order.

        Each function is normalised on its own, so a RENAMED helper that is called from
        another function still differs; renaming local names and reordering do not.
        """
        tree = _parse(code)
        if tree is None:
            return []
        hashes = []
        for node in ast.walk(tree):
            if isinstance(node, _FUNC_NODES):
                try:
                    clone = ast.parse(ast.unparse(node))  # detach and normalise independently
                    hashes.append(_normalized_digest(clone))
                except Exception:  # noqa: BLE001
                    continue
        return sorted(hashes)

    @classmethod
    def semantic_similarity(cls, code_a: str, code_b: str) -> float:
        """Order-insensitive structural similarity in [0, 1] (Jaccard over function hashes).

        With no functions on either side it is 1.0 for equal semantic hashes, else 0.0.
        """
        a, b = cls.compute_function_hashes(code_a), cls.compute_function_hashes(code_b)
        if not a and not b:
            return 1.0 if cls.compute_semantic_hash(code_a) == cls.compute_semantic_hash(code_b) else 0.0
        union = len(a) + len(b)
        shared = 0
        remaining = list(b)
        for h in a:  # multiset intersection
            if h in remaining:
                remaining.remove(h)
                shared += 1
        return shared / (union - shared) if union - shared else 1.0

    # ------------------------------------------------------------------ obfuscation

    @staticmethod
    def _as_tree(code_or_tree: Any) -> ast.AST | None:
        return code_or_tree if isinstance(code_or_tree, ast.AST) else _parse(code_or_tree)

    def _detect_obfuscation(self, tree: Any, code: str | None = None) -> float:
        """Obfuscation score in [0, 1] from naming and documentation signals.

        ``tree`` may also be the source string (the old signature).
        """
        if code is None and isinstance(tree, str):
            code = tree
        tree = self._as_tree(tree)
        if tree is None:
            return 0.0
        code = code or ""
        score = 0.0

        single_letter_ratio = self._single_letter_name_ratio(tree)
        if single_letter_ratio > 0.5:
            score += 0.3
        elif single_letter_ratio > 0.3:
            score += 0.15

        # No comments AND no docstrings in a longer file (weak: many people write neither).
        if code.count("\n") + 1 > 20 and self._comment_density(code) == 0 and not self._has_docstrings(tree):
            score += 0.1

        if self._naming_style_inconsistency(tree) > 0.6:
            score += 0.2

        if self._has_complexity_name_mismatch(tree, code):
            score += 0.25

        return min(1.0, score)

    @staticmethod
    def _meaningful_names(tree: ast.AST) -> list[str]:
        """Distinct function/variable/parameter names, minus classes and dunders."""
        return [
            name
            for name, kind in _bound_names(tree).items()
            if kind != "C" and not (name.startswith("__") and name.endswith("__"))
        ]

    @classmethod
    def _single_letter_name_ratio(cls, code_or_tree: Any) -> float:
        """Share of DISTINCT bound names that are unconventional single letters.

        Counted per distinct name (not per occurrence), ignoring the usual ``i j k n m x y _``,
        and only for files with at least six names. It was ``Name`` occurrences, so any numeric
        or loop-heavy program full of ``i``/``x``/``n`` looked obfuscated.
        """
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return 0.0
        names = cls._meaningful_names(tree)
        if len(names) < 6:
            return 0.0
        terse = [n for n in names if len(n) == 1 and n not in _CONVENTIONAL_NAMES]
        return len(terse) / len(names)

    @staticmethod
    def _comment_density(code: str) -> float:
        """Ratio of real comment lines to total lines."""
        lines = max(1, code.count("\n") + 1)
        return len({n for n, _ in extract_comments(code, "python")}) / lines

    @staticmethod
    def _has_docstrings(tree: ast.AST) -> bool:
        return any(
            isinstance(node, (*_FUNC_NODES, ast.ClassDef, ast.Module)) and ast.get_docstring(node)
            for node in ast.walk(tree)
        )

    @classmethod
    def _naming_style_inconsistency(cls, code_or_tree: Any) -> float:
        """Disagreement between snake_case and camelCase among function/variable names.

        Role-aware: PEP 8 code legitimately mixes snake_case functions, CamelCase classes and
        UPPER_CASE constants, and it used to be scored as maximally inconsistent (0.5-1.0).
        Classes, constants, dunders and single letters are now ignored. The result is 0 for
        fewer than four styled names, else ``2 * minority / total`` (0 = one style, 1 = even mix).
        """
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return 0.0
        snake = camel = 0
        for name in cls._meaningful_names(tree):
            core = name.lstrip("_")
            if len(core) < 2 or core.isupper():
                continue
            if "_" in core and core == core.lower():
                snake += 1
            elif "_" not in core and core[0].islower() and any(c.isupper() for c in core[1:]):
                camel += 1
        total = snake + camel
        return 0.0 if total < 4 else 2.0 * min(snake, camel) / total

    @classmethod
    def _has_complexity_name_mismatch(cls, code_or_tree: Any, code: str | None = None) -> bool:
        """Substantial code whose distinct names are all very short (average < 2.5 characters)."""
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return False
        if code is None and isinstance(code_or_tree, str):
            code = code_or_tree
        if (code or "").count("\n") + 1 < 20:
            return False
        names = [n for n in cls._meaningful_names(tree) if n not in _CONVENTIONAL_NAMES]
        if len(names) < 6:
            return False
        return sum(len(n) for n in names) / len(names) < 2.5

    # ------------------------------------------------------------------ paraphrase indicators

    def _detect_paraphrase_indicators(self, tree: Any, code: str | None = None) -> list[str]:
        """Indicators that code was rewritten in a mixed style (informational, conservative).

        Only evaluated for files of at least 30 lines, with thresholds that need a real
        sample (five comments, four or five functions): the earlier thresholds fired on
        ordinary human code (partially documented functions, some with try/except, comments of
        varying length), so most programs with a few functions were flagged as "evasion".
        """
        if code is None and isinstance(tree, str):
            code = tree
        tree = self._as_tree(tree)
        code = code or ""
        if tree is None or code.count("\n") + 1 < _MIN_LINES_FOR_INDICATORS:
            return []

        indicators = []
        if self._has_mixed_comment_style(code):
            indicators.append("Mixed comment style")
        if self._has_inconsistent_naming(tree):
            indicators.append("Inconsistent naming pattern")
        coverage = self._docstring_coverage_variance(tree)
        functions = [n for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        if len(functions) >= 5 and 0.3 < coverage < 0.7:
            indicators.append("Partial docstring coverage")
        if self._has_mixed_defensive_style(tree):
            indicators.append("Mixed defensive programming")
        if self._has_structure_name_discord(tree):
            indicators.append("Structure-naming mismatch")
        return indicators

    @staticmethod
    def _default_analysis(code: str = "") -> AdversarialAnalysis:
        """Analysis for input that could not be analysed (``analyzed=False``)."""
        return AdversarialAnalysis(
            semantic_hash=_fallback_hash(code) if code else "",
            obfuscation_score=0.0,
            paraphrase_indicators=[],
            evasion_detected=False,
            confidence=0.0,
            analyzed=False,
        )

    @staticmethod
    def _compute_confidence(obfuscation_score: float, indicators: list[str]) -> float:
        """Confidence in the evasion finding; 0.0 when there is nothing to be confident about
        (it returned 0.3 for code with no signal at all)."""
        if obfuscation_score > 0.7 or len(indicators) >= 4:
            return 0.9
        if obfuscation_score > 0.5 or len(indicators) >= 2:
            return 0.7
        if obfuscation_score > 0.3 or len(indicators) >= 1:
            return 0.5
        return 0.0

    @staticmethod
    def _has_mixed_comment_style(code: str) -> bool:
        """Verbose and terse comments mixed (needs five real comments)."""
        lengths = [len(body.strip()) for _, body in extract_comments(code, "python") if body.strip()]
        if len(lengths) < 5:
            return False
        avg = sum(lengths) / len(lengths)
        cv = (sum((x - avg) ** 2 for x in lengths) / len(lengths)) ** 0.5 / avg if avg > 0 else 0.0
        return cv > 1.2

    @classmethod
    def _has_inconsistent_naming(cls, code_or_tree: Any) -> bool:
        """Descriptive and terse function names mixed (needs four functions)."""
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return False
        lengths = [len(n.name) for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        if len(lengths) < 4:
            return False
        avg = sum(lengths) / len(lengths)
        return (sum((x - avg) ** 2 for x in lengths) / len(lengths)) ** 0.5 / avg > 0.9 if avg > 0 else False

    @classmethod
    def _docstring_coverage_variance(cls, code_or_tree: Any) -> float:
        """Docstring coverage over functions (0-1)."""
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return 0.0
        functions = [n for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        return sum(1 for f in functions if ast.get_docstring(f)) / len(functions) if functions else 0.0

    @classmethod
    def _has_mixed_defensive_style(cls, code_or_tree: Any) -> bool:
        """Between 30% and 70% of at least five functions use try/except."""
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return False
        functions = [n for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        if len(functions) < 5:
            return False
        with_try = sum(
            1
            for f in functions
            if any(isinstance(n, ast.Try) or type(n).__name__ == "TryStar" for n in ast.walk(f))
        )
        return 0.3 <= with_try / len(functions) <= 0.7

    @classmethod
    def _has_structure_name_discord(cls, code_or_tree: Any) -> bool:
        """Uniform function sizes but mostly single-letter function names."""
        tree = cls._as_tree(code_or_tree)
        if tree is None:
            return False
        functions = [n for n in ast.walk(tree) if isinstance(n, _FUNC_NODES)]
        if len(functions) < 3:
            return False
        lengths = [sum(1 for _ in ast.walk(f)) for f in functions]
        avg = sum(lengths) / len(lengths)
        cv = (sum((x - avg) ** 2 for x in lengths) / len(lengths)) ** 0.5 / avg if avg > 0 else 0.0
        single = sum(1 for f in functions if len(f.name) == 1)
        return cv < 0.3 and single >= len(functions) * 0.5


# Singleton instance
_global_defense: AdversarialDefense | None = None


def get_defense() -> AdversarialDefense:
    """Get or create the global adversarial defense instance (stateless)."""
    global _global_defense
    if _global_defense is None:
        _global_defense = AdversarialDefense()
    return _global_defense


def analyze_adversarial(code: str, language: str = "python") -> AdversarialAnalysis:
    """Convenience function: analyze code for adversarial obfuscation."""
    return get_defense().analyze(code, language)


def compute_semantic_hash(code: str) -> str:
    """Convenience function: compute the semantic hash for code."""
    return get_defense().compute_semantic_hash(code)
