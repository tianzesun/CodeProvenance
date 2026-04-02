"""
Test CodeProvenance Engine Registry.

Verifies that the versioned engine registration system works correctly.
"""

import pytest
from src.engines.similarity.codeprovenance import (
    get_engine,
    list_engines,
    is_registered,
    get_registry_info,
)


def test_engine_registry_basic():
    """Test basic registry functionality."""
    # Check that all versions are registered
    engines = list_engines()
    assert "codeprovenance:v1" in engines
    assert "codeprovenance:v2" in engines
    assert "codeprovenance:v3" in engines
    
    # Check registration status
    assert is_registered("codeprovenance:v1")
    assert is_registered("codeprovenance:v2")
    assert is_registered("codeprovenance:v3")
    assert not is_registered("codeprovenance:v99")


def test_get_engine():
    """Test getting engine instances."""
    # Get v1 engine
    engine_v1 = get_engine("codeprovenance:v1")
    assert engine_v1.version == "codeprovenance:v1"
    assert engine_v1.name == "CodeProvenance v1 (Basic Token)"
    
    # Get v2 engine
    engine_v2 = get_engine("codeprovenance:v2")
    assert engine_v2.version == "codeprovenance:v2"
    assert engine_v2.name == "CodeProvenance v2 (Token + AST)"
    
    # Get v3 engine
    engine_v3 = get_engine("codeprovenance:v3")
    assert engine_v3.version == "codeprovenance:v3"
    assert engine_v3.name == "CodeProvenance v3 (Advanced Graph)"


def test_engine_comparison():
    """Test that engines can compare code."""
    code_a = "def hello(): return 'world'"
    code_b = "def hello(): return 'world'"
    
    # Test v1
    engine_v1 = get_engine("codeprovenance:v1")
    score_v1 = engine_v1.compare(code_a, code_b)
    assert 0.0 <= score_v1 <= 1.0
    assert score_v1 == 1.0  # Identical code
    
    # Test v2
    engine_v2 = get_engine("codeprovenance:v2")
    score_v2 = engine_v2.compare(code_a, code_b)
    assert 0.0 <= score_v2 <= 1.0
    assert score_v2 == 1.0  # Identical code
    
    # Test v3
    engine_v3 = get_engine("codeprovenance:v3")
    score_v3 = engine_v3.compare(code_a, code_b)
    assert 0.0 <= score_v3 <= 1.0
    assert score_v3 == 1.0  # Identical code


def test_engine_config():
    """Test engine configuration retrieval."""
    engine_v1 = get_engine("codeprovenance:v1")
    config = engine_v1.get_config()
    
    assert config["version"] == "codeprovenance:v1"
    assert "ngram_size" in config
    assert "algorithm" in config


def test_registry_info():
    """Test registry info retrieval."""
    info = get_registry_info()
    
    assert "codeprovenance:v1" in info
    assert "codeprovenance:v2" in info
    assert "codeprovenance:v3" in info
    
    # Check v1 info
    v1_info = info["codeprovenance:v1"]
    assert v1_info["version"] == "codeprovenance:v1"
    assert v1_info["name"] == "CodeProvenance v1 (Basic Token)"


def test_invalid_engine():
    """Test that invalid engine version raises error."""
    with pytest.raises(ValueError):
        get_engine("codeprovenance:v99")


def test_engine_equality():
    """Test engine equality based on version."""
    engine_v1_a = get_engine("codeprovenance:v1")
    engine_v1_b = get_engine("codeprovenance:v1")
    engine_v2 = get_engine("codeprovenance:v2")
    
    assert engine_v1_a == engine_v1_b
    assert engine_v1_a != engine_v2
    assert hash(engine_v1_a) == hash(engine_v1_b)
    assert hash(engine_v1_a) != hash(engine_v2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])