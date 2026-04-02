"""
Test IR Layer.

Verifies that the Intermediate Representation layer works correctly.
"""

import pytest
from src.core.ir import (
    ASTIR,
    TokenIR,
    GraphIR,
    IRConverter,
    IRMetadata,
)


def test_ast_ir_creation():
    """Test AST IR creation from source code."""
    code = """
def hello():
    return "world"
"""
    ast_ir = ASTIR.from_source(code, "python")
    
    assert ast_ir.metadata.language == "python"
    assert ast_ir.metadata.representation_type == "ast"
    assert ast_ir.root is not None
    assert ast_ir.validate()


def test_token_ir_creation():
    """Test Token IR creation from source code."""
    code = """
def hello():
    return "world"
"""
    token_ir = TokenIR.from_source(code, "python")
    
    assert token_ir.metadata.language == "python"
    assert token_ir.metadata.representation_type == "token"
    assert len(token_ir.tokens) > 0
    assert token_ir.validate()


def test_graph_ir_creation():
    """Test Graph IR creation from source code."""
    code = """
def hello():
    return "world"
"""
    graph_ir = GraphIR.from_source(code, "python")
    
    assert graph_ir.metadata.language == "python"
    assert graph_ir.metadata.representation_type == "graph"
    assert len(graph_ir.nodes) > 0
    assert graph_ir.validate()


def test_ir_converter_ast_to_token():
    """Test converting AST to Token IR."""
    code = """
def hello():
    return "world"
"""
    ast_ir = ASTIR.from_source(code, "python")
    token_ir = IRConverter.ast_to_token(ast_ir)
    
    assert token_ir.metadata.language == "python"
    assert len(token_ir.tokens) > 0


def test_ir_converter_ast_to_graph():
    """Test converting AST to Graph IR."""
    code = """
def hello():
    return "world"
"""
    ast_ir = ASTIR.from_source(code, "python")
    graph_ir = IRConverter.ast_to_graph(ast_ir)
    
    assert graph_ir.metadata.language == "python"
    assert len(graph_ir.nodes) > 0


def test_ir_converter_token_to_graph():
    """Test converting Token to Graph IR."""
    code = """
def hello():
    return "world"
"""
    token_ir = TokenIR.from_source(code, "python")
    graph_ir = IRConverter.token_to_graph(token_ir)
    
    assert graph_ir.metadata.language == "python"
    assert len(graph_ir.nodes) > 0


def test_ir_metadata():
    """Test IR metadata creation."""
    code = "def hello(): return 'world'"
    metadata = IRMetadata.create_metadata(
        source_code=code,
        language="python",
        representation_type="ast"
    )
    
    assert metadata.language == "python"
    assert metadata.source_hash is not None
    assert metadata.timestamp is not None
    assert metadata.line_count == 1
    assert metadata.char_count == len(code)


def test_ast_ir_statistics():
    """Test AST IR statistics."""
    code = """
def hello():
    return "world"

def goodbye():
    return "farewell"
"""
    ast_ir = ASTIR.from_source(code, "python")
    stats = ast_ir.get_statistics()
    
    assert stats["total_nodes"] > 0
    assert stats["function_count"] == 2
    assert "FunctionDef" in stats["node_types"]


def test_token_ir_statistics():
    """Test Token IR statistics."""
    code = "def hello(): return 'world'"
    token_ir = TokenIR.from_source(code, "python")
    stats = token_ir.get_statistics()
    
    assert stats["total_tokens"] > 0
    assert stats["unique_types"] > 0


def test_graph_ir_statistics():
    """Test Graph IR statistics."""
    code = """
def hello():
    return "world"
"""
    graph_ir = GraphIR.from_source(code, "python")
    stats = graph_ir.get_statistics()
    
    assert stats["node_count"] > 0
    assert stats["unique_node_types"] > 0


def test_available_conversions():
    """Test getting available conversions."""
    conversions = IRConverter.get_available_conversions("ast")
    assert "token" in conversions
    assert "graph" in conversions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])