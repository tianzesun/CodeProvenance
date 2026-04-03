"""Main dataset generation pipeline.

Builds a publishable benchmark dataset with:
- Type-1 (exact clones)
- Type-2 (renamed clones)
- Type-3 (structural clones)
- Type-4 (semantic clones) with Easy/Medium/Hard
- Negative samples (easy and hard)

All results are deterministic and reproducible.
"""
from __future__ import annotations

import json
import random
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.generators.base_loader import CodePool
from benchmark.generators.type1_exact import generate_type1_clone
from benchmark.generators.type2_rename import generate_type2_clone
from benchmark.generators.type3_structure import generate_type3_clone
from benchmark.generators.type4_semantic import generate_type4_clone
from benchmark.generators.negatives import generate_negative_pair
from benchmark.generators.utils.ast_utils import count_lines, count_tokens


class DatasetBuilder:
    """Builds benchmark dataset according to configuration.
    
    Generates pairs with proper labeling and metadata.
    """
    
    def __init__(self, config_path: str = "benchmark/config/dataset_config.yaml"):
        """Initialize the dataset builder.
        
        Args:
            config_path: Path to configuration file.
        """
        self.config = self._load_config(config_path)
        self.seed = self.config.get("seed", 42)
        self.rng = random.Random(self.seed)
        self.pool = CodePool(seed=self.seed)
        
        # Statistics
        self.stats = {
            "type1": 0,
            "type2": 0,
            "type3": 0,
            "type4_easy": 0,
            "type4_medium": 0,
            "type4_hard": 0,
            "negative_easy": 0,
            "negative_hard": 0,
        }
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file.
            
        Returns:
            Configuration dictionary.
        """
        path = Path(config_path)
        if not path.exists():
            print(f"Warning: Config file {config_path} not found. Using defaults.")
            return self._default_config()
        
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration.
        
        Returns:
            Default configuration dictionary.
        """
        return {
            "seed": 42,
            "languages": ["python"],
            "dataset": {"total_pairs": 4000},
            "distribution": {
                "type1": 200,
                "type2": 200,
                "type3": 200,
                "type4_easy": 200,
                "type4_medium": 200,
                "type4_hard": 200,
                "negative_easy": 400,
                "negative_hard": 400,
            },
            "constraints": {
                "min_tokens": 20,
                "max_tokens": 300,
                "min_lines": 5,
                "max_lines": 50,
            },
        }
    
    def build(self) -> List[Dict[str, Any]]:
        """Build the complete dataset.
        
        Returns:
            List of dataset pairs with metadata.
        """
        print("=" * 70)
        print("  Building Benchmark Dataset v2")
        print("=" * 70)
        
        dataset = []
        distribution = self.config.get("distribution", {})
        constraints = self.config.get("constraints", {})
        
        # Generate Type-1 pairs
        print("\n[1/7] Generating Type-1 (Exact) clones...")
        n_type1 = distribution.get("type1", 200)
        for i in range(n_type1):
            code = self.pool.sample()
            clone = generate_type1_clone(code, seed=self.seed + i)
            
            if self._validate_pair(code, clone, constraints):
                dataset.append(self._create_pair(
                    code_a=code,
                    code_b=clone,
                    label=1,
                    clone_type="type1",
                    difficulty="easy",
                    metadata={"pair_index": i}
                ))
                self.stats["type1"] += 1
        
        print(f"      Generated {self.stats['type1']} Type-1 pairs")
        
        # Generate Type-2 pairs
        print("\n[2/7] Generating Type-2 (Renamed) clones...")
        n_type2 = distribution.get("type2", 200)
        for i in range(n_type2):
            code = self.pool.sample()
            clone = generate_type2_clone(code, seed=self.seed + i)
            
            if self._validate_pair(code, clone, constraints):
                dataset.append(self._create_pair(
                    code_a=code,
                    code_b=clone,
                    label=1,
                    clone_type="type2",
                    difficulty="easy",
                    metadata={"pair_index": i}
                ))
                self.stats["type2"] += 1
        
        print(f"      Generated {self.stats['type2']} Type-2 pairs")
        
        # Generate Type-3 pairs
        print("\n[3/7] Generating Type-3 (Structural) clones...")
        n_type3 = distribution.get("type3", 200)
        for i in range(n_type3):
            code = self.pool.sample()
            clone = generate_type3_clone(code, seed=self.seed + i)
            
            if self._validate_pair(code, clone, constraints):
                dataset.append(self._create_pair(
                    code_a=code,
                    code_b=clone,
                    label=1,
                    clone_type="type3",
                    difficulty="medium",
                    metadata={"pair_index": i}
                ))
                self.stats["type3"] += 1
        
        print(f"      Generated {self.stats['type3']} Type-3 pairs")
        
        # Generate Type-4 Easy pairs
        print("\n[4/7] Generating Type-4 Easy (Semantic) clones...")
        n_type4_easy = distribution.get("type4_easy", 200)
        for i in range(n_type4_easy):
            code = self.pool.sample()
            clone = generate_type4_clone(code, difficulty="easy", seed=self.seed + i)
            
            if self._validate_pair(code, clone, constraints):
                dataset.append(self._create_pair(
                    code_a=code,
                    code_b=clone,
                    label=1,
                    clone_type="type4_easy",
                    difficulty="medium",
                    metadata={"pair_index": i}
                ))
                self.stats["type4_easy"] += 1
        
        print(f"      Generated {self.stats['type4_easy']} Type-4 Easy pairs")
        
        # Generate Type-4 Medium pairs
        print("\n[5/7] Generating Type-4 Medium (Semantic) clones...")
        n_type4_medium = distribution.get("type4_medium", 200)
        for i in range(n_type4_medium):
            code = self.pool.sample()
            clone = generate_type4_clone(code, difficulty="medium", seed=self.seed + i)
            
            if self._validate_pair(code, clone, constraints):
                dataset.append(self._create_pair(
                    code_a=code,
                    code_b=clone,
                    label=1,
                    clone_type="type4_medium",
                    difficulty="hard",
                    metadata={"pair_index": i}
                ))
                self.stats["type4_medium"] += 1
        
        print(f"      Generated {self.stats['type4_medium']} Type-4 Medium pairs")
        
        # Generate Type-4 Hard pairs
        print("\n[6/7] Generating Type-4 Hard (Semantic) clones...")
        n_type4_hard = distribution.get("type4_hard", 200)
        for i in range(n_type4_hard):
            code = self.pool.sample()
            clone = generate_type4_clone(code, difficulty="hard", seed=self.seed + i)
            
            if self._validate_pair(code, clone, constraints):
                dataset.append(self._create_pair(
                    code_a=code,
                    code_b=clone,
                    label=1,
                    clone_type="type4_hard",
                    difficulty="very_hard",
                    metadata={"pair_index": i}
                ))
                self.stats["type4_hard"] += 1
        
        print(f"      Generated {self.stats['type4_hard']} Type-4 Hard pairs")
        
        # Generate Negative pairs
        print("\n[7/7] Generating Negative (Non-clone) pairs...")
        n_neg_easy = distribution.get("negative_easy", 400)
        n_neg_hard = distribution.get("negative_hard", 400)
        
        # Easy negatives
        for i in range(n_neg_easy):
            code_a, code_b = generate_negative_pair(
                self.pool, difficulty="easy", seed=self.seed + i
            )
            
            if self._validate_pair(code_a, code_b, constraints):
                dataset.append(self._create_pair(
                    code_a=code_a,
                    code_b=code_b,
                    label=0,
                    clone_type="negative_easy",
                    difficulty="easy",
                    metadata={"pair_index": i}
                ))
                self.stats["negative_easy"] += 1
        
        # Hard negatives
        for i in range(n_neg_hard):
            base = self.pool.sample()
            code_a, code_b = generate_negative_pair(
                self.pool, difficulty="hard", seed=self.seed + i + n_neg_easy
            )
            
            if self._validate_pair(code_a, code_b, constraints):
                dataset.append(self._create_pair(
                    code_a=code_a,
                    code_b=code_b,
                    label=0,
                    clone_type="negative_hard",
                    difficulty="hard",
                    metadata={"pair_index": i}
                ))
                self.stats["negative_hard"] += 1
        
        print(f"      Generated {self.stats['negative_easy']} Easy + {self.stats['negative_hard']} Hard negative pairs")
        
        # Shuffle dataset
        self.rng.shuffle(dataset)
        
        # Add index to each pair
        for i, pair in enumerate(dataset):
            pair["id"] = f"pair_{i:05d}"
        
        return dataset
    
    def _validate_pair(
        self,
        code_a: str,
        code_b: str,
        constraints: Dict[str, Any],
    ) -> bool:
        """Validate that a pair meets constraints.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            constraints: Constraint dictionary.
            
        Returns:
            True if pair is valid, False otherwise.
        """
        min_tokens = constraints.get("min_tokens", 20)
        max_tokens = constraints.get("max_tokens", 300)
        min_lines = constraints.get("min_lines", 5)
        max_lines = constraints.get("max_lines", 50)
        
        tokens_a = count_tokens(code_a)
        tokens_b = count_tokens(code_b)
        lines_a = count_lines(code_a)
        lines_b = count_lines(code_b)
        
        return (
            min_tokens <= tokens_a <= max_tokens and
            min_tokens <= tokens_b <= max_tokens and
            min_lines <= lines_a <= max_lines and
            min_lines <= lines_b <= max_lines
        )
    
    def _create_pair(
        self,
        code_a: str,
        code_b: str,
        label: int,
        clone_type: str,
        difficulty: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a dataset pair with metadata.
        
        Args:
            code_a: First code snippet.
            code_b: Second code snippet.
            label: 1 for clone, 0 for non-clone.
            clone_type: Type of clone or "negative_*".
            difficulty: Difficulty level.
            metadata: Additional metadata.
            
        Returns:
            Dataset pair dictionary.
        """
        pair = {
            "code_a": code_a,
            "code_b": code_b,
            "label": label,
            "clone_type": clone_type,
            "difficulty": difficulty,
            "language": "python",
            "tokens_a": count_tokens(code_a),
            "tokens_b": count_tokens(code_b),
            "lines_a": count_lines(code_a),
            "lines_b": count_lines(code_b),
            "metadata": metadata or {},
        }
        
        return pair
    
    def save(self, dataset: List[Dict[str, Any]], output_path: str) -> None:
        """Save dataset to JSON file.
        
        Args:
            dataset: Dataset to save.
            output_path: Output file path.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        # Create dataset with metadata
        dataset_with_meta = {
            "version": "2.0",
            "generated_at": datetime.now().isoformat(),
            "seed": self.seed,
            "total_pairs": len(dataset),
            "distribution": self.stats,
            "config": self.config,
            "pairs": dataset,
        }
        
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(dataset_with_meta, f, indent=2)
        
        print(f"\n{'='*70}")
        print(f"  Dataset saved to: {output}")
        print(f"  Total pairs: {len(dataset)}")
        print(f"{'='*70}")
        print("\nDistribution:")
        for key, count in self.stats.items():
            print(f"  {key}: {count}")


def build_dataset(
    config_path: str = "benchmark/config/dataset_config.yaml",
    output_path: str = "benchmark/data/generated/dataset.json",
) -> None:
    """Build benchmark dataset.
    
    Args:
        config_path: Path to configuration file.
        output_path: Output file path.
    """
    builder = DatasetBuilder(config_path)
    dataset = builder.build()
    builder.save(dataset, output_path)


if __name__ == "__main__":
    import sys
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else "benchmark/config/dataset_config.yaml"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "benchmark/data/generated/dataset.json"
    
    build_dataset(config_path, output_path)