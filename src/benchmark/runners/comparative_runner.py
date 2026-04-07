"""Comparative benchmark runner - Before vs After Canonicalization."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.benchmark.datasets.synthetic_generator import SyntheticDatasetGenerator
from src.benchmark.similarity.engines import TokenWinnowingEngine, ASTEngine, HybridEngine
from src.benchmark.normalizer.canonicalizer import CanonicalComparePipeline, Canonicalizer


class ComparativeBenchmarkRunner:
    """Comparative benchmark runner."""

    def __init__(self, output_dir: str = "reports/comparative"):
        self.output_dir = output_dir

    def run(
        self,
        type1: int = 30,
        type2: int = 30,
        type3: int = 30,
        type4: int = 30,
        non_clone: int = 100,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Run comparative benchmark."""
        generator = SyntheticDatasetGenerator(seed=seed)
        dataset = generator.generate_pair_count(type1, type2, type3, type4, non_clone)

        base_engines = {
            "token": TokenWinnowingEngine(),
            "ast": ASTEngine(),
            "hybrid": HybridEngine(),
        }

        canonicalizer = Canonicalizer()
        canon_engines = {
            f"{name}_canon": CanonicalComparePipeline(engine, canonicalizer)
            for name, engine in base_engines.items()
        }

        all_engines: Dict[str, Any] = {**base_engines, **canon_engines}
        results: Dict[str, Dict[str, Any]] = {}

        for engine_name, engine in all_engines.items():
            tp = fp = tn = fn = 0
            type_tp: Dict[int, int] = {}
            type_fn: Dict[int, int] = {}

            for pair in dataset.pairs:
                score = engine.compare(pair.code_a, pair.code_b)
                predicted = 1 if score >= 0.5 else 0

                if predicted == 1 and pair.label == 1:
                    tp += 1
                    type_tp[pair.clone_type] = type_tp.get(pair.clone_type, 0) + 1
                elif predicted == 0 and pair.label == 0:
                    tn += 1
                elif predicted == 1 and pair.label == 0:
                    fp += 1
                else:
                    fn += 1
                    type_fn[pair.clone_type] = type_fn.get(pair.clone_type, 0) + 1

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

            type_pairs: Dict[int, int] = {}
            for p in dataset.pairs:
                if p.label == 1:
                    type_pairs[p.clone_type] = type_pairs.get(p.clone_type, 0) + 1

            type_recall: Dict[int, float] = {}
            for ct, total in type_pairs.items():
                ct_tp = type_tp.get(ct, 0)
                type_recall[ct] = ct_tp / total if total > 0 else 0.0

            results[engine_name] = {
                "tp": tp, "fp": fp, "tn": tn, "fn": fn,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "type_recall": {k: round(v, 4) for k, v in sorted(type_recall.items())},
            }

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        comprehensive = {
            "run_id": f"comparative_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "overall": results,
        }

        report_file = output_path / f"{comprehensive['run_id']}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(comprehensive, f, indent=2)

        return comprehensive