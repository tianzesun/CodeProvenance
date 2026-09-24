# CodeProvenance Benchmark — Canonical Structure

**Status:** specification (2026-09-24) · **Owner:** engineering
**Purpose:** single canonical tree for AI-generated-code detection evaluation,
so every accuracy claim traces to a reproducible split. Complements
`docs/HUMAN_FP_BASELINE.md` (measured numbers) and `docs/AI_HOLDOUT_COLLECTION.md`
(acquisition checklist).

## Canonical tree

```
CodeProvenance Benchmark
│
├── 1. Detection Performance          (labelled, grouped-holdout)
│   ├── TPR / Recall                  P(flagged | AI)
│   ├── FPR (in-lab)                  P(flagged | human, same dataset)
│   ├── Precision                     P(AI | flagged)
│   ├── F1                            harmonic mean of Precision/Recall
│   ├── ROC-AUC                       discrimination over all thresholds
│   └── PR-AUC                        Average Precision (preferred under class imbalance)
│
├── 2. False Positive Validation
│   ├── 2a. Synthetic Human Code      human split of AIGCodeSet (in-lab FPR)
│   └── 2b. Real-World FPR Validation human corpora NEVER used in training/tuning
│       ├── novice student Python     Kaggle student corpus (n=174, current baseline)
│       ├── student Java              IR-Plag originals (n=7, thin — expand)
│       └── community Python          PoolC sample (contrast group, non-student)
│
├── 3. Robustness (adversarial)
│   ├── Refactoring                   rename / restructure / comment-strip
│   ├── Code completion               partial-AI (prefix-human + suffix-AI) — MISSING
│   ├── AI-assisted / lightly-edited  tool-assisted, paraphrased logic — PARTIAL
│   └── Mixed human + AI              interleaved authorship — MISSING
│
└── 4. Generalization (cross-language)
    ├── Python                        measured (AIGCodeSet / Kaggle / PoolC)
    ├── Java                          thin (IR-Plag n=7 human-only, no AI side)
    ├── C/C++                         MISSING for AI detection
    ├── JavaScript                    MISSING for AI detection
    └── Other                         .go/.rs/.kt/.swift — lexical-only, unvalidated
```

Section name is deliberately **"Real-World FPR Validation"** (§2b), not
"Real FPR": it signals an independently collected, verified human-code dataset.

## Metric definitions (AI = positive class)

| Metric | Formula | Where computed today |
| --- | --- | --- |
| TPR / Recall | TP / (TP + FN) | `benchmark/evaluation/metrics/basic.py::recall`, `benchmark_classifier.py::_metrics` |
| FPR | FP / (FP + TN) | derivable from confusion counts, **not a named metric — GAP** |
| Precision | TP / (TP + FP) | `basic.py::precision` |
| F1 | 2PR / (P + R) | `basic.py::f1_score` |
| ROC-AUC | P(score_AI > score_human) | `evaluation/metrics/roc_auc.py::compute_roc_auc`, grouped fold |
| PR-AUC | Average Precision | `roc_auc.py::compute_average_precision` exists, **not surfaced — GAP** |

Related but distinct: `scripts/measure_human_fp.py` reports
**flag rates at fixed thresholds** (FP@0.40/0.50/0.70) on human-only corpora —
that is §2b output (no AI side exists, so Precision/Recall/AUC are undefined
there). Do not confuse it with §1 FPR.

## Coverage map (honest, 2026-09-24)

| Branch | Status | Evidence |
| --- | --- | --- |
| §1 Detection Performance (Python) | LIVE | `benchmark_classifier.py` grouped holdout + `benchmark_report.json`; on `/ai-detector/accuracy` |
| §1 FPR (in-lab, named) | GAP | confusion counts exist; no first-class `fpr` field in `compute_metrics_from_confusion` or report |
| §1 PR-AUC surfaced | GAP | `compute_average_precision` exists; report + accuracy page show ROC-AUC only |
| §2a Synthetic human FPR | LIVE | AIGCodeSet human split inside grouped fold |
| §2b Real-World FPR (Python novice) | LIVE with caveats | `scripts/measure_human_fp.py` + `HUMAN_FP_BASELINE.md`; recalibrated FP@0.70 2.3% (2026-09-21) |
| §2b Real-World FPR (Java / other) | THIN/MISSING | IR-Plag n=7 Java human-only; no labelled student holdout yet |
| §3 Refactoring | PARTIAL | `tests/unit/test_ai_detector_adversarial.py` (unit) but no scored suite with flag-rate deltas |
| §3 Completion / mixed | MISSING | no partial-AI or interleaved-authorship datasets |
| §4 Python | LIVE | see §1/§2b |
| §4 Java/C++/JS/Other (AI side) | MISSING | similarity side has multi-lang sets (CodeXGLUE/BigCloneBench); AI detector has no AI-labelled non-Python set |

Two caveats that keep §2b credible:

1. Kaggle-174 is human **by dataset construction, not per-file ground truth**
   (`HUMAN_FP_BASELINE.md` caveats). It anchors the current number but does
   not replace the labelled institutional holdout.
2. Post-2026-09-21 diagnosis: the raw classifier is **worse than chance
   AI-vs-novice-human (AUC 0.382)** — novice student code scores *more*
   AI-like than AIGCodeSet AI. Recovering recall needs classifier retraining
   on mixed novice-human corpora, not threshold relaxation.

## Real-World FPR Validation — lockout protocol (§2b)

This is the distinction that makes the benchmark credible. A §2b corpus is
admissible **iff**:

1. **Collected separately** from all training/tuning data (never in
   AIGCodeSet training, never in `ai_ensemble_config.yaml` tuning, never in
   precision-regression fixtures).
2. **Verified human** per file (provenance: pre-LLM-era archives, invigilated
   work, or instructor-verified; suspicion is not a label).
3. **Versioned and checksummed** (dataset dir + manifest; SHA-256 per file —
   same governance as `SCIENTIFIC_WHITE_PAPER.md` §5).
4. **Scored with the production path only** (`AIDetectionOrchestrator`, the
   object the background job runs) at the **frozen product thresholds**
   (0.40 / 0.50 / 0.70) via `scripts/measure_human_fp.py`.
5. **Reported as flag rates with n and score distribution**
   (mean/median/p90/max + per-file dump), never folded back into training.
6. Any file that later enters training is **struck from §2b** and the removal
   is logged in the corpus manifest.

The labelled institutional holdout (`AI_HOLDOUT_COLLECTION.md`, target
300+300, pilot 60–100) becomes the first fully-admissible §2b AI-paired set
when it lands; until then §2b is human-only flag rates, and §1 numbers must
carry the "AIGCodeSet alone cannot validate production input" disclosure
already on the accuracy page.

## What to build (ordered, small slices)

1. **Surface FPR + PR-AUC in §1** (half-day): add `fpr` to
   `compute_metrics_from_confusion`, thread through `benchmark_classifier._metrics`
   into `benchmark_report.json`, add columns to `/ai-detector/accuracy`.
   Pure reporting — no scoring change.
2. **Adopt this tree in product copy**: rename accuracy-page sections to
   §§1–4 headings; §2b labelled "Real-World FPR Validation" with lockout link.
3. **§3 robustness suite**: scored transforms (rename/restructure/comment-strip/
   paraphrase) with pre/post flag-rate deltas on a frozen AI set; completion +
   mixed-authorship sets after.
4. **§4 non-Python AI sets**: smallest credible step is an AI-paired Java set
   (IR-Plag human originals + matched LLM rewrites of the same prompts).
5. **Institutional holdout**: data acquisition (user-side), not code —
   `docs/STUDENT_DATA_REQUEST_PACK.md` is the packaged ask.

## Anti-goals (per BENCHMARK_SYSTEM.md rules)

- Never tune thresholds on a §2b corpus; it stops being a validation set.
- Never report §1 numbers without the grouped-holdout (no-leakage) note.
- Never present flag rates on human-only data as Precision/Recall/AUC.

