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

import hashlib
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.backend.config.settings import settings

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API keys and their permissions."""

    def __init__(self) -> None:
        """Initialize the API key manager."""
        self._keys: dict[str, dict[str, Any]] = {}
        self._rate_limits: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "requests": 0,
                "window_start": time.time(),
            }
        )

    def create_key(
        self,
        name: str,
        tenant_id: str,
        rate_limit: int = 100,
        rate_window: int = 3600,
        permissions: list | None = None,
    ) -> str:
        """Create a new API key.

        Args:
            name: Human-readable name for the key
            tenant_id: Tenant identifier for isolation
            rate_limit: Number of requests allowed per window
            rate_window: Time window in seconds
            permissions: List of allowed permissions

        Returns:
            The generated API key
        """
        # Generate a secure random key
        key_bytes = hashlib.sha256(
            f"{uuid.uuid4()}{time.time()}{name}".encode()
        ).hexdigest()
        api_key = f"sk_live_{key_bytes[:32]}"

        self._keys[api_key] = {
            "name": name,
            "tenant_id": tenant_id,
            "rate_limit": rate_limit,
            "rate_window": rate_window,
            "permissions": permissions or ["analyze", "report", "compare"],
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "total_requests": 0,
        }

        logger.info(f"Created API key '{name}' for tenant '{tenant_id}'")
        return api_key

    def validate_key(self, api_key: str) -> dict[str, Any] | None:
        """Validate an API key.

        Args:
            api_key: The API key to validate

        Returns:
            Key metadata if valid, None otherwise
        """
        key_data = self._keys.get(api_key)
        if key_data:
            key_data["last_used"] = datetime.now().isoformat()
            return key_data
        return None

    def check_rate_limit(self, api_key: str) -> tuple[bool, int]:
        """Check if a request is within rate limits.

        Args:
            api_key: The API key making the request

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        key_data = self._keys.get(api_key)
        if not key_data:
            return False, 0

        rate_limit = key_data["rate_limit"]
        rate_window = key_data["rate_window"]

        current_time = time.time()
        rate_data = self._rate_limits[api_key]

        # Reset window if expired
        if current_time - rate_data["window_start"] > rate_window:
            rate_data["requests"] = 0
            rate_data["window_start"] = current_time

        # Check limit
        if rate_data["requests"] >= rate_limit:
            retry_after = int(rate_data["window_start"] + rate_window - current_time)
            return False, max(1, retry_after)

        # Increment counter
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
        key_data = self._keys.get(api_key)
        if not key_data:
            return 0

        rate_data = self._rate_limits[api_key]
        return max(0, key_data["rate_limit"] - rate_data["requests"])

    def revoke_key(self, api_key: str) -> bool:
        """Revoke an API key.

        Args:
            api_key: The API key to revoke

        Returns:
            True if key was revoked, False if not found
        """
        if api_key in self._keys:
            del self._keys[api_key]
            if api_key in self._rate_limits:
                del self._rate_limits[api_key]
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
        keys = []
        for key, data in self._keys.items():
            if tenant_id and data["tenant_id"] != tenant_id:
                continue
            keys.append(
                {
                    "key_prefix": key[:12] + "...",
                    "name": data["name"],
                    "tenant_id": data["tenant_id"],
                    "created_at": data["created_at"],
                    "last_used": data["last_used"],
                    "total_requests": data["total_requests"],
                    "rate_limit": data["rate_limit"],
                }
            )
        return keys


# Global API key manager instance
api_key_manager = APIKeyManager()

# FastAPI security scheme
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication and rate limiting middleware."""

    def __init__(
        self,
        app: Any,
        excluded_paths: list | None = None,
    ) -> None:
        """Initialize auth middleware.

        Args:
            app: The ASGI application
            excluded_paths: Paths that don't require authentication
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/v1/health",
            "/api/v1/auth",
        ]
        self.exclude_paths = self.excluded_paths

    def _has_valid_session_cookie(self, request: Request) -> bool:
        """Return True if the request carries a valid dashboard session cookie.

        The cookie is a JWT signed with AUTH_JWT_SECRET, the same token issued by
        ``_issue_auth_cookie`` in ``src.backend.api.server``. Only requests with a
        cryptographically valid, unexpired token bypass the API key requirement.
        """
        from src.backend.api.server import AUTH_COOKIE_NAME

        if not settings.AUTH_JWT_SECRET:
            return False

        token = request.cookies.get(AUTH_COOKIE_NAME)
        if not token:
            return False

        try:
            payload = jwt.decode(token, settings.AUTH_JWT_SECRET, algorithms=["HS256"])
        except JWTError:
            return False

        return bool(payload.get("sub"))

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """Process authentication for each request."""
        from src.backend.api.server import AUTH_EXEMPT_PREFIXES

        path = request.url.path

        # Skip authentication for excluded paths
        if any(
            path == excluded or (excluded != "/" and path.startswith(excluded))
            for excluded in self.excluded_paths
        ):
            return await call_next(request)

        # Skip authentication for exempt prefixes (API-key bypass paths)
        if path.startswith(AUTH_EXEMPT_PREFIXES):
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
                headers={"Retry-After": str(retry_after)},
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
            int(time.time() + key_data["rate_window"])
        )

        return response


def require_permission(permission: str) -> Callable:
    """Decorator to require specific permissions."""

    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            permissions = getattr(request.state, "permissions", [])
            if permission not in permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required",
                )
            return await func(request, *args, **kwargs)

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


def setup_default_keys() -> None:
    """Create default API keys for development/testing.

    Only creates keys when DEBUG_MODE is enabled. Never creates
    hardcoded keys that could be used in production.
    """
    from src.backend.config.settings import settings

    if not settings.DEBUG_MODE:
        logger.info("Skipping default API key creation (DEBUG_MODE is off)")
        return

    api_key_manager.create_key(
        name="Development Key",
        tenant_id="dev",
        rate_limit=1000,
        rate_window=60,
        permissions=["analyze", "report", "compare", "admin"],
    )

    api_key_manager.create_key(
        name="Demo Key",
        tenant_id="demo",
        rate_limit=10,
        rate_window=60,
        permissions=["analyze", "report", "compare"],
    )

    logger.warning(
        "Default API keys created for development only. "
        "These keys should NOT be used in production."
    )
