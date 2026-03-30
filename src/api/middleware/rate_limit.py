"""
Rate limiting middleware for CodeProvenance API.
Implements token bucket algorithm with Redis backend.
"""
import time
import json
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from src.config.database import SessionLocal
from src.models.database import Tenant
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits based on tenant tier.
    Uses Redis for distributed rate limiting with token bucket algorithm.
    """
    
    def __init__(
        self, 
        app, 
        redis_url: str = "redis://localhost:6379",
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.redis_url = redis_url
        self.exclude_paths = exclude_paths or [
            "/", "/docs", "/redoc", "/openapi.json", "/health"
        ]
        self.redis_client: Optional[redis.Redis] = None
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url)
        return self.redis_client
    
    async def _get_tenant_rate_limit(self, tenant_id) -> int:
        """
        Get rate limit (requests per minute) for tenant from database.
        Falls back to default if tenant not found.
        """
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant and tenant.rate_limit_per_minute:
                return tenant.rate_limit_per_minute
            # Default rate limits by tier
            tier_limits = {
                'free': 10,
                'basic': 100,
                'pro': 1000,
                'enterprise': 10000
            }
            return tier_limits.get(tenant.tier if tenant else 'free', 10)
        finally:
            db.close()
    
    async def _is_allowed(
        self, 
        redis_client: redis.Redis, 
        key: str, 
        limit: int, 
        window: int = 60
    ) -> Tuple[bool, dict]:
        """
        Check if request is allowed using token bucket algorithm.
        
        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        now = time.time()
        pipeline = redis_client.pipeline()
        
        # Get current bucket state
        pipeline.get(f"{key}:tokens")
        pipeline.get(f"{key}:timestamp")
        tokens, last_timestamp = await pipeline.execute()
        
        # Initialize if first request
        if tokens is None or last_timestamp is None:
            tokens = float(limit)
            last_timestamp = now
        
        # Calculate elapsed time and refill tokens
        elapsed = now - float(last_timestamp)
        tokens = min(limit, tokens + (elapsed * (limit / window)))
        
        # Check if request can be served
        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False
        
        # Save updated state
        pipeline = redis_client.pipeline()
        pipeline.setex(f"{key}:tokens", window, str(tokens))
        pipeline.setex(f"{key}:timestamp", window, str(now))
        await pipeline.execute()
        
        # Calculate reset time
        reset_time = int(now + ((limit - tokens) * (window / limit)))
        
        info = {
            "limit": limit,
            "remaining": int(tokens),
            "reset": reset_time,
            "window": window
        }
        
        return allowed, info
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Skip rate limiting for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Get tenant ID from request state (set by auth middleware)
        tenant_id = getattr(request.state, 'tenant_id', None)
        
        # If no tenant (shouldn't happen if auth middleware works), use IP-based limiting
        if not tenant_id:
            client_ip = request.client.host if request.client else "unknown"
            key = f"rate_limit:ip:{client_ip}"
            limit = 10  # Strict limit for unauthenticated requests
        else:
            key = f"rate_limit:tenant:{tenant_id}"
            limit = await self._get_tenant_rate_limit(tenant_id)
        
        # Check if request is allowed
        try:
            redis_client = await self._get_redis()
            allowed, info = await self._is_allowed(redis_client, key, limit)
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for {key}. "
                    f"Limit: {limit}, Path: {request.url.path}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(max(1, info["reset"] - int(time.time())))
                    }
                )
            
            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset"])
            return response
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request if rate limiting service is unavailable
            return await call_next(request)