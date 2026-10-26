# Benchmark Work (updated October 2026)

**Current Focus**: Benchmark Metric Integrity + Benchmark System Improvements

## Primary Objective

Ensure the benchmark system produces **statistically sound, reproducible, and trustworthy** results. Heavy emphasis on metric integrity testing.

## Key Active Files

- `tests/unit/test_benchmark_metric_integrity.py` — Core integrity tests for benchmark metrics
- `src/frontend/app/benchmark/page.tsx` — Frontend for the benchmark system
- `src/backend/benchmark/runners/class_evaluation_runner.py` — class-level evaluation (see below)
- `src/backend/benchmark/runners/learned_fusion_training_runner.py` — trains the production
  learned-fusion score (procedure in `docs/FUSION_TRAINING_WORKFLOW.md`)
- `docs/SCHEMA_OVERVIEW.md` — Needed when benchmark work touches data models

## Important Context

- Learned fusion is the production primary score; training and `engine-eval` runs belong on
  the GPU host (`docs/GPU_TRAINING_RUNBOOK.md`).
- Threshold and band changes are gated on a labelled student-code holdout
  (`docs/STUDENT_DATA_REQUEST_PACK.md`).
- Focus is on correctness, not just speed or features.
- Statistical rigor and false positive / false negative analysis are important.

## Things Codex Should Watch For

- Any changes that could affect metric calculation reproducibility
- Hidden assumptions in how submissions, jobs, or similarity results are structured
- Inconsistencies between backend models and what the benchmark tests expect
- Performance vs correctness trade-offs (flag them)

## Preferred Approach

- When exploring benchmark logic, start with the integrity test file.
- When schema questions arise during benchmark work, use `SCHEMA_OVERVIEW.md` first.
- Propose small, testable changes.
- Be explicit about what data/models the benchmark depends on.

## Current Risks / Watch Items

- Large schema file (`src/backend/models/database.py`) can easily pollute context.
- Frontend benchmark page may be out of sync with backend changes.

## Session Guidance

When the user is in a benchmark-focused session:
- Prioritize `test_benchmark_metric_integrity.py`
- Keep schema exploration lightweight using the overview file
- Flag any proposed change that would require deep changes to the schema

Update this file as the benchmark focus evolves.

## Class-level evaluation (October 2026)

`python -m src.backend.benchmark.runners.class_evaluation_runner` scores **every pair in each
class** through the production path (class-shared code removed, small files held at review) and
writes `reports/class_evaluation/`. Use it, not the pair-by-pair engine evaluation, for "how much
of a class does a professor see flagged". The engine evaluation's negatives are often hand-picked
look-alikes, so its false-positive rate is not a class flag rate.

Baseline (25 Oct 2026, threshold 0.75):

| Class | Pairs | AUC | Share of class flagged | Labelled copies caught | Labelled look-alikes flagged |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kaggle student code (174 submissions) | 15,051 | 0.874 | 2.5% | 92.9% | 49.7% |
| IR-Plag, 7 cases (56–70 each) | 1,540–2,415 | 0.45–0.91 | 31–79% | 50–92% | 13–93% |

Findings:
- On a realistic class (Kaggle) scoring behaves well: few pairs flagged, most copies caught.
- IR-Plag cases are hello-world-sized exercises where independent solutions are genuinely
  near-identical; in three cases they outscore the copies. No threshold or class-relative rule
  separates them, so IR-Plag should not drive threshold or calibration decisions.
- Class-relative re-scoring (subtracting the class median) was considered and rejected: it does
  not help where look-alikes outscore copies, and Kaggle does not need it.
