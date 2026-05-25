# Benchmark Work (May 2026)

**Current Focus**: Benchmark Metric Integrity + Benchmark System Improvements

## Primary Objective

Ensure the benchmark system produces **statistically sound, reproducible, and trustworthy** results. Heavy emphasis on metric integrity testing.

## Key Active Files

- `tests/unit/test_benchmark_metric_integrity.py` — Core integrity tests for benchmark metrics
- `src/frontend/app/benchmark/page.tsx` — Frontend for the benchmark system
- `docs/SCHEMA_OVERVIEW.md` — Needed when benchmark work touches data models

## Important Context

- The project recently went through a large schema merge (cms branch).
- Benchmark work must remain stable despite ongoing schema evolution.
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
- Some benchmark code may still reference older model patterns from before the cms merge.
- Frontend benchmark page may be out of sync with backend changes.

## Session Guidance

When the user is in a benchmark-focused session:
- Prioritize `test_benchmark_metric_integrity.py`
- Keep schema exploration lightweight using the overview file
- Flag any proposed change that would require deep changes to the schema

Update this file as the benchmark focus evolves.
