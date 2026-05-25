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

1. **Never read the full `src/backend/models/database.py`** (626 lines) unless the user explicitly says so.
   - Always prefer `@docs/SCHEMA_OVERVIEW.md` for schema questions.
2. Read `.ai-rules.md` and `AGENTS.md` before making changes.
3. Keep changes **minimal and localized**.
4. Fix root cause before changing code.
5. Treat anything touching DB schema, auth, or infra as high risk.

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
| `docs/SCHEMA_OVERVIEW.md` | Almost always for schema work | Primary schema reference |
| `src/backend/models/database.py` | Only when user explicitly asks | 626 lines — very expensive |
| `.ai-rules.md` | Before any code change | Detailed coding standards |
| `AGENTS.md` | Before any code change | Working agreements |
| `docs/PROJECT_STRUCTURE.md` | When unsure about file locations | High-level structure |

## What to Avoid

- Reading large model files by default
- Proposing big refactors during vibe sessions without confirmation
- Touching DB schema without discussing migration strategy
- Adding new dependencies without asking

Be helpful, concise, and token-conscious.
