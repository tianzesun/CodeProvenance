# IntegrityDesk Weight Tuning Workflow

This workflow implements the process from `IntegrityDesk_WeightTuning_Plan_v2.docx`
without changing production weights until a held-out test result is available.

## Input Format

Export benchmark pair scores as JSON or CSV. Each row needs a binary `label` and
per-engine scores. Canonical score columns are:

- `ast`
- `fingerprint`
- `embedding`
- `execution`
- `ngram`

Accepted aliases include `token` and `winnowing` for `fingerprint`, `semantic`
and `unixcoder` for `embedding`, `execution_cfg` for `execution`, and `gst` for
`ngram`.

Example JSON row:

```json
{
  "pair_id": "assignment1_a_b",
  "file_a": "a.py",
  "file_b": "b.py",
  "label": 1,
  "ast": 0.91,
  "fingerprint": 0.84,
  "embedding": 0.77,
  "execution": 0.65,
  "ngram": 0.42
}
```

## Run

```bash
source /home/tsun/Documents/CodeProvenance/venv/bin/activate
python -m src.backend.benchmark weight-tune \
  --input data/scored_pairs.json \
  --output results/weight_tuning_v1
```

For a quick smoke test, cap the search:

```bash
python -m src.backend.benchmark weight-tune \
  --input data/scored_pairs.json \
  --output results/weight_tuning_smoke \
  --grid-step 0.10 \
  --max-grid-runs 100
```

## Artifacts

The runner writes the plan deliverables:

- `train_pairs.json`
- `test_pairs.json`
- `dataset_stats.txt`
- `baseline.json`
- `solo_ast.json`
- `solo_fingerprint.json`
- `solo_embedding.json`
- `solo_execution.json`
- `solo_ngram.json`
- `solo_summary.csv`
- `search_log.csv`
- `best_weights_search.json`
- `threshold_sweep.csv`
- `best_threshold.json`
- `final_evaluation.json`
- `summary.json`

## Deployment Rule

Do not update `src/backend/engines/scoring/fusion_engine.py` or default
thresholds from a training result alone. Only deploy weights after
`final_evaluation.json` shows an acceptable held-out test result.
