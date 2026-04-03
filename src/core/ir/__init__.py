"""
IR Module - Versioned and Immutable Contracts

This module provides versioned, immutable IR (Intermediate Representation) contracts.
All IR schemas are frozen and versioned to prevent divergence.

Responsibility: IR schema definitions, versioning, validation
"""

from typing import Dict, Any, List, Optional, Protocol
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class IRVersion(Enum):
    """IR schema versions."""
    V1 = "1.0"
    V2 = "2.0"
    V3 = "3.0"
    LATEST = "3.0"


@dataclass(frozen=True)
class IRMetadata:
    """Immutable IR metadata."""
    version: IRVersion
    language: str
    source_hash: str
    timestamp: str
    representation_type: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version.value,
            "language": self.language,
            "source_hash": self.source_hash,
            "timestamp": self.timestamp,
            "representation_type": self.representation_type,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IRMetadata':
        """Create from dictionary."""
        return cls(
            version=IRVersion(data["version"]),
            language=data["language"],
            source_hash=data["source_hash"],
            timestamp=data["timestamp"],
            representation_type=data["representation_type"],
        )


class IRNode(Protocol):
    """Protocol for IR nodes."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        ...
    
    def validate(self) -> List[str]:
        """Validate node and return errors."""
        ...


class BaseIR(ABC):
    """Base class for all IR representations."""
    
    def __init__(self, metadata: IRMetadata):
        self._metadata = metadata
    
    @property
    def metadata(self) -> IRMetadata:
        """Get IR metadata."""
        return self._metadata
    
    @property
    def version(self) -> IRVersion:
        """Get IR version."""
        return self._metadata.version
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        pass
    
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseIR':
        """Deserialize from dictionary."""
        pass
    
    @abstractmethod
    def validate(self) -> List[str]:
        """Validate IR integrity."""
        pass
    
    def save(self, path: Path) -> None:
        """Save IR to file."""
        data = {
            "metadata": self._metadata.to_dict(),
            "data": self.to_dict(),
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> 'BaseIR':
        """Load IR from file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        metadata = IRMetadata.from_dict(data["metadata"])
        return cls.from_dict(data["data"], metadata)


@dataclass
class ASTNode:
    """AST node."""
    node_type: str
    value: str
    children: List['ASTNode']
    line_start: int
    line_end: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_type": self.node_type,
            "value": self.value,
            "children": [child.to_dict() for child in self.children],
            "line_start": self.line_start,
            "line_end": self.line_end,
            "metadata": self.metadata,
        }
    
    def validate(self) -> List[str]:
        """Validate node."""
        errors = []
        
        if not self.node_type:
            errors.append("Node type cannot be empty")
        
        if self.line_start < 0:
            errors.append("Line start must be non-negative")
        
        if self.line_end < self.line_start:
            errors.append("Line end must be >= line start")
        
        for child in self.children:
            errors.extend(child.validate())
        
        return errors


class ASTIR(BaseIR):
    """AST-based intermediate representation."""
    
    def __init__(self, root: ASTNode, metadata: IRMetadata):
        super().__init__(metadata)
        self._root = root
    
    @property
    def root(self) -> ASTNode:
        """Get root node."""
        return self._root
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "root": self._root.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], metadata: IRMetadata) -> 'ASTIR':
        """Deserialize from dictionary."""
        root_data = data["root"]
        root = ASTNode(
            node_type=root_data["node_type"],
            value=root_data["value"],
            children=[ASTNode(**child) for child in root_data["children"]],
            line_start=root_data["line_start"],
            line_end=root_data["line_end"],
            metadata=root_data["metadata"],
        )
        return cls(root, metadata)
    
    def validate(self) -> List[str]:
        """Validate AST IR."""
        return self._root.validate()


@dataclass
class GraphNode:
    """Graph node."""
    node_id: str
    node_type: str
    properties: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "properties": self.properties,
        }
    
    def validate(self) -> List[str]:
        """Validate node."""
        errors = []
        
        if not self.node_id:
            errors.append("Node ID cannot be empty")
        
        if not self.node_type:
            errors.append("Node type cannot be empty")
        
        return errors


@dataclass
class GraphEdge:
    """Graph edge."""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    properties: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "properties": self.properties,
        }
    
    def validate(self) -> List[str]:
        """Validate edge."""
        errors = []
        
        if not self.edge_id:
            errors.append("Edge ID cannot be empty")
        
        if not self.source_id:
            errors.append("Source ID cannot be empty")
        
        if not self.target_id:
            errors.append("Target ID cannot be empty")
        
        if not self.edge_type:
            errors.append("Edge type cannot be empty")
        
        return errors


class GraphIR(BaseIR):
    """Graph-based intermediate representation."""
    
    def __init__(self, nodes: List[GraphNode], edges: List[GraphEdge], metadata: IRMetadata):
        super().__init__(metadata)
        self._nodes = nodes
        self._edges = edges
    
    @property
    def nodes(self) -> List[GraphNode]:
        """Get nodes."""
        return self._nodes
    
    @property
    def edges(self) -> List[GraphEdge]:
        """Get edges."""
        return self._edges
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "nodes": [node.to_dict() for node in self._nodes],
            "edges": [edge.to_dict() for edge in self._edges],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], metadata: IRMetadata) -> 'GraphIR':
        """Deserialize from dictionary."""
        nodes = [GraphNode(**node_data) for node_data in data["nodes"]]
        edges = [GraphEdge(**edge_data) for edge_data in data["edges"]]
        return cls(nodes, edges, metadata)
    
    def validate(self) -> List[str]:
        """Validate graph IR."""
        errors = []
        
        # Validate nodes
        node_ids = set()
        for node in self._nodes:
            errors.extend(node.validate())
            if node.node_id in node_ids:
                errors.append(f"Duplicate node ID: {node.node_id}")
            node_ids.add(node.node_id)
        
        # Validate edges
        for edge in self._edges:
            errors.extend(edge.validate())
            
            if edge.source_id not in node_ids:
                errors.append(f"Edge source not found: {edge.source_id}")
            
            if edge.target_id not in node_ids:
                errors.append(f"Edge target not found: {edge.target_id}")
        
        return errors


class IRRegistry:
    """Registry for IR schemas."""
    
    def __init__(self):
        self._schemas: Dict[str, type] = {}
    
    def register(self, name: str, schema_class: type) -> None:
        """Register an IR schema."""
        self._schemas[name] = schema_class
    
    def get(self, name: str) -> Optional[type]:
        """Get an IR schema by name."""
        return self._schemas.get(name)
    
    def list_schemas(self) -> List[str]:
        """List all registered schemas."""
        return list(self._schemas.keys())


# Global IR registry
registry = IRRegistry()


def get_ir_schema(name: str) -> Optional[type]:
    """Get an IR schema by name."""
    return registry.get(name)


def register_ir_schema(name: str):
    """Decorator to register an IR schema."""
    def decorator(cls):
        registry.register(name, cls)
        return cls
    return decorator