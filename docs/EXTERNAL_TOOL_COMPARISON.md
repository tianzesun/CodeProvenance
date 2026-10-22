# External tool comparison (accuracy, not aspiration)

This page describes how to measure IntegrityDesk's similarity score against
real external plagiarism tools on the labeled corpora we already train on.

## What `engine-eval` measures

One run scores the **same pairs and labels** a `fusion-train-learned` run uses
(the loaders are shared, not duplicated), and reports per-scorer ROC-AUC plus
precision / recall / F1 at the best swept threshold and at 0.5:

| Scorer | What it is |
| --- | --- |
| `fused` | The production score: `BatchDetectionService` with the shipped learned artifact, then the structure-sensitivity floor. This is what users get. |
| `fused_rule` | The same service with the learned artifact disabled (rule fusion + the same floor). The learned layer has to beat this. |
| `ast`, `fingerprint`, `embedding`, `ngram`, `winnowing`, `logic_flow` | Individual features, for diagnosing which signal carries a corpus. |
| `jplag`, `dolos` | The real local tools (`tools/external/JPlag/jplag.jar`, `tools/external/dolos-cli`). |
| `moss` | Real Stanford MOSS, but only when `--moss-user-id` is given (requires a registered MOSS account). Without it the row is reported as unavailable. |

`moss` is also the one tool with an account: the adapter patches the vendored
`tools/external/moss/moss.pl` so its hardcoded `$userid` comes from
`MOSS_USER_ID`, falling back to `0`, and `ExternalToolRunner` refuses to submit
at all when no id is passed. Register with Stanford to obtain an id before
quoting any MOSS comparison.

Tools that cannot run are reported `available: false` with a reason. No score
in this harness is simulated.

## Commands

Per corpus, on the GPU host (feature extraction dominates the runtime):

```bash
source venv/bin/activate
for ds in IR-Plag-Dataset conplag kaggle_student_code; do
  python -m src.backend.benchmark engine-eval \
    --dataset "$ds" \
    --tools jplag dolos \
    --external-batch-size 80 \
    --output reports/engine_evaluation
done
```

Add `--moss-user-id <id>` to include MOSS, and `--pair-limit 40` for a quick
plumbing check. Reports land in `reports/engine_evaluation/ENGINE_EVAL_<dataset>_<timestamp>.{json,md}`.

`--external-batch-size` exists because JPlag and Dolos compare every submission
against every other one: scoring thousands of independent pairs in a single
invocation is quadratic. Each batch is a separate tool run, and if a batch fails
the tool is reported unavailable rather than scored from partial output (a
partial fill would make its AUC depend on which batches happened to succeed).

## Measured results (2026-10-22)

Full corpora, real tools, one run per corpus (`--tools jplag dolos`,
`--external-batch-size 80`, local CPU). ROC-AUC:

| Corpus | Pairs (+/−) | `fused` (prod.) | `fused_rule` | JPlag | Dolos |
| --- | --- | ---: | ---: | ---: | ---: |
| IR-Plag-Dataset | 460 (355/105) | 0.618 | 0.632 | 0.573 | **0.670** |
| conplag | 911 (251/660) | 0.813 | 0.662 | 0.821 | **0.838** |
| kaggle_student_code | 293 (100/193) | **0.883** | 0.872 | 0.847 | 0.859 |

Paired bootstrap (4,000 resamples) of `fused` minus the other scorer, 95% CI:

| Corpus | vs `fused_rule` | vs JPlag | vs Dolos |
| --- | --- | --- | --- |
| IR-Plag | −0.014 [−0.064, +0.036] | +0.045 [−0.011, +0.103] | **−0.052 [−0.086, −0.018]** |
| conplag | **+0.152 [+0.120, +0.183]** | −0.007 [−0.028, +0.013] | **−0.024 [−0.041, −0.009]** |
| kaggle | +0.012 [−0.011, +0.036] | **+0.036 [+0.007, +0.066]** | **+0.025 [+0.002, +0.050]** |

Reading:

- The learned layer earns its place on conplag (+0.15, unambiguous) and is
  indistinguishable from the rule score on the other two corpora. It was
  trained on IR-Plag + conplag, so the gain being concentrated in the larger
  corpus is what `dataset_weighting: proportional` predicts.
- Against the external tools the picture is mixed, not a defeat: parity with
  JPlag on conplag, ahead of both on the Python classroom corpus, behind Dolos
  on IR-Plag (the only clearly significant loss).
- MOSS is **not** in this table. It needs a registered account
  (`--moss-user-id`); until then no MOSS comparison exists.

### Absolute scores are not calibrated on two of three corpora

Median score, and share of *negative* pairs scored ≥ 0.5:

| Corpus | `fused` positives | `fused` negatives | negatives ≥ 0.5 | `fused_rule` negatives |
| --- | ---: | ---: | ---: | ---: |
| IR-Plag | 0.938 | 0.878 | 99% | 0.661 |
| conplag | 0.569 | 0.195 | 8% | 0.000 |
| kaggle | 1.000 | 0.775 | 68% | 0.844 |

On IR-Plag the production score ranks no better than the rule score but pushes
almost every independent solution to ~0.88: a fixed 0.5 cutoff would flag the
whole class. Kaggle is similar near the top of the scale. Only conplag behaves
like a probability. This is why the table above is AUC (ranking), and why
`F1@0.5` is not comparable across corpora — on IR-Plag the best swept threshold
is 0.00 (77% of pairs are positive, so "flag everything" maximises F1).

Consequence for the product: a score shown to a user needs its own
per-language calibration before it can be read as "how similar", not just a
rank.

## How to read the result

- Compare scorers **per corpus**, never pooled. A corpus that mixes
  near-verbatim Java with Python classroom work averages two different tasks.
- `fused` must beat `fused_rule` on a corpus to justify keeping the learned
  artifact's behavior there; if it does not, do not retrain on that corpus
  (see `FUSION_TRAINING_WORKFLOW.md`).
- Token-matching tools (`jplag`, `dolos`, `moss`) are expected to be strong on
  near-verbatim copying (Type-1/Type-2, e.g. the Java contest corpora) and weak
  on rewrites and same-assignment independent solutions. Treat a tool win
  there as a product finding, not as a bug in the harness.
- A pair a tool never reports is scored `0` (its "no match" answer) and the run
  logs how many that was. Check that warning before quoting an AUC.

## Paths that must not be quoted as measurements

These exist in the repository and produce numbers that look like comparisons
but are not measurements:

- `src/backend/benchmark/competitors/` — every tool, **including the
  IntegrityDesk column**, is generated by `_simulated_score` from
  literature-derived recall/FP profiles and a seeded RNG. The IntegrityDesk
  side is always simulated, because it imports a top-level
  `engines.scoring.fusion_engine` that does not exist and falls back to the
  simulation.
- `src/backend/benchmark/cross_dataset/tool_adapters.py` — MOSS / JPlag / Dolos
  fall back to `_simulate_moss` / `_simulate_jplag` / `_simulate_dolos` when the
  real tool or credentials are missing (`MOSS_USER_ID` is unset by default).

Use `engine-eval` for anything that will be published or shown to a customer.
