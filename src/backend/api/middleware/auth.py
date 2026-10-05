"""API Authentication Middleware.

Provides API key authentication and rate limiting for the REST API.

Features:
- API key validation
- Per-key rate limiting
- Tenant isolation
- Request logging

Usage:
    from fastapi import FastAPI
    from src.backend.api.middleware.auth import AuthMiddleware

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
"""

import functools
import hashlib
import inspect
import logging
import os
import secrets
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.backend.config.settings import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "sk_live_"
_MIN_CUSTOM_KEY_CHARS = 32
_MAX_SESSION_TOKEN_CHARS = 8192


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(api_key: str) -> str:
    """SHA-256 digest used as the lookup key.

    API keys are 128 random bits, so a plain digest is appropriate (unlike a
    password). Only digests are held in memory, so a heap dump or an accidental
    ``repr`` of the manager no longer exposes usable keys.
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


class APIKeyManager:
    """Manages API keys and their permissions.

    Thread-safe: handlers that run in worker threads may create or revoke keys
    while the middleware is validating requests.
    """

    def __init__(self) -> None:
        """Initialize the API key manager."""
        # Both maps are keyed by the key's SHA-256 digest, never the raw key.
        self._keys: dict[str, dict[str, Any]] = {}
        self._rate_limits: dict[str, dict[str, float]] = {}
        self._lock = threading.RLock()

    def create_key(
        self,
        name: str,
        tenant_id: str,
        rate_limit: int = 100,
        rate_window: int = 3600,
        permissions: list | None = None,
        api_key: str | None = None,
    ) -> str:
        """Create a new API key.

        Args:
            name: Human-readable name for the key
            tenant_id: Tenant identifier for isolation
            rate_limit: Number of requests allowed per window
            rate_window: Time window in seconds
            permissions: List of allowed permissions
            api_key: Register this exact key instead of generating one (used for a
                known development key); must be at least 32 characters.

        Returns:
            The API key. It is shown once; only a digest is retained.
        """
        if rate_limit < 1 or rate_window < 1:
            raise ValueError("rate_limit and rate_window must be positive")
        if api_key is None:
            # 128 bits from the OS CSPRNG. It used to be a hash of
            # uuid4 + wall-clock time + name.
            api_key = f"{_KEY_PREFIX}{secrets.token_hex(16)}"
        elif len(api_key) < _MIN_CUSTOM_KEY_CHARS:
            raise ValueError(
                f"api_key must be at least {_MIN_CUSTOM_KEY_CHARS} characters"
            )

        with self._lock:
            self._keys[_digest(api_key)] = {
                "name": name,
                "tenant_id": tenant_id,
                "rate_limit": rate_limit,
                "rate_window": rate_window,
                "permissions": list(permissions or ["analyze", "report", "compare"]),
                "key_prefix": api_key[:12] + "...",
                "created_at": _now_iso(),
                "last_used": None,
                "total_requests": 0,
            }

        # %r: a name containing newlines cannot forge log lines.
        logger.info("Created API key %r for tenant %r", name, tenant_id)
        return api_key

    def validate_key(self, api_key: str) -> dict[str, Any] | None:
        """Validate an API key.

        Args:
            api_key: The API key to validate

        Returns:
            Key metadata if valid, None otherwise
        """
        digest = _digest(api_key)
        with self._lock:
            key_data = self._keys.get(digest)
            if key_data:
                key_data["last_used"] = _now_iso()
                return key_data
        return None

    def check_rate_limit(self, api_key: str) -> tuple[bool, int]:
        """Check if a request is within rate limits (and count it if so).

        Args:
            api_key: The API key making the request

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        digest = _digest(api_key)
        with self._lock:
            key_data = self._keys.get(digest)
            if not key_data:
                return False, 0

            rate_limit = key_data["rate_limit"]
            rate_window = key_data["rate_window"]

            # Monotonic: the wall clock can jump (NTP, DST) and stretch or
            # collapse a window.
            current_time = time.monotonic()
            rate_data = self._rate_limits.setdefault(
                digest, {"requests": 0, "window_start": current_time}
            )

            # Reset window if expired
            if current_time - rate_data["window_start"] > rate_window:
                rate_data["requests"] = 0
                rate_data["window_start"] = current_time

            # Check limit
            if rate_data["requests"] >= rate_limit:
                retry_after = int(
                    rate_data["window_start"] + rate_window - current_time
                )
                return False, max(1, retry_after)

            rate_data["requests"] += 1
            key_data["total_requests"] += 1
            return True, 0

    def get_remaining_requests(self, api_key: str) -> int:
        """Get remaining requests in current window.

        Args:
            api_key: The API key

        Returns:
            Number of remaining requests
        """
        digest = _digest(api_key)
        with self._lock:
            key_data = self._keys.get(digest)
            if not key_data:
                return 0
            rate_data = self._rate_limits.get(digest)
            used = rate_data["requests"] if rate_data else 0
            return max(0, key_data["rate_limit"] - used)

    def seconds_until_reset(self, api_key: str) -> int:
        """Seconds until the current rate-limit window ends.

        ``X-RateLimit-Reset`` used to be ``now + rate_window`` on every response,
        i.e. always a full window away, even a second before the real reset.
        """
        digest = _digest(api_key)
        with self._lock:
            key_data = self._keys.get(digest)
            rate_data = self._rate_limits.get(digest)
            if not key_data:
                return 0
            if not rate_data:
                return int(key_data["rate_window"])
            remaining = (
                rate_data["window_start"] + key_data["rate_window"] - time.monotonic()
            )
            return max(0, int(remaining + 0.999))

    def revoke_key(self, api_key: str) -> bool:
        """Revoke an API key.

        Args:
            api_key: The API key to revoke

        Returns:
            True if key was revoked, False if not found
        """
        digest = _digest(api_key)
        with self._lock:
            if digest in self._keys:
                del self._keys[digest]
                self._rate_limits.pop(digest, None)
                logger.info("Revoked API key")
                return True
        return False

    def list_keys(self, tenant_id: str | None = None) -> list:
        """List API keys (optionally filtered by tenant).

        Args:
            tenant_id: Optional tenant ID to filter by

        Returns:
            List of key metadata (without the actual keys)
        """
        with self._lock:
            return [
                {
                    "key_prefix": data["key_prefix"],
                    "name": data["name"],
                    "tenant_id": data["tenant_id"],
                    "created_at": data["created_at"],
                    "last_used": data["last_used"],
                    "total_requests": data["total_requests"],
                    "rate_limit": data["rate_limit"],
                }
                for data in self._keys.values()
                if not tenant_id or data["tenant_id"] == tenant_id
            ]


# Global API key manager instance
api_key_manager = APIKeyManager()

# FastAPI security scheme
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _normalize_path(path: str) -> str:
    """``/health/`` -> ``/health`` (the root stays ``/``)."""
    return path.rstrip("/") or "/"


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication and rate limiting middleware."""

    def __init__(
        self,
        app: Any,
        excluded_paths: list | None = None,
        excluded_prefixes: Iterable[str] = (),
    ) -> None:
        """Initialize auth middleware.

        Args:
            app: The ASGI application
            excluded_paths: Exact paths that don't require authentication
            excluded_prefixes: Path prefixes that don't require authentication.
                Matched on a segment boundary (``/a`` covers ``/a/b`` but not
                ``/ab``). Empty by default, so the public surface only grows
                when you ask for it.
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/",
            "/health",
            "/api/v1/health",
            "/api/v1/auth",
        ]
        self.exclude_paths = self.excluded_paths
        self.excluded_prefixes = tuple(_normalize_path(p) for p in excluded_prefixes)

    def _is_public(self, path: str) -> bool:
        """Exact-match public paths, tolerating a trailing slash.

        Matching stays exact on purpose (a permissive value such as /api/upload
        must not turn /api/upload-admin public), but ``/health/`` used to be
        rejected while ``/health`` was allowed.
        """
        normalized = _normalize_path(path)
        if path in self.excluded_paths or normalized in self.excluded_paths:
            return True
        return any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in self.excluded_prefixes
        )

    def _has_valid_session_cookie(self, request: Request) -> bool:
        """Return True if the request carries a valid dashboard session cookie.

        The cookie is a JWT signed with AUTH_JWT_SECRET, the same token issued by
        ``_issue_auth_cookie`` in ``src.backend.api.server``. Only requests with a
        cryptographically valid, unexpired token bypass the API key requirement.
        """
        from src.backend.api.server import AUTH_COOKIE_NAME

        # The guard read ``settings.AUTH_JWT_SECRET`` but the decode read
        # ``settings.auth_jwt_secret``; if only one spelling exists the decode
        # raised AttributeError, which is not a JWTError and surfaced as a 500
        # on every cookie-authenticated request.
        #
        # Order matters. ``AUTH_JWT_SECRET`` is a ``SecretStr`` and is truthy, so
        # probing it first makes the ``or`` short-circuit and hand jose the
        # wrapper rather than a key -> ``JWKError: Expecting a string- or
        # bytes-formatted key`` -> 500 on every request. ``auth_jwt_secret`` is
        # the plain-string accessor that settings documents as the only
        # supported form for jose.
        secret = getattr(settings, "auth_jwt_secret", None)
        if secret is None:
            # Only the raw attribute exists; unwrap rather than pass the wrapper.
            secret = getattr(settings, "AUTH_JWT_SECRET", None)
            if hasattr(secret, "get_secret_value"):
                secret = secret.get_secret_value()
        if not secret or not isinstance(secret, (str, bytes)):
            return False

        token = request.cookies.get(AUTH_COOKIE_NAME)
        if not token or len(token) > _MAX_SESSION_TOKEN_CHARS:
            return False

        try:
            # Require ``exp``: python-jose only checks it when present, so a
            # token minted without one would never expire.
            payload = jwt.decode(
                token, secret, algorithms=["HS256"], options={"require_exp": True}
            )
        except JWTError:
            return False

        return isinstance(payload, dict) and bool(payload.get("sub"))

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """Process authentication for each request."""
        path = request.url.path

        if self._is_public(path):
            return await call_next(request)

        # CORS preflights never carry credentials; rejecting them here breaks
        # every cross-origin browser call before the CORS layer can answer.
        if (
            request.method == "OPTIONS"
            and "access-control-request-method" in request.headers
        ):
            return await call_next(request)

        # Dashboard sessions (HttpOnly cookie JWT) take precedence over API keys.
        # The dashboard uses cookie-based auth (see dashboard_auth_middleware), so a
        # request with a valid session cookie must not be rejected for missing an
        # API key header. API keys remain required for programmatic access.
        if self._has_valid_session_cookie(request):
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Authentication required",
                    "message": "Please provide an API key in the X-API-Key header",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Validate API key
        key_data = api_key_manager.validate_key(api_key)
        if not key_data:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid API key",
                    "message": "The provided API key is not valid",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Check rate limit
        allowed, retry_after = api_key_manager.check_rate_limit(api_key)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"You have exceeded your rate limit of {key_data['rate_limit']} requests per {key_data['rate_window']} seconds",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(key_data["rate_limit"]),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Add key data to request state
        request.state.api_key = api_key
        request.state.tenant_id = key_data["tenant_id"]
        request.state.permissions = key_data["permissions"]
        request.state.rate_limit = key_data["rate_limit"]
        request.state.rate_remaining = api_key_manager.get_remaining_requests(api_key)

        # Execute request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(key_data["rate_limit"])
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time() + api_key_manager.seconds_until_reset(api_key))
        )

        return response


def _find_request(args: tuple, kwargs: dict) -> Request | None:
    """Locate the Request among a handler's arguments, whatever it is named."""
    for value in (*args, *kwargs.values()):
        if isinstance(value, Request):
            return value
    return None


def require_permission(permission: str) -> Callable:
    """Decorator to require specific API-key permissions.

    Works on ``async`` and plain ``def`` handlers, and the handler's own
    signature is preserved. The old wrapper hid it behind ``(request, *args,
    **kwargs)``, so FastAPI saw ``args``/``kwargs`` as required query
    parameters and lost every real path/body parameter; it also awaited sync
    handlers and assumed the Request parameter was named ``request``.

    Requests authenticated by a dashboard session cookie carry no API-key
    permissions, so they are refused here; use :func:`require_user_permission`
    for role-based checks.
    """

    def decorator(func: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = _find_request(args, kwargs)
            if request is None:
                raise RuntimeError(
                    f"{func.__name__} uses require_permission but declares no Request parameter"
                )
            permissions = getattr(request.state, "permissions", [])
            if permission not in permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required",
                )
            if is_async:
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_current_tenant(request: Request) -> str:
    """Get the current tenant ID from request."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return tenant_id


#: Dashboard roles the console supports. The ``api`` principal built from an API
#: key is intentionally absent: it is a machine identity with no dashboard role.
DASHBOARD_ROLES: tuple[str, ...] = ("admin", "professor")

#: Permission granted to each dashboard role — the single source of truth for
#: RBAC, so a route guard and a UI affordance can never disagree about who may
#: do what.
#:
#: The split mirrors the product's division of labour:
#:
#: * ``admin`` owns the academic *registry* — creating users, terms and courses,
#:   binding a course to a term, and assigning users to courses. Admins
#:   deliberately hold no ``assignment:manage`` right: an assignment is a
#:   teaching artefact owned by the professor who teaches the course.
#: * ``professor`` owns the *teaching* workflow — running checks and managing
#:   the assignments of the courses they are assigned to. Professors hold no
#:   registry rights, so they cannot create or edit courses, terms or users.
#:
#: ``course:read:all`` / ``course:read:assigned`` are read scopes rather than
#: booleans: the assignment-aware details (which courses a professor may touch)
#: are resolved against ``course_instructors`` in
#: ``src.backend.application.services.academic_access``.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset(
        {
            "user:manage",
            "term:manage",
            "course:manage",
            "roster:manage",
            "course:read:all",
        }
    ),
    "professor": frozenset({"assignment:manage", "course:read:assigned"}),
}


def permissions_for_role(role: str | None) -> frozenset[str]:
    """Return the permission set granted to ``role``.

    Unknown and missing roles (including the ``api`` machine principal) get an
    empty set so every permission check fails closed rather than opening up.
    """
    if not role:
        return frozenset()
    return ROLE_PERMISSIONS.get(str(role).strip().lower(), frozenset())


def has_permission(user: dict | None, permission: str) -> bool:
    """Return True when the dashboard ``user`` dict holds ``permission``."""
    if not isinstance(user, dict):
        return False
    return permission in permissions_for_role(user.get("role"))


def dashboard_user(request: Request) -> dict:
    """Return the dashboard user attached by the middleware, else raise 401.

    Public so route modules can build their own role + row-level guards (see
    ``src.backend.api.routes.academic``) on top of the same authentication
    resolution used by :func:`require_roles`.
    """
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def _require_role(request: Request, allowed: tuple[str, ...]) -> dict:
    """Return the dashboard user when its role is in ``allowed``.

    Raises:
        HTTPException: 401 when unauthenticated, 403 when the role is not allowed.
    """
    user = dashboard_user(request)
    role = str(user.get("role") or "").strip().lower()
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{' or '.join(allowed).title()} role required",
        )
    return user


def require_roles(*roles: str) -> Callable:
    """Build a FastAPI dependency accepting only the listed dashboard roles.

    Args:
        *roles: Role names allowed to reach the endpoint, e.g. ``"admin"``.

    Returns:
        A dependency returning the caller's user dict, or raising 401 / 403.

    Raises:
        ValueError: When called without any role, which would deny everything.
    """
    allowed = tuple(str(role).strip().lower() for role in roles)
    if not allowed:
        raise ValueError("require_roles() needs at least one role")

    def dependency(request: Request) -> dict:
        """Return the authenticated caller when their role is allowed."""
        return _require_role(request, allowed)

    # A descriptive name keeps FastAPI diagnostics (and route-wiring tests that
    # assert which guard protects a path) readable instead of "dependency".
    dependency.__name__ = f"require_roles_{'_'.join(allowed)}"
    return dependency


def require_user_permission(permission: str) -> Callable:
    """Build a FastAPI dependency requiring a *role* permission.

    Unlike :func:`require_permission` (which checks the ``permissions`` list of
    an API key), this resolves the dashboard user's role to the
    :data:`ROLE_PERMISSIONS` matrix, so guards stay declarative and one matrix
    edit moves every route at once.

    Args:
        permission: Permission name, e.g. ``"course:manage"``.

    Returns:
        A dependency returning the caller's user dict, or raising 401 / 403.
    """

    def dependency(request: Request) -> dict:
        """Return the authenticated caller when their role holds the permission."""
        user = dashboard_user(request)
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user

    # Named after the permission so a route's guard is identifiable from the
    # FastAPI dependency graph (see the RBAC route-wiring test).
    dependency.__name__ = f"require_user_permission_{permission.replace(':', '_')}"
    return dependency


def require_admin(request: Request) -> dict:
    """FastAPI dependency requiring an authenticated admin user.

    Resolves the dashboard user attached to the request by the auth middleware
    and rejects non-admin callers. Keeps academic registry CRUD reachable for
    admins while professors continue to use the course-scoped endpoints.
    """
    return _require_role(request, ("admin",))


def setup_default_keys() -> dict[str, str]:
    """Create default API keys for development/testing.

    Only creates keys when ALLOW_DEV_API_KEYS and DEBUG_MODE are both enabled.
    Never creates hardcoded keys that could be used in production.

    Returns:
        ``{key name: key}`` for the keys created (empty when skipped). The keys
        are random and only a digest is stored, so they used to be unrecoverable
        the moment this function returned; the caller must surface them. Set
        DEV_API_KEY (>= 32 characters) to use a fixed development key instead.
    """
    if not settings.ALLOW_DEV_API_KEYS:
        logger.info("Skipping default API key creation (ALLOW_DEV_API_KEYS is off)")
        return {}

    if not settings.DEBUG_MODE:
        logger.info("Skipping default API key creation (DEBUG_MODE is off)")
        return {}

    created = {
        "Development Key": api_key_manager.create_key(
            name="Development Key",
            tenant_id="dev",
            rate_limit=1000,
            rate_window=60,
            permissions=["analyze", "report", "compare", "admin"],
            api_key=os.getenv("DEV_API_KEY") or None,
        ),
        "Demo Key": api_key_manager.create_key(
            name="Demo Key",
            tenant_id="demo",
            rate_limit=10,
            rate_window=60,
            permissions=["analyze", "report", "compare"],
        ),
    }

    logger.warning(
        "Default API keys created for development only. "
        "These keys should NOT be used in production."
    )
    return created
