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


class EmbeddingSimilarity(BaseSimilarityAlgorithm):
    """
    Embedding similarity algorithm that uses LLM embeddings for semantic comparison.
    
    Effective for detecting semantically similar code despite syntactic differences,
    including LLM-obfuscated code.
    """
    
    def __init__(self, model_name: str = "text-embedding-3-small"):
        """
        Initialize the embedding similarity algorithm.
        
        Args:
            model_name: Name of the embedding model to use
        """
        super().__init__("embedding")
        self.model_name = model_name
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
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set")
                self._client = OpenAI(api_key=api_key)
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
    
    def compare(self, parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> float:
        """
        Compare two parsed code representations based on embedding similarity.
        
        Args:
            parsed_a: First parsed code representation
            parsed_b: Second parsed code representation
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Get content to embed - we'll use the tokens joined by space
        tokens_a = parsed_a.get('tokens', [])
        tokens_b = parsed_b.get('tokens', [])
        
        text_a = ' '.join(tokens_a) if tokens_a else ''
        text_b = ' '.join(tokens_b) if tokens_b else ''
        
        if not text_a and not text_b:
            return 1.0
        if not text_a or not text_b:
            return 0.0
        
        # Get embeddings
        embedding_a = self._get_embedding(text_a)
        embedding_b = self._get_embedding(text_b)
        
        if embedding_a is None or embedding_b is None:
            # Fallback to token similarity if embedding fails
            from .token_similarity import TokenSimilarity
            token_sim = TokenSimilarity()
            return token_sim.compare(parsed_a, parsed_b)
        
        # Calculate cosine similarity
        try:
            # Normalize vectors
            norm_a = np.linalg.norm(embedding_a)
            norm_b = np.linalg.norm(embedding_b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = np.dot(embedding_a, embedding_b) / (norm_a * norm_b)
            
            # Ensure result is in [0, 1] range (cosine similarity is in [-1, 1])
            # We map [-1, 1] to [0, 1] by: (similarity + 1) / 2
            similarity = (similarity + 1) / 2
            
            return max(0.0, min(1.0, similarity))
        except Exception:
            # If anything goes wrong, fall back to token similarity
            from .token_similarity import TokenSimilarity
            token_sim = TokenSimilarity()
            return token_sim.compare(parsed_a, parsed_b)


# Register the parser with the factory (this would be done in __init__.py)
# from .base_similarity import ParserFactory
# ParserFactory.register_parser('embedding', EmbeddingSimilarity)
