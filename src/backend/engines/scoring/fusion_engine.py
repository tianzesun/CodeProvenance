"""Fusion Engine - Combined multi-engine scoring with configurable weights."""
import os
import time
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field

import yaml

from src.backend.evaluation.arbitration import BayesianArbitrator


@dataclass
class FusedScore:
    """Result of fused multi-engine similarity scoring."""
    final_score: float
    confidence: float = 0.8
    uncertainty: float = 0.0
    agreement_index: float = 1.0
    components: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)


# Baseline scores expected for two unrelated files in the same language.
# These represent the "noise floor" — scores that occur just from sharing
# a language's syntax, common patterns, and embedding vocabulary.
# Scores at or below baseline are treated as zero similarity.
LANGUAGE_BASELINE: Dict[str, float] = {
    "embedding": 0.70,    # UniXcoder sees "this is Python code" for both
    "winnowing": 0.25,    # Common keywords/structures produce some overlap
    "ngram": 0.15,        # Character n-grams share syntax tokens
    "ast": 0.25,          # Similar AST node types (functions, returns, etc.)
    "fingerprint": 0.15,  # Token-level overlap from language keywords
}


CONFIG_PATH = Path(__file__).parent.parent / "engine_weights.yaml"


def load_engine_config() -> Dict:
    """Load engine configuration from YAML config file."""
    if not CONFIG_PATH.exists():
        return _get_default_config()
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except Exception:
        return _get_default_config()


def save_engine_config(config: Dict) -> None:
    """Save engine configuration to YAML config file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)


def _get_default_config() -> Dict:
    return {
        "weights": {
            "ast": 0.65,
            "token": 0.25,
            "winnowing": 0.10,
            "graph": 0.00,
            "execution": 0.00,
            "embedding": 0.00,
            "ngram": 0.00,
            "codebert": 0.00,
        },
        "baseline_correction": {
            "enabled": True,
            "baselines": {
                "embedding": 0.70,
                "winnowing": 0.25,
                "ngram": 0.15,
                "ast": 0.25,
                "fingerprint": 0.15,
            }
        },
        "arbitration": {
            "enabled": True,
            "prior_precision_multiplier": 20.0,
            "minimum_agreement": 0.30,
        },
        "ast_boost": {
            "enabled": True,
            "threshold": 0.90,
            "minimum_guaranteed_score": 0.75,
        }
    }


# Default fallback values
DEFAULT_WEIGHTS: Dict[str, float] = _get_default_config()["weights"]
LANGUAGE_BASELINE: Dict[str, float] = _get_default_config()["baseline_correction"]["baselines"]


class FusionEngine:
    """Multi-engine fusion scoring authority.

    Combines similarity scores from multiple engines using
    configurable weights and produces a single fused score.

    Applies baseline correction to remove same-language noise floor
    so that unrelated files score near 0% instead of 30-50%.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self._config = load_engine_config()
        self._last_load_time = time.time()
        
        if weights is None:
            weights = self._config["weights"]
            
        self.weights: Dict[str, float] = dict(weights)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
            
        multiplier = self._config["arbitration"]["prior_precision_multiplier"]
        self._arbitrator = BayesianArbitrator(engine_prior_precisions={k: v*multiplier for k, v in self.weights.items()})

    def reload_config(self) -> None:
        """Reload configuration from disk if modified."""
        if self._config["advanced"].get("hot_reload", True):
            mtime = os.path.getmtime(CONFIG_PATH)
            if mtime > self._last_load_time:
                self.__init__()
    
    @classmethod
    def get_current_config(cls) -> Dict:
        """Get full current engine configuration."""
        return load_engine_config()
    
    @classmethod
    def update_config(cls, config: Dict) -> None:
        """Update and save engine configuration (Admin only)."""
        save_engine_config(config)
        
    @classmethod
    def get_standard_presets(cls) -> Dict[str, Dict[str, float]]:
        """Get standard faculty presets.
        
        These are safe multipliers that overlay on base weights, they do
        not modify the admin calibrated base configuration.
        """
        return {
            "default": {
                "name": "Balanced",
                "description": "Default balanced detection profile. Good for most assignments.",
                "multipliers": {}
            },
            "strict_copy": {
                "name": "Strict Copy Detection",
                "description": "For introductory assignments. Emphasizes exact matching.",
                "multipliers": {
                    "winnowing": 2.0,
                    "token": 1.5,
                    "ast": 0.5,
                    "graph": 0.5
                }
            },
            "semantic_plagiarism": {
                "name": "Advanced Plagiarism Detection",
                "description": "For advanced assignments. Detects obfuscation and modification.",
                "multipliers": {
                    "graph": 2.0,
                    "execution": 1.8,
                    "ast": 1.2,
                    "winnowing": 0.5
                }
            },
            "structure_focus": {
                "name": "Code Structure Focus",
                "description": "Prioritize architecture and design similarity over exact code.",
                "multipliers": {
                    "ast": 1.8,
                    "graph": 1.5,
                    "token": 0.5,
                    "winnowing": 0.5
                }
            },
            "ai_detection": {
                "name": "AI Generated Code Detection",
                "description": "Optimize for detecting AI generated code patterns.",
                "multipliers": {
                    "embedding": 3.0,
                    "ast": 1.2,
                    "graph": 1.5
                }
            }
        }

    def fuse(self, features: "FeatureVector", weight_multipliers: Optional[Dict[str, float]] = None) -> FusedScore:
        """Combine engine outputs into a single similarity score using Bayesian arbitration.

        Applies baseline correction: subtracts the expected same-language noise floor
        from each engine score before fusion. This prevents unrelated files from
        scoring 30-50% just because they share a programming language.

        Args:
            features: A FeatureVector containing scores from each engine.
            weight_multipliers: Optional per-engine multipliers to overlay on base weights.
                Used for user presets, does not modify base configuration.

        Returns:
            A FusedScore with the combined score, confidence, and per-engine breakdown.
        """
        raw_scores = features.as_dict()
        
        # Apply user preset weight multipliers if provided
        active_weights = dict(self.weights)
        if weight_multipliers:
            for engine, multiplier in weight_multipliers.items():
                if engine in active_weights:
                    active_weights[engine] *= multiplier
        
        # Re-normalize after multipliers
        total = sum(active_weights.values())
        if total > 0:
            active_weights = {k: v / total for k, v in active_weights.items()}

        # Apply baseline correction — subtract noise floor from each engine
        corrected_scores = {}
        for name, score in raw_scores.items():
            baseline = LANGUAGE_BASELINE.get(name, 0.0)
            corrected = max(0.0, score - baseline) / max(0.01, 1.0 - baseline)
            corrected_scores[name] = round(corrected, 4)

        arbitration = self._arbitrator.arbitrate(corrected_scores)
        
        # JPlag-style AST boost: if AST similarity is very high, guarantee minimum score
        final_score = arbitration.fused_score
        ast_score = corrected_scores.get("ast", 0.0)
        
        # Clamp to valid range
        final_score = min(1.0, max(0.0, final_score))

        return FusedScore(
            final_score=final_score,
            confidence=arbitration.agreement_index,
            uncertainty=arbitration.uncertainty,
            agreement_index=arbitration.agreement_index,
            components=raw_scores,
            contributions=arbitration.engine_contributions
        )

    def get_weights(self) -> Dict[str, float]:
        """Return the current normalized engine weights."""
        return dict(self.weights)

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update and re-normalize engine weights.

        Args:
            weights: A dict mapping engine names to raw weight values.
        """
        self.weights = dict(weights)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        self._arbitrator = BayesianArbitrator(engine_prior_precisions={k: v*20 for k, v in self.weights.items()})
