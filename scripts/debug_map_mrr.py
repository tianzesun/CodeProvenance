#!/usr/bin/env python
"""Debug MAP/MRR = 0 issue.

Run: ./venv/bin/python debug_map_mrr.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from benchmark.pipeline.external_loader import ExternalDatasetLoader
from benchmark.pipeline.stages import (
    EvaluationStage, MetricsStage, SimilarityResult
)

loader = ExternalDatasetLoader(data_root="data/datasets", seed=42)

print("=" * 70)
print("STEP 1: Check dataset ground truth")
print("=" * 70)

for name in ["poj104", "google_codejam", "kaggle"]:
    try:
        ds = loader.load_by_name(name, split="test", max_pairs=20)
        gt = ds.get_ground_truth()
        labels = list(gt.values())
        pos = sum(1 for l in labels if l == 1)
        neg = sum(1 for l in labels if l == 0)
        print(f"\n{name}:")
        print(f"  Pairs: {len(ds.pairs)}, Ground truth entries: {len(gt)}")
        print(f"  Positive: {pos}, Negative: {neg}")
        if pos > 0:
            for p in ds.pairs:
                if p.label == 1:
                    print(f"  Sample positive: id_a={p.id_a!r}, id_b={p.id_b!r}, label={p.label}")
                    print(f"  GT key exists: {(p.id_a, p.id_b) in gt} -> value={gt.get((p.id_a, p.id_b), 'MISSING')}")
                    break
    except Exception as e:
        print(f"\n{name}: ERROR - {e}")

print("\n" + "=" * 70)
print("STEP 2: Run benchmark and trace labels through pipeline")
print("=" * 70)

try:
    ds = loader.load_by_name("poj104", split="test", max_pairs=20)
    gt = ds.get_ground_truth()
    
    print(f"\nDataset: {ds.name}, {len(ds.pairs)} pairs")
    print(f"Ground truth: {sum(1 for v in gt.values() if v==1)} positive, {sum(1 for v in gt.values() if v==0)} negative")
    
    # Show sample GT keys
    print(f"\nSample GT keys (first 3):")
    for i, (k, v) in enumerate(gt.items()):
        if i >= 3:
            break
        print(f"  {k} -> {v}")
    
    from benchmark.pipeline import BenchmarkRunner, BenchmarkConfig
    from benchmark.pipeline.config import EngineConfig, OutputConfig, ThresholdConfig
    
    runner = BenchmarkRunner(seed=42)
    config = BenchmarkConfig(
        engine=EngineConfig(name="hybrid"),
        threshold=ThresholdConfig(optimize=True),
        output=OutputConfig(json=False, html=False, leaderboard=False),
    )
    result = runner.run(ds, config)
    
    if result.success:
        m = result.metrics
        print(f"\n{'=' * 70}")
        print("STEP 3: Final metrics")
        print(f"{'=' * 70}")
        print(f"  Precision: {m.precision:.4f}")
        print(f"  Recall:    {m.recall:.4f}")
        print(f"  F1:        {m.f1:.4f}")
        print(f"  MAP:       {m.map_score:.4f}")
        print(f"  MRR:       {m.mrr_score:.4f}")
        print(f"  TP={m.tp} FP={m.fp} TN={m.tn} FN={m.fn}")
        
        # Manually trace through evaluation
        print(f"\n{'=' * 70}")
        print("STEP 4: Manual label trace through EvaluationStage")
        print(f"{'=' * 70}")
        
        # Simulate what EvaluationStage does
        # We need the raw results from the similarity stage
        # Since we can't easily get them, let's check if the issue is in MetricsStage
        
        # Create mock results to test MetricsStage
        print("\nTesting MetricsStage with mock data...")
        
        # Case 1: Each pair is independent (unique id_a per pair)
        mock_results = [
            SimilarityResult(id_a="q1", id_b="d1", score=0.9, label=1),
            SimilarityResult(id_a="q1", id_b="d2", score=0.7, label=0),
            SimilarityResult(id_a="q1", id_b="d3", score=0.5, label=0),
            SimilarityResult(id_a="q2", id_b="d4", score=0.8, label=1),
            SimilarityResult(id_a="q2", id_b="d5", score=0.6, label=0),
            SimilarityResult(id_a="q3", id_b="d6", score=0.3, label=0),
        ]
        
        metrics_stage = MetricsStage()
        mock_metrics = metrics_stage.execute(mock_results, {"threshold": 0.5})
        print(f"  Mock (good data): MAP={mock_metrics.map_score:.4f}, MRR={mock_metrics.mrr_score:.4f}")
        
        # Case 2: Each pair has unique id_a (no grouping possible)
        mock_results2 = [
            SimilarityResult(id_a="q1", id_b="d1", score=0.9, label=1),
            SimilarityResult(id_a="q2", id_b="d2", score=0.8, label=1),
            SimilarityResult(id_a="q3", id_b="d3", score=0.3, label=0),
        ]
        mock_metrics2 = metrics_stage.execute(mock_results2, {"threshold": 0.5})
        print(f"  Mock (unique queries): MAP={mock_metrics2.map_score:.4f}, MRR={mock_metrics2.mrr_score:.4f}")
        
        # Case 3: All labels are 0
        mock_results3 = [
            SimilarityResult(id_a="q1", id_b="d1", score=0.9, label=0),
            SimilarityResult(id_a="q1", id_b="d2", score=0.7, label=0),
            SimilarityResult(id_a="q2", id_b="d3", score=0.8, label=0),
        ]
        mock_metrics3 = metrics_stage.execute(mock_results3, {"threshold": 0.5})
        print(f"  Mock (all zeros): MAP={mock_metrics3.map_score:.4f}, MRR={mock_metrics3.mrr_score:.4f}")
        
        print(f"\n{'=' * 70}")
        print("DIAGNOSIS")
        print(f"{'=' * 70}")
        if m.map_score == 0 and m.recall > 0:
            print("  MAP=0 but Recall>0 means:")
            print("  - True positives exist (classification works)")
            print("  - BUT no query has multiple results with relevant items")
            print("  - Most likely: each pair has unique id_a, so queries have only 1 result each")
            print("  - OR: positive pairs have id_a that doesn't group with any other pair")
            print("\n  FIX: For pairwise datasets, treat each positive pair as its own query")
            print("  with a single relevant result. AP=1.0, RR=1.0 for each.")
        else:
            print("  MAP and MRR are non-zero, or recall is also 0.")
            
except Exception as e:
    import traceback
    traceback.print_exc()
