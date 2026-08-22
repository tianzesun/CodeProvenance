# Human-Code False-Positive Baseline

**Date:** 2026-08-22 · **Detector:** `AIDetectionOrchestrator` (production
safe-blend, the exact object the background AI-detection job runs) ·
**Method:** `scripts/measure_human_fp.py` · **Raw report:**
`reports/human_fp/human_fp_report_*.json`

## The number that matters

Measured on the **Kaggle student corpus** — 174 real, novice-style student
Python submissions (sqlite CRUD exercises, two-line functions, awkward
docstrings — the product's actual input distribution):

| Threshold | False-positive rate |
| --- | ---: |
| ≥ 0.40 (medium band) | **47.1%** |
| ≥ 0.50 (neutral cut) | **39.1%** |
| ≥ 0.70 (high band) | **21.3%** |

Score distribution: mean 0.439, median 0.373, p90 0.761, max 0.812.

**At the current high band, roughly one in five innocent students writing
novice-style Python gets a high-concern AI flag.** In the dossier UX that
means a red "High concern" chip on a student who may well be innocent — the
viva-question framing is doing the real safety work, not the score.

## Control corpora (same run)

| Corpus | n | mean | FP@0.40 | FP@0.50 | FP@0.70 |
| --- | ---: | ---: | ---: | ---: | ---: |
| IR-Plag originals (student Java) | 7 | 0.190 | 0% | 0% | 0% |
| PoolC sample (community Python) | 100 | 0.217 | 0% | 0% | 0% (max 0.386) |

Experienced/community human code sails through. **The false positives are
concentrated exactly where production traffic lives: short, terse, novice
student Python.** This is the first direct confirmation, on external human
code, of what `AI_HOLDOUT_COLLECTION.md` predicted from the AIGCodeSet
precision regressions.

## Honest caveats

- The Kaggle corpus is treated as human **by dataset construction**, not by
  per-file ground truth; if any late-era samples were AI-assisted they would
  inflate these rates. The style evidence (novice idioms, inconsistencies)
  reads human throughout, but the labelled institutional holdout remains the
  decisive measurement.
- n=174 single-corpus, Python-only; IR-Plag originals are Java and few.
- Binoculars layer absent (falls back to heuristics, same as default
  deployment).

## What this changes

1. **The ML-enablement gate is now backed by a live number.** Enabling the
   classifier (or keeping thresholds where they are) is a decision about a
   measured 21–47% student-Python FP rate, not a theoretical one.
2. **Threshold/banding review is warranted** once the real holdout lands:
   either the high band rises for short submissions, or the dossier must
   render novice-code uncertainty more loudly than a severity chip.
3. **Reproduce on institutional data** with the request pack
   (`docs/STUDENT_DATA_REQUEST_PACK.md`); the pipeline is proven end-to-end
   (ingestion round-trips exactly, grouped benchmark runs on custom dataset
   dirs).
