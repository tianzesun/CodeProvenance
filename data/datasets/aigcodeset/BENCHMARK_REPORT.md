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
  `microsoft/codebert-base` is encoder-only (`RobertaModel`, no LM head), so
  `AutoModelForMaskedLM` silently builds a *random* head and its perplexity is
  noise. A real causal code LM is required — see the code-LM evaluation below.
- **Takeaway:** the pipeline (data → features → train → grouped-eval) now
  exists, is reproducible, and produces honest numbers. Becoming competitive
  requires (a) a code-LM perplexity signal, (b) a labelled dataset matching the
  actual student-code distribution, and (c) an external holdout — all now
  instrumented and one dataset/re-run away.

## Code-LM signal evaluation (2026-08-13)

**Motivation.** The statistical bigram perplexity replaces the code-LM signal
the field uses. The locally cached `microsoft/codebert-base` (and
`microsoft/unixcoder-base`) are encoder-only checkpoints with **no LM head**, so
loading them as a masked LM gives perplexity from a randomly-initialised head —
verified `lm_head.*` keys are absent from `pytorch_model.bin`. `PerplexityScorer`
now loads a **causal** code LM instead (`AutoModelForCausalLM`), which both has a
trained head and scores a whole window in one forward pass (no per-token masking
loop).

**Model.** `microsoft/CodeGPT-small-py` (124M GPT-2, ~500MB, downloaded to the
HF cache; CPU-only this environment). A causal next-token perplexity is
computed per 25-line window.

**Controlled comparison.** Same stratified 500-sample subset (190 AI / 309
human), same grouped-fold methodology, only the perplexity source changes. Full
metrics in `benchmark_report.statistical.json` and
`benchmark_report.codelm.json`.

| Perplexity source | Accuracy | Precision | Recall | F1 | AUC |
|-------------------|---------:|----------:|-------:|----:|----:|
| Statistical bigram (baseline) | 0.616 | 0.412 | 0.200 | 0.269 | 0.545 |
| Causal code-LM (CodeGPT-small-py) | 0.657 | 0.524 | 0.314 | 0.393 | 0.630 |

Raw signal separation (same 40-code probe): AI mean ppl **133** vs human **323**.

**Honest reading.** The code-LM signal is a real, measurable improvement
(+0.085 AUC on grouped holdout) and now runs on CPU at ~1s/sample — a full
7,336-sample feature build is feasible in hours, not the ~143 CPU-hours the
masked-LM approach implied. It does **not** close the gap to Turnitin-class
accuracy, improves recall mostly at the 0.40 threshold, and the ML classifier
remains **disabled by default** pending the short-code false-positive regression
being resolved. The remaining bottleneck is no longer compute — it is having a
causal code LM (or larger model) enabled in a production deployment.

## Safe-blend fusion evaluation (2026-08-21)

The classifier is now enabled in production via the orchestrator's
**safe-blend fusion** (see `orchestrator.blend_ml_heuristic`): the classifier's
weight grows with code length (its features misfire on short files), and when
it calls AI while the explainable signals call human, the fused score is
capped below the 0.70 high-risk threshold. This is what allows
`classification.enabled: true` without breaking the precision regression suite
(`tests/unit/test_ai_detector_orchestrator_precision.py`, 7/7 green).

Same leakage-free grouped fold (n=1,467), production blend formula; the ML
input is the holdout-trained classifier probability (documented approximation
of the live ml-mode ensemble score):

| Fusion path | Accuracy | Precision | Recall | F1 | AUC |
|-------------|---------:|----------:|-------:|----:|----:|
| Heuristic only (previous default) | 0.416 | 0.388 | 0.919 | 0.545 | 0.531 |
| ML classifier alone (unshippable) | 0.681 | 0.763 | 0.238 | 0.363 | 0.664 |
| **Safe blend (shipped)** | **0.491** | **0.416** | **0.824** | **0.553** | **0.591** |
| Safe blend @ 0.40 review threshold | 0.406 | 0.390 | 0.988 | 0.559 | 0.591 |
| Safe blend @ 0.70 high-risk threshold | 0.621 | 0.833 | 0.009 | 0.018 | 0.591 |

**Honest reading.** The blend recovers roughly half the ML classifier's AUC
advantage over the heuristic (+0.060 of the +0.133 gap) while keeping recall
high (0.824) — the length gate and disagreement cap cost raw accuracy by
design, because the classifier alone (0.238 recall at 0.763 precision) fails
the product's false-positive contract on short student code. The
high-risk band stays high-precision (0.833). The disagreement cap fired on 0
of 1,467 fold samples — it is a guardrail against extreme misfires, not a
routine adjustment. Full metrics: `safe_blend_comparison` in
`benchmark_report.json`.

## Reproduce

```bash
bash data/datasets/aigcodeset/download.sh
python -m src.backend.engines.ai.build_aigcodeset
python -m src.backend.engines.ai.benchmark_classifier   # writes benchmark_report.json
```
