"""
AST-based Intermediate Representation.

Provides tree-based representation of code structure using Abstract Syntax Trees.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from src.backend.core.ir.base_ir import BaseIR, IRMetadata


@dataclass
class ASTNode:
    """Represents a node in the Abstract Syntax Tree.
    
    Attributes:
        node_type: Type of AST node (e.g., 'FunctionDef', 'If', 'For')
        value: String value of the node (e.g., function name, operator)
        children: List of child AST nodes
        line_start: Starting line number in source (1-indexed)
        line_end: Ending line number in source (1-indexed)
        col_start: Starting column number (0-indexed)
        col_end: Ending column number (0-indexed)
        metadata: Additional metadata about the node
    """
    node_type: str
    value: str
    children: List['ASTNode'] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    col_start: int = 0
    col_end: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize AST node to dictionary."""
        return {
            "node_type": self.node_type,
            "value": self.value,
            "children": [child.to_dict() for child in self.children],
            "line_start": self.line_start,
            "line_end": self.line_end,
            "col_start": self.col_start,
            "col_end": self.col_end,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ASTNode':
        """Deserialize AST node from dictionary."""
        children = [cls.from_dict(child) for child in data.get("children", [])]
        return cls(
            node_type=data["node_type"],
            value=data["value"],
            children=children,
            line_start=data.get("line_start", 0),
            line_end=data.get("line_end", 0),
            col_start=data.get("col_start", 0),
            col_end=data.get("col_end", 0),
            metadata=data.get("metadata", {}),
        )
    
    def get_all_node_types(self) -> Set[str]:
        """Get all unique node types in this subtree."""
        types = {self.node_type}
        for child in self.children:
            types.update(child.get_all_node_types())
        return types
    
    def get_depth(self) -> int:
        """Get depth of this subtree."""
        if not self.children:
            return 1
        return 1 + max(child.get_depth() for child in self.children)
    
    def get_node_count(self) -> int:
        """Get total number of nodes in this subtree."""
        count = 1
        for child in self.children:
            count += child.get_node_count()
        return count
    
    def find_nodes_by_type(self, node_type: str) -> List['ASTNode']:
        """Find all nodes of a specific type in this subtree."""
        results = []
        if self.node_type == node_type:
            results.append(self)
        for child in self.children:
            results.extend(child.find_nodes_by_type(node_type))
        return results
    
    def __repr__(self) -> str:
        """String representation of AST node."""
        if self.children:
            return f"ASTNode({self.node_type}, children={len(self.children)})"
        return f"ASTNode({self.node_type}, '{self.value}')"


class ASTIR(BaseIR):
    """AST-based intermediate representation.
    
    Represents code as a tree structure where each node represents
    a syntactic construct (function, loop, condition, etc.).
    """
    
    def __init__(self, root: ASTNode, metadata: IRMetadata):
        """Initialize AST IR.
        
        Args:
            root: Root node of the AST
            metadata: IR metadata
        """
        super().__init__(metadata)
        self.root = root
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize AST IR to dictionary."""
        return {
            "root": self.root.to_dict(),
            "node_count": self.root.get_node_count(),
            "max_depth": self.root.get_depth(),
            "node_types": list(self.root.get_all_node_types()),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ASTIR':
        """Deserialize AST IR from dictionary.
        
        Note: This creates a placeholder. Use from_source() for actual parsing.
        """
        # Create placeholder metadata
        metadata = IRMetadata(
            language="unknown",
            source_hash="",
            timestamp="",
            representation_type="ast",
        )
        
        # Create placeholder root
        root = ASTNode(node_type="Module", value="")
        
        instance = cls(root=root, metadata=metadata)
        return instance
    
    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load AST-specific data from dictionary."""
        self.root = ASTNode.from_dict(data["root"])
    
    def validate(self) -> bool:
        """Validate AST IR integrity."""
        if not self.metadata.validate():
            return False
        
        if self.root is None:
            return False
        
        # Check that root is a valid AST node
        if not isinstance(self.root, ASTNode):
            return False
        
        return True
    
    @classmethod
    def from_source(
        cls,
        source_code: str,
        language: str,
        file_path: Optional[str] = None
    ) -> 'ASTIR':
        """Create AST IR from source code.
        
        Args:
            source_code: Source code to parse
            language: Programming language
            file_path: Optional path to source file
            
        Returns:
            ASTIR instance
            
        Raises:
            ValueError: If language is not supported
        """
        # Create metadata
        metadata = cls.create_metadata(source_code, language, "ast", file_path)
        
        # Parse source code into AST
        root = cls._parse_source(source_code, language)
        
        return cls(root=root, metadata=metadata)
    
    @staticmethod
    def _parse_source(source_code: str, language: str) -> ASTNode:
        """Parse source code into AST.
        
        Args:
            source_code: Source code to parse
            language: Programming language
            
        Returns:
            Root AST node
            
        Raises:
            ValueError: If language is not supported
        """
        if language == "python":
            return ASTIR._parse_python(source_code)
        elif language == "java":
            return ASTIR._parse_java(source_code)
        elif language == "javascript":
            return ASTIR._parse_javascript(source_code)
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    @staticmethod
    def _parse_python(source_code: str) -> ASTNode:
        """Parse Python source code into AST.
        
        Uses Python's built-in ast module.
        """
        try:
            import ast as python_ast
        except ImportError:
            raise ImportError("Python ast module not available")
        
        try:
            tree = python_ast.parse(source_code)
            return ASTIR._convert_python_ast(tree)
        except SyntaxError as e:
            # Return error node
            return ASTNode(
                node_type="Error",
                value=f"SyntaxError: {str(e)}",
                metadata={"error": str(e)}
            )
    
    @staticmethod
    def _convert_python_ast(node, line_offset: int = 0) -> ASTNode:
        """Convert Python ast node to our ASTNode format."""
        import ast as python_ast
        
        # Get node type
        node_type = type(node).__name__
        
        # Get node value
        value = ""
        if isinstance(node, python_ast.Name):
            value = node.id
        elif isinstance(node, python_ast.Constant):
            value = str(node.value)
        elif isinstance(node, python_ast.Str):
            value = node.s
        elif isinstance(node, python_ast.Num):
            value = str(node.n)
        elif isinstance(node, python_ast.FunctionDef):
            value = node.name
        elif isinstance(node, python_ast.ClassDef):
            value = node.name
        elif isinstance(node, python_ast.BinOp):
            value = type(node.op).__name__
        elif isinstance(node, python_ast.BoolOp):
            value = type(node.op).__name__
        elif isinstance(node, python_ast.Compare):
            value = type(node.ops[0]).__name__ if node.ops else ""
        
        # Get line numbers
        line_start = getattr(node, 'lineno', 0) + line_offset
        line_end = getattr(node, 'end_lineno', line_start) + line_offset
        col_start = getattr(node, 'col_offset', 0)
        col_end = getattr(node, 'end_col_offset', col_start)
        
        # Convert children
        children = []
        for child in python_ast.iter_child_nodes(node):
            children.append(ASTIR._convert_python_ast(child, line_offset))
        
        return ASTNode(
            node_type=node_type,
            value=value,
            children=children,
            line_start=line_start,
            line_end=line_end,
            col_start=col_start,
            col_end=col_end,
        )
    
    @staticmethod
    def _parse_java(source_code: str) -> ASTNode:
        """Parse Java source code into AST.
        
        Uses a simple regex-based parser for now.
        """
        import re
        
        lines = source_code.split('\n')
        root = ASTNode(node_type="CompilationUnit", value="")
        
        # Simple pattern matching for Java constructs
        patterns = {
            'Class': r'^\s*(?:public|private|protected)?\s*(?:abstract)?\s*class\s+(\w+)',
            'Method': r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+\s+)*(\w+)\s*\(',
            'If': r'^\s*if\s*\(',
            'For': r'^\s*for\s*\(',
            'While': r'^\s*while\s*\(',
        }
        
        for i, line in enumerate(lines, 1):
            for node_type, pattern in patterns.items():
                match = re.search(pattern, line)
                if match:
                    value = match.group(1) if match.groups() else ""
                    child = ASTNode(
                        node_type=node_type,
                        value=value,
                        line_start=i,
                        line_end=i,
                    )
                    root.children.append(child)
                    break
        
        return root
    
    @staticmethod
    def _parse_javascript(source_code: str) -> ASTNode:
        """Parse JavaScript source code into AST.
        
        Uses a simple regex-based parser for now.
        """
        import re
        
        lines = source_code.split('\n')
        root = ASTNode(node_type="Program", value="")
        
        # Simple pattern matching for JavaScript constructs
        patterns = {
            'Function': r'^\s*(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))',
            'Class': r'^\s*class\s+(\w+)',
            'If': r'^\s*if\s*\(',
            'For': r'^\s*for\s*\(',
            'While': r'^\s*while\s*\(',
        }
        
        for i, line in enumerate(lines, 1):
            for node_type, pattern in patterns.items():
                match = re.search(pattern, line)
                if match:
                    # Get the first non-None group
                    value = ""
                    for group in match.groups():
                        if group:
                            value = group
                            break
                    
                    child = ASTNode(
                        node_type=node_type,
                        value=value,
                        line_start=i,
                        line_end=i,
                    )
                    root.children.append(child)
                    break
        
        return root
    
    def get_functions(self) -> List[ASTNode]:
        """Get all function/method definitions."""
        return self.root.find_nodes_by_type("FunctionDef") or \
               self.root.find_nodes_by_type("Method") or \
               self.root.find_nodes_by_type("Function")
    
    def get_classes(self) -> List[ASTNode]:
        """Get all class definitions."""
        return self.root.find_nodes_by_type("ClassDef") or \
               self.root.find_nodes_by_type("Class")
    
    def get_control_flow(self) -> List[ASTNode]:
        """Get all control flow statements (if, for, while)."""
        results = []
        for node_type in ["If", "For", "While", "IfStmt", "ForStmt", "WhileStmt"]:
            results.extend(self.root.find_nodes_by_type(node_type))
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the AST."""
        node_types = self.root.get_all_node_types()
        
        return {
            "total_nodes": self.root.get_node_count(),
            "max_depth": self.root.get_depth(),
            "node_type_count": len(node_types),
            "node_types": list(node_types),
            "function_count": len(self.get_functions()),
            "class_count": len(self.get_classes()),
            "control_flow_count": len(self.get_control_flow()),
        }
    
    def __repr__(self) -> str:
        """String representation of AST IR."""
        stats = self.get_statistics()
        return f"ASTIR(nodes={stats['total_nodes']}, depth={stats['max_depth']}, language={self.metadata.language})"