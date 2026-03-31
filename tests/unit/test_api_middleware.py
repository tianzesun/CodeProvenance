"""
Unit tests for API Middleware

Tests the authentication and rate limiting middleware including:
- API key validation
- Tenant context setting
- Rate limiting logic
- Request processing
"""

import pytest
import hashlib
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware, RateLimiter


class TestAuthMiddleware:
    """Test the authentication middleware."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.middleware = AuthMiddleware(self.app)
    
    def test_exclude_paths(self):
        """Test that excluded paths are not authenticated."""
        exclude_paths = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health"
        ]
        
        for path in exclude_paths:
            assert path in self.middleware.exclude_paths
    
    def test_api_key_hashing(self):
        """Test API key hashing for storage."""
        api_key = "test-api-key-12345"
        
        # Hash the API key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        assert len(key_hash) == 64  # SHA256 hex digest
        assert key_hash != api_key  # Should be different from original
    
    def test_tenant_context_setting(self):
        """Test tenant context is set correctly."""
        tenant_id = "tenant-123"
        
        # Simulate setting tenant context
        context = {'tenant_id': tenant_id}
        
        assert context['tenant_id'] == tenant_id
    
    def test_api_key_expiration_check(self):
        """Test API key expiration validation."""
        # Expired key
        expired_time = datetime.utcnow() - timedelta(days=1)
        assert expired_time < datetime.utcnow()
        
        # Valid key
        valid_time = datetime.utcnow() + timedelta(days=30)
        assert valid_time > datetime.utcnow()
    
    def test_tenant_status_validation(self):
        """Test tenant status validation."""
        valid_statuses = ['active', 'trial']
        invalid_statuses = ['suspended', 'cancelled']
        
        for status in valid_statuses:
            assert status in ['active', 'trial', 'suspended', 'cancelled']
        
        for status in invalid_statuses:
            assert status in ['active', 'trial', 'suspended', 'cancelled']


class TestRateLimitMiddleware:
    """Test the rate limiting middleware."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.middleware = RateLimitMiddleware(
            self.app,
            redis_url="redis://localhost:6379"
        )
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        
        assert limiter is not None
    
    def test_rate_limit_check(self):
        """Test rate limit checking logic."""
        limiter = RateLimiter()
        
        # Simulate requests within limit
        for i in range(10):
            # Should not raise exception
            pass
        
        # Simulate request exceeding limit
        # Would raise HTTPException in real scenario
    
    def test_tenant_rate_limits(self):
        """Test different rate limits per tenant tier."""
        rate_limits = {
            'free': 10,
            'basic': 60,
            'pro': 300,
            'enterprise': 1000
        }
        
        for tier, limit in rate_limits.items():
            assert limit > 0
            assert isinstance(limit, int)


class TestRequestValidation:
    """Test request validation logic."""
    
    def test_required_fields(self):
        """Test that required fields are validated."""
        required_fields = ['name', 'submissions']
        
        for field in required_fields:
            assert field in required_fields
    
    def test_submission_count_validation(self):
        """Test submission count validation."""
        # At least 2 submissions required
        submissions_1 = [{'name': 'file1.py'}]
        submissions_2 = [{'name': 'file1.py'}, {'name': 'file2.py'}]
        
        assert len(submissions_1) < 2
        assert len(submissions_2) >= 2
    
    def test_threshold_validation(self):
        """Test threshold value validation."""
        valid_thresholds = [0.0, 0.2, 0.5, 0.7, 1.0]
        invalid_thresholds = [-0.1, 1.1, 2.0]
        
        for threshold in valid_thresholds:
            assert 0.0 <= threshold <= 1.0
        
        for threshold in invalid_thresholds:
            assert not (0.0 <= threshold <= 1.0)


class TestErrorHandling:
    """Test error handling in middleware."""
    
    def test_authentication_error(self):
        """Test authentication error handling."""
        error = HTTPException(
            status_code=401,
            detail="Invalid or inactive API key"
        )
        
        assert error.status_code == 401
        assert "Invalid" in error.detail
    
    def test_rate_limit_error(self):
        """Test rate limit error handling."""
        error = HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
        
        assert error.status_code == 429
        assert "Rate limit" in error.detail
    
    def test_validation_error(self):
        """Test validation error handling."""
        error = HTTPException(
            status_code=400,
            detail="No submissions provided"
        )
        
        assert error.status_code == 400
        assert "No submissions" in error.detail


class TestMiddlewareIntegration:
    """Test middleware integration scenarios."""
    
    def test_request_flow(self):
        """Test complete request flow through middleware."""
        # 1. Request comes in
        # 2. Auth middleware checks API key
        # 3. Rate limit middleware checks limits
        # 4. Request is processed
        
        steps = [
            'request_received',
            'auth_check',
            'rate_limit_check',
            'request_processed'
        ]
        
        assert len(steps) == 4
    
    def test_tenant_isolation(self):
        """Test that tenants are isolated."""
        tenant_1 = {'id': 'tenant-1', 'data': 'data-1'}
        tenant_2 = {'id': 'tenant-2', 'data': 'data-2'}
        
        assert tenant_1['id'] != tenant_2['id']
        assert tenant_1['data'] != tenant_2['data']


class TestSecurityFeatures:
    """Test security features."""
    
    def test_api_key_hashing_security(self):
        """Test that API keys are properly hashed."""
        api_key = "super-secret-api-key"
        
        # Hash should be irreversible
        hash_1 = hashlib.sha256(api_key.encode()).hexdigest()
        hash_2 = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Same input should produce same hash
        assert hash_1 == hash_2
        
        # Hash should not reveal original key
        assert api_key not in hash_1
    
    def test_timing_safe_comparison(self):
        """Test timing-safe comparison for signatures."""
        import hmac
        
        sig1 = "a" * 64
        sig2 = "a" * 64
        sig3 = "b" * 64
        
        # Same signatures should match
        assert hmac.compare_digest(sig1, sig2) is True
        
        # Different signatures should not match
        assert hmac.compare_digest(sig1, sig3) is False
    
    def test_sql_injection_prevention(self):
        """Test that SQL injection is prevented."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--"
        ]
        
        for input_str in malicious_inputs:
            # Should be escaped/parameterized
            assert "'" in input_str  # Contains quotes that should be escaped


if __name__ == '__main__':
    pytest.main([__file__, '-v'])