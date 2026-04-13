# AGENTS.md

## Working agreements
- Keep edits minimal and localized
- Fix root cause before changing code
- Do not invent APIs, files, or commands
- Prefer existing project patterns over new abstractions
- Validate changes before finalizing
- Ask for confirmation before adding dependencies
- Treat auth, migrations, infra, secrets, background tasks, scheduled jobs, and external API integrations as high risk
- If a change touches DB schema, ensure a rollback migration exists

## Code Style
- Format with `black` before committing
- Lint with `ruff` (config in `pyproject.toml`)
- All functions and classes must have docstrings
- Follow PEP 8 style guide
- Maximum line length: 100 characters
- Use 4 spaces for indentation (no tabs)

## Project Specific
- This is a **Python 3.10** project using FastAPI (see requirements.txt for pinned versions)
- Use type hints for all new code
- Follow existing patterns in src/ directory
- Test changes: run relevant unit tests first with `pytest tests/unit/`, then integration tests when appropriate
- Use existing logging patterns from src/infrastructure/
- Avoid introducing async patterns unless necessary
- Always use the virtual environment: `source /home/tsun/Documents/CodeProvenance/venv/bin/activate`
- Never hardcode secrets; use .env via python-dotenv (see .env.example for reference)
- Use conventional commits: `feat:`, `fix:`, `chore:`, `refactor:`, `test:`, `docs:`
