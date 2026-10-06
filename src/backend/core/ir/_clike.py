"""Brace-aware structural parser for Java and JavaScript.

Builds a nested :class:`~.ast_ir.ASTNode` tree (Class > Method/Function > If/For/
While/Try/... > Block) from the token stream and records, on every function-like
node, the calls made directly in its body (``metadata["calls"]``, entries are
``"name"`` or ``"qualifier.name"``). This replaces the line-by-line regexes that
produced flat lists and mistook ``if (x)`` for a method named ``if``.

It is a heuristic recogniser: no type information, no regex-literal handling
in JavaScript, and generics are not parsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._lexer import RawToken, lex

_CONTROL = {
    "if": "If", "for": "For", "while": "While", "switch": "Switch", "try": "Try",
    "catch": "Catch", "finally": "Finally", "do": "Do", "else": "Else",
    "synchronized": "Synchronized", "with": "With",
}  # fmt: skip
_CLASS_KEYWORDS = {"class", "interface", "enum"}
# identifiers followed by "(" that are not calls
_NOT_CALLS = set(_CONTROL) | {
    "function", "return", "typeof", "new", "await", "yield", "throw", "super",
    "this", "case", "default", "assert", "void", "delete", "in", "of", "instanceof",
}  # fmt: skip
_NOT_DECL_LEAD = {
    "return",
    "throw",
    "new",
    "else",
    "yield",
    "assert",
    "await",
    "case",
    "delete",
}
FUNCTION_TYPES = {"Method", "Function"}


@dataclass
class _Open:
    node: object  # ASTNode
    saved_header: list[RawToken] = field(default_factory=list)
    saved_paren: int = 0
    saved_calls: list[tuple[int, str, str]] = field(default_factory=list)


def parse_clike(source: str, language: str):
    """Parse ``source`` ('java' or 'javascript') into an ASTNode tree."""
    from .ast_ir import ASTNode

    java = language == "java"
    tokens = [t for t in lex(source, language) if t.kind != "comment"]
    root = ASTNode(
        node_type="CompilationUnit" if java else "Program",
        value="",
        line_start=1,
        col_start=0,
    )
    stack: list[_Open] = [_Open(root)]
    header: list[RawToken] = []
    calls: list[tuple[int, str, str]] = []  # (index in header, name, qualifier)
    paren = 0

    def owner_node():
        """Innermost function-like node, else innermost non-control node."""
        for frame in reversed(stack):
            if frame.node.node_type in FUNCTION_TYPES:
                return frame.node
        for frame in reversed(stack):
            if frame.node.node_type in ("Class", "AnonymousClass"):
                return frame.node
        return stack[0].node

    def record_calls(skip_index: int | None = None) -> None:
        owner = owner_node()
        for index, name, qualifier in calls:
            if index != skip_index:
                owner.metadata.setdefault("calls", []).append(
                    f"{qualifier}.{name}" if qualifier else name
                )

    def make_node(node_type: str, value: str, first: RawToken | None, brace: RawToken):
        start = first or brace
        node = ASTNode(
            node_type=node_type,
            value=value,
            line_start=start.line,
            line_end=brace.end_line,
            col_start=start.col,
            col_end=brace.end_col,
        )
        stack[-1].node.children.append(node)
        return node

    for i, tok in enumerate(tokens):
        text = tok.text
        nxt = tokens[i + 1].text if i + 1 < len(tokens) else ""

        if tok.kind == "punct" and text == "{":
            node_type, value, skip = _classify(header, paren, java)
            node = make_node(node_type, value, header[0] if header else None, tok)
            if node_type == "Class" or node_type == "AnonymousClass":
                node.metadata["kind"] = _class_kind(header)
            record_calls(skip_index=skip)
            # calls were just recorded: do not resume them when the block closes
            stack.append(_Open(node, header, paren, []))
            header, calls, paren = [], [], 0
            continue

        if tok.kind == "punct" and text == "}":
            if len(stack) > 1:
                frame = stack.pop()
                frame.node.line_end = tok.end_line
                frame.node.col_end = tok.end_col
                if (
                    frame.saved_paren > 0
                ):  # block inside call args: resume the outer header
                    header, calls, paren = (
                        frame.saved_header,
                        frame.saved_calls,
                        frame.saved_paren,
                    )
                else:
                    header, calls, paren = [], [], 0
            continue

        if tok.kind == "punct" and text == ";" and paren == 0:
            _finish_statement(header, calls, stack, java, record_calls, ASTNode)
            header, calls = [], []
            continue

        if (
            tok.kind == "punct"
            and text == ":"
            and paren == 0
            and header
            and header[0].text in ("case", "default")
        ):
            header, calls = [], []  # switch label
            continue

        # ordinary token: extend the header, track parens and call sites
        if text in ("(", "[") and tok.kind == "punct":
            paren += 1
        elif text in (")", "]") and tok.kind == "punct":
            paren = max(0, paren - 1)

        if tok.kind == "ident" and nxt == "(" and text not in _NOT_CALLS:
            prev = header[-1].text if header else ""
            if prev not in ("function",):
                qualifier = ""
                if prev in (".", "?.") and len(header) >= 2:
                    q = header[-2]
                    qualifier = q.text if q.kind == "ident" else "?"
                calls.append((len(header), text, qualifier))
        header.append(tok)

    # EOF: close dangling blocks
    last = tokens[-1] if tokens else None
    while len(stack) > 1:
        frame = stack.pop()
        if last is not None:
            frame.node.line_end = last.end_line
            frame.node.col_end = last.end_col
    if last is not None:
        root.line_end, root.col_end = last.end_line, last.end_col
    return root


def _class_kind(header: list[RawToken]) -> str:
    for t in header:
        if t.text in _CLASS_KEYWORDS:
            return t.text
    return "anonymous"


def _matching_close_paren_tail(texts: list[str], start: int) -> bool:
    """True if texts[start] is '(' whose matching ')' is the last token."""
    depth = 0
    for j in range(start, len(texts)):
        if texts[j] == "(":
            depth += 1
        elif texts[j] == ")":
            depth -= 1
            if depth == 0:
                return j == len(texts) - 1
    return False


def _classify(
    header: list[RawToken], paren: int, java: bool
) -> tuple[str, str, int | None]:
    """(node_type, name, index of the declaration-name token in header)."""
    texts = [t.text for t in header]
    kinds = [t.kind for t in header]
    first = texts[0] if texts else ""

    if paren > 0:  # `{` inside call arguments: lambda / anonymous fn / object literal
        if texts and texts[-1] in ("->", "=>"):
            return "Function", "", None
        for j in range(len(texts) - 1, -1, -1):
            if texts[j] == "function":
                k = j + 1
                if k < len(texts) and texts[k] == "*":
                    k += 1
                name = ""
                if (
                    k < len(texts)
                    and kinds[k] == "ident"
                    and k + 1 < len(texts)
                    and texts[k + 1] == "("
                ):
                    name, k = texts[k], k + 1
                if (
                    k < len(texts)
                    and texts[k] == "("
                    and _matching_close_paren_tail(texts, k)
                ):
                    return "Function", name, None
                break
        for j in range(len(texts) - 3):
            if (
                texts[j] == "new"
                and kinds[j + 1] == "ident"
                and texts[j + 2] == "("
                and _matching_close_paren_tail(texts, j + 2)
            ):
                return "AnonymousClass", "", None
        return "Block", "", None

    # class / interface / enum
    for j, t in enumerate(texts):
        if t in _CLASS_KEYWORDS and (j == 0 or texts[j - 1] != "."):
            name = (
                texts[j + 1] if j + 1 < len(texts) and kinds[j + 1] == "ident" else ""
            )
            return "Class", name, None

    if texts and texts[-1] in ("->", "=>") and first not in ("case", "default"):
        name = ""
        if not java and "=" in texts:  # JS: `const f = (...) => {` names the function
            e = texts.index("=")
            if e > 0 and kinds[e - 1] == "ident":
                name = texts[e - 1]
        return "Function", name, None

    if first in _CONTROL:
        if first == "else" and len(texts) > 1 and texts[1] == "if":
            return "If", "", None
        return _CONTROL[first], "", None

    if "function" in texts:
        j = texts.index("function")
        k = j + 1
        if k < len(texts) and texts[k] == "*":
            k += 1
        if (
            k < len(texts)
            and kinds[k] == "ident"
            and k + 1 < len(texts)
            and texts[k + 1] == "("
        ):
            return "Function", texts[k], k
        name = ""
        if "=" in texts[:j]:
            e = texts.index("=")
            if e > 0 and kinds[e - 1] == "ident":
                name = texts[e - 1]
        return "Function", name, None

    for j, t in enumerate(texts):  # first `ident (` at top level => method / ctor
        if (
            kinds[j] == "ident"
            and j + 1 < len(texts)
            and texts[j + 1] == "("
            and t not in _NOT_CALLS
        ):
            if "=" in texts[:j]:
                break  # `x = foo(...) {` is not a declaration
            if j > 0 and texts[j - 1] == "new":
                return "AnonymousClass", "", None
            if j > 0 and texts[j - 1] in (".", "?."):
                break
            return "Method", t, j
    return "Block", "", None


def _finish_statement(header, calls, stack, java, record_calls, ASTNode) -> None:
    """Handle a statement terminated by ';' at paren depth 0."""
    if not header:
        return
    texts = [t.text for t in header]
    first = texts[0]
    parent = stack[-1].node

    if first in _CONTROL:
        siblings = parent.children
        if first == "while" and siblings and siblings[-1].node_type == "Do":
            record_calls()  # `do { } while (cond);` - the condition's calls
            return
        end = header[-1]
        parent.children.append(
            ASTNode(
                node_type=(
                    _CONTROL[first]
                    if not (first == "else" and "if" in texts[1:2])
                    else "If"
                ),
                value="",
                line_start=header[0].line,
                line_end=end.end_line,
                col_start=header[0].col,
                col_end=end.end_col,
            )
        )
        record_calls()
        return

    if java and parent.node_type == "Class":
        # abstract / interface method declaration: `Type name(params);`
        for j, t in enumerate(header):
            if t.kind == "ident" and j + 1 < len(header) and texts[j + 1] == "(":
                lead = texts[:j]
                if (
                    lead
                    and "=" not in lead
                    and "." not in lead
                    and first not in _NOT_DECL_LEAD
                    and header[j - 1].kind in ("ident", "op", "punct")
                    and (header[j - 1].kind == "ident" or texts[j - 1] in (">", "]"))
                ):
                    end = header[-1]
                    parent.children.append(
                        ASTNode(
                            node_type="Method",
                            value=t.text,
                            line_start=header[0].line,
                            line_end=end.end_line,
                            col_start=header[0].col,
                            col_end=end.end_col,
                            metadata={"abstract": True},
                        )
                    )
                    calls[:] = [c for c in calls if c[0] != j]
                break
    record_calls()
