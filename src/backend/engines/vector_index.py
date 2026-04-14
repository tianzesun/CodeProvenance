"""
FAISS Vector Database Layer for fast semantic retrieval.

Turns the system from O(n²) pairwise comparison into O(log N) retrieval.
Combined with hybrid reranking for maximum accuracy + speed.
"""
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from pathlib import Path

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class CodeVectorIndex:
    """
    FAISS-based vector index for fast code similarity retrieval.
    
    Architecture:
    1. Fast approximate nearest neighbor search with FAISS
    2. Hybrid feature vectors combining AST/GST/Token signals
    3. Reranking layer for final precision
    """
    
    # Feature vector dimensions
    DIM = 128
    
    def __init__(self, index_path: Optional[str] = None):
        self.index = None
        self.id_map: List[str] = []  # Maps FAISS internal ID to file/submission ID
        self._metadata: Dict[str, Dict[str, Any]] = {}
        
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is required for vector indexing")
        
        if index_path and Path(index_path).exists():
            self.load(index_path)
        else:
            # Initialize with IVF index for large datasets
            quantizer = faiss.IndexFlatL2(self.DIM)
            self.index = faiss.IndexIVFFlat(quantizer, self.DIM, 100)  # 100 clusters
    
    def embed(self, code: str, engine_scores: Optional[Dict[str, float]] = None) -> np.ndarray:
        """
        Convert code into 128-dimensional feature vector.
        
        Combines:
        - AST subtree fingerprint histogram
        - GST match signature
        - Token k-gram features
        - Structural statistics
        """
        if engine_scores is None:
            # If no precomputed scores, compute basic features
            from src.backend.engines.similarity.ast_similarity import ASTSimilarity
            from src.backend.engines.similarity.token_similarity import TokenSimilarity
            
            ast_engine = ASTSimilarity()
            token_engine = TokenSimilarity()
            
            features = ast_engine.extract_features({"raw": code})
            tokens = token_engine._extract_tokens({"raw": code})
            
            # Build feature vector
            vec = np.zeros(self.DIM, dtype=np.float32)
            
            # Structural features (first 32 dimensions)
            vec[0] = features.get("node_count", 0) / 1000.0
            vec[1] = features.get("function_count", 0) / 50.0
            vec[2] = features.get("branch_count", 0) / 50.0
            vec[3] = features.get("loop_count", 0) / 50.0
            
            # AST fingerprint hash projection (dimensions 32-96)
            if "subtree_hashes" in features:
                for i, h in enumerate(list(features["subtree_hashes"])[:64]):
                    vec[32 + i] = h % 1000 / 1000.0
            
            # Token k-gram features (dimensions 96-128)
            for i, token in enumerate(tokens[:32]):
                vec[96 + i] = hash(token) % 1000 / 1000.0
            
            return vec
        
        # Use precomputed engine scores for faster embedding
        vec = np.zeros(self.DIM, dtype=np.float32)
        vec[0] = engine_scores.get("ast", 0.0)
        vec[1] = engine_scores.get("gst", 0.0)
        vec[2] = engine_scores.get("token", 0.0)
        vec[3] = engine_scores.get("semantic", 0.0)
        vec[4] = engine_scores.get("cfg", 0.0)
        
        return vec
    
    def train(self, vectors: np.ndarray) -> None:
        """Train the FAISS index on a dataset of vectors."""
        if not self.index.is_trained:
            self.index.train(vectors.astype(np.float32))
    
    def add(self, submission_id: str, code: str, engine_scores: Optional[Dict[str, float]] = None) -> None:
        """Add a submission to the index."""
        vec = self.embed(code, engine_scores)
        
        if not self.index.is_trained:
            # Train on first 1000 entries
            if len(self.id_map) >= 1000:
                all_vecs = np.array([self.embed(c) for c in self._metadata.values()])
                self.train(all_vecs)
        
        self.index.add(vec.reshape(1, -1).astype(np.float32))
        self.id_map.append(submission_id)
        self._metadata[submission_id] = {"code": code, "scores": engine_scores}
    
    def query(self, code: str, k: int = 50) -> List[Tuple[str, float]]:
        """
        Fast approximate similarity search.
        
        Returns top-k candidates with raw FAISS distance scores.
        These should be reranked with full hybrid scoring for final precision.
        """
        vec = self.embed(code)
        
        if not self.index.is_trained or len(self.id_map) < 100:
            # Fallback to exact search for small datasets
            return self._exact_search(vec, k)
        
        distances, indices = self.index.search(vec.reshape(1, -1).astype(np.float32), k)
        
        candidates = []
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(self.id_map):
                # Convert L2 distance to similarity score [0, 1]
                similarity = 1.0 / (1.0 + dist)
                candidates.append((self.id_map[idx], similarity))
        
        return candidates
    
    def _exact_search(self, query_vec: np.ndarray, k: int) -> List[Tuple[str, float]]:
        """Exact L2 search for small datasets."""
        candidates = []
        for sid, metadata in self._metadata.items():
            vec = self.embed(metadata["code"], metadata.get("scores"))
            dist = np.linalg.norm(query_vec - vec)
            similarity = 1.0 / (1.0 + dist)
            candidates.append((sid, similarity))
        
        return sorted(candidates, key=lambda x: x[1], reverse=True)[:k]
    
    def save(self, path: str) -> None:
        """Save index and metadata to disk."""
        faiss.write_index(self.index, f"{path}.faiss")
        np.savez(f"{path}.meta", id_map=self.id_map, metadata=self._metadata)
    
    def load(self, path: str) -> None:
        """Load index and metadata from disk."""
        self.index = faiss.read_index(f"{path}.faiss")
        data = np.load(f"{path}.meta.npz", allow_pickle=True)
        self.id_map = data["id_map"].tolist()
        self._metadata = data["metadata"].item()


class VectorSearchPipeline:
    """
    Full vector search pipeline with hybrid reranking.
    
    Architecture:
    1. FAISS fast candidate retrieval (top 50)
    2. Hybrid AST/GST/Token reranking
    3. Explainable report generation
    """
    
    def __init__(self, index_path: Optional[str] = None):
        self.vector_index = CodeVectorIndex(index_path)
        
        # Load full scoring engines for reranking
        from src.backend.engines.similarity.base_similarity import SimilarityEngine, register_builtin_algorithms
        self.scorer = SimilarityEngine()
        register_builtin_algorithms(self.scorer)
    
    def search(self, code: str, k: int = 10, rerank: bool = True) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Full search pipeline: fast retrieval + precise reranking.
        
        Returns: list of (submission_id, final_score, engine_scores)
        """
        # Step 1: Fast FAISS retrieval
        candidates = self.vector_index.query(code, k=50)
        
        if not rerank:
            return [(sid, score, {}) for sid, score in candidates[:k]]
        
        # Step 2: Hybrid reranking of top candidates
        results = []
        query_parsed = {"raw": code}
        
        for sid, approx_score in candidates:
            candidate_code = self.vector_index._metadata[sid]["code"]
            candidate_parsed = {"raw": candidate_code}
            
            # Full precise scoring
            score_result = self.scorer.compare(query_parsed, candidate_parsed)
            final_score = score_result["overall_score"]
            
            results.append((sid, final_score, score_result))
        
        # Step 3: Sort by final score
        return sorted(results, key=lambda x: x[1], reverse=True)[:k]
