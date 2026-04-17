#!/usr/bin/env python3
"""
Local Embedding Server - FastAPI server providing text embeddings via sentence-transformers.

This server mimics the OpenAI embeddings API format and can be used as a drop-in
replacement for OpenAI's embedding service in development environments.

Usage:
    python embedding_server.py

Or with uvicorn:
    uvicorn embedding_server:app --host 0.0.0.0 --port 8001 --workers 1

API Endpoints:
    GET  /health - Health check
    POST /v1/embeddings - Generate embeddings (OpenAI-compatible format)
"""

import os
import sys
import logging
import time
from typing import List, Union, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default model - can be overridden with environment variable
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

class EmbeddingRequest(BaseModel):
    """OpenAI-compatible embedding request format."""
    input: Union[str, List[str]] = Field(..., description="Text or list of texts to embed")
    model: Optional[str] = Field(DEFAULT_MODEL, description="Model to use for embeddings")
    user: Optional[str] = Field(None, description="Optional user identifier")

class EmbeddingResponse(BaseModel):
    """OpenAI-compatible embedding response format."""
    object: str = "list"
    data: List[dict]
    model: str
    usage: dict
    elapsed_seconds: float

# Global model variable
embedding_model = None

def load_model():
    """Load the sentence transformer model."""
    global embedding_model
    try:
        logger.info(f"Loading embedding model: {DEFAULT_MODEL}")
        from sentence_transformers import SentenceTransformer
        embedding_model = SentenceTransformer(DEFAULT_MODEL)
        logger.info("Model loaded successfully")
        return embedding_model
    except ImportError as e:
        logger.error(f"Failed to import sentence_transformers: {e}")
        logger.error("Please install with: pip install sentence-transformers")
        raise
    except Exception as e:
        logger.error(f"Failed to load model {DEFAULT_MODEL}: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan manager for model loading/cleanup."""
    # Load model on startup
    load_model()
    yield
    # Cleanup on shutdown (if needed)
    logger.info("Shutting down embedding server")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="Local Embedding Server",
    description="FastAPI server providing text embeddings via sentence-transformers",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model": DEFAULT_MODEL,
        "model_loaded": embedding_model is not None,
        "timestamp": time.time()
    }

@app.post("/v1/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """Generate embeddings for input text(s)."""
    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Ensure input is a list
        texts = [request.input] if isinstance(request.input, str) else request.input

        if not texts:
            raise HTTPException(status_code=400, detail="No input texts provided")

        # Log request info
        logger.info(f"Processing {len(texts)} text(s) with model {request.model}")

        # Generate embeddings
        start_time = time.time()
        vectors = embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        elapsed_seconds = time.time() - start_time

        # Estimate token usage (rough approximation)
        token_estimate = sum(len(text.split()) * 1.3 for text in texts)  # 1.3x multiplier for subwords

        # Format response in OpenAI-compatible format
        data = []
        for i, vector in enumerate(vectors):
            data.append({
                "object": "embedding",
                "index": i,
                "embedding": vector.tolist()
            })

        response = EmbeddingResponse(
            data=data,
            model=request.model or DEFAULT_MODEL,
            usage={
                "prompt_tokens": int(token_estimate),
                "total_tokens": int(token_estimate)
            },
            elapsed_seconds=round(elapsed_seconds, 3)
        )

        logger.info(".3f")
        return response

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "message": "Local Embedding Server",
        "model": DEFAULT_MODEL,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

def main():
    """Main entry point for running the server."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))

    logger.info(f"Starting embedding server on {host}:{port}")
    logger.info(f"Using model: {DEFAULT_MODEL}")

    uvicorn.run(
        "embedding_server:app",
        host=host,
        port=port,
        reload=False,
        workers=1,  # Single worker for GPU memory efficiency
        log_level="info"
    )

if __name__ == "__main__":
    main()