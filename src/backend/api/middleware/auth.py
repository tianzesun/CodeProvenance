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
import hmac
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API keys and their permissions."""
    
    def __init__(self) -> None:
        """Initialize the API key manager."""
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._rate_limits: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "requests": 0,
            "window_start": time.time(),
        })
    
    def create_key(
        self,
        name: str,
        tenant_id: str,
        rate_limit: int = 100,
        rate_window: int = 3600,
        permissions: Optional[list] = None,
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
    
    def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
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
            retry_after = int(
                rate_data["window_start"] + rate_window - current_time
            )
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
            logger.info(f"Revoked API key")
            return True
        return False
    
    def list_keys(self, tenant_id: Optional[str] = None) -> list:
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
            keys.append({
                "key_prefix": key[:12] + "...",
                "name": data["name"],
                "tenant_id": data["tenant_id"],
                "created_at": data["created_at"],
                "last_used": data["last_used"],
                "total_requests": data["total_requests"],
                "rate_limit": data["rate_limit"],
            })
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
        excluded_paths: Optional[list] = None,
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
        ]
        self.exclude_paths = self.excluded_paths
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Any:
        """Process authentication for each request."""
        path = request.url.path
        
        # Skip authentication for excluded paths
        if any(
            path == excluded or (excluded != "/" and path.startswith(excluded))
            for excluded in self.excluded_paths
        ):
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


# Create some default API keys for development
def setup_default_keys() -> None:
    """Create default API keys for development/testing."""
    # Development key (unlimited)
    api_key_manager.create_key(
        name="Development Key",
        tenant_id="dev",
        rate_limit=1000,
        rate_window=60,
        permissions=["analyze", "report", "compare", "admin"],
    )
    
    # Demo key (limited)
    api_key_manager.create_key(
        name="Demo Key",
        tenant_id="demo",
        rate_limit=10,
        rate_window=60,
        permissions=["analyze", "report", "compare"],
    )
    
    logger.info("Default API keys created for development")
