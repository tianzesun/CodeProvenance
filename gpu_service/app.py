"""FastAPI entry point for GPU inference service."""
import uuid
import logging
from fastapi import FastAPI, HTTPException
from .schemas import CompareRequest, BatchRequest, TaskResponse

logger = logging.getLogger("gpu_service")

app = FastAPI(title="IntegrityDesk GPU Service", version="1.0")

# Lazy model loading
_model = None
_model_error = None

def get_model():
    """Lazy load model. Returns None if dependencies missing."""
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error:
        return None
    try:
        from .model import CodeBERTModel
        _model = CodeBERTModel()
        return _model
    except Exception as e:
        _model_error = str(e)
        logger.warning(f"Model not loaded: {e}")
        return None

@app.get("/health")
async def health():
    model_ok = get_model() is not None
    return {"status": "ok", "service": "IntegrityDesk GPU", "model_loaded": model_ok}

@app.post("/compare", response_model=TaskResponse)
async def compare(req: CompareRequest):
    """Submit async comparison task."""
    from .queue import enqueue
    task_id = str(uuid.uuid4())
    try:
        enqueue({"id": task_id, "code_a": req.code_a, "code_b": req.code_b})
    except ImportError:
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"task_id": task_id}

@app.post("/compare/batch")
async def compare_batch(req: BatchRequest):
    """Submit async batch comparison."""
    from .queue import enqueue
    ids = []
    try:
        for p in req.pairs:
            task_id = str(uuid.uuid4())
            enqueue({"id": task_id, "code_a": p.code_a, "code_b": p.code_b})
            ids.append(task_id)
    except ImportError:
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"task_ids": ids}

@app.get("/result/{task_id}")
async def get(task_id: str):
    """Get async result."""
    from .queue import get_result
    result = get_result(task_id)
    if result is None:
        return {"status": "processing"}
    return {"status": "done", "result": result}

@app.post("/predict")
async def predict(req: CompareRequest):
    """Sync single comparison (no queue)."""
    model = get_model()
    if model is None:
        raise HTTPException(status_code=503, detail=f"Model not available: {_model_error}")
    sims = model.similarity_batch([{"code_a": req.code_a, "code_b": req.code_b}])
    score = sims[0]
    risk = "CRITICAL" if score >= 0.9 else "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW"
    return {"score": round(score, 4), "risk": risk}

@app.post("/predict/batch")
async def predict_batch(req: BatchRequest):
    """Sync batch comparison (no queue)."""
    model = get_model()
    if model is None:
        raise HTTPException(status_code=503, detail=f"Model not available: {_model_error}")
    pairs = [{"code_a": p.code_a, "code_b": p.code_b} for p in req.pairs]
    scores = model.similarity_batch(pairs)
    results = []
    for s in scores:
        risk = "CRITICAL" if s >= 0.9 else "HIGH" if s >= 0.75 else "MEDIUM" if s >= 0.5 else "LOW"
        results.append({"score": round(s, 4), "risk": risk})
    return {"results": results}