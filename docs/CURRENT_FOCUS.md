# Current Focus (updated 24 November 2026)

**CURRENT MODE: Detection Honesty & Pilot Readiness** (post-case-loop phase)

> **Reminder:** Update this file when your main focus shifts. Codex relies on it being accurate.

**Working Mode** (update this when switching):
- **Current Mode**: Detection honesty + getting ready for the pilot (`docs/PILOT_RUNBOOK.md`)
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
- **Human-code FP baseline measured & published in-product**: after the
  2026-09-21 recalibration, **2.3%** of real novice student Python flags at the
  0.70 high band (9.8% at 0.40 medium; was 21%/47% pre-fix); 0% on
  community/expert code. See `docs/HUMAN_FP_BASELINE.md` — surfaced on the
  accuracy page, results banner, and dossier evidence details.
- **E2E verified on a from-scratch stack** (fresh Postgres → full alembic chain →
  integration 30/30 → live upload/dossier/viva/PDF). Alembic runs clean from
  zero (head `e2f4a6b8c0d1` at the time; now `u4v5w6x7y8z9`, and CI checks
  that migrations create every table and column the models use).
- **FP deep-dive** (2026-08-22, `docs/HUMAN_FP_BASELINE.md` § Per-file deep-dive):
  style, not length, drives student flags, so a length-based "short submission"
  annotation was rejected.
- **Plagiarism-side false matches (October)**: code most of the class shares is
  left out and professors are told; tiny, empty, starter-code and reordered pairs
  are held at review with a stated reason.
- **Class-level evaluation** (2026-10-25): runner and October baseline in
  `docs/BENCHMARK_WORK.md`.
- **Sharing and workspace settings** (PR #9, 2026-10-25): courses, analyses and
  cases are private unless shared; per-workspace settings, encrypted credentials
  and notifications. Rollout notes in `docs/ROLLOUT_SHARING_AND_SETTINGS.md`.
- **Results page → case**: a flagged pair can open a case directly (2026-10-26).
- **First external AI holdout** (2026-11-06, CoDet-M4 Python, source-balanced):
  live blend AUC 0.523 vs 0.591 in-domain; the ML classifier transfers (0.667),
  the heuristic does not (0.458). Offline fusion sweeps gain ≤0.03 within the
  student-FP contract, so the blend was left unchanged. Details in
  `docs/AI_DETECTOR_VS_TURNITIN.md` § External holdout.
- **Similarity explanations are the score's own terms** (PR #25, 2026-11-10):
  each pair's `contributions` are the learned model's coefficient × feature, so
  the results page leads with the engines that raised the score (mostly
  winnowing), not embedding, which the model barely weights. Chunked pairs use
  the strongest chunk's terms.
- **Similarity accuracy measured on trusted labels** (2026-11-11, ConPlag class
  evaluation; `docs/BENCHMARK_WORK.md` § ConPlag): on par with JPlag/Dolos
  (AUC 0.813 vs 0.821/0.838); 2.3% of innocent pairs reach the high band and
  64% of copies reach the review band. Misses are copies rewritten inside a
  personal template, which no engine (or tool) separates from innocent work;
  containment scoring was tried and rejected. **Do not chase false flags from
  the Kaggle labels**: some of its "innocent" pairs are copies (§ Class-level
  evaluation).
- **Honest product copy** (PRs #36–#41, 2026-11-12): the README, upload panel,
  assignment types, Integrity Assessment Report and settings say only what the
  product does. **AI authorship checks are off by default** (#41), because the
  detector ranks near chance out of domain.
- **Organization membership** (PRs #43–#47, 2026-11-13;
  `docs/ORGANIZATION_MEMBERSHIP_DESIGN.md`): existing users join the
  institution's organization (migration `u4v5w6x7y8z9`, with a dry-run script),
  new accounts join it, admins add and remove members, and cases require
  membership plus access to the analysis. `/api/v1` applies per-person job
  access (#42). Admin user listing is deployment-wide by design (#53).
- **Auth hardening** (PR #48): Argon2id passwords, and sessions end on password
  change (7-day cap). UTORid / Entra ID sign-in is planned for **after** the
  pilot (`docs/SSO_PLAN.md`, not started).
- **Pilot runbook** (PR #50): approvals, deploy freeze, configuration, backup,
  deploy and rollback, smoke tests, go/no-go — `docs/PILOT_RUNBOOK.md`.
- **Overnight fixes** (PR #52, 2026-11-23; `docs/OVERNIGHT_REPORT.md`): added
  `#` / `//` comments no longer hide matched code; a UTF-8 BOM no longer
  changes AI or similarity scores or blocks starter-code removal; the dossier
  PDF is the dossier; the cases list shows priority, not an invented "Risk %".
- **Case page lists its linked pairs** (PR #55), showing only analyses the
  viewer can open; three orphaned dashboard pages were removed (PR #54).
- **Integration tests sign in** (PR #57): `test_professor_journey` and
  `test_benchmark_tool_errors` use a signed-in client fixture.
- **Security review fixes** (PRs #58–#59, 2026-11-24): detector calibrate and
  retrain are admin-only; every model file loads through the restricted
  unpickler (`src/backend/utils/safe_pickle.py`); the stale
  `engines/ai_detection/ai_detection.py` fork is gone; MD5/SHA-1 replaced by
  SHA-256 (the learned-fusion feature cache rebuilds once on the next retrain).
- **Tests stay off the shared database** (2026-11-24): `tests/conftest.py`
  switches a remote `DATABASE_URL` to a local test database unless
  `ALLOW_REMOTE_TEST_DB=1`; `pytest.ini` no longer stops at the first failure.
  Setup in the README § Testing & CI.

## Current Active Areas

1. **Student-code holdout (the #1 ceiling-raiser)** — tooling is DONE
   (ingestion round-trips exactly, grouped benchmark runs). Blocker is labelled
   institutional data; the ask is packaged in `docs/STUDENT_DATA_REQUEST_PACK.md`
   (pilot scope: 60–100 ground-truth samples). **This is a user-side data
   acquisition task, not a coding task.**
2. **Threshold/banding review** — deliberately GATED on the real holdout; do not
   move bands on the unlabelled corpus alone. ConPlag shows lowering bands is not
   a cheap recall win (76 of 251 copies score under 0.3).
3. **Disguised similarity copies (optional research)** — catching copies rewritten
   inside a template would need per-function or template-stripped comparison.
   Multi-day, uncertain payoff, since JPlag and Dolos stop at the same place; only
   start it on request.
4. **Pilot go/no-go** (`docs/PILOT_RUNBOOK.md` § 1 and § 7): Information Risk
   Assessment and data-steward sign-off, load test at the largest pilot class,
   restore test. Approvals are user-side.
5. **Coverage feature fix + retrain** (`docs/OVERNIGHT_REPORT.md` § Held back):
   `#` comments still zero the `coverage` feature. The patch is ready but makes
   Kaggle AUC worse without a retrain (0.880 → 0.867), so it ships only together
   with a learned-fusion retrain on the GPU host, followed by the ConPlag and
   Kaggle class evaluations.
6. **Production calibrator file** (follow-up to PR #58): if the pilot host has
   `src/backend/.calibrator.pkl`, it was written before retraining became
   admin-only, so any signed-in user could have made it. Delete it unless its
   origin is known. This is an operations step, not a code change.

## Must-Read Files

- `docs/AI_DETECTOR_VS_TURNITIN.md` — capability matrix, honest gaps, ordering
- `docs/HUMAN_FP_BASELINE.md` — the measured FP numbers and caveats
- `docs/AI_HOLDOUT_COLLECTION.md` — data-acquisition checklist
- `docs/SCHEMA_OVERVIEW.md` — schema reference (avoid full database.py)

## Files to Avoid Reading Unless Explicitly Asked

- `src/backend/models/database.py` — use `SCHEMA_OVERVIEW.md`
- `src/backend/api/server.py` (19k+ lines) — grep, don't read whole
- Large migration files unless schema debugging is the explicit task

## Session Rules for Codex

- Same as before: prefer small focused files, grep server.py, be token-aware.
- High-risk areas (auth, migrations, background jobs) per AGENTS.md.
- Validate changes: `pytest tests/unit/` first; `tsc --noEmit` for frontend.

## Current Mindset

- Measure, then claim. Every accuracy statement in the product should trace to
  a reproducible script or benchmark report.
- The viva-question framing is the product's safety mechanism — keep copy
  discipline ("decision support, never proof") intact in every surface.
