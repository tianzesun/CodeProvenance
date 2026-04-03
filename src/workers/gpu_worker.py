"""GPU Worker - Persistent model with queue-based task processing.

Architecture:
    API Layer → Redis Queue → GPU Worker Pool → Results

Usage:
    CUDA_VISIBLE_DEVICES=0 python workers/gpu_worker.py
"""
import os
import sys
import time
import signal
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [GPU] %(message)s')
logger = logging.getLogger("gpu_worker")

class GPUWorker:
    """GPU worker with persistent model and OOM protection."""

    def __init__(self, device="auto"):
        self.running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except: device = "cpu"
        self.device = device

        self._model = None
        self._tokenizer = None
        self._loaded = False

        logger.info(f"GPU Worker initialized: device={device}")

    def _cleanup_cuda(self):
        """Clear CUDA cache on OOM."""
        try:
            import torch
            torch.cuda.empty_cache()
        except: pass

    def _load_model(self, model_name="microsoft/codebert-base"):
        """Lazy-load model (keeps it in memory for all tasks)."""
        if self._loaded: return
        try:
            from transformers import AutoTokenizer, AutoModel
            logger.info(f"Loading model: {model_name}")
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = AutoModel.from_pretrained(model_name).to(self.device)
            self._model.eval()
            self._loaded = True
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _infer_batch(self, codes_a, codes_b):
        """Batch inference for GPU efficiency.

        Args:
            codes_a, codes_b: Lists of code strings (batch)

        Returns:
            List of cosine similarity scores
        """
        self._load_model()

        pairs = list(zip(codes_a, codes_b))
        texts_a = [a or "" for a, b in pairs]
        texts_b = [b or "" for a, b in pairs]

        tok_a = self._tokenizer(texts_a, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)
        tok_b = self._tokenizer(texts_b, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)

        import torch
        with torch.no_grad():
            out_a = self._model(**tok_a)
            out_b = self._model(**tok_b)

        emb_a = out_a.last_hidden_state[:, 0, :]
        emb_b = out_b.last_hidden_state[:, 0, :]

        # Cosine similarity
        norm_a = emb_a.norm(dim=-1, keepdim=True)
        norm_b = emb_b.norm(dim=-1, keepdim=True)
        sims = (emb_a * emb_b).sum(dim=-1) / (norm_a * norm_b).clamp(min=1e-8)
        
        # Clamp and convert to list
        sims = sims.clamp(0, 1).cpu().tolist()
        
        # Handle single value
        if isinstance(sims, float): sims = [sims]
        
        return sims

    def compare(self, code_a, code_b):
        """Single comparison (wraps batch for 1 item)."""
        return self._infer_batch([code_a], [code_b])[0]

    def _handle_signal(self, signum, frame):
        """Graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run(self):
        """Main worker loop - processes from queue."""
        logger.info("GPU Worker started")
        self._load_model()
        
        while self.running:
            task = self._get_task()
            if not task:
                time.sleep(0.1)
                continue
            try:
                result = self.process(task)
                self._save_result(result)
            except RuntimeError as e:
                if "CUDA out of memory" in str(e):
                    self._cleanup_cuda()
                logger.error(f"Task failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

    def process(self, task):
        """Process a task (dict with 'id', 'code_a', 'code_b')."""
        if isinstance(task, tuple):
            return self.compare(task[0], task[1])
        return {
            "id": task.get("id", "unknown"),
            "score": self.compare(task["code_a"], task["code_b"]),
        }

    def _get_task(self):
        """Get next task from queue. Override for production use."""
        # TODO: Connect to Redis/RabbitMQ
        return None

    def _save_result(self, result):
        """Save result. Override for production."""
        pass


if __name__ == "__main__":
    worker = GPUWorker()
    # Test mode: run batch inference
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        worker._load_model()
        scores = worker._infer_batch(
            ["def foo(x): return x + 1", "a = 1; b = 2"],
            ["def bar(y): return y + 1", "c = 3; d = 4"]
        )
        print(f"Batch scores: {scores}")
    else:
        worker.run()
