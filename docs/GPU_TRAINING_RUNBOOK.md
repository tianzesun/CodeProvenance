# GPU Training Runbook

Everything that trains a model or measures external tools runs on the GPU host.
The laptop checkout is for editing and reviewing code; a training or an
`engine-eval` run there costs hours and produces the same numbers.

This page is the whole procedure: three scripts, one gate, one explicit
promotion step.

## Why the GPU host is much faster (and what was fixed to make it so)

`engine-eval` and `fusion-train-learned` score pairs one at a time, and each pair
hands the embedding model **two** sequences. A GPU forward pass over two
sequences uses a small fraction of the device; the model is built for batches of
32. Two changes make the GPU host worth it:

1. **Device auto-detection** already exists (`UniXcoderSimilarity` picks CUDA
   when `torch.cuda.is_available()`); `scripts/gpu/setup.sh` prints which device
   the run will use, so a CPU-only torch build cannot waste hours silently.
2. **Embedding prewarm** (on by default) encodes every distinct submission once,
   at `EMBEDDING_BATCH_SIZE` per pass, and leaves the vectors in the disk cache
   that per-pair scoring already reads. Scores are unchanged — both paths end at
   the same `.npy` file — so this is a pure wall-clock change.

Measured effect on the corpora (distinct texts, no model involved):

| Corpus | Pairs | Per-pair encodings | Distinct texts after prewarm |
| --- | ---: | ---: | ---: |
| IR-Plag-Dataset | 460 | 920 | 453 |
| conplag | 911 | 1822 | 946 |
| kaggle_student_code | 293 | 586 | 166 |

So the work drops by 2x–3.5x, and each remaining forward pass carries up to 32
texts instead of 2.

Do not promise a customer a GPU duration we have not measured: the report's
`runtime_seconds` is the only number to quote, and it is machine-specific.

## 1. Get the code and the corpora onto the GPU host

```bash
git clone https://github.com/tianzesun/CodeProvenance.git
cd CodeProvenance
git pull            # need the commit that introduced scripts/gpu and fusion-gate
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The corpora are gitignored, so copy them from the machine that downloaded them:

```bash
rsync -av --info=progress2 other-host:CodeProvenance/data/datasets/ data/datasets/
```

| Corpus | Size |
| --- | ---: |
| `conplag` | 74 MB |
| `IR-Plag-Dataset` | 4.0 MB |
| `kaggle_student_code` | 736 KB |

## 2. Verify the host

```bash
bash scripts/gpu/setup.sh
```

Read the output before going further:

- `cuda: available, <device name>` — the run will use the GPU. If it says
  `NOT AVAILABLE`, stop: a CPU wheel is installed or the driver/container has no
  device, and the run will be laptop-speed.
- `learned training: has --no-prewarm-embeddings` and `gate: available` — the
  checkout is new enough. A stale checkout exits here instead of failing halfway.
- The corpus table must show non-zero pairs for all three corpora. An `UNUSABLE`
  row means the copy is incomplete or at an unexpected path; point
  `DATA_ROOTS` at the real location.
- A dirty working tree warning means the result is not reproducible from a
  commit. Commit or stash before measuring.

Paths are all overrideable:

```bash
PYTHON_BIN=/opt/conda/bin/python \
DATA_ROOTS="/data/corpora /data/more" \
REPORT_ROOT=/data/reports \
bash scripts/gpu/setup.sh
```

## 3. Retrain the candidate (equal dataset weighting)

```bash
bash scripts/gpu/train_equal.sh
```

What it runs, and why each flag matters:

| Flag | Why |
| --- | --- |
| `--datasets IR-Plag-Dataset conplag kaggle_student_code` | the three corpora with labels that match what the product scores |
| `--cv-folds 5` | grouped folds, namespaced per dataset, so no corpus leaks into its own evaluation |
| `--dataset-weighting equal` | 911 conplag pairs would otherwise outvote 460 IR-Plag and 293 kaggle pairs |
| `--cache <report dir>/fusion_training/.cache/features.jsonl` | the expensive step is paid once; a crash or a changed mix re-uses it |
| `--artifact <report dir>/model_equal.json` | **the script never writes the shipped artifact**; a candidate is a file in `reports/` until a human promotes it |
| prewarm (default on) | one batched encode pass instead of two sequences per pair |

Preview both commands without touching the device or the cache:

```bash
DRY_RUN=1 bash scripts/gpu/train_equal.sh
DRY_RUN=1 bash scripts/gpu/eval_real_tools.sh
```

Then the same script runs the gate:

```bash
python -m src.backend.benchmark fusion-gate --report reports/fusion_training/equal
```

```
dataset                 shipped  candidate    delta  result
--------------------------------------------------------------
IR-Plag-Dataset          0.6184     0.62xx  +0.00xx  PASS
conplag                  0.8134     0.81xx  +0.00xx  PASS
kaggle_student_code      0.8833     0.88xx  +0.00xx  PASS

GATE: PASS - every corpus is at least level with the shipped artifact
Pooled AUC is not a criterion; compare per corpus.
```

The bar (`0.6184 / 0.8134 / 0.8833`) is the **shipped artifact** measured on the
same corpora with the same harness on 2026-10-22. Non-negotiable properties of
this gate:

- **Per corpus only.** A candidate that gains on one corpus and loses on another
  fails. Pooled AUC is not read; it is flattered by the corpora being separable
  from each other.
- **Missing is fail.** A report without a corpus cannot prove it did not regress.
- **Compared at 4 decimals**, the precision the bar is quoted at, so a re-run
  that reproduces the shipped number does not fail on float noise.
- `--tolerance 0.004` exists for a trade-off someone explicitly accepted; it is
  not a default.

Useful on a partial run:

```bash
# Only IR-Plag was retrained/scored, and that is the question being asked:
python -m src.backend.benchmark fusion-gate --report reports/fusion_training/equal \
  --baseline IR-Plag-Dataset=0.6184 --json
```

## 4. Measure against the real external tools

```bash
bash scripts/gpu/eval_real_tools.sh
```

This runs `engine-eval --dataset <corpus> --tools jplag dolos` for all three
corpora and then gates the production `fused` AUC per corpus. It writes one
report per corpus to `reports/engine_evaluation/`; the gate reads the newest file
per corpus, so re-running a single corpus updates only that row.

- `TOOLS="jplag dolos"` by default. MOSS needs a Stanford account
  (`--moss-user-id`); without it the tool is reported unavailable, never
  simulated.
- `BATCH_SIZE=80` matches the measured runs. JPlag/Dolos are quadratic in
  submissions, which is why pairs are scored in batches; a batch that fails
  marks that tool unavailable rather than silently scoring zero.

## 5. Promote a passing candidate (explicit, one commit)

```bash
cp reports/fusion_training/equal/model_equal.json \
   src/backend/engines/similarity/models/learned_fusion_model.json
git add src/backend/engines/similarity/models/learned_fusion_model.json
git commit -m "feat: ship the equal-weight learned fusion artifact"
```

Rollback is a checkout of the tracked file:

```bash
git checkout -- src/backend/engines/similarity/models/learned_fusion_model.json
```

## 6. Record what was run

Copy the gate output and the report's `runtime_seconds` into
`docs/FUSION_TRAINING_WORKFLOW.md` next to the other measured attempts. A run
without its per-corpus rows and runtime is not evidence.

## What not to do

- **Do not train on the laptop.** CPU embedding is ~1.9 s/pair; 1664 pairs is
  close to an hour before any fitting, and the machine is also serving the app.
- **Do not omit `--artifact`.** Without it the runner overwrites the shipped
  artifact, which turns a candidate into a release.
- **Do not add `poolc_600k_python` to `--datasets`.** Its `similar` label means
  "same problem", not "copied"; measured attempts are in
  [FUSION_TRAINING_WORKFLOW.md](FUSION_TRAINING_WORKFLOW.md).
- **Do not quote pooled/combined AUC** as a result. Use the per-corpus rows.
- **Do not disable the embedding** to save time. The artifact would be fitted
  with `embedding == 0` everywhere while production feeds it real values.
