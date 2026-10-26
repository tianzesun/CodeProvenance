"""Fail when the migrated database is missing tables or columns the models use.

A column added to ``src/backend/models/database.py`` without a migration works
on a hand-patched dev database but breaks every fresh install, the first time
the ORM selects or inserts it. CI runs this right after ``alembic upgrade head``
on an empty Postgres.

Missing tables and columns fail the check. Nullability differences are printed
for information only.

Usage:
    python scripts/check_schema_drift.py   # uses the configured DATABASE_URL
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backend.config.settings import get_settings  # noqa: E402
from src.backend.models.database import Base  # noqa: E402


def find_drift(url: str) -> tuple[list[str], list[str]]:
    """Return (problems, notes) comparing model metadata with the database."""
    inspector = inspect(create_engine(url))
    existing = set(inspector.get_table_names())
    problems: list[str] = []
    notes: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            problems.append(f"missing table: {table.name}")
            continue
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        for column in table.columns:
            found = columns.get(column.name)
            if found is None:
                problems.append(f"missing column: {table.name}.{column.name}")
            elif found["nullable"] != column.nullable and not column.primary_key:
                notes.append(
                    f"nullability differs: {table.name}.{column.name} "
                    f"(model nullable={column.nullable}, db nullable={found['nullable']})"
                )
    return problems, notes


def main() -> int:
    problems, notes = find_drift(get_settings().DATABASE_URL.get_secret_value())
    for line in notes:
        print(f"note: {line}")
    for line in problems:
        print(f"error: {line}")
    if problems:
        print(f"{len(problems)} schema problem(s): add a migration for each.")
        return 1
    print("Migrated schema has every table and column the models use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
