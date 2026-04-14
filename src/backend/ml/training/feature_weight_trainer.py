"""Feature Weight Trainer - Logistic Regression for learning weights from data."""
from typing import Dict, List, Any, Tuple
import json
FEATURE_ORDER = ["ast", "fingerprint", "embedding", "ngram", "winnowing"]

class FeatureWeightTrainer:
    def __init__(self, class_weight: str = "balanced"):
        self.class_weight = class_weight
        self._model = None
        self._scaler_mean = None
        self._scaler_std = None
    def train(self, X: List[List[float]], y: List[int]) -> Dict[str, Any]:
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import cross_val_score
        except ImportError:
            return self._train_simple(X, y)
        X_scaled, self._scaler_mean, self._scaler_std = self._scale(X)
        self._model = LogisticRegression(class_weight=self.class_weight, max_iter=1000)
        self._model.fit(X_scaled, y)
        cv = cross_val_score(self._model, X_scaled, y, cv=min(5, len(y)))
        return {"weights": self.get_weights(),
                "metrics": {"train_acc": self._model.score(X_scaled, y),
                            "cv_acc": f"{cv.mean():.3f}",
                            "intercept": float(self._model.intercept_[0])},
                "feature_importance": dict(zip(FEATURE_ORDER, self._model.coef_[0].tolist()))}
    def get_weights(self) -> Dict[str, float]:
        if self._model is None:
            return {f: 1.0/len(FEATURE_ORDER) for f in FEATURE_ORDER}
        return dict(zip(FEATURE_ORDER, self._model.coef_[0].tolist()))
    def predict_proba(self, X: List[List[float]]) -> List[float]:
        if self._model is None: return [0.5]*len(X)
        return self._model.predict_proba(self._scale(X, self._scaler_mean, self._scaler_std))[:,1].tolist()
    def to_features(self, fd: Dict[str, float]) -> List[float]:
        return [fd.get(f, 0.0) for f in FEATURE_ORDER]
    @staticmethod
    def _scale(X, m=None, s=None):
        if m is None:
            n, m2 = len(X), len(X[0])
            m = [sum(X[i][j] for i in range(n))/n for j in range(m2)]
            s = [max((sum((X[i][j]-m[j])**2 for i in range(n))/n)**0.5, 1e-8) for j in range(m2)]
            return [[(X[i][j]-m[j])/s[j] for j in range(m2)] for i in range(n)], m, s
        return [[(x-me)/sd for x, me, sd in zip(r, m, s)] for r in X]
    @staticmethod
    def _train_simple(X, y):
        n = len(X[0]); w = [1.0/n]*n; b = 0.0; lr = 0.01
        for _ in range(100):
            for xi, yi in zip(X, y):
                p = sum(we*x for we, x in zip(w, xi)) + b; e = yi - p
                w = [we + lr*e*x for we, x in zip(w, xi)]; b += lr*e
        return {"weights": dict(zip(FEATURE_ORDER, w)), "metrics": {"note": "simple training"}, "feature_importance": dict(zip(FEATURE_ORDER, w)), "intercept": b}

class MLDecisionEngine:
    def __init__(self, trainer: FeatureWeightTrainer, threshold: float = 0.5):
        self.trainer = trainer; self.threshold = threshold
    def decide(self, features: Dict[str, float]) -> Dict[str, Any]:
        x = self.trainer.to_features(features)
        score = self.trainer.predict_proba([x])[0]
        return {"label": 1 if score >= self.threshold else 0, "score": score, "features": features}
