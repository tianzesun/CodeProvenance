"""GPU Worker - Processes tasks from Redis queue with batching."""
import sys
import time
import torch
from .model import CodeBERTModel
from .batcher import Batcher
from .queue import save_result

class GPUWorker:
    def __init__(self):
        self.model = CodeBERTModel()
        self.batcher = Batcher()
        print("GPU Worker ready.")
    
    def run(self):
        """Main loop - collect batches and process."""
        while True:
            batch = self.batcher.collect()
            if not batch:
                time.sleep(0.05)
                continue
            
            try:
                results = self.model.similarity_batch(batch)
                for task, score in zip(batch, results):
                    risk = "CRITICAL" if score >= 0.9 else "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.5 else "LOW"
                    save_result(task["id"], {"score": round(score, 4), "risk": risk})
            except RuntimeError as e:
                if "CUDA out of memory" in str(e):
                    torch.cuda.empty_cache()
                    print("CUDA OOM - cleared cache, retrying batch")
                    # Re-add to queue
                    from .queue import enqueue
                    for task in batch:
                        enqueue(task)
                else:
                    print(f"Error: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

if __name__ == "__main__":
    worker = GPUWorker()
    worker.run()
