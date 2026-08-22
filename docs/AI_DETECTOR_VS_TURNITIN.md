# AI Detector vs Turnitin — Capability Matrix & Gap Analysis

**Date:** 2026-08-14
**Author:** engineering
**Scope:** `src/backend/engines/ai/` (AI-generated code detection) compared with
Turnitin's AI writing detection product. Honest assessment — this is not a
claim of parity.

## Executive summary

The product ships a polished, explainable AI-detection workflow (per-submission
scorecards, signal breakdown, PDF export, flagged regions) but the underlying
detection science is **not world-class**. The live engine was a tuned heuristic
ensemble (8 signals) with grouped-holdout AUC **~0.52–0.55**; a trained ML
classifier reaches AUC **~0.66** but could not ship outright because it raises
false positives on short student code.

**Update (2026-08-21):** the classifier now ships **enabled** via the
orchestrator's safe-blend fusion — its weight is gated by code length and its
influence is capped when it disagrees with the explainable signals. Measured on
the leakage-free grouped fold: heuristic-only AUC 0.531 → safe blend **0.591**
(recall 0.824), with the precision regression suite green. The ML classifier
alone (AUC 0.664) remains unshippable standalone. See
`data/datasets/aigcodeset/BENCHMARK_REPORT.md` § "Safe-blend fusion evaluation".

Turnitin, by contrast, ships a validated detector with published language
coverage, sentence-level highlights, a non-native-English limitation, and
published false-positive targets (its own docs claim <1% FP on papers ≥20% AI;
independent studies put real-world FP at 5–20%). It is treated as a screening
signal, not an accusation.

## Capability matrix

Legend: **LIVE** = on in default production config · **DISABLED** = built but
off by default (`ai_ensemble_config.yaml`) · **PARTIAL** = works but limited ·
**MISSING** = not implemented.

| # | Capability | IntegrityDesk (ours) | Turnitin | Industry / par | Notes |
|---|-----------|---------------------|----------|----------------|-------|
| 1 | Core detection on prose/essays | **MISSING** | **LIVE** (98%-accuracy claim at ≥20% AI text; hides 1–19% band) | LIVE | Turnitin is a prose detector; ours is code-only. No essay input path. |
| 2 | Core detection on code | **LIVE** (heuristic) | PARTIAL (not Turnitin's focus) | LIVE | Ours: 8 signals + tree-sitter AST + statistical perplexity/burstiness. |
| 3 | ML classifier | **LIVE** (safe-blend fusion, 2026-08-21) | **LIVE** (validated) | LIVE | Ours: blended with heuristics behind a length gate + disagreement cap; blend AUC 0.591 vs heuristic 0.531, ML alone 0.664. |
| 4 | Transformer (causal code-LM) perplexity | **LIVE** (default-on, 2026-08-21) | n/a | LIVE | `PerplexityScorer` uses CodeGPT-small-py (AUC 0.63 vs 0.545 statistical), loaded once per process and shared across jobs; falls back to the statistical model when the checkpoint is not cached locally. Enabled by making AI detection a background job. |
| 5 | Sentence/region-level highlights | **LIVE** (flagged code regions) | **LIVE** (sentence-level) | LIVE | Ours: annotated code + per-signal evidence. |
| 6 | % AI score per submission | **LIVE** | **LIVE** (0–100, hides <20%) | LIVE | Ours shows raw 0–100; Turnitin hides 1–19% to cut false positives. |
| 7 | Scorecard / evidence detail | **LIVE** | PARTIAL | BEST | Ours shows per-signal signal values (entropy, burstiness, stylometry…) — more explainable than Turnitin. |
| 8 | Calibration confidence / trust indicator | **LIVE** | PARTIAL | BEST | Ours: `ScoreCalibrator` (learned legacy calibrator) + `highest_signal` + `calibration_confidence`. |
| 9 | Batch / multi-file upload | **LIVE** | **LIVE** | **LIVE** | Ours: zip + multi-file, per-file scorecards. |
| 10 | PDF / report export | **LIVE** | **LIVE** | **LIVE** | Ours: per-submission scorecards + PDF export. |
| 11 | History / institutional review trail | **LIVE** | **LIVE** | **LIVE** | Ours: jobs + `/ai-detector/results/[id]`. |
| 12 | Language coverage (detection) | **PARTIAL** | prose: English + others | — | Frontend advertises `.kt`/`.swift`; signals are Python-weighted (AST extractor tuned for Python; other languages fall back to generic signals). **2026-08-14:** tree-sitter AST now parses all advertised languages (Python/Java/C/C++/C#/JS/TS/Go/Rust); fixed TypeScript loader resolving `language_typescript` (was silently falling back to lexical). Kotlin/Swift remain lexical-only (bindings not installed). |
| 13 | Non-native-English / L2 caveat handling | MISSING (n/a, code) | **LIVE** (documented L2 limitation) | BEST | For code the analogue is "non-expert student style"; not modeled. |
| 14 | Adversarial / obfuscation resistance testing | **MISSING** | partial | par | No test suite for paraphrasing/refactoring/comment-stripping attacks on our detector. |
| 15 | Published false-positive-rate targets | **DISABLED** (numbers exist, not surfaced) | **LIVE** (<1% claimed at ≥20% AI; independent: 5–20%) | par | Our real FP numbers exist in `data/datasets/aigcodeset/benchmark_report.json`; not shown in product until the benchmark page ships. |
| 16 | External holdout beyond one dataset | **DISABLED** | **LIVE** | par | We rely on AIGCodeSet (single dataset, competitive-programming style). FPR validation UI exists (`/tools/fpr-validation`). |
| 17 | Score-as-signal framing (not proof) | **LIVE** | **LIVE** | BEST | Both explicitly tell users not to treat scores as sole basis for action. |
| 18 | Binoculars / open detection SOTA | MISSING (not installed) | n/a | optional | Not installed in `requirements.txt`. |
| 19 | Per-generator calibration (GEMINI/LLAMA/CODESTRAL) | **DISABLED** (measured, not surfaced) | n/a | par | Measured: CODESTRAL AUC 0.72 > LLAMA 0.68 > GEMINI 0.60 on grouped holdout. |
| 20 | Model versioning & retrainability | **LIVE** | closed | — | `AICodeClassifier` content-derived version hash; `save`/`load`; `/api/ai-detect/retrain` exists. |

## Honest gaps that block "world-class"

1. **No prose/essay detection.** The biggest scope gap vs Turnitin. Admissible
   only because this is a code-integrity product.
2. **Live engine is still the weakest path, but improved.** The default config
   now runs the safe-blend fusion (AUC ~0.59 on the grouped fold, up from
   ~0.52 heuristic-only). The full ML classifier (0.66) and causal code-LM
   (0.63) remain stronger individually but cannot ship standalone: the
   classifier fails the short-code false-positive contract, and the code-LM
   costs ~6s/score on CPU against a synchronous endpoint.
3. **False-positive safety is why ML only ships blended.** On short terse
   student code, the trained classifier broke 3 precision regression tests
   (`test_ai_detector_orchestrator_precision.py`). The safe-blend fusion
   (length gate + disagreement cap, 2026-08-21) resolves this for the blended
   path; standalone enablement still requires a student-code distribution
   dataset + threshold tuning.
4. **Single-dataset validation.** All published accuracy numbers come from
   AIGCodeSet (competitive-programming style). Not representative of the
   product's real input (short assignment submissions). Needs an external
   student-code holdout.
5. **No adversarial-resistance suite.** No automated tests for paraphrase /
   comment-stripping / refactor attacks; a credulous humanizer would defeat the
   heuristic path.
6. **Language overclaim.** `.kt`/`.swift` advertised in the upload UI while the
   feature kit is Python-weighted — a correctness-of-claims issue. **Addressed
   (2026-08-14):** the upload page now qualifies that Kotlin/Swift get lexical +
   statistical signals only (no AST-structure signal) and treats those results
   as review indicators.

## What we did about this (this work item)

- Wrote this honest matrix instead of a marketing claim.
- Built an **accuracy-benchmark page** that surfaces the real numbers
  (grouped-holdout, per-generator, heuristic-vs-ML) directly in the product,
  with methodology disclosures — the same evidence Turnitin-style vendors
  publish, so reviewers can judge the detector on data rather than UI.
- Built the **student-code holdout ingestion pipeline** (folder/CSV/JSONL →
  benchmark format + `--dataset-dir`) so the single biggest blocker for
  enabling ML — a validated student-code dataset — becomes a data-acquisition
  problem, not a tooling problem.

## Suggested ordering to close the gap

1. Enable ML classifier after validating on a student-code holdout (seed
   precision regression tests). **Partially done (2026-08-21):** the
   safe-blend fusion (length gate + disagreement cap) lets the classifier ship
   enabled with the precision suite green and blend AUC 0.591 on AIGCodeSet.
   Full standalone validation on a real student-code holdout is still the
   ceiling-raiser — the ingestion pipeline (`build_student_dataset.py`) is
   ready; the blocker is data, not tooling.
2. Wire causal code-LM perplexity (`huggingface_model`) for a default-on
   transformer signal. **Done (2026-08-21):** AI detection now runs as a
   background job (`/api/ai-detect` returns a job id immediately; the upload
   flow offloads scoring off the event loop), loaded models are cached
   process-wide, and `huggingface_model` defaults to CodeGPT-small-py with a
   graceful statistical fallback when the checkpoint is not cached.
3. Build adversarial-resistance tests (paraphrase, comment-strip, refactor).
   **Done (2026-08-14):** `tests/unit/test_ai_detector_adversarial.py`.
4. Document per-language support honestly (drop/qualify `.kt`/`.swift` claims).
   **Done (2026-08-14):** upload page qualifies Kotlin/Swift as lexical-only.
5. Only then consider prose/essay detection and Binoculars.