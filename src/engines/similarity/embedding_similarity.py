"""
Embedding-based similarity algorithm using LLM embeddings.

Compares code based on semantic similarity using vector embeddings.
"""

from typing import List, Dict, Any, Optional
from .base_similarity import BaseSimilarityAlgorithm
import numpy as np
import os
import hashlib
import pickle
from pathlib import Path
from src.domain.models import Finding, EvidenceBlock


class EmbeddingSimilarity(BaseSimilarityAlgorithm):
    """
    Embedding similarity algorithm that uses LLM embeddings for semantic comparison.
    
    Effective for detecting semantically similar code despite syntactic differences,
    including LLM-obfuscated code.
    """
    
    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the embedding similarity algorithm.
        
        Args:
            model_name: Name of the embedding model to use
        """
        super().__init__("embedding")
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.cache_dir = Path("./.embedding_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self._client = None
    
    def _get_openai_client(self):
        """
        Get or create OpenAI client.
        
        Returns:
            OpenAI client instance
        """
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = self.api_key or os.getenv("OPENAI_API_KEY")
                base_url = self.base_url or os.getenv("OPENAI_BASE_URL")

                if not api_key and not base_url:
                    raise ValueError("OPENAI_API_KEY or an embedding server URL must be configured")

                # OpenAI-compatible local servers often accept a dummy token.
                resolved_api_key = api_key or "EMPTY"
                if base_url:
                    self._client = OpenAI(api_key=resolved_api_key, base_url=base_url)
                else:
                    self._client = OpenAI(api_key=resolved_api_key)
            except ImportError:
                raise ImportError("OpenAI package not installed. Install with: pip install openai")
        return self._client
    
    def _get_cache_path(self, text: str) -> Path:
        """
        Get cache file path for a given text.
        
        Args:
            text: Text to get cache path for
            
        Returns:
            Path to cache file
        """
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{text_hash}.pkl"
    
    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Get embedding for text, using cache if available.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if failed
        """
        if not text.strip():
            return None
        
        # Check cache first
        cache_path = self._get_cache_path(text)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                # If cache is corrupted, we'll recompute
                pass
        
        # Get embedding from OpenAI
        try:
            client = self._get_openai_client()
            response = client.embeddings.create(
                input=text,
                model=self.model_name
            )
            embedding = np.array(response.data[0].embedding)
            
            # Cache the result
            try:
                with open(cache_path, 'wb') as f:
                    pickle.dump(embedding, f)
            except Exception:
                # If we can't cache, continue anyway
                pass
            
            return embedding
        except Exception as e:
            # In a production system, you'd log this error
            return None
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Finding:
        """
        Compare two parsed code representations based on embedding similarity.
        
        Returns:
            A Finding object containing scores and evidence.
        """
        raw_a = parsed_a.get('raw', '')
        raw_b = parsed_b.get('raw', '')
        
        if not raw_a and not raw_b:
            return Finding(engine=self.name, score=1.0, confidence=1.0)
        if not raw_a or not raw_b:
            return Finding(engine=self.name, score=0.0, confidence=1.0)
        
        # Get embeddings
        embedding_a = self._get_embedding(raw_a)
        embedding_b = self._get_embedding(raw_b)
        
        if embedding_a is None or embedding_b is None:
            # Fallback to simple token similarity (not implemented here for simplicity)
            return Finding(engine=self.name, score=0.5, confidence=0.3)
        
        # Calculate cosine similarity
        norm_a = np.linalg.norm(embedding_a)
        norm_b = np.linalg.norm(embedding_b)
        
        if norm_a == 0 or norm_b == 0:
            score = 0.0
        else:
            score = np.dot(embedding_a, embedding_b) / (norm_a * norm_b)
            # Map [-1, 1] to [0, 1]
            score = (score + 1) / 2
            
        score = max(0.0, min(1.0, score))
        
        # Evidence
        evidence = []
        if score > 0.85:
            evidence.append(EvidenceBlock(
                engine=self.name,
                score=score,
                confidence=0.8,
                a_snippet="Semantic vector similarity detected",
                b_snippet="Semantic vector similarity detected",
                transformation_notes=["LLM-based semantic embedding match"]
            ))

        return Finding(
            engine=self.name,
            score=score,
            confidence=0.85,
            evidence_blocks=evidence,
            methodology=f"Semantic comparison using {self.model_name} embeddings."
        )


# Register the parser with the factory (this would be done in __init__.py)
# from .base_similarity import ParserFactory
# ParserFactory.register_parser('embedding', EmbeddingSimilarity)
