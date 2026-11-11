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

`python -m src.backend.benchmark.runners.class_evaluation_runner [--datasets ...]` scores
**every pair in each class** through the production path (class-shared code removed, small files
held at review) and writes `reports/class_evaluation/`: a Markdown table at the default review
policy's bands (review ≥0.35, high ≥0.65), a JSON report that also keeps 0.75/0.95, and every
labelled pair with its engine features and score contributions (`*_labelled_pairs.jsonl`). Use it, not the pair-by-pair engine evaluation, for "how much
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
- **The Kaggle "look-alikes flagged" column is not a false-flag rate** (audited 10 Nov 2026 from
  the per-pair dump). Some innocent-labelled pairs are copies: `submission144`/`145` are
  identical, `37`/`39` differ only in identifier names. Flagged look-alikes share more identical
  lines than caught copies (median 44% vs 32%), and most are same-task variants no rule can call
  either way. Only 3 of 193 negatives are objectively wrong, so relabelling would not change
  training, but tuning on these labels would teach the product to pass renamed copies. Measure
  false flags on ConPlag (`--datasets conplag`, annotated verdicts) instead. Both corpora are in
  the learned-fusion training set, so their labelled-pair metrics are in-sample.

## ConPlag class evaluation (November 2026)

Run `CLASS_EVAL_20261111_103016` on the GPU host: 21 contest problems as classes, 911
human-annotated pairs (251 copies, 660 innocent same-problem pairs). Unlike Kaggle, these labels
can be trusted, so this is the false-flag and recall measurement to use.

| Cut-off | Copies caught | Innocent pairs flagged |
| --- | ---: | ---: |
| 0.35 (default review band) | 64.1% | 17.3% |
| 0.45 (introductory review band) | 57.8% | 8.5% |
| 0.65 (default high band) | 44.6% | 2.3% |
| 0.75 (earlier class-eval cut-off) | 40.6% | 0.8% |

Findings:
- **False flags are low; missed copies are the limit.** At the high band 2.3% of innocent pairs
  are flagged, and 0.1–4.8% of each class's pairs reach 0.75, under 2% in 17 of 21 problems
  (problem 14 is the outlier, 13.3%, with a 23-line shared template). The innocent pairs are hand-picked same-problem solutions, so
  17% at the review band overstates what a real class would see there.
- **Parity with established tools.** On the same 911 pairs (`reports/engine_evaluation/
  ENGINE_EVAL_conplag_20261022_130311.md`): Dolos AUC 0.838, JPlag 0.821, IntegrityDesk 0.813.
- **Caught copies are near-verbatim; missed ones look innocent to every engine.** Copies scoring
  ≥0.75 have every lexical engine at 1.0. For copies under 0.4, no engine separates them from
  innocent pairs (AUC 0.36–0.60). Sampled misses rewrite the copied algorithm inside each
  author's own contest template (one pair: 259 vs 39 lines).
- **Rejected: containment** (share of the smaller file found in the larger, identifier-normalised
  8-gram tokens). AUC missed-vs-innocent 0.557 vs 0.568 for plain overlap: innocent pairs share
  templates too, and the copied cores are rewritten at token level.
- **Lowering the threshold is not a fix**: 76 of 251 copies score under 0.3. Band moves stay gated
  on the student holdout.
- ConPlag and Kaggle are both in the learned-fusion training set, so their labelled-pair metrics
  are in-sample; the per-class share of pairs flagged is mostly over unlabelled pairs.
