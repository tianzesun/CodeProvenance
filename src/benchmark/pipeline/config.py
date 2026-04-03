"""Benchmark configuration specification.

Single config object that defines the entire pipeline behavior.
All runs are defined by this config - explicit configuration.
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import hashlib


@dataclass
class DatasetConfig:
    """Dataset configuration."""
    name: str = "bigclonebench"
    version: str = "1.0"
    path: str = ""


@dataclass
class EngineConfig:
    """Similarity engine configuration."""
    name: str = "hybrid"
    version: str = "1.0"


@dataclass
class NormalizerConfig:
    """Code normalizer configuration."""
    type: str = "moss"


@dataclass
class ParserConfig:
    """Code parser configuration."""
    type: str = "ast"
    max_ast_depth: int = 10


@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation mode configuration."""
    mode: str = "pairwise"  # pairwise | ranking


@dataclass
class MetricsConfig:
    """Metrics to compute."""
    metrics: List[str] = field(default_factory=lambda: [
        "precision", "recall", "f1", "accuracy", "map", "mrr"
    ])


@dataclass(frozen=True)
class ThresholdConfig:
    """Threshold optimization configuration."""
    optimize: bool = True
    strategy: str = "f1_max"  # f1_max | precision_fixed | recall_fixed


@dataclass(frozen=True)
class OutputConfig:
    """Output format configuration."""
    json: bool = True
    html: bool = False
    leaderboard: bool = True


@dataclass
class BenchmarkConfig:
    """Master benchmark configuration.
    
    This is the heart of reproducibility.
    Every run is fully defined by this config object.
    
    Usage:
        config = BenchmarkConfig(
            dataset=DatasetConfig(name="bigclonebench", version="v1"),
            engine=EngineConfig(name="hybrid", version="v1"),
            normalizer=NormalizerConfig(type="moss"),
            parser=ParserConfig(type="ast"),
            evaluation=EvaluationConfig(mode="pairwise"),
            metrics=MetricsConfig(metrics=["precision", "recall", "f1", "map", "mrr"]),
            threshold=ThresholdConfig(optimize=True, strategy="f1_max"),
            output=OutputConfig(json=True, html=True, leaderboard=True)
        )
    """
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    normalizer: NormalizerConfig = field(default_factory=NormalizerConfig)
    parser: ParserConfig = field(default_factory=ParserConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    def config_hash(self) -> str:
        """Compute deterministic hash of this config.
        
        Returns:
            SHA256 hash string for reproducibility tracking.
        """
        import json
        config_dict = {
            "dataset": {"name": self.dataset.name, "version": self.dataset.version},
            "engine": {"name": self.engine.name, "version": self.engine.version},
            "normalizer": {"type": self.normalizer.type},
            "parser": {"type": self.parser.type, "max_ast_depth": self.parser.max_ast_depth},
            "evaluation": {"mode": self.evaluation.mode},
            "metrics": self.metrics.metrics,
            "threshold": {"optimize": self.threshold.optimize, "strategy": self.threshold.strategy},
            "output": {"json": self.output.json, "html": self.output.html, "leaderboard": self.output.leaderboard}
        }
        config_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "BenchmarkConfig":
        """Create config from dictionary.
        
        Args:
            config_dict: Configuration dictionary.
            
        Returns:
            BenchmarkConfig instance.
        """
        d = config_dict
        return cls(
            dataset=DatasetConfig(
                name=d.get("dataset", {}).get("name", "bigclonebench"),
                version=d.get("dataset", {}).get("version", "1.0"),
                path=d.get("dataset", {}).get("path", "")
            ),
            engine=EngineConfig(
                name=d.get("engine", {}).get("name", "hybrid"),
                version=d.get("engine", {}).get("version", "1.0")
            ),
            normalizer=NormalizerConfig(
                type=d.get("normalizer", {}).get("type", "moss")
            ),
            parser=ParserConfig(
                type=d.get("parser", {}).get("type", "ast"),
                max_ast_depth=d.get("parser", {}).get("max_ast_depth", 10)
            ),
            evaluation=EvaluationConfig(
                mode=d.get("evaluation", {}).get("mode", "pairwise")
            ),
            metrics=MetricsConfig(
                metrics=d.get("metrics", {}).get("metrics", [
                    "precision", "recall", "f1", "map", "mrr"
                ])
            ),
            threshold=ThresholdConfig(
                optimize=d.get("threshold", {}).get("optimize", True),
                strategy=d.get("threshold", {}).get("strategy", "f1_max")
            ),
            output=OutputConfig(
                json=d.get("output", {}).get("json", True),
                html=d.get("output", {}).get("html", False),
                leaderboard=d.get("output", {}).get("leaderboard", True)
            )
        )