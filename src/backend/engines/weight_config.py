"""
Engine Weight Configuration Loader.

Loads, validates and manages engine weights from engine_weights.yaml.
Supports hot reload, validation, and runtime configuration updates.
All weights and thresholds are fully configurable from this single source.
"""

from __future__ import annotations

import yaml
import os
import logging
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
from threading import Lock
import time

logger = logging.getLogger(__name__)


class EngineWeightConfig:
    """
    Centralized configuration for all similarity engine weights and thresholds.
    
    Loads from engine_weights.yaml, validates schema, and provides type safe access
    to all configuration values. Supports hot reloading of changes.
    
    All hardcoded weights and thresholds have been moved here.
    """
    
    _instance: Optional[EngineWeightConfig] = None
    _lock = Lock()
    
    DEFAULT_CONFIG_PATH = Path(__file__).parent / "engine_weights.yaml"
    
    @classmethod
    def get_instance(cls) -> EngineWeightConfig:
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = EngineWeightConfig()
            return cls._instance
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._last_load_time = 0.0
        self._last_modified_time = 0.0
        
        # Valid engine names for validation
        self.valid_engines: Set[str] = {
            "ast", "token", "winnowing", "gst", "semantic", "web",
            "ai_detection", "execution_cfg", "tree_kernel", "cfg"
        }
        
        self.load_config()
    
    def load_config(self) -> None:
        """Load and validate configuration from yaml file."""
        try:
            if not self.config_path.exists():
                logger.warning("Engine weights config not found at %s, using defaults", self.config_path)
                self._load_defaults()
                return
            
            mtime = os.path.getmtime(self.config_path)
            if mtime == self._last_modified_time:
                return  # No changes
            
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
            
            self._last_modified_time = mtime
            self._last_load_time = time.time()
            
            self._validate_config()
            self._normalize_weights()
            
            logger.info(
                "Engine weights config loaded successfully, modified at %s",
                time.ctime(self._last_modified_time)
            )
            
        except Exception as e:
            logger.error("Failed to load engine weights config: %s", str(e), exc_info=True)
            self._load_defaults()
    
    def reload_if_changed(self) -> bool:
        """Hot reload configuration if file has changed. Returns True if reloaded."""
        if not self.config_path.exists():
            return False
        
        current_mtime = os.path.getmtime(self.config_path)
        if current_mtime > self._last_modified_time:
            logger.info("Engine weights config changed, reloading")
            self.load_config()
            return True
        return False
    
    def _validate_config(self) -> None:
        """Validate configuration schema."""
        if "weights" not in self._config:
            raise ValueError("Missing 'weights' section in config")
        
        # Validate all weights are numbers
        for engine, weight in self._config["weights"].items():
            if engine not in self.valid_engines:
                logger.warning("Unknown engine in weights: %s", engine)
            if not isinstance(weight, (int, float)):
                raise ValueError(f"Invalid weight for {engine}: must be number")
            if weight < 0.0 or weight > 1.0:
                raise ValueError(f"Invalid weight for {engine}: must be between 0.0 and 1.0")
    
    def _normalize_weights(self) -> None:
        """Normalize weights to sum to exactly 1.0."""
        total = sum(self._config["weights"].values())
        if total <= 0.0:
            logger.warning("All engine weights are zero, using default weights")
            self._load_defaults()
            return
        
        # Normalize
        for engine in self._config["weights"]:
            self._config["weights"][engine] /= total
    
    def _load_defaults(self) -> None:
        """Load default configuration if file is missing or invalid."""
        self._config = {
            "weights": {
                "ast": 0.45,
                "token": 0.15,
                "winnowing": 0.05,
                "gst": 0.05,
                "semantic": 0.15,
                "execution_cfg": 0.15,
                "tree_kernel": 0.0,
                "cfg": 0.0,
                "web": 0.0,
                "ai_detection": 0.0
            },
            "baseline_correction": {
                "baselines": {
                    "winnowing": 0.35,
                    "ast": 0.25,
                    "fingerprint": 0.3,
                    "ngram": 0.2,
                    "embedding": 0.25
                }
            },
            "precision_guard": {
                "enabled": True,
                "high_score_floor": 0.68,
                "extreme_score_floor": 0.85,
                "evidence_threshold": 0.4,
                "lexical_threshold": 0.45,
                "minimum_concrete_engines": 2,
                "minimum_concrete_engines_high_score": 1,
                "minimum_lexical_engines": 2,
                "minimum_lexical_engines_high_score": 1,
                "penalty_multiplier": 0.75,
                "semantic_only_cap": 0.45,
                "cfg_high_score_bypass": True
            },
            "deep_verify": {
                "tree_kernel_min": 0.60,
                "ast_normalized_min": 0.45,
                "cfg_similarity_min": 0.50,
                "minimum_agreeing_engines": 3,
                "minimum_agreeing_engines_high_score": 2,
                "final_confidence_floor": 0.65,
                "false_positive_safety_cap": 0.58,
                "cfg_bypass_enabled": True,
                "cfg_bypass_threshold": 0.80
            },
            "decision": {
                "default_threshold": 0.78,
                "minimum_confidence": 0.4,
                "minimum_engine_agreement": 2
            },
            "thresholds": {
                "identical": 0.85,
                "high_similarity": 0.80,
                "medium_similarity": 0.62,
                "low_similarity": 0.35
            }
        }
        self._normalize_weights()
    
    @property
    def weights(self) -> Dict[str, float]:
        """Get normalized engine weights."""
        self.reload_if_changed()
        return self._config["weights"].copy()
    
    def get_weight(self, engine: str, default: float = 0.0) -> float:
        """Get weight for specific engine."""
        self.reload_if_changed()
        return self._config["weights"].get(engine, default)
    
    @property
    def deep_verify_thresholds(self) -> Dict[str, Any]:
        """Get DeepVerify thresholds configuration."""
        self.reload_if_changed()
        return self._config.get("deep_verify", {})
    
    @property
    def precision_guard(self) -> Dict[str, Any]:
        """Get precision guard configuration."""
        self.reload_if_changed()
        return self._config.get("precision_guard", {})
    
    @property
    def baselines(self) -> Dict[str, float]:
        """Get baseline correction values."""
        self.reload_if_changed()
        return self._config.get("baseline_correction", {}).get("baselines", {})
    
    @property
    def decision_thresholds(self) -> Dict[str, Any]:
        """Get decision thresholds."""
        self.reload_if_changed()
        return self._config.get("decision", {})
    
    @property
    def classification_thresholds(self) -> Dict[str, float]:
        """Get similarity classification thresholds."""
        self.reload_if_changed()
        return self._config.get("thresholds", {})
    
    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Update engine weights at runtime and persist to config file.
        
        Args:
            new_weights: Dictionary of engine name to new weight value
        """
        with self._lock:
            for engine, weight in new_weights.items():
                if engine in self.valid_engines:
                    self._config["weights"][engine] = max(0.0, min(1.0, weight))
            
            self._normalize_weights()
            
            # Persist to file
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
            
            logger.info("Engine weights updated and persisted")
    
    def get_enabled_engines(self) -> List[str]:
        """Get list of engines with non-zero weight."""
        return [engine for engine, weight in self.weights.items() if weight > 0.001]


# Convenience accessors
def get_engine_weights() -> Dict[str, float]:
    """Get current normalized engine weights."""
    return EngineWeightConfig.get_instance().weights

def get_engine_weight(engine: str, default: float = 0.0) -> float:
    """Get weight for a specific engine."""
    return EngineWeightConfig.get_instance().get_weight(engine, default)

def get_deep_verify_config() -> Dict[str, Any]:
    """Get DeepVerify configuration."""
    return EngineWeightConfig.get_instance().deep_verify_thresholds
