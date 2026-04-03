import torch
from typing import List, Dict, Any
from .config import DEVICE, MODEL_NAME

class CodeBERTModel:
    """Persistent CodeBERT model with batch inference."""
    
    def __init__(self, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Loading {MODEL_NAME} on {self.device}...")
        from transformers import AutoTokenizer, AutoModel
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModel.from_pretrained(MODEL_NAME).to(self.device)
        self.model.eval()
        print("Model loaded!")
    
    def encode(self, texts: List[str]) -> torch.Tensor:
        """Batch embed texts."""
        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1)
    
    def similarity_batch(self, pairs: List[Dict[str, Any]]) -> List[float]:
        """Batch similarity computation.

        Args:
            pairs: [{"code_a": "...", "code_b": "..."}, ...]
        
        Returns:
            List of cosine similarity scores [0, 1]
        """
        if not pairs: return []
        texts_a = [p.get("code_a", "") for p in pairs]
        texts_b = [p.get("code_b", "") for p in pairs]
        
        emb_a = self.encode(texts_a)
        emb_b = self.encode(texts_b)
        
        sims = torch.nn.functional.cosine_similarity(emb_a, emb_b)
        return sims.clamp(0, 1).cpu().tolist()
