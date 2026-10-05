"""
Rate limiting middleware for API requests.

Provides configurable rate limiting per tenant to prevent abuse
and ensure fair resource usage.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, status
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: (window name, seconds). Each name maps to a ``requests_per_<name>`` attribute.
_WINDOWS: tuple[tuple[str, int], ...] = (("minute", 60), ("hour", 3600), ("day", 86400))
_EVICT_EVERY = 1024  # sweep idle tenants once per this many checks


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of one rate-limit check (no exception needed to read it)."""

    allowed: bool
    retry_after: int = 0
    exceeded: str | None = None  # "minute" | "hour" | "day" when not allowed
    usage: dict[str, dict[str, int]] = field(default_factory=dict)


class RateLimiter:
    """
    Sliding-window rate limiter for API requests.

    Tracks requests per tenant and enforces limits:
    - Requests per minute
    - Requests per hour
    - Requests per day

    Each tenant keeps one deque of timestamps per window. Expired entries are
    dropped from the left, so a check is O(1) amortised. It used to rebuild and
    re-scan one list of up to ``requests_per_day`` timestamps several times per
    request while holding the global lock. Rejected requests are not recorded,
    so each deque is bounded by its limit.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per tenant
            requests_per_hour: Maximum requests per hour per tenant
            requests_per_day: Maximum requests per day per tenant
            clock: Monotonic time source (injectable for tests). The wall clock
                is not used because NTP/DST jumps would stretch or collapse windows.
        """
        for name, value in (
            ("requests_per_minute", requests_per_minute),
            ("requests_per_hour", requests_per_hour),
            ("requests_per_day", requests_per_day),
        ):
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day

        self._clock = clock
        # tenant_id -> window name -> timestamps (oldest first)
        self._tenants: dict[str, dict[str, deque[float]]] = {}
        self._checks = 0
        self.lock = threading.Lock()

    # -- internals (call with the lock held) -------------------------------

    def _limit(self, name: str) -> int:
        return getattr(self, f"requests_per_{name}")

    def _prune(self, queues: dict[str, deque[float]], now: float) -> None:
        for name, seconds in _WINDOWS:
            queue = queues[name]
            cutoff = now - seconds
            while queue and queue[0] <= cutoff:
                queue.popleft()

    def _usage(self, queues: dict[str, deque[float]] | None) -> dict[str, dict[str, int]]:
        usage = {}
        for name, _seconds in _WINDOWS:
            used = len(queues[name]) if queues else 0
            limit = self._limit(name)
            usage[name] = {"used": used, "remaining": max(0, limit - used), "limit": limit}
        return usage

    def _evict_idle(self, now: float) -> None:
        """Forget tenants with no requests left in the last day.

        Entries were created for every tenant id ever seen (and even by read-only
        calls) and never removed, so memory grew without bound.
        """
        for tenant_id in list(self._tenants):
            queues = self._tenants[tenant_id]
            self._prune(queues, now)
            if not queues["day"]:
                del self._tenants[tenant_id]

    # -- public API -------------------------------------------------------

    def check(self, tenant_id: str) -> RateLimitDecision:
        """Count a request for ``tenant_id`` and report whether it is allowed."""
        with self.lock:
            now = self._clock()
            queues = self._tenants.get(tenant_id)
            if queues is None:
                queues = {name: deque() for name, _ in _WINDOWS}
                self._tenants[tenant_id] = queues
            self._prune(queues, now)

            for name, seconds in _WINDOWS:
                queue = queues[name]
                limit = self._limit(name)
                if len(queue) >= limit:
                    # Retry once the entry whose expiry frees a slot ages out,
                    # not a fixed 60/3600/86400 as before.
                    expires_at = queue[len(queue) - limit] + seconds
                    retry_after = max(1, math.ceil(expires_at - now))
                    return RateLimitDecision(False, retry_after, name, self._usage(queues))

            for queue in queues.values():
                queue.append(now)

            self._checks += 1
            if self._checks % _EVICT_EVERY == 0:
                self._evict_idle(now)
            return RateLimitDecision(True, 0, None, self._usage(queues))

    def check_rate_limit(self, tenant_id: str, request: Request | None = None) -> None:
        """
        Check if request exceeds rate limit for tenant.

        Args:
            tenant_id: Tenant identifier
            request: FastAPI request object (unused; kept for compatibility)

        Raises:
            HTTPException: If rate limit exceeded (429)
        """
        decision = self.check(tenant_id)
        if decision.allowed:
            return
        limit = self._limit(decision.exceeded)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Limit: {limit}/{decision.exceeded}",
                "retry_after": decision.retry_after,
            },
            headers={"Retry-After": str(decision.retry_after)},
        )

    def get_remaining(self, tenant_id: str) -> dict[str, Any]:
        """
        Get remaining requests for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dict with remaining request counts
        """
        with self.lock:
            queues = self._tenants.get(tenant_id)
            if queues is not None:  # read-only: never creates an entry
                self._prune(queues, self._clock())
            return self._usage(queues)

    def reset(self, tenant_id: str):
        """Reset rate limit for a tenant."""
        with self.lock:
            self._tenants.pop(tenant_id, None)


# Singleton instance
rate_limiter = RateLimiter()


class RateLimitMiddleware:
    """
    ASGI middleware for rate limiting.

    The previous class had the signature ``__call__(request, call_next)``, which
    is not an ASGI app, so ``app.add_middleware(RateLimitMiddleware)`` failed on
    the first request; and it *raised* HTTPException, which middleware outside
    the router cannot turn into a response (a 500). It now answers 429 itself.

    Add it BEFORE the auth middleware so it runs inside it and can see the
    tenant that middleware resolves. Requests with no tenant are limited per
    client address, not all pooled into one shared ``"default"`` bucket where a
    single noisy client exhausted the limit for everyone.
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_url: str | None = None,
        limiter: RateLimiter | None = None,
        exempt_paths: Iterable[str] = ("/health", "/api/v1/health"),
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: ASGI application
            redis_url: Accepted for compatibility. Distributed (Redis) limiting is
                NOT implemented: counts are per process.
            limiter: Limiter to use (defaults to the module singleton)
            exempt_paths: Path prefixes (segment boundary) that are never limited,
                so orchestrator health probes cannot be throttled.
        """
        self.app = app
        self.redis_url = redis_url
        self.limiter = limiter or rate_limiter
        self.exempt_paths = tuple(p.rstrip("/") or "/" for p in exempt_paths)

    def _is_exempt(self, path: str) -> bool:
        normalized = path.rstrip("/") or "/"
        return any(
            normalized == p or normalized.startswith(p + "/") for p in self.exempt_paths
        )

    @staticmethod
    def _identity(scope: Scope) -> str:
        tenant_id = (scope.get("state") or {}).get("tenant_id")
        if tenant_id:
            return str(tenant_id)
        client = scope.get("client")
        return f"ip:{client[0]}" if client else "ip:unknown"

    @staticmethod
    def _headers(decision: RateLimitDecision) -> dict[str, str]:
        usage = decision.usage
        return {
            "X-RateLimit-Limit-Minute": str(usage["minute"]["limit"]),
            "X-RateLimit-Remaining-Minute": str(usage["minute"]["remaining"]),
            "X-RateLimit-Limit-Hour": str(usage["hour"]["limit"]),
            "X-RateLimit-Remaining-Hour": str(usage["hour"]["remaining"]),
            "X-RateLimit-Limit-Day": str(usage["day"]["limit"]),
            "X-RateLimit-Remaining-Day": str(usage["day"]["remaining"]),
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._is_exempt(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        decision = self.limiter.check(self._identity(scope))
        headers = self._headers(decision)

        if not decision.allowed:
            limit = decision.usage[decision.exceeded]["limit"]
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {limit}/{decision.exceeded}",
                    "retry_after": decision.retry_after,
                },
                headers={**headers, "Retry-After": str(decision.retry_after)},
            )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                for name, value in headers.items():
                    response_headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
