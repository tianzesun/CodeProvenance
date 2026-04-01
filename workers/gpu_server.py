"""GPU Inference Service - FastAPI with batching and queue.

Architecture:
    API Request → Redis Queue → GPU Worker (batched) → Redis Result → API Response

Usage:
    # Install: pip install redis fastapi uvicorn transformers torch
    # Start Redis: redis-server
    # Start GPU worker: python gpu_server.py worker
    # Start API: python gpu_server.py api
    
    # Test: curl -X POST http://localhost:8001/predict -d '{"code_a":"def f():pass","code_b":"def g():pass"}'
"""
import os
import sys
import json
import uuid
import time
import signal
from pathlib import Path

print("Starting GPU Server module...")

def detect_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except:
        return "cpu"

DEVICE = detect_device()
print(f"Device: {DEVICE}")

class EmbeddingModel:
    """Persistent model loaded once (not per-request)."""
    
    def __init__(self, model_name="microsoft/codebert-base"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self._loaded = False
    
    def load(self):
        if self._loaded: return
        from transformers import AutoTokenizer, AutoModel
        print(f"Loading {self.model_name} on {DEVICE}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name).to(DEVICE)
        self.model.eval()
        self._loaded = True
        print("Model loaded!")
    
    @staticmethod
    def cosine_similarity(a, b):
        import torch
        norm_a = a.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        norm_b = b.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        return (a * b).sum(dim=-1) / (norm_a * norm_b)
    
    def encode_batch(self, texts):
        """Batch encoding for GPU efficiency."""
        self.load()
        import torch
        batch = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            outputs = self.model(**batch)
        return outputs.last_hidden_state[:, 0, :]
    
    def compare_batch(self, texts_a, texts_b):
        """Compare multiple pairs in batch (efficient GPU usage)."""
        embeddings_a = self.encode_batch(texts_a)
        embeddings_b = self.encode_batch(texts_b)
        sims = self.cosine_similarity(embeddings_a, embeddings_b)
        return sims.clamp(0, 1).cpu().tolist()

model = EmbeddingModel()

# ─────────────────────────────────────────────
# API Mode: FastAPI server
# ─────────────────────────────────────────────
def start_api():
    from fastapi import FastAPI
    from pydantic import BaseModel
    
    app = FastAPI(title="CodeProvenance GPU Service", version="1.0")
    
    class CompareRequest(BaseModel):
        code_a: str
        code_b: str
    
    class BatchRequest(BaseModel):
        pairs: list  # [{"code_a": "...", "code_b": "..."}, ...]
    
    # Load model on startup
    @app.on_event("startup")
    async def startup():
        model.load()
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "device": DEVICE, "model_loaded": model._loaded}
    
    @app.post("/predict")
    async def predict(req: CompareRequest):
        score = model.compare_batch([req.code_a], [req.code_b])[0]
        risk = "CRITICAL" if score >= 0.9 else "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW"
        return {"score": round(score, 4), "risk": risk}
    
    @app.post("/predict_batch")
    async def predict_batch(req: BatchRequest):
        texts_a = [p.get("code_a", "") for p in req.pairs]
        texts_b = [p.get("code_b", "") for p in req.pairs]
        scores = model.compare_batch(texts_a, texts_b)
        return {
            "results": [
                {"score": round(s, 4), 
                 "risk": "CRITICAL" if s >= 0.9 else "HIGH" if s >= 0.75 else "MEDIUM" if s >= 0.5 else "LOW"}
                for s in scores
            ]
        }
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

# ─────────────────────────────────────────────
# Worker Mode: Background task processor
# ─────────────────────────────────────────────
def start_worker():
    """Worker mode - processes tasks from queue."""
    model.load()
    import time
    print("GPU Worker started. Press Ctrl+C to stop.")
    
    # Simple file-based queue (use Redis in production)
    queue_dir = Path("/tmp/codeprovenance_queue")
    result_dir = Path("/tmp/codeprovenance_results")
    queue_dir.mkdir(exist_ok=True)
    result_dir.mkdir(exist_ok=True)
    
    while True:
        # Check for tasks
        tasks = list(queue_dir.glob("*.json"))
        if tasks:
            task_file = tasks[0]
            try:
                with open(task_file) as f:
                    task = json.load(f)
                pairs = task.get("pairs", [])
                texts_a = [p["code_a"] for p in pairs]
                texts_b = [p["code_b"] for p in pairs]
                scores = model.compare_batch(texts_a, texts_b)
                
                result = {"task_id": task.get("task_id"), "scores": scores}
                with open(result_dir / f"{task['task_id']}.json", "w") as f:
                    json.dump(result, f)
                task_file.unlink()
            except Exception as e:
                print(f"Task failed: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        start_worker()
    else:
        start_api()
