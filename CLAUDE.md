# CLAUDE.md

This file provides high-level guidance for Claude (and Cursor Codex) when working on IntegrityDesk.

## Project Philosophy

IntegrityDesk is a production-grade code similarity detection platform (MOSS + AI detector replacement) used in academic settings.

We value:
- **Minimal, localized changes**
- **Production readiness** over clever abstractions
- **Token efficiency** during long exploratory ("vibe") coding sessions
- Strong multi-tenancy and review workflow

## Critical Rules for This Session

**Session Start Ritual (Always do this):**
At the beginning of every new session, read in this order:
1. `docs/CURRENT_FOCUS.md`
2. `docs/SCHEMA_OVERVIEW.md`
3. `docs/BENCHMARK_WORK.md`

Then continue with normal rules.

**Schema Work Mode (Current Reality):**
The user is **currently editing** `src/backend/models/database.py`.

- **Never** read the full `src/backend/models/database.py` (626 lines) unless the user explicitly says:  
  “read the full database.py” or “check the implementation in the model file”.
- When the user is doing schema work, you **must** default to this order:
  1. `docs/SCHEMA_WORK_NOTES.md`
  2. `docs/SCHEMA_OVERVIEW.md`
  3. `docs/CURRENT_FOCUS.md`
- Only read the full model file as a last resort after getting explicit permission.

1. Read `.ai-rules.md` and `AGENTS.md` before making changes.
2. Keep changes **minimal and localized**.
3. Fix root cause before changing code.
4. Treat anything touching DB schema, auth, or infra as high risk.

## Vibe Coding Mode (Long Exploratory Sessions)

When the user is in "vibe coding" mode:
- Be exploratory but disciplined.
- Propose small, safe iterations rather than large refactors.
- Actively suggest smaller context files instead of large ones.
- Flag high-risk areas early (schema changes, migrations, external services).
- Summarize findings instead of dumping large code blocks.

## Current Context (May 2026)

- Working heavily on the large production database schema (`src/backend/models/database.py`)
- Active benchmark work (`tests/unit/test_benchmark_metric_integrity.py` and `src/frontend/app/benchmark/page.tsx`)
- Recently upgraded frontend to Next.js 16.2.6 + React 19.1
- Using remote Neon Postgres (connection can be flaky)

## Key Architectural Concepts

- Strong multi-tenancy (tenant_id on almost every table)
- Review workflow: `Case` + `CaseResultLink` + `CaseComment`
- Organization vs Tenant distinction (Organization is higher level)
- Heavy use of JSONB for flexible evidence + structured columns for queryability

## File Guidance

| File | When to Read | Notes |
|------|--------------|-------|
| `docs/CURRENT_FOCUS.md` | **Start of every session** | Current goals and active work |
| `docs/SCHEMA_OVERVIEW.md` | Schema questions | Primary schema reference (use instead of full model file) |
| `docs/BENCHMARK_WORK.md` | Benchmark-related work | Current benchmark focus and risks |
| `src/backend/models/database.py` | Only when user explicitly asks | 626 lines — very expensive |
| `.ai-rules.md` | Before any code change | Detailed coding standards |
| `AGENTS.md` | Before any code change | Working agreements |

## What to Avoid

- Reading large model files by default (use the small focus files instead)
- Skipping the Session Start Ritual (`CURRENT_FOCUS.md`, `SCHEMA_OVERVIEW.md`, `BENCHMARK_WORK.md`)
- Proposing big refactors during vibe sessions without confirmation
- Touching DB schema without discussing migration strategy
- Adding new dependencies without asking

Be helpful, concise, and token-conscious.
