"""
Graph-based Intermediate Representation.

Provides graph-based representation of code structure and dependencies.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from src.backend.core.ir.base_ir import BaseIR, IRMetadata


@dataclass
class GraphNode:
    """Represents a node in the code graph.
    
    Attributes:
        node_id: Unique identifier for the node
        node_type: Type of node (e.g., 'function', 'class', 'variable', 'statement')
        label: Human-readable label for the node
        properties: Additional properties (e.g., line number, complexity)
    """
    node_id: str
    node_type: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph node to dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "properties": self.properties,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphNode':
        """Deserialize graph node from dictionary."""
        return cls(
            node_id=data["node_id"],
            node_type=data["node_type"],
            label=data["label"],
            properties=data.get("properties", {}),
        )
    
    def __repr__(self) -> str:
        """String representation of graph node."""
        return f"GraphNode({self.node_id}, {self.node_type}, '{self.label}')"
    
    def __hash__(self) -> int:
        """Hash based on node_id."""
        return hash(self.node_id)
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on node_id."""
        if not isinstance(other, GraphNode):
            return False
        return self.node_id == other.node_id


@dataclass
class GraphEdge:
    """Represents an edge in the code graph.
    
    Attributes:
        source_id: ID of the source node
        target_id: ID of the target node
        edge_type: Type of relationship (e.g., 'calls', 'contains', 'uses', 'defines')
        weight: Optional weight for the edge
        properties: Additional properties
    """
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph edge to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "properties": self.properties,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphEdge':
        """Deserialize graph edge from dictionary."""
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_type=data["edge_type"],
            weight=data.get("weight", 1.0),
            properties=data.get("properties", {}),
        )
    
    def __repr__(self) -> str:
        """String representation of graph edge."""
        return f"GraphEdge({self.source_id} --{self.edge_type}--> {self.target_id})"
    
    def __hash__(self) -> int:
        """Hash based on source, target, and edge type."""
        return hash((self.source_id, self.target_id, self.edge_type))
    
    def __eq__(self, other: object) -> bool:
        """Check equality based on source, target, and edge type."""
        if not isinstance(other, GraphEdge):
            return False
        return (self.source_id == other.source_id and
                self.target_id == other.target_id and
                self.edge_type == other.edge_type)


class GraphIR(BaseIR):
    """Graph-based intermediate representation.
    
    Represents code as a graph with nodes (functions, classes, variables)
    and edges (calls, contains, uses, defines).
    """
    
    def __init__(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        metadata: IRMetadata
    ):
        """Initialize Graph IR.
        
        Args:
            nodes: List of graph nodes
            edges: List of graph edges
            metadata: IR metadata
        """
        super().__init__(metadata)
        self.nodes = nodes
        self.edges = edges
        
        # Build adjacency lists for efficient traversal
        self._node_map: Dict[str, GraphNode] = {n.node_id: n for n in nodes}
        self._outgoing: Dict[str, List[GraphEdge]] = {}
        self._incoming: Dict[str, List[GraphEdge]] = {}
        
        for edge in edges:
            self._outgoing.setdefault(edge.source_id, []).append(edge)
            self._incoming.setdefault(edge.target_id, []).append(edge)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize Graph IR to dictionary."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_types": list(self.get_node_types()),
            "edge_types": list(self.get_edge_types()),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphIR':
        """Deserialize Graph IR from dictionary.
        
        Note: This creates a placeholder. Use from_source() for actual graph construction.
        """
        # Create placeholder metadata
        metadata = IRMetadata(
            language="unknown",
            source_hash="",
            timestamp="",
            representation_type="graph",
        )
        
        # Create placeholder nodes and edges
        nodes = []
        edges = []
        
        instance = cls(nodes=nodes, edges=edges, metadata=metadata)
        return instance
    
    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load Graph-specific data from dictionary."""
        self.nodes = [GraphNode.from_dict(n) for n in data["nodes"]]
        self.edges = [GraphEdge.from_dict(e) for e in data["edges"]]
        
        # Rebuild adjacency lists
        self._node_map = {n.node_id: n for n in self.nodes}
        self._outgoing = {}
        self._incoming = {}
        
        for edge in self.edges:
            self._outgoing.setdefault(edge.source_id, []).append(edge)
            self._incoming.setdefault(edge.target_id, []).append(edge)
    
    def validate(self) -> bool:
        """Validate Graph IR integrity."""
        if not self.metadata.validate():
            return False
        
        if not isinstance(self.nodes, list) or not isinstance(self.edges, list):
            return False
        
        # Check that all nodes are valid
        node_ids = set()
        for node in self.nodes:
            if not isinstance(node, GraphNode):
                return False
            if node.node_id in node_ids:
                return False  # Duplicate node ID
            node_ids.add(node.node_id)
        
        # Check that all edges reference valid nodes
        for edge in self.edges:
            if not isinstance(edge, GraphEdge):
                return False
            if edge.source_id not in node_ids:
                return False
            if edge.target_id not in node_ids:
                return False
        
        return True
    
    @classmethod
    def from_source(
        cls,
        source_code: str,
        language: str,
        file_path: Optional[str] = None
    ) -> 'GraphIR':
        """Create Graph IR from source code.
        
        Args:
            source_code: Source code to analyze
            language: Programming language
            file_path: Optional path to source file
            
        Returns:
            GraphIR instance
            
        Raises:
            ValueError: If language is not supported
        """
        # Create metadata
        metadata = cls.create_metadata(source_code, language, "graph", file_path)
        
        # Build graph from source code
        nodes, edges = cls._build_graph(source_code, language)
        
        return cls(nodes=nodes, edges=edges, metadata=metadata)
    
    @staticmethod
    def _build_graph(source_code: str, language: str) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Build graph from source code.
        
        Args:
            source_code: Source code to analyze
            language: Programming language
            
        Returns:
            Tuple of (nodes, edges)
            
        Raises:
            ValueError: If language is not supported
        """
        if language == "python":
            return GraphIR._build_python_graph(source_code)
        elif language == "java":
            return GraphIR._build_java_graph(source_code)
        elif language == "javascript":
            return GraphIR._build_javascript_graph(source_code)
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    @staticmethod
    def _build_python_graph(source_code: str) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Build graph from Python source code.
        
        Uses Python's ast module to extract structure.
        """
        try:
            import ast as python_ast
        except ImportError:
            raise ImportError("Python ast module not available")
        
        nodes = []
        edges = []
        
        try:
            tree = python_ast.parse(source_code)
        except SyntaxError:
            # Return empty graph on syntax error
            return nodes, edges
        
        # Track current context
        current_class = None
        current_function = None
        
        # Walk the AST
        for node in python_ast.walk(tree):
            if isinstance(node, python_ast.ClassDef):
                # Create class node
                class_id = f"class:{node.name}"
                nodes.append(GraphNode(
                    node_id=class_id,
                    node_type="class",
                    label=node.name,
                    properties={"line": node.lineno}
                ))
                current_class = class_id
                
            elif isinstance(node, python_ast.FunctionDef):
                # Create function node
                func_id = f"func:{node.name}"
                nodes.append(GraphNode(
                    node_id=func_id,
                    node_type="function",
                    label=node.name,
                    properties={"line": node.lineno}
                ))
                
                # If inside a class, add containment edge
                if current_class:
                    edges.append(GraphEdge(
                        source_id=current_class,
                        target_id=func_id,
                        edge_type="contains"
                    ))
                
                current_function = func_id
                
            elif isinstance(node, python_ast.Call):
                # Track function calls
                if isinstance(node.func, python_ast.Name):
                    called_name = node.func.id
                    called_id = f"func:{called_name}"
                    
                    # Create target node if it doesn't exist
                    if called_id not in {n.node_id for n in nodes}:
                        nodes.append(GraphNode(
                            node_id=called_id,
                            node_type="function",
                            label=called_name,
                            properties={"external": True}
                        ))
                    
                    # Add call edge
                    if current_function:
                        edges.append(GraphEdge(
                            source_id=current_function,
                            target_id=called_id,
                            edge_type="calls"
                        ))
        
        return nodes, edges
    
    @staticmethod
    def _build_java_graph(source_code: str) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Build graph from Java source code.
        
        Uses simple pattern matching.
        """
        import re
        
        nodes = []
        edges = []
        
        lines = source_code.split('\n')
        current_class = None
        current_method = None
        
        for line_num, line in enumerate(lines, 1):
            # Match class definitions
            class_match = re.search(r'class\s+(\w+)', line)
            if class_match:
                class_name = class_match.group(1)
                class_id = f"class:{class_name}"
                nodes.append(GraphNode(
                    node_id=class_id,
                    node_type="class",
                    label=class_name,
                    properties={"line": line_num}
                ))
                current_class = class_id
            
            # Match method definitions
            method_match = re.search(r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(', line)
            if method_match:
                method_name = method_match.group(1)
                method_id = f"method:{method_name}"
                nodes.append(GraphNode(
                    node_id=method_id,
                    node_type="method",
                    label=method_name,
                    properties={"line": line_num}
                ))
                
                # If inside a class, add containment edge
                if current_class:
                    edges.append(GraphEdge(
                        source_id=current_class,
                        target_id=method_id,
                        edge_type="contains"
                    ))
                
                current_method = method_id
            
            # Match method calls
            call_match = re.search(r'(\w+)\s*\(', line)
            if call_match and current_method:
                called_name = call_match.group(1)
                # Skip keywords
                if called_name not in ['if', 'for', 'while', 'switch', 'catch']:
                    called_id = f"method:{called_name}"
                    
                    # Create target node if it doesn't exist
                    if called_id not in {n.node_id for n in nodes}:
                        nodes.append(GraphNode(
                            node_id=called_id,
                            node_type="method",
                            label=called_name,
                            properties={"external": True}
                        ))
                    
                    # Add call edge
                    edges.append(GraphEdge(
                        source_id=current_method,
                        target_id=called_id,
                        edge_type="calls"
                    ))
        
        return nodes, edges
    
    @staticmethod
    def _build_javascript_graph(source_code: str) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Build graph from JavaScript source code.
        
        Uses simple pattern matching.
        """
        import re
        
        nodes = []
        edges = []
        
        lines = source_code.split('\n')
        current_class = None
        current_function = None
        
        for line_num, line in enumerate(lines, 1):
            # Match class definitions
            class_match = re.search(r'class\s+(\w+)', line)
            if class_match:
                class_name = class_match.group(1)
                class_id = f"class:{class_name}"
                nodes.append(GraphNode(
                    node_id=class_id,
                    node_type="class",
                    label=class_name,
                    properties={"line": line_num}
                ))
                current_class = class_id
            
            # Match function definitions
            func_match = re.search(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))', line)
            if func_match:
                func_name = func_match.group(1) or func_match.group(2)
                func_id = f"func:{func_name}"
                nodes.append(GraphNode(
                    node_id=func_id,
                    node_type="function",
                    label=func_name,
                    properties={"line": line_num}
                ))
                
                # If inside a class, add containment edge
                if current_class:
                    edges.append(GraphEdge(
                        source_id=current_class,
                        target_id=func_id,
                        edge_type="contains"
                    ))
                
                current_function = func_id
            
            # Match function calls
            call_match = re.search(r'(\w+)\s*\(', line)
            if call_match and current_function:
                called_name = call_match.group(1)
                # Skip keywords
                if called_name not in ['if', 'for', 'while', 'switch', 'catch', 'function', 'class']:
                    called_id = f"func:{called_name}"
                    
                    # Create target node if it doesn't exist
                    if called_id not in {n.node_id for n in nodes}:
                        nodes.append(GraphNode(
                            node_id=called_id,
                            node_type="function",
                            label=called_name,
                            properties={"external": True}
                        ))
                    
                    # Add call edge
                    edges.append(GraphEdge(
                        source_id=current_function,
                        target_id=called_id,
                        edge_type="calls"
                    ))
        
        return nodes, edges
    
    def get_node_by_id(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID."""
        return self._node_map.get(node_id)
    
    def get_outgoing_edges(self, node_id: str) -> List[GraphEdge]:
        """Get all outgoing edges from a node."""
        return self._outgoing.get(node_id, [])
    
    def get_incoming_edges(self, node_id: str) -> List[GraphEdge]:
        """Get all incoming edges to a node."""
        return self._incoming.get(node_id, [])
    
    def get_node_types(self) -> Set[str]:
        """Get unique node types."""
        return {node.node_type for node in self.nodes}
    
    def get_edge_types(self) -> Set[str]:
        """Get unique edge types."""
        return {edge.edge_type for edge in self.edges}
    
    def get_nodes_by_type(self, node_type: str) -> List[GraphNode]:
        """Get all nodes of a specific type."""
        return [node for node in self.nodes if node.node_type == node_type]
    
    def get_edges_by_type(self, edge_type: str) -> List[GraphEdge]:
        """Get all edges of a specific type."""
        return [edge for edge in self.edges if edge.edge_type == edge_type]
    
    def get_functions(self) -> List[GraphNode]:
        """Get all function/method nodes."""
        return self.get_nodes_by_type("function") + self.get_nodes_by_type("method")
    
    def get_classes(self) -> List[GraphNode]:
        """Get all class nodes."""
        return self.get_nodes_by_type("class")
    
    def get_call_graph(self) -> 'GraphIR':
        """Extract call graph (only call edges).
        
        Returns:
            New GraphIR containing only call relationships
        """
        call_edges = self.get_edges_by_type("calls")
        call_node_ids = set()
        
        for edge in call_edges:
            call_node_ids.add(edge.source_id)
            call_node_ids.add(edge.target_id)
        
        call_nodes = [n for n in self.nodes if n.node_id in call_node_ids]
        
        return GraphIR(nodes=call_nodes, edges=call_edges, metadata=self.metadata)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the graph."""
        node_type_counts = {}
        for node in self.nodes:
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
        
        edge_type_counts = {}
        for edge in self.edges:
            edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1
        
        # Calculate average degree
        total_degree = 0
        for node in self.nodes:
            out_degree = len(self.get_outgoing_edges(node.node_id))
            in_degree = len(self.get_incoming_edges(node.node_id))
            total_degree += out_degree + in_degree
        
        avg_degree = total_degree / len(self.nodes) if self.nodes else 0
        
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "unique_node_types": len(self.get_node_types()),
            "unique_edge_types": len(self.get_edge_types()),
            "average_degree": round(avg_degree, 2),
        }
    
    def __repr__(self) -> str:
        """String representation of Graph IR."""
        stats = self.get_statistics()
        return f"GraphIR(nodes={stats['node_count']}, edges={stats['edge_count']}, language={self.metadata.language})"
    
    def __len__(self) -> int:
        """Get number of nodes."""
        return len(self.nodes)