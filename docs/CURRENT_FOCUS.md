# Current Focus (May 2026)

**CURRENT MODE: Schema Work Mode** (Actively editing `src/backend/models/database.py`)

> **Reminder:** Update this file when your main focus shifts. Codex relies on it being accurate.

**Working Mode** (update this when switching):
- **Current Mode**: Schema Work Mode (actively editing `database.py`)
- Alternative modes: Benchmark Mode, General Exploration

> **Session Start Ritual (Mandatory for Codex)**
> At the beginning of every session, read these files **in this exact order**:
> 1. `docs/CURRENT_FOCUS.md` (this file)
> 2. `docs/SCHEMA_OVERVIEW.md`
> 3. `docs/BENCHMARK_WORK.md`
>
> Only after reading the above three files should you continue with the rest of the session.

**Primary Goal**: Deep work on the large production database schema + benchmark metric integrity system.

## Current Active Areas

1. **Database Schema** (`src/backend/models/database.py`)
   - Large, complex multi-tenant schema (Organization, Course, Assignment, Case, Review Workflow, etc.)
   - Work is happening directly in the model definitions

2. **Benchmark Metric Integrity** (`tests/unit/test_benchmark_metric_integrity.py`)
   - Focused on correctness and statistical rigor of benchmark metrics

3. **Benchmark Frontend** (`src/frontend/app/benchmark/page.tsx`)
   - UI for the benchmark system

## Must-Read Files (Read These First)

- `docs/SCHEMA_OVERVIEW.md` — Primary schema reference (use instead of the full model file)
- `docs/CURRENT_FOCUS.md` — This file (always read at session start)
- `docs/BENCHMARK_WORK.md` — Details on current benchmark work
- `CLAUDE.md` — Session rules and token efficiency guidelines
- `.cursorrules` — Hard rules for Codex behavior

## Files to Avoid Reading Unless Explicitly Asked

- `src/backend/models/database.py` (626 lines) — Very expensive. Use `SCHEMA_OVERVIEW.md` instead.
- Large migration files unless schema debugging is the explicit task

## Session Rules for Codex

- At the start of every new session, read:
  1. `docs/CURRENT_FOCUS.md`
  2. `docs/SCHEMA_OVERVIEW.md`
  3. `docs/BENCHMARK_WORK.md`
- Strongly prefer small, focused files over large ones.
- When exploring schema, default to `SCHEMA_OVERVIEW.md`.
- When working on benchmarks, default to `BENCHMARK_WORK.md`.
- Be explicit about token usage — suggest smaller alternatives when possible.
- Flag anything that would require reading the full `database.py`.

## Current Mindset

- Long, exploratory vibe coding sessions
- High focus on correctness (especially benchmark metrics)
- Careful with schema changes (high risk area)
- Token efficiency is important

Update this file when your main focus shifts.
