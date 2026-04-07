"""
Distribution Engine - Core component for converting deterministic scores to distributions.

Generates controlled variations of code pairs and builds score distributions
across transformation space. This turns single-point observations into
statistically defensible measurements.
"""

from dataclasses import dataclass
from typing import Callable, List, Dict, Any
import numpy as np


@dataclass(frozen=True)
class ScoreDistribution:
    """Statistical distribution of similarity scores across perturbations."""
    mean: float
    std: float
    min: float
    max: float
    samples: List[float]

    @classmethod
    def from_samples(cls, samples: List[float]) -> 'ScoreDistribution':
        return cls(
            mean=float(np.mean(samples)),
            std=float(np.std(samples)),
            min=float(np.min(samples)),
            max=float(np.max(samples)),
            samples=samples
        )


class DistributionEngine:
    """
    Builds score distributions by applying controlled semantic-preserving
    transformations and re-running the detection tool.
    """

    def __init__(
        self,
        tool_runner: Callable[[str, str, str], float],
        transformer: Any,
        n_samples: int = 30
    ):
        """
        Args:
            tool_runner: Function that takes (tool_id, code_a, code_b) and returns score
            transformer: Code transformer that applies semantic preserving variations
            n_samples: Number of perturbation samples to generate
        """
        self.tool_runner = tool_runner
        self.transformer = transformer
        self.n_samples = n_samples

    def build_distribution(self, code_a: str, code_b: str, tool_id: str) -> ScoreDistribution:
        """
        Generate a full score distribution for a code pair under perturbation.

        Args:
            code_a: First source code file
            code_b: Second source code file
            tool_id: Identifier of detection tool to run

        Returns:
            ScoreDistribution with statistical properties
        """
        scores = []

        for _ in range(self.n_samples):
            a_transformed = self.transformer.apply_random(code_a)
            b_transformed = self.transformer.apply_random(code_b)

            score = self.tool_runner(tool_id, a_transformed, b_transformed)
            scores.append(score)

        return ScoreDistribution.from_samples(scores)

    def build_batch_distributions(
        self,
        pairs: List[Dict[str, str]],
        tool_id: str
    ) -> List[ScoreDistribution]:
        """Build distributions for multiple pairs in batch mode."""
        return [
            self.build_distribution(pair["code_a"], pair["code_b"], tool_id)
            for pair in pairs
        ]