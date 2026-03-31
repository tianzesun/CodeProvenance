"""
Rate limiting middleware for API requests.

Provides configurable rate limiting per tenant to prevent abuse
and ensure fair resource usage.
"""

from fastapi import Request, HTTPException, status
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time
import threading


class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    
    Tracks requests per tenant and enforces limits:
    - Requests per minute
    - Requests per hour
    - Requests per day
    """
    
    def __init__(self, 
                 requests_per_minute: int = 60,
                 requests_per_hour: int = 1000,
                 requests_per_day: int = 10000):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per tenant
            requests_per_hour: Maximum requests per hour per tenant
            requests_per_day: Maximum requests per day per tenant
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        
        # Track requests: tenant_id -> list of timestamps
        self.request_counts: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()
    
    def check_rate_limit(self, tenant_id: str, request: Request) -> None:
        """
        Check if request exceeds rate limit for tenant.
        
        Args:
            tenant_id: Tenant identifier
            request: FastAPI request object
            
        Raises:
            HTTPException: If rate limit exceeded (429)
        """
        now = time.time()
        
        with self.lock:
            # Clean old entries
            self._clean_old_entries(tenant_id, now)
            
            # Check minute limit
            minute_count = self._count_requests_in_window(
                tenant_id, now - 60
            )
            if minute_count >= self.requests_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {self.requests_per_minute}/minute",
                        "retry_after": 60
                    }
                )
            
            # Check hour limit
            hour_count = self._count_requests_in_window(
                tenant_id, now - 3600
            )
            if hour_count >= self.requests_per_hour:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {self.requests_per_hour}/hour",
                        "retry_after": 3600
                    }
                )
            
            # Check day limit
            day_count = self._count_requests_in_window(
                tenant_id, now - 86400
            )
            if day_count >= self.requests_per_day:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {self.requests_per_day}/day",
                        "retry_after": 86400
                    }
                )
            
            # Record this request
            self.request_counts[tenant_id].append(now)
    
    def _count_requests_in_window(self, tenant_id: str, since: float) -> int:
        """Count requests since given timestamp."""
        return sum(
            1 for ts in self.request_counts[tenant_id]
            if ts > since
        )
    
    def _clean_old_entries(self, tenant_id: str, now: float):
        """Remove requests older than 24 hours."""
        cutoff = now - 86400
        self.request_counts[tenant_id] = [
            ts for ts in self.request_counts[tenant_id]
            if ts > cutoff
        ]
    
    def get_remaining(self, tenant_id: str) -> Dict[str, int]:
        """
        Get remaining requests for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dict with remaining request counts
        """
        now = time.time()
        
        with self.lock:
            self._clean_old_entries(tenant_id, now)
            
            minute_used = self._count_requests_in_window(tenant_id, now - 60)
            hour_used = self._count_requests_in_window(tenant_id, now - 3600)
            day_used = self._count_requests_in_window(tenant_id, now - 86400)
            
            return {
                "minute": {
                    "used": minute_used,
                    "remaining": max(0, self.requests_per_minute - minute_used),
                    "limit": self.requests_per_minute
                },
                "hour": {
                    "used": hour_used,
                    "remaining": max(0, self.requests_per_hour - hour_used),
                    "limit": self.requests_per_hour
                },
                "day": {
                    "used": day_used,
                    "remaining": max(0, self.requests_per_day - day_used),
                    "limit": self.requests_per_day
                }
            }
    
    def reset(self, tenant_id: str):
        """Reset rate limit for a tenant."""
        with self.lock:
            if tenant_id in self.request_counts:
                del self.request_counts[tenant_id]


# Singleton instance
rate_limiter = RateLimiter()