"""CodeBERT/UniXcoder embedding similarity for GPU server deployment.

Replace OpenAI embeddings with local CodeBERT model.
Usage:
    from src.engines.similarity.codebert_similarity import CodeBERTSimilarity
    similarity = CodeBERTSimilarity(device='cuda')
    score = similarity.compare({'raw': code_a}, {'raw': code_b})
"""
from typing import Dict, List, Any

class CodeBERTSimilarity:
    def __init__(self, model_name="microsoft/codebert-base", device="auto"):
        self.model_name = model_name
        if device == "auto":
            device = "cuda" if self._has_gpu() else "cpu"
        self.device = device
        self._model = None
    @staticmethod
    def _has_gpu():
        try:
            import torch
            return torch.cuda.is_available()
        except: return False
    def _load_model(self):
        if self._model: return
        from transformers import AutoTokenizer, AutoModel
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name).to(self.device)
        self._model.eval()
    def _encode(self, code):
        self._load_model()
        inputs = self._tokenizer(code, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        import torch
        with torch.no_grad():
            outputs = self._model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).squeeze().tolist()
    def compare(self, a, b):
        ca = a.get('raw', '') if isinstance(a, dict) else a
        cb = b.get('raw', '') if isinstance(b, dict) else b
        if not ca or not cb: return 0.0
        ea, eb = self._encode(ca), self._encode(cb)
        dot = sum(x*y for x,y in zip(ea,eb)); na = sum(x*x for x in ea)**0.5; nb = sum(x*x for x in eb)**0.5
        if na == 0 or nb == 0: return 0.0
        return max(0.0, min(1.0, dot/(na*nb)))

class UniXcoderSimilarity(CodeBERTSimilarity):
    def __init__(self, device="auto"):
        super().__init__("microsoft/unixcoder-base", device)
