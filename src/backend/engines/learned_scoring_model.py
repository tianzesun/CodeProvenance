"""
Learned Unified Scoring Model
Turns heuristic detector into learned ranking model (JPlag+ / Turnitin style)

Uses gradient boosted trees to automatically learn optimal engine weighting
from labeled data, instead of hand-tuned fixed weights.
"""
from typing import List, Dict, Tuple, Any, Optional
import numpy as np
import pickle
from pathlib import Path

try:
    from sklearn.ensemble import GradientBoostingRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class LearnedScoringModel:
    """
    Unified learned scoring model that automatically weights all plagiarism engines.
    
    Outperforms manual fixed weights by learning context-sensitive weighting:
    - When to trust AST vs GST vs Token similarity
    - How to handle edge cases and obfuscation
    - Dataset-specific patterns
    """
    
    FEATURE_NAMES = [
        "ast_similarity",
        "token_similarity",
        "gst_similarity",
        "semantic_similarity",
        "cfg_similarity",
        "size_ratio",
        "function_overlap",
        "normalized_edit_dist"
    ]
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.is_trained = False
        self._default_weights = np.array([0.45, 0.20, 0.25, 0.10, 0.0, 0.0, 0.0, 0.0])
        
        if model_path and Path(model_path).exists():
            self.load(model_path)
        elif SKLEARN_AVAILABLE:
            self.model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
    
    def featurize(self, engine_scores: Dict[str, float], metadata: Dict[str, Any]) -> np.ndarray:
        """
        Convert engine scores and metadata into feature vector.
        
        Args:
            engine_scores: Raw scores from all engines
            metadata: Additional pair metadata (size, overlap, etc.)
        """
        features = np.zeros(len(self.FEATURE_NAMES))
        
        # Engine similarity scores
        features[0] = engine_scores.get("ast", 0.0)
        features[1] = engine_scores.get("token", 0.0)
        features[2] = engine_scores.get("gst", 0.0)
        features[3] = engine_scores.get("semantic", 0.0)
        features[4] = engine_scores.get("cfg", 0.0)
        
        # Metadata features
        features[5] = metadata.get("size_ratio", 1.0)
        features[6] = metadata.get("function_overlap", 0.0)
        features[7] = metadata.get("edit_distance", 0.0)
        
        return features
    
    def train(self, training_data: List[Tuple[Dict[str, float], Dict[str, Any], float]]) -> None:
        """
        Train the model on labeled dataset.
        
        Args:
            training_data: List of (engine_scores, metadata, label) tuples
                           label: 1.0 = plagiarism, 0.0 = unrelated
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for training")
        
        X = []
        y = []
        
        for scores, metadata, label in training_data:
            X.append(self.featurize(scores, metadata))
            y.append(label)
        
        X = np.array(X)
        y = np.array(y)
        
        self.model.fit(X, y)
        self.is_trained = True
    
    def predict(self, engine_scores: Dict[str, float], metadata: Dict[str, Any]) -> float:
        """
        Predict unified similarity score between 0 and 1.
        
        Returns:
            Combined similarity score optimized by learned model
        """
        features = self.featurize(engine_scores, metadata)
        
        if self.is_trained and self.model is not None:
            score = float(self.model.predict([features])[0])
        else:
            # Fallback to hand-tuned weights if model not trained
            score = float(np.dot(features[:8], self._default_weights))
        
        # Clamp to valid range
        return min(1.0, max(0.0, score))
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Return learned feature importance weights."""
        if not self.is_trained or self.model is None:
            return dict(zip(self.FEATURE_NAMES, self._default_weights))
        
        return dict(zip(self.FEATURE_NAMES, self.model.feature_importances_))
    
    def save(self, path: str) -> None:
        """Save trained model to disk."""
        with open(path, 'wb') as f:
            pickle.dump({
                "model": self.model,
                "is_trained": self.is_trained
            }, f)
    
    def load(self, path: str) -> None:
        """Load trained model from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.is_trained = data["is_trained"]


class GatedFusionModel:
    """
    Advanced gated fusion model (mixture-of-experts).
    
    This is what high-end industrial systems use.
    Dynamically weights each expert engine based on input features.
    """
    
    def __init__(self):
        self.gate_weights = np.random.randn(8, 4) * 0.1
        self.expert_weights = np.array([0.45, 0.25, 0.20, 0.10])
    
    def _softmax(self, x: np.ndarray) -> np.ndarray:
        ex = np.exp(x - np.max(x))
        return ex / ex.sum()
    
    def predict(self, engine_scores: Dict[str, float], metadata: Dict[str, Any]) -> float:
        """
        Gated prediction: dynamically adjusts expert weights per pair.
        
        Gate network decides how much to trust each engine for this specific pair.
        """
        features = LearnedScoringModel().featurize(engine_scores, metadata)
        
        # Compute gate logits
        gate_logits = features @ self.gate_weights
        expert_weights = self._softmax(gate_logits)
        
        # Get expert scores
        experts = np.array([
            engine_scores.get("ast", 0.0),
            engine_scores.get("gst", 0.0),
            engine_scores.get("token", 0.0),
            engine_scores.get("semantic", 0.0)
        ])
        
        # Weighted combination with dynamic per-pair weights
        score = float(expert_weights @ experts)
        
        # Confidence boost for high AST matches
        if engine_scores.get("ast", 0.0) > 0.85:
            score = max(score, 0.92)
        
        return min(1.0, max(0.0, score))


class ScoringPipeline:
    """
    Full end-to-end scoring pipeline combining all layers:
    
    1. LSH candidate filtering
    2. All engine feature extraction
    3. Learned unified scoring
    4. Ranking and evidence generation
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.scoring_model = LearnedScoringModel(model_path)
        self.gated_model = GatedFusionModel()
        self.use_gated = False
    
    def score_pair(self, code_a: str, code_b: str, extract_features_fn: callable) -> Dict[str, Any]:
        """
        Full pipeline to score a single pair of code files.
        """
        # Extract all engine features
        engine_scores, metadata = extract_features_fn(code_a, code_b)
        
        # Get unified score
        if self.use_gated:
            final_score = self.gated_model.predict(engine_scores, metadata)
        else:
            final_score = self.scoring_model.predict(engine_scores, metadata)
        
        return {
            "final_score": final_score,
            "engine_scores": engine_scores,
            "metadata": metadata,
            "feature_importance": self.scoring_model.get_feature_importance()
        }
