# AI-Generated Code Detection: Honest Benchmark Report

**Date:** 2026-08-12
**Dataset:** AIGCodeSet (Demirok & Kutlu, IEEE SIU 2025, arXiv:2412.16594)
**License:** CDLA Permissive v2.0

## What was done

1. **Acquired a real labeled dataset.** AIGCodeSet contains 2,795 AI-generated
   and 4,541 human-written Python samples (7,336 after dedup + length filter),
   produced by three LLMs (GEMINI, LLAMA, CODESTRAL) plus human CodeNet
   submissions. Materialised by `src/backend/engines/ai/build_aigcodeset.py`
   (data lives under `data/datasets/aigcodeset/`, gitignored per project
   convention; download via `data/datasets/aigcodeset/download.sh`).

2. **Trained the classifier.** `AICodeClassifier` (HistGradientBoosting, 23
   features = tree-sitter AST + stylometry + perplexity/burstiness) trained on
   all 7,336 samples; model saved under
   `src/backend/engines/ai/models/` (gitignored).

3. **Measured honestly** with `src/backend/engines/ai/benchmark_classifier.py`,
   using a **grouped holdout split by `problem_id`** so the same programming
   problem never appears in both train and test (prevents style-memorisation
   leakage).

## Results

### Grouped holdout (unseen problems, no leakage)

| Threshold | Accuracy | Precision | Recall | F1 | AUC |
|-----------|---------:|----------:|-------:|----:|----:|
| 0.50 (default) | 0.681 | 0.763 | 0.238 | 0.363 | 0.664 |
| 0.40 (medium risk) | 0.646 | 0.547 | 0.425 | 0.478 | 0.664 |
| 0.70 (high risk) | 0.666 | 0.874 | 0.146 | 0.251 | 0.664 |

### Heuristic vs ML (same unseen test fold)

| Method | Accuracy | Precision | Recall | F1 | AUC |
|--------|---------:|----------:|-------:|----:|----:|
| Heuristic only (current default) | 0.472 | 0.402 | 0.785 | 0.531 | 0.524 |
| Trained ML classifier | 0.681 | 0.763 | 0.238 | 0.363 | 0.664 |

### Per-generator sensitivity (unseen problems)

| Generator | Precision | Recall | AUC |
|-----------|----------:|-------:|----:|
| GEMINI | 0.354 | 0.120 | 0.597 |
| LLAMA | 0.558 | 0.283 | 0.676 |
| CODESTRAL | 0.584 | 0.312 | 0.720 |

## Interpretation (honest)

- **The ML classifier is a real but modest improvement** over the heuristic on
  unseen problems: AUC 0.664 vs 0.524. It does *not* "compete with Turnitin" —
  Turnitin-class accuracy (claimed >0.95 AUC on its own prose data) is far
  above what this feature set achieves on code.
- **The classifier trades recall for precision.** At the default 0.5 threshold
  it catches only ~24% of AI samples (too many false negatives); at 0.40 it
  catches ~43% but flags ~45% of human code as AI (false-positive risk). The
  heuristic has the opposite bias (78% recall, 40% precision).
- **Domain mismatch is the biggest problem.** AIGCodeSet is competitive-
  programming style. On short, terse *student* code — the product's main input —
  the trained classifier **raises false positives vs the tuned heuristics**
  (verified: it broke 3 regression tests in
  `test_ai_detector_orchestrator_precision.py`). Because of this, the ML
  classifier is **disabled by default** (`ai_ensemble_config.yaml`).
- **The transformer perplexity path is not usable here**: the locally cached
  `microsoft/codebert-base` is tokenizer-only (no weights), and no LLM API key
  is configured, so statistical bigram perplexity is the only option. A real
  code LM would be the single highest-value next step.
- **Takeaway:** the pipeline (data → features → train → grouped-eval) now
  exists, is reproducible, and produces honest numbers. Becoming competitive
  requires (a) a code-LM perplexity signal, (b) a labelled dataset matching the
  actual student-code distribution, and (c) an external holdout — all now
  instrumented and one dataset/re-run away.

## Reproduce

```bash
bash data/datasets/aigcodeset/download.sh
python -m src.backend.engines.ai.build_aigcodeset
python -m src.backend.engines.ai.benchmark_classifier   # writes benchmark_report.json
```
