"""
Fusion Engine - EDS.md Layer 3: Layered Fusion Strategy.

Implements:
- Layer 1: Compute S_f, S_a, S_s signals
- Layer 2: Feature extraction (9 features)
- Layer 3: Fusion model with adaptive weighting + rules

Fusion levels:
- Level 1: Weighted rule-based (MVP)
- Level 2: Logistic regression (planned)
- Level 3: Learning-to-rank (planned)

EDS.md recommendations:
- DO NOT use simple average
- Use weighted fusion: w_f=0.4, w_a=0.35, w_s=0.25
- Apply boost/penalty rules
- Use adaptive weighting based on signal strength
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from src.engines.base_engine import BaseEngine, EngineResult
from src.engines.fusion.feature_extractor import (
    FusionFeatureExtractor,
    EngineSignals,
)


@dataclass
class FusionWeights:
    """Fusion weights following EDS.md recommendations."""
    fingerprint: float = 0.40   # S_f: stable signal (main engine)
    ast: float = 0.35          # S_a: structural complement
    semantic: float = 0.25     # S_s: AI fallback (prevents bypass)

    def to_dict(self) -> Dict[str, float]:
        return {"w_f": self.fingerprint, "w_a": self.ast, "w_s": self.semantic}


class FusionEngine(BaseEngine):
    """
    Layered fusion engine following EDS.md spec.
    
    Flow: compute signals -> extract features -> apply fusion -> apply rules -> S_final
    """
    
    def __init__(self, weights: Optional[FusionWeights] = None,
                 threshold: float = 0.5,
                 adaptive: bool = True):
        super().__init__(name="fusion", weight=1.0)
        self.weights = weights or FusionWeights()
        self.threshold = threshold
        self.adaptive = adaptive
        self.feature_extractor = FusionFeatureExtractor()
        
        # Individual engines (created lazily)
        self._fingerprint_engine = None
        self._ast_engine = None
        self._semantic_engine = None
    
    def _get_fingerprint_engine(self):
        if self._fingerprint_engine is None:
            from src.engines.fingerprint.engine import FingerprintEngine
            self._fingerprint_engine = FingerprintEngine()
        return self._fingerprint_engine
    
    def _get_ast_engine(self):
        if self._ast_engine is None:
            from src.engines.ast.engine import ASTEngine
            self._ast_engine = ASTEngine()
        return self._ast_engine
    
    def _get_semantic_engine(self):
        if self._semantic_engine is None:
            from src.engines.semantic.engine import SemanticEngine
            self._semantic_engine = SemanticEngine()
        return self._semantic_engine
    
    def compute_signals(self, code_a: str, code_b: str, language: str) -> EngineSignals:
        """Layer 1: Compute S_f, S_a, S_s signals."""
        sf = self._get_fingerprint_engine().compare(code_a, code_b, language).score
        try:
            sa = self._get_ast_engine().compare(code_a, code_b, language).score
        except Exception:
            sa = 0.0
        try:
            ss = self._get_semantic_engine().compare(code_a, code_b, language).score
        except Exception:
            ss = 0.0
        return EngineSignals(fingerprint=sf, ast=sa, semantic=ss)
    
    def compare(self, code_a: str, code_b: str, language: str = 'auto',
                **kwargs) -> EngineResult:
        """Full fusion pipeline following EDS.md spec."""
        # Layer 1: Compute signals
        signals = self.compute_signals(code_a, code_b, language)
        
        # Layer 2: Extract features
        features = self.feature_extractor.extract(signals)
        
        # Layer 3: Apply fusion
        s_final = self._fuse(signals, features)
        
        # Apply rules (boost/penalty)
        s_final = self._apply_rules(s_final, signals)
        
        # Clamp to [0, 1]
        s_final = max(0.0, min(1.0, s_final))
        
        return EngineResult(
            score=round(s_final, 4),
            details={
                "signals": signals.to_dict(),
                "features": features,
                "adaptive": self.adaptive,
                "weights": self.weights.to_dict(),
            },
            confidence=self._confidence(signals),
        )
    
    def _fuse(self, signals: EngineSignals, features: Dict[str, float]) -> float:
        """
        Layer 3: Fusion model.
        
        Level 1: Weighted rule-based fusion (MVP)
        S_final = w_f * S_f + w_a * S_a + w_s * S_s
        
        With adaptive weighting if enabled.
        """
        if self.adaptive:
            weights = self._adaptive_weights(signals)
        else:
            weights = self.weights
        
        s_final = (weights.fingerprint * signals.fingerprint +
                   weights.ast * signals.ast +
                   weights.semantic * signals.semantic)
        return s_final
    
    def _adaptive_weights(self, signals: EngineSignals) -> FusionWeights:
        """
        Adaptive weighting: change weights based on signal strength.
        
        Following EDS.md:
        - If S_f is low -> increase S_s weight (try semantic)
        - If S_f is high -> use normal weights (fingerprint is reliable)
        - If signals disagree -> increase AST weight
        """
        sf, sa, ss = signals.fingerprint, signals.ast, signals.semantic
        
        if sf < 0.3:
            # Fingerprint weak -> increase semantic weight
            return FusionWeights(
                fingerprint=0.25,
                ast=0.35,
                semantic=0.40,
            )
        elif abs(sf - sa) > 0.4:
            # High disagreement -> emphasize AST (structure)
            return FusionWeights(
                fingerprint=0.30,
                ast=0.50,
                semantic=0.20,
            )
        return self.weights  # Normal case
    
    def _apply_rules(self, s_final: float, signals: EngineSignals) -> float:
        """
        Apply rule-based boost/penalty following EDS.md spec.
        
        Rule 1: Strong match boost (S_f > 0.8 -> +0.05)
        Rule 2: Consistency boost (S_f > 0.6 AND S_a > 0.6 -> +0.05)
        Rule 3: Conflict penalty (S_f high but S_a very low -> -0.05)
        """
        sf, sa, ss = signals.fingerprint, signals.ast, signals.semantic
        
        # Rule 1: Strong match boost
        if sf > 0.8:
            s_final += 0.05
        
        # Rule 2: Consistency boost
        if sf > 0.6 and sa > 0.6:
            s_final += 0.05
        
        # Rule 3: Conflict penalty
        if sf > 0.7 and sa < 0.3:
            s_final -= 0.05
        
        return s_final
    
    def _confidence(self, signals: EngineSignals) -> float:
        """
        Estimate confidence based on signal consistency.
        
        EDS.md: low variance = high confidence.
        """
        values = [signals.fingerprint, signals.ast, signals.semantic]
        variance = self.feature_extractor._variance(values)
        # Map variance to confidence: low variance -> high confidence
        confidence = max(0.5, 1.0 - variance * 5)
        return round(confidence, 4)
    
    def get_name(self) -> str:
        return "fusion"