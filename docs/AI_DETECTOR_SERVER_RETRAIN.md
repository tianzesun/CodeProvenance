# AI Detector: ship the code-LM perplexity model to the deployment host

Operations runbook for moving `microsoft/CodeGPT-small-py` onto the GPU
deployment host, retraining the AIGCodeSet classifier against it, and
re-measuring. Written 2026-10-18 to be followed on the server without reading
the code first.

## Why this is the remaining lever

The trained classifier stores which perplexity model produced its training
features (`metadata.perplexity_model`) and `AIEnsembleScorer` **ignores** a
classifier whose recorded model differs from the one the running scorer
produced (`classifier_status: feature_mismatch`). The deployment host cannot
reach HuggingFace, so `PerplexityScorer` falls back to the statistical model
and the classifier must be trained on that same statistical scale.

That fallback is what caps detection quality: with statistical perplexity the
fused AUC on AIGCodeSet is 0.6067, *below* the classifier's own grouped-holdout
AUC (~0.66), because the perplexity feature carries no real code-LM signal.
The training corpus (`data/datasets/aigcodeset`) is built from the
`huggingface_model` in `ai_ensemble_config.yaml`, so shipping the cache and
retraining is the only measured path left to raise AI-side recall without
raising student false positives. See `docs/HUMAN_FP_BASELINE.md` (§
Re-measurement 2026-10-18) for the classifier-on/off/guard A/B this follows.

**Do not skip the retrain.** Copying the cache alone changes runtime features
to `huggingface`, which makes the *existing* model mismatch and get ignored —
detection would silently fall back to the heuristic path.

## Facts the loader depends on

| Fact | Value |
| --- | --- |
| Configured model | `perplexity.huggingface_model: "microsoft/CodeGPT-small-py"` |
| Loader | `perplexity._load_cached_transformer`, `local_files_only=True` — never downloads |
| Cache root | `$HF_HOME/hub`, default `~/.cache/huggingface/hub` |
| Runtime label | `huggingface` when the checkpoint loads, else `statistical` |
| Fingerprint | `feature_rows.pipeline_fingerprint` covers extractor sources, schema version, the `perplexity` config block and `AICODE_TRANSFORMER_MODEL` |
| Grouped split needs | `data/datasets/aigcodeset/data/samples.jsonl` (present in the clean 7140-sample materialisation) |

The runbook below was validated on the laptop: the slim cache (step 1) loads
offline in ~6 s, and `PerplexityScorer.score` then reports `model: huggingface`.

---

## 1. Build a slim cache on the laptop (~490 MB instead of 1.9 GB)

The full HF directory is 1.9 GB because it holds every weight format
(`pytorch_model.bin` 509 MB, `model.safetensors` 509 MB, `tf_model.h5` 497 MB,
`flax_model.msgpack` 497 MB). Only one weight file plus the tokenizer/config
are needed. Building the slim tree also avoids copying the second, incomplete
snapshot that sits in this cache.

```bash
SRC=~/.cache/huggingface/hub/models--microsoft--CodeGPT-small-py
REV=$(cat "$SRC/refs/main" | tr -d '\n')
OUT=/tmp/opencode/codegpt-cache
rm -rf "$OUT"
DST="$OUT/hub/models--microsoft--CodeGPT-small-py"
mkdir -p "$DST/snapshots/$REV" "$DST/refs"

for f in config.json generation_config.json \
         merges.txt special_tokens_map.json tokenizer_config.json \
         vocab.json added_tokens.json; do
  cp -L "$SRC/snapshots/$REV/$f" "$DST/snapshots/$REV/$f"
done
cp -L "$SRC/snapshots/$REV/pytorch_model.bin" "$DST/snapshots/$REV/pytorch_model.bin"

# HF reads refs/main verbatim; a trailing newline makes the revision unresolvable
# ("couldn't find it in the cached files"), so write it without one.
printf '%s' "$REV" > "$DST/refs/main"
printf '1' > "$OUT/hub/version.txt"

du -sh "$OUT"                                   # expect ~490M
```

Verify it loads **before** transferring anything:

```bash
cd /path/to/CodeProvenance && source venv/bin/activate
HF_HOME=/tmp/opencode/codegpt-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -c "
from src.backend.engines.ai.perplexity import PerplexityScorer
s = PerplexityScorer(model_path='microsoft/CodeGPT-small-py')
r = s.score('def add(a, b):\n    return a + b\n')
print('model label:', r['model'])
"
# expect: model label: huggingface    (statistical => the tree is wrong)
```

Prefer the whole 1.9 GB directory instead? `rsync -a` the original
(`~/.cache/huggingface/hub/models--microsoft--CodeGPT-small-py/`) — `-a`
preserves the `snapshots/* -> ../../blobs/*` symlinks, which resolve inside the
copied directory. Both layouts work; the slim tree is just 4× smaller.

## 2. Transfer to the server

```bash
SERVER=suntian4@neurosmx10          # <-- your ssh target
ssh "$SERVER" 'mkdir -p ~/.cache/huggingface'
rsync -a --info=progress2 /tmp/opencode/codegpt-cache/hub/ \
      "$SERVER:~/.cache/huggingface/hub/"
# no rsync? pipe a tarball instead:
# tar -C /tmp/opencode/codegpt-cache/hub -cf - . \
#   | ssh "$SERVER" 'mkdir -p ~/.cache/huggingface/hub && tar -C ~/.cache/huggingface/hub -xf -'
```

Verify on the server:

```bash
ssh "$SERVER"
ls -l ~/.cache/huggingface/hub/models--microsoft--CodeGPT-small-py/snapshots/*/
# expect: pytorch_model.bin, config.json, vocab.json, merges.txt,
#         tokenizer_config.json, special_tokens_map.json, added_tokens.json,
#         generation_config.json
```

If the backend runs as a *different* user than the one you are logged in as,
either copy into that user's home or set `HF_HOME` in the app's env file
(`src/backend/api/server.py` loads `src/backend/.env.local` via dotenv):

```bash
ps -o user= -p "$(pgrep -f 'uvicorn src.backend.api.server:app' | head -1)"
# if that user is not you: add  HF_HOME=/home/suntian4/.cache/huggingface  to .env.local
```

## 3. Server pre-flight (cheap and decisive)

```bash
cd ~/projects/CodeProvenance && source venv/bin/activate

# 3a. The transformer stack must actually be installed; if not, the loader
#     falls back to statistical and nothing else in this runbook matters.
python -c "import torch, transformers; print('torch', torch.__version__, '| transformers', transformers.__version__)"

# 3b. Confirm the cache is picked up and the features get the right label.
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python - <<'EOF'
import glob
from src.backend.engines.ai.feature_rows import build_feature_rows
paths = sorted(glob.glob("data/datasets/aigcodeset/data/ai/*.py"))[:5]
codes = [open(p, encoding="utf-8", errors="replace").read() for p in paths]
build = build_feature_rows(codes, ["python"] * len(codes))
print("perplexity_model:", build.perplexity_model)
print("model counts:", dict(build.perplexity_models))
EOF
```

Expect `perplexity_model: huggingface`. If it prints `statistical`, stop here —
the cache path, `HF_HOME`, or the torch/transformers install is wrong, and a
retrain would only produce another unusable model. The loader logs the reason
at INFO level: `HF code LM microsoft/CodeGPT-small-py unavailable locally,
using statistical model: ...`.

## 4. Retrain (features ≈ 2 h on this corpus)

The corpus is already materialised (7140 samples: 2599 AI / 4541 human, with
`samples.jsonl`). Do **not** re-run `build_aigcodeset` — it would append a
second copy.

```bash
# A feature cache makes a ~2 h pass resumable (saved every 100 samples) and
# makes any later retrain with different hyper-parameters instant.
# Delete a cache built before the cache landed on the host: its fingerprint
# would still match and it would silently replay statistical features.
ls src/backend/engines/ai/models/feature_cache*.json 2>/dev/null && \
  rm -f src/backend/engines/ai/models/feature_cache*.json

nohup env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python -m src.backend.engines.ai.train_classifier data/datasets/aigcodeset/data \
    --model-dir src/backend/engines/ai/models \
    --feature-cache src/backend/engines/ai/models/feature_cache_codegpt.json \
    --refit-all \
  > /tmp/opencode/train_codegpt.log 2>&1 &
```

Measured on this corpus with the code LM: mean 0.95 s/file (median 16 lines,
p90 42) → ~2 h for 7146 samples, plus a few minutes to fit. Watch it with:

```bash
tail -f /tmp/opencode/train_codegpt.log
```

Expected lines, in order:

```
Loaded 7140 samples (2599 AI, 4541 human)
Evaluating on held-out PROBLEMS (317 groups)        <- grouped split, not random
Trained model version=... on ... samples
Refit on all 7140 samples: version=...
Saved model version=... to src/backend/engines/ai/models/ai_code_classifier_<version>.joblib
```

Two lines must **not** appear:

- `No problem ids found: using a random stratified split` — the grouped index
  (`samples.jsonl`) was not found; the reported metrics would be optimistic.
- `Perplexity came from more than one model (...)` — part of the corpus was
  scored statistically (the loader gave up mid-run); rebuild after fixing 3b.

The new model is timestamp-named and the loader always picks the newest by
modification time, so the previous model stays on disk as a rollback.

## 5. Verify the runtime agrees with the training features

```bash
HF_HUB_OFFLINE=1 python - <<'EOF'
from src.backend.engines.ai.classifier import load_shared_classifier
c = load_shared_classifier()
print("metadata:", c.metadata if c else None)
EOF

HF_HUB_OFFLINE=1 python - <<'EOF'
from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator
r = AIDetectionOrchestrator().analyze(
    "import sqlite3\n\n\ndef get_conn():\n    return sqlite3.connect('school.db')\n",
    language="python",
)
print("method:", r["method"], "| score:", r["ai_probability"])
print("fusion:", (r.get("layers") or {}).get("fusion"))
EOF
```

Expect `metadata: {'perplexity_model': 'huggingface'}` and `method: ml`. A
`feature_mismatch` warning, or `method: heuristic`, means the cache is not
visible to this shell/process (step 2) — fix that before measuring.

## 6. Restart and re-measure

```bash
bash scripts/restart.sh          # the running backend has the old features cached

# The code LM makes scoring slower (~1 s for a small file, up to ~18 s for a
# long one), so budget tens of minutes for the corpora runs.
python scripts/measure_human_fp.py --corpora kaggle_student_code --dump-scores --out /tmp/opencode/G_codelm
python scripts/measure_ai_accuracy.py --limit 400 --dump-scores /tmp/opencode/G_codelm_ai.json
```

Compare against the 2026-10-18 baseline (statistical perplexity, guard on):

| | statistical (baseline) | code LM (this run) |
| --- | ---: | ---: |
| student flagged @0.40 | 11.5% | ? |
| student flagged @0.70 | 2.87% | ? |
| AI recall @0.40 (400 files) | 6.0% | ? |
| AI-vs-human AUC | 0.6067 | ? |

Interpretation:

- **Recall/AUC up, student FP roughly flat** → the code LM paid off; keep it.
- **Student FP up noticeably** → the classifier features changed scale, so the
  `orchestrator.corroboration_floor` / `classifier_only_cap` guard (0.30 / 0.35)
  may need retuning; re-run the A/B from `docs/HUMAN_FP_BASELINE.md`.
- Numbers are **not comparable** with the laptop's or any transformer-era
  figure unless the same perplexity model is in use on both hosts.

Blend tuning does not need another corpus run: the dumps above record
`ml_score`/`heuristic_score`/`lines` per file, and

```bash
python scripts/sweep_ml_blend.py --fp-dump /tmp/opencode/G_codelm \
    --ai-dump /tmp/opencode/G_codelm_ai.json --weights 0.5,0.65,0.8,1.0
```

replays the shipped `blend_ml_heuristic` over them (the 2026-10-18 sweep showed
the shipped 0.50 is already the best operating point).

## Rollback

A model and a perplexity model are a **pair**: the loader takes the newest
`ai_code_classifier_*.joblib` by mtime, and the ensemble ignores it whenever the
runtime perplexity label differs. So reverting means reverting both.

Back to the statistical-perplexity setup (the pre-2026-10-18 state):

```bash
cd ~/projects/CodeProvenance
# 1. Hide the code-LM cache so the scorer falls back to statistical.
mv ~/.cache/huggingface/hub/models--microsoft--CodeGPT-small-py{,.disabled}
# 2. Hide the code-LM model; the statistical-trained one becomes the newest.
#    (_MODEL_GLOB is "ai_code_classifier_*.joblib", so .disabled files are
#    ignored — no need to delete anything.)
for f in src/backend/engines/ai/models/ai_code_classifier_*.joblib; do
  case "$f" in *202610182329*|*<new-version>*) mv "$f"{,.disabled};; esac
done
bash scripts/restart.sh
```

Want to keep the code LM but distrust the new classifier? That needs a retrain
on the same scale (step 4 with a different `--seed`/`--test-size`, or a smaller
corpus for a fast read) — there is no drop-in revert, because the older model's
features are on the statistical scale.
