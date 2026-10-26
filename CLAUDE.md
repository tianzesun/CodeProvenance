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
At the beginning of every new session, follow the ritual in `docs/CURRENT_FOCUS.md`:
1. `docs/CURRENT_FOCUS.md`
2. `docs/AI_DETECTOR_VS_TURNITIN.md`
3. `git log --oneline -15` (docs can lag the code)

Read `docs/SCHEMA_OVERVIEW.md` for schema questions and `docs/BENCHMARK_WORK.md` for
benchmark work.

**Large files:**
- **Never** read the full `src/backend/models/database.py` (~1,360 lines) unless the user
  explicitly asks; use `docs/SCHEMA_OVERVIEW.md` instead.
- `src/backend/api/server.py` is 19k+ lines: grep it, don't read it whole.

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

## Current Context (October 2026)

- Detection honesty and product hardening; see `docs/CURRENT_FOCUS.md` for what is done and open
- Schema is stable (no active schema work)
- Recently upgraded frontend to Next.js 16.2.6 + React 19.1
- Using remote Neon Postgres (connection can be flaky)

## Key Architectural Concepts

- Strong multi-tenancy (`tenant_id` on tenant-level tables, `organization_id` on academic ones)
- Review workflow: `Case` + `CaseResultLink` + `CaseComment` + `PairReview`
- Courses, analyses and cases are private unless shared (`ResourceShare`)
- Organization vs Tenant distinction (Organization is higher level)
- Heavy use of JSONB for flexible evidence + structured columns for queryability

## File Guidance

| File | When to Read | Notes |
|------|--------------|-------|
| `docs/CURRENT_FOCUS.md` | **Start of every session** | Current goals and active work |
| `docs/SCHEMA_OVERVIEW.md` | Schema questions | Primary schema reference (use instead of full model file) |
| `docs/BENCHMARK_WORK.md` | Benchmark-related work | Current benchmark focus and risks |
| `docs/AI_DETECTOR_VS_TURNITIN.md` | **Start of every session** | Capability matrix and honest gaps |
| `src/backend/models/database.py` | Only when user explicitly asks | ~1,360 lines — very expensive |
| `.ai-rules.md` | Before any code change | Detailed coding standards |
| `AGENTS.md` | Before any code change | Working agreements |

## What to Avoid

- Reading large model files by default (use the small focus files instead)
- Skipping the Session Start Ritual (`CURRENT_FOCUS.md`, `AI_DETECTOR_VS_TURNITIN.md`, `git log`)
- Proposing big refactors during vibe sessions without confirmation
- Touching DB schema without discussing migration strategy
- Adding new dependencies without asking

Be helpful, concise, and token-conscious.
