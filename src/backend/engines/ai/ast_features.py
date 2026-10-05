"""Tree-sitter AST feature extraction for AI-generated code detection.

Extracts a fixed-length numeric feature vector from source code using
tree-sitter for each supported language (Python, Java, C/C++, C#, JavaScript,
TypeScript, Go, Rust). Designed to feed the AI ensemble scorer and the machine
learning classifier.

Degrades gracefully: if tree-sitter (or the language binding) is unavailable,
the extractor falls back to lexical features so the pipeline never crashes.
"""

from __future__ import annotations

import keyword
import logging
import math
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

_LANGUAGE_ALIASES = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "c++": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "cs": "csharp",
    "c#": "csharp",
    "golang": "go",
    "rs": "rust",
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FEATURE_NAMES = (
    "node_type_entropy",
    "cyclomatic_complexity",
    "avg_identifier_length",
    "identifier_length_std",
    "identifier_naming_entropy",
    "comment_to_code_ratio",
    "blank_line_ratio",
    "avg_function_length",
    "avg_class_length",
    "indentation_consistency",
    "whitespace_entropy",
)


def normalize_language(language: str | None) -> str:
    """Lower-case a language name and resolve aliases (``js`` -> ``javascript``)."""
    name = (language or "python").strip().lower()
    return _LANGUAGE_ALIASES.get(name, name)


@dataclass
class ASTFeatureVector:
    """Fixed-length feature vector describing the structural style of code.

    All values are normalised to [0, 1] where meaningful so the vector can be
    passed directly to machine learning classifiers. ``node_type_entropy`` is the
    NORMALISED Shannon entropy of the node-type distribution (1.0 = uniform).
    (The docstring used to call it "bits", and ``to_vector`` and the ensemble
    divided it by 9 as if it were; that squashed the value into [0, 0.11].)
    ``avg_function_length`` / ``avg_class_length`` are in lines.
    """

    node_type_entropy: float = 0.0
    cyclomatic_complexity: float = 0.0
    avg_identifier_length: float = 0.0
    identifier_length_std: float = 0.0
    identifier_naming_entropy: float = 0.0
    comment_to_code_ratio: float = 0.0
    blank_line_ratio: float = 0.0
    avg_function_length: float = 0.0
    avg_class_length: float = 0.0
    indentation_consistency: float = 0.0
    whitespace_entropy: float = 0.0
    function_count: int = 0
    class_count: int = 0
    #: True only for a clean tree-sitter parse. A tree containing syntax errors,
    #: or the lexical fallback, is False; consumers skip the structural features
    #: that are placeholders in that case.
    parse_success: bool = True
    extra: dict[str, float] = field(default_factory=dict)

    FEATURE_MEANINGFUL: ClassVar[tuple[str, ...]] = _FEATURE_NAMES

    def to_vector(self) -> list[float]:
        """Return a fixed-length numeric vector for ML consumption."""
        values = [
            min(1.0, self.node_type_entropy),
            min(1.0, self.cyclomatic_complexity),
            self.avg_identifier_length,
            min(1.0, self.identifier_length_std),
            self.identifier_naming_entropy,
            self.comment_to_code_ratio,
            self.blank_line_ratio,
            min(1.0, self.avg_function_length / 100.0),
            min(1.0, self.avg_class_length / 200.0),
            self.indentation_consistency,
            self.whitespace_entropy,
        ]
        return [round(float(v), 6) for v in values]

    def feature_names(self) -> list[str]:
        """Ordered feature names matching ``to_vector``."""
        return list(_FEATURE_NAMES)

    def as_dict(self) -> dict[str, Any]:
        """Serialisable representation including derived stats."""
        data: dict[str, Any] = {
            name: round(getattr(self, name), 4) for name in _FEATURE_NAMES
        }
        data.update(
            function_count=self.function_count,
            class_count=self.class_count,
            parse_success=self.parse_success,
            extra=self.extra,
        )
        return data


def _safe_entropy(counter: Counter) -> float:
    """Normalised Shannon entropy of a Counter's value distribution.

    Returns 1.0 for uniform distributions, 0.0 for a single symbol.
    """
    total = sum(counter.values())
    if total <= 1 or len(counter) <= 1:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        prob = count / total
        entropy -= prob * math.log2(prob)
    return entropy / math.log2(len(counter))


def _uniq_preserving(items: list[str]) -> list[str]:
    """Deduplicate items preserving order."""
    return list(dict.fromkeys(items))


def _mean(values: list[float]) -> float:
    """Mean of a list, 0.0 for empty input."""
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


# ---------------------------------------------------------------------------
# Process-wide tree-sitter language cache
# ---------------------------------------------------------------------------

# A ``Language`` is immutable and safe to share; building one imports a binding
# package, so it is done once per process instead of once per extractor (and an
# extractor is created per analysis job). Parsers are NOT thread-safe and stay
# per-extractor, guarded by a lock.
_LANGUAGE_CACHE: dict[str, Any] = {}
_LANGUAGE_CACHE_LOCK = threading.Lock()

_LANGUAGE_MODULES = {
    "python": "tree_sitter_python",
    "java": "tree_sitter_java",
    "cpp": "tree_sitter_cpp",
    "c": "tree_sitter_cpp",
    "csharp": "tree_sitter_c_sharp",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
}


def _language_symbol_candidates(language: str) -> list[str]:
    """Ordered attribute names to try when building a Language object.

    ``tree_sitter_typescript`` exports ``language_typescript`` and
    ``language_tsx`` rather than ``language``.
    """
    return ["language", f"language_{language}", "language_typescript", "language_tsx"]


def _load_language_object(language: str) -> Any | None:
    """Return a cached tree-sitter ``Language`` or None when unavailable."""
    with _LANGUAGE_CACHE_LOCK:
        if language in _LANGUAGE_CACHE:
            return _LANGUAGE_CACHE[language]
        module_name = _LANGUAGE_MODULES.get(language)
        lang = None
        if module_name is not None:
            try:
                from tree_sitter import Language

                module = __import__(module_name, fromlist=["language"])
                symbol = next(
                    (c for c in _language_symbol_candidates(language) if hasattr(module, c)),
                    None,
                )
                if symbol is None:
                    logger.info(
                        "Tree-sitter module %s has no language symbol (tried %s)",
                        module_name,
                        _language_symbol_candidates(language),
                    )
                else:
                    lang = Language(getattr(module, symbol)())
            except Exception as exc:  # pragma: no cover - import failures vary by env
                logger.info("Tree-sitter unavailable for %s: %s", language, exc)
        _LANGUAGE_CACHE[language] = lang
        return lang


class TreeSitterASTExtractor:
    """Extract structural features from code using tree-sitter.

    Supports Python, Java, C, C++, C#, JavaScript, TypeScript, Go and Rust.
    Falls back to lexical features for unsupported languages.
    """

    _NODE_TYPES: ClassVar[dict[str, list[str] | None]] = {
        "python": [
            "function_definition",
            "class_definition",
            "if_statement",
            "for_statement",
            "while_statement",
            "call",
        ],
        "java": [
            "method_declaration",
            "class_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "method_invocation",
        ],
        "cpp": [
            "function_definition",
            "class_specifier",
            "if_statement",
            "for_statement",
            "while_statement",
            "call_expression",
        ],
        "c": [
            "function_definition",
            "struct_specifier",
            "if_statement",
            "for_statement",
            "while_statement",
            "call_expression",
        ],
        "csharp": [
            "method_declaration",
            "class_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "invocation_expression",
        ],
        "javascript": [
            "function_declaration",
            "class_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "call_expression",
        ],
        "typescript": [
            "function_declaration",
            "class_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "call_expression",
        ],
        "go": [
            "func_declaration",
            "type_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "call_expression",
        ],
        "rust": [
            "function_item",
            "struct_item",
            "if_expression",
            "for_expression",
            "while_expression",
            "call_expression",
        ],
    }

    #: Node types that are comments. (Rust's ``attribute_item`` is ``#[derive(..)]``,
    #: not a comment, and used to be listed here.)
    _COMMENT_NODE_TYPES = frozenset(
        {"comment", "line_comment", "block_comment", "comment_block", "doc_comment"}
    )
    _IDENTIFIER_NODE_TYPES = frozenset({"identifier", "property_identifier", "object", "field"})
    _HASH_COMMENT_LANGUAGES = frozenset({"python", "perl", "ruby"})

    def __init__(self) -> None:
        self._parsers: dict[str, Any] = {}
        self._lock = threading.Lock()

    # Kept for backward compatibility with callers/tests.
    def _language_module_name(self, language: str) -> str | None:
        """Return the tree-sitter language package name for a language."""
        return _LANGUAGE_MODULES.get(language)

    def _language_symbol_candidates(self, language: str) -> list[str]:
        """Ordered attribute names to try when building a Language object."""
        return _language_symbol_candidates(language)

    def _load_language(self, language: str) -> Any | None:
        """Return ``(Language, Parser)`` for a language or None on failure."""
        language = normalize_language(language)
        if language in self._parsers:
            return self._parsers[language]
        lang = _load_language_object(language)
        if lang is None:
            self._parsers[language] = None
            return None
        try:
            from tree_sitter import Parser

            self._parsers[language] = (lang, Parser(lang))
        except Exception as exc:  # pragma: no cover
            logger.info("Tree-sitter parser unavailable for %s: %s", language, exc)
            self._parsers[language] = None
        return self._parsers[language]

    def extract(self, code: str, language: str = "python") -> ASTFeatureVector:
        """Extract an :class:`ASTFeatureVector` for the given code."""
        language = normalize_language(language)
        loaded = self._load_language(language)
        if loaded is None:
            return self._lexical_fallback(code, language)

        _lang, parser = loaded
        source = code.encode("utf-8")
        try:
            with self._lock:  # a tree-sitter Parser must not be used concurrently
                tree = parser.parse(source)
        except Exception as exc:  # pragma: no cover - parse errors depend on input
            logger.info("Tree-sitter parse failed for %s: %s", language, exc)
            return self._lexical_fallback(code, language)

        node_types = self._NODE_TYPES[language]
        func_type, class_type = node_types[0], node_types[1]
        # if / for / while. The old slice stopped at ``for``, so ``while`` loops
        # never counted towards cyclomatic complexity.
        branch_types = frozenset(node_types[2:5])
        source_lines = source.splitlines()

        node_counts: Counter = Counter()
        identifiers: list[str] = []
        func_lengths: list[float] = []
        class_lengths: list[float] = []
        comment_rows: set[int] = set()
        branches = 0

        # ONE traversal. The tree used to be walked five separate times
        # (node counts, identifiers, function/class counts, branches, lengths).
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            kind = node.type
            node_counts[kind] += 1
            stack.extend(node.children)

            if kind in self._IDENTIFIER_NODE_TYPES:
                text = (node.text or b"").decode("utf-8", errors="replace").strip()
                if text and _IDENTIFIER_RE.match(text):
                    identifiers.append(text)
            elif kind == func_type:
                func_lengths.append(max(1, node.end_point[0] - node.start_point[0] + 1))
            elif kind == class_type:
                class_lengths.append(max(1, node.end_point[0] - node.start_point[0] + 1))
            elif kind in self._COMMENT_NODE_TYPES:
                start_row, start_col = node.start_point
                prefix = source_lines[start_row][:start_col] if start_row < len(source_lines) else b""
                if not prefix.strip():  # whole-line comment, not a trailing one
                    comment_rows.update(range(start_row, node.end_point[0] + 1))
            if kind in branch_types:
                branches += 1

        identifier_stats = self._identifier_stats(identifiers)
        blank_line_ratio, indentation_consistency, whitespace_entropy = (
            self._whitespace_features(code)
        )
        non_blank = sum(1 for line in code.splitlines() if line.strip())
        cyclomatic = 1 + branches

        return ASTFeatureVector(
            node_type_entropy=_safe_entropy(node_counts),
            cyclomatic_complexity=min(1.0, cyclomatic / 50.0),
            avg_identifier_length=identifier_stats["avg_length"],
            identifier_length_std=identifier_stats["length_std"],
            identifier_naming_entropy=identifier_stats["naming_entropy"],
            comment_to_code_ratio=round(len(comment_rows) / max(1, non_blank), 4),
            blank_line_ratio=blank_line_ratio,
            avg_function_length=_mean(func_lengths),
            avg_class_length=_mean(class_lengths),
            indentation_consistency=indentation_consistency,
            whitespace_entropy=whitespace_entropy,
            function_count=len(func_lengths),
            class_count=len(class_lengths),
            parse_success=not tree.root_node.has_error,
            extra={"cyclomatic": cyclomatic},
        )

    def _walk(self, node: Any):
        """Yield all nodes under the given tree-sitter node depth-first."""
        stack = [node]
        while stack:
            current = stack.pop()
            if current is None:
                continue
            yield current
            stack.extend(current.children)

    def _identifier_stats(self, identifiers: list[str]) -> dict[str, float]:
        """Compute average length, std dev, and naming-style entropy."""
        if not identifiers:
            return {"avg_length": 0.0, "length_std": 0.0, "naming_entropy": 0.0}

        lengths = [float(len(ident)) for ident in identifiers]
        avg_length = sum(lengths) / len(lengths)
        variance = sum((length - avg_length) ** 2 for length in lengths) / len(lengths)
        length_std = math.sqrt(variance)

        # Naming-style entropy: how concentrated identifiers are on one naming style
        style_counter: Counter = Counter()
        for ident in identifiers:
            if re.match(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$", ident):
                style_counter["snake"] += 1
            elif re.match(r"^[a-z][a-zA-Z0-9]*$", ident):
                style_counter["camel"] += 1
            elif re.match(r"^[A-Z][a-zA-Z0-9]*$", ident):
                style_counter["pascal"] += 1
            elif re.match(r"^[a-z]$", ident):
                style_counter["single_char"] += 1
            else:
                style_counter["other"] += 1

        # Scaled so 1.0 = one dominant style (AI-like), 0.0 = perfectly mixed
        naming_entropy = 1.0 - _safe_entropy(style_counter)

        return {
            "avg_length": min(1.0, avg_length / 12.0),
            "length_std": min(1.0, length_std / 5.0),
            "naming_entropy": naming_entropy,
        }

    def _count_comments(self, code: str, language: str) -> float:
        """Whole-line comment-to-code line ratio, for the lexical fallback."""
        lines = code.splitlines()
        if not lines:
            return 0.0
        if language in self._HASH_COMMENT_LANGUAGES:
            line_comment = re.compile(r"^\s*#")
        else:
            # ``*`` only counts as a block-comment continuation when followed by
            # whitespace; ``*args`` / ``*ptr = 1`` are code.
            line_comment = re.compile(r"^\s*(//|/\*|\*/|\*(\s|$))")
        comment_count = sum(1 for line in lines if line_comment.match(line))
        non_blank = sum(1 for line in lines if line.strip())
        return round(comment_count / max(1, non_blank), 4)

    def _whitespace_features(self, code: str) -> tuple[float, float, float]:
        """Compute blank-line ratio, indentation consistency, and whitespace entropy."""
        lines = code.splitlines()
        if not lines:
            return 0.0, 0.0, 0.0

        total = len(lines)
        blank = sum(1 for line in lines if not line.strip())
        blank_ratio = round(blank / total, 4)

        non_blank = [line for line in lines if line.strip()]
        consistent = 0
        lead_lengths: Counter = Counter()
        for line in non_blank:
            lead = line[: len(line) - len(line.lstrip(" \t"))]
            lead_lengths[len(lead)] += 1
            # Consistent: no indentation, only tabs, or spaces in multiples of 4.
            # The test was ``len(line) - len(line.lstrip()) % 4 == 0``; ``%``
            # binds tighter than ``-`` so it compared the line LENGTH to a
            # remainder and was almost never true, leaving this feature at ~0.
            if not lead or set(lead) == {"\t"} or (set(lead) == {" "} and len(lead) % 4 == 0):
                consistent += 1
        indentation_consistency = round(consistent / max(1, len(non_blank)), 4)
        return blank_ratio, indentation_consistency, _safe_entropy(lead_lengths)

    def _lexical_fallback(self, code: str, language: str = "python") -> ASTFeatureVector:
        """Produce a best-effort vector when tree-sitter is unavailable.

        Uses pure lexical analysis so the pipeline still works for languages
        without a tree-sitter binding or when the library is missing.
        ``parse_success`` is False: ``node_type_entropy`` and the complexity are
        placeholders here and consumers must not read them as measurements.
        """
        lines = code.splitlines()
        if not lines:
            return ASTFeatureVector(parse_success=False)

        # Keywords are not identifiers; counting them skewed length and naming stats.
        identifiers = [
            word
            for word in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code)
            if not keyword.iskeyword(word)
        ]
        identifier_stats = self._identifier_stats(identifiers)
        blank_ratio, indentation_consistency, whitespace_entropy = (
            self._whitespace_features(code)
        )

        function_count = len(
            re.findall(
                r"\b(def|function|func|public\s+static\s+\w+\s+\w+|static\s+\w+\s+\w+)\s+\w+",
                code,
            )
        )
        return ASTFeatureVector(
            node_type_entropy=0.5,
            cyclomatic_complexity=0.0,
            avg_identifier_length=identifier_stats["avg_length"],
            identifier_length_std=identifier_stats["length_std"],
            identifier_naming_entropy=identifier_stats["naming_entropy"],
            comment_to_code_ratio=self._count_comments(code, language),
            blank_line_ratio=blank_ratio,
            avg_function_length=0.0,
            avg_class_length=0.0,
            indentation_consistency=indentation_consistency,
            whitespace_entropy=whitespace_entropy,
            function_count=function_count,
            class_count=0,
            parse_success=False,
        )


def get_ast_features(code: str, language: str = "python") -> ASTFeatureVector:
    """Module-level convenience wrapper around :class:`TreeSitterASTExtractor`."""
    return TreeSitterASTExtractor().extract(code, language)
