"""Layer 4: Explainability - evidence-level granularity for auditors.

Provides the "why" behind every verdict:
  - Matched functions (one-to-one, with similarity and a precise overlap type)
  - Matched code blocks (shift-tolerant line-level regions)
  - Structural overlap (size-weighted function structure)
  - Control flow comparison
  - Identifier renames (derived from aligned, structurally equal code)

Output shape (see ``ExplanationReport.to_dict``)::

    {"function_overlap": {"fib": {"name_b": "fibo", "similarity": 0.92, "lines_a": [1, 6],
                                  "lines_b": [1, 6], "type": "renamed_variables"}},
     "block_matches": [{"lines_a": [1, 4], "lines_b": [1, 4], "score": 0.95, "type": "loop_pattern"}],
     "ast": {...}, "control_flow": {...}, "variable_renames": [...],
     "renaming_pattern": "identifier_renaming", "plagiarism_type": "type_2_renamed"}

What was wrong before (each of these affected the evidence shown to committees):
- The indentation-based function extractor crashed (TypeError on ``None``) on a whitespace-only
  line before the first function, ended every function at the first tab-indented line, and cut a
  function short at any nested ``def``. Python is now parsed with ``ast``; other languages use a
  brace/indent extractor.
- "Renamed variables" were inferred from identifier STRING similarity across ALL function pairs
  (same-length names with ratio > 0.6), so unrelated functions produced "renames", and a real
  rename (``x`` -> ``total``) was invisible. Renames now come from aligning matched functions
  whose token structure agrees, and require a consistent mapping.
- Function overlap compared raw characters (quadratic, whitespace- and comment-sensitive, threshold
  0.3 so any two short functions "overlapped") and allowed many-to-one matches. It now compares
  identifier-masked token streams, one-to-one, with a size floor.
- Blocks were fixed, aligned 4-line windows compared character-wise: a one-line shift hid a copy.
  Matching is now ``SequenceMatcher`` over normalised lines.
- "Shared structure" was the similarity of the sorted function NAMES, reported as "AST overlap".
- ``type_5_template`` was inferred without any template; it now requires the starter code.
- Control flow counted keywords inside comments/strings and ``{``/``}`` of Python dict literals.
"""

from __future__ import annotations

import ast
import builtins
import keyword
import logging
import re
import warnings
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from ._text import MAX_CODE_CHARS, tokens

logger = logging.getLogger(__name__)

# Work caps (the layer is O(n^2) in the worst case; these keep it bounded)
MAX_LINES = 4000
MAX_FUNCTIONS = 200
MAX_TOKENS_PER_FUNCTION = 1500
MIN_FUNCTION_TOKENS = 12  # trivial helpers / getters are not evidence
FUNCTION_MATCH_THRESHOLD = 0.5
MIN_BLOCK_LINES = 3
MAX_RENAMES = 10


# ─── Plagiarism type classification ────────────────────────────────────────
PLAGIARISM_TYPES = {
    "type_1_identical": "Exact copy with no changes",
    "type_2_renamed": "Identifier renaming only",
    "type_3_restructured": "Control flow reordering + renaming",
    "type_4_semantic": "Similar logic, different implementation (not conclusive)",
    "type_5_template": "Shared assignment template / starter code",
    "shared_blocks": "Shared code blocks without matching functions (verify against the starter code)",
}
NOT_CLASSIFIED = "not_plagiarized"  # value kept for compatibility; it is NOT a finding of originality


@dataclass
class FunctionOverlap:
    """Evidence for one matched function pair."""

    name_a: str
    name_b: str
    similarity: float  # [0, 1]
    lines_a: tuple[int, int]  # start, end line
    lines_b: tuple[int, int]
    type: str  # "identical", "renamed_variables", "restructured", "different_names"


@dataclass
class BlockMatch:
    """Evidence for one matched code block."""

    lines_a: tuple[int, int]
    lines_b: tuple[int, int]
    score: float
    type: str  # "loop_pattern", "conditional_block", "function_body", "import_section"


@dataclass
class VariableRename:
    """One detected identifier renaming."""

    original: str
    renamed_to: str
    context: str  # "parameter", "local_var", "loop_counter"


@dataclass
class ControlFlowEvidence:
    """Control flow comparison evidence."""

    identical: bool
    sequence_a: list[str]
    sequence_b: list[str]
    similarity: float


@dataclass
class ExplanationReport:
    """Complete explainability evidence report."""

    function_overlap: list[FunctionOverlap] = field(default_factory=list)
    function_count_a: int = 0
    function_count_b: int = 0
    avg_function_similarity: float = 0.0

    block_matches: list[BlockMatch] = field(default_factory=list)
    block_match_count: int = 0

    ast_function_count_a: int = 0
    ast_function_count_b: int = 0
    ast_class_count_a: int = 0
    ast_class_count_b: int = 0
    ast_shared_structure: float = 0.0

    control_flow: ControlFlowEvidence | None = None

    variable_renames: list[VariableRename] = field(default_factory=list)
    renaming_pattern: str = "none"
    plagiarism_type: str = NOT_CLASSIFIED
    plagiarism_description: str = ""

    #: Share of the matched lines that also appear in the instructor's starter code (0 without one).
    template_overlap_ratio: float = 0.0
    #: True when the input was long enough that part of it was not examined.
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        function_overlap: dict[str, Any] = {}
        for fo in self.function_overlap:
            key, n = fo.name_a, 1
            while key in function_overlap:  # methods share names (__init__): they used to overwrite each other
                n += 1
                key = f"{fo.name_a}#{n}"
            function_overlap[key] = {
                "name_b": fo.name_b,
                "similarity": round(fo.similarity, 4),
                "lines_a": list(fo.lines_a),
                "lines_b": list(fo.lines_b),
                "type": fo.type,
            }
        cf = self.control_flow
        return {
            "function_overlap": function_overlap,
            "function_count_a": self.function_count_a,
            "function_count_b": self.function_count_b,
            "avg_function_similarity": round(self.avg_function_similarity, 4),
            "block_matches": [
                {"lines_a": list(bm.lines_a), "lines_b": list(bm.lines_b), "score": round(bm.score, 4), "type": bm.type}
                for bm in self.block_matches
            ],
            "block_match_count": self.block_match_count,
            "ast": {
                "function_count_a": self.ast_function_count_a,
                "function_count_b": self.ast_function_count_b,
                "class_count_a": self.ast_class_count_a,
                "class_count_b": self.ast_class_count_b,
                "shared_structure": round(self.ast_shared_structure, 4),
            },
            "control_flow": {
                "identical": cf.identical if cf else False,
                "similarity": round(cf.similarity, 4) if cf else 0.0,
                "sequence_a": cf.sequence_a[:10] if cf else [],
                "sequence_b": cf.sequence_b[:10] if cf else [],
            },
            "variable_renames": [
                {"original": vr.original, "renamed_to": vr.renamed_to, "context": vr.context}
                for vr in self.variable_renames[:MAX_RENAMES]
            ],
            "renaming_pattern": self.renaming_pattern,
            "plagiarism_type": self.plagiarism_type,
            "plagiarism_description": self.plagiarism_description,
            "template_overlap_ratio": round(self.template_overlap_ratio, 4),
            "truncated": self.truncated,
        }

    def summary(self) -> str:
        """Human-readable summary for academic committee reports."""
        lines = ["Evidence Summary:", ""]

        if self.function_overlap:
            lines.append("Function overlap:")
            for fo in self.function_overlap[:10]:
                lines.append(f"  {fo.name_a} → {fo.name_b}: {fo.similarity:.0%} ({fo.type})")
            if len(self.function_overlap) > 10:
                lines.append(f"  ... and {len(self.function_overlap) - 10} more")
            lines.append("")

        if self.ast_shared_structure > 0:
            lines.append(
                f"Structural overlap: {self.ast_shared_structure:.0%}"
                f" ({self.ast_function_count_a} vs {self.ast_function_count_b} functions)"
            )
            lines.append("")

        if self.control_flow and self.control_flow.similarity > 0:
            flow_label = "identical" if self.control_flow.identical else f"{self.control_flow.similarity:.0%} similar"
            lines.append(f"Control flow: {flow_label}")
            lines.append(f"  A: {' → '.join(self.control_flow.sequence_a[:8])}")
            lines.append(f"  B: {' → '.join(self.control_flow.sequence_b[:8])}")
            lines.append("")

        if self.variable_renames:
            lines.append("Identifier renames detected:")
            for vr in self.variable_renames[:5]:
                lines.append(f"  {vr.original} → {vr.renamed_to} ({vr.context})")
            lines.append("")

        if self.template_overlap_ratio > 0:
            lines.append(f"Matched lines also present in the starter code: {self.template_overlap_ratio:.0%}")
            lines.append("")

        if self.plagiarism_type != NOT_CLASSIFIED:
            lines.append(f"Classification: {self.plagiarism_type}")
            lines.append(f"  {self.plagiarism_description}")
        elif self.plagiarism_description:
            lines.append(self.plagiarism_description)

        if self.truncated:
            lines.append("(Large input: only the first part of each file was examined.)")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions for code analysis
# ═══════════════════════════════════════════════════════════════════════════
PYTHON_KEYWORDS = {
    "if", "else", "elif", "for", "while", "def", "class", "return", "import", "from", "with", "as",
    "try", "except", "finally", "raise", "yield", "assert", "pass", "break", "continue", "del",
    "global", "nonlocal", "and", "or", "not", "in", "is", "lambda", "True", "False", "None",
    "print", "range", "len", "int", "str", "list", "dict", "set", "float",
}  # fmt: skip

COMMON_PYTHON_BUILTINS = {
    "len", "int", "str", "float", "list", "dict", "set", "tuple", "print", "range", "input", "type",
    "sum", "min", "max", "abs", "sorted", "reversed", "enumerate", "zip", "map", "filter",
    "isinstance", "hasattr", "getattr",
}  # fmt: skip

_OTHER_KEYWORDS = {
    "function", "func", "fn", "var", "let", "const", "switch", "case", "default", "do", "catch",
    "throw", "throws", "new", "this", "self", "super", "public", "private", "protected", "static",
    "final", "void", "null", "nil", "true", "false", "struct", "interface", "enum", "extends",
    "implements", "package", "namespace", "using", "include", "int", "long", "double", "char",
    "bool", "boolean", "string", "async", "await", "typeof", "instanceof",
}  # fmt: skip
_NON_RENAMEABLE = set(keyword.kwlist) | set(dir(builtins)) | PYTHON_KEYWORDS | COMMON_PYTHON_BUILTINS | _OTHER_KEYWORDS

_CONTROL = {"if", "else", "elif", "for", "while", "switch", "case", "return", "break", "continue"}
_EXCEPTION = {"try", "catch", "except", "finally"}


def _parse_python(code: str) -> ast.AST | None:
    """The AST when ``code`` is valid Python, else None (never raises)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None


def _masked(code: str, language: str | None) -> list[str]:
    """Identifier-masked token stream: identifiers -> ID, numbers -> NUM, strings -> STR."""
    out = []
    for kind, text in tokens(code, language):
        if kind == "ident":
            out.append(text if text in _NON_RENAMEABLE else "ID")
        elif kind == "number":
            out.append("NUM")
        elif kind == "string":
            out.append("STR")
        else:
            out.append(text)
    return out[:MAX_TOKENS_PER_FUNCTION]


def _exact_tokens(code: str, language: str | None) -> list[str]:
    """Token stream with identifiers and literals preserved (comments and layout dropped)."""
    return [text for _, text in tokens(code, language)][:MAX_TOKENS_PER_FUNCTION]


_GENERIC_HEADER = re.compile(r"^\s*(?:async\s+)?(?:def|function|func|fn|sub)\s+(\w+)\s*\(([^)]*)\)")
_CLIKE_HEADER = re.compile(r"^\s*(?:[\w<>\[\],.*&:]+\s+)+?(\w+)\s*\(([^;{}()]*)\)\s*(?:const\s*)?(?:throws\s+[\w, .]+)?\s*\{?\s*$")
_NOT_FUNCTIONS = {"if", "for", "while", "switch", "catch", "return", "else", "sizeof", "do", "synchronized"}


def _strip_line_noise(line: str) -> str:
    """Remove string literals and ``//`` comments from one line (for brace counting)."""
    line = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "", line)
    return line.split("//", 1)[0]


def _params(raw: str) -> list[str]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        part = part.split("=")[0].split(":")[0].strip()
        words = re.findall(r"[A-Za-z_]\w*", part)
        if words:
            out.append(words[-1])  # "int x" -> x; "x" -> x
    return out


def _extract_functions_python(code: str, tree: ast.AST) -> list[dict[str, Any]]:
    lines = code.split("\n")
    functions = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", None) or node.lineno
        first_body = node.body[0].lineno if node.body else node.lineno
        args = node.args
        names = [a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]]
        names += [a.arg for a in (args.vararg, args.kwarg) if a is not None]
        functions.append(
            {
                "name": node.name,
                "start_line": node.lineno,
                "end_line": end,
                "params": [n for n in names if n not in ("self", "cls")],
                "body": "\n".join(lines[first_body - 1 : end]),
            }
        )
    functions.sort(key=lambda f: f["start_line"])
    return functions


def _extract_functions_generic(code: str) -> list[dict[str, Any]]:
    """Brace- or indentation-delimited functions for non-Python source."""
    lines = code.split("\n")
    functions = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = _GENERIC_HEADER.match(line) or _CLIKE_HEADER.match(line)
        if not match or match.group(1) in _NOT_FUNCTIONS:
            i += 1
            continue
        name, params = match.group(1), _params(match.group(2))
        indent = len(line) - len(line.lstrip())
        brace_open = "{" in _strip_line_noise(line) or (i + 1 < len(lines) and lines[i + 1].strip().startswith("{"))
        end = i
        if brace_open:
            depth, started, j = 0, False, i
            while j < len(lines):
                for ch in _strip_line_noise(lines[j]):
                    if ch == "{":
                        depth, started = depth + 1, True
                    elif ch == "}":
                        depth -= 1
                if started and depth <= 0:
                    break
                j += 1
            end = min(j, len(lines) - 1)
        else:  # indentation-delimited (tabs and spaces both count as indentation)
            j = i + 1
            last = i
            while j < len(lines):
                text = lines[j]
                if text.strip():
                    if len(text) - len(text.lstrip()) <= indent:
                        break
                    last = j
                j += 1
            end = last
        functions.append(
            {"name": name, "start_line": i + 1, "end_line": end + 1, "params": params, "body": "\n".join(lines[i + 1 : end + 1])}
        )
        i = end + 1 if end > i else i + 1
    return functions


def _extract_functions(code: str) -> list[dict[str, Any]]:
    """Function definitions (name, 1-based line range, parameters, body text)."""
    code = (code or "")[:MAX_CODE_CHARS]
    tree = _parse_python(code)
    functions = _extract_functions_python(code, tree) if tree is not None else _extract_functions_generic(code)
    return functions[:MAX_FUNCTIONS]


def _extract_control_flow(code: str, language: str | None = None) -> list[str]:
    """Control-flow keyword sequence (comments/strings ignored; ``else if`` is one ELIF)."""
    python = language == "python"
    result: list[str] = []
    previous = ""
    for kind, text in tokens(code, language):
        if kind == "ident":
            if text == "if" and previous == "else":
                result[-1] = "ELIF"  # "else if" -> ELIF (matches Python's elif)
            elif text in _CONTROL:
                result.append(text.upper())
            elif text in _EXCEPTION:
                result.append("EXCEPTION")
        elif kind == "op" and not python and text in "{}":
            result.append("BLOCK_START" if text == "{" else "BLOCK_END")
        previous = text
    return result


def _detect_renames(
    params_a: list[str],
    params_b: list[str],
    body_a: str,
    body_b: str,
    language: str | None = None,
) -> list[VariableRename]:
    """Identifier renames between two MATCHED function bodies.

    The identifier-masked token streams are aligned; each aligned identifier pair is a candidate
    (a -> b). A rename needs a consistent mapping: most occurrences of ``a`` must align to the
    same ``b``, and each ``b`` is used once. Attribute names (after a dot) are not variables.
    """
    toks_a, toks_b = tokens(body_a, language)[:MAX_TOKENS_PER_FUNCTION], tokens(body_b, language)[:MAX_TOKENS_PER_FUNCTION]

    def prep(toks: list[tuple[str, str]]) -> tuple[list[str], list[str], list[bool], list[str]]:
        masked, raw, attr, prev_raw = [], [], [], []
        last = ""
        for kind, text in toks:
            if kind == "ident":
                masked.append(text if text in _NON_RENAMEABLE else "ID")
            elif kind == "number":
                masked.append("NUM")
            elif kind == "string":
                masked.append("STR")
            else:
                masked.append(text)
            raw.append(text)
            attr.append(last == ".")
            prev_raw.append(last)
            last = text
        return masked, raw, attr, prev_raw

    ma, ra, attr_a, prev_a = prep(toks_a)
    mb, rb, attr_b, _ = prep(toks_b)
    if not ma or not mb:
        return []

    pairs: Counter[tuple[str, str]] = Counter()
    for block in SequenceMatcher(None, ma, mb, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            i, j = block.a + k, block.b + k
            if ma[i] == "ID" and not attr_a[i] and not attr_b[j]:
                pairs[(ra[i], rb[j])] += 1

    occurrences = Counter(t for t, m, at in zip(ra, ma, attr_a) if m == "ID" and not at)
    loop_vars = {t for t, p, m in zip(ra, prev_a, ma) if m == "ID" and p == "for"}
    renames: list[VariableRename] = []
    used_b: set[str] = set()
    for (a, b), count in pairs.most_common():
        if a == b or b in used_b or any(r.original == a for r in renames):
            continue
        if count / max(1, occurrences[a]) < 0.6:  # not a consistent mapping
            continue
        used_b.add(b)
        context = "parameter" if a in params_a else "loop_counter" if a in loop_vars else "local_var"
        renames.append(VariableRename(original=a, renamed_to=b, context=context))
        if len(renames) >= MAX_RENAMES:
            break
    return renames


def _similarity(a: list[str], b: list[str], floor: float) -> float:
    """SequenceMatcher ratio with cheap upper-bound rejection (0.0 below ``floor``)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    if matcher.real_quick_ratio() < floor or matcher.quick_ratio() < floor:
        return 0.0
    return matcher.ratio()


_IMPORT_LINE = re.compile(r"^\s*(?:import\s|from\s+\S+\s+import\s|#include|using\s|package\s|require\()")


class Layer4Explainability:
    """Explainability layer - generates human-readable evidence for every verdict.

    Used for coordinator reviews, integrity-committee hearings, student appeals and evidence
    preservation. It describes similarities; it does not decide anything.
    """

    def evaluate(
        self,
        code_a: str,
        code_b: str,
        engine_scores: dict[str, float] | None = None,
        engine_details: dict[str, Any] | None = None,
        template_code: str | None = None,
    ) -> ExplanationReport:
        """Run explainability analysis on a pair of code files.

        Args:
            code_a, code_b: Source code of the two files.
            engine_scores / engine_details: unused (kept for interface compatibility).
            template_code: Optional instructor starter code; matched lines that also appear in it
                are reported as ``template_overlap_ratio`` and drive ``type_5_template``.
        """
        code_a, code_b = (code_a or "")[:MAX_CODE_CHARS], (code_b or "")[:MAX_CODE_CHARS]
        truncated = code_a.count("\n") >= MAX_LINES or code_b.count("\n") >= MAX_LINES
        code_a, code_b = "\n".join(code_a.split("\n")[:MAX_LINES]), "\n".join(code_b.split("\n")[:MAX_LINES])
        python = _parse_python(code_a) is not None and _parse_python(code_b) is not None
        language = "python" if python else None

        # ── Functions: one-to-one matching on identifier-masked token streams ──
        funcs_a, funcs_b = _extract_functions(code_a), _extract_functions(code_b)
        for f in (*funcs_a, *funcs_b):
            f["masked"] = _masked(f["body"], language)
            f["exact"] = _exact_tokens(f["body"], language)
        eligible_a = [f for f in funcs_a if len(f["masked"]) >= MIN_FUNCTION_TOKENS]
        eligible_b = [f for f in funcs_b if len(f["masked"]) >= MIN_FUNCTION_TOKENS]

        candidates: list[tuple[float, int, int]] = []
        for i, fa in enumerate(eligible_a):
            for j, fb in enumerate(eligible_b):
                sim = _similarity(fa["masked"], fb["masked"], FUNCTION_MATCH_THRESHOLD)
                if sim >= FUNCTION_MATCH_THRESHOLD:
                    candidates.append((sim, i, j))
        candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
        used_a: set[int] = set()
        used_b: set[int] = set()
        matched: list[tuple[dict[str, Any], dict[str, Any], float]] = []
        for sim, i, j in candidates:
            if i in used_a or j in used_b:
                continue
            used_a.add(i)
            used_b.add(j)
            matched.append((eligible_a[i], eligible_b[j], sim))

        function_overlap: list[FunctionOverlap] = []
        for fa, fb, sim in sorted(matched, key=lambda m: m[0]["start_line"]):
            if fa["exact"] == fb["exact"]:
                overlap_type = "identical" if fa["name"] == fb["name"] else "different_names"
            elif sim >= 0.999:
                overlap_type = "renamed_variables"
            else:
                overlap_type = "restructured"
            function_overlap.append(
                FunctionOverlap(
                    name_a=fa["name"],
                    name_b=fb["name"],
                    similarity=sim,
                    lines_a=(fa["start_line"], fa["end_line"]),
                    lines_b=(fb["start_line"], fb["end_line"]),
                    type=overlap_type,
                )
            )
        avg_func_sim = sum(fo.similarity for fo in function_overlap) / len(function_overlap) if function_overlap else 0.0

        # ── Blocks: shift-tolerant matching over normalised lines ──
        block_matches, matched_lines_a = self._match_blocks(code_a, code_b, language)

        # ── Structure: size-weighted similarity of matched functions (whole file if no functions) ──
        if funcs_a or funcs_b:
            total_a = sum(len(f["masked"]) for f in funcs_a) or 1
            total_b = sum(len(f["masked"]) for f in funcs_b) or 1
            shared = sum(sim * min(len(fa["masked"]), len(fb["masked"])) for fa, fb, sim in matched)
            struct_sim = min(1.0, shared / max(total_a, total_b))
        else:
            struct_sim = _similarity(_masked(code_a, language), _masked(code_b, language), 0.0)

        if python:
            class_count_a = sum(isinstance(n, ast.ClassDef) for n in ast.walk(_parse_python(code_a)))
            class_count_b = sum(isinstance(n, ast.ClassDef) for n in ast.walk(_parse_python(code_b)))
        else:
            class_count_a = len(re.findall(r"^\s*(?:class|struct|interface)\s+\w+", code_a, re.MULTILINE))
            class_count_b = len(re.findall(r"^\s*(?:class|struct|interface)\s+\w+", code_b, re.MULTILINE))

        # ── Control flow ──
        flow_a, flow_b = _extract_control_flow(code_a, language), _extract_control_flow(code_b, language)
        if flow_a and flow_b:
            flow_sim = SequenceMatcher(None, flow_a[:3000], flow_b[:3000], autojunk=False).ratio()
            flow_identical = flow_a == flow_b
        else:
            flow_sim, flow_identical = 0.0, False
        control_flow = ControlFlowEvidence(
            identical=flow_identical, sequence_a=flow_a[:15], sequence_b=flow_b[:15], similarity=flow_sim
        )

        # ── Renames: only inside matched function pairs that are structurally the same ──
        seen: set[tuple[str, str]] = set()
        variable_renames: list[VariableRename] = []
        for fa, fb, sim in matched:
            if sim < 0.8:
                continue
            for rename in _detect_renames(fa["params"], fb["params"], fa["body"], fb["body"], language):
                key = (rename.original, rename.renamed_to)
                if key not in seen:
                    seen.add(key)
                    variable_renames.append(rename)
        variable_renames = variable_renames[:MAX_RENAMES]

        # ── Template overlap ──
        template_ratio = self._template_overlap(code_a, matched_lines_a, template_code)

        files_identical = (
            bool(code_a.strip()) and "\n".join(l.rstrip() for l in code_a.strip().split("\n")) == "\n".join(l.rstrip() for l in code_b.strip().split("\n"))
        )
        plagiarism_type, plagiarism_desc = self._classify_type(
            function_overlap=function_overlap,
            block_matches=block_matches,
            variable_renames=variable_renames,
            control_flow_sim=control_flow.similarity,
            files_identical=files_identical,
            template_ratio=template_ratio,
        )

        if variable_renames:
            renaming_pattern = "identifier_renaming"
        elif any(fo.type == "different_names" for fo in function_overlap):
            renaming_pattern = "function_renaming"
        elif any(fo.type == "identical" for fo in function_overlap):
            renaming_pattern = "exact_copy"
        elif block_matches:
            renaming_pattern = "block_reuse"
        else:
            renaming_pattern = "none"

        return ExplanationReport(
            function_overlap=function_overlap,
            function_count_a=len(funcs_a),
            function_count_b=len(funcs_b),
            avg_function_similarity=avg_func_sim,
            block_matches=block_matches,
            block_match_count=len(block_matches),
            ast_function_count_a=len(funcs_a),
            ast_function_count_b=len(funcs_b),
            ast_class_count_a=class_count_a,
            ast_class_count_b=class_count_b,
            ast_shared_structure=struct_sim,
            control_flow=control_flow,
            variable_renames=variable_renames,
            renaming_pattern=renaming_pattern,
            plagiarism_type=plagiarism_type,
            plagiarism_description=plagiarism_desc,
            template_overlap_ratio=template_ratio,
            truncated=truncated,
        )

    # ------------------------------------------------------------------ blocks / template

    @staticmethod
    def _match_blocks(code_a: str, code_b: str, language: str | None) -> tuple[list[BlockMatch], set[int]]:
        """Matching runs of >= 3 meaningful lines; returns (blocks, matched A line numbers)."""

        def normalise(code: str) -> tuple[list[str], list[int], list[str]]:
            norm, numbers, raw = [], [], []
            for number, line in enumerate(code.split("\n"), 1):
                text = line.strip()
                if not text:
                    continue
                key = " ".join(_masked(text, language))
                if not key:  # comment-only line
                    continue
                norm.append(key)
                numbers.append(number)
                raw.append(text)
            return norm, numbers, raw

        norm_a, nums_a, raw_a = normalise(code_a)
        norm_b, nums_b, raw_b = normalise(code_b)
        if not norm_a or not norm_b:
            return [], set()

        blocks: list[BlockMatch] = []
        matched_lines: set[int] = set()
        for m in SequenceMatcher(None, norm_a, norm_b, autojunk=False).get_matching_blocks():
            if m.size < MIN_BLOCK_LINES:
                continue
            seg_a = raw_a[m.a : m.a + m.size]
            seg_b = raw_b[m.b : m.b + m.size]
            if all(_IMPORT_LINE.match(line) for line in seg_a):
                btype = "import_section"
            else:
                text = " ".join(norm_a[m.a : m.a + m.size])
                if re.search(r"\b(?:for|while)\b", text):
                    btype = "loop_pattern"
                elif re.search(r"\b(?:if|else|elif|switch)\b", text):
                    btype = "conditional_block"
                else:
                    btype = "function_body"
            equal = sum(1 for x, y in zip(seg_a, seg_b) if x == y) / m.size
            blocks.append(
                BlockMatch(
                    lines_a=(nums_a[m.a], nums_a[m.a + m.size - 1]),
                    lines_b=(nums_b[m.b], nums_b[m.b + m.size - 1]),
                    score=0.85 + 0.15 * equal,  # identifier-normalised match 0.85; byte-identical lines 1.0
                    type=btype,
                )
            )
            if btype != "import_section":
                matched_lines.update(nums_a[m.a : m.a + m.size])
        blocks.sort(key=lambda b: (-(b.lines_a[1] - b.lines_a[0]), -b.score, b.lines_a[0]))
        return blocks[:15], matched_lines

    @staticmethod
    def _template_overlap(code_a: str, matched_lines_a: set[int], template_code: str | None) -> float:
        """Share of the matched (non-import) lines of A that also appear in the starter code."""
        if not template_code or not matched_lines_a:
            return 0.0
        template_lines = {l.strip() for l in template_code.split("\n") if l.strip()}
        lines = code_a.split("\n")
        hits = sum(1 for n in matched_lines_a if 0 < n <= len(lines) and lines[n - 1].strip() in template_lines)
        return hits / len(matched_lines_a)

    # ------------------------------------------------------------------ classification

    def _classify_type(
        self,
        function_overlap: list[FunctionOverlap],
        block_matches: list[BlockMatch],
        variable_renames: list[VariableRename],
        control_flow_sim: float,
        files_identical: bool = False,
        template_ratio: float = 0.0,
    ) -> tuple[str, str]:
        """Classify the similarity pattern from the evidence.

        These are descriptions of what the evidence looks like, not findings of misconduct; a
        coordinator has to judge them against the assignment (common solutions, starter code).

        Returns:
            Tuple of (type_name, human_description)
        """
        if files_identical:
            return "type_1_identical", "The two files are identical (ignoring line endings and trailing whitespace)."
        if template_ratio >= 0.7:
            return (
                "type_5_template",
                f"{template_ratio:.0%} of the matched code also appears in the starter code: the overlap is "
                "most likely the shared template, not copying.",
            )

        identical = [fo for fo in function_overlap if fo.type == "identical"]
        renamed_funcs = [fo for fo in function_overlap if fo.type in ("renamed_variables", "different_names")]
        restructured = [fo for fo in function_overlap if fo.type == "restructured"]
        avg_func_sim = (
            sum(fo.similarity for fo in function_overlap) / len(function_overlap) if function_overlap else 0.0
        )

        if identical and not variable_renames:
            return "type_1_identical", f"{len(identical)} function(s) are identical across both files."
        if renamed_funcs and variable_renames:
            return (
                "type_2_renamed",
                f"Identifier renaming detected - {len(variable_renames)} identifier(s) renamed; "
                "function bodies are structurally the same.",
            )
        if restructured and control_flow_sim > 0.5:
            return "type_3_restructured", "Similar logic with a different structure (reordering and/or renaming)."
        if avg_func_sim > 0.5 and not variable_renames:
            return (
                "type_4_semantic",
                "Similar logic with a different implementation. This is also what a common solution to the "
                "same task looks like - not conclusive on its own.",
            )
        if any(bm.score > 0.9 and bm.type != "import_section" for bm in block_matches) and not function_overlap:
            return (
                "shared_blocks",
                "Shared code blocks without matching functions. Check them against the starter code.",
            )
        return NOT_CLASSIFIED, "No similarity pattern identified (this is not a finding of originality)."
