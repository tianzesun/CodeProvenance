"""Database configuration and session management."""

import os
from contextvars import ContextVar
from pathlib import Path
from typing import ContextManager, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv(Path(__file__).parent.parent / ".env.local")

# Get database URL from environment. Do not fall back to a local SQLite database.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Set it in src/backend/.env.local; local SQLite is not "
        "supported for the backend runtime."
    )
if DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "SQLite DATABASE_URL values are not supported for the backend runtime. Use the "
        "remote PostgreSQL/Neon DATABASE_URL from src/backend/.env.local."
    )

# Create engine with PostgreSQL/Neon settings.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tenant context variable for request-scoped context
_tenant_context: ContextVar[Optional[str]] = ContextVar("_tenant_context", default=None)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def get_db() -> ContextManager[Session]:
    """Get a database session context manager.

    Usage:
        with get_db() as db:
            db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_tenant_context(db: Session, tenant_id: str) -> None:
    """Set tenant context for the current request.

    This is used for multi-tenant isolation.
    """
    _tenant_context.set(tenant_id)


def get_tenant_context() -> Optional[str]:
    """Get the current tenant context.

    Returns:
        The current tenant_id or None if not set.
    """
    return _tenant_context.get()


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    _tenant_context.set(None)


def init_db() -> None:
    """Initialize the database, creating all tables."""
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all tables from the database."""
    Base.metadata.drop_all(bind=engine)
