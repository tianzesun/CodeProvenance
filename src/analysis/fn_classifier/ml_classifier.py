"""
FN ML Classifier - ML-based classification (Level 2).

Second-level classifier for when rules are ambiguous.
Plans to use CodeBERT/CodeT5 for multi-label classification.

Currently a stub - ready for ML model integration.
"""
from typing import Dict, List, Any, Optional

from src.analysis.fn_classifier.taxonomy import FNCategory, label


class MLClassifier:
    """
    ML-based classifier for FN pairs.
    
    Phase 1 (current): Stub - returns empty labels
    Phase 2: Use pre-trained features with sklearn
    Phase 3: CodeBERT/CodeT5 fine-tuning
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._loaded = False
    
    def classify(self, code1: str, code2: str, features: Dict[str, float]) -> List[str]:
        """
        ML-based classification.
        
        Currently returns empty list (stub). 
        To be replaced with model inference.
        """
        if not self._loaded and self.model_path:
            self._load_model()
        
        # Phase 2: Use heuristic-based fallback
        return self._heuristic_fallback(features)
    
    def _load_model(self):
        """Load ML model from path."""
        self._loaded = True
    
    def _heuristic_fallback(self, features: Dict[str, float]) -> List[str]:
        """Fallback heuristic when ML model not available."""
        token_sim = features.get("token_similarity", 0)
        ident_overlap = features.get("identifier_overlap", 0)
        length_ratio = features.get("length_ratio", 1.0)
        
        labels = []
        if token_sim < 0.5 and ident_overlap >= 0.3:
            labels.append(label(FNCategory.LEXICAL, "variable_renaming"))
        if 0.3 <= token_sim < 0.7 and ident_overlap >= 0.2:
            labels.append(label(FNCategory.STRUCTURAL, "statement_reordering"))
        if length_ratio > 1.5:
            labels.append(label(FNCategory.OBFUSCATION, "dead_code_insertion"))
        
        return labels if labels else [label(FNCategory.LEXICAL, "variable_renaming")]
    
    def train(self, training_data: List[Dict[str, Any]]) -> None:
        """Train ML model on labeled FN data (stub)."""
        pass
    
    def predict_batch(self, batch: List[Dict[str, Any]]) -> List[List[str]]:
        """Predict categories for a batch of FN pairs."""
        return [self.classify(item.get("code1", ""), item.get("code2", ""), 
                              item.get("features", {})) for item in batch]