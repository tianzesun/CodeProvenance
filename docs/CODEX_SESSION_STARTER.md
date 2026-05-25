# Codex Session Starter

Copy and paste the entire block below at the beginning of every new chat with Codex.

---

# Codex Session Start

Read these files **in this exact order** before doing anything else:

1. `docs/CURRENT_FOCUS.md`
2. `docs/SCHEMA_OVERVIEW.md`
3. `docs/BENCHMARK_WORK.md`
4. `docs/SCHEMA_WORK_NOTES.md`   (if it exists and has recent content)

After reading them, follow these rules **strictly**:

- You are in long "vibe coding" mode. Be exploratory but disciplined.
- **The user is currently editing** `src/backend/models/database.py`.
- **Never** read the full `src/backend/models/database.py` (626 lines) unless I explicitly write one of these phrases:
  - “read the full database.py”
  - “check the implementation in the model file”
- When doing schema work, you **must** default to this priority:
  1. `docs/SCHEMA_WORK_NOTES.md`
  2. `docs/SCHEMA_OVERVIEW.md`
  3. `docs/CURRENT_FOCUS.md`
- Follow all rules in `.cursorrules` and `CLAUDE.md`.
- Keep changes minimal and localized.
- Prioritize small, focused files over large ones.
- When working on benchmarks, heavily reference `docs/BENCHMARK_WORK.md` and `tests/unit/test_benchmark_metric_integrity.py`.
- Be token-conscious. Suggest smaller alternatives when possible.

Current active files:
- `src/backend/models/database.py` (schema work)
- `tests/unit/test_benchmark_metric_integrity.py`
- `src/frontend/app/benchmark/page.tsx`

Confirm you have read the required files **in order** and understood the strict rules before proceeding.
