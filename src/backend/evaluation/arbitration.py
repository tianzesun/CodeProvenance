import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class ArbitrationResult:
    fused_score: float
    uncertainty: float
    engine_contributions: Dict[str, float]
    agreement_index: float

class BayesianArbitrator:
    """
    Statistical arbitration layer to combine multi-engine results.
    Avoids 'metric inflation' by using a probabilistic consensus model.
    """
    
    def __init__(self, engine_prior_precisions: Optional[Dict[str, float]] = None):
        # Precision represents our confidence in each engine (1/variance)
        self.precisions = engine_prior_precisions or {
            "ast": 5.0,
            "fingerprint": 4.0,
            "embedding": 3.0,
            "ngram": 2.0,
            "winnowing": 2.0
        }

    def arbitrate(self, engine_scores: Dict[str, float]) -> ArbitrationResult:
        """
        Perform Bayesian fusion of engine scores.
        Treats each score as a noisy observation of the 'true' similarity.
        """
        scores = []
        precs = []
        names = []
        
        for name, score in engine_scores.items():
            if name in self.precisions:
                scores.append(score)
                precs.append(self.precisions[name])
                names.append(name)
        
        if not scores:
            return ArbitrationResult(0.0, 1.0, {}, 0.0)
            
        scores = np.array(scores)
        precs = np.array(precs)
        
        # Bayesian Update for Gaussian (simplified for [0, 1] range)
        # Posterior mean = sum(precision * score) / sum(precision)
        posterior_precision = np.sum(precs)
        fused_score = np.sum(precs * scores) / posterior_precision
        
        # Uncertainty is inverse of posterior precision
        uncertainty = 1.0 / (1.0 + posterior_precision)
        
        # Calculate contributions
        contributions = {names[i]: float(precs[i] * scores[i] / (fused_score * posterior_precision)) 
                        if fused_score > 0 else 0.0 
                        for i in range(len(names))}
        
        # Agreement index: how much the engines agree with the fused score
        # 1.0 = perfect agreement, 0.0 = total chaos
        if len(scores) > 1:
            variance = np.average((scores - fused_score)**2, weights=precs)
            agreement_index = 1.0 / (1.0 + variance * 10) # Scaled
        else:
            agreement_index = 1.0
            
        return ArbitrationResult(
            fused_score=float(fused_score),
            uncertainty=float(uncertainty),
            engine_contributions=contributions,
            agreement_index=float(agreement_index)
        )

class ConsensusArbitrator:
    """
    Arbitrates based on engine consensus.
    If engines disagree significantly, it penalizes the final score.
    """
    
    def arbitrate(self, engine_scores: Dict[str, float]) -> float:
        scores = list(engine_scores.values())
        if not scores:
            return 0.0
            
        mean_score = np.mean(scores)
        std_dev = np.std(scores)
        
        # Penalty for disagreement
        # If std_dev is high, we are less sure, so we pull the score towards 0.5 (uncertainty) 
        # or just reduce it if it's supposed to be a 'safe' detection.
        penalty = 1.0 - (std_dev * 2.0)
        return float(max(0.0, mean_score * max(0.0, penalty)))
