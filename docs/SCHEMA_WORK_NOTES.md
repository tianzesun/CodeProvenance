# Schema Work Notes

**Last Updated**: 2026-05-25

## Working Mode (Update This When Switching Focus)

**Current Mode**: Schema Work Mode

- **Schema Work Mode** — Actively editing `src/backend/models/database.py` (default when deep in schema changes)
- **Benchmark Mode** — Focused on `test_benchmark_metric_integrity.py` and benchmark correctness
- **Mixed Mode** — Working across both schema + benchmark at the same time

> Update the mode above when your focus shifts. This tells Codex how strictly it should avoid reading the full `database.py`.

## Current Schema Work Focus

- Actively working inside `src/backend/models/database.py`
- Primary goal: Improve / stabilize the large production schema (post-cms merge)
- Also maintaining benchmark metric integrity during schema changes

## Current Active Changes / Considerations

(Write here what you're currently modifying, open questions, or things Codex should be aware of)

Examples:
- Adding / modifying X table
- Considering breaking change to Y relationship
- Need to keep Z metric stable

## Things Codex Should Know

- Do **not** suggest reading the full `database.py` unless explicitly asked.
- Prefer `docs/SCHEMA_OVERVIEW.md` + this file for context.
- Any proposed change should consider impact on benchmark metrics.

## Open Questions / Risks

- 

## Recent Decisions

- 
