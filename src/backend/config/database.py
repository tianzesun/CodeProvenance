from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / '.env.local')
"""Database configuration and session management."""
import os
from typing import Optional, ContextManager
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from contextvars import ContextVar

# Get database URL from environment or use SQLite as default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./integritydesk.db")

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
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


def _apply_sqlite_compat_migrations() -> None:
    """Patch older SQLite databases with columns added after initial table creation."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    statements = []

    if "reset_token" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255)")
    if "reset_token_expires" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def init_db() -> None:
    """Initialize the database, creating all tables."""
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_compat_migrations()


def drop_db() -> None:
    """Drop all tables from the database."""
    Base.metadata.drop_all(bind=engine)
