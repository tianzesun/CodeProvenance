# AI-Generated Code Detection Module

Optional next-generation detection layer for CodeProvenance. It keeps the
legacy pattern/scoring heuristics and adds an ensemble scorer that fuses
**tree-sitter AST features**, **perplexity / burstiness**, **stylometry** and
an optional trained **ML classifier** into a single AI-likelihood score.

No network access is required: the transformer path is opt-in and only used
when a model is explicitly configured (see below).

## Layout

| File | Purpose |
|------|---------|
| `ast_features.py` | `TreeSitterASTExtractor` → `ASTFeatureVector` (11 features) for Python/Java/C/C++/C#/JS/TS/Go/Rust; regex lexical fallback for other languages |
| `perplexity.py` | `PerplexityScorer` — windowed (25 lines, 5 overlap) bigram perplexity + burstiness; per-document statistical fallback; optional cached HuggingFace LM |
| `classifier.py` | `AICodeClassifier` (sklearn `HistGradientBoostingClassifier`, 24-feature fixed vector), versioned save/load |
| `ensemble.py` | `AIEnsembleConfig` + `AIEnsembleScorer` — weighted fusion, `flagged_regions`, config from `ai_ensemble_config.yaml` |
| `ai_ensemble_config.yaml` | Hot-loadable weights / thresholds / classification switch |
| `train_classifier.py` | CLI to train and evaluate the classifier |
| `orchestrator.py` | Orchestrates all engines; ensemble is Layer 4; selects ML mode when classifier present |
| `models/` | Saved classifier joblib files (gitignored at runtime) |

## How scoring works

`AIEnsembleScorer.score(code, language)` produces:

- `ai_probability` — fused score in `[0,1]`
- `signals` — `ast`, `stylometry`, `perplexity`, `burstiness`, `pattern_library`
- `flagged_regions` — line ranges whose windowed perplexity < 2.0 (`low_perplexity`),
  plus `reason`/`severity`/`detail` for the UI breakdown
- `mode` — `heuristic` (no trained model) or `ml` (classifier active)
- `classifier` — `{ai_probability, version}` when active

Weights by mode (from `ai_ensemble_config.yaml`):

| Signal | heuristic | ml |
|--------|-----------|----|
| classifier | — | 0.45 |
| ast | 0.20 | 0.15 |
| stylometry | 0.25 | 0.15 |
| perplexity | 0.25 | 0.15 |
| burstiness | 0.15 | 0.10 |
| pattern_library | 0.15 | — |

The orchestrator (`_get_ensemble()`) loads the scorer lazily. When a trained
classifier exists **and** `classification.enabled: true`, the ML ensemble score
is trusted; otherwise the heuristic-fusion signal path is used. Every module
degrades gracefully (untrained model → neutral 0.5, no tree-sitter binding →
regex fallback, short code → 0.0).

## Thresholds

Aligned with `_ai_bucket` in `src/backend/api/server.py`:

| Threshold | Value |
|-----------|-------|
| `medium_risk` | 0.40 |
| `high_risk` | 0.70 |
| `refactor_selection` | 0.35 |

## Retraining the classifier

### Labeled dataset

Either a directory:

```
data/
  ai/     <- one file per AI-generated submission
  human/  <- one file per human-written submission
```

or a JSON/JSONL file:

```json
{"samples": [{"code": "...", "label": 1, "source": "optional"}]}
```

`label` is `1` (AI) or `0` (human). Exactly like the similarity-engine
datasets, the classifier learns from the *feature vectors*, not raw code.

### Training command

```bash
python -m src.backend.engines.ai.train_classifier data/ \
    --model-dir src/backend/engines/ai/models
```

Requires ≥10 samples covering both classes. A stratified 20% holdout is kept
for evaluation; the run prints accuracy / precision / recall / F1 / AUC plus
misclassified samples for debugging. The model is saved with a versioned
filename (`ai_code_classifier_<hash>_<timestamp>.joblib`).

### Making the classifier active

1. Train (above) — model lands in `src/backend/engines/ai/models/`.
2. In `ai_ensemble_config.yaml`, set `classification.enabled: true`.
   Optionally override `classification.model_dir`.

The scorer auto-loads the latest model; the orchestrator then uses `ml` mode.

## Recalibration

- Weight/severity rebalancing → edit `ai_ensemble_config.yaml` (hot reload).
- Full rebuild → delete old joblib files under `models/` and retrain.
- The `perplexity` section tweaks the window (`window_lines`), overlap
  (`overlap_lines`), and flags a transformer LM.

## Optional HuggingFace LM

Transformers/model downloads are expensive and are **never** triggered
automatically. To use a locally cached code LM for perplexity instead of the
statistical model, set either:

- `perplexity.huggingface_model` in `ai_ensemble_config.yaml`, or
- the `AICODE_TRANSFORMER_MODEL` environment variable

to a locally cached name (e.g. `microsoft/codebert-base`). Without these, the
scorer uses the statistical bigram model and never touches the network.

## Persistence

Per-job results (including `flagged_regions` and `classifier_details`) are
persisted to the `ai_detection_results` table (see
`alembic/versions/c0d1e2f3a4b5_add_ai_detection_results.py`). Writes are
best-effort: an insert failure is logged and does not fail the analysis job.