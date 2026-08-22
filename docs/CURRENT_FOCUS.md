# Current Focus (August 2026)

**CURRENT MODE: Detection Honesty & Product Hardening** (post-case-loop phase)

> **Reminder:** Update this file when your main focus shifts. Codex relies on it being accurate.

**Working Mode** (update this when switching):
- **Current Mode**: Detection honesty + closing the professor case loop
- Alternative modes: Benchmark Mode, Schema Work Mode (dormant — schema is stable)

> **Session Start Ritual (Mandatory for Codex)**
> At the beginning of every session, read these files **in this exact order**:
> 1. `docs/CURRENT_FOCUS.md` (this file)
> 2. `docs/AI_DETECTOR_VS_TURNITIN.md` (capability matrix + honest gaps)
> 3. `git log --oneline -15` (actual state; docs can lag)
>
> Only after the above should you continue with the rest of the session.

**Primary Goal**: ship a credible, honestly-calibrated academic-integrity product.
The professor case loop is complete (detect → dossier → viva questions → PDF →
outcome recording); the current phase is making the detector's *numbers* as honest
as its UI.

## What is done (don't re-plan these)

- **Case loop end-to-end**: similarity + AI detection + web provenance → unified
  dossier with viva questions → printable PDF → `viva_outcomes` recording
  (migration `e2f4a6b8c0d1`, rollback verified)
- **Learned fusion** is the production primary score (LOGO AUC 0.865 on 1371 pairs,
  artifact retrained 2026-08-22); training runner lives at
  `src/backend/benchmark/runners/learned_fusion_training_runner.py`
- **Human-code FP baseline measured & published in-product**: 21% of real novice
  student Python flags at the 0.70 high band, 47% at 0.40 medium; 0% on
  community/expert code. See `docs/HUMAN_FP_BASELINE.md` — surfaced on the
  accuracy page, results banner, and dossier evidence details.
- **E2E verified on a from-scratch stack** (fresh Postgres → full alembic chain →
  integration 30/30 → live upload/dossier/viva/PDF). Alembic runs clean from
  zero (head `e2f4a6b8c0d1`).

## Current Active Areas

1. **Student-code holdout (the #1 ceiling-raiser)** — tooling is DONE
   (ingestion round-trips exactly, grouped benchmark runs). Blocker is labelled
   institutional data; the ask is packaged in `docs/STUDENT_DATA_REQUEST_PACK.md`
   (pilot scope: 60–100 ground-truth samples). **This is a user-side data
   acquisition task, not a coding task.**
2. **FP deep-dive** — per-file score analysis of the kaggle student corpus
   (length ↔ flag-rate interaction) to ground any short-code uncertainty
   annotation in data rather than guesswork.
3. **Threshold/banding review** — deliberately GATED on the real holdout; do not
   move bands on the unlabelled corpus alone.

## Must-Read Files

- `docs/AI_DETECTOR_VS_TURNITIN.md` — capability matrix, honest gaps, ordering
- `docs/HUMAN_FP_BASELINE.md` — the measured FP numbers and caveats
- `docs/AI_HOLDOUT_COLLECTION.md` — data-acquisition checklist
- `docs/SCHEMA_OVERVIEW.md` — schema reference (avoid full database.py)

## Files to Avoid Reading Unless Explicitly Asked

- `src/backend/models/database.py` — use `SCHEMA_OVERVIEW.md`
- `src/backend/api/server.py` (13k+ lines) — grep, don't read whole
- Large migration files unless schema debugging is the explicit task
- `docs/TODO.md` — historical 48-week roadmap, largely superseded

## Session Rules for Codex

- Same as before: prefer small focused files, grep server.py, be token-aware.
- High-risk areas (auth, migrations, background jobs) per AGENTS.md.
- Validate changes: `pytest tests/unit/` first; `tsc --noEmit` for frontend.

## Current Mindset

- Measure, then claim. Every accuracy statement in the product should trace to
  a reproducible script or benchmark report.
- The viva-question framing is the product's safety mechanism — keep copy
  discipline ("decision support, never proof") intact in every surface.
