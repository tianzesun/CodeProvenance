# AI Detection Accuracy — measured findings

Measured on the local corpora with `scripts/measure_ai_accuracy.py`
(AIGCodeSet: 220 AI + 220 human, grouped by problem id) plus the Kaggle
novice-student corpus (172 files, human by construction).

Reproduce:

```bash
python scripts/measure_ai_accuracy.py --limit 220
python scripts/measure_ai_accuracy.py --limit 220 --dump-signals /tmp/signals.json
python scripts/ab_fusion_strategies.py --signals /tmp/signals.json
```

## 1. The shipped thresholds are unreachable

| corpus | n | mean | median | p90 | max | ≥0.40 | ≥0.70 |
|---|---|---|---|---|---|---|---|
| AIGCodeSet AI | 220 | 0.126 | 0.116 | 0.174 | 0.330 | **0%** | 0% |
| AIGCodeSet human | 220 | 0.112 | 0.108 | 0.146 | 0.202 | 0% | 0% |
| Kaggle student | 172 | 0.179 | 0.181 | 0.222 | 0.396 | 0% | 0% |

**0 of 612 files reach `medium_risk = 0.40`.** The highest score observed
anywhere is 0.396. In the deployed configuration every submission — including
genuine AI-generated code — is rendered "likely human", so the AI Code Review
screen is currently non-functional rather than merely imprecise.

This is a calibration failure, not a threshold-tuning failure: the fused scores
are compressed into roughly [0.08, 0.40] while the bands assume a [0, 1] scale.

## 2. Discrimination is weak (ROC-AUC 0.59)

Grouped 5-fold CV by AIGCodeSet problem id (the same assignment never spans
train and test):

| strategy | CV AUC |
|---|---|
| current weights | 0.5927 |
| usefulness-proportional weights | 0.5941 |
| greedy-selected subset | 0.5493 |

Per-signal AUC on the full corpus:

| signal | AUC | usefulness | current weight |
|---|---|---|---|
| whitespace_rhythm | 0.5618 | 0.124 | 0.02 |
| stylometry | 0.5606 | 0.121 | 0.10 |
| pattern_library | 0.5410 | 0.082 | 0.15 |
| burstiness | 0.5319 | 0.064 | 0.08 |
| vocabulary_richness | 0.4773 | 0.045 | 0.04 |
| structural_entropy | 0.5062 | 0.012 | 0.07 |
| perplexity | 0.4942 | 0.012 | 0.12 |
| docstring_density | 0.4977 | 0.005 | 0.02 |

Every signal is near chance. The weights are also misaligned with measured
usefulness: `perplexity` is effectively noise (AUC 0.494) yet carries the
second-highest weight, while the best signal `whitespace_rhythm` gets the
lowest.

Note the two tables disagree about the ceiling: the fused score separates
better (0.59) than most individual signals because they are weakly
*complementary*, not because any one of them works.

## 3. Rejected: reliability-weighted fusion

A fix was implemented and then **reverted on evidence**. Several signals return
exactly `0.0` when a file is too small for them to measure anything, and the
unweighted average scored that "no evidence" identically to "strong evidence of
human authorship" — a real conceptual flaw. Scaling each signal's weight by
`assess_signal_reliability` did not help:

| metric | shipped | candidate | delta |
|---|---|---|---|
| grouped CV roc_auc | 0.5987 | 0.5277 | **−0.0710** |
| whole-set roc_auc | 0.5745 | 0.5399 | −0.0346 |

Dropping zero-reliability signals discards real signal from long files (a
40-line file still has measurable burstiness), which costs more discrimination
than the bias it removes. The change was reverted; `orchestrator.py` is
unmodified. The rejected variant is kept as
`ab_fusion_strategies._reliability_weighted_heuristic` so the negative result
stays reproducible.

## 4. Why the obvious fixes do not work

- **Greedy signal selection** overfits: 0.6025 in-sample but 0.5493 under
  grouped CV. Tuning on this corpus without a grouped holdout is misleading.
- **Reweighting** is worth ~0.001 AUC. There is no weight vector that rescues
  near-chance signals.
- The ML classifier is already blended in (`classification.enabled: true`) and
  carries ~0.5 weight at ≥60 lines, so it does not lift the fused AUC beyond
  0.59 either.

## What is actually needed

The heuristic signals are close to exhausted. Meaningful gains require one of:

1. **Enable Binoculars in deployment.** It is the only genuinely strong signal
   in the stack (0.40 weight, published 0.01% FPR) and it is currently absent
   by default, which is why the numbers above are all heuristic-only. It needs
   a reproducible install (see the open packaging blocker) and a run on the
   full FP corpus before its accuracy can be claimed.
2. **Retrain the classifier** on current features with a grouped holdout, and
   report CV rather than in-sample AUC.
3. **Recalibrate the output scale** so the bands mean something. Until scores
   span [0, 1], the 0.40/0.70 bands are decorative. Any new operating point
   must be chosen from a labelled ROC curve with a stated FPR budget, not
   guessed — with AUC 0.59 the honest framing is "low-confidence triage
   signal", not "detector".
