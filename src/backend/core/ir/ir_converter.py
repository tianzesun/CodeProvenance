"""
IR Converter.

Provides conversion utilities between different intermediate representations.
"""

from typing import Any, Dict, List, Optional, Set
from src.backend.core.ir.base_ir import BaseIR, IRMetadata
from src.backend.core.ir.ast_ir import ASTIR, ASTNode
from src.backend.core.ir.token_ir import TokenIR, Token
from src.backend.core.ir.graph_ir import GraphIR, GraphNode, GraphEdge


class IRConverter:
    """Converts between different IR representations.
    
    Provides methods to convert:
    - AST → Token
    - AST → Graph
    - Token → Graph
    - And reverse conversions where possible
    """
    
    @staticmethod
    def ast_to_token(ast_ir: ASTIR) -> TokenIR:
        """Convert AST IR to Token IR.
        
        Extracts tokens from AST by traversing all leaf nodes.
        
        Args:
            ast_ir: AST-based IR
            
        Returns:
            Token-based IR
        """
        tokens = []
        
        def extract_tokens(node: ASTNode) -> None:
            """Recursively extract tokens from AST nodes."""
            # If node has no children, it's a leaf node (token)
            if not node.children:
                token_type = IRConverter._ast_type_to_token_type(node.node_type)
                tokens.append(Token(
                    token_type=token_type,
                    value=node.value,
                    line=node.line_start,
                    column=node.col_start,
                ))
            else:
                # Recursively process children
                for child in node.children:
                    extract_tokens(child)
        
        # Extract tokens from root
        extract_tokens(ast_ir.root)
        
        # Create new metadata for token IR
        token_metadata = IRMetadata(
            language=ast_ir.metadata.language,
            source_hash=ast_ir.metadata.source_hash,
            timestamp=ast_ir.metadata.timestamp,
            representation_type="token",
            file_path=ast_ir.metadata.file_path,
            line_count=ast_ir.metadata.line_count,
            char_count=ast_ir.metadata.char_count,
        )
        
        return TokenIR(tokens=tokens, metadata=token_metadata)
    
    @staticmethod
    def _ast_type_to_token_type(ast_type: str) -> str:
        """Convert AST node type to token type.
        
        Args:
            ast_type: AST node type
            
        Returns:
            Token type
        """
        # Map common AST types to token types
        type_map = {
            'Name': 'IDENTIFIER',
            'Constant': 'LITERAL',
            'Str': 'STRING',
            'Num': 'NUMBER',
            'FormattedValue': 'STRING',
            'JoinedStr': 'STRING',
            'Bytes': 'BYTES',
            'NameConstant': 'BOOLEAN',
            'Ellipsis': 'ELLIPSIS',
            'keyword': 'KEYWORD',
        }
        
        return type_map.get(ast_type, 'SYMBOL')
    
    @staticmethod
    def ast_to_graph(ast_ir: ASTIR) -> GraphIR:
        """Convert AST IR to Graph IR.
        
        Creates a containment graph from AST structure.
        
        Args:
            ast_ir: AST-based IR
            
        Returns:
            Graph-based IR
        """
        nodes = []
        edges = []
        
        def process_node(ast_node: ASTNode, parent_id: Optional[str] = None) -> str:
            """Process AST node and add to graph.
            
            Args:
                ast_node: AST node to process
                parent_id: ID of parent node (for containment edges)
                
            Returns:
                ID of created graph node
            """
            # Create graph node
            node_id = f"{ast_node.node_type}_{ast_node.line_start}_{ast_node.col_start}"
            graph_node = GraphNode(
                node_id=node_id,
                node_type=ast_node.node_type.lower(),
                label=ast_node.value or ast_node.node_type,
                properties={
                    "line_start": ast_node.line_start,
                    "line_end": ast_node.line_end,
                    "col_start": ast_node.col_start,
                    "col_end": ast_node.col_end,
                }
            )
            nodes.append(graph_node)
            
            # Add containment edge from parent
            if parent_id:
                edges.append(GraphEdge(
                    source_id=parent_id,
                    target_id=node_id,
                    edge_type="contains"
                ))
            
            # Process children
            for child in ast_node.children:
                process_node(child, node_id)
            
            return node_id
        
        # Process root
        process_node(ast_ir.root)
        
        # Create new metadata for graph IR
        graph_metadata = IRMetadata(
            language=ast_ir.metadata.language,
            source_hash=ast_ir.metadata.source_hash,
            timestamp=ast_ir.metadata.timestamp,
            representation_type="graph",
            file_path=ast_ir.metadata.file_path,
            line_count=ast_ir.metadata.line_count,
            char_count=ast_ir.metadata.char_count,
        )
        
        return GraphIR(nodes=nodes, edges=edges, metadata=graph_metadata)
    
    @staticmethod
    def token_to_graph(token_ir: TokenIR) -> GraphIR:
        """Convert Token IR to Graph IR.
        
        Creates a sequential graph from token stream.
        
        Args:
            token_ir: Token-based IR
            
        Returns:
            Graph-based IR
        """
        nodes = []
        edges = []
        
        # Create a node for each token
        for i, token in enumerate(token_ir.tokens):
            node_id = f"token_{i}"
            graph_node = GraphNode(
                node_id=node_id,
                node_type="token",
                label=token.value,
                properties={
                    "token_type": token.token_type,
                    "line": token.line,
                    "column": token.column,
                    "normalized": token.normalized,
                }
            )
            nodes.append(graph_node)
            
            # Add sequential edge from previous token
            if i > 0:
                edges.append(GraphEdge(
                    source_id=f"token_{i-1}",
                    target_id=node_id,
                    edge_type="next"
                ))
        
        # Create new metadata for graph IR
        graph_metadata = IRMetadata(
            language=token_ir.metadata.language,
            source_hash=token_ir.metadata.source_hash,
            timestamp=token_ir.metadata.timestamp,
            representation_type="graph",
            file_path=token_ir.metadata.file_path,
            line_count=token_ir.metadata.line_count,
            char_count=token_ir.metadata.char_count,
        )
        
        return GraphIR(nodes=nodes, edges=edges, metadata=graph_metadata)
    
    @staticmethod
    def graph_to_token(graph_ir: GraphIR) -> TokenIR:
        """Convert Graph IR to Token IR.
        
        Extracts tokens from graph nodes.
        
        Args:
            graph_ir: Graph-based IR
            
        Returns:
            Token-based IR
        """
        tokens = []
        
        # Extract tokens from graph nodes
        for node in graph_ir.nodes:
            if node.node_type == "token":
                # Reconstruct token from node properties
                token = Token(
                    token_type=node.properties.get("token_type", "UNKNOWN"),
                    value=node.label,
                    line=node.properties.get("line", 0),
                    column=node.properties.get("column", 0),
                    normalized=node.properties.get("normalized", ""),
                )
                tokens.append(token)
        
        # Sort tokens by line and column
        tokens.sort(key=lambda t: (t.line, t.column))
        
        # Create new metadata for token IR
        token_metadata = IRMetadata(
            language=graph_ir.metadata.language,
            source_hash=graph_ir.metadata.source_hash,
            timestamp=graph_ir.metadata.timestamp,
            representation_type="token",
            file_path=graph_ir.metadata.file_path,
            line_count=graph_ir.metadata.line_count,
            char_count=graph_ir.metadata.char_count,
        )
        
        return TokenIR(tokens=tokens, metadata=token_metadata)
    
    @staticmethod
    def merge_graphs(graphs: List[GraphIR]) -> GraphIR:
        """Merge multiple graph IRs into one.
        
        Useful for combining graphs from multiple files.
        
        Args:
            graphs: List of graph IRs to merge
            
        Returns:
            Merged graph IR
        """
        if not graphs:
            raise ValueError("No graphs to merge")
        
        all_nodes = []
        all_edges = []
        
        # Track seen node IDs to avoid duplicates
        seen_node_ids: Set[str] = set()
        
        for graph in graphs:
            # Add nodes (skip duplicates)
            for node in graph.nodes:
                if node.node_id not in seen_node_ids:
                    all_nodes.append(node)
                    seen_node_ids.add(node.node_id)
            
            # Add edges (skip duplicates)
            for edge in graph.edges:
                edge_key = (edge.source_id, edge.target_id, edge.edge_type)
                if edge_key not in {(e.source_id, e.target_id, e.edge_type) for e in all_edges}:
                    all_edges.append(edge)
        
        # Use metadata from first graph
        merged_metadata = IRMetadata(
            language=graphs[0].metadata.language,
            source_hash="merged",
            timestamp=graphs[0].metadata.timestamp,
            representation_type="graph",
            file_path=None,
            line_count=sum(g.metadata.line_count for g in graphs),
            char_count=sum(g.metadata.char_count for g in graphs),
        )
        
        return GraphIR(nodes=all_nodes, edges=all_edges, metadata=merged_metadata)
    
    @staticmethod
    def convert(ir: BaseIR, target_type: str) -> BaseIR:
        """Convert IR to target type.
        
        Args:
            ir: Source IR
            target_type: Target IR type ('ast', 'token', 'graph')
            
        Returns:
            Converted IR
            
        Raises:
            ValueError: If conversion is not supported
        """
        source_type = ir.metadata.representation_type
        
        if source_type == target_type:
            return ir
        
        # Define conversion matrix
        conversions = {
            ('ast', 'token'): IRConverter.ast_to_token,
            ('ast', 'graph'): IRConverter.ast_to_graph,
            ('token', 'graph'): IRConverter.token_to_graph,
            ('graph', 'token'): IRConverter.graph_to_token,
        }
        
        conversion_key = (source_type, target_type)
        if conversion_key not in conversions:
            raise ValueError(
                f"Conversion from {source_type} to {target_type} not supported. "
                f"Supported conversions: {list(conversions.keys())}"
            )
        
        return conversions[conversion_key](ir)
    
    @staticmethod
    def get_available_conversions(source_type: str) -> List[str]:
        """Get list of available conversions from source type.
        
        Args:
            source_type: Source IR type
            
        Returns:
            List of target types that can be converted to
        """
        conversions = {
            'ast': ['token', 'graph'],
            'token': ['graph'],
            'graph': ['token'],
        }
        
        return conversions.get(source_type, [])