"""
Code Stylometry Feature Extractor + AI Detection Module.

Stylometry: analyzing coding style to identify authorship and detect AI-generated code.

Features extracted:
1. Lexical features: variable naming habits (camelCase vs snake_case), identifier length
2. Syntactic features: statements per function, nesting depth, loop/branch patterns
3. Structural features: function/class organization, import ordering
4. Semantic features: error handling style, comprehensions, f-strings, type hints

Performance notes
-----------------
* The AST is traversed exactly once. Every counter (statements, loops, branches,
  calls, nesting depth, docstrings, type hints, ...) is gathered in that pass,
  using type-keyed set lookups instead of chains of ``isinstance`` calls.
* Identifiers are counted once with ``Counter`` and all per-identifier work runs
  over *unique* identifiers weighted by frequency, not over every occurrence.
* The extractor is stateless (all tallies are local to one ``extract`` call),
  so one instance can be shared across threads.
* ``detect_batch`` fans work out across processes for large file sets.

Requires Python 3.10+.
"""

from __future__ import annotations

import ast
import itertools
import keyword
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# Module-level constants (built once, not per node / per call)
# --------------------------------------------------------------------------- #

_KEYWORDS = frozenset(keyword.kwlist)
_IDENT_RE = re.compile(r"\b[A-Za-z_]\w*")
_COMMENT_RE = re.compile(r"#[^\n]*")


def _ast_types(*names: str) -> frozenset[type]:
    """Collect AST classes by name, skipping any this Python version lacks."""
    return frozenset(getattr(ast, n) for n in names if hasattr(ast, n))


_STMT_TYPES = frozenset(ast.stmt.__subclasses__())
_FUNC_TYPES = _ast_types("FunctionDef", "AsyncFunctionDef")
_LOOP_TYPES = _ast_types("For", "AsyncFor", "While")
_FOR_TYPES = _ast_types("For", "AsyncFor")
_COMP_TYPES = _ast_types("ListComp", "SetComp", "DictComp", "GeneratorExp")
_IMPORT_TYPES = _ast_types("Import", "ImportFrom")
#: Node types that add one level of nesting.
_NESTING_TYPES = _ast_types(
    "If", "For", "AsyncFor", "While", "With", "AsyncWith", "Try", "TryStar", "Match"
)


def _docstring_length(body: list[ast.stmt]) -> int:
    """Length of the docstring in ``body``, or -1 if there is none."""
    if body and type(body[0]) is ast.Expr:
        value = body[0].value
        if type(value) is ast.Constant and isinstance(value.value, str):
            return len(value.value)
    return -1


def _has_type_hints(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the function annotates its return value or any parameter."""
    if fn.returns is not None:
        return True
    a = fn.args
    params = itertools.chain(a.posonlyargs, a.args, a.kwonlyargs, (a.vararg, a.kwarg))
    return any(p is not None and p.annotation is not None for p in params)


# --------------------------------------------------------------------------- #
# Feature vector
# --------------------------------------------------------------------------- #

#: Single source of truth for vector order; ``to_vector`` and ``feature_names``
#: both derive from it so they cannot drift apart.
_VECTOR_FIELDS: tuple[str, ...] = (
    "avg_identifier_length",
    "identifier_length_std",
    "camel_case_ratio",
    "snake_case_ratio",
    "single_char_var_ratio",
    "descriptive_var_ratio",
    "var_naming_entropy",
    "avg_statements_per_func",
    "avg_nesting_depth",
    "max_nesting_depth",
    "loop_ratio",
    "branch_ratio",
    "func_call_ratio",
    "num_functions",
    "num_classes",
    "num_imports",
    "avg_func_length",
    "import_order_score",
    "comment_density",
    "docstring_ratio",
    "inline_comment_count",
    "cyclomatic_complexity",
    "unique_keywords",
    "keyword_diversity",
    "has_try_except",
    "exception_handling_ratio",
    "list_comprehension_ratio",
    "f_string_ratio",
    "type_hint_ratio",
)


@dataclass
class StylometryFeatures:
    """
    Complete stylometry feature vector for a code snippet.

    Can be used for:
    - Authorship attribution (who wrote this code?)
    - AI detection (human vs AI-generated?)
    - Style clustering (group similar styles)
    """

    doc_id: str = ""
    #: False when the source could not be parsed; all features are then zero.
    parse_ok: bool = True

    # === Lexical features ===
    avg_identifier_length: float = 0.0
    identifier_length_std: float = 0.0
    camel_case_ratio: float = 0.0  # among camelCase + snake_case identifiers
    snake_case_ratio: float = 0.0
    single_char_var_ratio: float = 0.0
    descriptive_var_ratio: float = 0.0  # identifiers >= 4 chars

    # === Naming habits ===
    most_common_prefix: str = ""
    most_common_suffix: str = ""
    var_naming_entropy: float = 0.0  # Shannon entropy of identifier chars

    # === Syntactic features ===
    avg_statements_per_func: float = 0.0
    avg_nesting_depth: float = 0.0
    max_nesting_depth: int = 0
    loop_ratio: float = 0.0  # loop statements / total statements
    branch_ratio: float = 0.0  # if statements / total statements
    func_call_ratio: float = 0.0  # function calls / total statements

    # === Structural features ===
    num_functions: int = 0
    num_classes: int = 0
    num_imports: int = 0
    avg_func_length: float = 0.0
    import_order_score: float = 0.0  # 0 = random, 1 = sorted

    # === Comment features ===
    comment_density: float = 0.0  # comment + docstring chars / total chars
    docstring_ratio: float = 0.0  # functions with docstrings / total
    inline_comment_count: int = 0

    # === Complexity features ===
    cyclomatic_complexity: float = 0.0
    unique_keywords: int = 0
    keyword_diversity: float = 0.0  # unique keywords / total keywords

    # === Pattern features ===
    has_try_except: bool = False
    exception_handling_ratio: float = 0.0
    list_comprehension_ratio: float = 0.0  # comprehensions / for loops
    f_string_ratio: float = 0.0  # f-strings / (f-strings + .format + % formatting)
    type_hint_ratio: float = 0.0  # functions with type hints / total

    def to_vector(self) -> list[float]:
        """Convert to numeric feature vector for ML."""
        return [float(getattr(self, name)) for name in _VECTOR_FIELDS]

    @staticmethod
    def feature_names() -> list[str]:
        """Names corresponding to to_vector() indices."""
        return list(_VECTOR_FIELDS)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


@dataclass
class _Tally:
    """Raw counts from a single AST pass. Local to one ``extract`` call."""

    statements: int = 0
    loops: int = 0
    for_loops: int = 0
    branches: int = 0
    calls: int = 0
    handlers: int = 0
    comprehensions: int = 0
    classes: int = 0
    imports: int = 0
    complexity: int = 1  # base path
    f_strings: int = 0
    other_formatting: int = 0  # .format() calls and "..." % x
    docstring_chars: int = 0
    funcs_with_docstring: int = 0
    funcs_with_type_hints: int = 0
    func_lengths: list[int] = field(default_factory=list)
    func_nesting: list[int] = field(default_factory=list)
    func_statements: list[int] = field(default_factory=list)


def _walk(tree: ast.Module) -> _Tally:
    """Single iterative traversal gathering every AST-derived count.

    Nesting depth and statement counts are attributed to the innermost
    enclosing function. Counters live in locals for speed and are copied to the
    tally at the end.
    """
    tally = _Tally()
    func_nesting = tally.func_nesting
    func_statements = tally.func_statements
    func_lengths = tally.func_lengths

    statements = loops = for_loops = branches = calls = handlers = 0
    comprehensions = classes = imports = complexity = 0
    f_strings = other_formatting = 0
    docstring_chars = funcs_with_docstring = funcs_with_type_hints = 0
    nested_format_specs: set[int] = set()

    doc_len = _docstring_length(tree.body)
    if doc_len >= 0:
        docstring_chars += doc_len

    # Stack entries: (node, nesting depth within current function, function index)
    stack: list[tuple[ast.AST, int, int]] = [(tree, 0, -1)]
    pop = stack.pop
    push = stack.append
    children = ast.iter_child_nodes

    while stack:
        node, depth, fidx = pop()
        nt = type(node)

        if nt in _STMT_TYPES:
            statements += 1
            if fidx >= 0:
                func_statements[fidx] += 1

        if nt in _FUNC_TYPES:
            body = node.body
            func_lengths.append(len(body))
            doc_len = _docstring_length(body)
            if doc_len >= 0:
                funcs_with_docstring += 1
                docstring_chars += doc_len
            if _has_type_hints(node):
                funcs_with_type_hints += 1
            fidx = len(func_nesting)
            func_nesting.append(0)
            func_statements.append(0)
            depth = 0
        else:
            if nt in _NESTING_TYPES:
                depth += 1
                if fidx >= 0 and depth > func_nesting[fidx]:
                    func_nesting[fidx] = depth

            if nt is ast.If:
                branches += 1
                complexity += 1
            elif nt in _LOOP_TYPES:
                loops += 1
                complexity += 1
                if nt in _FOR_TYPES:
                    for_loops += 1
            elif nt is ast.Call:
                calls += 1
                func = node.func
                if type(func) is ast.Attribute and func.attr == "format":
                    other_formatting += 1
            elif nt is ast.ExceptHandler:
                handlers += 1
                complexity += 1
            elif nt in _COMP_TYPES:
                comprehensions += 1
            elif nt is ast.FormattedValue:
                # ``f"{x:>{w}}"`` nests a second JoinedStr inside the format spec.
                # Remember it so it is not counted as an extra f-string. (A parent
                # is always popped before its children, so the id is known in time.)
                spec = node.format_spec
                if spec is not None:
                    nested_format_specs.add(id(spec))
            elif nt is ast.JoinedStr:
                if id(node) not in nested_format_specs:
                    f_strings += 1
            elif nt is ast.BoolOp:
                complexity += len(node.values) - 1
            elif nt is ast.IfExp:
                complexity += 1
            elif nt is ast.comprehension:
                complexity += len(node.ifs)
            elif nt is ast.BinOp:
                left = node.left
                if (
                    type(node.op) is ast.Mod
                    and type(left) is ast.Constant
                    and isinstance(left.value, str)
                ):
                    other_formatting += 1
            elif nt is ast.ClassDef:
                classes += 1
                doc_len = _docstring_length(node.body)
                if doc_len >= 0:
                    docstring_chars += doc_len
            elif nt in _IMPORT_TYPES:
                imports += 1

        for child in children(node):
            push((child, depth, fidx))

    tally.statements = statements
    tally.loops = loops
    tally.for_loops = for_loops
    tally.branches = branches
    tally.calls = calls
    tally.handlers = handlers
    tally.comprehensions = comprehensions
    tally.classes = classes
    tally.imports = imports
    tally.complexity += complexity
    tally.f_strings = f_strings
    tally.other_formatting = other_formatting
    tally.docstring_chars = docstring_chars
    tally.funcs_with_docstring = funcs_with_docstring
    tally.funcs_with_type_hints = funcs_with_type_hints
    return tally


def _import_order_score(tree: ast.Module) -> float:
    """Fraction of adjacent top-level imports that are in alphabetical order."""
    names: list[str] = []
    for stmt in tree.body:
        if type(stmt) is ast.Import:
            names.append(stmt.names[0].name.lower())
        elif type(stmt) is ast.ImportFrom:
            names.append(("." * stmt.level + (stmt.module or "")).lower())
    if len(names) < 2:
        return 1.0
    in_order = sum(1 for a, b in zip(names, names[1:]) if a <= b)
    return in_order / (len(names) - 1)


def _entropy(char_counter: Counter) -> float:
    """Shannon entropy (bits) of a character distribution."""
    total = sum(char_counter.values())
    if total == 0:
        return 0.0
    log2 = math.log2
    return -sum((c / total) * log2(c / total) for c in char_counter.values())


class StylometryExtractor:
    """
    Extracts stylometry features from Python code.

    Stateless and therefore safe to share across threads.

    Usage:
        extractor = StylometryExtractor()
        features = extractor.extract("def my_func(x): ...")
        vector = features.to_vector()
    """

    def extract(self, source: str, doc_id: str = "") -> StylometryFeatures:
        """Extract all stylometry features from Python source code."""
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, RecursionError):
            return StylometryFeatures(doc_id=doc_id, parse_ok=False)

        tally = _walk(tree)
        f = StylometryFeatures(doc_id=doc_id)

        self._fill_lexical(f, source)
        self._fill_syntactic(f, tally)
        self._fill_structural(f, tally, tree)
        self._fill_comments(f, tally, source)
        self._fill_patterns(f, tally)
        return f

    # -- lexical ---------------------------------------------------------- #

    @staticmethod
    def _fill_lexical(f: StylometryFeatures, source: str) -> None:
        """Identifier and keyword statistics, computed over unique tokens."""
        counts = Counter(_IDENT_RE.findall(source))

        total = sum_len = sum_sq = single = descriptive = camel = snake = 0
        keyword_total = keyword_unique = 0
        prefixes: Counter = Counter()
        suffixes: Counter = Counter()
        chars: Counter = Counter()

        for ident, n in counts.items():
            if ident in _KEYWORDS:
                keyword_total += n
                keyword_unique += 1
                continue

            length = len(ident)
            total += n
            sum_len += length * n
            sum_sq += length * length * n
            if length == 1:
                single += n
            elif length >= 4:
                descriptive += n
            if length >= 3:
                prefixes[ident[:3]] += n
                suffixes[ident[-3:]] += n

            if "_" in ident.strip("_"):
                if ident.islower():
                    snake += n
            elif ident[0].islower() and not ident.islower():
                camel += n

            for ch in ident.lower():
                chars[ch] += n

        f.unique_keywords = keyword_unique
        f.keyword_diversity = keyword_unique / max(1, keyword_total)

        if total:
            mean = sum_len / total
            f.avg_identifier_length = mean
            if total > 1:
                variance = (sum_sq - total * mean * mean) / (total - 1)
                f.identifier_length_std = math.sqrt(max(0.0, variance))
            f.single_char_var_ratio = single / total
            # Length-1 identifiers are never "descriptive" (>= 4 chars).
            f.descriptive_var_ratio = descriptive / total
        styled = camel + snake
        if styled:
            f.camel_case_ratio = camel / styled
            f.snake_case_ratio = snake / styled

        f.var_naming_entropy = round(_entropy(chars), 4)
        if prefixes:
            f.most_common_prefix = prefixes.most_common(1)[0][0]
            f.most_common_suffix = suffixes.most_common(1)[0][0]

    # -- AST-derived ------------------------------------------------------ #

    @staticmethod
    def _fill_syntactic(f: StylometryFeatures, t: _Tally) -> None:
        stmts = max(1, t.statements)
        f.avg_statements_per_func = (
            sum(t.func_statements) / len(t.func_statements) if t.func_statements else 0.0
        )
        if t.func_nesting:
            f.avg_nesting_depth = sum(t.func_nesting) / len(t.func_nesting)
            f.max_nesting_depth = max(t.func_nesting)
        f.loop_ratio = t.loops / stmts
        f.branch_ratio = t.branches / stmts
        f.func_call_ratio = t.calls / stmts
        f.cyclomatic_complexity = t.complexity
        f.exception_handling_ratio = t.handlers / stmts

    @staticmethod
    def _fill_structural(f: StylometryFeatures, t: _Tally, tree: ast.Module) -> None:
        f.num_functions = len(t.func_lengths)
        f.num_classes = t.classes
        f.num_imports = t.imports
        f.avg_func_length = (
            sum(t.func_lengths) / len(t.func_lengths) if t.func_lengths else 0.0
        )
        f.import_order_score = _import_order_score(tree)

    @staticmethod
    def _fill_comments(f: StylometryFeatures, t: _Tally, source: str) -> None:
        # Regex-based, so a '#' inside a string literal is counted as a comment.
        comments = _COMMENT_RE.findall(source)
        f.inline_comment_count = len(comments)
        if source:
            comment_chars = sum(map(len, comments)) + t.docstring_chars
            f.comment_density = round(comment_chars / len(source), 4)
        n_funcs = max(1, len(t.func_lengths))
        f.docstring_ratio = t.funcs_with_docstring / n_funcs
        f.type_hint_ratio = t.funcs_with_type_hints / n_funcs

    @staticmethod
    def _fill_patterns(f: StylometryFeatures, t: _Tally) -> None:
        f.has_try_except = t.handlers > 0
        f.list_comprehension_ratio = t.comprehensions / max(1, t.for_loops)
        formatted = t.f_strings + t.other_formatting
        f.f_string_ratio = t.f_strings / formatted if formatted else 0.0


# --------------------------------------------------------------------------- #
# AI detection
# --------------------------------------------------------------------------- #


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


#: Each scaler maps a raw feature value to [0, 1], where 1 = "most AI-like".
#: Direction is handled here (e.g. fewer single-char names => higher), so every
#: weight below is positive. The original mixed negative weights with already
#: inverted values, which cancelled out and rewarded the *human* pattern.
_AI_SCALERS: dict[str, Callable[[float], float]] = {
    "comment_density": lambda v: _clamp01(v / 0.1),  # AI tends toward 5-15%
    "descriptive_var_ratio": _clamp01,
    "type_hint_ratio": _clamp01,
    "var_naming_entropy": lambda v: _clamp01(v / 4.0),
    "docstring_ratio": _clamp01,
    "exception_handling_ratio": _clamp01,
    "list_comprehension_ratio": lambda v: _clamp01(v / 0.5),
    "single_char_var_ratio": lambda v: 1.0 - _clamp01(v),  # fewer short names
    "max_nesting_depth": lambda v: 1.0 - _clamp01(v / 4.0),  # shallower nesting
}

_DEFAULT_WEIGHTS: dict[str, float] = {
    "comment_density": 0.15,
    "descriptive_var_ratio": 0.15,
    "type_hint_ratio": 0.12,
    "var_naming_entropy": 0.10,
    "docstring_ratio": 0.10,
    "exception_handling_ratio": 0.10,
    "list_comprehension_ratio": 0.08,
    "single_char_var_ratio": 0.10,
    "max_nesting_depth": 0.10,
}


class AIDetector:
    """
    Heuristic detector for AI-generated vs human-written Python.

    Combines stylometry features into a weighted score in [0, 1]. This is a
    heuristic, not a trained classifier: treat scores as a triage signal and
    calibrate ``threshold`` on labelled examples from your own corpus before
    relying on it for any decision.

    Signals that push the score toward "AI": dense comments, descriptive names,
    type hints everywhere, docstrings everywhere, consistent error handling,
    comprehensions, few single-letter names, shallow nesting.
    """

    def __init__(
        self, threshold: float = 0.6, weights: dict[str, float] | None = None
    ) -> None:
        self.threshold = threshold
        self.weights = dict(weights or _DEFAULT_WEIGHTS)
        unknown = set(self.weights) - set(_AI_SCALERS)
        if unknown:
            raise ValueError(f"No scaler for feature(s): {sorted(unknown)}")
        self._total_weight = sum(self.weights.values())
        self.extractor = StylometryExtractor()

    def detect(self, source: str, doc_id: str = "") -> dict[str, Any]:
        """
        Detect if code is AI-generated.

        Returns:
            {"is_ai", "confidence", "ai_score", "threshold", "parsed", "features"}
        """
        features = self.extractor.extract(source, doc_id)
        if not features.parse_ok:
            return {
                "is_ai": False,
                "confidence": 0.0,
                "ai_score": 0.0,
                "threshold": self.threshold,
                "parsed": False,
                "features": {},
            }

        score = self._score_ai_likelihood(features)
        return {
            "is_ai": score >= self.threshold,
            "confidence": round(abs(score - 0.5) * 2, 4),  # 0-1, higher = surer
            "ai_score": round(score, 4),
            "threshold": self.threshold,
            "parsed": True,
            "features": self._feature_summary(features),
        }

    def _score_ai_likelihood(self, features: StylometryFeatures) -> float:
        """Weighted mean of scaled signals. 0 = human-like, 1 = AI-like."""
        if self._total_weight <= 0:
            return 0.0
        score = sum(
            w * _AI_SCALERS[name](getattr(features, name))
            for name, w in self.weights.items()
        )
        return score / self._total_weight

    @staticmethod
    def _feature_summary(features: StylometryFeatures) -> dict[str, Any]:
        """Create a summary of key features for reporting."""
        return {
            "comment_density": features.comment_density,
            "descriptive_var_ratio": features.descriptive_var_ratio,
            "type_hint_ratio": features.type_hint_ratio,
            "var_naming_entropy": features.var_naming_entropy,
            "docstring_ratio": features.docstring_ratio,
            "num_functions": features.num_functions,
            "avg_nesting_depth": features.avg_nesting_depth,
            "single_char_var_ratio": features.single_char_var_ratio,
        }


# --------------------------------------------------------------------------- #
# Convenience functions
# --------------------------------------------------------------------------- #

_DEFAULT_EXTRACTOR = StylometryExtractor()


def get_stylometry_features(source: str, doc_id: str = "") -> StylometryFeatures:
    """Extract stylometry features from code."""
    return _DEFAULT_EXTRACTOR.extract(source, doc_id)


def detect_ai_generated(source: str, threshold: float = 0.6) -> dict[str, Any]:
    """Detect if code is AI-generated."""
    return AIDetector(threshold).detect(source)


def _detect_worker(args: tuple[str, str, float]) -> dict[str, Any]:
    source, doc_id, threshold = args
    result = AIDetector(threshold).detect(source, doc_id)
    result["doc_id"] = doc_id
    return result


def detect_batch(
    sources: Sequence[str] | Iterable[str],
    threshold: float = 0.6,
    workers: int | None = None,
    min_parallel: int = 32,
) -> list[dict[str, Any]]:
    """
    Run detection over many sources, in parallel when the batch is large enough.

    Each result carries ``doc_id`` (the item's index as a string). Below
    ``min_parallel`` items, or with ``workers == 1``, it runs in-process because
    process start-up would cost more than it saves.
    """
    jobs = [(src, str(i), threshold) for i, src in enumerate(sources)]
    if workers == 1 or len(jobs) < min_parallel:
        return [_detect_worker(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        chunk = max(1, len(jobs) // ((workers or 4) * 4))
        return list(pool.map(_detect_worker, jobs, chunksize=chunk))
