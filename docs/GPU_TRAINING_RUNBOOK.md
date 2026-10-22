# GPU Training Runbook

Everything that trains a model or measures external tools runs on the GPU host.
The laptop checkout is for editing and reviewing code; a training or an
`engine-eval` run there costs hours and produces the same numbers.

This page is the whole procedure: four scripts, one gate, one explicit
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
- `fingerprint=` per corpus identifies the pairs, labels and code bodies. Two
  hosts with different fingerprints do not share a corpus copy; see
  [the bar section](#the-bar-is-measured-on-the-host-that-runs-the-gate).
- The external-tools block runs JPlag and Dolos once on two toy files. `BROKEN`
  there means a full `engine-eval` would report the tool unavailable, so fix it
  now (the most common cause is a Node ABI mismatch, described under
  [measure against the real external tools](#4-measure-against-the-real-external-tools)).
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

### The bar is measured on the host that runs the gate

The three built-in constants were measured on the development machine on
2026-10-22. They only transfer to a host that holds the *same corpus files*.
`bash scripts/gpu/setup.sh` prints a `fingerprint=` per corpus, and two hosts with
different fingerprints will not agree on AUC even for the shipped artifact.

This is not hypothetical. On the T4 host the shipped artifact measured
`0.6184 / 0.8134 / 0.8898` — IR-Plag and conplag identical, kaggle 0.0065 higher,
with the dependency-free `rule` scorer moving on kaggle too (0.8718 → 0.8773) and
nowhere else, and JPlag independently landing 0.005 higher on kaggle only.
`kaggle_student_code` is assembled locally from the Kaggle CSV instead of being
downloaded, so its copy drifts between machines.

**The standing procedure is a host baseline, not the constants.** Once per host,
and again after promoting an artifact or changing a corpus:

```bash
# 1) with the shipped artifact in place, measure it on this host's corpora
bash scripts/gpu/eval_real_tools.sh

# 2) freeze those numbers as the bar, with a manifest
bash scripts/gpu/baseline.sh
```

`baseline.sh` keeps the newest report per corpus and writes
`reports/engine_evaluation_shipped/BASELINE.json`:

```json
{
  "created_at": "2026-10-22T16:49:02+00:00",
  "commit": "89e5c754",
  "artifact_sha256": "b4718fcb…",
  "scores": {"IR-Plag-Dataset": 0.618404, "conplag": 0.813377,
             "kaggle_student_code": 0.883342},
  "reports": ["ENGINE_EVAL_conplag_20261022_100901.json", "…"],
  "corpus_fingerprints": {"IR-Plag-Dataset": "10f45afb…", "…": "…"}
}
```

After that, `train_equal.sh` and `eval_real_tools.sh` pick it up **by default**
(`_common.sh` uses `reports/engine_evaluation_shipped` whenever it holds a
`BASELINE.json`); neither needs an environment variable. Set `BASELINE_REPORT` to
point somewhere else, or delete the directory to fall back to the constants — the
scripts print which bar is in force:

```
bar:      host-measured shipped artifact from …/reports/engine_evaluation_shipped
```

The gate checks the manifest before judging:

- **Artifact hash.** If the shipped artifact changed since the baseline was
  measured, the bar no longer describes it and the gate stops with
  `Re-measure it with scripts/gpu/baseline.sh`. `--allow-stale-baseline` judges
  against the old bar anyway and says so.
- **Corpus fingerprints** are recorded, not enforced: they need the dataset roots
  and would make the gate load every corpus. Compare them by eye against
  `setup.sh` after moving data between hosts.
- **Full precision is rounded to 4 decimals** before comparing, because the bar
  comes from a report (`0.618404`) and the candidate is quoted as `0.6184`.
- A corpus missing from the baseline falls back to its constant with a
  `warning:`; the verdict never shrinks to the corpora the baseline covers.

The scripts refuse a `BASELINE_REPORT` that points at the directory the run is
about to overwrite (`OUT`): you would be judging a run against itself, and the
old measurement is gone by the time the gate reads it. They also refuse a
baseline report that is also the candidate report.

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
- **The binaries live in `tools/external/`, which is gitignored.** A fresh
  `git clone` on the GPU host has the corpora (once copied) but no
  `JPlag/jplag.jar` or `dolos-cli`, so every report says
  `UNAVAILABLE: tool did not produce pair scores` and the run measures
  IntegrityDesk only. Copy them over and re-run:

  ```bash
  rsync -av --info=progress2 other-host:CodeProvenance/tools/external/ tools/external/
  ```

  The script refuses to finish in that state: if none of the requested tools
  produced a score for any corpus it exits 2 with the command above instead of
  printing a green gate. `ALLOW_MISSING_TOOLS=1` downgrades that to a warning
  when the question really is IntegrityDesk alone.

### Dolos needs a pinned Node, not the host's

`dolos-cli` is a Node script, and its parsers are native modules compiled against
one Node ABI (`NODE_MODULE_VERSION`). The copy in this checkout was built with
Node 25 (ABI 141). A host on Node 22 (ABI 127) starts the CLI, answers `--help`,
passes any presence check, and then dies on the first real run:

```
[error] The module '.../tree_sitter_elm_binding.node' was compiled against a
different Node.js version using NODE_MODULE_VERSION 141. This version of Node.js
requires NODE_MODULE_VERSION 127.
```

`node -p process.versions.modules` prints the ABI a machine has; it has to match
the one the CLI was built against. A mismatch can point either way: a copied
`node_modules` (built on another machine) under the host Node, or a pinned
runtime under parsers that were rebuilt on this host. The adapter now names the
Node it actually loaded at the start of the error, and `setup.sh` prints the
error itself, so run it rather than reasoning from versions.

Three ways out, in order of preference:

1. **Pin the runtime next to the CLI.** Put a matching Node in
   `tools/external/dolos-cli/node/bin/` and rsync `tools/external/` as a whole.
   The adapter puts that directory ahead of `PATH` (and still honours the older
   `node20/bin` location). If the parsers were already rebuilt on this host, pin
   the runtime *and* rebuild for it:
   `cd tools/external/dolos-cli && PATH="$PWD/node/bin:$PATH" npm rebuild`.
2. **Use the host's Node instead**: move the pinned runtime aside
   (`mv node node.unused`) when the parsers were rebuilt here. Fast, but the
   pairing is then host-specific and does not survive a fresh rsync.
3. **Use the standalone Dolos binary** under `tools/external/dolos/`, which has
   no Node dependency at all.

`bash scripts/gpu/setup.sh` runs both tools once on two toy files and prints
`OK`/`BROKEN` with the tool's own output, so this is caught before a full run.
A failed batch still marks the whole tool unavailable rather than scoring from
partial output.

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
