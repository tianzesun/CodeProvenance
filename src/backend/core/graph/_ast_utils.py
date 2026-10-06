"""Shared AST helpers for the CFG and DFG builders."""

from __future__ import annotations

import ast


def header_end_line(node: ast.AST, lines: list[str] | None = None) -> int:
    """Last source line of a node's *header*.

    For compound statements (if/for/def/class/with/try...) ``end_lineno`` covers the
    whole body. Using it as a CFG node's span made a ``def`` or ``for`` node
    "contain" every statement inside it, which broke line-based lookups. Here a
    compound statement spans only its header lines.
    """
    start = getattr(node, "lineno", 0)
    if not start:
        return 0
    end = getattr(node, "end_lineno", None) or start
    body = getattr(node, "body", None)
    if isinstance(body, list) and body:
        first = getattr(body[0], "lineno", 0)
        if first > start:
            last = first - 1
            if lines:
                while (
                    last > start
                    and last - 1 < len(lines)
                    and (
                        not lines[last - 1].strip()
                        or lines[last - 1].lstrip().startswith("#")
                    )
                ):
                    last -= 1
            return last
        return start
    return end


def source_for_node(lines: list[str], node: ast.AST) -> str:
    """Source text of a node (header only for compound statements)."""
    start = getattr(node, "lineno", None)
    if not start or not lines or not 0 < start <= len(lines):
        return ""
    end = header_end_line(node, lines)
    return " ".join(lines[start - 1 : end]).strip()
