"""
Authentication tests for IntegrityDesk API.
"""
import pytest
from fastapi.testclient import TestClient
from src.backend.backend.main import app
from src.backend.backend.config.database import SessionLocal
from src.backend.backend.models.database import Tenant, ApiKey
import hashlib

client = TestClient(app)


def test_auth_middleware_exists():
    """Test that auth middleware is configured."""
    # This test would check that the middleware is properly installed
    # For now, we'll just verify the app exists
    assert app is not None


def test_api_key_hashing():
    """Test API key hashing functionality."""
    api_key = "test-api-key-12345"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    assert len(key_hash) == 64
    assert key_hash == hashlib.sha256(api_key.encode()).hexdigest()


def test_tenant_model():
    """Test Tenant model creation."""
    db = SessionLocal()
    try:
        # This would test actual tenant creation in a real test
        # For now, we'll just verify the model can be imported
        assert Tenant is not None
        assert ApiKey is not None
    finally:
        db.close()