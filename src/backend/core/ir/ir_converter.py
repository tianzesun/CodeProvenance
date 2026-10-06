"""
IR Converter.

Provides conversion utilities between different intermediate representations.
"""

import hashlib
import warnings
from collections.abc import Callable
from dataclasses import replace
from typing import ClassVar

from .ast_ir import ASTIR, ASTNode
from .base_ir import BaseIR, IRMetadata
from .graph_ir import GraphEdge, GraphIR, GraphNode
from .token_ir import Token, TokenIR

# Python operator node -> source symbol
_OP_SYMBOLS = {
    "Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "FloorDiv": "//", "Mod": "%",
    "Pow": "**", "MatMult": "@", "LShift": "<<", "RShift": ">>", "BitOr": "|",
    "BitXor": "^", "BitAnd": "&", "And": "and", "Or": "or", "Not": "not",
    "Invert": "~", "UAdd": "+", "USub": "-", "Eq": "==", "NotEq": "!=", "Lt": "<",
    "LtE": "<=", "Gt": ">", "GtE": ">=", "Is": "is", "IsNot": "is not", "In": "in",
    "NotIn": "not in",
}  # fmt: skip
# nodes that stand for a keyword (emitted before their children)
_KEYWORD_NODES = {
    "If": "if", "For": "for", "AsyncFor": "for", "While": "while", "Return": "return",
    "Raise": "raise", "Pass": "pass", "Break": "break", "Continue": "continue",
    "FunctionDef": "def", "AsyncFunctionDef": "def", "ClassDef": "class",
    "Import": "import", "ImportFrom": "from", "Try": "try", "With": "with",
    "AsyncWith": "with", "Assert": "assert", "Delete": "del", "Global": "global",
    "Nonlocal": "nonlocal", "Lambda": "lambda", "Yield": "yield", "YieldFrom": "yield",
    "Await": "await", "ExceptHandler": "except",
    # Java / JavaScript tree (see _clike)
    "Class": "class", "Function": "function", "Switch": "switch", "Catch": "catch",
    "Finally": "finally", "Do": "do", "Else": "else", "Synchronized": "synchronized",
}  # fmt: skip
# nodes whose ``value`` is a user identifier
_IDENTIFIER_NODES = {
    "Name", "arg", "alias", "Attribute", "keyword", "FunctionDef", "AsyncFunctionDef",
    "ClassDef", "ExceptHandler", "Class", "Method", "Function", "ImportFrom",
}  # fmt: skip
_CONTEXT_NODES = {"Load", "Store", "Del"}


def _derive_metadata(source: IRMetadata, representation_type: str) -> IRMetadata:
    return replace(source, representation_type=representation_type)


class IRConverter:
    """Converts between different IR representations.

    Provides methods to convert:
    - AST → Token
    - AST → Graph
    - Token → Graph
    - Graph → Token (token graphs only)
    """

    @staticmethod
    def ast_to_token(ast_ir: ASTIR) -> TokenIR:
        """Convert AST IR to Token IR.

        Tokens are emitted in AST *pre-order*, which is source order for most
        constructs but not all (decorators come after a function body, dict
        keys before values, all comparison operators before their operands).

        The old version kept only leaf nodes: names of functions/classes and
        attributes were dropped, operators and ``Load``/``Store`` contexts
        became empty SYMBOL tokens, and every constant was an un-normalizable
        LITERAL.
        """
        tokens: list[Token] = []

        for node in ast_ir.root.iter_nodes():
            line, col = node.line_start, node.col_start
            ntype = node.node_type

            if ntype in _CONTEXT_NODES:
                continue
            if (
                ntype in _OP_SYMBOLS
            ):  # operator leaf; parents carry no token of their own
                tokens.append(Token("OPERATOR", _OP_SYMBOLS[ntype], line, col))
                continue

            keyword = _KEYWORD_NODES.get(ntype)
            if keyword is not None:
                tokens.append(Token("KEYWORD", keyword, line, col))
            if ntype == "Constant":
                tokens.append(
                    Token(IRConverter._constant_token_type(node), node.value, line, col)
                )
            elif node.value and ntype in _IDENTIFIER_NODES:
                tokens.append(Token("IDENTIFIER", node.value, line, col))
            elif node.value and keyword is None and not node.children:
                tokens.append(
                    Token(
                        IRConverter._ast_type_to_token_type(ntype),
                        node.value,
                        line,
                        col,
                    )
                )

        return TokenIR(
            tokens=tokens, metadata=_derive_metadata(ast_ir.metadata, "token")
        )

    @staticmethod
    def _constant_token_type(node: ASTNode) -> str:
        const_type = node.metadata.get("const_type")
        if const_type is None:  # IR deserialized from an older file
            if node.value in ("True", "False"):
                return "BOOLEAN"
            if node.value == "None":
                return "NULL"
            try:
                float(node.value)
                return "NUMBER"
            except ValueError:
                return "STRING"
        return {
            "str": "STRING", "bytes": "STRING", "int": "NUMBER", "float": "NUMBER",
            "complex": "NUMBER", "bool": "BOOLEAN", "NoneType": "NULL",
            "ellipsis": "ELLIPSIS",
        }.get(const_type, "SYMBOL")  # fmt: skip

    @staticmethod
    def _ast_type_to_token_type(ast_type: str) -> str:
        """Convert AST node type to token type."""
        type_map = {
            "Name": "IDENTIFIER",
            "Constant": "LITERAL",
            "Str": "STRING",
            "Num": "NUMBER",
            "FormattedValue": "STRING",
            "JoinedStr": "STRING",
            "Bytes": "BYTES",
            "NameConstant": "BOOLEAN",
            "Ellipsis": "ELLIPSIS",
            "keyword": "KEYWORD",
        }
        return type_map.get(ast_type, "SYMBOL")

    @staticmethod
    def ast_to_graph(ast_ir: ASTIR) -> GraphIR:
        """Convert AST IR to a containment graph.

        Node IDs end in a running counter (``Name_3_4_17``). The old
        ``Type_line_col`` IDs collided for position-less nodes (every ``Load``
        was ``Load_0_0``) and for nested nodes starting at the same column
        (``a.b.c`` and ``a.b``), so the graph failed ``validate()``.
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        counter = 0
        stack: list[tuple[ASTNode, str | None]] = [(ast_ir.root, None)]
        while stack:
            ast_node, parent_id = stack.pop()
            node_id = f"{ast_node.node_type}_{ast_node.line_start}_{ast_node.col_start}_{counter}"
            counter += 1
            nodes.append(
                GraphNode(
                    node_id=node_id,
                    node_type=ast_node.node_type.lower(),
                    label=ast_node.value or ast_node.node_type,
                    properties={
                        "ast_type": ast_node.node_type,
                        "line_start": ast_node.line_start,
                        "line_end": ast_node.line_end,
                        "col_start": ast_node.col_start,
                        "col_end": ast_node.col_end,
                    },
                )
            )
            if parent_id is not None:
                edges.append(GraphEdge(parent_id, node_id, "contains"))
            stack.extend((child, node_id) for child in reversed(ast_node.children))

        return GraphIR(
            nodes=nodes,
            edges=edges,
            metadata=_derive_metadata(ast_ir.metadata, "graph"),
        )

    @staticmethod
    def token_to_graph(token_ir: TokenIR) -> GraphIR:
        """Convert Token IR to a sequential graph (``next`` edges)."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for i, token in enumerate(token_ir.tokens):
            node_id = f"token_{i}"
            nodes.append(
                GraphNode(
                    node_id=node_id,
                    node_type="token",
                    label=token.value,
                    properties={
                        "token_type": token.token_type,
                        "line": token.line,
                        "column": token.column,
                        "normalized": token.normalized,
                    },
                )
            )
            if i > 0:
                edges.append(GraphEdge(f"token_{i - 1}", node_id, "next"))

        return GraphIR(
            nodes=nodes,
            edges=edges,
            metadata=_derive_metadata(token_ir.metadata, "graph"),
        )

    @staticmethod
    def graph_to_token(graph_ir: GraphIR) -> TokenIR:
        """Convert a token graph back to Token IR.

        Tokens keep the graph's node order. The old version re-sorted by
        (line, column), which scrambled streams that are not in source order
        (e.g. tokens that came from :meth:`ast_to_token`).

        Graphs without ``token`` nodes (call graphs, AST graphs) cannot be
        converted; a warning is issued instead of silently returning nothing.
        """
        tokens = [
            Token(
                token_type=node.properties.get("token_type", "UNKNOWN"),
                value=node.label,
                line=node.properties.get("line", 0),
                column=node.properties.get("column", 0),
                normalized=node.properties.get("normalized", ""),
            )
            for node in graph_ir.nodes
            if node.node_type == "token"
        ]
        if not tokens and graph_ir.nodes:
            warnings.warn(
                "graph_to_token: graph has no 'token' nodes (only graphs produced by "
                "token_to_graph can be converted); returning an empty TokenIR",
                stacklevel=2,
            )
        return TokenIR(
            tokens=tokens, metadata=_derive_metadata(graph_ir.metadata, "token")
        )

    @staticmethod
    def merge_graphs(graphs: list[GraphIR], namespace: bool = True) -> GraphIR:
        """Merge multiple graph IRs into one.

        Args:
            graphs: Graphs to merge (e.g. one per file).
            namespace: Prefix every ID with ``g{index}:`` so graphs stay
                separate. With ``False`` nodes with equal IDs are unified (the
                old behaviour), which is only right when equal IDs mean the same
                entity: merging two token graphs (``token_0`` ...) or two AST
                graphs that way silently dropped most of the second file.

        Raises:
            ValueError: If ``graphs`` is empty.
        """
        if not graphs:
            raise ValueError("No graphs to merge")

        all_nodes: list[GraphNode] = []
        all_edges: list[GraphEdge] = []
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()  # was rebuilt per edge: O(E²)

        for index, graph in enumerate(graphs):
            prefix = f"g{index}:" if namespace else ""
            for node in graph.nodes:
                node_id = prefix + node.node_id
                if node_id not in seen_nodes:
                    seen_nodes.add(node_id)
                    all_nodes.append(replace(node, node_id=node_id))
            for edge in graph.edges:
                key = (prefix + edge.source_id, prefix + edge.target_id, edge.edge_type)
                if key not in seen_edges:
                    seen_edges.add(key)
                    all_edges.append(replace(edge, source_id=key[0], target_id=key[1]))

        languages = {g.metadata.language for g in graphs}
        # A fixed "merged" hash made every merged graph compare equal.
        digest = hashlib.sha256(
            "\n".join(g.metadata.source_hash for g in graphs).encode()
        ).hexdigest()
        merged_metadata = IRMetadata(
            language=languages.pop() if len(languages) == 1 else "mixed",
            source_hash=digest,
            timestamp=graphs[0].metadata.timestamp,
            representation_type="graph",
            file_path=None,
            line_count=sum(g.metadata.line_count for g in graphs),
            char_count=sum(g.metadata.char_count for g in graphs),
        )
        return GraphIR(nodes=all_nodes, edges=all_edges, metadata=merged_metadata)

    # (source, target) -> converter; single source of truth for convert() and
    # get_available_conversions() (they used to keep separate hard-coded tables).
    _CONVERSIONS: ClassVar[dict[tuple[str, str], str]] = {
        ("ast", "token"): "ast_to_token",
        ("ast", "graph"): "ast_to_graph",
        ("token", "graph"): "token_to_graph",
        ("graph", "token"): "graph_to_token",
    }
    _IR_CLASSES: ClassVar[dict[str, type[BaseIR]]] = {
        "ast": ASTIR,
        "token": TokenIR,
        "graph": GraphIR,
    }

    @staticmethod
    def convert(ir: BaseIR, target_type: str) -> BaseIR:
        """Convert IR to target type ('ast', 'token', 'graph').

        Raises:
            ValueError: If conversion is not supported
            TypeError: If the IR's class contradicts its metadata
        """
        source_type = ir.metadata.representation_type
        expected_class = IRConverter._IR_CLASSES.get(source_type)
        if expected_class is not None and not isinstance(ir, expected_class):
            raise TypeError(
                f"IR metadata says '{source_type}' but object is {type(ir).__name__}"
            )

        if source_type == target_type:
            return ir

        key = (source_type, target_type)
        if key not in IRConverter._CONVERSIONS:
            raise ValueError(
                f"Conversion from {source_type} to {target_type} not supported. "
                f"Supported conversions: {list(IRConverter._CONVERSIONS)}"
            )
        converter: Callable[[BaseIR], BaseIR] = getattr(
            IRConverter, IRConverter._CONVERSIONS[key]
        )
        return converter(ir)

    @staticmethod
    def get_available_conversions(source_type: str) -> list[str]:
        """Target types reachable from ``source_type``."""
        return [dst for (src, dst) in IRConverter._CONVERSIONS if src == source_type]
