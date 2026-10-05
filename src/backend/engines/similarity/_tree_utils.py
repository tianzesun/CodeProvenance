"""Iterative tree helpers for the AST engines.

The engines' trees are built from token streams in which every keyword opens a
new nesting level that is never closed, so depth grows with the NUMBER OF KEYWORDS
in a file. Recursive traversals (``subtree_size``, ``to_tuple``, hashing ...)
therefore hit Python's recursion limit on files of a few hundred statements, the
exception was swallowed by the engine, and the file silently scored 0. Everything
here is iterative. It also computes sizes and hashes for ALL nodes in one pass:
the old code called ``subtree_size()`` and ``to_tuple()`` per node, which is
quadratic in the tree size.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from typing import Any

try:  # the project's fast hash, when available
    from src.backend.utils.hash_utils import fast_hash64 as _fast_hash64
except Exception:  # pragma: no cover - utility module may be absent in isolation
    _fast_hash64 = None


def hash64(data: bytes) -> int:
    """Deterministic 64-bit hash of ``data``."""
    if _fast_hash64 is not None:
        try:
            return int(_fast_hash64(data)) & ((1 << 64) - 1)
        except Exception:  # noqa: S110
            pass
    return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "little")


def preorder(root: Any) -> list[Any]:
    """Nodes in pre-order (parent before children, children left to right)."""
    out: list[Any] = []
    stack = [root]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(node.children))
    return out


def postorder(root: Any) -> list[Any]:
    """Nodes in post-order (children before parent)."""
    out: list[Any] = []
    stack: list[tuple[Any, bool]] = [(root, False)]
    while stack:
        node, expanded = stack.pop()
        if expanded:
            out.append(node)
            continue
        stack.append((node, True))
        for child in reversed(node.children):
            stack.append((child, False))
    return out


def with_depths(root: Any) -> list[tuple[Any, int]]:
    """``(node, depth)`` in pre-order; the root has depth 0."""
    out: list[tuple[Any, int]] = []
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        out.append((node, depth))
        for child in reversed(node.children):
            stack.append((child, depth + 1))
    return out


def subtree_sizes(root: Any) -> dict[int, int]:
    """``id(node) -> number of nodes in its subtree`` for every node."""
    sizes: dict[int, int] = {}
    for node in postorder(root):
        sizes[id(node)] = 1 + sum(sizes[id(c)] for c in node.children)
    return sizes


def subtree_hashes(
    root: Any,
    label: Callable[[Any], str],
    *,
    ordered: bool = True,
) -> dict[int, int]:
    """``id(node) -> 64-bit hash`` of each node's whole subtree, computed bottom-up.

    ``label`` gives the node's own text; ``ordered=False`` makes the hash independent
    of child order.
    """
    hashes: dict[int, int] = {}
    for node in postorder(root):
        child_hashes = [hashes[id(c)] for c in node.children]
        if not ordered:
            child_hashes.sort()
        payload = f"{label(node)}|{child_hashes}".encode()
        hashes[id(node)] = hash64(payload)
    return hashes


def max_depth(root: Any) -> int:
    """Depth of the deepest node (root = 0)."""
    return max((d for _, d in with_depths(root)), default=0)


def count_by(nodes: Iterable[Any], key: Callable[[Any], str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        k = key(node)
        counts[k] = counts.get(k, 0) + 1
    return counts
