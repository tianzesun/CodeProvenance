# Fusion Training Workflow

This workflow prepares the plagiarism fusion model before large-scale training on a GPU server.

This document is written as an operations runbook. Another engineer should be able to
follow it on a separate machine without needing to read the code first.

**Run training and `engine-eval` on the GPU host, not on the app laptop.** The
short procedure is [GPU_TRAINING_RUNBOOK.md](GPU_TRAINING_RUNBOOK.md):
`bash scripts/gpu/setup.sh`, then `train_equal.sh` or `eval_real_tools.sh`, then
the `fusion-gate` verdict. The rest of this page explains the corpora, the
commands behind those scripts, and every measured attempt so far.

## What It Does

The workflow now supports three separate commands:

- `fusion-optimize`
  - Runs validation-set fusion experiments on PROGpedia.
  - Compares equal weights, seeded weights, pooling, Optuna tuning, and a stacked model when available.
- `fusion-train`
  - Trains supervised fusion models on labeled local datasets.
  - Exports feature tables, trains several candidate models, saves the best model, and writes Markdown and JSON reports.
- `fusion-train-learned`
  - Trains the production scorer (a calibrated logistic model over the seven
    production features: ast, fingerprint, embedding, ngram, winnowing,
    logic_flow, coverage) on combined labeled datasets.
  - Writes the JSON artifact consumed by `BatchDetectionService` at
    `src/backend/engines/similarity/models/learned_fusion_model.json`, so the
    production similarity score becomes `P(plagiarism | features)` instead of
    the rule-based confidence. Falls back to rule scoring when the artifact is
    absent.

## Supported Local Datasets

The supervised training workflow currently knows how to load:

- `conplag`
- `conplag_classroom_java`
- `IR-Plag-Dataset`
- `codexglue_clone`
- `poj104`

`fusion-train-learned` has its own list, because a corpus is only usable there
if its labels describe pairs of *correctly labelled* submissions:

- `IR-Plag-Dataset` (Java, 460 loadable pairs: 355 plagiarized / 105
  non-plagiarized across 7 cases) — each case contributes
  original-vs-plagiarized and original-vs-non-plagiarized pairs. The negatives
  are two independent solutions of the same assignment.
- `conplag` (Java, 911 pairs) — contest pairs with a plagiarized / not
  plagiarized verdict; negatives are again same-problem.
- `kaggle_student_code` (Python, 293 pairs) — submissions from one classroom
  with an explicit cheating label. 100 positive / 193 negative.
- `poolc_600k_python` (Python, ~600k pairs, sampled) — **read the warning in
  Step 6 before using this one.**

The command searches these roots by default:

- `data/datasets`
- `data/bigger_datasets`

### Getting a corpus onto the training machine

`data/*` is gitignored, so a corpus exists only on the machine that downloaded
it. A retrain therefore needs those directories copied (or re-downloaded) first:

| Corpus | Size on disk |
| --- | ---: |
| `poolc_600k_python` (1 of 9 shards) | 218 MB |
| `conplag` | 74 MB |
| `IR-Plag-Dataset` | 4.0 MB |
| `kaggle_student_code` | 736 KB |

Extraction cost is dominated by the embedding feature: measured on a CPU-only
laptop, one pair costs `1.86 s` with the embedding on and `0.096 s` with it off.
So 20000 pairs is roughly 10 hours of CPU, and proportionally less with a CUDA
embedding runtime. Do not turn the embedding off to save time: the artifact
would then be fitted with `embedding == 0` everywhere while production feeds it
real values, which silently discards the feature. `--cache` is the intended way
to pay that cost once.

You can override this on another machine with `--dataset-roots`.

## Before You Start

Confirm these four things first:

1. The repository is present on the server.
2. The Python environment contains the project dependencies.
3. The datasets have been copied onto the server.
4. You know where reports should be written.

The checkout must also be current: `fusion-train-learned` gained `--cv-folds`,
`--dataset-weighting`, `--cache`, `--max-pairs`, `--poolc-negative-ratio` and
`--dataset-roots` in `9742e557`. A stale checkout fails immediately with
`unrecognized arguments`. Note that the corpora are gitignored, so they live in
whichever checkout downloaded them; if that is a different directory than the one
running the code, pass `--dataset-roots` rather than copying 300 MB around.

Recommended shell setup:

```bash
cd /home/tsun/CodeProvenance
export PYTHON_BIN=/home/tsun/CodeProvenance/venv/bin/python
export DATA_ROOT_1=/home/tsun/CodeProvenance/data/datasets
export DATA_ROOT_2=/home/tsun/CodeProvenance/data/bigger_datasets
export REPORT_ROOT=/home/tsun/CodeProvenance/reports
```

Quick sanity checks:

```bash
$PYTHON_BIN --version
$PYTHON_BIN -c "import optuna, sklearn; print('optuna/sklearn ok')"
test -d "$DATA_ROOT_1"
test -d "$DATA_ROOT_2"
# The running checkout must be new enough to know the current flags:
$PYTHON_BIN -m src.backend.benchmark fusion-train-learned --help | grep -c -- --cv-folds
# ...and the module that will run must be the checkout you think it is:
$PYTHON_BIN -c "import src.backend.benchmark as m; print(m.__file__)"
```

If the server uses different locations, change the four environment variables above and
keep the commands the same.

## Recommended Execution Order

Use this staged plan when the full datasets are ready:

1. Run a smoke test with a very small sample.
2. Run validation-set fusion search on PROGpedia.
3. Run a medium supervised training job.
4. Run the full training job on the GPU server.
5. Compare the reports and keep the best model artifact.

## Command Templates

These are the only two commands the operator needs:

Validation-set fusion search:

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-optimize \
  --dataset-root "$DATA_ROOT_1/progpedia" \
  --trials 100 \
  --output "$REPORT_ROOT/fusion_optimization"
```

Supervised fusion training:

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-train \
  --dataset-roots "$DATA_ROOT_1" "$DATA_ROOT_2" \
  --train-datasets conplag conplag_classroom_java codexglue_clone \
  --eval-datasets IR-Plag-Dataset conplag_classroom_java \
  --train-pairs 5000 \
  --eval-pairs 1000 \
  --optuna-trials 50 \
  --output "$REPORT_ROOT/fusion_training_full"
```

## Step 1: Smoke Test

Small local smoke run:

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-train \
  --dataset-roots "$DATA_ROOT_1" "$DATA_ROOT_2" \
  --train-datasets conplag conplag_classroom_java \
  --eval-datasets IR-Plag-Dataset conplag_classroom_java \
  --train-pairs 40 \
  --eval-pairs 30 \
  --optuna-trials 0 \
  --output "$REPORT_ROOT/fusion_training_smoke"
```

What success looks like:

- the command exits normally
- a Markdown report is created
- a JSON report is created
- `best_model.pkl` is created
- `train_matrix.csv` and `eval_matrix.csv` are created

Useful check:

```bash
find "$REPORT_ROOT/fusion_training_smoke" -maxdepth 2 -type f | sort
```

## Step 2: Validation-Set Search

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-optimize \
  --dataset-root "$DATA_ROOT_1/progpedia" \
  --trials 100 \
  --output "$REPORT_ROOT/fusion_optimization"
```

What this step is for:

- compares equal weights against tuned fusion
- checks whether the weighted formula is improving
- gives a quick benchmark before the larger supervised training job

## Step 3: Medium Training Run

Use this when the smoke test works and you want a real comparison without committing to
the full dataset size yet:

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-train \
  --dataset-roots "$DATA_ROOT_1" "$DATA_ROOT_2" \
  --train-datasets conplag conplag_classroom_java codexglue_clone \
  --eval-datasets IR-Plag-Dataset conplag_classroom_java \
  --train-pairs 1000 \
  --eval-pairs 300 \
  --optuna-trials 20 \
  --output "$REPORT_ROOT/fusion_training_medium"
```

## Step 4: Full GPU Training Run

Use this once the medium run looks healthy:

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-train \
  --dataset-roots "$DATA_ROOT_1" "$DATA_ROOT_2" \
  --train-datasets conplag conplag_classroom_java codexglue_clone \
  --eval-datasets IR-Plag-Dataset conplag_classroom_java \
  --train-pairs 5000 \
  --eval-pairs 1000 \
  --optuna-trials 50 \
  --output "$REPORT_ROOT/fusion_training_full"
```

If your server stores the datasets elsewhere, replace `"$DATA_ROOT_1"` and
`"$DATA_ROOT_2"` with the real folders.

## Step 6: Train The Production Learned-Fusion Artifact

Train the scorer that production actually uses. The reference recipe reproduces
the currently shipped artifact:

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-train-learned \
  --datasets IR-Plag-Dataset conplag \
  --output "$REPORT_ROOT/learned_fusion"
```

Reference result of that recipe (shipped artifact, 2026-08-22): out-of-fold AUC
`0.8650` vs production rule `0.8090` on 1371 pairs, per dataset IR-Plag
`0.7021` and conplag `0.7950`.

**Read the per-dataset numbers, not the combined one.** The combined AUC is
flattered by the two corpora being separable from each other; the per-dataset
rows are the honest generalisation estimate.

What success looks like:

- the report shows the out-of-fold `Learned fusion` AUC above `Production fused
  (rule)` on the same pairs
- **no per-dataset row regresses** against the currently shipped artifact
- the artifact `src/backend/engines/similarity/models/learned_fusion_model.json`
  is rewritten

### Adding the Python corpora

`kaggle_student_code` is the closest thing the repo has to the production
input: Python submissions from one class, with cheating labels.

```bash
$PYTHON_BIN -m src.backend.benchmark fusion-train-learned \
  --datasets IR-Plag-Dataset conplag kaggle_student_code \
  --cv-folds 5 \
  --cache "$REPORT_ROOT/learned_fusion/features.jsonl" \
  --output "$REPORT_ROOT/learned_fusion"
```

Two rules make the evaluation honest enough to act on:

- **Grouped folds.** `--cv-folds 5` assigns every fold key to one fold, and the
  fold key is namespaced by dataset (`<dataset>::<case|problem|group>`), so
  unrelated corpora never share a fold. `--cv-folds 0` keeps the original
  leave-one-group-out, which is only affordable when few groups exist.
- **A cache.** Feature extraction is the expensive step (the embedding feature
  dominates: ~1.9 s/pair on a CPU laptop). `--cache` makes a long run resumable
  and makes alternative training mixes cost only a logistic fit.

These three corpora are CSV/py files. Reading `poolc_600k_python` is the one step
that needs an extra package: its `.parquet` shards need `pyarrow`, which
`requirements.txt` pins **below 26**:

```bash
$PYTHON_BIN -m pip install 'pyarrow<26'
$PYTHON_BIN -c "import pyarrow.parquet, pyarrow; print('pyarrow', pyarrow.__version__)"
```

`requirements.txt` pins `numpy==1.26.3` (for the torch build), while pyarrow 26
and newer require `numpy>=2`. A plain `pip install pyarrow` therefore installs a
build that imports as `ImportError: pyarrow requires NumPy 2.0 or newer, found
1.26.3`. Verified against numpy 1.26.3: 22.0.0, 23.0.1, 24.0.0 and 25.0.0 import
fine, 26.0.0 does not. Do not "fix" this by upgrading numpy: torch in this repo
is built against the numpy 1.x ABI.

### Warning: what PoolC labels actually mean

**Do not train on `poolc_600k_python`.** This section is kept as the record of
why, because the corpus is otherwise the most attractive one in the repo (598736
pairs in the single downloaded shard).

Its labels are not plagiarism labels:

- every pair of accepted solutions to the **same** competitive-programming
  problem is labelled `similar` (299963 pairs), including pairs whose token
  overlap is only ~0.29 — two different programs that happen to solve the same
  task;
- every **cross-problem** pair is labelled `different` (298773 pairs), i.e. the
  negatives are trivially easy and are *not* the case the product scores.

The loader admits its positives and, by default, **no** negatives
(`--poolc-negative-ratio 0`), which is the least harmful way to read it — but it
is still harmful. See the measured attempts below: 10000 PoolC positives scored
*below a coin flip* (rule AUC 0.4594) on a pooled set where they were 86% of the
pairs, because the label "same problem" is anti-correlated with the similarity
features the product scores on. Two independent solutions to one assignment are
the product's false-positive case, not its positive case.

Keep the corpus only for non-training uses, e.g. reading code pairs to smoke-test
the parquet loader — `--max-pairs N` caps how many pairs are read (PoolC alone
defaults to 20000 when omitted) and `--poolc-negative-ratio 0` keeps the
cross-problem negatives out. And always judge a run on the per-dataset rows for
IR-Plag, conplag and kaggle_student_code rather than on the pooled AUC.

### Measured attempts (2026-10-18)

Both candidate mixes were run on the T4 server. **Neither was shipped**, and the
second one answers the PoolC question definitively.

**A — same-problem corpora only** (`IR-Plag-Dataset conplag kaggle_student_code`,
`--cv-folds 5 --dataset-weighting proportional`; 1664 pairs, 706 positive):

| Dataset | Pairs | Rule AUC | Out-of-fold AUC | Shipped artifact |
| --- | ---: | ---: | ---: | ---: |
| IR-Plag-Dataset | 460 | 0.6324 | 0.6185 | **0.6184** |
| conplag | 911 | 0.6617 | 0.7809 | **0.8134** |
| kaggle_student_code | 293 | 0.8718 | 0.8269 | **0.8833** |

Pooled: rule 0.7437, out-of-fold 0.8137. Fails the decision rule on IR-Plag and
on kaggle_student_code. The likely cause is the mix: ~82% of the pairs are Java,
and kaggle_student_code is a single Python classroom group, so its out-of-fold
predictions always come from a model that never saw that corpus.

The right-hand column is the shipped artifact measured on the same pairs by
`engine-eval --dataset <corpus> --tools jplag dolos` (2026-10-22, see
`EXTERNAL_TOOL_COMPARISON.md`). Compare candidates against **that** column, not
only against `Rule AUC`: A is level with the shipped artifact on IR-Plag
(0.6185 vs 0.6184) but loses ~0.03 on conplag and ~0.06 on kaggle, which is the
real reason it was not shipped.

**B — the same mix plus the PoolC positives** (`--max-pairs 20000
--poolc-negative-ratio 0.0 --dataset-weighting equal`; 11664 pairs, 10706
positive — 86% of them PoolC):

| Dataset | Pairs | Rule AUC | Out-of-fold AUC | Shipped artifact |
| --- | ---: | ---: | ---: | ---: |
| IR-Plag-Dataset | 460 | 0.6324 | 0.6741 | 0.6184 |
| conplag | 911 | 0.6617 | **0.4343** | 0.8134 |
| kaggle_student_code | 293 | 0.8718 | 0.7088 | 0.8833 |

Pooled: rule **0.4594**, out-of-fold 0.7376.

B loses to A exactly where it matters and lands *below a coin flip* on conplag.
The decisive number is the rule column on the pooled set: 0.4594. The rule
scorer's ordering is **anti-correlated** with the PoolC `similar` label, because
that label means "same problem", not "copied code" — two independent accepted
solutions share meaning but not text, so the similarity features score them low.
Fitting 10000 such pairs as positives rotates the decision boundary the wrong
way, and the two corpora with real cheating labels pay for it.

Two conclusions worth keeping:

- **Do not train the learned fusion model on the PoolC positives.** The MOSS /
  IR-Plag / conplag / kaggle style labels are the only ones that match what the
  product scores. Drop `poolc_600k_python` from `--datasets` for training
  purposes.
- **Do not read the pooled AUC.** It looked healthy in B (0.7376) while every
  dataset that matters regressed, because 86% of the pooled pairs are the
  corpus whose label semantics disagree with the product.

The shipped artifact therefore stands. The exits from here are more *labelled
same-assignment* data (see `docs/AI_HOLDOUT_COLLECTION.md` for the collection
pattern used on the AI side) or a per-language scoring decision, not another mix
of the corpora already in `data/datasets`.

One experiment is still worth running on the existing three corpora (no PoolC):
`--dataset-weighting equal` with the A mix. The measured shipped artifact gains
from the learned layer only on conplag (+0.15 AUC) and is indistinguishable from
the rule score on IR-Plag and kaggle, which is what proportional weighting
(911 conplag pairs vs 460 IR-Plag, 293 kaggle) predicts. The bar to beat is the
shipped column in the table above: 0.6184 / 0.8134 / 0.8833. Do not ship a
candidate that only trades one corpus for another.

Run it through the script rather than by hand, because the script also refuses to
write the shipped artifact and applies the gate:

```bash
bash scripts/gpu/train_equal.sh
```

See [GPU_TRAINING_RUNBOOK.md](GPU_TRAINING_RUNBOOK.md) for the flags it passes and
the gate's exact semantics.

### Decision rule

Ship the new artifact only when all of the following hold:

1. the per-dataset out-of-fold AUC for IR-Plag, conplag and kaggle_student_code
   is at least as high as the currently shipped artifact's on the same corpora;
2. the learned out-of-fold AUC beats the rule baseline on those same corpora;
3. `reports/engine_evaluation` run against IR-Plag does not lose AUC.

For the accuracy side of this question — how the production score compares with
real JPlag / Dolos on the same pairs, per corpus — use `engine-eval --dataset`
described in [EXTERNAL_TOOL_COMPARISON.md](EXTERNAL_TOOL_COMPARISON.md). That
harness reports a `fused_rule` baseline next to the production `fused` score,
so a corpus where the learned layer adds nothing is visible directly.

Otherwise keep the existing artifact: it is a tracked file, so the rollback is
`git checkout -- src/backend/engines/similarity/models/learned_fusion_model.json`.

After this step, `BatchDetectionService` uses the learned score as the primary
similarity score with the rule-based confidence kept in the `fused_score`
feature for transparency. Removing the artifact reverts production to the
rule-based path.

## Step 5: Compare Runs

Look at the generated Markdown reports first. The main things to compare are:

- best overall result
- best saved model
- F1 score
- precision
- recall
- threshold

Quick command to list reports:

```bash
find "$REPORT_ROOT" -name "fusion_training_report_*.md" | sort
```

Quick command to inspect the most recent JSON result:

```bash
export LATEST_JSON=$(find "$REPORT_ROOT/fusion_training_full" -name "fusion_training_results_*.json" | sort | tail -n 1)
$PYTHON_BIN - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["LATEST_JSON"])
payload = json.loads(path.read_text())
print("best overall result:", payload["best_experiment_name"])
print("best model:", payload["best_model_name"])
for item in payload["experiments"]:
    print(item["name"], round(item["best_metrics"]["f1_score"], 4))
PY
```

## Outputs

Each `fusion-train` run writes:

- `train_matrix.csv`
- `eval_matrix.csv`
- `best_model.pkl`
- `fusion_training_report_<timestamp>.md`
- `fusion_training_results_<timestamp>.json`
- `cache/pair_signals.json`

Each `fusion-optimize` run writes:

- `fusion_optimization_report_<timestamp>.md`
- `fusion_optimization_results_<timestamp>.json`
- `fusion_training_matrix.csv`
- `cache/pair_signals.json`

## How To Tell If The Run Is Healthy

Normal signs:

- progress logs appear during record extraction
- model training logs appear one model at a time
- output files appear in the chosen report folder
- the final lines print the best result and model path

Warning signs:

- no dataset folders exist at the configured roots
- no output files are written
- only the startup lines appear and nothing else for a very long time
- the report shows missing capabilities when you expected `optuna` or `sklearn`

## Troubleshooting

If the command fails immediately:

- check that `PYTHON_BIN` points to the right virtual environment
- check that the dataset folder names match the expected names exactly
- check that the selected datasets really exist under the configured roots

If the run is very slow:

- lower `--train-pairs`
- lower `--eval-pairs`
- set `--optuna-trials 0` for a quick test
- run the smoke test first, then the medium run, then the full run

If the GPU server uses a different checkout path:

- change `PYTHON_BIN`
- change `DATA_ROOT_1`
- change `DATA_ROOT_2`
- change `REPORT_ROOT`

The commands themselves do not need to change after that.

## Notes

- Feature extraction is cached, so repeated runs on the same pair set get faster.
- Progress logging is emitted during feature extraction and model training.
- The best model is selected by evaluation F1 score.
- Benchmark runs encode each distinct submission once before pairwise scoring
  (embedding prewarm). Pairwise calls hand the model two sequences at a time, so
  on a GPU this is the difference between using the device and leaving it idle;
  `--no-prewarm-embeddings` exists only to reproduce an old timing.
- The corpora sizes here (1664 pairs) do not need a GPU to fit the logistic
  model; the GPU is for the embedding features during extraction.
