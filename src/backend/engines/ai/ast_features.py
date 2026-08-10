"""Tree-sitter AST feature extraction for AI-generated code detection.

Extracts a fixed-length numeric feature vector from source code using
tree-sitter for each supported language (Python, Java, C/C++, C#, JavaScript,
TypeScript, Go, Rust). Designed to feed the AI ensemble scorer and the machine
learning classifier.

Degrades gracefully: if tree-sitter (or the language binding) is unavailable,
the extractor falls back to lexical features so the pipeline never crashes.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ASTFeatureVector:
    """Fixed-length feature vector describing the structural style of code.

    All values are normalised to [0, 1] where meaningful so the vector can be
    passed directly to machine learning classifiers. ``node_type_entropy`` is
    the exception (bits) — it is capped and scaled in ``to_vector``.
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
    parse_success: bool = True
    extra: Dict[str, float] = field(default_factory=dict)

    FEATURE_MEANINGFUL = (
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

    def to_vector(self) -> List[float]:
        """Return a fixed-length numeric vector for ML consumption."""
        values = [
            min(1.0, self.node_type_entropy / 9.0),
            min(1.0, self.cyclomatic_complexity),
            self.avg_identifier_length,
            min(1.0, self.identifier_length_std / 5.0),
            self.identifier_naming_entropy,
            self.comment_to_code_ratio,
            self.blank_line_ratio,
            min(1.0, self.avg_function_length / 100.0),
            min(1.0, self.avg_class_length / 200.0),
            self.indentation_consistency,
            self.whitespace_entropy,
        ]
        return [round(float(v), 6) for v in values]

    def feature_names(self) -> List[str]:
        """Ordered feature names matching ``to_vector``."""
        return [
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
        ]

    def as_dict(self) -> Dict[str, Any]:
        """Serialisable representation including derived stats."""
        return {
            "node_type_entropy": round(self.node_type_entropy, 4),
            "cyclomatic_complexity": round(self.cyclomatic_complexity, 4),
            "avg_identifier_length": round(self.avg_identifier_length, 4),
            "identifier_length_std": round(self.identifier_length_std, 4),
            "identifier_naming_entropy": round(self.identifier_naming_entropy, 4),
            "comment_to_code_ratio": round(self.comment_to_code_ratio, 4),
            "blank_line_ratio": round(self.blank_line_ratio, 4),
            "avg_function_length": round(self.avg_function_length, 4),
            "avg_class_length": round(self.avg_class_length, 4),
            "indentation_consistency": round(self.indentation_consistency, 4),
            "whitespace_entropy": round(self.whitespace_entropy, 4),
            "function_count": self.function_count,
            "class_count": self.class_count,
            "parse_success": self.parse_success,
            "extra": self.extra,
        }


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


def _uniq_preserving(items: List[str]) -> List[str]:
    """Deduplicate items preserving order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class TreeSitterASTExtractor:
    """Extract structural features from code using tree-sitter.

    Supports Python, Java, C, C++, C#, JavaScript, TypeScript, Go and Rust.
    Falls back to lexical features for unsupported languages.
    """

    _NODE_TYPES: Dict[str, Optional[List[str]]] = {
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

    _COMMENT_NODE_TYPES = (
        "comment",
        "line_comment",
        "block_comment",
        "comment_block",
        "doc_comment",
        "attribute_item",
    )

    def __init__(self) -> None:
        self._loaded: Dict[str, Any] = {}
        self._attempted: set = set()

    def _language_module_name(self, language: str) -> Optional[str]:
        """Return the tree-sitter language package name for a language."""
        mapping = {
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
        return mapping.get(language)

    def _load_language(self, language: str) -> Optional[Any]:
        """Lazily load a tree-sitter Language object or None on failure."""
        if language in self._loaded:
            return self._loaded[language]
        if language in self._attempted:
            return None

        self._attempted.add(language)
        module_name = self._language_module_name(language)
        if module_name is None:
            self._loaded[language] = None
            return None

        try:
            from tree_sitter import Language, Parser

            module = __import__(module_name, fromlist=["language"])
            lang = Language(module.language())
            parser = Parser(lang)
            self._loaded[language] = (lang, parser)
            return self._loaded[language]
        except Exception as exc:  # pragma: no cover - import failures vary by env
            logger.info("Tree-sitter unavailable for %s: %s", language, exc)
            self._loaded[language] = None
            return None

    def extract(self, code: str, language: str = "python") -> ASTFeatureVector:
        """Extract an :class:`ASTFeatureVector` for the given code."""
        loaded = self._load_language(language)
        if loaded is None:
            return self._lexical_fallback(code)

        _lang, parser = loaded
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - parse errors depend on input
            logger.info("Tree-sitter parse failed for %s: %s", language, exc)
            return self._lexical_fallback(code)

        node_counts: Counter = Counter()
        for node in self._walk(tree.root_node):
            node_counts[node.type] += 1

        # Node-type distribution entropy (lower = more uniform = more AI-like)
        node_type_entropy = _safe_entropy(node_counts)

        # Identifier-related features
        identifiers = self._collect_identifiers(tree.root_node, language)
        identifier_stats = self._identifier_stats(identifiers)

        # Functions / classes
        func_ids = self._count_node_types(
            tree.root_node, self._NODE_TYPES.get(language, ())[:2]
        )
        function_count, class_count = func_ids

        # Whitespace / structural features from raw source
        blank_line_ratio, indentation_consistency, whitespace_entropy = (
            self._whitespace_features(code)
        )

        # Comment ratio
        comment_lines = self._count_comments(code, language)

        # Cyclomatic complexity (approximate using branch nodes)
        branch_types = set(self._NODE_TYPES.get(language, ())[2:4])
        cyclomatic = 1 + sum(
            1 for node in self._walk(tree.root_node) if node.type in branch_types
        )

        vector = ASTFeatureVector(
            node_type_entropy=node_type_entropy,
            cyclomatic_complexity=min(1.0, cyclomatic / 50.0),
            avg_identifier_length=identifier_stats["avg_length"],
            identifier_length_std=identifier_stats["length_std"],
            identifier_naming_entropy=identifier_stats["naming_entropy"],
            comment_to_code_ratio=comment_lines,
            blank_line_ratio=blank_line_ratio,
            avg_function_length=0.0,  # filled below
            avg_class_length=0.0,
            indentation_consistency=indentation_consistency,
            whitespace_entropy=whitespace_entropy,
            function_count=function_count,
            class_count=class_count,
            parse_success=True,
        )

        # Average function / class length computed from node byte spans
        func_node_types = self._NODE_TYPES.get(language, ())[:2]
        class_node_types = self._NODE_TYPES.get(language, ())[1:2]
        func_lengths, class_lengths = self._structure_lengths(
            tree.root_node, func_node_types, class_node_types
        )
        vector.avg_function_length = _mean(func_lengths)
        vector.avg_class_length = _mean(class_lengths)
        vector.extra = {"cyclomatic": cyclomatic}
        return vector

    def _walk(self, node: Any):
        """Yield all nodes under the given tree-sitter node depth-first."""
        stack = [node]
        while stack:
            current = stack.pop()
            if current is None:
                continue
            yield current
            for child in current.children:
                stack.append(child)

    def _count_node_types(self, node: Any, types: Tuple[str, ...]) -> Tuple[int, int]:
        """Count function and class node occurrences."""
        function_count = 0
        class_count = 0
        for current in self._walk(node):
            if current.type == types[0] if types else False:
                function_count += 1
            if len(types) > 1 and current.type == types[1]:
                class_count += 1
        return function_count, class_count

    def _structure_lengths(
        self,
        node: Any,
        func_types: Tuple[str, ...],
        class_types: Tuple[str, ...],
    ) -> Tuple[List[float], List[float]]:
        """Approximate average function and class length (lines)."""
        func_lengths: List[float] = []
        class_lengths: List[float] = []
        func_type = func_types[0] if func_types else ""
        class_type = class_types[0] if class_types else ""
        for current in self._walk(node):
            if current.type == func_type:
                start = current.start_point[0]
                end = current.end_point[0]
                func_lengths.append(max(1, end - start + 1))
            if class_type and current.type == class_type:
                start = current.start_point[0]
                end = current.end_point[0]
                class_lengths.append(max(1, end - start + 1))
        return func_lengths, class_lengths

    def _collect_identifiers(self, node: Any, language: str) -> List[str]:
        """Collect identifier text from identifier nodes in the AST."""
        identifiers: List[str] = []
        for current in self._walk(node):
            if current.type in ("identifier", "property_identifier", "object", "field"):
                text = current.text.decode("utf-8", errors="replace").strip()
                if text and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
                    identifiers.append(text)
        return identifiers

    def _identifier_stats(self, identifiers: List[str]) -> Dict[str, float]:
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
        distribution_entropy = _safe_entropy(style_counter)
        naming_entropy = 1.0 - distribution_entropy

        return {
            "avg_length": min(1.0, avg_length / 12.0),
            "length_std": min(1.0, length_std / 5.0),
            "naming_entropy": naming_entropy,
        }

    def _count_comments(self, code: str, language: str) -> float:
        """Return comment-to-code line ratio."""
        lines = code.splitlines()
        if not lines:
            return 0.0
        line_comment = re.compile(
            r"^\s*(#|//|/\*.*\*/|(\*.*))"
            if language in ("python", "perl", "ruby")
            else r"^\s*(//|/\*.*\*/|(\*.*))"
        )
        comment_count = sum(1 for line in lines if line_comment.match(line))
        non_blank = [line for line in lines if line.strip()]
        return round(comment_count / max(1, len(non_blank)), 4)

    def _whitespace_features(self, code: str) -> Tuple[float, float, float]:
        """Compute blank-line ratio, indentation consistency, and whitespace entropy."""
        lines = code.splitlines()
        if not lines:
            return 0.0, 0.0, 0.0

        total = len(lines)
        blank = sum(1 for line in lines if not line.strip())
        blank_ratio = round(blank / total, 4)

        # Indentation consistency: fraction of non-blank lines with 4-space multiples
        non_blank = [line for line in lines if line.strip()]
        consistent = sum(
            1 for line in non_blank if len(line) - len(line.lstrip(" \t")) % 4 == 0
        )
        indentation_consistency = round(consistent / max(1, len(non_blank)), 4)

        # Whitespace entropy: variability of leading-whitespace run lengths
        lead_lengths: Counter = Counter()
        for line in non_blank:
            lead = len(line) - len(line.lstrip(" \t"))
            lead_lengths[lead] += 1
        whitespace_entropy = _safe_entropy(lead_lengths)
        return blank_ratio, indentation_consistency, whitespace_entropy

    def _lexical_fallback(self, code: str) -> ASTFeatureVector:
        """Produce a best-effort vector when tree-sitter is unavailable.

        Uses pure lexical analysis so the pipeline still works for languages
        without a tree-sitter binding or when the library is missing.
        """
        lines = code.splitlines()
        if not lines:
            return ASTFeatureVector(parse_success=False)

        identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code)
        identifier_stats = self._identifier_stats(identifiers)
        blank_ratio, indentation_consistency, whitespace_entropy = (
            self._whitespace_features(code)
        )

        # Approximate function count by heuristic patterns
        function_count = len(
            re.findall(
                r"\b(def|function|func|public\s+static\s+\w+\s+\w+|static\s+\w+\s+\w+)\s+\w+",
                code,
            )
        )
        comment_lines = self._count_comments(code, "python")

        return ASTFeatureVector(
            node_type_entropy=0.5,
            cyclomatic_complexity=0.0,
            avg_identifier_length=identifier_stats["avg_length"],
            identifier_length_std=identifier_stats["length_std"],
            identifier_naming_entropy=identifier_stats["naming_entropy"],
            comment_to_code_ratio=comment_lines,
            blank_line_ratio=blank_ratio,
            avg_function_length=0.0,
            avg_class_length=0.0,
            indentation_consistency=indentation_consistency,
            whitespace_entropy=whitespace_entropy,
            function_count=function_count,
            class_count=0,
            parse_success=False,
        )


def _mean(values: List[float]) -> float:
    """Mean of a list, 0.0 for empty input."""
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def get_ast_features(code: str, language: str = "python") -> ASTFeatureVector:
    """Module-level convenience wrapper around :class:`TreeSitterASTExtractor`."""
    return TreeSitterASTExtractor().extract(code, language)
