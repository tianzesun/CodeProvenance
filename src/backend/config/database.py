"""Database configuration and session management.

Environment
-----------
DATABASE_URL                  Required. PostgreSQL only (``postgres://`` is accepted and rewritten to
                              ``postgresql://``). It contains the password, so it is never logged or put in an error.
DATABASE_POOL_SIZE            Connections kept per process (default 10).
DATABASE_MAX_OVERFLOW         Extra connections allowed per process under load (default 20).
DATABASE_POOL_TIMEOUT         Seconds to wait for a free connection (default 30).
DATABASE_POOL_RECYCLE         Seconds before a connection is replaced (default 300).
DATABASE_CONNECT_TIMEOUT      Seconds to wait when connecting (default 15).
DATABASE_SSLMODE              Used only when the URL has no ``sslmode``. Defaults to ``require`` for remote hosts.
                              Prefer ``verify-full`` in production so the server certificate is checked.
DATABASE_STATEMENT_TIMEOUT_MS Optional per-statement timeout. Poolers in transaction mode (PgBouncer, including
                              Neon's pooled endpoint) may reject the ``options`` start-up parameter this uses.
DATABASE_APPLICATION_NAME     Name shown in ``pg_stat_activity`` (default ``integritydesk-backend``).
DATABASE_TENANT_RLS           ``true`` applies the current tenant to each transaction as ``app.tenant_id`` so
                              PostgreSQL row-level-security policies can use it (see ``set_tenant_context``).
DATABASE_ALLOW_DROP           Must be ``true`` for ``drop_db(confirm=True)`` to do anything.
DATABASE_MODEL_MODULES        Comma-separated modules that define the ORM models, imported by ``init_db()`` so the
                              tables it creates are the ones you expect (e.g. ``src.backend.models.database``).
APP_ENV / APP_ENV_FILE        ``APP_ENV=production`` means the ``.env.local`` file is never read. Same rule as
                              ``settings.py``; ``APP_ENV_FILE`` points at a different file.
DEBUG_MODE                    Relaxes the TLS rule below for local development.

Nothing here connects, or even needs DATABASE_URL, until ``get_engine()`` is first used, so models can import ``Base``
without a database configured.
"""

import importlib
import logging
import os
import re
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_PLAINTEXT_SSLMODES = frozenset({"disable", "allow", "prefer"})  # may fall back to an unencrypted connection


# ── Configuration ────────────────────────────────────────────────────────────


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    """Read an integer setting. The value itself is not echoed in errors."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number.") from None
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _load_env_file() -> None:
    """Read ``.env.local`` for local development. Production (APP_ENV=production) never reads a file.

    This used to run at import time in every environment, copying whatever the file held into ``os.environ``.
    """
    if os.environ.get("APP_ENV", "development").strip().lower() == "production":
        return
    override = os.environ.get("APP_ENV_FILE")
    path = Path(override) if override else Path(__file__).resolve().parent.parent / ".env.local"
    if not path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional: without it only real environment variables are used
        return
    load_dotenv(path)


@dataclass(frozen=True)
class DatabaseConfig:
    # repr=False: the URL holds the password, and dataclasses print every field.
    url: URL = field(repr=False)
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    connect_timeout: int
    application_name: str
    statement_timeout_ms: int | None
    sslmode: str | None
    remote: bool
    tenant_rls: bool


def _load_config() -> DatabaseConfig:
    _load_env_file()

    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        # Do not fall back to a local SQLite database.
        raise RuntimeError(
            "DATABASE_URL is required. Provide it through the environment (a secret store in production, "
            "src/backend/.env.local for local development); local SQLite is not supported for the backend runtime."
        )
    try:
        url = make_url(raw)
    except Exception:
        # `from None`: the original error can contain the URL, and with it the password.
        raise RuntimeError("DATABASE_URL is not a valid database URL.") from None

    backend = url.get_backend_name()
    if backend == "sqlite":
        raise RuntimeError(
            "SQLite DATABASE_URL values are not supported for the backend runtime. Use a PostgreSQL DATABASE_URL."
        )
    if backend not in ("postgresql", "postgres"):
        raise RuntimeError(f"Only PostgreSQL is supported for DATABASE_URL (got {backend!r}).")
    if backend == "postgres":
        # Neon, Heroku and others hand out postgres://, which SQLAlchemy 1.4+ no longer accepts.
        url = url.set(drivername="postgresql" + url.drivername[len("postgres"):])

    host = url.host or ""
    remote = bool(host) and host not in _LOCAL_HOSTS and not host.startswith("/")

    # TLS. libpq's default (`prefer`) silently falls back to plaintext, so a remote host gets an explicit mode.
    in_url = url.query.get("sslmode")
    if isinstance(in_url, tuple):
        in_url = in_url[-1]
    sslmode = in_url or os.environ.get("DATABASE_SSLMODE", "").strip().lower() or ("require" if remote else None)
    if remote and sslmode in _PLAINTEXT_SSLMODES and not _flag("DEBUG_MODE"):
        raise RuntimeError(
            f"DATABASE_URL sslmode={sslmode!r} can send data unencrypted to a remote database. "
            "Use sslmode=require, or verify-full in production."
        )
    if remote and sslmode == "require" and not _flag("DEBUG_MODE"):
        logger.warning(
            "Database TLS: sslmode=require encrypts the connection but does not verify the server certificate. "
            "Use sslmode=verify-full in production."
        )

    timeout_ms = _int_env("DATABASE_STATEMENT_TIMEOUT_MS", 0, minimum=0, maximum=3_600_000)

    return DatabaseConfig(
        url=url,
        pool_size=_int_env("DATABASE_POOL_SIZE", 10, minimum=1, maximum=200),
        max_overflow=_int_env("DATABASE_MAX_OVERFLOW", 20, minimum=0, maximum=400),
        pool_timeout=_int_env("DATABASE_POOL_TIMEOUT", 30, minimum=1, maximum=600),
        pool_recycle=_int_env("DATABASE_POOL_RECYCLE", 300, minimum=30, maximum=86_400),
        connect_timeout=_int_env("DATABASE_CONNECT_TIMEOUT", 15, minimum=1, maximum=120),
        application_name=(os.environ.get("DATABASE_APPLICATION_NAME") or "integritydesk-backend").strip()[:63],
        statement_timeout_ms=timeout_ms or None,
        sslmode=sslmode,
        remote=remote,
        tenant_rls=_flag("DATABASE_TENANT_RLS"),
    )


# ── Engine and session factory (created on first use) ────────────────────────

_lock = threading.RLock()
_config: DatabaseConfig | None = None
_engine: Engine | None = None
_session_factory: "sessionmaker[Session] | None" = None
_fork_hook_registered = False


def get_config() -> DatabaseConfig:
    global _config
    with _lock:
        if _config is None:
            _config = _load_config()
        return _config


def _dispose_inherited_pool() -> None:
    # After fork() the child shares the parent's sockets. Drop them without closing, so the parent's connections
    # stay open and the child opens its own. (Matters with gunicorn --preload and multiprocessing.)
    if _engine is not None:
        _engine.dispose(close=False)


def get_engine() -> Engine:
    """The process-wide engine. Creating it does not open a connection."""
    global _engine, _fork_hook_registered
    with _lock:
        if _engine is None:
            cfg = get_config()
            connect_args: dict[str, object] = {
                "connect_timeout": cfg.connect_timeout,  # fail fast instead of hanging on an unreachable DB
                "application_name": cfg.application_name,
            }
            if cfg.sslmode and "sslmode" not in cfg.url.query:
                connect_args["sslmode"] = cfg.sslmode
            if cfg.statement_timeout_ms:
                connect_args["options"] = f"-c statement_timeout={cfg.statement_timeout_ms}"

            _engine = create_engine(
                cfg.url,
                pool_pre_ping=True,
                pool_size=cfg.pool_size,
                max_overflow=cfg.max_overflow,
                pool_timeout=cfg.pool_timeout,
                pool_recycle=cfg.pool_recycle,  # replace connections before an idle-suspending host drops them
                pool_use_lifo=True,  # reuse the most recent connection so idle ones can expire
                echo=False,
                # Bound parameter values (student names, file contents) stay out of exception messages and logs.
                hide_parameters=True,
                connect_args=connect_args,
            )
            if hasattr(os, "register_at_fork") and not _fork_hook_registered:
                os.register_at_fork(after_in_child=_dispose_inherited_pool)
                _fork_hook_registered = True
        return _engine


def get_session_factory() -> "sessionmaker[Session]":
    global _session_factory
    with _lock:
        if _session_factory is None:
            # `autocommit=False` was passed here before; SQLAlchemy 2.0 only accepts that value, so it is dropped.
            # autoflush is off, so pending objects are not visible to queries until `flush()` or `commit()`.
            _session_factory = sessionmaker(bind=get_engine(), autoflush=False)
            if get_config().tenant_rls:
                event.listen(_session_factory, "after_begin", _apply_tenant_to_transaction)
        return _session_factory


def dispose_engine() -> None:
    """Close the pool and forget the engine and configuration. Call on application shutdown, and in tests that
    change the environment."""
    global _config, _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _config = _engine = _session_factory = None


if TYPE_CHECKING:
    engine: Engine
    SessionLocal: sessionmaker[Session]
    DATABASE_URL: str


def __getattr__(name: str):
    # Keeps `from database import engine, SessionLocal, DATABASE_URL` working, built on first use.
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_session_factory()
    if name == "DATABASE_URL":
        # The full URL including the password, as before. Prefer `get_engine().url`, which masks it when printed.
        return get_config().url.render_as_string(hide_password=False)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Base(DeclarativeBase):
    """Base class for all database models."""


# ── Sessions ─────────────────────────────────────────────────────────────────


def get_db() -> Iterator[Session]:
    """FastAPI dependency: ``db: Session = Depends(get_db)``.

    This was annotated ``AbstractContextManager[Session]`` and documented as ``with get_db() as db:``, but it is a
    generator, and ``with get_db()`` raises ``TypeError``. For scripts and background jobs use ``session_scope()``.
    """
    db = get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session for code outside a request: commits when the block ends, rolls back if it raises.

    Usage:
        with session_scope() as db:
            db.add(...)
    """
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database() -> bool:
    """True if a trivial query succeeds. For readiness probes. The failure reason is logged by type only."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database health check failed (%s)", type(exc).__name__)
        return False


# ── Tenant context ───────────────────────────────────────────────────────────

# Request-scoped tenant. NOTE: this is only a value other code can read. It isolates nothing by itself: every query
# has to filter on it, or PostgreSQL row-level security has to enforce it (DATABASE_TENANT_RLS=true).
#
# In FastAPI, a *sync* dependency runs in a worker thread on a copy of the context, so a value set there is not
# visible to the endpoint. Set it in an `async` dependency or middleware, or use `tenant_context()` around the work.
_tenant_context: ContextVar[str | None] = ContextVar("_tenant_context", default=None)

MAX_TENANT_ID_LENGTH = 128

_SET_TENANT_SQL = text("SELECT set_config('app.tenant_id', :tid, true)")  # true = for this transaction only


def _validate_tenant_id(tenant_id: str) -> str:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id must be a non-empty string.")
    value = tenant_id.strip()
    if len(value) > MAX_TENANT_ID_LENGTH or "\x00" in value:
        raise ValueError("tenant_id is too long or contains invalid characters.")
    return value


def _apply_tenant_to_transaction(session, transaction, connection) -> None:
    """Runs at the start of every transaction when DATABASE_TENANT_RLS is on.

    With no tenant set it writes an empty id, so a policy such as
    ``tenant_id = current_setting('app.tenant_id', true)`` matches nothing: it fails closed.
    (Table owners and superusers bypass RLS unless the table uses FORCE ROW LEVEL SECURITY.)
    """
    connection.execute(_SET_TENANT_SQL, {"tid": get_tenant_context() or ""})


def set_tenant_context(db: Session, tenant_id: str) -> Token:
    """Set tenant context for the current request. Returns a token for ``reset_tenant_context``.

    This is used for multi-tenant isolation. The ``db`` argument was previously ignored; the tenant is now also
    recorded on the session (``db.info["tenant_id"]``) and, with DATABASE_TENANT_RLS, applied to the open transaction.
    """
    tenant = _validate_tenant_id(tenant_id)
    token = _tenant_context.set(tenant)
    db.info["tenant_id"] = tenant
    if get_config().tenant_rls and db.in_transaction():
        db.execute(_SET_TENANT_SQL, {"tid": tenant})
    return token


def get_tenant_context() -> str | None:
    """Get the current tenant context.

    Returns:
        The current tenant_id or None if not set.
    """
    return _tenant_context.get()


def reset_tenant_context(token: Token) -> None:
    """Restore the tenant that was current before the matching ``set_tenant_context`` call."""
    _tenant_context.reset(token)


def clear_tenant_context() -> None:
    """Clear the current tenant context."""
    _tenant_context.set(None)


@contextmanager
def tenant_context(tenant_id: str) -> Iterator[None]:
    """Run a block as a tenant, restoring the previous value afterwards even if it raises."""
    token = _tenant_context.set(_validate_tenant_id(tenant_id))
    try:
        yield
    finally:
        _tenant_context.reset(token)


# ── Schema management ────────────────────────────────────────────────────────


_MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _import_model_modules(modules: Iterable[str]) -> None:
    for name in modules:
        if not _MODULE_NAME.match(name):
            raise RuntimeError(f"{name!r} is not a valid module name.")
        importlib.import_module(name)  # importing is what registers a model's tables on Base.metadata


def init_db(model_modules: Iterable[str] = ()) -> None:
    """Create any missing tables from the ORM models.

    ``Base.metadata`` only knows the models whose modules have been imported, and nothing in this module imports them.
    Pass the module(s) here (``init_db(["src.backend.models.database"])``), or set ``DATABASE_MODEL_MODULES``, or import
    them before calling. With none registered this used to create nothing and report success, which is how a database
    could look initialised with no tables in it. Now it stops with an error.

    For local development and tests. Production schema changes belong in migrations: ``create_all`` never alters an
    existing table, so it hides drift between the models and the database.
    """
    extra = [m.strip() for m in os.environ.get("DATABASE_MODEL_MODULES", "").split(",") if m.strip()]
    _import_model_modules([*model_modules, *extra])
    if not Base.metadata.tables:
        raise RuntimeError(
            "No ORM models are registered on Base, so init_db() would create nothing. Import the model module "
            "first, pass it as init_db([\"your.models.module\"]), or set DATABASE_MODEL_MODULES."
        )
    Base.metadata.create_all(bind=get_engine())


def drop_db(*, confirm: bool = False) -> None:
    """Drop all tables from the database. Destructive: refuses unless explicitly allowed twice.

    Needs ``confirm=True`` and ``DATABASE_ALLOW_DROP=true``. This backend only runs against a remote PostgreSQL
    database, so an unguarded ``drop_all`` in a test run could erase real data.
    """
    if not confirm:
        raise RuntimeError("drop_db() deletes every table. Call drop_db(confirm=True) if that is what you want.")
    if not _flag("DATABASE_ALLOW_DROP"):
        raise RuntimeError("drop_db() is disabled. Set DATABASE_ALLOW_DROP=true in a throwaway environment to allow it.")
    cfg = get_config()
    logger.warning("Dropping all tables on database host %r", cfg.url.host or "local socket")
    Base.metadata.drop_all(bind=get_engine())
