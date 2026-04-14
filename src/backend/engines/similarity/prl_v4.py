"""
PRL v4 Architecture - Graph + CodeBERT + LLM Reasoning Pipeline.

Complete pipeline:
  [Candidate] -> [Graph Builder] -> [Graph Encoder] -> [Semantic Encoder] -> [LLM Reasoner] -> [Decision]
     code_a/b      AST+CFG+DFG       GNN cosine       CodeBERT embed      Boundary check       Fusion

Implements:
1. GraphEncoder: GNN-based code graph embedding (PyTorch Geometric)
2. SemanticEncoder: CodeBERT-based semantic embedding
3. LLMReasoner: LLM-based boundary reasoning for plagiarism detection
4. PRLv4Engine: Full pipeline with weighted fusion
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base_similarity import BaseSimilarityAlgorithm


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class GraphEmbedding:
    """GNN-generated graph embedding."""
    vector: List[float]
    node_count: int = 0
    edge_count: int = 0
    cyclomatic_complexity: int = 0


@dataclass
class SemanticEmbedding:
    """CodeBERT-generated semantic embedding."""
    vector: List[float]
    model_name: str = ""
    token_count: int = 0


@dataclass
class LLMReasoningResult:
    """Result from LLM-based reasoning."""
    is_plagiarism: bool = False
    confidence: float = 0.0
    reasoning: str = ""
    evidence: List[str] = field(default_factory=list)
    plagiarism_type: str = "unknown"  # type1, type2, type3, type4, semantic


@dataclass
class PRLv4Result:
    """Complete PRL v4 pipeline result."""
    overall_score: float = 0.0
    graph_score: float = 0.0
    semantic_score: float = 0.0
    llm_score: float = 0.0
    llm_result: Optional[LLMReasoningResult] = None
    decision: str = "unknown"  # similar, dissimilar, uncertain
    confidence: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Graph Encoder (GNN-based)
# ============================================================================

class GraphEncoder:
    """
    Graph Neural Network encoder for code graphs.
    
    Converts AST+CFG+DFG combined graphs into dense embeddings
    using a simplified GraphSAGE approach.
    """
    
    def __init__(
        self,
        embedding_dim: int = 128,
        num_layers: int = 2,
        aggr: str = "mean",
    ):
        """
        Initialize graph encoder.
        
        Args:
            embedding_dim: Output embedding dimension
            num_layers: Number of message passing layers
            aggr: Aggregation method ('mean', 'sum', 'max')
        """
        self.embedding_dim = embedding_dim
        self.num_layers = num_layers
        self.aggr = aggr
        self._model: Optional[Any] = None
    
    def encode(self, graph_data: Any) -> GraphEmbedding:
        """
        Encode a combined graph into embedding.
        
        Args:
            graph_data: CombinedGraph from combined_builder
            
        Returns:
            GraphEmbedding with dense vector
        """
        if graph_data is None:
            return GraphEmbedding(vector=[0.0] * self.embedding_dim)
        
        # Extract features from graph
        node_features = self._extract_node_features(graph_data)
        edge_index = self._extract_edge_index(graph_data)
        
        if not node_features:
            return GraphEmbedding(
                vector=[0.0] * self.embedding_dim,
                node_count=0,
            )
        
        # Apply message passing
        embedding = self._message_passing(node_features, edge_index)
        
        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        # Compute complexity metrics
        cyclomatic = 1
        if hasattr(graph_data, 'cfg'):
            cyclomatic = graph_data.cfg.node_count - graph_data.cfg.edge_count + 2
        
        return GraphEmbedding(
            vector=embedding,
            node_count=len(node_features),
            edge_count=len(edge_index) // 2 if edge_index else 0,
            cyclomatic_complexity=max(1, cyclomatic),
        )
    
    def similarity(self, emb_a: GraphEmbedding, emb_b: GraphEmbedding) -> float:
        """Compute cosine similarity between two graph embeddings."""
        if not emb_a.vector or not emb_b.vector:
            return 0.0
        
        dot = sum(a * b for a, b in zip(emb_a.vector, emb_b.vector))
        norm_a = math.sqrt(sum(x * x for x in emb_a.vector))
        norm_b = math.sqrt(sum(x * x for x in emb_b.vector))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))
    
    def _extract_node_features(self, graph_data: Any) -> List[Dict[str, float]]:
        """Extract node features from combined graph."""
        features = []
        
        if not hasattr(graph_data, 'cfg') or not graph_data.cfg.nodes:
            return features
        
        # Node type one-hot encoding
        node_types = self._get_node_types(graph_data)
        
        for node_id, node in graph_data.cfg.nodes.items():
            feat = {}
            
            # Node type features
            for ntype in node_types:
                feat[f"type_{ntype}"] = 1.0 if node.node_type == ntype else 0.0
            
            # Structural features
            feat["in_degree"] = len(node.predecessors) / 10.0
            feat["out_degree"] = len(node.successors) / 10.0
            feat["is_loop_header"] = 1.0 if "Loop" in node.node_type else 0.0
            feat["is_conditional"] = 1.0 if node.node_type == "Condition" else 0.0
            feat["is_return"] = 1.0 if node.node_type == "Return" else 0.0
            
            features.append(feat)
        
        return features
    
    def _extract_edge_index(self, graph_data: Any) -> List[Tuple[int, int]]:
        """Extract edge connectivity from graph."""
        edges = []
        
        if not hasattr(graph_data, 'cfg'):
            return edges
        
        node_ids = list(graph_data.cfg.nodes.keys())
        id_to_idx = {nid: idx for idx, nid in enumerate(node_ids)}
        
        for edge in graph_data.cfg.edges:
            if edge.source in id_to_idx and edge.target in id_to_idx:
                edges.append((id_to_idx[edge.source], id_to_idx[edge.target]))
        
        return edges
    
    def _get_node_types(self, graph_data: Any) -> List[str]:
        """Get unique node types for feature encoding."""
        if not hasattr(graph_data, 'cfg'):
            return []
        return list({n.node_type for n in graph_data.cfg.nodes.values()})
    
    def _message_passing(
        self,
        node_features: List[Dict[str, float]],
        edge_index: List[Tuple[int, int]],
    ) -> List[float]:
        """
        Simplified message passing for graph embedding.
        
        Implements mean aggregation without trainable weights
        (uses handcrafted features directly).
        """
        if not node_features:
            return [0.0] * self.embedding_dim
        
        # Build adjacency
        n = len(node_features)
        all_keys = list(node_features[0].keys())
        
        # Initialize node representations
        reps = []
        for feat in node_features:
            rep = [feat.get(k, 0.0) for k in all_keys]
            reps.append(rep)
        
        # Message passing layers
        for layer in range(self.num_layers):
            new_reps = []
            for i in range(n):
                # Aggregate neighbor messages
                neighbor_msgs = []
                for src, tgt in edge_index:
                    if tgt == i:
                        neighbor_msgs.append(reps[src])
                
                if neighbor_msgs and self.aggr == "mean":
                    msg = [sum(col) / len(col) for col in zip(*neighbor_msgs)]
                elif neighbor_msgs and self.aggr == "sum":
                    msg = [sum(col) for col in zip(*neighbor_msgs)]
                elif neighbor_msgs:
                    msg = [max(col) for col in zip(*neighbor_msgs)]
                else:
                    msg = [0.0] * len(reps[i])
                
                # Update: combine self with neighbors
                alpha = 0.5  # Self-weight
                new_rep = [alpha * s + (1 - alpha) * m for s, m in zip(reps[i], msg)]
                new_reps.append(new_rep)
            
            reps = new_reps
        
        # Graph-level pooling (mean of all nodes)
        if reps:
            graph_rep = [sum(col) / len(col) for col in zip(*reps)]
        else:
            graph_rep = [0.0] * len(all_keys)
        
        # Pad or truncate to embedding_dim
        if len(graph_rep) < self.embedding_dim:
            graph_rep.extend([0.0] * (self.embedding_dim - len(graph_rep)))
        elif len(graph_rep) > self.embedding_dim:
            graph_rep = graph_rep[:self.embedding_dim]
        
        return graph_rep


# ============================================================================
# Semantic Encoder (CodeBERT-based)
# ============================================================================

class SemanticEncoder:
    """
    CodeBERT-based semantic encoder for code.
    
    Uses pre-trained CodeBERT or UniXcoder models to generate
    semantic embeddings of source code.
    """
    
    def __init__(
        self,
        model_name: str = "microsoft/codebert-base",
        device: str = "auto",
        max_length: int = 512,
    ):
        """
        Initialize semantic encoder.
        
        Args:
            model_name: HuggingFace model name
            device: 'cpu', 'cuda', or 'auto'
            max_length: Maximum token length
        """
        self.model_name = model_name
        self.max_length = max_length
        self._device = device
        self._tokenizer = None
        self._model = None
    
    def encode(self, code: str) -> SemanticEmbedding:
        """
        Encode source code into semantic embedding.
        
        Args:
            code: Source code string
            
        Returns:
            SemanticEmbedding with dense vector
        """
        if not code or not code.strip():
            return SemanticEmbedding(vector=[], token_count=0)
        
        self._ensure_loaded()
        
        if self._model is None or self._tokenizer is None:
            # Fallback: simple hash-based embedding
            return self._fallback_encode(code)
        
        import torch
        
        inputs = self._tokenizer(
            code,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
        ).to(self._device)
        
        with torch.no_grad():
            outputs = self._model(**inputs)
        
        # Mean pooling over token embeddings
        embedding = outputs.last_hidden_state.mean(dim=1).squeeze().tolist()
        
        if isinstance(embedding, float):
            embedding = [embedding]
        
        return SemanticEmbedding(
            vector=embedding,
            model_name=self.model_name,
            token_count=len(inputs['input_ids'][0]),
        )
    
    def similarity(self, emb_a: SemanticEmbedding, emb_b: SemanticEmbedding) -> float:
        """Compute cosine similarity between semantic embeddings."""
        if not emb_a.vector or not emb_b.vector:
            return 0.0
        
        dot = sum(a * b for a, b in zip(emb_a.vector, emb_b.vector))
        norm_a = math.sqrt(sum(x * x for x in emb_a.vector))
        norm_b = math.sqrt(sum(x * x for x in emb_b.vector))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))
    
    def _ensure_loaded(self):
        """Lazy load model."""
        if self._model is not None:
            return
        
        try:
            import torch
            if self._device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            
            from transformers import AutoTokenizer, AutoModel
            
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name).to(self._device)
            self._model.eval()
        except ImportError:
            self._model = None
            self._tokenizer = None
    
    def _fallback_encode(self, code: str) -> SemanticEmbedding:
        """Fallback embedding using n-gram hashing."""
        # Simple character 3-gram frequency vector
        ngram_size = 3
        freq: Dict[str, int] = {}
        
        code_lower = code.lower()
        for i in range(len(code_lower) - ngram_size + 1):
            ngram = code_lower[i:i + ngram_size]
            freq[ngram] = freq.get(ngram, 0) + 1
        
        # Normalize to unit vector
        keys = sorted(freq.keys())
        vector = [freq[k] for k in keys]
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        
        return SemanticEmbedding(
            vector=vector,
            model_name="ngram_fallback",
            token_count=len(code.split()),
        )


# ============================================================================
# LLM Reasoner
# ============================================================================

class LLMReasoner:
    """
    LLM-based boundary reasoning for plagiarism detection.
    
    When similarity scores are near the decision boundary,
    uses LLM to provide additional analysis and evidence.
    """
    
    def __init__(
        self,
        enabled: bool = False,
        model: str = "gpt-4o-mini",
        boundary_margin: float = 0.1,
        similarity_threshold: float = 0.5,
    ):
        """
        Initialize LLM reasoner.
        
        Args:
            enabled: Whether to enable LLM reasoning
            model: LLM model identifier
            boundary_margin: Margin around threshold for boundary zone
            similarity_threshold: Base similarity threshold
        """
        self.enabled = enabled
        self.model = model
        self.boundary_margin = boundary_margin
        self.similarity_threshold = similarity_threshold
        self._client = None
    
    def reason(
        self,
        code_a: str,
        code_b: str,
        graph_score: float,
        semantic_score: float,
        overall_score: float,
    ) -> LLMReasoningResult:
        """
        Perform LLM-based reasoning on code pair.
        
        Args:
            code_a: First code snippet
            code_b: Second code snippet
            graph_score: Graph similarity score
            semantic_score: Semantic similarity score
            overall_score: Overall similarity score
            
        Returns:
            LLMReasoningResult with analysis
        """
        if not self.enabled:
            return self._heuristic_reason(code_a, code_b, graph_score, semantic_score, overall_score)
        
        # Check if in boundary zone
        lower_bound = self.similarity_threshold - self.boundary_margin
        upper_bound = self.similarity_threshold + self.boundary_margin
        
        if lower_bound <= overall_score <= upper_bound:
            # Need LLM reasoning
            return self._llm_reason(code_a, code_b, graph_score, semantic_score, overall_score)
        
        # Outside boundary - use heuristic
        return self._heuristic_reason(code_a, code_b, graph_score, semantic_score, overall_score)
    
    def detect_plagiarism_type(
        self,
        code_a: str,
        code_b: str,
        evidence: Dict[str, Any],
    ) -> Tuple[str, float]:
        """
        Detect the type of plagiarism.
        
        Returns:
            (plagiarism_type, confidence)
        """
        graph_score = evidence.get("graph_score", 0.0)
        semantic_score = evidence.get("semantic_score", 0.0)
        
        # Type detection heuristics
        if graph_score > 0.9 and semantic_score > 0.9:
            return "type1_identical", 0.95
        elif graph_score > 0.8 and semantic_score < 0.6:
            return "type2_renamed", 0.80
        elif graph_score > 0.5 and semantic_score > 0.5:
            return "type3_restructured", 0.70
        elif semantic_score > 0.6 and graph_score < 0.4:
            return "type4_semantic", 0.60
        
        return "unknown", 0.5
    
    def _heuristic_reason(
        self,
        code_a: str,
        code_b: str,
        graph_score: float,
        semantic_score: float,
        overall_score: float,
    ) -> LLMReasoningResult:
        """Heuristic-based reasoning without LLM."""
        is_plagiarism = overall_score >= self.similarity_threshold
        confidence = abs(overall_score - self.similarity_threshold) * 2
        confidence = min(1.0, max(0.0, confidence))
        
        evidence = []
        if graph_score > 0.7:
            evidence.append("High structural similarity")
        if semantic_score > 0.7:
            evidence.append("High semantic similarity")
        if graph_score < 0.3:
            evidence.append("Different control flow structures")
        if semantic_score < 0.3:
            evidence.append("Different semantic content")
        
        plagi_type, plagi_conf = self.detect_plagiarism_type(
            code_a, code_b,
            {"graph_score": graph_score, "semantic_score": semantic_score}
        )
        
        reasoning = f"Overall similarity: {overall_score:.2f}, "
        reasoning += f"Graph: {graph_score:.2f}, Semantic: {semantic_score:.2f}. "
        if is_plagiarism:
            reasoning += f"Likely plagiarism ({plagi_type})."
        else:
            reasoning += "Likely independent work."
        
        return LLMReasoningResult(
            is_plagiarism=is_plagiarism,
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence,
            plagiarism_type=plagi_type,
        )
    
    def _llm_reason(
        self,
        code_a: str,
        code_b: str,
        graph_score: float,
        semantic_score: float,
        overall_score: float,
    ) -> LLMReasoningResult:
        """LLM-based reasoning (requires API access)."""
        try:
            self._ensure_client()
            if self._client is None:
                return self._heuristic_reason(code_a, code_b, graph_score, semantic_score, overall_score)
            
            prompt = self._build_prompt(code_a, code_b, graph_score, semantic_score)
            
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            return self._parse_llm_response(content, overall_score)
            
        except Exception:
            return self._heuristic_reason(code_a, code_b, graph_score, semantic_score, overall_score)
    
    def _ensure_client(self):
        """Lazy initialize OpenAI client."""
        if self._client is not None:
            return
        try:
            from openai import OpenAI
            self._client = OpenAI()
        except ImportError:
            self._client = None
    
    def _build_prompt(
        self,
        code_a: str,
        code_b: str,
        graph_score: float,
        semantic_score: float,
    ) -> str:
        """Build prompt for LLM reasoning."""
        # Truncate code if too long
        max_code_len = 2000
        code_a_trunc = code_a[:max_code_len] if len(code_a) > max_code_len else code_a
        code_b_trunc = code_b[:max_code_len] if len(code_b) > max_code_len else code_b
        
        return f"""Analyze these two code snippets for potential plagiarism.

Code A:
```python
{code_a_trunc}
```

Code B:
```python
{code_b_trunc}
```

Automated analysis results:
- Structural (graph) similarity: {graph_score:.3f}
- Semantic similarity: {semantic_score:.3f}

Please analyze:
1. Are these codes likely plagiarized or independently written?
2. What type of plagiarism (if any): Type-1 (identical), Type-2 (renamed), Type-3 (restructured), Type-4 (semantic only)
3. What evidence supports your conclusion?

Respond in JSON format:
{{"is_plagiarism": true/false, "confidence": 0.0-1.0, "type": "typeX", "evidence": ["reason1", "reason2"]}}
"""
    
    def _parse_llm_response(self, content: str, overall_score: float) -> LLMReasoningResult:
        """Parse LLM response into reasoning result."""
        try:
            # Extract JSON from response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                
                return LLMReasoningResult(
                    is_plagiarism=data.get("is_plagiarism", overall_score >= 0.5),
                    confidence=data.get("confidence", 0.5),
                    reasoning=f"LLM analysis: {data.get('type', 'unknown')}. "
                             f"Evidence: {'; '.join(data.get('evidence', []))}",
                    evidence=data.get("evidence", []),
                    plagiarism_type=data.get("type", "unknown"),
                )
        except (json.JSONDecodeError, KeyError):
            pass
        
        return LLMReasoningResult(
            is_plagiarism=overall_score >= self.similarity_threshold,
            confidence=0.5,
            reasoning="LLM response parsing failed, using heuristic fallback.",
            evidence=["LLM parsing failed"],
        )


# ============================================================================
# PRL v4 Engine - Full Pipeline
# ============================================================================

class PRLv4Engine(BaseSimilarityAlgorithm):
    """
    PRL v4 Architecture Engine.
    
    Pipeline: [Candidate] -> [Graph Builder] -> [Graph Encoder] -> 
              [Semantic Encoder] -> [LLM Reasoner] -> [Decision]
    """
    
    def __init__(
        self,
        # Graph encoder config
        graph_embedding_dim: int = 128,
        graph_layers: int = 2,
        
        # Semantic encoder config
        semantic_model: str = "microsoft/codebert-base",
        semantic_device: str = "auto",
        
        # Fusion weights
        graph_weight: float = 0.4,
        semantic_weight: float = 0.4,
        llm_weight: float = 0.2,
        
        # Decision config
        similarity_threshold: float = 0.5,
        
        # LLM config
        llm_enabled: bool = False,
        llm_model: str = "gpt-4o-mini",
        llm_boundary_margin: float = 0.1,
    ):
        """Initialize PRL v4 engine."""
        super().__init__("prl_v4")
        
        self.graph_weight = graph_weight
        self.semantic_weight = semantic_weight
        self.llm_weight = llm_weight
        self.similarity_threshold = similarity_threshold
        
        # Initialize encoders
        self.graph_encoder = GraphEncoder(
            embedding_dim=graph_embedding_dim,
            num_layers=graph_layers,
        )
        self.semantic_encoder = SemanticEncoder(
            model_name=semantic_model,
            device=semantic_device,
        )
        self.llm_reasoner = LLMReasoner(
            enabled=llm_enabled,
            model=llm_model,
            boundary_margin=llm_boundary_margin,
            similarity_threshold=similarity_threshold,
        )
    
    def get_params(self) -> Dict[str, Any]:
        """Get all configurable parameters."""
        return {
            "graph_weight": self.graph_weight,
            "semantic_weight": self.semantic_weight,
            "llm_weight": self.llm_weight,
            "similarity_threshold": self.similarity_threshold,
            "graph_embedding_dim": self.graph_encoder.embedding_dim,
            "graph_layers": self.graph_encoder.num_layers,
            "semantic_model": self.semantic_encoder.model_name,
            "llm_enabled": self.llm_reasoner.enabled,
        }
    
    def set_params(self, **params) -> "PRLv4Engine":
        """Set parameters."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two code representations using PRL v4 pipeline.
        
        Args:
            parsed_a: Dict with 'content' or 'tokens' keys
            parsed_b: Dict with 'content' or 'tokens' keys
            
        Returns:
            Similarity score in [0, 1]
        """
        code_a = self._extract_code(parsed_a)
        code_b = self._extract_code(parsed_b)
        
        if not code_a or not code_b:
            return 0.0
        
        result = self.analyze_full(code_a, code_b)
        return result.overall_score
    
    def analyze_full(self, code_a: str, code_b: str) -> PRLv4Result:
        """
        Full PRL v4 analysis with detailed results.
        
        Args:
            code_a: First code snippet
            code_b: Second code snippet
            
        Returns:
            PRLv4Result with all component scores
        """
        # Stage 1: Graph encoding
        graph_a = self._build_graph(code_a)
        graph_b = self._build_graph(code_b)
        
        emb_a = self.graph_encoder.encode(graph_a)
        emb_b = self.graph_encoder.encode(graph_b)
        graph_score = self.graph_encoder.similarity(emb_a, emb_b)
        
        # Stage 2: Semantic encoding
        sem_a = self.semantic_encoder.encode(code_a)
        sem_b = self.semantic_encoder.encode(code_b)
        semantic_score = self.semantic_encoder.similarity(sem_a, sem_b)
        
        # Stage 3: Fusion (before LLM)
        fusion_weight_total = self.graph_weight + self.semantic_weight
        if fusion_weight_total > 0:
            fused_score = (
                graph_score * self.graph_weight +
                semantic_score * self.semantic_weight
            ) / fusion_weight_total
        else:
            fused_score = 0.0
        
        # Stage 4: LLM reasoning (if needed)
        llm_result = self.llm_reasoner.reason(
            code_a, code_b, graph_score, semantic_score, fused_score
        )
        
        llm_score = 1.0 if llm_result.is_plagiarism else 0.0
        
        # Stage 5: Final decision
        total_weight = self.graph_weight + self.semantic_weight + self.llm_weight
        if total_weight > 0 and self.llm_reasoner.enabled:
            overall = (
                graph_score * self.graph_weight +
                semantic_score * self.semantic_weight +
                llm_score * self.llm_weight
            ) / total_weight
        else:
            overall = fused_score
        
        overall = max(0.0, min(1.0, overall))
        
        # Decision
        if overall >= self.similarity_threshold + 0.1:
            decision = "similar"
        elif overall <= self.similarity_threshold - 0.1:
            decision = "dissimilar"
        else:
            decision = "uncertain"
        
        confidence = abs(overall - self.similarity_threshold) * 2
        confidence = min(1.0, max(0.0, confidence))
        
        return PRLv4Result(
            overall_score=overall,
            graph_score=graph_score,
            semantic_score=semantic_score,
            llm_score=llm_score,
            llm_result=llm_result,
            decision=decision,
            confidence=confidence,
            evidence={
                "graph_embedding_dim": len(emb_a.vector),
                "semantic_model": sem_a.model_name,
                "token_count_a": sem_a.token_count,
                "token_count_b": sem_b.token_count,
            },
        )
    
    def _extract_code(self, parsed: Dict[str, Any]) -> str:
        """Extract raw code from parsed dict."""
        if "content" in parsed:
            return parsed["content"]
        if "raw" in parsed:
            return parsed["raw"]
        if "tokens" in parsed:
            return " ".join(t.get("value", "") for t in parsed["tokens"])
        return ""
    
    def _build_graph(self, code: str):
        """Build combined graph from code."""
        try:
            from src.backend.core.graph.combined_builder import (
                CFGDFGBuilder,
                CombinedGraph,
            )
            builder = CFGDFGBuilder()
            return builder.build(code)
        except Exception:
            return None