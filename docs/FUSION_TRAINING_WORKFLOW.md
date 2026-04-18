# Fusion Training Workflow

This workflow prepares the plagiarism fusion model before large-scale training on a GPU server.

This document is written as an operations runbook. Another engineer should be able to
follow it on a separate machine without needing to read the code first.

## What It Does

The workflow now supports two separate commands:

- `fusion-optimize`
  - Runs validation-set fusion experiments on PROGpedia.
  - Compares equal weights, seeded weights, pooling, Optuna tuning, and a stacked model when available.
- `fusion-train`
  - Trains supervised fusion models on labeled local datasets.
  - Exports feature tables, trains several candidate models, saves the best model, and writes Markdown and JSON reports.

## Supported Local Datasets

The supervised training workflow currently knows how to load:

- `conplag`
- `conplag_classroom_java`
- `IR-Plag-Dataset`
- `codexglue_clone`
- `poj104`

The command searches these roots by default:

- `data/datasets`
- `data/bigger_datasets`

You can override this on another machine with `--dataset-roots`.

## Before You Start

Confirm these four things first:

1. The repository is present on the server.
2. The Python environment contains the project dependencies.
3. The datasets have been copied onto the server.
4. You know where reports should be written.

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
- The current workflow is CPU-friendly for feature building and model training; moving it to a GPU server mainly helps when you scale the data volume and want faster end-to-end experiment cycles.
