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
import uuid
import asyncio
import logging
import time
from collections import deque
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
_model_load_lock = asyncio.Lock()

# Batching queue system
BATCH_QUEUE = deque()
BATCH_RESULTS = {}
BATCH_LOCK = asyncio.Lock()

BATCH_SIZE = 32
BATCH_TIMEOUT = 0.05  # 50ms window for batching

def _load_model_sync():
    """Synchronous model load (runs in thread pool)."""
    global embedding_model

    if embedding_model is not None:
        return embedding_model

    logger.info(f"Loading embedding model: {DEFAULT_MODEL}")
    start = time.time()

    from sentence_transformers import SentenceTransformer
    embedding_model = SentenceTransformer(DEFAULT_MODEL, device="cpu")

    # Warmup run to eliminate first request latency
    embedding_model.encode("warmup")

    load_time = time.time() - start
    logger.info(f"✅ Model loaded and warmed up in {load_time:.2f}s")

    return embedding_model

async def ensure_model_loaded():
    """Thread-safe lazy model loader."""
    global embedding_model
    if embedding_model is not None:
        return embedding_model
    async with _model_load_lock:
        if embedding_model is not None:
            return embedding_model
        return await asyncio.to_thread(_load_model_sync)

async def batch_worker():
    """Background batch processing worker."""
    global embedding_model

    while True:
        await asyncio.sleep(BATCH_TIMEOUT)

        if embedding_model is None:
            continue

        async with BATCH_LOCK:
            if not BATCH_QUEUE:
                continue

            batch = []
            ids = []

            while BATCH_QUEUE and len(batch) < BATCH_SIZE:
                item = BATCH_QUEUE.popleft()
                batch.append(item["text"])
                ids.append(item["id"])

        # Process embedding batch outside lock
        vectors = embedding_model.encode(
            batch,
            normalize_embeddings=True,
            batch_size=BATCH_SIZE,
            show_progress_bar=False
        )

        for i, _id in enumerate(ids):
            BATCH_RESULTS[_id] = vectors[i].tolist()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan manager - server starts immediately, model loads on demand."""
    # Start background batch worker
    asyncio.create_task(batch_worker())

    yield
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
            batch_size=32,
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

        logger.info(f"Embedding generated in {elapsed_seconds:.3f}s")
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