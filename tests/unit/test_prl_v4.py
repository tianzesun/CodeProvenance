"""
Unit tests for PRL v4 Architecture (Graph + CodeBERT + LLM).

Tests cover:
- GraphEncoder: GNN-based code graph embedding
- SemanticEncoder: CodeBERT-based semantic embedding
- LLMReasoner: Boundary reasoning
- PRLv4Engine: Full pipeline
"""

from __future__ import annotations

import pytest
from typing import Dict, Any

from src.backend.engines.similarity.prl_v4 import (
    GraphEmbedding,
    SemanticEmbedding,
    LLMReasoningResult,
    PRLv4Result,
    GraphEncoder,
    SemanticEncoder,
    LLMReasoner,
    PRLv4Engine,
)


# ============================================================================
# Graph Encoder Tests
# ============================================================================

class TestGraphEncoder:
    """Tests for GraphEncoder."""
    
    def test_creation(self):
        """Test basic encoder creation."""
        encoder = GraphEncoder(embedding_dim=128, num_layers=2)
        assert encoder.embedding_dim == 128
        assert encoder.num_layers == 2
    
    def test_encode_none_input(self):
        """Test encoding None input."""
        encoder = GraphEncoder()
        emb = encoder.encode(None)
        assert emb.vector == [0.0] * 128
    
    def test_similarity_identical(self):
        """Test similarity of identical embeddings."""
        encoder = GraphEncoder()
        emb = GraphEmbedding(vector=[0.5, 0.5, 0.5, 0.5])
        sim = encoder.similarity(emb, emb)
        assert sim == 1.0
    
    def test_similarity_orthogonal(self):
        """Test similarity of orthogonal embeddings."""
        encoder = GraphEncoder()
        emb_a = GraphEmbedding(vector=[1.0, 0.0, 0.0, 0.0])
        emb_b = GraphEmbedding(vector=[0.0, 1.0, 0.0, 0.0])
        sim = encoder.similarity(emb_a, emb_b)
        assert sim == 0.0
    
    def test_similarity_empty(self):
        """Test similarity with empty embeddings."""
        encoder = GraphEncoder()
        emb_a = GraphEmbedding(vector=[])
        emb_b = GraphEmbedding(vector=[1.0, 0.0])
        sim = encoder.similarity(emb_a, emb_b)
        assert sim == 0.0


# ============================================================================
# Semantic Encoder Tests
# ============================================================================

class TestSemanticEncoder:
    """Tests for SemanticEncoder."""
    
    def test_creation(self):
        """Test basic encoder creation."""
        encoder = SemanticEncoder(
            model_name="microsoft/codebert-base",
            max_length=512,
        )
        assert encoder.model_name == "microsoft/codebert-base"
        assert encoder.max_length == 512
    
    def test_encode_empty(self):
        """Test encoding empty code."""
        encoder = SemanticEncoder()
        emb = encoder.encode("")
        assert emb.vector == []
        assert emb.token_count == 0
    
    def test_encode_fallback(self):
        """Test fallback encoding when model not available."""
        encoder = SemanticEncoder()
        # Model not loaded, should use fallback
        code = "def foo(x): return x"
        emb = encoder.encode(code)
        # Should have ngram-based vector
        assert emb.token_count > 0
    
    def test_similarity(self):
        """Test semantic similarity computation."""
        encoder = SemanticEncoder()
        emb_a = SemanticEmbedding(vector=[0.6, 0.8])
        emb_b = SemanticEmbedding(vector=[0.6, 0.8])
        sim = encoder.similarity(emb_a, emb_b)
        assert sim == 1.0


# ============================================================================
# LLM Reasoner Tests
# ============================================================================

class TestLLMReasoner:
    """Tests for LLMReasoner."""
    
    def test_creation(self):
        """Test basic reasoner creation."""
        reasoner = LLMReasoner(
            enabled=False,
            model="gpt-4o-mini",
        )
        assert not reasoner.enabled
        assert reasoner.model == "gpt-4o-mini"
    
    def test_reason_disabled(self):
        """Test reasoning when LLM is disabled."""
        reasoner = LLMReasoner(enabled=False)
        result = reasoner.reason(
            code_a="def foo(): pass",
            code_b="def foo(): pass",
            graph_score=0.9,
            semantic_score=0.8,
            overall_score=0.85,
        )
        assert isinstance(result, LLMReasoningResult)
        assert result.is_plagiarism  # Above threshold
    
    def test_reason_below_threshold(self):
        """Test reasoning when score is below threshold."""
        reasoner = LLMReasoner(enabled=False, similarity_threshold=0.5)
        result = reasoner.reason(
            code_a="def foo(): pass",
            code_b="def bar(): x = 1",
            graph_score=0.2,
            semantic_score=0.1,
            overall_score=0.15,
        )
        assert not result.is_plagiarism
    
    def test_detect_plagiarism_type(self):
        """Test plagiarism type detection."""
        reasoner = LLMReasoner()
        
        # Type-1: Identical
        plagi_type, conf = reasoner.detect_plagiarism_type(
            "def foo(): return x",
            "def foo(): return x",
            {"graph_score": 0.95, "semantic_score": 0.95},
        )
        assert plagi_type == "type1_identical"
        
        # Type-2: Renamed
        plagi_type, conf = reasoner.detect_plagiarism_type(
            "def foo(x): return x",
            "def bar(y): return y",
            {"graph_score": 0.85, "semantic_score": 0.4},
        )
        assert plagi_type == "type2_renamed"
        
        # Type-3: Restructured
        plagi_type, conf = reasoner.detect_plagiarism_type(
            "def foo(): if True: return 1",
            "def foo(): x = 1; return x",
            {"graph_score": 0.6, "semantic_score": 0.7},
        )
        assert plagi_type == "type3_restructured"
        
        # Type-4: Semantic only
        plagi_type, conf = reasoner.detect_plagiarism_type(
            "for i in range(n): pass",
            "while i < n: i += 1",
            {"graph_score": 0.2, "semantic_score": 0.7},
        )
        assert plagi_type == "type4_semantic"
    
    def test_boundary_zone(self):
        """Test boundary zone detection."""
        reasoner = LLMReasoner(
            enabled=False,
            similarity_threshold=0.5,
            boundary_margin=0.1,
        )
        
        # Score in boundary zone (0.4 - 0.6)
        result = reasoner.reason(
            code_a="def foo(): pass",
            code_b="def bar(): pass",
            graph_score=0.5,
            semantic_score=0.5,
            overall_score=0.5,  # Exactly at threshold
        )
        assert isinstance(result, LLMReasoningResult)


# ============================================================================
# PRL v4 Engine Tests
# ============================================================================

class TestPRLv4Engine:
    """Tests for PRLv4Engine."""
    
    def test_creation(self):
        """Test basic engine creation."""
        engine = PRLv4Engine(
            graph_weight=0.4,
            semantic_weight=0.4,
            llm_weight=0.2,
        )
        assert engine.graph_weight == 0.4
        assert engine.semantic_weight == 0.4
    
    def test_get_params(self):
        """Test parameter retrieval."""
        engine = PRLv4Engine()
        params = engine.get_params()
        assert "graph_weight" in params
        assert "semantic_weight" in params
        assert "similarity_threshold" in params
    
    def test_set_params(self):
        """Test parameter setting."""
        engine = PRLv4Engine()
        engine.set_params(graph_weight=0.5)
        assert engine.graph_weight == 0.5
    
    def test_compare_empty(self):
        """Test comparing empty inputs."""
        engine = PRLv4Engine()
        score = engine.compare({}, {})
        assert score == 0.0
    
    @pytest.mark.skip(reason="Requires HuggingFace model access")
    def test_compare_tokens(self):
        """Test comparing token-based input."""
        engine = PRLv4Engine()
        parsed_a = {
            "tokens": [
                {"type": "KEYWORD", "value": "def"},
                {"type": "NAME", "value": "foo"},
                {"type": "NAME", "value": "x"},
                {"type": "KEYWORD", "value": "return"},
                {"type": "NAME", "value": "x"},
            ]
        }
        parsed_b = {
            "tokens": [
                {"type": "KEYWORD", "value": "def"},
                {"type": "NAME", "value": "foo"},
                {"type": "NAME", "value": "y"},
                {"type": "KEYWORD", "value": "return"},
                {"type": "NAME", "value": "y"},
            ]
        }
        score = engine.compare(parsed_a, parsed_b)
        assert 0.0 <= score <= 1.0
    
    def test_compare_content(self):
        """Test comparing content-based input."""
        engine = PRLv4Engine()
        parsed_a = {"content": "def foo(x): return x"}
        parsed_b = {"content": "def foo(x): return x"}
        score = engine.compare(parsed_a, parsed_b)
        assert 0.0 <= score <= 1.0
    
    def test_analyze_full(self):
        """Test full analysis pipeline."""
        engine = PRLv4Engine(llm_enabled=False)
        code_a = "def add(a, b): return a + b"
        code_b = "def add(x, y): return x + y"
        
        result = engine.analyze_full(code_a, code_b)
        assert isinstance(result, PRLv4Result)
        assert 0.0 <= result.overall_score <= 1.0
        assert 0.0 <= result.graph_score <= 1.0
        assert 0.0 <= result.semantic_score <= 1.0
        assert result.decision in ["similar", "dissimilar", "uncertain"]
    
    def test_analyze_different_codes(self):
        """Test analysis of very different codes."""
        engine = PRLv4Engine()
        code_a = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        code_b = """
class Calculator:
    def __init__(self):
        self.result = 0
    def add(self, x):
        self.result += x
"""
        result = engine.analyze_full(code_a, code_b)
        assert 0.0 <= result.overall_score <= 1.0


# ============================================================================
# Data Structure Tests
# ============================================================================

class TestDataStructures:
    """Tests for data structures."""
    
    def test_graph_embedding(self):
        """Test GraphEmbedding creation."""
        emb = GraphEmbedding(
            vector=[0.1, 0.2, 0.3],
            node_count=5,
            edge_count=4,
            cyclomatic_complexity=2,
        )
        assert len(emb.vector) == 3
        assert emb.node_count == 5
    
    def test_semantic_embedding(self):
        """Test SemanticEmbedding creation."""
        emb = SemanticEmbedding(
            vector=[0.5, 0.5],
            model_name="codebert",
            token_count=10,
        )
        assert emb.model_name == "codebert"
        assert emb.token_count == 10
    
    def test_llm_result(self):
        """Test LLMReasoningResult creation."""
        result = LLMReasoningResult(
            is_plagiarism=True,
            confidence=0.85,
            reasoning="High similarity detected",
            evidence=["Same structure", "Similar variables"],
            plagiarism_type="type2_renamed",
        )
        assert result.is_plagiarism
        assert result.confidence == 0.85
        assert len(result.evidence) == 2
    
    def test_prlv4_result(self):
        """Test PRLv4Result creation."""
        result = PRLv4Result(
            overall_score=0.75,
            graph_score=0.7,
            semantic_score=0.8,
            llm_score=1.0,
            decision="similar",
            confidence=0.5,
        )
        assert result.overall_score == 0.75
        assert result.decision == "similar"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])