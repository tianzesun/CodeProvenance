"""FastAPI entry point for GPU inference service."""
import uuid
from fastapi import FastAPI
from .schemas import CompareRequest, BatchRequest, TaskResponse
from .queue import enqueue, get_result, enqueue_batch

app = FastAPI(title="CodeProvenance GPU Service", version="1.0")

# Store for synchronous mode (no queue)
_model = None

def get_model():
    global _model
    if _model is None:
        from .model import CodeBERTModel
        _model = CodeBERTModel()
    return _model

@app.get("/health")
async def health():
    return {"status": "ok", "service": "CodeProvenance GPU"}

@app.post("/compare", response_model=TaskResponse)
async def compare(req: CompareRequest):
    """Submit a comparison task (async)."""
    task_id = str(uuid.uuid4())
    enqueue({"id": task_id, "code_a": req.code_a, "code_b": req.code_b})
    return {"task_id": task_id}

@app.post("/compare/batch")
async def compare_batch(req: BatchRequest):
    """Submit batch comparison (async)."""
    ids = []
    for p in req.pairs:
        task_id = str(uuid.uuid4())
        enqueue({"id": task_id, "code_a": p.code_a, "code_b": p.code_b})
        ids.append(task_id)
    return {"task_ids": ids}

@app.get("/result/{task_id}")
async def get(task_id: str):
    """Get result by task_id."""
    result = get_result(task_id)
    if result is None:
        return {"status": "processing"}
    return {"status": "done", "result": result}

# Synchronous endpoints (for small-scale use)
@app.post("/predict")
async def predict(req: CompareRequest):
    """Synchronous single comparison (no queue)."""
    model = get_model()
    sims = model.similarity_batch([{"code_a": req.code_a, "code_b": req.code_b}])
    score = sims[0]
    risk = "CRITICAL" if score >= 0.9 else "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW"
    return {"score": round(score, 4), "risk": risk}

@app.post("/predict/batch")
async def predict_batch(req: BatchRequest):
    """Synchronous batch comparison (no queue)."""
    model = get_model()
    pairs = [{"code_a": p.code_a, "code_b": p.code_b} for p in req.pairs]
    scores = model.similarity_batch(pairs)
    results = []
    for s in scores:
        risk = "CRITICAL" if s >= 0.9 else "HIGH" if s >= 0.75 else "MEDIUM" if s >= 0.5 else "LOW"
        results.append({"score": round(s, 4), "risk": risk})
    return {"results": results}
