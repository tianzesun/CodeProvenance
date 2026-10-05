"""Normalized AST subtree hashing for structure-aware plagiarism detection.

What was wrong (and why similarity scores were unreliable):
- Identifiers were renumbered by first appearance in the WHOLE FILE, so the hash of a subtree
  depended on every name seen before it. The same function copied into two files hashed
  differently unless the preceding code happened to introduce names in the same order. Each
  subtree is now canonicalised on its own (names numbered by first appearance WITHIN it).
- ``expr_context`` nodes (``Load()``) count as AST nodes, so every ``Name`` was a "subtree" of size
  2 and trivial leaves dominated the multiset: unrelated programs scored high. Context nodes are
  skipped and the minimum size is 4.
- Two files with no hashes (unparseable, empty, not Python, or all starter code) scored 1.0. No
  evidence is now 0.0, and :meth:`compare` says whether each side parsed.
- ``bool`` constants were rewritten to ``0`` (``bool`` is an ``int``), so ``x == True`` and
  ``x == 0`` hashed the same; ``ClassDef`` names, ``except ... as`` names and docstrings were not
  normalised.
- The traversal was recursive: a long expression (``a + b + c + ...`` with a thousand terms) raised
  ``RecursionError``; only ``SyntaxError`` was caught around parsing. Everything is iterative now.
- Starter code can be excluded exactly: ``exact_hashes(starter)`` gives hashes that keep names and
  literals, and ``hash_source(..., exclude_exact=...)`` drops those subtrees. The AST needs no
  text surgery on the submission (removing lines of a Python file breaks its syntax).
- Jaccard is diluted when one file contains the other, so ``compare`` also reports containment.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import warnings
from collections import Counter
from dataclasses import dataclass, field

MAX_SOURCE_CHARS = 1_000_000
MAX_NODES = 300_000
_BUILTIN_NAMES = frozenset(n for n in dir(builtins) if not n.startswith("_"))
_IGNORED_FIELDS = frozenset({"lineno", "col_offset", "end_lineno", "end_col_offset", "ctx", "type_comment", "kind"})
_FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class ASTSubtreeHashResult:
    """Subtree hash multiset and parse status."""

    hashes: list[str]
    parse_error: str = ""
    #: hashes that keep names and literals, parallel to ``hashes`` (for starter-code matching)
    exact_hashes: list[str] = field(default_factory=list)

    @property
    def parsed(self) -> bool:
        return not self.parse_error


@dataclass(frozen=True)
class ASTComparison:
    """Similarity of two sources with the facts needed to interpret it."""

    similarity: float  # multiset Jaccard
    containment: float  # shared / size of the SMALLER multiset (a copied function inside a big file)
    shared: int
    hashes_a: int
    hashes_b: int
    parsed_a: bool
    parsed_b: bool

    @property
    def comparable(self) -> bool:
        """Both sides parsed and produced subtrees: otherwise the numbers say nothing."""
        return self.parsed_a and self.parsed_b and self.hashes_a > 0 and self.hashes_b > 0


def _strip_docstring(node: ast.AST) -> None:
    body = getattr(node, "body", None)
    if (
        isinstance(body, list)
        and body
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], "value", None), ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
        if not body:
            body.append(ast.Pass())


def _identifier_fields(node: ast.AST) -> tuple[str, ...]:
    """Scalar fields of ``node`` that hold a name bound or used in the program."""
    if isinstance(node, ast.Name):
        return ("id",)
    if isinstance(node, ast.arg):
        return ("arg",)
    if isinstance(node, (*_FUNC_TYPES, ast.ClassDef)):
        return ("name",)
    if isinstance(node, ast.ExceptHandler):
        return ("name",)
    if isinstance(node, ast.alias):
        return ("asname",)
    return ()


def _scalar(value: object, exact: bool) -> object:
    """A literal value for hashing: broad type only unless ``exact``."""
    if exact:
        return value
    if isinstance(value, bool) or value is None or value is Ellipsis:
        return value  # bool is checked BEFORE int (it is an int subclass)
    if isinstance(value, str):
        return "LIT_STR"
    if isinstance(value, bytes):
        return "LIT_BYTES"
    if isinstance(value, (int, float, complex)):
        return "LIT_NUM"
    return value


class ASTSubtreeHasher:
    """Compute normalized AST subtree hashes and multiset similarity."""

    def __init__(self, min_subtree_size: int = 4, max_subtree_size: int = 32) -> None:
        if min_subtree_size < 1 or max_subtree_size < min_subtree_size:
            raise ValueError("need 1 <= min_subtree_size <= max_subtree_size")
        self.min_subtree_size = min_subtree_size
        self.max_subtree_size = max_subtree_size

    # ------------------------------------------------------------------ public API

    def hash_source(self, source: str, *, exclude_exact: frozenset[str] | set[str] | None = None) -> ASTSubtreeHashResult:
        """Parse and hash every eligible subtree (rename- and literal-resistant).

        Subtrees whose EXACT hash is in ``exclude_exact`` (starter code) are left out.
        """
        tree, error = self._parse(source)
        if tree is None:
            return ASTSubtreeHashResult([], parse_error=error)
        exclude = exclude_exact or frozenset()
        hashes: list[str] = []
        exact: list[str] = []
        for canonical, exact_hash in self._subtree_hashes(tree):
            if exact_hash in exclude:
                continue
            hashes.append(canonical)
            exact.append(exact_hash)
        return ASTSubtreeHashResult(hashes, exact_hashes=exact)

    def exact_hashes(self, source: str) -> frozenset[str]:
        """Name- and literal-preserving subtree hashes (use to describe starter code)."""
        tree, _ = self._parse(source)
        if tree is None:
            return frozenset()
        return frozenset(exact for _, exact in self._subtree_hashes(tree))

    def compare(
        self, source_a: str, source_b: str, *, exclude_exact: frozenset[str] | set[str] | None = None
    ) -> ASTComparison:
        """Multiset Jaccard and containment between normalized subtree hashes."""
        a = self.hash_source(source_a, exclude_exact=exclude_exact)
        b = self.hash_source(source_b, exclude_exact=exclude_exact)
        counts_a, counts_b = Counter(a.hashes), Counter(b.hashes)
        shared = sum((counts_a & counts_b).values())
        union = sum((counts_a | counts_b).values())
        smaller = min(len(a.hashes), len(b.hashes))
        return ASTComparison(
            similarity=shared / union if union else 0.0,
            containment=shared / smaller if smaller else 0.0,
            shared=shared,
            hashes_a=len(a.hashes),
            hashes_b=len(b.hashes),
            parsed_a=a.parsed,
            parsed_b=b.parsed,
        )

    def similarity(self, source_a: str, source_b: str) -> float:
        """Multiset Jaccard similarity; 0.0 when either side has no subtrees.

        (Two files with no hashes used to be "1.0 similar": any two unparseable files, any two
        non-Python files, any two empty submissions.)
        """
        return self.compare(source_a, source_b).similarity

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _parse(source: str) -> tuple[ast.AST | None, str]:
        if not isinstance(source, str) or len(source) > MAX_SOURCE_CHARS:
            return None, "source missing or too large"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # invalid-escape SyntaxWarnings are noise
                return ast.parse(source), ""
        except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def _subtree_hashes(self, tree: ast.AST) -> list[tuple[str, str]]:
        """``[(canonical_hash, exact_hash)]`` for every eligible subtree (iterative)."""
        order: list[ast.AST] = []
        children: dict[int, list[ast.AST]] = {}
        stack = [tree]
        while stack:
            node = stack.pop()
            order.append(node)
            if len(order) > MAX_NODES:
                return []
            if isinstance(node, (ast.Module, ast.ClassDef, *_FUNC_TYPES)):
                _strip_docstring(node)
            kids = [c for c in ast.iter_child_nodes(node) if not isinstance(c, ast.expr_context)]
            children[id(node)] = kids
            stack.extend(reversed(kids))

        sizes: dict[int, int] = {}
        for node in reversed(order):  # children before parents
            sizes[id(node)] = 1 + sum(sizes[id(c)] for c in children[id(node)])

        result = []
        for node in order:
            size = sizes[id(node)]
            if self.min_subtree_size <= size <= self.max_subtree_size:
                result.append((self._digest(node, children, exact=False), self._digest(node, children, exact=True)))
        return result

    def _digest(self, root: ast.AST, children: dict[int, list[ast.AST]], exact: bool) -> str:
        """Hash of one subtree. Canonical mode numbers names by first appearance INSIDE it."""
        local: dict[str, str] = {}
        payload: list[object] = []
        stack = [root]
        while stack:
            node = stack.pop()
            payload.append(type(node).__name__)
            named = _identifier_fields(node)
            for name, value in ast.iter_fields(node):
                if name in _IGNORED_FIELDS or isinstance(value, (list, ast.AST)):
                    continue
                if name in named and isinstance(value, str) and not exact:
                    if value in _BUILTIN_NAMES and isinstance(node, ast.Name):
                        payload.append((name, value))  # len / print / max keep their meaning
                    else:
                        payload.append((name, local.setdefault(value, f"ID_{len(local)}")))
                elif name == "value" and isinstance(node, ast.Constant):
                    payload.append((name, _scalar(value, exact)))
                else:
                    payload.append((name, value))
            kids = children[id(node)]
            payload.append(len(kids))
            stack.extend(reversed(kids))
        return hashlib.sha256(repr(payload).encode("utf-8", "surrogatepass")).hexdigest()
